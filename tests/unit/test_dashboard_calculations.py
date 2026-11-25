"""
Mathematical & Financial Calculations Test Suite for Quantum Trader Dashboard.

Validates:
1. 1% Risk Reactive Position Sizing formula (Q = min(Q_risk, Q_alloc, Q_cash)) under standard, edge, and bound constraints.
2. Risk:Reward Ratio preview calculations, minimum 2.0:1 threshold, and edge cases (SL >= E, TP <= E).
3. Indian regulatory charges and taxes (Brokerage ₹20, 0.1% STT, turnover fee, SEBI fee, stamp duty, 18% GST).
4. US regulatory transaction charges ($0 brokerage, SEC Section 31, FINRA TAF on sell).
5. Multi-point historical equity curve reconstruction (N+2 points), drawdown %, and Sharpe ratio.
6. Deterministic 4-factor radial confluence scoring (Trend 30%, RSI 25%, MACD 25%, VWAP 20%).
"""

from decimal import Decimal
import math
import unittest

from trading.risk import calculate_position_size, PositionSizeResult, calculate_rr_preview
from trading.charges import calculate_trade_friction, calculate_us_trade_friction, round_inr
from trading.metrics import calculate_performance_metrics, PerformanceMetrics, reconstruct_multipoint_equity_curve
from dashboard.components.gauges import calculate_deterministic_confluence


class TestPositionSizingCalculations(unittest.TestCase):
    """Tests the 1% risk position sizing formula across standard and boundary conditions."""

    def test_standard_1pct_risk_sizing(self):
        """
        Standard institutional sizing:
        Equity: ₹100,000, Cash: ₹100,000, Entry: ₹2500, SL: ₹2450.
        Risk/sh: ₹50, Risk Budget (1%): ₹1000 -> Q_risk = 1000 // 50 = 20
        Allocation Cap (20%): ₹20,000 -> Q_alloc = 20000 // 2500 = 8
        Cash Cap: ₹100,000 -> Q_cash = 100000 // 2500 = 40
        Expected: min(20, 8, 40) = 8 shares.
        """
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),
            max_risk_pct=0.01,
            max_allocation_pct=0.20,
        )
        self.assertTrue(res.is_approved)
        self.assertEqual(res.quantity, 8)
        self.assertEqual(res.capital_required_inr, Decimal("20000.00"))
        self.assertEqual(res.total_risk_inr, Decimal("400.00"))
        self.assertLessEqual(float(res.total_risk_inr), 1000.00)

    def test_sizing_tight_stop_allocation_constrained(self):
        """Tight stop loss where concentration cap (20%) is the binding constraint."""
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("1000.00"),
            stop_loss_price=Decimal("990.00"),  # Risk/sh = ₹10 -> Q_risk = 100
        )
        # Q_alloc = 20000 // 1000 = 20 shares
        self.assertEqual(res.quantity, 20)

    def test_sizing_wide_stop_risk_constrained(self):
        """Wide stop loss where 1% risk budget is the binding constraint."""
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("1000.00"),
            stop_loss_price=Decimal("900.00"),  # Risk/sh = ₹100 -> Q_risk = 1000 // 100 = 10
        )
        # Q_alloc = 20, Q_cash = 100 -> min(10, 20, 100) = 10 shares
        self.assertEqual(res.quantity, 10)

    def test_sizing_cash_constrained(self):
        """Low liquid cash limits quantity below risk and allocation caps."""
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("5000.00"),  # Cash only allows 5 shares
            entry_price=Decimal("1000.00"),
            stop_loss_price=Decimal("950.00"),
        )
        self.assertEqual(res.quantity, 5)

    def test_sizing_zero_or_negative_equity(self):
        """Zero equity produces 0 quantity and rejects order."""
        res = calculate_position_size(
            equity=Decimal("0.00"),
            available_cash=Decimal("10000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2400.00"),
        )
        self.assertFalse(res.is_approved)
        self.assertEqual(res.quantity, 0)

    def test_sizing_invalid_entry_price(self):
        """Entry price <= 0 returns 0 quantity with rejection reason."""
        res_zero = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("0.00"),
            stop_loss_price=Decimal("-10.00"),
        )
        self.assertFalse(res_zero.is_approved)
        self.assertIn("Entry price must be strictly positive", res_zero.rejection_reason)

    def test_sizing_stop_loss_greater_than_or_equal_to_entry(self):
        """Stop-loss >= Entry price returns 0 quantity and rejects order."""
        res_eq = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2500.00"),
        )
        self.assertFalse(res_eq.is_approved)
        self.assertIn("Stop-loss price must be strictly below entry", res_eq.rejection_reason)

        res_gt = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2550.00"),
        )
        self.assertFalse(res_gt.is_approved)

    def test_sizing_insufficient_cash_for_one_share(self):
        """Cash less than 1 share entry price returns quantity 0."""
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("1500.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),
        )
        self.assertFalse(res.is_approved)
        self.assertEqual(res.quantity, 0)
        self.assertIn("Insufficient cash", res.rejection_reason)

    def test_sizing_single_share_risk_exceeds_budget(self):
        """When single-share risk > 1% budget, quantity rounds to 0."""
        # Equity: ₹10,000 -> 1% budget = ₹100. Single share risk = ₹2500 - ₹2300 = ₹200
        res = calculate_position_size(
            equity=Decimal("10000.00"),
            available_cash=Decimal("10000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2300.00"),
        )
        self.assertFalse(res.is_approved)
        self.assertEqual(res.quantity, 0)
        self.assertIn("risk budget", res.rejection_reason)

    def test_sizing_strict_integer_flooring(self):
        """Ensures fractional share calculation is strictly floored to integer."""
        # Budget = ₹1000, risk/sh = ₹33 -> 1000 // 33 = 30.303 -> 30
        res = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("500.00"),
            stop_loss_price=Decimal("467.00"),
        )
        self.assertEqual(res.quantity, 30)
        self.assertIsInstance(res.quantity, int)

    def test_actual_risk_percentage_never_exceeds_budget(self):
        """Mathematical invariant: total risk incurred is <= 1.0% of equity."""
        for eq_val in [50000, 100000, 250000, 1000000]:
            equity = Decimal(str(eq_val))
            res = calculate_position_size(
                equity=equity,
                available_cash=equity,
                entry_price=Decimal("1850.50"),
                stop_loss_price=Decimal("1810.00"),
                max_risk_pct=0.01,
            )
            if res.is_approved:
                actual_risk_pct = float(res.total_risk_inr / equity) * 100.0
                self.assertLessEqual(actual_risk_pct, 1.00001)


