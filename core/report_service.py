"""
Reporting Service – Weekly Registration Coverage

Provides registration coverage reports combining weekview menu data
with meal registration tracking.

Phase 1: Weekly registration coverage per department.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, timedelta
from typing import List

from sqlalchemy import text

from .db import get_session
from .meal_registration_repo import MealRegistrationRepo


@dataclass
class DepartmentCoverage:
    """Coverage statistics for a single department."""
    department_id: str
    department_name: str
    lunch_expected: int
    lunch_registered: int
    dinner_expected: int
    dinner_registered: int
    total_expected: int
    total_registered: int
    coverage_percent: int


class ReportService:
    """Service for generating reports."""
    
    def __init__(self):
        self.registration_repo = MealRegistrationRepo()
    
    def get_weekly_registration_coverage(
        self, 
        tenant_id: int | str, 
        site_id: str,
        year: int, 
        week: int
    ) -> List[DepartmentCoverage]:
        """
        Calculate weekly registration coverage for all departments at a site.
        
        For each department:
        - Count expected meals (menu items exist for lunch/dinner on each day)
        - Count registered meals (registration flag is True)
        - Compute coverage percentage
        
        Args:
            tenant_id: Tenant ID
            site_id: Site ID (UUID string)
            year: ISO year
            week: ISO week number (1-53)
        
        Returns:
            List of DepartmentCoverage objects sorted by department_name
        """
        # Get all departments for the site
        departments = self._get_departments_for_site(site_id)
        
        if not departments:
            return []
        
        coverage_list = []
        
        for dept in departments:
            dept_id = dept["id"]
            dept_name = dept["name"]
            
            # Calculate date range for the week
            jan4 = _date(year, 1, 4)
            week1_monday = jan4 - timedelta(days=jan4.weekday())
            week_monday = week1_monday + timedelta(weeks=week - 1)
            week_dates = [week_monday + timedelta(days=i) for i in range(7)]
            
            # Fetch weekview_items (menu planning data) for this department
            db = get_session()
            try:
                menu_rows = db.execute(
                    text("""
                        SELECT local_date, meal
                        FROM weekview_items
                        WHERE tenant_id = :tid
                          AND department_id = :dept_id
                          AND local_date >= :start_date
                          AND local_date <= :end_date
                          AND title IS NOT NULL
                          AND title != ''
                    """),
                    {
                        "tid": int(tenant_id),
                        "dept_id": dept_id,
                        "start_date": week_dates[0].isoformat(),
                        "end_date": week_dates[6].isoformat(),
                    }
                ).fetchall()
                
                menu_lookup = {(str(r[0]), str(r[1])) for r in menu_rows}
            finally:
                db.close()
            
            # Fetch meal registrations for this department
            registrations = self.registration_repo.get_registrations_for_week(
                tenant_id=tenant_id,
                site_id=site_id,
                department_id=dept_id,
                year=year,
                week=week
            )
            
            # Build registration lookup: (date, meal_type) -> registered
            reg_lookup = {
                (r["date"], r["meal_type"]): r["registered"]
                for r in registrations
            }
            
            # Count expected and registered meals
            lunch_expected = 0
            lunch_registered = 0
            dinner_expected = 0
            dinner_registered = 0
            
            # For each day in the week, check if menu exists
            for day_date in week_dates:
                date_str = day_date.isoformat()
                
                # Check lunch
                if (date_str, "lunch") in menu_lookup:
                    lunch_expected += 1
                    if reg_lookup.get((date_str, "lunch"), False):
                        lunch_registered += 1
                
                # Check dinner
                if (date_str, "dinner") in menu_lookup:
                    dinner_expected += 1
                    if reg_lookup.get((date_str, "dinner"), False):
                        dinner_registered += 1
            
            # Calculate totals and percentage
            total_expected = lunch_expected + dinner_expected
            total_registered = lunch_registered + dinner_registered
            
            if total_expected > 0:
                coverage_percent = round(100 * total_registered / total_expected)
            else:
                coverage_percent = 0
            
            coverage_list.append(DepartmentCoverage(
                department_id=dept_id,
                department_name=dept_name,
                lunch_expected=lunch_expected,
                lunch_registered=lunch_registered,
                dinner_expected=dinner_expected,
                dinner_registered=dinner_registered,
                total_expected=total_expected,
                total_registered=total_registered,
                coverage_percent=coverage_percent
            ))
        
        # Sort by department name
        coverage_list.sort(key=lambda x: x.department_name)
        
        return coverage_list
    
    def _get_departments_for_site(self, site_id: str) -> list[dict]:
        """
        Get all departments for a given site.
        
        Returns list of dicts with keys: id, name
        """
        db = get_session()
        try:
            rows = db.execute(
                text("""
                    SELECT id, name
                    FROM departments
                    WHERE site_id = :site_id
                    ORDER BY name
                """),
                {"site_id": site_id}
            ).fetchall()
            
            return [{"id": str(r[0]), "name": str(r[1])} for r in rows]
        finally:
            db.close()
