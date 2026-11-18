"""
Hourly upcoming prayer request reminder service.

Finds confirmed/scheduled prayer requests taking place within the upcoming
lookahead window (default: 60 minutes) in the configured application timezone,
sends reminder emails via the existing EmailService, and tracks delivery state
on each document to prevent duplicate reminders.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, render_template
from pymongo.errors import PyMongoError

from app.repositories.prayer_request_repository import PrayerRequestRepository
from app.services.audit_service import AuditService
from app.services.email_service import EmailService, mask_email

logger = logging.getLogger(__name__)

# If a worker crashed mid-send, allow another run to reclaim after this many minutes
CLAIM_STALE_MINUTES = 15


def resolve_schedule_timezone(tz_name):
    """Resolve an IANA timezone name (default Asia/Kolkata) with safe fallback."""
    name = (tz_name or "Asia/Kolkata").strip()
    try:
        return ZoneInfo(name), name
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        if name.lower() in ("asia/kolkata", "asia/calcutta", "ist"):
            logger.warning("IANA tzdata not found for '%s'; falling back to fixed UTC+05:30.", name)
            return timezone(timedelta(hours=5, minutes=30)), name
        logger.warning("Unknown timezone '%s'; falling back to UTC.", name)
        return timezone.utc, "UTC"


class PrayerReminderService:
    """Service responsible for sending upcoming prayer session reminder emails."""

    def __init__(self, repository=None, email_service=None, audit_service=None):
        self.repository = repository or PrayerRequestRepository()
        self.email_service = email_service  # created lazily from current_app.config
        self.audit_service = audit_service or AuditService()

    @staticmethod
    def _naive(dt):
        """Drop tzinfo so datetimes read from MongoDB and parsed values compare safely."""
        return dt.replace(tzinfo=None) if isinstance(dt, datetime) else None

    @staticmethod
    def _format_date(dt):
        return dt.strftime("%A, %d %B %Y") if isinstance(dt, datetime) else ""

    @staticmethod
    def _format_time(dt):
        return dt.strftime("%I:%M %p").lstrip("0") if isinstance(dt, datetime) else ""

    @classmethod
    def _already_reminded(cls, req):
        """Return True if a reminder was already sent for this exact scheduled_at value."""
        if req.get("reminder_sent") is not True:
            return False
        return cls._naive(req.get("reminder_sent_for")) == cls._naive(req.get("scheduled_at"))

    def _render_reminder(self, req, cfg):
        """Render subject, plain-text body, and HTML body for a reminder email."""
        req_id = req.get("_id")
        sched_dt = self._naive(req.get("scheduled_at"))
        org_name = cfg.get("MAIL_SENDER_NAME") or "The Hope Federation"
        subject = f"Reminder: Your prayer session is coming up soon - {org_name}"

        context = {
            "subject": subject,
            "name": req.get("name") or "Friend",
            "reference": f"PR-{str(req_id)[-6:].upper()}" if req_id else "",
            "category": req.get("category") or "",
            "date_str": self._format_date(sched_dt),
            "time_str": self._format_time(sched_dt),
            "timezone_label": cfg.get("SCHEDULE_TIMEZONE_LABEL") or "IST (Indian Standard Time)",
            "org_name": org_name,
            "contact_email": cfg.get("MAIL_REPLY_TO") or cfg.get("MAIL_DEFAULT_SENDER") or "",
        }
        text_body = render_template("emails/prayer_reminder.txt", **context)
        html_body = render_template("emails/prayer_reminder.html", **context)
        return subject, text_body, html_body

    def run(self, now=None, window_minutes=None, dry_run=False):
        """
        Check MongoDB for prayer requests scheduled within the next `window_minutes`
        and send one reminder email per upcoming request.

        Args:
            now: Optional datetime override (aware, or naive treated as UTC) for testing.
            window_minutes: Lookahead window in minutes (defaults to PRAYER_REMINDER_WINDOW_MINUTES / 60).
            dry_run: When True, logs matching requests without sending emails or updating MongoDB.

        Returns:
            dict with execution summary and status:
              - "completed": ran cleanly with zero email failures
              - "completed_with_errors": ran cleanly, but one or more individual emails failed
              - "skipped_disabled": MAIL_ENABLED is False (no emails attempted)
              - "db_error": could not query MongoDB
        """
        started_perf = time.perf_counter()
        cfg = current_app.config

        if window_minutes is None:
            window_minutes = int(cfg.get("PRAYER_REMINDER_WINDOW_MINUTES", 60) or 60)
        if window_minutes <= 0:
            raise ValueError("window_minutes must be a positive integer.")

        tz, tz_name = resolve_schedule_timezone(cfg.get("SCHEDULE_TIMEZONE", "Asia/Kolkata"))
        if now is None:
            now_utc = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now_utc = now.replace(tzinfo=timezone.utc)
        else:
            now_utc = now.astimezone(timezone.utc)

        now_local = now_utc.astimezone(tz)
        # PrayerRequestService stores admin-entered wall-clock times directly in scheduled_at
        window_start = now_local.replace(tzinfo=None)
        window_end = window_start + timedelta(minutes=window_minutes)

        summary = {
            "status": "completed",
            "started_at": now_local.isoformat(),
            "timezone": tz_name,
            "window_start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
            "window_end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": bool(dry_run),
            "found": 0,
            "already_reminded": 0,
            "pending": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "error": None,
            "duration_ms": 0,
        }

        logger.info(
            "Prayer reminder job started at %s (%s). Checking window [%s .. %s]%s.",
            summary["started_at"],
            tz_name,
            summary["window_start"],
            summary["window_end"],
            " [DRY RUN]" if dry_run else "",
        )

        try:
            upcoming = self.repository.find_upcoming_scheduled(window_start, window_end)
        except PyMongoError as exc:
            summary["status"] = "db_error"
            summary["error"] = type(exc).__name__
            summary["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 1)
            logger.error("Prayer reminder job failed while querying MongoDB: %s", type(exc).__name__)
            return summary
        except Exception as exc:
            summary["status"] = "db_error"
            summary["error"] = type(exc).__name__
            summary["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 1)
            logger.exception("Prayer reminder job encountered an unexpected database error: %s", type(exc).__name__)
            return summary

        pending = []
        for req in upcoming:
            if self._already_reminded(req):
                summary["already_reminded"] += 1
            else:
                pending.append(req)

        summary["found"] = len(upcoming)
        summary["pending"] = len(pending)

        logger.info(
            "Found %d upcoming scheduled prayer request(s) in window (%d pending reminder, %d already reminded).",
            summary["found"],
            summary["pending"],
            summary["already_reminded"],
        )

        if not pending:
            summary["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 1)
            logger.info(
                "Prayer reminder job finished (status=%s, duration=%sms).",
                summary["status"],
                summary["duration_ms"],
            )
            return summary

        email_service = self.email_service or EmailService(cfg)

        if not dry_run and not email_service.is_enabled():
            summary["status"] = "skipped_disabled"
            summary["skipped"] = len(pending)
            summary["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 1)
            logger.warning(
                "MAIL_ENABLED is off; skipped sending %d upcoming prayer reminder(s).",
                len(pending),
            )
            return summary

        stale_before = now_utc - timedelta(minutes=CLAIM_STALE_MINUTES)

        for req in pending:
            req_id = req.get("_id")
            sched_raw = req.get("scheduled_at")
            recipient = (req.get("email") or "").strip()

            if req.get("is_anonymous") or not recipient:
                summary["skipped"] += 1
                logger.info("Skipping prayer request %s: anonymous or empty email.", req_id)
                continue

            if dry_run:
                summary["skipped"] += 1
                logger.info(
                    "[DRY RUN] Would send reminder for prayer request %s (scheduled %s) to %s.",
                    req_id,
                    self._naive(sched_raw).strftime("%Y-%m-%d %H:%M") if isinstance(sched_raw, datetime) else sched_raw,
                    mask_email(recipient),
                )
                continue

            claimed = False
            try:
                claimed = self.repository.claim_reminder(
                    req_id=req_id,
                    scheduled_at=sched_raw,
                    claimed_at=now_utc,
                    stale_before=stale_before,
                )
                if not claimed:
                    summary["skipped"] += 1
                    logger.info(
                        "Skipping prayer request %s: reminder already sent or in progress.",
                        req_id,
                    )
                    continue

                subject, text_body, html_body = self._render_reminder(req, cfg)
                outcome = email_service.send(recipient, subject, text_body, html_body)
                attempt_time = datetime.now(timezone.utc)

                if outcome.sent:
                    self.repository.mark_reminder_sent(req_id, sched_raw, attempt_time)
                    self.audit_service.record_action(
                        action="PRAYER_REMINDER_EMAIL_SENT",
                        module="PRAYER_REQUESTS",
                        admin_user_id=None,
                        record_id=req_id,
                        context={
                            "recipient": mask_email(recipient),
                            "scheduled_at": sched_raw.isoformat() if isinstance(sched_raw, datetime) else None,
                            "status": outcome.status,
                        },
                    )
                    summary["sent"] += 1
                    logger.info(
                        "Reminder email sent for prayer request %s to %s.",
                        req_id,
                        mask_email(recipient),
                    )
                else:
                    self.repository.mark_reminder_failed(
                        req_id=req_id,
                        scheduled_at=sched_raw,
                        status=outcome.status,
                        error=outcome.error,
                        attempted_at=attempt_time,
                    )
                    self.audit_service.record_action(
                        action="PRAYER_REMINDER_EMAIL_FAILED",
                        module="PRAYER_REQUESTS",
                        admin_user_id=None,
                        record_id=req_id,
                        context={
                            "recipient": mask_email(recipient),
                            "scheduled_at": sched_raw.isoformat() if isinstance(sched_raw, datetime) else None,
                            "status": outcome.status,
                            "error": outcome.error,
                        },
                    )
                    summary["failed"] += 1
                    logger.error(
                        "Reminder email failed for prayer request %s to %s (status=%s, error=%s).",
                        req_id,
                        mask_email(recipient),
                        outcome.status,
                        outcome.error,
                    )
            except Exception as exc:
                summary["failed"] += 1
                logger.exception(
                    "Unexpected error processing reminder for prayer request %s: %s",
                    req_id,
                    type(exc).__name__,
                )
                if claimed:
                    try:
                        self.repository.release_reminder_claim(req_id)
                    except Exception as release_exc:
                        logger.error(
                            "Could not release reminder claim for prayer request %s: %s",
                            req_id,
                            type(release_exc).__name__,
                        )

        if summary["failed"] > 0:
            summary["status"] = "completed_with_errors"

        summary["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 1)
        logger.info(
            "Prayer reminder job finished: status=%s, found=%d, pending=%d, sent=%d, failed=%d, skipped=%d, duration=%sms.",
            summary["status"],
            summary["found"],
            summary["pending"],
            summary["sent"],
            summary["failed"],
            summary["skipped"],
            summary["duration_ms"],
        )
        return summary
