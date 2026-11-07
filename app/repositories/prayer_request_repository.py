from datetime import datetime, timezone
import re
from bson import ObjectId
from app.database import get_db


class PrayerRequestRepository:
    """Repository handling all MongoDB operations for confidential prayer requests."""

    VALID_STATUSES = ["new", "in_review", "praying", "completed", "archived"]
    CATEGORIES = [
        "Health & Healing",
        "Family & Relationships",
        "Guidance & Wisdom",
        "Financial & Provision",
        "Spiritual Growth",
        "Thanksgiving & Praise",
        "Other",
    ]

    def __init__(self, db=None):
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else get_db()
        return db["prayer_requests"]

    def create(self, data):
        """Insert a new prayer request."""
        now = datetime.now(timezone.utc)
        doc = dict(data)
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = now
        doc["status"] = doc.get("status", "new").lower()
        doc["notes"] = doc.get("notes", [])
        doc["is_anonymous"] = bool(doc.get("is_anonymous", False))
        if doc["is_anonymous"]:
            doc["name"] = "Anonymous"
            doc["email"] = ""
            doc["phone"] = ""

        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_id(self, req_id):
        """Find a single prayer request by ID."""
        if not req_id:
            return None
        try:
            oid = ObjectId(req_id) if isinstance(req_id, str) else req_id
            return self.collection.find_one({"_id": oid})
        except Exception:
            return None

    def update(self, req_id, update_fields):
        """Update specific fields of a prayer request."""
        oid = ObjectId(req_id) if isinstance(req_id, str) else req_id
        update_fields["updated_at"] = datetime.now(timezone.utc)
        self.collection.update_one({"_id": oid}, {"$set": update_fields})
        return self.find_by_id(oid)

    def add_note(self, req_id, note_entry):
        """Append an internal note to the prayer request."""
        oid = ObjectId(req_id) if isinstance(req_id, str) else req_id
        note_entry["created_at"] = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": oid},
            {
                "$push": {"notes": note_entry},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        return self.find_by_id(oid)

    def delete(self, req_id):
        """Permanently delete a prayer request (Super Admin only)."""
        oid = ObjectId(req_id) if isinstance(req_id, str) else req_id
        result = self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    def list_requests(self, skip=0, limit=20, status=None, category=None, search=None, start_date=None, end_date=None, sort_field="created_at", sort_dir=-1):
        """Query prayer requests with status/category filtering and date boundaries."""
        query = {}
        if status and status != "all":
            query["status"] = status.lower()
        if category and category != "all":
            query["category"] = category

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
                {"category": regex},
            ]

        cursor = self.collection.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
        return list(cursor)

    def count(self, status=None, category=None, search=None, start_date=None, end_date=None):
        """Count prayer requests matching criteria."""
        query = {}
        if status and status != "all":
            query["status"] = status.lower()
        if category and category != "all":
            query["category"] = category

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
                {"category": regex},
            ]

        if not query:
            try:
                return self.collection.estimated_document_count()
            except Exception:
                pass
        return self.collection.count_documents(query)

    def get_summary_stats(self, start_date=None, end_date=None):
        """Aggregate prayer request counts by status and category using MongoDB aggregation."""
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
                "_id": "$status",
                "count": {"$sum": 1}
            }
        })

        results = list(self.collection.aggregate(pipeline))

        stats = {
            "total": 0,
            "new": 0,
            "in_review": 0,
            "praying": 0,
            "completed": 0,
            "archived": 0,
        }

        for item in results:
            status = item["_id"]
            count = item["count"]
            stats["total"] += count
            if status in stats:
                stats[status] = count

        return stats
