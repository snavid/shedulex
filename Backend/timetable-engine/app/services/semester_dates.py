from datetime import date

from app.models.domain import Timetable
from app.services.calendar_client import fetch_semester_dates


def _parse_academic_year_start(academic_year: str) -> int:
    """Extract start year from strings like '2025/2026' or '2025-2026'."""
    if not academic_year:
        return date.today().year
    token = academic_year.replace("-", "/").split("/")[0].strip()
    try:
        return int(token)
    except ValueError:
        return date.today().year


def fallback_semester_dates(tt: Timetable) -> dict:
    """Reasonable semester window when calendar semester is not linked."""
    year = _parse_academic_year_start(tt.academic_year or "")
    if tt.semester == 1:
        start = date(year, 9, 1)
        end = date(year + 1, 1, 31)
    else:
        start = date(year + 1, 2, 1)
        end = date(year + 1, 6, 30)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "calendar_semester_id": tt.calendar_semester_id,
    }


def resolve_semester_dates(tt: Timetable) -> dict:
    if tt.calendar_semester_id:
        fetched = fetch_semester_dates(tt.calendar_semester_id)
        if fetched:
            return fetched
    return fallback_semester_dates(tt)
