# Quantum Trader — Institutional AI Paper Trading Simulator (NSE & US Equities)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.41+-FF4B4B.svg)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 279 Passed](https://img.shields.io/badge/Tests-279%20Passed-brightgreen.svg)]()

An institutional-grade, broker-independent quantitative research and paper trading platform engineered for **Indian Equities (NSE/BSE)** and **US Mega-Caps (NYSE/NASDAQ)**, featuring a Bloomberg Terminal / TradingView / Linear-inspired dark UI.

---

## ⚠️ Important Institutional Disclaimers & Safety Guardrails
- **Paper Trading Only:** The application simulates virtual execution strictly in a sandbox environment with dual virtual accounts (Default starting capital: **₹100,000.00 INR** for NSE and **$25,000.00 USD** for US Mega-Caps).
- **No Broker Connection:** Real order execution is architecturally decoupled and hard-locked to disabled (`ENABLE_REAL_TRADING=false`). The system will never place real financial orders.
- **AI as Analysis Assistant:** Google Gemini is utilized purely to explain technical indicators, summarize relevant news, evaluate signal confluence, and detect conflicting patterns. The **deterministic Python quantitative engine** strictly enforces all trading rules, risk budgets, stop-loss limits, and position sizing.
- **No Guaranteed Returns:** AI confidence is an informational heuristic evaluating technical alignment clarity, **never a probability of profit or financial guarantee**.

---

## Architecture Overview

```
                         +-----------------------------+
                         |      Market Data Feeds      |
                         | (yfinance -> Broker Adapter)|
                         +--------------+--------------+
                                        |
                                        v
+-----------------------+     +-------------------+     +-------------------------+
|   Google Gemini AI    |<--->| Technical Engine  |---> | Quantitative Strategy   |
| (Structured Reasoning)|     | (EMA, RSI, MACD)  |     | (Deterministic Signals) |
+-----------------------+     +-------------------+     +------------+------------+
                                                                     |
                                                                     v
                                                        +-------------------------+
                                                        |   Risk & Sizing Engine  |
                                                        | (1% Risk, Indian Taxes) |
                                                        +------------+------------+
                                                                     |
                                                                     v
                                                        +-------------------------+
                                                        |   Paper Trading Engine  |
                                                        |  (Ledger & Execution)   |
                                                        +------------+------------+
                                                                     |
       +-------------------------------------------------------------+
       |                                                             |
       v                                                             v
+---------------+                                           +-----------------+
| PostgreSQL DB |                                           | Streamlit & API |
| (Ledger/State)|                                           |   (Dashboard)   |
+---------------+                                           +-----------------+
```

---

## Technology Stack

| Layer | Component | Version / Library |
| :--- | :--- | :--- |
| **Language & Runtime** | Python | 3.12+ (Tested on 3.13) |
| **Backend REST API** | FastAPI, Uvicorn, Pydantic v2 | FastAPI 0.115.6, Uvicorn 0.34.0 |
| **Database & ORM** | PostgreSQL 16 Alpine, SQLAlchemy 2.0 Async, asyncpg | SQLAlchemy 2.0.36, asyncpg 0.30.0 |
| **Database Migrations** | Alembic | Alembic 1.14.0 |
| **Interactive Dashboard** | Streamlit, Plotly, TradingView, Custom Dark UI | Streamlit 1.41.1, Plotly 5.24.1, TradingView Lightweight Charts (HTML5 Canvas) + Advanced Widget, Obsidian Dark Design System (`Inter` / `JetBrains Mono`) |
| **Quantitative Indicators** | NumPy, pandas | EMA (20/50), RSI (14), MACD (12, 26, 9), VWAP |
| **Artificial Intelligence** | Google Gemini API (gemini-2.5-flash) | Google GenAI SDK with grounded structured schemas |
| **Containerization** | Docker, Docker Compose | Non-root users (`appuser`, `streamlituser`), memory tuned |
| **Observability** | Structured JSON Logging, Prometheus | `python-json-logger`, `/metrics` endpoint |

---

## Indian Stock Market Configuration (NSE)

