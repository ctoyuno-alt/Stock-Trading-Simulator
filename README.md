# Gemini-Powered AI Paper Trading Simulator (NSE/BSE)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An institutional-grade, broker-independent AI-assisted paper trading and quantitative research platform tailored for the **National Stock Exchange (NSE)** and **Bombay Stock Exchange (BSE)** of India.

---

## ⚠️ Important Disclaimer & Safety Guardrails
- **Paper Trading Only:** This system simulates trade execution strictly in a sandbox environment with virtual funds (Initial virtual equity: ₹100,000 INR).
- **No Broker Connection:** The application is architecturally decoupled from real broker APIs (Zerodha Kite, Groww, Angel One, Upstox, etc.) and will never place live financial orders.
- **AI As Analysis Assistant:** Google Gemini is utilized purely to explain technical indicators, summarize reliable news, evaluate signal confluence, and detect conflicting patterns. The **deterministic Python quantitative engine** strictly enforces all trading rules, risk budgets, stop-loss limits, and position sizing. AI confidence is an informational heuristic, **never a guarantee of profit**.

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

## Trading Configuration (Indian Stock Market)
- **Base Currency:** Indian Rupee (INR / ₹)
- **Primary Exchange:** NSE (National Stock Exchange of India)
- **Trading Style:** Swing Trading (Multi-day to multi-week holding periods)
- **Universe:** Top 10 Liquid NSE Large-caps: `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`, `BHARTIARTL`, `SBIN`, `ITC`, `LT`, `TATAMOTORS`.
- **Trading Session:** 09:15 to 15:30 IST (Asia/Kolkata). System prevents trade simulation outside trading hours and on NSE exchange holidays.
- **Risk Budget:** Maximum risk per position is capped strictly at **1.0% of virtual equity**.
- **Mandatory Stop-Loss:** Every trade must have a mathematically derived stop-loss prior to execution.
- **Friction & Taxes Simulated:**
  - Brokerage: ₹20 / order (discount broker standard)
  - Securities Transaction Tax (STT): 0.1% on delivery turnover
  - Exchange Turnover Charges: 0.00345%
  - GST: 18% on (Brokerage + Exchange Charges + SEBI Fees)
  - SEBI Turnover Charges: 0.0001%
  - Stamp Duty: 0.015% (Buy side)
  - Slippage: Configurable basis points (default: 5 bps / 0.05%)

---

## Project Directory Structure

```text
Stock-Trading-Simulator/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/              # API Endpoints (health, market-data, portfolio, backtest)
│   │   ├── core/             # Configuration, logging, security, safety kill-switch
│   │   └── main.py           # FastAPI entrypoint
│   └── requirements.txt      # Backend dependencies
├── indicators/               # Quantitative Indicators (EMA, RSI, MACD, VWAP)
├── strategies/               # Deterministic Strategy Logic (Trend-following swing)
├── trading/                  # Paper Trading Engine (Ledger, Order Execution, Sizing, Risk)
├── database/                 # SQLAlchemy 2.0 Async Models, Engine & Migrations
├── dashboard/                # Streamlit Multi-Page Interactive Dashboard
│   ├── app.py                # Dashboard entrypoint
│   └── requirements.txt      # Dashboard dependencies
├── docker/                   # Dockerfiles for backend and dashboard
├── scripts/                  # Utility scripts (data warmup, db migrations, backup/restore)
├── tests/                    # Pytest suite
│   ├── unit/                 # Unit tests (indicators, sizing, stop-loss, taxes)
│   └── integration/          # Integration tests (ledger, engine, data pipeline)
├── docker-compose.yml        # Multi-container orchestration (Backend, DB, Dashboard)
├── .env.example              # Environment variables template
├── .gitignore                # Git exclusions
└── README.md                 # Project documentation
```

---

## Implementation Roadmap
- [x] **Phase 1: Environment Verification & Repository Initialization**
- [ ] **Phase 2: Docker Compose & PostgreSQL Setup**
- [ ] **Phase 3: Historical NSE Market-Data Ingestion**
- [ ] **Phase 4: Technical Indicator Engine**
- [ ] **Phase 5: Deterministic Swing-Trading Strategy**
- [ ] **Phase 6: Gemini API Integration & Structured Analysis**
- [ ] **Phase 7: Paper Trading Engine & Risk Management**
- [ ] **Phase 8: Streamlit Dashboard**
- [ ] **Phase 9: Backtesting & Automated Tests**
- [ ] **Phase 10: Monitoring, Backups, Security Hardening & Documentation**
