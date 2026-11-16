"""
Structured JSON Logging for High-Reliability Quantitative Systems.

Ensures:
- ISO 8601 UTC timestamps.
- JSON-formatted log lines for centralized observability (ELK, Datadog, CloudWatch).
- Sensitive parameter masking (API keys, DB credentials, auth tokens).
"""

from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any, Dict


# Mask patterns for credentials in dictionary keys
SENSITIVE_KEY_PATTERNS = re.compile(
    r"(api_?key|password|secret|token|authorization|credential)",
    re.IGNORECASE
)

# Text-level masking patterns for embedded secrets in log messages
EMBEDDED_SECRET_PATTERNS = [
    # Google API Key format (AIza followed by 30 to 45 chars)
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,45}"), "********"),
    # Key-value secret patterns: password=xxx, api_key=xxx, secret=xxx, token=xxx
    (re.compile(r"((?:password|api_?key|secret|token|auth)\s*[=:]\s*['\"]?)([^'\"\s&,]+)", re.IGNORECASE), r"\1********"),
]


class MaskingJSONFormatter(logging.Formatter):
    """Custom logging formatter that serializes records to JSON and masks sensitive information."""

    def __init__(self, service_name: str = "paper-trading-backend") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # Base log payload
        log_payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Include exception traceback if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra attributes
        if hasattr(record, "extra_context") and isinstance(record.extra_context, dict):
            log_payload["context"] = self._mask_data(record.extra_context)

        # Mask sensitive keys and text in the final output
        sanitized_payload = self._mask_data(log_payload)
        return json.dumps(sanitized_payload, default=str)

    def _mask_data(self, data: Any) -> Any:
        if isinstance(data, dict):
            masked = {}
            for k, v in data.items():
                if SENSITIVE_KEY_PATTERNS.search(str(k)):
                    masked[k] = "********"
                else:
                    masked[k] = self._mask_data(v)
            return masked
        elif isinstance(data, list):
            return [self._mask_data(item) for item in data]
        elif isinstance(data, str):
            masked_str = data
            for pattern, repl in EMBEDDED_SECRET_PATTERNS:
                masked_str = pattern.sub(repl, masked_str)
            return masked_str
        return data


def setup_logging(log_level: str = "INFO", service_name: str = "paper-trading-backend") -> logging.Logger:
    """Configures structured JSON logging on root and application loggers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing stream handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(MaskingJSONFormatter(service_name=service_name))
    root_logger.addHandler(console_handler)

    # Quiet external verbose loggers
    logging.getLogger("uvicorn.access").handlers = [console_handler]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger
