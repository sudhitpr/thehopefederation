from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId


class User(UserMixin):
    """Admin User model integrating with Flask-Login."""

    ROLES = ["Super Admin", "Admin", "Staff"]

    def __init__(
        self,
        email,
        name=None,
        password_hash=None,
        role="Staff",
        is_active=True,
        _id=None,
        created_at=None,
        last_login=None,
        reset_token=None,
        reset_token_expiry=None,
    ):
        self._id = ObjectId(_id) if _id and isinstance(_id, str) else _id
        self.email = email.lower().strip() if email else ""
        self.name = name or ""
        self.password_hash = password_hash
        self.role = role if role in self.ROLES else "Staff"
        self._is_active = is_active
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_login = last_login
        self.reset_token = reset_token
        self.reset_token_expiry = reset_token_expiry

    @property
    def id(self):
        """String representation of MongoDB _id for Flask-Login session."""
        return str(self._id) if self._id else None

    @property
    def is_active(self):
        """Flask-Login active status check."""
        return self._is_active

    def set_password(self, password):
        """Hash and set user password securely using scrypt/pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify plain password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles):
        """Check if user belongs to any of the specified roles."""
        return self.role in roles

    def can_manage_users(self):
        """Only Super Admin can manage administrative users."""
        return self.role == "Super Admin"

    def can_delete(self):
        """Only Super Admin can permanently delete records."""
        return self.role == "Super Admin"

    def to_dict(self):
        """Convert to MongoDB document dictionary."""
        doc = {
            "email": self.email,
            "name": self.name,
            "password_hash": self.password_hash,
            "role": self.role,
            "is_active": self._is_active,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "reset_token": self.reset_token,
            "reset_token_expiry": self.reset_token_expiry,
        }
        if self._id:
            doc["_id"] = self._id
        return doc

    @classmethod
    def from_dict(cls, doc):
        """Construct User instance from MongoDB document."""
        if not doc:
            return None
        return cls(
            _id=doc.get("_id"),
            email=doc.get("email"),
            name=doc.get("name"),
            password_hash=doc.get("password_hash"),
            role=doc.get("role", "Staff"),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at"),
            last_login=doc.get("last_login"),
            reset_token=doc.get("reset_token"),
            reset_token_expiry=doc.get("reset_token_expiry"),
        )
