"""
Application Configuration and Safety Guardrails.

Enforces:
- Strict paper-trading mode (real trading disabled by default).
- Indian stock market (NSE/BSE) trading conventions and calendar.
- Risk management boundaries (1% risk budget, stop loss mandates).
- Sanitized secret masking to prevent credentials leaking into logs.
- Dual-mode execution: uses Pydantic Settings when installed in container/venv,
  with transparent standard-library fallback for standalone environments.
"""

from decimal import Decimal
from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


def _parse_env_file(filepath: str = ".env") -> Dict[str, str]:
    """Lightweight standard library .env parser."""
    env_vars: Dict[str, str] = {}
    path = Path(filepath)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


if HAS_PYDANTIC:
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=False
        )

        ENVIRONMENT: str = "development"
        LOG_LEVEL: str = "INFO"
        DEBUG: bool = False

        ENABLE_REAL_TRADING: bool = Field(
            default=False,
            description="CRITICAL: Live order execution. Must remain False in paper-trading phase."
        )
        PAPER_TRADING_KILL_SWITCH: bool = Field(
            default=False,
            description="Global emergency halt. When True, all paper order placement is blocked."
        )

        PRIMARY_EXCHANGE: str = "NSE"
        SECONDARY_EXCHANGE: str = "BSE"
        CURRENCY: str = "INR"
        INITIAL_VIRTUAL_CAPITAL_INR: Decimal = Field(
            default=Decimal("100000.00"),
            description="Initial virtual capital in Indian Rupees (₹100,000.00)"
        )
        TRADING_UNIVERSE: str = (
            "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,"
            "BHARTIARTL.NS,SBIN.NS,ITC.NS,LT.NS,TATAMOTORS.NS"
        )

        MARKET_TIMEZONE: str = "Asia/Kolkata"
        MARKET_OPEN_TIME: str = "09:15"
        MARKET_CLOSE_TIME: str = "15:30"

        MAX_RISK_PER_TRADE: float = 0.005
        MAX_OPEN_POSITIONS: int = 2
        MAX_ALLOCATION_PER_POSITION: float = 0.10
        DEFAULT_RISK_REWARD_RATIO: float = 2.0
        MIN_STOP_LOSS_PCT: float = 0.015

        BROKERAGE_PER_ORDER_INR: Decimal = Decimal("20.00")
        STT_TAX_RATE: Decimal = Decimal("0.001")
        EXCHANGE_TURNOVER_RATE: Decimal = Decimal("0.0000345")
        SEBI_CHARGES_RATE: Decimal = Decimal("0.000001")
        STAMP_DUTY_RATE: Decimal = Decimal("0.00015")
        GST_RATE: Decimal = Decimal("0.18")
        SLIPPAGE_BPS: float = 5.0

        EMA_FAST_PERIOD: int = 20
        EMA_SLOW_PERIOD: int = 50
        RSI_PERIOD: int = 14
        RSI_OVERSOLD: float = 30.0
        RSI_OVERBOUGHT: float = 70.0
        MACD_FAST: int = 12
        MACD_SLOW: int = 26
        MACD_SIGNAL: int = 9

        GEMINI_API_KEY: str = Field(default="")
        GEMINI_MODEL: str = "gemini-2.5-flash"
        GEMINI_TEMPERATURE: float = 0.2
        GEMINI_TIMEOUT_SECONDS: int = 15

        DATA_PROVIDER: str = "yfinance"
        DATA_CACHE_TTL_MINUTES: int = 15

        POSTGRES_USER: str = "trader_user"
        POSTGRES_PASSWORD: str = "trader_secure_password"
        POSTGRES_DB: str = "paper_trading_db"
        POSTGRES_HOST: str = "postgres"
        POSTGRES_PORT: int = 5432
        DATABASE_URL: str = ""

        BACKEND_HOST: str = "0.0.0.0"
        BACKEND_PORT: int = 8000
        DASHBOARD_HOST: str = "0.0.0.0"
        DASHBOARD_PORT: int = 8501
        BACKEND_INTERNAL_URL: str = "http://backend:8000"

        # Authentication & JWT Security Settings
        JWT_SECRET_KEY: str = Field(
            default="quantum_trader_super_secure_jwt_secret_key_2026",
            description="HMAC-SHA256 signature key for issuing and validating JWT access tokens."
        )
        JWT_ALGORITHM: str = "HS256"
        JWT_EXPIRATION_HOURS: int = 24
        DEFAULT_ADMIN_USERNAME: str = "admin"
        DEFAULT_ADMIN_PASSWORD: str = "admin_secure_password"
        DEFAULT_ADMIN_EMAIL: str = "admin@quantumtrader.local"

        @field_validator("ENABLE_REAL_TRADING")
        @classmethod
        def validate_safety_lock(cls, v: bool) -> bool:
            if v:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: ENABLE_REAL_TRADING cannot be True in this phase. "
                    "This platform is strictly designated for paper trading and quantitative research."
                )
            return v

        @property
        def async_database_url(self) -> str:
            if self.DATABASE_URL:
                url = self.DATABASE_URL
                if url.startswith("postgresql://"):
                    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
                return url
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        @property
        def universe_list(self) -> List[str]:
            return [ticker.strip().upper() for ticker in self.TRADING_UNIVERSE.split(",") if ticker.strip()]

        def sanitized_dict(self) -> Dict[str, Any]:
            data = self.model_dump()
            sensitive_keys = {"gemini_api_key", "postgres_password", "database_url"}
            for key in sensitive_keys:
                if key in data and data[key]:
                    data[key] = "********"
            return data