### 1. Active Large-Cap Universe
Tracks the top 10 liquid NSE equities with standard tick size of **₹0.05** and lot size of **1 share**:
- `RELIANCE` (Reliance Industries Ltd - Energy/Conglomerate)
- `TCS` (Tata Consultancy Services Ltd - IT Services)
- `INFY` (Infosys Ltd - IT Services)
- `HDFCBANK` (HDFC Bank Ltd - Private Banking)
- `ICICIBANK` (ICICI Bank Ltd - Private Banking)
- `BHARTIARTL` (Bharti Airtel Ltd - Telecom)
- `SBIN` (State Bank of India - Public Banking)
- `ITC` (ITC Ltd - FMCG)
- `LT` (Larsen & Toubro Ltd - Infrastructure)
- `TATAMOTORS` (Tata Motors Ltd - Automotive)

### 2. Market Sessions & Holiday Calendar
- **Regular Cash Market Hours:** 09:15 to 15:30 IST (`Asia/Kolkata`), Monday through Friday.
- **Enforcement:** Orders placed outside trading hours or on official NSE holidays are automatically rejected unless session bypass is explicitly flagged for simulation.

### 3. Institutional Indian Transaction Frictions
Simulated on every virtual trade:
- **Brokerage:** Flat ₹20.00 per executed order (discount broker standard).
- **Securities Transaction Tax (STT):** 0.1% on delivery turnover (Buy and Sell).
- **Exchange Turnover Charges (NSE):** 0.00345% of turnover.
- **SEBI Charges:** ₹10 per crore (0.0001% of turnover).
- **Stamp Duty:** 0.015% of turnover (applicable on BUY orders only).
- **GST:** 18% applied to (Brokerage + Exchange Charges + SEBI Fees).
- **Slippage Simulation:** 5 basis points (0.05%) applied adverse to market price.

### 4. 1.0% Equity Risk Position Sizing Formula
$$\text{Quantity} = \min\left( \left\lfloor \frac{\text{Virtual Equity} \times 0.01}{\text{Entry Price} - \text{Stop Loss Price}} \right\rfloor, \; \left\lfloor \frac{\text{Virtual Equity} \times 0.20}{\text{Entry Price}} \right\rfloor, \; \left\lfloor \frac{\text{Available Cash}}{\text{Entry Price}} \right\rfloor \right)$$

---

## US Stock Market Configuration (NYSE/NASDAQ)

### 1. Active Mega-Cap Universe
Tracks 10 liquid US Mega-Cap equities with standard tick size of **$0.01** and lot size of **1 share**:
- `AAPL` (Apple Inc. - NASDAQ)
- `MSFT` (Microsoft Corporation - NASDAQ)
- `NVDA` (NVIDIA Corporation - NASDAQ)
- `AMZN` (Amazon.com, Inc. - NASDAQ)
- `GOOGL` (Alphabet Inc. - NASDAQ)
- `META` (Meta Platforms, Inc. - NASDAQ)
- `TSLA` (Tesla, Inc. - NASDAQ)
- `BRK-B` (Berkshire Hathaway Inc. Class B - NYSE)
- `JPM` (JPMorgan Chase & Co. - NYSE)
- `V` (Visa Inc. - NYSE)

### 2. Market Sessions
- **Regular Cash Market Hours:** 09:30 to 16:00 ET (`America/New_York`), Monday through Friday.
- **Enforcement:** Orders outside regular US market hours or on NYSE holidays are rejected unless session bypass is flagged for sandbox simulation.

### 3. Institutional US Transaction Frictions
Simulated on every virtual US trade:
- **Brokerage:** **$0.00** commission per order.
- **SEC Section 31 Fee:** `0.0000278` of notional turnover (strictly on SELL exit orders, min `$0.01`).
- **FINRA TAF:** `$0.000166` per share (strictly on SELL exit orders, min `$0.01`, max `$8.30`).
- **Slippage Simulation:** 5 basis points (0.05%) applied adverse to market price.

---

## Quantum Trader UI Overhaul & Dashboard Architecture

### Design System & Visual Tokens
Configured in `.streamlit/config.toml` and `dashboard/styles.py` with Google Fonts (`Inter` for UI copy and `JetBrains Mono` for tabular financial metrics):
- **Surfaces & Borders:** `#080B11` (Obsidian Canvas), `#0E131F` (Slate Surface), `#131A2B` (Elevated Surface), `#1E2638` (Structural Borders).
- **Semantic Accents:** `#FF9900` (Bloomberg Amber), `#00E676` (Emerald Bullish), `#FF3366` (Crimson Bearish), `#00F2FE` (Cyan Technical), `#A855F7` (Purple AI/VWAP).

