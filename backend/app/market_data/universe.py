"""
Trading Universe and Symbol Metadata Management for Indian (NSE) and US (NYSE/NASDAQ) Markets.

Tracks:
1. Indian NSE Large-Cap Universe (10 liquid equities):
   - RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, BHARTIARTL, SBIN, ITC, LT, TATAMOTORS
2. US Mega-Cap Universe (10 liquid equities):
   - AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, BRK-B, JPM, V
"""

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class InstrumentMetadata:
    symbol: str          # e.g. "RELIANCE" or "AAPL"
    yfinance_ticker: str # e.g. "RELIANCE.NS" or "AAPL"
    company_name: str
    sector: str
    exchange: str        # "NSE", "BSE", "NASDAQ", "NYSE"
    tick_size: Decimal   # NSE = ₹0.05, US = $0.01
    lot_size: int        # 1
    currency: str        # "INR" or "USD"
    market: str = "IN"   # "IN" (India) or "US" (United States)
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
            "market": self.market,
            "is_active": self.is_active,
        }


# Default 10 Liquid NSE Large-Cap Universe (India)
DEFAULT_IN_UNIVERSE: Dict[str, InstrumentMetadata] = {
    "RELIANCE": InstrumentMetadata(
        symbol="RELIANCE",
        yfinance_ticker="RELIANCE.NS",
        company_name="Reliance Industries Limited",
        sector="Oil, Gas & Consumable Fuels / Conglomerate",
        exchange="NSE",
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
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
        market="IN",
    ),
}

