"""
Unit Tests for Virtual Exchange Matching Engine & GTT Bracket Orders.
"""

from decimal import Decimal
import unittest

from trading.virtual_exchange import (
    GTTOrderStatus,
    GTTOrderType,
    VirtualExchangeMatchingEngine,
)


class TestVirtualExchange(unittest.TestCase):

    def setUp(self):
        self.exchange = VirtualExchangeMatchingEngine(slippage_bps=5.0)

    def test_register_bracket_order(self):
        """Verify registration of both Stop-Loss and Take-Profit GTT bracket orders."""
        orders = self.exchange.register_bracket_order(
            account_id=1,
            position_id=101,
            symbol="RELIANCE",
            quantity=10,
            stop_loss_price=Decimal("1300.00"),
            take_profit_price=Decimal("1450.00"),
        )

        self.assertEqual(len(orders), 2)
        sl_order = next(o for o in orders if o.order_type == GTTOrderType.STOP_LOSS)
        tp_order = next(o for o in orders if o.order_type == GTTOrderType.TAKE_PROFIT)

        self.assertEqual(sl_order.trigger_price, Decimal("1300.00"))
        self.assertEqual(tp_order.trigger_price, Decimal("1450.00"))
        self.assertEqual(sl_order.status, GTTOrderStatus.ACTIVE)
        self.assertEqual(tp_order.status, GTTOrderStatus.ACTIVE)

    def test_stop_loss_trigger_and_oco_cancellation(self):
        """Verify that price dropping to or below SL triggers liquidation and cancels opposite TP order."""
        orders = self.exchange.register_bracket_order(
            account_id=1,
            position_id=102,
            symbol="TCS",
            quantity=5,
            stop_loss_price=Decimal("2400.00"),
            take_profit_price=Decimal("2600.00"),
        )
        sl_order = next(o for o in orders if o.order_type == GTTOrderType.STOP_LOSS)
        tp_order = next(o for o in orders if o.order_type == GTTOrderType.TAKE_PROFIT)

        # Price ticks at 2450 (within safe range) -> No trigger
        events_safe = self.exchange.process_tick("TCS", Decimal("2450.00"))
        self.assertEqual(len(events_safe), 0)
        self.assertEqual(sl_order.status, GTTOrderStatus.ACTIVE)
        self.assertEqual(tp_order.status, GTTOrderStatus.ACTIVE)

        # Price ticks at 2395 (breaches SL 2400) -> Triggers SL
        events_breach = self.exchange.process_tick("TCS", Decimal("2395.00"))
        self.assertEqual(len(events_breach), 1)
        self.assertEqual(events_breach[0].order.order_id, sl_order.order_id)
        self.assertEqual(sl_order.status, GTTOrderStatus.TRIGGERED)
        # OCO: Take-profit order must be automatically cancelled
        self.assertEqual(tp_order.status, GTTOrderStatus.CANCELLED)

    def test_take_profit_trigger_and_oco_cancellation(self):
        """Verify that price rising to or above TP triggers target execution and cancels SL order."""
        orders = self.exchange.register_bracket_order(
            account_id=1,
            position_id=103,
            symbol="INFY",
            quantity=15,
            stop_loss_price=Decimal("1100.00"),
            take_profit_price=Decimal("1250.00"),
        )
        sl_order = next(o for o in orders if o.order_type == GTTOrderType.STOP_LOSS)
        tp_order = next(o for o in orders if o.order_type == GTTOrderType.TAKE_PROFIT)

        # Price hits 1255 (crosses TP 1250)
        events = self.exchange.process_tick("INFY", Decimal("1255.00"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].order.order_id, tp_order.order_id)
        self.assertEqual(tp_order.status, GTTOrderStatus.TRIGGERED)
        # Opposite SL cancelled
        self.assertEqual(sl_order.status, GTTOrderStatus.CANCELLED)

    def test_cancel_orders_for_position(self):
        """Verify explicit cancellation when a position is closed manually."""
        self.exchange.register_bracket_order(
            account_id=1,
            position_id=104,
            symbol="ITC",
            quantity=20,
            stop_loss_price=Decimal("280.00"),
            take_profit_price=Decimal("320.00"),
        )
        active_before = self.exchange.get_active_orders(symbol="ITC")
        self.assertEqual(len(active_before), 2)

        cancelled = self.exchange.cancel_orders_for_position(104, reason="Manual exit")
        self.assertEqual(cancelled, 2)
        active_after = self.exchange.get_active_orders(symbol="ITC")
        self.assertEqual(len(active_after), 0)


if __name__ == "__main__":
    unittest.main()
