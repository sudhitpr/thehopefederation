import logging
import re
from email_validator import validate_email, EmailNotValidError
from app.repositories.registration_repository import RegistrationRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class RegistrationService:
    """Business logic and validation service for volunteer and partner registrations."""

    VALID_TYPES = RegistrationRepository.VALID_TYPES
    VALID_STATUSES = RegistrationRepository.VALID_STATUSES

    def __init__(self, repository=None, audit_service=None):
        self.repository = repository or RegistrationRepository()
        self.audit_service = audit_service or AuditService()

    def validate_submission(self, data):
        """
        Server-side validation for volunteer and partner registrations.
        Returns: (cleaned_dict, error_message)
        """
        errors = []
        cleaned = {}

        # 1. Registration Type
        reg_type = str(data.get("registration_type", "")).lower().strip()
        if reg_type not in self.VALID_TYPES:
            reg_type = "volunteer"
        cleaned["registration_type"] = reg_type

        # 2. Name
        name = str(data.get("name", "")).strip()
        if not name:
            errors.append("Contact/Full name is required.")
        cleaned["name"] = name

        # 3. Email
        email = str(data.get("email", "")).strip().lower()
        if not email:
            errors.append("Email address is required.")
        else:
            try:
                valid_info = validate_email(email, check_deliverability=False)
                cleaned["email"] = valid_info.normalized
            except EmailNotValidError:
                errors.append(f"'{email}' is not a valid email address.")
                cleaned["email"] = email

        # 4. Phone
        phone = str(data.get("phone", "")).strip()
        if not phone:
            errors.append("Phone number is required.")
        cleaned["phone"] = phone

        # General location fields
        cleaned["address"] = str(data.get("address", "")).strip()
        cleaned["city"] = str(data.get("city", "")).strip()
        cleaned["state"] = str(data.get("state", "")).strip()
        cleaned["country"] = str(data.get("country", "")).strip()
        cleaned["message"] = str(data.get("message", "")).strip()

        # Partner-specific fields
        if reg_type == "partner":
            org_name = str(data.get("organization_name", "")).strip()
            if not org_name:
                errors.append("Organization name is required for partner registrations.")
            cleaned["organization_name"] = org_name
            cleaned["organization_type"] = str(data.get("organization_type", "")).strip()
            cleaned["website"] = str(data.get("website", "")).strip()
            cleaned["area_of_partnership"] = str(data.get("area_of_partnership", "")).strip()
            cleaned["partnership_interests"] = str(data.get("partnership_interests", "")).strip()
        else:
            # Volunteer-specific fields
            cleaned["occupation"] = str(data.get("occupation", "")).strip()
            cleaned["skills"] = str(data.get("skills", "")).strip()
            cleaned["availability"] = str(data.get("availability", "")).strip()
            cleaned["preferred_activities"] = str(data.get("preferred_activities", "")).strip()
            cleaned["date_of_birth"] = str(data.get("date_of_birth", "")).strip()
            cleaned["gender"] = str(data.get("gender", "")).strip()

        if errors:
            return None, " ".join(errors)

        return cleaned, None

    def create_registration(self, data, actor_user=None):
        """Validate and create a new registration record."""
        cleaned, err = self.validate_submission(data)
        if err:
            return None, err

        doc = self.repository.create(cleaned)
        
        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="REGISTRATION_CREATED",
            module="REGISTRATIONS",
            admin_user_id=actor_id,
            record_id=doc["_id"],
            context={
                "type": doc["registration_type"],
                "name": doc["name"],
                "email": doc["email"]
            }
        )
        return doc, None

    def get_registrations(self, page=1, per_page=15, reg_type=None, status=None, search=None, start_date=None, end_date=None, sort_field="created_at", sort_dir=-1):
        """Retrieve paginated and filtered registrations."""
        skip = (page - 1) * per_page
        items = self.repository.list_registrations(
            skip=skip,
            limit=per_page,
            reg_type=reg_type,
            status=status,
            search=search,
            start_date=start_date,
            end_date=end_date,
            sort_field=sort_field,
            sort_dir=sort_dir
        )
        total = self.repository.count(
            reg_type=reg_type,
            status=status,
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

    def get_by_id(self, reg_id):
        """Get single registration by ID."""
        return self.repository.find_by_id(reg_id)

    def update_status(self, reg_id, new_status, actor_user):
        """Update registration status with audit logging."""
        new_status = new_status.lower().strip()
        if new_status not in self.VALID_STATUSES:
            return None, f"Invalid status '{new_status}'."

        existing = self.repository.find_by_id(reg_id)
        if not existing:
            return None, "Registration not found."

        old_status = existing.get("status")
        updated = self.repository.update(reg_id, {"status": new_status})

        self.audit_service.record_action(
            action="REGISTRATION_STATUS_CHANGED",
            module="REGISTRATIONS",
            admin_user_id=actor_user.id if actor_user else None,
            record_id=reg_id,
            context={"old_status": old_status, "new_status": new_status, "email": existing.get("email")}
        )
        return updated, None

    def add_admin_note(self, reg_id, note_text, actor_user):
        """Append an internal note to the registration."""
        if not note_text or not note_text.strip():
            return None, "Note content cannot be empty."

        existing = self.repository.find_by_id(reg_id)
        if not existing:
            return None, "Registration not found."

        note_entry = {
            "note": note_text.strip(),
            "author_id": actor_user.id if actor_user else None,
            "author_name": actor_user.name or actor_user.email if actor_user else "Admin",
        }
        updated = self.repository.add_note(reg_id, note_entry)

        self.audit_service.record_action(
            action="REGISTRATION_NOTE_ADDED",
            module="REGISTRATIONS",
            admin_user_id=actor_user.id if actor_user else None,
            record_id=reg_id,
            context={"note_snippet": note_text[:60]}
        )
        return updated, None

    def delete_registration(self, reg_id, actor_user):
        """Delete registration record (restricted to Super Admin)."""
        if not actor_user or actor_user.role != "Super Admin":
            return False, "Only Super Administrators can permanently delete registrations."

        existing = self.repository.find_by_id(reg_id)
        if not existing:
            return False, "Registration not found."

        success = self.repository.delete(reg_id)
        if success:
            self.audit_service.record_action(
                action="REGISTRATION_DELETED",
                module="REGISTRATIONS",
                admin_user_id=actor_user.id,
                record_id=reg_id,
                context={"type": existing.get("registration_type"), "name": existing.get("name")}
            )
        return success, None
