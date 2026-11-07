import logging
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


def create_indexes(db):
    """
    Ensure all required indexes exist on MongoDB collections.
    Safe to run repeatedly; PyMongo skips already existing identical indexes.
    """
    results = {}
    try:
        # 1. Users collection
        users_col = db["users"]
        users_col.create_index([("email", ASCENDING)], unique=True, name="idx_users_email_unique")
        users_col.create_index([("role", ASCENDING)], name="idx_users_role")
        users_col.create_index([("is_active", ASCENDING)], name="idx_users_active")
        users_col.create_index([("created_at", DESCENDING)], name="idx_users_created_at")
        users_col.create_index([("reset_token", ASCENDING)], sparse=True, name="idx_users_reset_token")
        users_col.create_index(
            [("role", ASCENDING), ("created_at", DESCENDING)],
            name="idx_users_role_date"
        )
        results["users"] = ["email (unique)", "role", "is_active", "created_at", "reset_token", "role_date"]

        # 2. Registrations collection (unified volunteer & partner)
        reg_col = db["registrations"]
        reg_col.create_index([("registration_type", ASCENDING)], name="idx_reg_type")
        reg_col.create_index([("status", ASCENDING)], name="idx_reg_status")
        reg_col.create_index([("email", ASCENDING)], name="idx_reg_email")
        reg_col.create_index([("phone", ASCENDING)], name="idx_reg_phone")
        reg_col.create_index([("name", ASCENDING)], name="idx_reg_name")
        reg_col.create_index([("created_at", DESCENDING)], name="idx_reg_created_at")
        # Compound indexes for frequent admin filtered queries & sorting
        reg_col.create_index(
            [("registration_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_reg_type_date"
        )
        reg_col.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_reg_status_date"
        )
        reg_col.create_index(
            [("registration_type", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_reg_type_status_date"
        )
        results["registrations"] = [
            "registration_type", "status", "email", "phone", "name",
            "created_at", "type_date", "status_date", "compound"
        ]

        # 3. Prayer Requests collection
        prayer_col = db["prayer_requests"]
        prayer_col.create_index([("status", ASCENDING)], name="idx_prayer_status")
        prayer_col.create_index([("category", ASCENDING)], name="idx_prayer_category")
        prayer_col.create_index([("created_at", DESCENDING)], name="idx_prayer_created_at")
        # Compound indexes for category & status listing
        prayer_col.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_prayer_status_date"
        )
        prayer_col.create_index(
            [("category", ASCENDING), ("created_at", DESCENDING)],
            name="idx_prayer_category_date"
        )
        prayer_col.create_index(
            [("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)],
            name="idx_prayer_status_cat_date"
        )
        results["prayer_requests"] = [
            "status", "category", "created_at", "status_date", "category_date", "status_cat_date"
        ]

        # 4. Audit Logs collection
        audit_col = db["audit_logs"]
        audit_col.create_index([("admin_user_id", ASCENDING)], name="idx_audit_admin_id")
        audit_col.create_index([("module", ASCENDING)], name="idx_audit_module")
        audit_col.create_index([("action", ASCENDING)], name="idx_audit_action")
        audit_col.create_index([("timestamp", DESCENDING)], name="idx_audit_timestamp")
        audit_col.create_index(
            [("module", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_audit_module_time"
        )
        audit_col.create_index(
            [("action", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_audit_action_time"
        )
        audit_col.create_index(
            [("admin_user_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_audit_admin_time"
        )
        results["audit_logs"] = [
            "admin_user_id", "module", "action", "timestamp",
            "module_time", "action_time", "admin_time"
        ]

        logger.info("Successfully ensured MongoDB indexes.")
        return results

    except PyMongoError as err:
        logger.error("Error creating MongoDB indexes: %s", err)
        raise