### Global Chrome
- **Live Ticker Marquee (`dashboard/components/ticker.py`):** CSS-animated streaming market ticker across active NSE and US instruments.
- **Institutional Top App Bar (`dashboard/components/header.py`):** Market switcher (`NSE INR` / `US USD`), active session clock, kill-switch status pill, and user RBAC badge.
- **Authentication Gate (`dashboard/auth.py`):** JWT sign-in, self-registration, and dual-tier password recovery screen.

### 8 Modular Tabs (`dashboard/tabs/`)
1. `tab_market.py` — **Market & Technicals:** Live KPIs, TradingView Lightweight Charts (HTML5 Canvas) + TradingView Advanced Widget, and 3-panel Plotly Candlestick/Volume/MACD + RSI charts.
2. `tab_ai.py` — **AI Confluence Analysis:** Deterministic 4-factor strategy scoring, radial SVG/Plotly confluence gauge (`dashboard/components/gauges.py`), and on-demand grounded Gemini interpretation.
3. `tab_autotrader.py` — **Autonomous AI Auto-Trader:** Strategy execution controls, risk thresholds, decision audit trails, 24/7 daemon management, and GTT bracket orders.
4. `tab_positions.py` — **Positions & Execution:** Open exposure table, one-click position close, reactive 1% risk sizer, R:R ratio preview badge, and live NSE & US statutory friction breakdown cards.
5. `tab_ledger.py` — **Trade Ledger & Performance:** Sharpe ratio, max drawdown, reconstructed multi-point (`N + 2`) equity curve, filterable trade ledger, and CSV export.
6. `tab_backtest.py` — **Historical Backtest:** Walk-forward simulation with NSE/US statutory frictions, equity & underwater drawdown curves, CAGR/Sortino/Calmar metrics, session caching, and CSV export.
7. `tab_health.py` — **System Health & Freshness:** Backend readiness probe, DB latency sparkline, dual NSE/US market clocks, searchable universe inspector, and programmatic API key provisioning.
8. `tab_admin.py` — **Admin User & Account Management:** Admin-only RBAC user directory, platform capital KPIs, role/status/API-key/password/capital funding workbench, and immutable audit trail.

---

## Repository Structure

```text
Stock-Trading-Simulator/
├── .streamlit/
│   └── config.toml           # Streamlit institutional dark theme & server config
├── backend/
│   ├── app/
│   │   ├── ai/               # Gemini AI grounded analyzer and schemas
│   │   ├── api/              # FastAPI endpoints (health, market, indicators, strategy, trading, backtest, monitoring, admin, auth)
│   │   ├── core/             # Configuration, secret-masking logging, market schedule
│   │   └── main.py           # FastAPI application entrypoint
│   └── requirements.txt      # Pinned backend dependencies
├── indicators/               # Quantitative indicators (EMA, RSI, MACD, VWAP, unified engine)
├── strategies/               # Deterministic multi-factor swing trading state machine
├── trading/                  # Paper engine, 1% risk sizing, ledger, NSE/US charges, metrics, backtest engine
├── database/                 # SQLAlchemy 2.0 async models, session, init_db, Alembic migrations
├── dashboard/
│   ├── app.py                # Slim Quantum Trader Streamlit orchestrator (< 300 lines)
│   ├── auth.py               # Authentication & password recovery UI
│   ├── styles.py             # Institutional dark theme design tokens & CSS
│   ├── api_client.py         # Typed REST client for FastAPI backend
│   ├── components/           # charts.py, gauges.py, header.py, ticker.py, tradingview.py
│   └── tabs/                 # 8 modular tab views (tab_market .. tab_admin)
├── docker/                   # Hardened non-root Dockerfiles
├── scripts/                  # Data warmup, migrations, backup/restore, security audit
├── tests/
│   ├── unit/                 # 278 unit tests across 20 modules (core, math, indicators, strategy, AI, risk, auth, admin, US market, dashboard)
│   └── integration/          # Full 7-stage end-to-end integration test
├── docker-compose.yml        # Memory-tuned multi-service orchestration
├── .env.example              # Environment variables template
├── .gitignore                # Security-first ignore rules
└── README.md                 # Complete documentation
```