else:
    class Settings:  # type: ignore
        """Standard-library fallback settings class for pre-container environments."""

        def __init__(self, **kwargs: Any) -> None:
            file_env = _parse_env_file(".env")
            merged = {**file_env, **os.environ, **kwargs}

            def _get(key: str, default: Any, cast_type: Any) -> Any:
                val = merged.get(key)
                if val is None:
                    return default
                if cast_type is bool:
                    return str(val).lower() in ("true", "1", "yes")
                if cast_type is Decimal:
                    return Decimal(str(val))
                return cast_type(val)

            self.ENVIRONMENT: str = _get("ENVIRONMENT", "development", str)
            self.LOG_LEVEL: str = _get("LOG_LEVEL", "INFO", str)
            self.DEBUG: bool = _get("DEBUG", False, bool)

            self.ENABLE_REAL_TRADING: bool = _get("ENABLE_REAL_TRADING", False, bool)
            if self.ENABLE_REAL_TRADING:
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: ENABLE_REAL_TRADING cannot be True in this phase. "
                    "This platform is strictly designated for paper trading and quantitative research."
                )

            self.PAPER_TRADING_KILL_SWITCH: bool = _get("PAPER_TRADING_KILL_SWITCH", False, bool)
            self.PRIMARY_EXCHANGE: str = _get("PRIMARY_EXCHANGE", "NSE", str)
            self.SECONDARY_EXCHANGE: str = _get("SECONDARY_EXCHANGE", "BSE", str)
            self.CURRENCY: str = _get("CURRENCY", "INR", str)
            self.INITIAL_VIRTUAL_CAPITAL_INR: Decimal = _get("INITIAL_VIRTUAL_CAPITAL_INR", Decimal("100000.00"), Decimal)
            self.TRADING_UNIVERSE: str = _get(
                "TRADING_UNIVERSE",
                "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,BHARTIARTL.NS,SBIN.NS,ITC.NS,LT.NS,TATAMOTORS.NS",
                str
            )
            self.MARKET_TIMEZONE: str = _get("MARKET_TIMEZONE", "Asia/Kolkata", str)
            self.MARKET_OPEN_TIME: str = _get("MARKET_OPEN_TIME", "09:15", str)
            self.MARKET_CLOSE_TIME: str = _get("MARKET_CLOSE_TIME", "15:30", str)

            self.MAX_RISK_PER_TRADE: float = _get("MAX_RISK_PER_TRADE", 0.005, float)
            self.MAX_OPEN_POSITIONS: int = _get("MAX_OPEN_POSITIONS", 2, int)
            self.MAX_ALLOCATION_PER_POSITION: float = _get("MAX_ALLOCATION_PER_POSITION", 0.10, float)
            self.DEFAULT_RISK_REWARD_RATIO: float = _get("DEFAULT_RISK_REWARD_RATIO", 2.0, float)
            self.MIN_STOP_LOSS_PCT: float = _get("MIN_STOP_LOSS_PCT", 0.015, float)

            self.BROKERAGE_PER_ORDER_INR: Decimal = _get("BROKERAGE_PER_ORDER_INR", Decimal("20.00"), Decimal)
            self.STT_TAX_RATE: Decimal = _get("STT_TAX_RATE", Decimal("0.001"), Decimal)
            self.EXCHANGE_TURNOVER_RATE: Decimal = _get("EXCHANGE_TURNOVER_RATE", Decimal("0.0000345"), Decimal)
            self.SEBI_CHARGES_RATE: Decimal = _get("SEBI_CHARGES_RATE", Decimal("0.000001"), Decimal)
            self.STAMP_DUTY_RATE: Decimal = _get("STAMP_DUTY_RATE", Decimal("0.00015"), Decimal)
            self.GST_RATE: Decimal = _get("GST_RATE", Decimal("0.18"), Decimal)
            self.SLIPPAGE_BPS: float = _get("SLIPPAGE_BPS", 5.0, float)

            self.EMA_FAST_PERIOD: int = _get("EMA_FAST_PERIOD", 20, int)
            self.EMA_SLOW_PERIOD: int = _get("EMA_SLOW_PERIOD", 50, int)
            self.RSI_PERIOD: int = _get("RSI_PERIOD", 14, int)
            self.RSI_OVERSOLD: float = _get("RSI_OVERSOLD", 30.0, float)
            self.RSI_OVERBOUGHT: float = _get("RSI_OVERBOUGHT", 70.0, float)
            self.MACD_FAST: int = _get("MACD_FAST", 12, int)
            self.MACD_SLOW: int = _get("MACD_SLOW", 26, int)
            self.MACD_SIGNAL: int = _get("MACD_SIGNAL", 9, int)

            self.GEMINI_API_KEY: str = _get("GEMINI_API_KEY", "", str)
            self.GEMINI_MODEL: str = _get("GEMINI_MODEL", "gemini-2.5-flash", str)
            self.GEMINI_TEMPERATURE: float = _get("GEMINI_TEMPERATURE", 0.2, float)
            self.GEMINI_TIMEOUT_SECONDS: int = _get("GEMINI_TIMEOUT_SECONDS", 15, int)

            self.DATA_PROVIDER: str = _get("DATA_PROVIDER", "yfinance", str)
            self.DATA_CACHE_TTL_MINUTES: int = _get("DATA_CACHE_TTL_MINUTES", 15, int)

            self.POSTGRES_USER: str = _get("POSTGRES_USER", "trader_user", str)
            self.POSTGRES_PASSWORD: str = _get("POSTGRES_PASSWORD", "trader_secure_password", str)
            self.POSTGRES_DB: str = _get("POSTGRES_DB", "paper_trading_db", str)
            self.POSTGRES_HOST: str = _get("POSTGRES_HOST", "postgres", str)
            self.POSTGRES_PORT: int = _get("POSTGRES_PORT", 5432, int)
            self.DATABASE_URL: str = _get("DATABASE_URL", "", str)

            self.BACKEND_HOST: str = _get("BACKEND_HOST", "0.0.0.0", str)
            self.BACKEND_PORT: int = _get("BACKEND_PORT", 8000, int)
            self.DASHBOARD_HOST: str = _get("DASHBOARD_HOST", "0.0.0.0", str)
            self.DASHBOARD_PORT: int = _get("DASHBOARD_PORT", 8501, int)
            self.BACKEND_INTERNAL_URL: str = _get("BACKEND_INTERNAL_URL", "http://backend:8000", str)

            self.JWT_SECRET_KEY: str = _get("JWT_SECRET_KEY", "quantum_trader_super_secure_jwt_secret_key_2026", str)
            self.JWT_ALGORITHM: str = _get("JWT_ALGORITHM", "HS256", str)
            self.JWT_EXPIRATION_HOURS: int = _get("JWT_EXPIRATION_HOURS", 24, int)
            self.DEFAULT_ADMIN_USERNAME: str = _get("DEFAULT_ADMIN_USERNAME", "admin", str)
            self.DEFAULT_ADMIN_PASSWORD: str = _get("DEFAULT_ADMIN_PASSWORD", "admin_secure_password", str)
            self.DEFAULT_ADMIN_EMAIL: str = _get("DEFAULT_ADMIN_EMAIL", "admin@quantumtrader.local", str)

        @property
        def async_database_url(self) -> str:
            if self.DATABASE_URL:
                url = self.DATABASE_URL
                if url.startswith("postgresql://"):
                    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
                return url
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        @property
        def universe_list(self) -> List[str]:
            return [ticker.strip().upper() for ticker in self.TRADING_UNIVERSE.split(",") if ticker.strip()]

        def sanitized_dict(self) -> Dict[str, Any]:
            data = vars(self).copy()
            sensitive_keys = {"GEMINI_API_KEY", "POSTGRES_PASSWORD", "DATABASE_URL"}
            for key in sensitive_keys:
                if key in data and data[key]:
                    data[key] = "********"
            return data


@lru_cache()
def get_settings() -> Settings:
    """Cached factory function for singleton settings instance."""
    return Settings()
