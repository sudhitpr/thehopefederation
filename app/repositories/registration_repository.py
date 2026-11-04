from datetime import datetime, timezone
import re
from bson import ObjectId
from app.database import get_db


class RegistrationRepository:
    """Repository handling all MongoDB operations for unified volunteer & partner registrations."""

    VALID_TYPES = ["volunteer", "partner"]
    VALID_STATUSES = ["new", "contacted", "approved", "rejected", "active", "inactive"]

    def __init__(self, db=None):
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else get_db()
        return db["registrations"]

    def create(self, data):
        """Insert a new registration document."""
        now = datetime.now(timezone.utc)
        doc = dict(data)
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = now
        doc["status"] = doc.get("status", "new").lower()
        doc["notes"] = doc.get("notes", [])
        if "registration_type" not in doc or doc["registration_type"] not in self.VALID_TYPES:
            doc["registration_type"] = "volunteer"

        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_id(self, reg_id):
        """Find registration by ObjectId or string ID."""
        if not reg_id:
            return None
        try:
            oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
            return self.collection.find_one({"_id": oid})
        except Exception:
            return None

    def update(self, reg_id, update_fields):
        """Update specific fields of a registration."""
        oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
        update_fields["updated_at"] = datetime.now(timezone.utc)
        self.collection.update_one({"_id": oid}, {"$set": update_fields})
        return self.find_by_id(oid)

    def add_note(self, reg_id, note_entry):
        """Append an internal admin note to the registration."""
        oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
        note_entry["created_at"] = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": oid},
            {
                "$push": {"notes": note_entry},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        return self.find_by_id(oid)

    def delete(self, reg_id):
        """Permanently delete a registration (Super Admin only)."""
        oid = ObjectId(reg_id) if isinstance(reg_id, str) else reg_id
        result = self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    def list_registrations(self, skip=0, limit=20, reg_type=None, status=None, search=None, start_date=None, end_date=None, sort_field="created_at", sort_dir=-1):
        """Query registrations with flexible filtering, search, and pagination."""
        query = {}
        if reg_type and reg_type != "all":
            query["registration_type"] = reg_type.lower()
        if status and status != "all":
            query["status"] = status.lower()

        # Date range filtering
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            query["created_at"] = date_query

        # Text search across name, email, phone, organization_name
        if search:
            regex = re.compile(re.escape(search.strip()), re.IGNORECASE)
            query["$or"] = [
                {"name": regex},
                {"email": regex},
                {"phone": regex},
                {"organization_name": regex},
                {"city": regex},
            ]

        cursor = self.collection.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
        return list(cursor)

    def count(self, reg_type=None, status=None, search=None, start_date=None, end_date=None):
        """Count registrations matching filter criteria."""
        query = {}
        if reg_type and reg_type != "all":
            query["registration_type"] = reg_type.lower()
        if status and status != "all":
            query["status"] = status.lower()

        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            query["created_at"] = date_query

        if search:
            regex = re.compile(re.escape(search.strip()), re.IGNORECASE)
            query["$or"] = [
                {"name": regex},
                {"email": regex},
                {"phone": regex},
                {"organization_name": regex},
                {"city": regex},
            ]

        if not query:
            try:
                return self.collection.estimated_document_count()
            except Exception:
                pass
        return self.collection.count_documents(query)

    def get_summary_stats(self, start_date=None, end_date=None):
        """Get aggregate counts by registration type and status using MongoDB aggregation."""
        match_stage = {}
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            match_stage["created_at"] = date_query

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})

        pipeline.append({
            "$group": {
                "_id": {
                    "type": "$registration_type",
                    "status": "$status"
                },
                "count": {"$sum": 1}
            }
        })

        results = list(self.collection.aggregate(pipeline))
        
        stats = {
            "total": 0,
            "volunteers": 0,
            "partners": 0,
            "new": 0,
            "contacted": 0,
            "approved": 0,
            "rejected": 0,
            "active": 0,
            "inactive": 0,
        }

        for item in results:
            count = item["count"]
            reg_type = item["_id"].get("type")
            status = item["_id"].get("status")

            stats["total"] += count
            if reg_type == "volunteer":
                stats["volunteers"] += count
            elif reg_type == "partner":
                stats["partners"] += count

            if status in stats:
                stats[status] += count

        return stats
