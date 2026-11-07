from datetime import datetime, timezone
from bson import ObjectId
from app.database import get_db


class AuditRepository:
    """Repository handling audit log records."""

    def __init__(self, db=None):
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else get_db()
        return db["audit_logs"]

    def log(self, action, module, admin_user_id=None, record_id=None, context=None):
        """Create an audit log entry."""
        entry = {
            "action": action,
            "module": module,
            "admin_user_id": str(admin_user_id) if admin_user_id else None,
            "record_id": str(record_id) if record_id else None,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(entry)
        entry["_id"] = result.inserted_id
        return entry

    def list_logs(self, skip=0, limit=50, module=None, action=None, admin_user_id=None):
        """List audit logs sorted by newest first."""
        query = {}
        if module:
            query["module"] = module
        if action:
            query["action"] = action
        if admin_user_id:
            query["admin_user_id"] = str(admin_user_id)

        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        return list(cursor)

    def count(self, module=None, action=None, admin_user_id=None):
        """Count audit logs matching query."""
        query = {}
        if module:
            query["module"] = module
        if action:
            query["action"] = action
        if admin_user_id:
            query["admin_user_id"] = str(admin_user_id)
        if not query:
            try:
                return self.collection.estimated_document_count()
            except Exception:
                pass
        return self.collection.count_documents(query)
