"""
NSE/BSE Trading Universe and Symbol Metadata Management.

Tracks the initial 10 liquid NSE large-cap stocks:
- Reliance Industries Ltd (Energy/Conglomerate)
- Tata Consultancy Services Ltd (IT Services)
- Infosys Ltd (IT Services)
- HDFC Bank Ltd (Banking & Financials)
- ICICI Bank Ltd (Banking & Financials)
- Bharti Airtel Ltd (Telecom)
- State Bank of India (Public Banking)
- ITC Ltd (FMCG)
- Larsen & Toubro Ltd (Infrastructure/Capital Goods)
- Tata Motors Ltd (Automotive)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass(frozen=True)
class InstrumentMetadata:
    symbol: str          # e.g. "RELIANCE"
    yfinance_ticker: str # e.g. "RELIANCE.NS"
    company_name: str
    sector: str
    exchange: str        # "NSE" or "BSE"
    tick_size: Decimal   # Standard NSE tick size = ₹0.05
    lot_size: int        # Standard Cash equity = 1
    currency: str        # "INR"
    is_active: bool = True

    def to_dict(self) -> Dict[str, str | float | int | bool]:
        return {
            "symbol": self.symbol,
            "yfinance_ticker": self.yfinance_ticker,
            "company_name": self.company_name,
            "sector": self.sector,
            "exchange": self.exchange,
            "tick_size": float(self.tick_size),
            "lot_size": self.lot_size,
            "currency": self.currency,
            "is_active": self.is_active,
        }


# Default 10 Liquid NSE Large-Cap Universe
DEFAULT_UNIVERSE: Dict[str, InstrumentMetadata] = {
    "RELIANCE": InstrumentMetadata(
        symbol="RELIANCE",
        yfinance_ticker="RELIANCE.NS",
        company_name="Reliance Industries Limited",
        sector="Oil, Gas & Consumable Fuels / Conglomerate",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "TCS": InstrumentMetadata(
        symbol="TCS",
        yfinance_ticker="TCS.NS",
        company_name="Tata Consultancy Services Limited",
        sector="Information Technology",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "INFY": InstrumentMetadata(
        symbol="INFY",
        yfinance_ticker="INFY.NS",
        company_name="Infosys Limited",
        sector="Information Technology",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "HDFCBANK": InstrumentMetadata(
        symbol="HDFCBANK",
        yfinance_ticker="HDFCBANK.NS",
        company_name="HDFC Bank Limited",
        sector="Financial Services / Private Banking",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "ICICIBANK": InstrumentMetadata(
        symbol="ICICIBANK",
        yfinance_ticker="ICICIBANK.NS",
        company_name="ICICI Bank Limited",
        sector="Financial Services / Private Banking",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "BHARTIARTL": InstrumentMetadata(
        symbol="BHARTIARTL",
        yfinance_ticker="BHARTIARTL.NS",
        company_name="Bharti Airtel Limited",
        sector="Telecommunication",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "SBIN": InstrumentMetadata(
        symbol="SBIN",
        yfinance_ticker="SBIN.NS",
        company_name="State Bank of India",
        sector="Financial Services / Public Banking",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "ITC": InstrumentMetadata(
        symbol="ITC",
        yfinance_ticker="ITC.NS",
        company_name="ITC Limited",
        sector="Fast Moving Consumer Goods (FMCG)",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "LT": InstrumentMetadata(
        symbol="LT",
        yfinance_ticker="LT.NS",
        company_name="Larsen & Toubro Limited",
        sector="Construction & Engineering",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
    "TATAMOTORS": InstrumentMetadata(
        symbol="TATAMOTORS",
        yfinance_ticker="TATAMOTORS.NS",
        company_name="Tata Motors Limited",
        sector="Automobile and Auto Components",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
    ),
}


class UniverseManager:
    """Manages the active universe of tradable Indian instruments."""

    def __init__(self, custom_universe: Optional[Dict[str, InstrumentMetadata]] = None) -> None:
        self._instruments: Dict[str, InstrumentMetadata] = custom_universe or DEFAULT_UNIVERSE

    def normalize_symbol(self, raw_symbol: str) -> str:
        """
        Normalizes any input string to standard base symbol (e.g. 'reliance.ns' -> 'RELIANCE').
        """
        cleaned = raw_symbol.strip().upper()
        if cleaned.endswith(".NS"):
            cleaned = cleaned[:-3]
        elif cleaned.endswith(".BO"):
            cleaned = cleaned[:-3]
        return cleaned

    def get_yfinance_ticker(self, raw_symbol: str) -> str:
        """
        Returns the Yahoo Finance formatted ticker (e.g., 'RELIANCE' -> 'RELIANCE.NS').
        """
        base = self.normalize_symbol(raw_symbol)
        inst = self._instruments.get(base)
        if inst:
            return inst.yfinance_ticker
        return f"{base}.NS"

    def get_instrument(self, raw_symbol: str) -> Optional[InstrumentMetadata]:
        base = self.normalize_symbol(raw_symbol)
        return self._instruments.get(base)

    def list_instruments(self) -> List[InstrumentMetadata]:
        return list(self._instruments.values())

    def get_symbols(self) -> List[str]:
        return list(self._instruments.keys())

    def get_yfinance_tickers(self) -> List[str]:
        return [inst.yfinance_ticker for inst in self._instruments.values()]


# Default singleton instance
universe_manager = UniverseManager()
