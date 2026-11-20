"""
Autonomous Background Trading Daemon Service.

Runs 24/7 inside the backend container as an asynchronous service.
Provides:
- Independent periodic execution without requiring active browser sessions.
- Market session scheduling (NSE 09:15-15:30 IST / US 09:30-16:00 ET).
- Real-time tick evaluation against Virtual Exchange GTT bracket orders.
- Daily Circuit Breaker enforcement (-2.0% daily max loss).
- Immediate push notification dispatching via Telegram.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from backend.app.core.market_schedule import is_market_open
from backend.app.core.notifications import notifier
from database.session import get_db
from trading.auto_trader import auto_trading_bot, AutoTraderConfig
from trading.virtual_exchange import virtual_exchange

logger = logging.getLogger(__name__)


class TradingDaemon:
    """Autonomous server daemon orchestrating 24/7 paper and live trading cycles."""

    def __init__(self, interval_seconds: int = 30) -> None:
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_cycle_at: Optional[datetime] = None
        self.cycles_completed: int = 0
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_reason: Optional[str] = None
        self.enabled_markets: List[str] = ["IN", "US"]

    def start(self, interval_seconds: Optional[int] = None) -> bool:
        """Starts the background trading daemon."""
        if self.is_running:
            logger.info("Trading daemon is already running.")
            return False

        if interval_seconds:
            self.interval_seconds = max(5, interval_seconds)

        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Trading daemon started with {self.interval_seconds}s polling interval.")
        return True

    def stop(self) -> bool:
        """Stops the background trading daemon."""
        if not self.is_running:
            return False

        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Trading daemon stopped.")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Returns live daemon execution telemetry."""
        in_open, in_reason = is_market_open(market="IN")
        us_open, us_reason = is_market_open(market="US")

        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "cycles_completed": self.cycles_completed,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "markets_status": {
                "IN": {"is_open": in_open, "reason": in_reason},
                "US": {"is_open": us_open, "reason": us_reason},
            },
            "active_gtt_orders_count": len(virtual_exchange.get_active_orders()),
        }

    async def _run_loop(self) -> None:
        """Continuous async execution loop."""
        logger.info("Trading daemon loop initiated.")
        while self.is_running:
            try:
                await self._execute_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in trading daemon cycle: {str(exc)}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

        self.is_running = False
        logger.info("Trading daemon loop terminated.")

    async def _execute_cycle(self) -> None:
        """Executes a single evaluation pass for each active market."""
        self.last_cycle_at = datetime.now(timezone.utc)
        self.cycles_completed += 1

        async for session in get_db():
            for market in self.enabled_markets:
                is_open, reason = is_market_open(market=market)
                cfg = auto_trading_bot.config

                # If enforce_market_hours is True and market is closed, skip candidate scan
                if cfg.enforce_market_hours and not is_open:
                    logger.debug(f"Daemon skipping {market} market: {reason}")
                    continue

                if self.circuit_breaker_active:
                    logger.warning(f"Daemon skipping {market}: Daily Circuit Breaker is active.")
                    continue

                # Run autonomous cycle on database session
                try:
                    result = await auto_trading_bot.run_cycle(
                        session=session,
                        market=market,
                        config_override=cfg,
                    )
                    # Notify on orders executed
                    if result.get("orders_executed_count", 0) > 0:
                        logger.info(f"Daemon executed {result['orders_executed_count']} order(s) in {market} market.")
                except Exception as cycle_err:
                    logger.warning(f"Daemon error executing {market} cycle: {str(cycle_err)}")

            break


# Global daemon singleton instance
trading_daemon = TradingDaemon(interval_seconds=30)
