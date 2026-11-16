"""
End-to-End Integration Test for Entire AI Paper Trading Platform Pipeline.

Exercises all core architectural layers:
1. Ingestion: Provider & Candle data validation.
2. Quantitative Indicators: EMA 20/50, RSI 14, MACD (12/26/9), VWAP.
3. Deterministic Strategy: Multi-factor confluence & signal generation.
4. Gemini AI Synthesis: Schema-validated interpretation with disclaimers.
5. Risk Management: 1.0% equity risk sizing and pre-trade validations.
6. Execution Friction: Slippage, Brokerage, STT, Exchange fees, GST, Stamp Duty.
7. Performance Analytics: Win Rate, Profit Factor, Drawdown, Sharpe Ratio.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.ai.gemini_analyzer import GeminiMarketAnalyzer
from backend.app.ai.schemas import AI_DISCLAIMER_TEXT, MarketAnalysisSummary
from backend.app.market_data.yfinance_provider import YFinanceProvider
from indicators.engine import TechnicalIndicatorEngine
from strategies.swing_strategy import EMAMACDSwingStrategy
from trading.charges import calculate_trade_friction
from trading.metrics import calculate_performance_metrics
from trading.risk import calculate_position_size, validate_order_risk

IST_ZONE = ZoneInfo("Asia/Kolkata")


class TestEndToEndPipeline(unittest.TestCase):

    def test_complete_quant_pipeline_flow(self):
        # ----------------------------------------------------------------------
        # STAGE 1: Market Data Ingestion & Integrity Validation
        # ----------------------------------------------------------------------
        symbol = "RELIANCE"
        batch = YFinanceProvider.generate_synthetic_history(
            symbol=symbol,
            start_price=Decimal("2500.00"),
            days=100,
            trend=0.0012,
            volatility=0.012,
        )
        self.assertIsNotNone(batch.validation)
        self.assertTrue(batch.validation.is_valid, "Stage 1 failed: Market data validation rejected candles.")
        self.assertEqual(len(batch.candles), 100)

        # ----------------------------------------------------------------------
        # STAGE 2: Quantitative Technical Indicators
        # ----------------------------------------------------------------------
        indicator_engine = TechnicalIndicatorEngine()
        series = indicator_engine.compute(symbol, batch.candles, require_full_warmup=True)
        snapshot = series.snapshot

        self.assertTrue(snapshot.is_warmed_up, "Stage 2 failed: Indicator series not warmed up.")
        self.assertIsNotNone(snapshot.ema_fast_20)
        self.assertIsNotNone(snapshot.ema_slow_50)
        self.assertIsNotNone(snapshot.rsi_14)
        self.assertIsNotNone(snapshot.macd_histogram)
        self.assertIsNotNone(snapshot.vwap)

        # ----------------------------------------------------------------------
        # STAGE 3: Deterministic Strategy Evaluation
        # ----------------------------------------------------------------------
        strategy = EMAMACDSwingStrategy(min_risk_reward=2.0)
        signal = strategy.generate_signal(symbol, batch.candles)

        self.assertIn(signal.action.value, ["BUY", "SELL", "HOLD"], "Stage 3 failed: Invalid signal action.")
        self.assertGreater(signal.technical_score, 0.0)
        self.assertLess(signal.suggested_stop_loss, signal.entry_price)
        self.assertGreater(signal.suggested_take_profit, signal.entry_price)
        self.assertGreaterEqual(signal.risk_reward_ratio, 2.0)

        # ----------------------------------------------------------------------
        # STAGE 4: Gemini AI Grounded Analysis & Schema Validation
        # ----------------------------------------------------------------------
        analyzer = GeminiMarketAnalyzer(api_key="")
        ai_summary = asyncio.run(
            analyzer.analyze_market_state(
                symbol=symbol,
                snapshot=snapshot,
                signal=signal,
            )
        )
        self.assertIsInstance(ai_summary, MarketAnalysisSummary, "Stage 4 failed: AI output not schema compliant.")
        self.assertEqual(ai_summary.symbol, symbol)
        self.assertIn("DISCLAIMER", ai_summary.disclaimer)
        self.assertEqual(ai_summary.disclaimer, AI_DISCLAIMER_TEXT)

        # ----------------------------------------------------------------------
        # STAGE 5: Risk Management & 1% Equity Position Sizing
        # ----------------------------------------------------------------------
        virtual_equity = Decimal("100000.00")
        available_cash = Decimal("100000.00")
        sizing = calculate_position_size(
            equity=virtual_equity,
            available_cash=available_cash,
            entry_price=signal.entry_price,
            stop_loss_price=signal.suggested_stop_loss,
            max_risk_pct=0.01,
            max_allocation_pct=0.20,
        )

        self.assertTrue(sizing.is_approved, f"Stage 5 failed: Sizing rejected - {sizing.rejection_reason}")
        self.assertGreater(sizing.quantity, 0)
        # Verify 1% risk constraint strictly adhered to
        self.assertLessEqual(sizing.total_risk_inr, virtual_equity * Decimal("0.01"))
        # Verify 20% concentration cap strictly adhered to
        self.assertLessEqual(sizing.capital_required_inr, virtual_equity * Decimal("0.20"))

        risk_val = validate_order_risk(
            symbol=symbol,
            side="BUY",
            quantity=sizing.quantity,
            entry_price=signal.entry_price,
            stop_loss_price=signal.suggested_stop_loss,
            open_positions_count=0,
            existing_symbols=set(),
            enforce_market_hours=False,
        )
        self.assertTrue(risk_val.is_valid, f"Stage 5 failed: Pre-trade risk failed: {risk_val.rejection_reasons}")

        # ----------------------------------------------------------------------
        # STAGE 6: Execution Friction & Indian Regulatory Taxes
        # ----------------------------------------------------------------------
        buy_friction = calculate_trade_friction(
            symbol=symbol,
            side="BUY",
            quantity=sizing.quantity,
            price=signal.entry_price,
            slippage_bps=5.0,
        )
        self.assertGreater(buy_friction.executed_price, buy_friction.requested_price)  # Adverse slippage
        self.assertEqual(buy_friction.brokerage_inr, Decimal("20.00"))
        self.assertGreater(buy_friction.stt_tax_inr, Decimal("0.00"))
        self.assertGreater(buy_friction.stamp_duty_inr, Decimal("0.00"))  # Stamp duty on BUY
        self.assertGreater(buy_friction.gst_inr, Decimal("0.00"))
        self.assertEqual(
            buy_friction.net_cash_impact_inr,
            buy_friction.turnover + buy_friction.total_charges_inr,
            "Stage 6 failed: Buy net cash mismatch.",
        )

        # ----------------------------------------------------------------------
        # STAGE 7: Performance Analytics & Trade Accounting
        # ----------------------------------------------------------------------
        realized_pnls = [Decimal("1200.00"), Decimal("-450.00"), Decimal("850.00")]
        charges_paid = [Decimal("65.00"), Decimal("42.00"), Decimal("50.00")]
        equity_curve = [Decimal("100000.00"), Decimal("101200.00"), Decimal("100750.00"), Decimal("101600.00")]

        metrics = calculate_performance_metrics(
            realized_pnls=realized_pnls,
            charges_paid=charges_paid,
            equity_curve=equity_curve,
        )
        self.assertEqual(metrics.total_trades, 3)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertAlmostEqual(metrics.win_rate_pct, 66.67, places=1)
        self.assertEqual(metrics.total_gross_profit_inr, Decimal("2050.00"))
        self.assertEqual(metrics.total_gross_loss_inr, Decimal("450.00"))
        self.assertAlmostEqual(metrics.profit_factor, 4.56, places=2)
        self.assertEqual(metrics.total_net_realized_pnl_inr, Decimal("1600.00"))
        self.assertGreater(metrics.total_charges_paid_inr, Decimal("150.00"))


if __name__ == "__main__":
    unittest.main()