class TestRiskRewardRatioCalculations(unittest.TestCase):
    """Tests Risk:Reward preview calculations and institutional threshold rules."""

    def test_standard_2_to_1_rr_ratio(self):
        """E = 100, SL = 95, TP = 110 produces exactly 2.0:1 R:R with OPTIMAL green status."""
        preview = calculate_rr_preview(entry=100.0, stop_loss=95.0, take_profit=110.0)
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 2.0)
        self.assertEqual(preview["tier"], "OPTIMAL")
        self.assertEqual(preview["status_color"], "#00E676")
        self.assertEqual(preview["stop_loss_pct"], 5.0)
        self.assertEqual(preview["take_profit_pct"], 10.0)

    def test_high_rr_ratio_above_2(self):
        """E = 2500, SL = 2400 (Risk=100), TP = 2750 (Reward=250) -> R:R 2.5:1 OPTIMAL."""
        preview = calculate_rr_preview(entry=2500.0, stop_loss=2400.0, take_profit=2750.0)
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 2.5)
        self.assertEqual(preview["tier"], "OPTIMAL")

    def test_suboptimal_rr_ratio_between_1_5_and_2_0(self):
        """E = 100, SL = 95 (Risk=5), TP = 109 (Reward=9) -> R:R 1.8:1 SUBOPTIMAL amber status."""
        preview = calculate_rr_preview(entry=100.0, stop_loss=95.0, take_profit=109.0)
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 1.8)
        self.assertEqual(preview["tier"], "SUBOPTIMAL")
        self.assertEqual(preview["status_color"], "#FF9900")

    def test_rejected_rr_ratio_below_1_5(self):
        """E = 100, SL = 95 (Risk=5), TP = 106 (Reward=6) -> R:R 1.2:1 REJECTED red status."""
        preview = calculate_rr_preview(entry=100.0, stop_loss=95.0, take_profit=106.0)
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 1.2)
        self.assertEqual(preview["tier"], "REJECTED")
        self.assertEqual(preview["status_color"], "#FF3366")

    def test_invalid_sl_greater_equal_entry(self):
        """SL >= Entry returns is_valid=False with explanatory reason."""
        preview = calculate_rr_preview(entry=100.0, stop_loss=105.0, take_profit=120.0)
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 0.0)

        preview_equal = calculate_rr_preview(entry=100.0, stop_loss=100.0, take_profit=120.0)
        self.assertFalse(preview_equal["is_valid"])

    def test_invalid_tp_less_equal_entry(self):
        """TP <= Entry returns is_valid=False with explanatory reason."""
        preview = calculate_rr_preview(entry=100.0, stop_loss=90.0, take_profit=95.0)
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["rr_ratio"], 0.0)

    def test_invalid_entry_zero_or_negative(self):
        """Entry <= 0 returns is_valid=False."""
        preview = calculate_rr_preview(entry=0.0, stop_loss=-10.0, take_profit=20.0)
        self.assertFalse(preview["is_valid"])

    def test_invalid_nan_parameters(self):
        """NaN entry, stop_loss, or take_profit returns is_valid=False and reason."""
        preview_nan_e = calculate_rr_preview(entry=float("nan"), stop_loss=90.0, take_profit=120.0)
        self.assertFalse(preview_nan_e["is_valid"])
        self.assertEqual(preview_nan_e["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_nan_e["reason"])

        preview_nan_sl = calculate_rr_preview(entry=100.0, stop_loss=float("nan"), take_profit=120.0)
        self.assertFalse(preview_nan_sl["is_valid"])
        self.assertEqual(preview_nan_sl["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_nan_sl["reason"])

        preview_nan_tp = calculate_rr_preview(entry=100.0, stop_loss=90.0, take_profit=float("nan"))
        self.assertFalse(preview_nan_tp["is_valid"])
        self.assertEqual(preview_nan_tp["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_nan_tp["reason"])

    def test_invalid_inf_parameters(self):
        """Infinite entry, stop_loss, or take_profit returns is_valid=False and reason."""
        preview_inf_e = calculate_rr_preview(entry=float("inf"), stop_loss=90.0, take_profit=120.0)
        self.assertFalse(preview_inf_e["is_valid"])
        self.assertEqual(preview_inf_e["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_inf_e["reason"])

        preview_ninf_sl = calculate_rr_preview(entry=100.0, stop_loss=float("-inf"), take_profit=120.0)
        self.assertFalse(preview_ninf_sl["is_valid"])
        self.assertEqual(preview_ninf_sl["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_ninf_sl["reason"])

        preview_inf_tp = calculate_rr_preview(entry=100.0, stop_loss=90.0, take_profit=float("inf"))
        self.assertFalse(preview_inf_tp["is_valid"])
        self.assertEqual(preview_inf_tp["rr_ratio"], 0.0)
        self.assertIn("NaN or infinite", preview_inf_tp["reason"])

    def test_invalid_non_numeric_parameters(self):
        """Non-numeric string or None returns is_valid=False and reason."""
        preview_str = calculate_rr_preview(entry="invalid", stop_loss=90.0, take_profit=120.0)
        self.assertFalse(preview_str["is_valid"])
        self.assertEqual(preview_str["rr_ratio"], 0.0)
        self.assertIn("Invalid numerical parameters", preview_str["reason"])

        preview_none = calculate_rr_preview(entry=100.0, stop_loss=None, take_profit=120.0)
        self.assertFalse(preview_none["is_valid"])
        self.assertEqual(preview_none["rr_ratio"], 0.0)
        self.assertIn("Invalid numerical parameters", preview_none["reason"])

    def test_gauges_component_calculate_rr_preview_inf_and_nan_rejection(self):
        """Verifies dashboard.components.gauges.calculate_rr_preview rejects inf and nan parameters."""
        from dashboard.components.gauges import calculate_rr_preview as gauges_rr
        for bad_val in [float("inf"), float("-inf"), float("nan")]:
            res_e = gauges_rr(bad_val, 90.0, 120.0)
            self.assertFalse(res_e["is_valid"])
            self.assertEqual(res_e["rr_ratio"], 0.0)
            self.assertIn("NaN or infinite", res_e["reason"])

            res_sl = gauges_rr(100.0, bad_val, 120.0)
            self.assertFalse(res_sl["is_valid"])
            self.assertEqual(res_sl["rr_ratio"], 0.0)
            self.assertIn("NaN or infinite", res_sl["reason"])

            res_tp = gauges_rr(100.0, 90.0, bad_val)
            self.assertFalse(res_tp["is_valid"])
            self.assertEqual(res_tp["rr_ratio"], 0.0)
            self.assertIn("NaN or infinite", res_tp["reason"])


class TestIndianRegulatoryChargesCalculations(unittest.TestCase):
    """Tests Indian cash delivery charges, slippage, and statutory taxes."""

    def test_nse_buy_order_charges_breakdown(self):
        """
        Validates line-by-line Indian statutory charges on BUY order:
        Price: ₹2500, Qty: 10
        1. 5 bps slippage adverse: 2500 * 1.0005 = ₹2501.25
        2. Turnover: 10 * 2501.25 = ₹25012.50
        3. Brokerage: ₹20.00
        4. STT (0.1%): ₹25.01
        5. Exchange (0.00345%): ₹0.86
        6. SEBI (0.0001%): ₹0.03
        7. Stamp duty (0.015% on BUY): ₹3.75
        8. GST (18% on Brokerage ₹20 + Exch ₹0.86 + SEBI ₹0.03 = ₹20.89): ₹3.76
        9. Total Charges: 20 + 25.01 + 0.86 + 0.03 + 3.75 + 3.76 = ₹53.41
        10. Net Cash Impact: 25012.50 + 53.41 = ₹25065.91
        """
        cost = calculate_trade_friction(
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            price=Decimal("2500.00"),
            slippage_bps=5.0,
        )
        self.assertEqual(cost.executed_price, Decimal("2501.25"))
        self.assertEqual(cost.turnover, Decimal("25012.50"))
        self.assertEqual(cost.brokerage_inr, Decimal("20.00"))
        self.assertEqual(cost.stt_tax_inr, Decimal("25.01"))
        self.assertEqual(cost.exchange_turnover_inr, Decimal("0.86"))
        self.assertEqual(cost.sebi_charges_inr, Decimal("0.03"))
        self.assertEqual(cost.stamp_duty_inr, Decimal("3.75"))
        self.assertEqual(cost.gst_inr, Decimal("3.76"))
        self.assertEqual(cost.total_charges_inr, Decimal("53.41"))
        self.assertEqual(cost.net_cash_impact_inr, Decimal("25065.91"))

    def test_nse_sell_order_charges_no_stamp_duty(self):
        """
        Validates Indian charges on SELL order:
        1. 5 bps adverse slippage: 2500 * 0.9995 = ₹2498.75
        2. Turnover: 10 * 2498.75 = ₹24987.50
        3. Stamp duty is strictly ₹0.00 on SELL.
        4. Net cash credited = Turnover - Total Charges.
        """
        cost = calculate_trade_friction(
            symbol="RELIANCE",
            side="SELL",
            quantity=10,
            price=Decimal("2500.00"),
            slippage_bps=5.0,
        )
        self.assertEqual(cost.executed_price, Decimal("2498.75"))
        self.assertEqual(cost.turnover, Decimal("24987.50"))
        self.assertEqual(cost.stamp_duty_inr, Decimal("0.00"))  # Zero on SELL
        self.assertEqual(cost.net_cash_impact_inr, cost.turnover - cost.total_charges_inr)

    def test_nse_penny_rounding_precision(self):
        """All currency fields must be strictly quantised to Decimal('0.01')."""
        cost = calculate_trade_friction(
            symbol="INFY",
            side="BUY",
            quantity=3,
            price=Decimal("1745.35"),
        )
        for field in [cost.executed_price, cost.turnover, cost.total_charges_inr, cost.net_cash_impact_inr]:
            self.assertEqual(field.as_tuple().exponent, -2)

    def test_invalid_trade_side_or_quantity_raises(self):
        """Invalid side or zero quantity raises ValueError."""
        with self.assertRaises(ValueError):
            calculate_trade_friction("TCS", "HOLD", 10, Decimal("3500.00"))

        with self.assertRaises(ValueError):
            calculate_trade_friction("TCS", "BUY", 0, Decimal("3500.00"))


class TestUSRegulatoryChargesCalculations(unittest.TestCase):
    """Tests US zero-commission trading and SEC Section 31 + FINRA TAF regulatory fees."""

    def test_us_buy_order_zero_charges(self):
        """US BUY order incurs zero brokerage and zero regulatory charges."""
        cost = calculate_us_trade_friction(
            symbol="AAPL",
            side="BUY",
            quantity=50,
            price=Decimal("180.00"),
        )
        self.assertEqual(cost.brokerage_inr, Decimal("0.00"))
        self.assertEqual(cost.total_charges_inr, Decimal("0.00"))
        # 5 bps adverse fill: 180 * 1.0005 = $180.09
        self.assertEqual(cost.executed_price, Decimal("180.09"))
        self.assertEqual(cost.net_cash_impact_inr, cost.turnover)

    def test_us_sell_order_sec_and_finra_charges(self):
        """
        US SELL order incurs SEC Section 31 fee and FINRA TAF strictly on sales:
        Price: $180.00, Qty: 50
        1. 5 bps adverse slippage: 180 * 0.9995 = $179.91
        2. Turnover: 50 * 179.91 = $8995.50
        3. Brokerage: $0.00
        4. SEC Fee (0.0000278 of turnover, min $0.01): 8995.50 * 0.0000278 = $0.25
        5. FINRA TAF ($0.000166/sh, min $0.01, max $8.30): 50 * 0.000166 = $0.0083 -> min $0.01
        6. Total Charges: 0.25 + 0.01 = $0.26
        7. Net Cash Impact: 8995.50 - 0.26 = $8995.24
        """
        cost = calculate_us_trade_friction(
            symbol="AAPL",
            side="SELL",
            quantity=50,
            price=Decimal("180.00"),
        )
        self.assertEqual(cost.executed_price, Decimal("179.91"))
        self.assertEqual(cost.turnover, Decimal("8995.50"))
        self.assertEqual(cost.total_charges_inr, Decimal("0.26"))
        self.assertEqual(cost.net_cash_impact_inr, Decimal("8995.24"))

    def test_us_finra_taf_max_cap_at_8_30(self):
        """FINRA TAF caps at exactly $8.30 for large institutional sell quantities."""
        cost = calculate_us_trade_friction(
            symbol="AAPL",
            side="SELL",
            quantity=100000,  # 100k * 0.000166 = $16.60 -> capped at $8.30
            price=Decimal("180.00"),
        )
        # Total charges = SEC ($499.75) + FINRA ($8.30)
        self.assertLessEqual(cost.total_charges_inr, Decimal("600.00"))


class TestMultiPointEquityCurveReconstruction(unittest.TestCase):
    """Tests the multi-point equity curve reconstruction algorithm from trade records."""

    def test_reconstruction_produces_n_plus_2_points(self):
        """
        Historical curve reconstruction for 3 trades produces exactly 3 + 2 = 5 points:
        Start -> Trade 1 -> Trade 2 -> Trade 3 -> Current.
        Completely eliminates the 2-point straight line bug!
        """
        recon = reconstruct_multipoint_equity_curve(
            initial_capital=100000.0,
            closed_trades_pnl=[1500.0, -800.0, 2200.0],
            unrealized_pnl=400.0,
        )
        self.assertEqual(recon["total_points"], 5)
        self.assertEqual(len(recon["equity_curve"]), 5)
        self.assertEqual(recon["labels"], ["Start", "Trade 1", "Trade 2", "Trade 3", "Current"])
        # Point values:
        # Start: 100000
        # Trade 1: 101500
        # Trade 2: 100700
        # Trade 3: 102900
        # Current: 102900 + 400 = 103300
        self.assertEqual(recon["equity_curve"], [100000.0, 101500.0, 100700.0, 102900.0, 103300.0])
        self.assertEqual(recon["final_equity"], 103300.0)

    def test_reconstruction_empty_trades(self):
        """When 0 trades exist, produces Start and Current points (2 points)."""
        recon = reconstruct_multipoint_equity_curve(
            initial_capital=100000.0,
            closed_trades_pnl=[],
            unrealized_pnl=0.0,
        )
        self.assertEqual(recon["total_points"], 2)
        self.assertEqual(recon["equity_curve"], [100000.0, 100000.0])

    def test_drawdown_peak_to_trough_calculation(self):
        """Computes peak-to-trough drawdown % correctly across equity curve steps."""
        # Start: 100k -> 110k (peak) -> 99k (drop 11k = 10%) -> 105k
        recon = reconstruct_multipoint_equity_curve(
            initial_capital=100000.0,
            closed_trades_pnl=[10000.0, -11000.0, 6000.0],
            unrealized_pnl=0.0,
        )
        self.assertEqual(recon["max_drawdown_amount"], 11000.0)
        # Peak was 110,000, DD was 11,000 -> 11000 / 110000 * 100 = 10.0%
        self.assertEqual(recon["max_drawdown_pct"], 10.0)

    def test_performance_metrics_win_rate_and_profit_factor(self):
        """calculate_performance_metrics validates win rate, profit factor, and Sharpe."""
        pnls = [Decimal("1000.00"), Decimal("2000.00"), Decimal("-1000.00")]
        charges = [Decimal("50.00"), Decimal("50.00"), Decimal("50.00")]
        curve = [Decimal("100000"), Decimal("101000"), Decimal("103000"), Decimal("102000"), Decimal("104000"), Decimal("105000")]

        metrics = calculate_performance_metrics(pnls, charges, curve)
        self.assertEqual(metrics.total_trades, 3)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertAlmostEqual(metrics.win_rate_pct, 66.67, places=1)
        # Gross profit = 3000, gross loss = 1000 -> PF = 3.0
        self.assertEqual(metrics.profit_factor, 3.0)
        self.assertIsNotNone(metrics.sharpe_ratio)


class TestDeterministicConfluenceScoring(unittest.TestCase):
    """Tests the deterministic 4-factor radial confluence scoring formula."""

    def test_max_confluence_score_100(self):
        """
        Optimal confluence:
        1. Trend: EMA 20 (2510) > EMA 50 (2500) and Close (2515) >= EMA 20 -> 30 pts
        2. Momentum: RSI at 55.0 (corridor 48-65) -> 25 pts
        3. MACD: Hist (+1.5) > 0 and expanding from prev (+1.0) -> 25 pts
        4. VWAP: Close (2515) >= VWAP (2505) -> 20 pts
        Total: 30 + 25 + 25 + 20 = 100.0 pts.
        """
        score = calculate_deterministic_confluence(
            close=2515.0,
            ema_20=2510.0,
            ema_50=2500.0,
            rsi_14=55.0,
            macd_hist=1.5,
            prev_macd_hist=1.0,
            vwap=2505.0,
        )
        self.assertEqual(score, 100.0)

    def test_min_confluence_score_0(self):
        """
        Fully bearish confluence:
        1. Trend: EMA 20 (2480) <= EMA 50 (2500) -> 0 pts
        2. Momentum: RSI at 30.0 (< 35) -> 0 pts
        3. MACD: Hist (-0.5) <= 0 -> 0 pts
        4. VWAP: Close (2470) < VWAP (2500) -> 0 pts
        Total: 0.0 pts.
        """
        score = calculate_deterministic_confluence(
            close=2470.0,
            ema_20=2480.0,
            ema_50=2500.0,
            rsi_14=30.0,
            macd_hist=-0.5,
            prev_macd_hist=-0.2,
            vwap=2500.0,
        )
        self.assertEqual(score, 0.0)

    def test_pullback_trend_score(self):
        """EMA 20 > EMA 50 but Close < EMA 20 awards 15 pts (pullback in uptrend)."""
        score = calculate_deterministic_confluence(
            close=2505.0,  # Below EMA 20 (2510)
            ema_20=2510.0,
            ema_50=2500.0,
            rsi_14=55.0,   # 25 pts
            macd_hist=1.5, # 25 pts
            prev_macd_hist=1.0,
            vwap=2500.0,   # 20 pts
        )
        # 15 + 25 + 25 + 20 = 85.0 pts
        self.assertEqual(score, 85.0)

    def test_rsi_corridor_scores(self):
        """Tests RSI score tiers (48-65 -> 25, 40-48 -> 12, >70 -> 5, <35 -> 0, else -> 10)."""
        base = dict(close=2515.0, ema_20=2510.0, ema_50=2500.0, macd_hist=1.5, prev_macd_hist=1.0, vwap=2505.0)
        # Non-RSI points: Trend (30) + MACD (25) + VWAP (20) = 75 pts.

        # RSI 45 -> +12 pts = 87
        self.assertEqual(calculate_deterministic_confluence(rsi_14=45.0, **base), 87.0)

        # RSI 75 -> +5 pts = 80
        self.assertEqual(calculate_deterministic_confluence(rsi_14=75.0, **base), 80.0)

        # RSI 32 -> +0 pts = 75
        self.assertEqual(calculate_deterministic_confluence(rsi_14=32.0, **base), 75.0)

        # RSI 38 -> +10 pts = 85
        self.assertEqual(calculate_deterministic_confluence(rsi_14=38.0, **base), 85.0)


if __name__ == "__main__":
    unittest.main()
