#!/usr/bin/env python3
"""
Standalone hourly cron job script for upcoming Prayer Request email reminders.

Usage (local or production):
    python scripts/send_prayer_reminders.py
    python scripts/send_prayer_reminders.py --dry-run
    python scripts/send_prayer_reminders.py --window-minutes 60
    python scripts/send_prayer_reminders.py --env production --log-file /path/to/reminders.log

All database, email, and timezone settings are loaded from the active environment
and the project's .env file (never hardcoded). Safe to invoke from any working
directory via system cron or cPanel Cron Jobs.
"""
import argparse
import logging
import os
import sys

# Dynamically resolve project root relative to this script (no hardcoded paths)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

# Load .env from project root without overriding variables already set in the environment
_dotenv_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path)
else:
    load_dotenv()


def _configure_logging(log_file=None, verbose=False):
    """Configure clean, timestamped logging for cron execution."""
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    if log_file:
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Keep verbose PyMongo internal logs quiet
    for name in (
        "pymongo",
        "pymongo.topology",
        "pymongo.connection",
        "pymongo.serverSelection",
        "pymongo.command",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Send reminder emails for prayer requests scheduled within the next hour."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Identify upcoming prayer requests without sending emails or modifying the database.",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=None,
        help="Lookahead window in minutes (default: PRAYER_REMINDER_WINDOW_MINUTES or 60).",
    )
    parser.add_argument(
        "--env",
        dest="env_name",
        default=None,
        help="Optional Flask environment override (development, production, testing).",
    )
    parser.add_argument(
        "--log-file",
        default=os.environ.get("PRAYER_REMINDER_LOG_FILE") or None,
        help="Optional file path to append execution logs.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser.parse_args(argv)


def main(argv=None, app=None):
    """
    Entry point for cron execution.
    Returns exit code 0 on normal completion, or 1 on fatal/database errors.
    """
    args = _parse_args(argv)
    _configure_logging(log_file=args.log_file, verbose=args.verbose)
    logger = logging.getLogger("cron.prayer_reminders")

    if args.window_minutes is not None and args.window_minutes <= 0:
        logger.error("--window-minutes must be a positive integer.")
        return 1

    try:
        if app is None:
            from app import create_app
            app = create_app(args.env_name)

        from app.services.prayer_reminder_service import PrayerReminderService

        with app.app_context():
            service = PrayerReminderService()
            summary = service.run(
                window_minutes=args.window_minutes,
                dry_run=args.dry_run,
            )

        if summary["status"] == "db_error":
            logger.error("Cron run aborted due to database error (%s).", summary.get("error"))
            return 1

        return 0

    except Exception as exc:
        logger.exception("Fatal error running prayer reminder cron job: %s", type(exc).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