---

## Quickstart & Deployment Runbook

### 1. Configure Environment
```bash
cd /home/it/projects/Stock-Trading-Simulator

# Copy environment template
cp .env.example .env

# Edit .env to add your Google Gemini API key (optional - offline fallback works automatically)
nano .env
```

### 2. Deploy with Docker Compose
```bash
# Build and launch PostgreSQL, FastAPI Backend, and Streamlit Dashboard
docker compose up -d --build

# Verify container health and logs
docker compose ps
docker compose logs -f backend
```

- **Streamlit Dashboard:** [http://localhost:8501](http://localhost:8501)
- **FastAPI Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Metrics:** [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **System Readiness Probe:** [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

## Operational Runbooks

### Database Backup & Restore Runbook
The standalone script `scripts/backup_restore_db.sh` manages compressed database backups:

```bash
# Create timestamped compressed backup in ./backups/
./scripts/backup_restore_db.sh backup

# Restore database from backup
./scripts/backup_restore_db.sh restore backups/paper_trading_db_YYYYMMDD_HHMMSS.sql.gz
```

### Database Migrations Runbook (Alembic)
```bash
# Run all pending migrations to head
./scripts/run_migrations.sh upgrade head

# Rollback one migration
./scripts/run_migrations.sh downgrade -1
```

### Historical Market Data Ingestion Runbook
```bash
# Ingest 1 year of daily data for all 10 liquid stocks
python3 scripts/ingest_historical_data.py --period 1y --timeframe 1d

# Offline synthetic generation for sandbox testing
python3 scripts/ingest_historical_data.py --symbols RELIANCE,TCS,INFY --synthetic
```

### Security & Secret Scrubbing Audit
```bash
./scripts/security_audit.sh
```

---

## Automated Test Verification

Run all unit and integration tests with a single command:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Run the Quantum Trader dashboard verification suite (calculations, components, E2E workflows & defect guardrails, and headless smoke tests):

```bash
python3 -m unittest discover -s tests/unit -p "test_dashboard_*.py" -v
```

**Verified Test Suite (279 Tests Total across 21 Test Files):**
- `tests/unit/test_dashboard_calculations.py` (37 tests): 1% risk sizing invariants, R:R preview, NSE & US regulatory frictions, multi-point (`N + 2`) equity curve reconstruction, and deterministic 4-factor confluence scoring.
- `tests/unit/test_dashboard_components.py` (41 tests): Institutional dark CSS tokens, ticker tape marquee, Plotly candlestick/MACD/RSI/equity charts, TradingView Lightweight Canvas & widget serialization, and radial confluence gauge helpers.
- `tests/unit/test_dashboard_e2e.py` (16 tests): 7 pairwise cross-feature interactions, 4 end-to-end NSE/US/AutoTrader/Admin lifecycles, and 5 production-tab defect regression guardrails (including NSE & US statutory friction HTML cards).
- `tests/unit/test_dashboard_smoke.py` (76 tests): `DashboardAPIClient` HTTP transport & endpoints, auth gate & RBAC tab visibility, headless `dashboard/app.py` execution, uniform tab contracts, and adversarial `None`/error resilience.
- `tests/unit/test_admin_account_management.py` (25 tests): Admin RBAC security guardrails, user management, capital funding/reset, credential rotation, and audit logging.
- `tests/unit/test_security_auth.py` (12 tests): JWT auth, password hashing, RBAC guards, and API key authentication.
- `tests/unit/test_us_market.py` (9 tests): US Mega-Cap universe, `America/New_York` market hours, and SEC Section 31 / FINRA TAF calculations.
- `tests/unit/test_phase2_core.py` (8 tests): Config safety lock, credential masking, weekend closures, NSE holidays, Indian delivery tax calculations on BUY and SELL.
- `tests/unit/test_phase4_indicators.py` (7 tests): EMA precision, Golden/Death cross detection, RSI bounds, MACD warmup, VWAP daily reset, warmup threshold validation, full snapshot computation.
- `tests/unit/test_phase3_market_data.py` (6 tests): Universe metadata, symbol normalizer, candle data validation, anomaly detection, chronological ordering, synthetic data generator.
- `tests/unit/test_phase7_trading.py` (6 tests): 1% risk position sizing, concentration limits, cash constraints, duplicate prevention, minimum stop distance, performance metrics.
- `tests/unit/test_auto_trader.py` (6 tests): Autonomous AI auto-trader configuration, scanning, sizing, and audit trail.
- `tests/unit/test_password_recovery.py` (5 tests): Dual-tier self-service reset token lifecycle and admin password override.
- `tests/unit/test_risk_circuit_breaker.py` (5 tests): Daily loss circuit breaker and kill-switch enforcement.
- `tests/unit/test_phase5_strategy.py` (4 tests): Warmup rejection, BUY confluence with stop-loss/take-profit, SELL breakdown, walk-forward signal history.
- `tests/unit/test_phase6_ai.py` (4 tests): Profit disclaimers, prompt grounding with exact numbers, deterministic fallback synthesis, JSON markdown stripping.
- `tests/unit/test_virtual_exchange.py` (4 tests): Virtual exchange order matching, slippage, and fill execution.
- `tests/unit/test_phase9_backtest.py` (3 tests): Backtest warmup enforcement, invariant accounting verification, trade log charges audit.
- `tests/unit/test_phase10_monitoring.py` (3 tests): Process memory consumption, uptime calculation, security settings lockout.
- `tests/unit/test_logging.py` (1 test): JSON log formatting and scrubbing of embedded API keys and passwords.
- `tests/integration/test_end_to_end_pipeline.py` (1 test): Full 7-stage end-to-end integration pipeline.

---

## Complete REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health/live` | Process liveness check |
| `GET` | `/health/ready` | Database connection latency & safety check |
| `GET` | `/metrics` | Prometheus exposition format metrics |
| `GET` | `/api/v1/monitoring/diagnostics` | System telemetry, memory usage, and runtime state |
| `GET` | `/api/v1/system/status` | Trading session status, virtual capital, universe |
| `POST` | `/api/v1/system/kill-switch` | Emergency kill switch toggle |
| `GET` | `/api/v1/market-data/universe` | Tracked 10-stock universe with tick sizes |
| `GET` | `/api/v1/market-data/candles/{symbol}` | OHLCV historical candles with data quality audit |
| `POST` | `/api/v1/market-data/sync` | Ingest historical candles into database |
| `GET` | `/api/v1/indicators/{symbol}` | Indicator time series (EMA, RSI, MACD, VWAP) |
| `GET` | `/api/v1/indicators/snapshot/{symbol}` | Instantaneous latest indicator snapshot |
| `GET` | `/api/v1/strategies/signal/{symbol}` | Deterministic swing trading signal with stop/target |
| `GET` | `/api/v1/strategies/signals` | Multi-asset universe scanner |
| `POST` | `/api/v1/ai/analyze/{symbol}` | Grounded Gemini AI structured market interpretation |
| `POST` | `/api/v1/trading/orders/buy` | Place virtual BUY order with 1% risk sizing |
| `POST` | `/api/v1/trading/positions/{id}/close` | Manually close open position at market |
| `GET` | `/api/v1/trading/positions` | List open and closed virtual positions |
| `GET` | `/api/v1/trading/orders` | Chronological trade ledger order audit trail |
| `GET` | `/api/v1/trading/portfolio` | Account equity, cash balance, and open exposure |
| `GET` | `/api/v1/trading/metrics` | Win rate, profit factor, max drawdown, Sharpe ratio |
| `POST` | `/api/v1/backtest/run` | Execute walk-forward historical backtest |

---

## Roadmap & Status

- [x] **Phase 1: Environment Verification & Repository Initialization**
- [x] **Phase 2: Docker Compose & PostgreSQL Setup**
- [x] **Phase 3: Historical NSE Market-Data Ingestion**
- [x] **Phase 4: Technical Indicator Engine**
- [x] **Phase 5: Deterministic Swing-Trading Strategy**
- [x] **Phase 6: Gemini API Integration & Structured Analysis**
- [x] **Phase 7: Paper Trading Engine & Risk Management**
- [x] **Phase 8: Streamlit Dashboard**
- [x] **Phase 9: Backtesting & Automated Tests**
- [x] **Phase 10: Monitoring, Backups, Security Hardening & Documentation**
