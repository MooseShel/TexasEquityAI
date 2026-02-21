"""
Assessment Monitor Service
Detects year-over-year assessment changes and flags properties
where the increase exceeds a configurable threshold.

Uses valuation_history from the properties table to compare years.
"""

import logging
from typing import Dict, List, Optional
from backend.db.supabase_client import SupabaseService

logger = logging.getLogger(__name__)


class AssessmentMonitor:

    def __init__(self):
        self.supabase = SupabaseService()

    async def add_watch(self, account_number: str, district: str = 'HCAD',
                        threshold_pct: float = 5.0) -> Dict:
        """Add a property to the watch list."""
        if not self.supabase.client:
            return {"error": "Database not available"}

        # Fetch current property data
        prop = await self.supabase.get_property_by_account(account_number)
        if not prop:
            return {"error": f"Property {account_number} not found in database"}

        appraised = float(prop.get('appraised_value', 0) or 0)
        address = prop.get('address', '')

        # Extract year-over-year change from valuation_history
        val_history = prop.get('valuation_history', {})
        change_pct, baseline_val, baseline_yr, latest_yr = self._compute_change(
            val_history, appraised
        )

        try:
            record = {
                "account_number": account_number,
                "district": district,
                "address": address,
                "baseline_appraised": baseline_val,
                "baseline_year": baseline_yr,
                "latest_appraised": appraised,
                "latest_year": latest_yr,
                "change_pct": round(change_pct, 2) if change_pct else None,
                "alert_triggered": abs(change_pct) >= threshold_pct if change_pct else False,
                "alert_threshold_pct": threshold_pct,
            }
            result = self.supabase.client.table("property_watches") \
                .upsert(record, on_conflict="account_number,district") \
                .execute()
            if result.data:
                logger.info(f"AssessmentMonitor: Added watch for {account_number} (change: {change_pct:.1f}%)")
                return {**result.data[0], "property": prop}
            return {"error": "Failed to save watch"}
        except Exception as e:
            logger.error(f"AssessmentMonitor: Error adding watch: {e}")
            return {"error": str(e)}

    async def remove_watch(self, account_number: str, district: str = 'HCAD') -> bool:
        """Remove a property from the watch list."""
        if not self.supabase.client:
            return False
        try:
            self.supabase.client.table("property_watches") \
                .delete() \
                .eq("account_number", account_number) \
                .eq("district", district) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"AssessmentMonitor: Error removing watch: {e}")
            return False

    async def get_watch_list(self) -> List[Dict]:
        """Get all watched properties with current status."""
        if not self.supabase.client:
            return []
        try:
            result = self.supabase.client.table("property_watches") \
                .select("*") \
                .order("alert_triggered", desc=True) \
                .order("change_pct", desc=True) \
                .execute()
            return result.data or []
        except Exception as e:
            logger.error(f"AssessmentMonitor: Error getting watch list: {e}")
            return []

    async def refresh_all(self) -> Dict:
        """Re-check all watched properties for assessment changes."""
        watches = await self.get_watch_list()
        if not watches:
            return {"checked": 0, "alerts": 0}

        alerts = 0
        checked = 0
        for watch in watches:
            acct = watch.get('account_number', '')
            threshold = float(watch.get('alert_threshold_pct', 5.0))
            try:
                prop = await self.supabase.get_property_by_account(acct)
                if not prop:
                    continue

                appraised = float(prop.get('appraised_value', 0) or 0)
                val_history = prop.get('valuation_history', {})
                change_pct, baseline_val, baseline_yr, latest_yr = self._compute_change(
                    val_history, appraised
                )

                update = {
                    "latest_appraised": appraised,
                    "latest_year": latest_yr,
                    "change_pct": round(change_pct, 2) if change_pct else None,
                    "alert_triggered": abs(change_pct) >= threshold if change_pct else False,
                    "address": prop.get('address', watch.get('address', '')),
                }

                if update["alert_triggered"]:
                    alerts += 1

                self.supabase.client.table("property_watches") \
                    .update(update) \
                    .eq("id", watch['id']) \
                    .execute()
                checked += 1

            except Exception as e:
                logger.warning(f"AssessmentMonitor: Failed to refresh {acct}: {e}")

        logger.info(f"AssessmentMonitor: Refreshed {checked} properties, {alerts} alerts triggered")
        return {"checked": checked, "alerts": alerts}

    def _compute_change(self, val_history, current_appraised: float):
        """
        Extract year-over-year change from valuation_history.
        valuation_history is typically: {"2024": {"appraised": 350000, ...}, "2023": {...}}
        Returns: (change_pct, baseline_value, baseline_year, latest_year)
        """
        import datetime
        current_year = datetime.datetime.now().year

        if not val_history or not isinstance(val_history, dict):
            return (0, current_appraised, current_year - 1, current_year)

        # Sort years descending
        years = sorted(
            [y for y in val_history.keys() if y.isdigit()],
            key=lambda y: int(y), reverse=True
        )

        if len(years) < 2:
            return (0, current_appraised, current_year - 1, current_year)

        latest_yr = int(years[0])
        prev_yr = int(years[1])

        latest_data = val_history.get(years[0], {})
        prev_data = val_history.get(years[1], {})

        # Handle different formats: could be dict or direct value
        if isinstance(latest_data, dict):
            latest_val = float(latest_data.get('appraised', latest_data.get('total', 0)) or 0)
        else:
            latest_val = float(latest_data or 0)

        if isinstance(prev_data, dict):
            prev_val = float(prev_data.get('appraised', prev_data.get('total', 0)) or 0)
        else:
            prev_val = float(prev_data or 0)

        # Use current_appraised if latest_val is 0
        if latest_val == 0:
            latest_val = current_appraised

        if prev_val == 0:
            return (0, current_appraised, prev_yr, latest_yr)

        change_pct = ((latest_val - prev_val) / prev_val) * 100
        return (change_pct, prev_val, prev_yr, latest_yr)
