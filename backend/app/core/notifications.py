"""
Telegram Real-Time Push Notification Engine for Paper & Live Trading.

Provides:
- 100% Free real-time alerts dispatched to your mobile phone or desktop via Telegram Bot API.
- Instant notifications for order execution, Stop-Loss liquidations, Take-Profit targets,
  daily circuit breaker alerts, and market session recaps.
- Graceful offline fallback with zero external library dependencies.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Manages real-time alert dispatching via Telegram Bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID") or ""
        self.enabled = enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token.strip() and self.chat_id.strip())

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Sends a formatted message to the registered Telegram chat."""
        if not self.enabled or not self.is_configured:
            logger.debug("Telegram notification skipped: Bot is not configured or disabled.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("Telegram notification delivered successfully.")
                    return True
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8")
            logger.warning(f"Telegram API delivery failed (HTTP {exc.code}): {err_body}")
        except Exception as exc:
            logger.warning(f"Telegram notification connection error: {str(exc)}")

        return False

    def notify_order_filled(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        executed_price: Decimal,
        currency: str = "INR",
        reason: str = "Quantitative Confluence",
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
    ) -> bool:
        """Alerts trader on order execution."""
        curr_sym = "$" if currency == "USD" else "₹"
        emoji = "🟢" if side.upper() == "BUY" else "🔴"
        sl_text = f"{curr_sym}{stop_loss:,.2f}" if stop_loss else "None"
        tp_text = f"{curr_sym}{take_profit:,.2f}" if take_profit else "None"

        msg = (
            f"<b>{emoji} ORDER EXECUTED: {side.upper()} {symbol}</b>\n\n"
            f"• <b>Quantity:</b> {quantity} shares\n"
            f"• <b>Executed Price:</b> {curr_sym}{executed_price:,.2f}\n"
            f"• <b>Total Turnover:</b> {curr_sym}{executed_price * Decimal(quantity):,.2f}\n"
            f"• <b>Stop-Loss:</b> {sl_text}\n"
            f"• <b>Target:</b> {tp_text}\n"
            f"• <b>Rationale:</b> <code>{reason}</code>\n"
            f"• <b>Order ID:</b> <code>{order_id}</code>\n"
            f"• <b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return self.send_message(msg)

    def notify_position_closed(
        self,
        symbol: str,
        exit_price: Decimal,
        quantity: int,
        realized_pnl: Decimal,
        return_pct: float,
        reason: str,
        currency: str = "INR",
    ) -> bool:
        """Alerts trader on position closure (Stop-Loss or Take-Profit)."""
        curr_sym = "$" if currency == "USD" else "₹"
        is_win = realized_pnl >= Decimal("0.00")
        header_emoji = "🎯 <b>TAKE-PROFIT ACHIEVED</b>" if is_win else "🛑 <b>STOP-LOSS LIQUIDATION</b>"
        pnl_emoji = "✅" if is_win else "🔻"

        msg = (
            f"{header_emoji} — <b>{symbol}</b>\n\n"
            f"• <b>Exit Price:</b> {curr_sym}{exit_price:,.2f} ({quantity} shares)\n"
            f"• <b>Net P&L:</b> {pnl_emoji} {curr_sym}{realized_pnl:+,.2f} (<b>{return_pct:+.2f}%</b>)\n"
            f"• <b>Trigger Reason:</b> <code>{reason}</code>\n"
            f"• <b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        return self.send_message(msg)

    def notify_circuit_breaker(
        self,
        daily_loss_pct: float,
        current_equity: Decimal,
        currency: str = "INR",
    ) -> bool:
        """High-priority alert when daily max drawdown circuit breaker trips."""
        curr_sym = "$" if currency == "USD" else "₹"
        msg = (
            f"🚨 <b>DAILY CIRCUIT BREAKER TRIPPED!</b> 🚨\n\n"
            f"• <b>Daily Drawdown:</b> -{daily_loss_pct*100:.2f}% (Limit: -2.0%)\n"
            f"• <b>Current Equity:</b> {curr_sym}{current_equity:,.2f}\n"
            f"• <b>Action Taken:</b> Trading bot emergency halted for remainder of session.\n"
            f"• <b>Status:</b> All new entries locked. Open positions protected.\n"
            f"• <b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        return self.send_message(msg)

    def test_connection(self) -> Tuple[bool, str]:
        """Tests validity of token and chat_id by dispatching a verification ping."""
        if not self.bot_token or not self.chat_id:
            return False, "Bot token or Chat ID is missing."

        test_msg = (
            "🔔 <b>Antigravity AI Trading Engine — Test Connection</b>\n\n"
            "Your Telegram alert system is successfully configured and active! "
            "You will receive instant alerts for order fills, stop-losses, and daily recaps."
        )
        success = self.send_message(test_msg)
        if success:
            return True, "Verification message delivered successfully to your Telegram account!"
        return False, "Failed to connect to Telegram API. Please verify your Bot Token and Chat ID."


# Global notifier instance
notifier = TelegramNotifier()
