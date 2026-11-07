import logging
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    """Service handling audit logs for all administrative actions."""

    def __init__(self, repository=None):
        self.repository = repository or AuditRepository()

    def record_action(self, action, module, admin_user_id=None, record_id=None, context=None):
        """Record an administrative action to the audit collection."""
        try:
            return self.repository.log(
                action=action,
                module=module,
                admin_user_id=admin_user_id,
                record_id=record_id,
                context=context,
            )
        except Exception as err:
            logger.error("Failed to write audit log (%s on %s): %s", action, module, err)
            return None

    def get_logs(self, page=1, per_page=20, module=None, action=None, admin_user_id=None):
        """Retrieve paginated audit logs."""
        skip = (page - 1) * per_page
        logs = self.repository.list_logs(
            skip=skip,
            limit=per_page,
            module=module,
            action=action,
            admin_user_id=admin_user_id,
        )
        total = self.repository.count(
            module=module,
            action=action,
            admin_user_id=admin_user_id,
        )
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        return {
            "items": logs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
