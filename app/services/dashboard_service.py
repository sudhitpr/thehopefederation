from app.repositories.registration_repository import RegistrationRepository
from app.repositories.prayer_request_repository import PrayerRequestRepository


class DashboardService:
    """Service providing aggregated operational metrics and recent activity feeds for the dashboard."""

    def __init__(self, reg_repo=None, prayer_repo=None):
        self.reg_repo = reg_repo or RegistrationRepository()
        self.prayer_repo = prayer_repo or PrayerRequestRepository()

    def get_dashboard_data(self):
        """Aggregate all dashboard metrics and recent items."""
        reg_stats = self.reg_repo.get_summary_stats()
        prayer_stats = self.prayer_repo.get_summary_stats()

        # Unprocessed prayer requests = new + in_review
        pending_prayers = prayer_stats.get("new", 0) + prayer_stats.get("in_review", 0)

        recent_registrations = self.reg_repo.list_registrations(
            skip=0,
            limit=5,
            sort_field="created_at",
            sort_dir=-1
        )

        recent_prayers = self.prayer_repo.list_requests(
            skip=0,
            limit=5,
            sort_field="created_at",
            sort_dir=-1
        )

        return {
            "registrations": {
                "total": reg_stats.get("total", 0),
                "volunteers": reg_stats.get("volunteers", 0),
                "partners": reg_stats.get("partners", 0),
                "new": reg_stats.get("new", 0),
                "approved": reg_stats.get("approved", 0),
                "rejected": reg_stats.get("rejected", 0),
                "active": reg_stats.get("active", 0),
            },
            "prayer_requests": {
                "total": prayer_stats.get("total", 0),
                "new": prayer_stats.get("new", 0),
                "in_review": prayer_stats.get("in_review", 0),
                "praying": prayer_stats.get("praying", 0),
                "completed": prayer_stats.get("completed", 0),
                "archived": prayer_stats.get("archived", 0),
                "pending": pending_prayers,
            },
            "recent_registrations": recent_registrations,
            "recent_prayers": recent_prayers,
        }
