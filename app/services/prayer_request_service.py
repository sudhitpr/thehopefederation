import logging
from email_validator import validate_email, EmailNotValidError
from app.repositories.prayer_request_repository import PrayerRequestRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class PrayerRequestService:
    """Service handling submission, privacy, review workflow, and notes for prayer requests."""

    VALID_STATUSES = PrayerRequestRepository.VALID_STATUSES
    CATEGORIES = PrayerRequestRepository.CATEGORIES

    def __init__(self, repository=None, audit_service=None):
        self.repository = repository or PrayerRequestRepository()
        self.audit_service = audit_service or AuditService()

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