# Default 10 Liquid Mega-Cap Universe (United States - NYSE & NASDAQ)
DEFAULT_US_UNIVERSE: Dict[str, InstrumentMetadata] = {
    "AAPL": InstrumentMetadata(
        symbol="AAPL",
        yfinance_ticker="AAPL",
        company_name="Apple Inc.",
        sector="Technology / Consumer Electronics",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "MSFT": InstrumentMetadata(
        symbol="MSFT",
        yfinance_ticker="MSFT",
        company_name="Microsoft Corporation",
        sector="Technology / Enterprise Software & Cloud",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "NVDA": InstrumentMetadata(
        symbol="NVDA",
        yfinance_ticker="NVDA",
        company_name="NVIDIA Corporation",
        sector="Technology / Semiconductors & AI",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "AMZN": InstrumentMetadata(
        symbol="AMZN",
        yfinance_ticker="AMZN",
        company_name="Amazon.com, Inc.",
        sector="Consumer Discretionary / E-Commerce & Cloud",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "GOOGL": InstrumentMetadata(
        symbol="GOOGL",
        yfinance_ticker="GOOGL",
        company_name="Alphabet Inc.",
        sector="Communication Services / Search & AI",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "META": InstrumentMetadata(
        symbol="META",
        yfinance_ticker="META",
        company_name="Meta Platforms, Inc.",
        sector="Communication Services / Social Platforms",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "TSLA": InstrumentMetadata(
        symbol="TSLA",
        yfinance_ticker="TSLA",
        company_name="Tesla, Inc.",
        sector="Consumer Discretionary / EV & Energy",
        exchange="NASDAQ",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "BRK-B": InstrumentMetadata(
        symbol="BRK-B",
        yfinance_ticker="BRK-B",
        company_name="Berkshire Hathaway Inc. (Class B)",
        sector="Financial Services / Diversified Conglomerate",
        exchange="NYSE",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "JPM": InstrumentMetadata(
        symbol="JPM",
        yfinance_ticker="JPM",
        company_name="JPMorgan Chase & Co.",
        sector="Financial Services / Diversified Banking",
        exchange="NYSE",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
    "V": InstrumentMetadata(
        symbol="V",
        yfinance_ticker="V",
        company_name="Visa Inc.",
        sector="Financial Services / Transaction Processing",
        exchange="NYSE",
        tick_size=Decimal("0.01"),
        lot_size=1,
        currency="USD",
        market="US",
    ),
}

# Unified Universe containing both Indian and US equities
DEFAULT_UNIVERSE: Dict[str, InstrumentMetadata] = {
    **DEFAULT_IN_UNIVERSE,
    **DEFAULT_US_UNIVERSE,
}


class UniverseManager:
    """Manages the active universe of tradable Indian (NSE 2,600+ equities) and US instruments."""

    def __init__(self, custom_universe: Optional[Dict[str, InstrumentMetadata]] = None) -> None:
        self._instruments: Dict[str, InstrumentMetadata] = dict(custom_universe or DEFAULT_UNIVERSE)
        self._top_liquid_in_symbols: List[str] = list(DEFAULT_IN_UNIVERSE.keys())
        self._top_liquid_us_symbols: List[str] = list(DEFAULT_US_UNIVERSE.keys())
        self._aliases: Dict[str, str] = {
            "ZOMATO": "ETERNAL",  # Zomato rebranded to Eternal Limited on NSE
        }
        self._load_full_nse_directory()

    def _load_full_nse_directory(self) -> None:
        """Loads all official listed equity instruments from the NSE master CSV directory."""
        csv_path = Path(__file__).parent / "nse_equities.csv"
        if not csv_path.exists():
            return

        try:
            with open(csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cleaned_row = {k.strip(): v.strip() for k, v in row.items() if k}
                    sym = cleaned_row.get("SYMBOL", "").upper()
                    if not sym:
                        continue

                    # If not already present in curated defaults, register with official metadata
                    if sym not in self._instruments:
                        company_name = cleaned_row.get("NAME OF COMPANY", sym)
                        series = cleaned_row.get("SERIES", "EQ")
                        self._instruments[sym] = InstrumentMetadata(
                            symbol=sym,
                            yfinance_ticker=f"{sym}.NS",
                            company_name=company_name,
                            sector=f"NSE Equity ({series})",
                            exchange="NSE",
                            tick_size=Decimal("0.05"),
                            lot_size=1,
                            currency="INR",
                            market="IN",
                        )
        except Exception:
            # Fallback gracefully to default curated universe if file cannot be read
            pass

    def normalize_symbol(self, raw_symbol: str) -> str:
        """
        Normalizes any input string to standard base symbol.
        e.g. 'reliance.ns' -> 'RELIANCE', 'aapl' -> 'AAPL', 'brk.b' -> 'BRK-B', 'zomato' -> 'ETERNAL'.
        """
        cleaned = raw_symbol.strip().upper()
        if cleaned.endswith(".NS") or cleaned.endswith(".BO"):
            cleaned = cleaned[:-3]
        elif cleaned in ("BRK.B", "BRK/B"):
            cleaned = "BRK-B"
        return self._aliases.get(cleaned, cleaned)

    def get_yfinance_ticker(self, raw_symbol: str) -> str:
        """
        Returns the Yahoo Finance formatted ticker.
        e.g., 'RELIANCE' -> 'RELIANCE.NS', 'AAPL' -> 'AAPL', 'TATAPOWER' -> 'TATAPOWER.NS'.
        """
        base = self.normalize_symbol(raw_symbol)
        inst = self._instruments.get(base)
        if inst:
            return inst.yfinance_ticker
        # If not known, default to .NS if appears Indian, else raw base
        return f"{base}.NS"

    def get_instrument(self, raw_symbol: str) -> Optional[InstrumentMetadata]:
        base = self.normalize_symbol(raw_symbol)
        return self._instruments.get(base)

    def get_market_for_symbol(self, raw_symbol: str) -> str:
        """Returns 'US' for US instruments, 'IN' for Indian instruments."""
        inst = self.get_instrument(raw_symbol)
        if inst:
            return inst.market
        base = self.normalize_symbol(raw_symbol)
        if base in DEFAULT_US_UNIVERSE:
            return "US"
        return "IN"

    def list_instruments(
        self,
        market: Optional[str] = None,
        scan_only: bool = False,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[InstrumentMetadata]:
        """Lists tradable instruments, optionally filtered by market, category, search query, or limit."""
        target_market = market.upper() if market else None
        search_term = search.strip().lower() if search else None

        results = []
        for inst in self._instruments.values():
            if target_market and inst.market != target_market:
                continue
            if scan_only and inst.market == "IN" and inst.symbol not in self._top_liquid_in_symbols:
                continue
            if scan_only and inst.market == "US" and inst.symbol not in self._top_liquid_us_symbols:
                continue
            if search_term:
                if search_term not in inst.symbol.lower() and search_term not in inst.company_name.lower():
                    continue
            results.append(inst)
            if limit and len(results) >= limit:
                break

        return results

    def get_symbols(self, market: Optional[str] = None, scan_only: bool = False) -> List[str]:
        """
        Returns list of normalized symbols.
        If scan_only is True, returns only the focused liquid subset for autonomous auto-trader evaluation.
        """
        if scan_only:
            if market == "IN":
                return list(self._top_liquid_in_symbols)
            elif market == "US":
                return list(self._top_liquid_us_symbols)
            return self._top_liquid_in_symbols + self._top_liquid_us_symbols

        if market:
            target = market.upper()
            return [inst.symbol for inst in self._instruments.values() if inst.market == target]
        return list(self._instruments.keys())

    def get_yfinance_tickers(self, market: Optional[str] = None, scan_only: bool = False) -> List[str]:
        symbols = self.get_symbols(market=market, scan_only=scan_only)
        return [self.get_yfinance_ticker(s) for s in symbols]


# Default singleton instance
universe_manager = UniverseManager()
