from datetime import datetime, time, timedelta, timezone
from app.repositories.registration_repository import RegistrationRepository
from app.repositories.prayer_request_repository import PrayerRequestRepository


class ReportService:
    """Service providing aggregate analytics and reports with flexible date boundary filtering."""

    def __init__(self, reg_repo=None, prayer_repo=None):
        self.reg_repo = reg_repo or RegistrationRepository()
        self.prayer_repo = prayer_repo or PrayerRequestRepository()

    @staticmethod
    def calculate_date_range(period="all", custom_start=None, custom_end=None):
        """
        Calculate start and end datetime bounds based on preset period or custom range.
        Returns: (start_datetime, end_datetime) in UTC timezone.
        """
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
        today_end = datetime.combine(now.date(), time.max).replace(tzinfo=timezone.utc)

        if period == "today":
            return today_start, today_end

        if period == "week":
            # Start of current week (Monday)
            start_week = today_start - timedelta(days=today_start.weekday())
            return start_week, today_end

        if period == "month":
            # Start of current calendar month
            start_month = today_start.replace(day=1)
            return start_month, today_end

        if period == "year":
            # Start of current calendar year
            start_year = today_start.replace(month=1, day=1)
            return start_year, today_end

        if period == "custom" and custom_start and custom_end:
            try:
                s_dt = datetime.strptime(custom_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                e_dt = datetime.strptime(custom_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                return s_dt, e_dt
            except Exception:
                pass

        # Default "all" -> no boundary
        return None, None

    def generate_report(self, period="all", custom_start=None, custom_end=None):
        """Generate comprehensive operational report for registrations and prayer requests."""
        start_dt, end_dt = self.calculate_date_range(period, custom_start, custom_end)

        reg_stats = self.reg_repo.get_summary_stats(start_date=start_dt, end_date=end_dt)
        prayer_stats = self.prayer_repo.get_summary_stats(start_date=start_dt, end_date=end_dt)

        # Category breakdown for prayer requests within date range
        category_pipeline = []
        if start_dt or end_dt:
            date_match = {}
            if start_dt:
                date_match["$gte"] = start_dt
            if end_dt:
                date_match["$lte"] = end_dt
            category_pipeline.append({"$match": {"created_at": date_match}})

        category_pipeline.append({
            "$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }
        })
        category_pipeline.append({"$sort": {"count": -1}})

        cat_results = list(self.prayer_repo.collection.aggregate(category_pipeline))
        categories_breakdown = [{"category": item["_id"] or "Uncategorized", "count": item["count"]} for item in cat_results]

        return {
            "period": period,
            "start_date": start_dt,
            "end_date": end_dt,
            "registrations": reg_stats,
            "prayer_requests": prayer_stats,
            "prayer_categories": categories_breakdown,
        }
