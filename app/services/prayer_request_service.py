import logging
from datetime import datetime, timezone
from email_validator import validate_email, EmailNotValidError
from app.repositories.prayer_request_repository import PrayerRequestRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class PrayerRequestService:
    """Service handling submission, privacy, review workflow, and notes for prayer requests."""

    VALID_STATUSES = PrayerRequestRepository.VALID_STATUSES
    CATEGORIES = PrayerRequestRepository.CATEGORIES

    def __init__(self, repository=None, audit_service=None, email_service=None):
        self.repository = repository or PrayerRequestRepository()
        self.audit_service = audit_service or AuditService()
        self.email_service = email_service  # created lazily (needs app context)

    def validate_submission(self, data):
        """
        Validate prayer request submission.
        Returns: (cleaned_dict, error_message)
        """
        errors = []
        cleaned = {}

        # 1. Prayer text (mandatory)
        text = str(data.get("request_text", "")).strip()
        if not text:
            errors.append("Prayer request content cannot be empty.")
        cleaned["request_text"] = text

        # 2. Category
        cat = str(data.get("category", "Other")).strip()
        if cat not in self.CATEGORIES:
            cat = "Other"
        cleaned["category"] = cat

        # 3. Anonymous option
        is_anon = str(data.get("is_anonymous", "")).lower() in ("true", "1", "yes", "on")
        cleaned["is_anonymous"] = is_anon

        # 4. Contact details
        if is_anon:
            cleaned["name"] = "Anonymous"
            cleaned["email"] = ""
            cleaned["phone"] = ""
            cleaned["preferred_contact"] = "None"
        else:
            name = str(data.get("name", "")).strip()
            cleaned["name"] = name or "Friend in Need"
            
            email = str(data.get("email", "")).strip().lower()
            if email:
                try:
                    valid_info = validate_email(email, check_deliverability=False)
                    cleaned["email"] = valid_info.normalized
                except EmailNotValidError:
                    errors.append(f"'{email}' is not a valid email address.")
                    cleaned["email"] = email
            else:
                cleaned["email"] = ""

            cleaned["phone"] = str(data.get("phone", "")).strip()
            cleaned["preferred_contact"] = str(data.get("preferred_contact", "None")).strip()

        if errors:
            return None, " ".join(errors)

        return cleaned, None

    def create_request(self, data, actor_user=None):
        """Validate and insert a new prayer request."""
        cleaned, err = self.validate_submission(data)
        if err:
            return None, err

        doc = self.repository.create(cleaned)

        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="PRAYER_REQUEST_CREATED",
            module="PRAYER_REQUESTS",
            admin_user_id=actor_id,
            record_id=doc["_id"],
            context={
                "category": doc["category"],
                "is_anonymous": doc["is_anonymous"]
            }
        )
        return doc, None

    def get_requests(self, page=1, per_page=15, status=None, category=None, search=None, start_date=None, end_date=None, sort_field="created_at", sort_dir=-1):
        """Retrieve paginated and filtered prayer requests."""
        skip = (page - 1) * per_page
        items = self.repository.list_requests(
            skip=skip,
            limit=per_page,
            status=status,
            category=category,
            search=search,
            start_date=start_date,
            end_date=end_date,
            sort_field=sort_field,
            sort_dir=sort_dir
        )
        total = self.repository.count(
            status=status,
            category=category,
            search=search,
            start_date=start_date,
            end_date=end_date
        )
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    def get_by_id(self, req_id):
        """Retrieve single prayer request by ID."""
        return self.repository.find_by_id(req_id)

    def update_status(self, req_id, new_status, actor_user):
        """Update workflow status (new -> in_review -> praying -> completed -> archived)."""
        new_status = new_status.lower().strip()
        if new_status not in self.VALID_STATUSES:
            return None, f"Invalid status '{new_status}'."

        existing = self.repository.find_by_id(req_id)
        if not existing:
            return None, "Prayer request not found."

        old_status = existing.get("status")
        updated = self.repository.update(req_id, {"status": new_status})

        self.audit_service.record_action(
            action="PRAYER_REQUEST_STATUS_CHANGED",
            module="PRAYER_REQUESTS",
            admin_user_id=actor_user.id if actor_user else None,
            record_id=req_id,
            context={"old_status": old_status, "new_status": new_status, "category": existing.get("category")}
        )
        return updated, None

    def parse_scheduled_datetime(self, val):
        """
        Parse datetime from string, ISO format, or return datetime object.
        Returns: (parsed_datetime, error_message)
        """
        if val is None or (isinstance(val, str) and not val.strip()):
            return None, None

        if isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            return val, None

        if isinstance(val, str):
            val_str = val.strip()
            formats = [
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %I:%M %p",
                "%Y-%m-%dT%I:%M %p",
                "%Y-%m-%d %I:%M%p",
                "%m/%d/%Y %I:%M %p",
                "%m/%d/%Y %H:%M",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(val_str, fmt)
                    return dt.replace(tzinfo=timezone.utc), None
                except ValueError:
                    continue

            try:
                dt = datetime.fromisoformat(val_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt, None
            except (ValueError, TypeError):
                pass

        return None, "Invalid date and time format. Please provide a valid schedule."

    def schedule_request(self, req_id, scheduled_at, actor_user=None, notify=True):
        """
        Assign, edit, reschedule, or clear the scheduled date and time for a prayer request.

        After the schedule is saved, the requester is notified by email (best effort).
        The outcome is returned on the updated document under ``schedule_notification``;
        an email failure never rolls back or blocks the saved schedule.
        """
        existing = self.repository.find_by_id(req_id)
        if not existing:
            return None, "Prayer request not found."

        if scheduled_at is None or (isinstance(scheduled_at, str) and not scheduled_at.strip()):
            scheduled_dt = None
        else:
            scheduled_dt, err = self.parse_scheduled_datetime(scheduled_at)
            if err:
                return None, err

        old_scheduled = existing.get("scheduled_at")
        updated = self.repository.schedule(req_id, scheduled_dt)
        if not updated:
            return None, "Unable to save the schedule. Please try again."

        if scheduled_dt is None:
            action = "PRAYER_REQUEST_SCHEDULE_CLEARED"
            change_type = "cleared"
        elif old_scheduled is not None:
            action = "PRAYER_REQUEST_RESCHEDULED"
            change_type = "rescheduled"
        else:
            action = "PRAYER_REQUEST_SCHEDULED"
            change_type = "scheduled"

        self.audit_service.record_action(
            action=action,
            module="PRAYER_REQUESTS",
            admin_user_id=actor_user.id if actor_user else None,
            record_id=req_id,
            context={
                "previous_scheduled_at": old_scheduled.isoformat() if isinstance(old_scheduled, datetime) else None,
                "scheduled_at": scheduled_dt.isoformat() if scheduled_dt else None,
                "category": existing.get("category"),
            }
        )

        if notify:
            updated["schedule_notification"] = self.send_schedule_notification(
                updated, change_type, old_scheduled, actor_user=actor_user
            )
        return updated, None

    # ------------------------------------------------------------------
    # Email notifications
    # ------------------------------------------------------------------
    @staticmethod
    def _naive(dt):
        """Drop tzinfo so values read from MongoDB (naive) and parsed values (aware) compare safely."""
        return dt.replace(tzinfo=None) if isinstance(dt, datetime) else None

    @staticmethod
    def _format_date(dt):
        return dt.strftime("%A, %d %B %Y") if isinstance(dt, datetime) else ""

    @staticmethod
    def _format_time(dt):
        return dt.strftime("%I:%M %p").lstrip("0") if isinstance(dt, datetime) else ""

    def send_schedule_notification(self, req, change_type, previous_dt=None, actor_user=None):
        """
        Email the requester about a scheduled / rescheduled / cleared prayer session.
        Never raises. Returns a dict: {"status": ..., "change_type": ..., "error": ...}.
        """
        req_id = req.get("_id")
        result = {"status": "skipped", "change_type": change_type, "error": None}

        try:
            new_dt = self._naive(req.get("scheduled_at"))
            prev_dt = self._naive(previous_dt)

            # Nothing actually changed -> do not email the requester
            if change_type == "cleared" and prev_dt is None:
                result["error"] = "no_change"
                return result
            if change_type == "rescheduled" and prev_dt == new_dt:
                result["error"] = "no_change"
                return result

            recipient = (req.get("email") or "").strip()
            if req.get("is_anonymous") or not recipient:
                result["error"] = "no_email"
                logger.info("Prayer request %s has no email address; schedule notification skipped.", req_id)
                return result

            from flask import current_app, render_template
            from app.services.email_service import EmailService, mask_email

            cfg = current_app.config
            org_name = cfg.get("MAIL_SENDER_NAME") or "The Hope Federation"
            subjects = {
                "scheduled": "Your prayer request has been scheduled",
                "rescheduled": "Your prayer session has been rescheduled",
                "cleared": "Your scheduled prayer session has been cancelled",
            }
            subject = f"{subjects.get(change_type, subjects['scheduled'])} - {org_name}"

            context = {
                "subject": subject,
                "change_type": change_type,
                "name": req.get("name") or "Friend",
                "reference": f"PR-{str(req_id)[-6:].upper()}" if req_id else "",
                "category": req.get("category") or "",
                "date_str": self._format_date(new_dt),
                "time_str": self._format_time(new_dt),
                "previous_date_str": self._format_date(prev_dt),
                "previous_time_str": self._format_time(prev_dt),
                "timezone_label": cfg.get("SCHEDULE_TIMEZONE_LABEL") or "IST (Indian Standard Time)",
                "org_name": org_name,
                "contact_email": cfg.get("MAIL_REPLY_TO") or cfg.get("MAIL_DEFAULT_SENDER") or "",
            }
            text_body = render_template("emails/prayer_schedule_notification.txt", **context)
            html_body = render_template("emails/prayer_schedule_notification.html", **context)

            email_service = self.email_service or EmailService()
            outcome = email_service.send(recipient, subject, text_body, html_body)
            result["status"] = outcome.status
            result["error"] = outcome.error

            if outcome.status in ("sent", "failed", "not_configured", "invalid_recipient"):
                self.audit_service.record_action(
                    action="PRAYER_SCHEDULE_EMAIL_SENT" if outcome.sent else "PRAYER_SCHEDULE_EMAIL_FAILED",
                    module="PRAYER_REQUESTS",
                    admin_user_id=actor_user.id if actor_user else None,
                    record_id=req_id,
                    context={
                        "change_type": change_type,
                        "recipient": mask_email(recipient),
                        "status": outcome.status,
                        "error": outcome.error,
                    },
                )
        except Exception as exc:  # an email problem must never affect the saved schedule
            logger.exception("Unexpected error preparing schedule notification for prayer request %s: %s",
                             req_id, type(exc).__name__)
            result["status"] = "failed"
            result["error"] = "unexpected_error"

        self._record_notification(req_id, result)
        return result

    def _record_notification(self, req_id, result):
        """Persist the last notification outcome on the prayer request (best effort)."""
        if not req_id:
            return
        try:
            self.repository.set_schedule_notification(req_id, {
                "status": result.get("status"),
                "change_type": result.get("change_type"),
                "error": result.get("error"),
                "attempted_at": datetime.now(timezone.utc),
            })
        except Exception as exc:
            logger.error("Could not record schedule notification status for prayer request %s: %s",
                         req_id, type(exc).__name__)

    def add_admin_note(self, req_id, note_text, actor_user):
        """Append an internal confidential note to the prayer request."""
        if not note_text or not note_text.strip():
            return None, "Note content cannot be empty."

        existing = self.repository.find_by_id(req_id)
        if not existing:
            return None, "Prayer request not found."

        note_entry = {
            "note": note_text.strip(),
            "author_id": actor_user.id if actor_user else None,
            "author_name": actor_user.name or actor_user.email if actor_user else "Admin",
        }
        updated = self.repository.add_note(req_id, note_entry)

        self.audit_service.record_action(
            action="PRAYER_REQUEST_NOTE_ADDED",
            module="PRAYER_REQUESTS",
            admin_user_id=actor_user.id if actor_user else None,
            record_id=req_id,
            context={"note_snippet": note_text[:60]}
        )
        return updated, None

    def archive_request(self, req_id, actor_user):
        """Archive a prayer request."""
        return self.update_status(req_id, "archived", actor_user)

    def delete_request(self, req_id, actor_user):
        """Permanently delete prayer request (restricted to Super Admin)."""
        if not actor_user or actor_user.role != "Super Admin":
            return False, "Only Super Administrators can permanently delete prayer requests."

        existing = self.repository.find_by_id(req_id)
        if not existing:
            return False, "Prayer request not found."

        success = self.repository.delete(req_id)
        if success:
            self.audit_service.record_action(
                action="PRAYER_REQUEST_DELETED",
                module="PRAYER_REQUESTS",
                admin_user_id=actor_user.id,
                record_id=req_id,
                context={"category": existing.get("category")}
            )
        return success, None
