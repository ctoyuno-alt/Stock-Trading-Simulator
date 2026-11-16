"""
Indian Stock Market (NSE/BSE) Trading Session & Holiday Calendar.

Handles:
- NSE Cash Market trading hours: 09:15 to 15:30 IST (Asia/Kolkata).
- Weekend closures (Saturday & Sunday).
- Official NSE market holidays (Standard calendar).
- Session enforcement to prevent order execution outside active market hours.
"""

from datetime import date, datetime, time
from typing import Optional, Set, Tuple
from zoneinfo import ZoneInfo


IST_ZONE = ZoneInfo("Asia/Kolkata")
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)

# Standard official NSE Trading Holidays (Format: YYYY-MM-DD)
# Updated for current and upcoming calendar years
NSE_HOLIDAYS: Set[date] = {
    # 2025 Holidays
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr
    date(2025, 4, 10),   # Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 21),  # Diwali Laxmi Pujan (Muhurat Trading session separate)
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Gurunanak Jayanti
    date(2025, 12, 25),  # Christmas
    # 2026 Holidays
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 3),    # Holi
    date(2026, 3, 20),   # Id-Ul-Fitr
    date(2026, 3, 31),   # Mahavir Jayanti
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 8),   # Diwali Laxmi Pujan
    date(2026, 11, 24),  # Gurunanak Jayanti
    date(2026, 12, 25),  # Christmas
}


def get_current_ist_time() -> datetime:
    """Returns the current datetime in IST (Asia/Kolkata)."""
    return datetime.now(IST_ZONE)


def is_market_open(check_time: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Evaluates whether the NSE/BSE stock exchange is currently open for trading.
    
    Returns:
        (is_open: bool, reason: str)
    """
    if check_time is None:
        check_time = get_current_ist_time()
    else:
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=IST_ZONE)
        else:
            check_time = check_time.astimezone(IST_ZONE)

    current_date = check_time.date()
    current_clock = check_time.time()
    weekday = check_time.weekday()  # Monday=0, Sunday=6

    # 1. Weekend check
    if weekday == 5:
        return False, "Market closed: Saturday weekend"
    if weekday == 6:
        return False, "Market closed: Sunday weekend"

    # 2. Holiday check
    if current_date in NSE_HOLIDAYS:
        return False, f"Market closed: Official NSE Trading Holiday ({current_date.isoformat()})"

    # 3. Time window check (09:15 to 15:30 IST)
    if current_clock < MARKET_OPEN_TIME:
        return False, f"Market pre-open: Trading starts at 09:15 IST (Current: {current_clock.strftime('%H:%M:%S')})"
    if current_clock > MARKET_CLOSE_TIME:
        return False, f"Market post-close: Trading ended at 15:30 IST (Current: {current_clock.strftime('%H:%M:%S')})"

    return True, "Market is OPEN (Regular Trading Session 09:15 - 15:30 IST)"
