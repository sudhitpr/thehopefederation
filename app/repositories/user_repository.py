from bson import ObjectId
from app.database import get_db
from app.models.user import User


class UserRepository:
    """Repository handling all MongoDB operations for admin users."""

    def __init__(self, db=None):
        self._db = db

    @property
    def collection(self):
        db = self._db if self._db is not None else get_db()
        return db["users"]

    def find_by_id(self, user_id):
        """Find a single user by ObjectId or string ID."""
        if not user_id:
            return None
        try:
            oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
            doc = self.collection.find_one({"_id": oid})
            return User.from_dict(doc)
        except Exception:
            return None

    def find_by_email(self, email):
        """Find user by unique email address."""
        if not email:
            return None
        doc = self.collection.find_one({"email": email.lower().strip()})
        return User.from_dict(doc)

    def find_by_reset_token(self, token):
        """Find user by valid password reset token."""
        if not token:
            return None
        doc = self.collection.find_one({"reset_token": token})
        return User.from_dict(doc)

    def create(self, user):
        """Insert a new user document."""
        doc = user.to_dict()
        result = self.collection.insert_one(doc)
        user._id = result.inserted_id
        return user

    def update(self, user_id, update_fields):
        """Update specific fields of an existing user."""
        oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.collection.update_one({"_id": oid}, {"$set": update_fields})
        return self.find_by_id(oid)

    def list_all(self, skip=0, limit=50, role=None, is_active=None):
        """List users with optional role and status filters."""
        query = {}
        if role:
            query["role"] = role
        if is_active is not None:
            query["is_active"] = is_active

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return [User.from_dict(doc) for doc in cursor]

    def count(self, role=None, is_active=None):
        """Count users matching query."""
        query = {}
        if role:
            query["role"] = role
        if is_active is not None:
            query["is_active"] = is_active
        if not query:
            try:
                return self.collection.estimated_document_count()
            except Exception:
                pass
        return self.collection.count_documents(query)

    def delete(self, user_id):
        """Delete user by ID."""
        oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        result = self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0
