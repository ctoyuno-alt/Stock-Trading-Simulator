"""
Stock Market Trading Sessions & Holiday Calendars for Indian (NSE) and US (NYSE/NASDAQ) Markets.

Handles:
- NSE Cash Market trading hours: 09:15 to 15:30 IST (Asia/Kolkata).
- US Regular trading hours: 09:30 to 16:00 ET (America/New_York).
- Weekend closures (Saturday & Sunday).
- Official Indian NSE market holidays & US Federal market holidays.
- Session enforcement to prevent order execution outside active market hours.
"""

from datetime import date, datetime, time
from typing import Optional, Set, Tuple
from zoneinfo import ZoneInfo


IST_ZONE = ZoneInfo("Asia/Kolkata")
ET_ZONE = ZoneInfo("America/New_York")

# NSE Market Timings (IST)
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)

# US Market Timings (ET)
US_MARKET_OPEN_TIME = time(9, 30)
US_MARKET_CLOSE_TIME = time(16, 0)

# Official NSE Trading Holidays (Format: YYYY-MM-DD)
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
    date(2025, 10, 21),  # Diwali Laxmi Pujan
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

# Official US Stock Market Holidays (NYSE & NASDAQ)
US_HOLIDAYS: Set[date] = {
    # 2025 Holidays
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # Martin Luther King Jr. Day
    date(2025, 2, 17),   # Washington's Birthday (Presidents' Day)
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth National Independence Day
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving Day
    date(2025, 12, 25),  # Christmas Day
    # 2026 Holidays
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 2, 16),   # Washington's Birthday (Presidents' Day)
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth National Independence Day
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
}


def get_current_ist_time() -> datetime:
    """Returns the current datetime in IST (Asia/Kolkata)."""
    return datetime.now(IST_ZONE)


def get_current_et_time() -> datetime:
    """Returns the current datetime in Eastern Time (America/New_York)."""
    return datetime.now(ET_ZONE)


def is_us_market_open(check_time: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Evaluates whether the US stock exchanges (NYSE / NASDAQ) are currently open for regular trading.
    
    Returns:
        (is_open: bool, reason: str)
    """
    if check_time is None:
        check_time = get_current_et_time()
    else:
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=ET_ZONE)
        else:
            check_time = check_time.astimezone(ET_ZONE)

    current_date = check_time.date()
    current_clock = check_time.time()
    weekday = check_time.weekday()  # Monday=0, Sunday=6

    # 1. Weekend check
    if weekday == 5:
        return False, "US Market closed: Saturday weekend"
    if weekday == 6:
        return False, "US Market closed: Sunday weekend"

    # 2. Holiday check
    if current_date in US_HOLIDAYS:
        return False, f"US Market closed: Official Holiday ({current_date.isoformat()})"

    # 3. Time window check (09:30 to 16:00 ET)
    if current_clock < US_MARKET_OPEN_TIME:
        return False, f"US Market pre-open: Trading starts at 09:30 ET (Current: {current_clock.strftime('%H:%M:%S')})"
    if current_clock > US_MARKET_CLOSE_TIME:
        return False, f"US Market post-close: Trading ended at 16:00 ET (Current: {current_clock.strftime('%H:%M:%S')})"

    return True, "US Market is OPEN (Regular Trading Session 09:30 - 16:00 ET)"


def is_market_open(
    check_time: Optional[datetime] = None,
    market: str = "IN",
) -> Tuple[bool, str]:
    """
    Evaluates whether the specified stock exchange (NSE or US) is currently open for trading.
    Defaults to Indian market ('IN') for complete backward compatibility.
    
    Returns:
        (is_open: bool, reason: str)
    """
    if market.upper() == "US":
        return is_us_market_open(check_time)

    # Default: Indian Market (NSE/BSE)
    if check_time is None:
        check_time = get_current_ist_time()
    else:
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=IST_ZONE)
        else:
            check_time = check_time.astimezone(IST_ZONE)

    current_date = check_time.date()
    current_clock = check_time.time()
    weekday = check_time.weekday()

    if weekday == 5:
        return False, "Market closed: Saturday weekend"
    if weekday == 6:
        return False, "Market closed: Sunday weekend"

    if current_date in NSE_HOLIDAYS:
        return False, f"Market closed: Official NSE Trading Holiday ({current_date.isoformat()})"

    if current_clock < MARKET_OPEN_TIME:
        return False, f"Market pre-open: Trading starts at 09:15 IST (Current: {current_clock.strftime('%H:%M:%S')})"
    if current_clock > MARKET_CLOSE_TIME:
        return False, f"Market post-close: Trading ended at 15:30 IST (Current: {current_clock.strftime('%H:%M:%S')})"

    return True, "Market is OPEN (Regular Trading Session 09:15 - 15:30 IST)"
