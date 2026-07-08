from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.modules.supplier_calendar.models import SupplierCalendarClosure
from app.modules.supplier_calendar.schemas import (
    SupplierCalendarClosureCreate,
    SupplierCalendarYearResponse,
    SupplierCalendarDayResponse,
    SupplierCalendarTotalsResponse,
)


def easter_sunday(year: int) -> date:
    """Gregorian computus, valid for the years used by the app."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def italian_holidays(year: int) -> dict[date, str]:
    holidays = {
        date(year, 1, 1): "Capodanno",
        date(year, 1, 6): "Epifania",
        date(year, 4, 25): "Liberazione",
        date(year, 5, 1): "Festa del lavoro",
        date(year, 6, 2): "Festa della Repubblica",
        date(year, 8, 15): "Ferragosto",
        date(year, 11, 1): "Ognissanti",
        date(year, 12, 8): "Immacolata",
        date(year, 12, 25): "Natale",
        date(year, 12, 26): "Santo Stefano",
    }
    holidays[easter_sunday(year) + timedelta(days=1)] = "Lunedi dell'Angelo"
    return holidays


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _closures_between(db: Session, start: date, end: date) -> list[SupplierCalendarClosure]:
    stmt = (
        select(SupplierCalendarClosure)
        .where(
            and_(
                SupplierCalendarClosure.start_date <= end,
                SupplierCalendarClosure.end_date >= start,
            )
        )
        .order_by(SupplierCalendarClosure.start_date.asc(), SupplierCalendarClosure.id.asc())
    )
    return list(db.scalars(stmt).all())


def load_non_working_dates_for_ranges(
    db: Session,
    ranges: Iterable[tuple[date | None, date | None]],
) -> set[date]:
    valid_ranges = [(start, end) for start, end in ranges if start and end]
    if not valid_ranges:
        return set()

    min_date = min(min(start, end) for start, end in valid_ranges)
    max_date = max(max(start, end) for start, end in valid_ranges)
    non_working_dates: set[date] = set()

    for year in range(min_date.year, max_date.year + 1):
        non_working_dates.update(italian_holidays(year).keys())

    for closure in _closures_between(db, min_date, max_date):
        range_start = max(closure.start_date, min_date)
        range_end = min(closure.end_date, max_date)
        non_working_dates.update(date_range(range_start, range_end))

    return non_working_dates


def business_days_delta(
    start: date,
    end: date,
    non_working_dates: set[date] | None = None,
) -> int:
    if end < start:
        return -business_days_delta(end, start, non_working_dates)

    non_working_dates = non_working_dates or set()
    count = 0
    for current in date_range(start, end):
        if current.weekday() < 5 and current not in non_working_dates:
            count += 1
    return max(count - 1, 0)


def get_calendar_year(db: Session, year: int) -> SupplierCalendarYearResponse:
    start, end = _year_bounds(year)
    holidays_map = italian_holidays(year)
    closures = _closures_between(db, start, end)

    days_by_date: dict[date, SupplierCalendarDayResponse] = {}
    weekend_days = 0
    for current in date_range(start, end):
        if current.weekday() >= 5:
            weekend_days += 1
            days_by_date[current] = SupplierCalendarDayResponse(
                date=current, kind="weekend", label="Sabato/Domenica"
            )

    holidays = [
        SupplierCalendarDayResponse(date=holiday_date, kind="holiday", label=label)
        for holiday_date, label in sorted(holidays_map.items())
    ]
    for holiday in holidays:
        days_by_date[holiday.date] = holiday

    closure_dates: set[date] = set()
    for closure in closures:
        range_start = max(closure.start_date, start)
        range_end = min(closure.end_date, end)
        for current in date_range(range_start, range_end):
            closure_dates.add(current)
            days_by_date[current] = SupplierCalendarDayResponse(
                date=current, kind="closure", label=closure.label
            )

    return SupplierCalendarYearResponse(
        year=year,
        holidays=holidays,
        closures=closures,
        days=[days_by_date[key] for key in sorted(days_by_date)],
        totals=SupplierCalendarTotalsResponse(
            weekend_days=weekend_days,
            holiday_days=len(holidays),
            closure_days=len(closure_dates),
        ),
    )


def create_closure(db: Session, payload: SupplierCalendarClosureCreate) -> SupplierCalendarClosure:
    closure = SupplierCalendarClosure(
        start_date=payload.start_date,
        end_date=payload.end_date,
        label=payload.label,
    )
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure


def delete_closure(db: Session, closure_id: int) -> bool:
    closure = db.get(SupplierCalendarClosure, closure_id)
    if not closure:
        return False
    db.delete(closure)
    db.commit()
    return True
