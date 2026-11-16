#!/usr/bin/env python3
"""
CLI Historical Market Data Ingestion and Warmup Utility.

Usage:
    python3 scripts/ingest_historical_data.py --period 1y --timeframe 1d
    python3 scripts/ingest_historical_data.py --symbols RELIANCE,TCS --synthetic
"""

import argparse
import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from backend.app.market_data.storage import MarketDataStorage


async def main():
    parser = argparse.ArgumentParser(description="Ingest historical market data for NSE universe.")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols to ingest (defaults to all 10 liquid stocks)",
    )
    parser.add_argument(
        "--period",
        type=str,
        default="1y",
        help="Historical lookback period (e.g., 1mo, 3mo, 6mo, 1y, 2y)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        choices=["1d", "1h", "15m", "5m"],
        help="Candle timeframe",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use deterministic synthetic generator (for offline environments)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate data without writing to database",
    )

    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = universe_manager.get_symbols()

    print(f"================================================================================")
    print(f" Market Data Ingestion: {len(symbols)} Instruments [{args.timeframe} / {args.period}]")
    print(f" Mode: {'SYNTHETIC FIXTURE' if args.synthetic else 'YFINANCE PROVIDER'}")
    print(f"================================================================================")

    provider = YFinanceProvider()

    session_factory = None
    if not args.dry_run:
        print("==> Initializing database connection...")
        try:
            from database.init_db import init_db
            from database.session import get_sessionmaker
            await init_db()
            session_factory = get_sessionmaker()
        except Exception as e:
            print(f"WARNING: DB init note: {e}")

    total_candles_ingested = 0
    total_anomalies = 0

    for idx, sym in enumerate(symbols, 1):
        clean_sym = universe_manager.normalize_symbol(sym)
        inst = universe_manager.get_instrument(clean_sym)
        inst_name = inst.company_name if inst else clean_sym

        print(f"\n[{idx}/{len(symbols)}] Processing {clean_sym} ({inst_name})...")

        if args.synthetic:
            batch = YFinanceProvider.generate_synthetic_history(clean_sym, days=150)
        else:
            batch = provider.fetch_historical_ohlcv(clean_sym, timeframe=args.timeframe, period=args.period)
            if not batch.candles:
                print(f"    Notice: yfinance yielded 0 candles (likely offline). Generating synthetic fallback...")
                batch = YFinanceProvider.generate_synthetic_history(clean_sym, days=150)

        # Validate
        validation = batch.validation or provider.validate_batch(batch)
        print(f"    Candles: {len(batch.candles)} bars | Provider: {batch.provider}")
        print(f"    Time Range: {batch.start_time.strftime('%Y-%m-%d')} to {batch.end_time.strftime('%Y-%m-%d')}")
        print(f"    Delayed: {batch.is_delayed} ({batch.delay_minutes} min delay notice)")
        print(f"    Data Integrity: {'PASSED' if validation.is_valid else 'FAILED'}")

        if validation.anomalies_detected:
            print(f"    ⚠️ Anomalies detected: {len(validation.anomalies_detected)}")
            for anom in validation.anomalies_detected[:3]:
                print(f"       - {anom}")
            total_anomalies += len(validation.anomalies_detected)

        if not args.dry_run and batch.candles:
            try:
                async with session_factory() as session:
                    saved = await MarketDataStorage.save_candles(session, batch)
                    print(f"    Database: Successfully persisted {saved} candles.")
                    total_candles_ingested += saved
            except Exception as e:
                print(f"    Database persistence note (may require running DB): {e}")

    print(f"\n================================================================================")
    print(f" INGESTION SUMMARY")
    print(f" Instruments processed: {len(symbols)}")
    print(f" Total candles processed: {total_candles_ingested if not args.dry_run else 'Dry run (skipped DB write)'}")
    print(f" Total data anomalies: {total_anomalies}")
    print(f" Completed at: {datetime.now(timezone.utc).isoformat()}")
    print(f"================================================================================")


if __name__ == "__main__":
    asyncio.run(main())
