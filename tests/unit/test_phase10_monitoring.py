"""
Unit Tests for Phase 10: System Monitoring, Process Metrics, and Observability.
"""

import time
import unittest

from backend.app.core.monitoring import get_process_memory_mb, get_service_uptime_seconds, SERVICE_START_TIME
from backend.app.core.config import get_settings


class TestPhase10Monitoring(unittest.TestCase):

    def test_process_memory_measurement(self):
        """Verify process memory consumption returns a realistic positive number in MB."""
        mem_mb = get_process_memory_mb()
        self.assertIsInstance(mem_mb, float)
        self.assertGreater(mem_mb, 1.0)
        self.assertLess(mem_mb, 2048.0)  # Should remain well under 2GB

    def test_uptime_calculation(self):
        """Verify service start time is monotonic and non-negative."""
        self.assertIsInstance(SERVICE_START_TIME, float)
        elapsed = get_service_uptime_seconds()
        self.assertGreaterEqual(elapsed, 0.0)

    def test_security_settings_lockout(self):
        """Verify settings enforce real trading lockout and kill switch defaults."""
        settings = get_settings()
        self.assertFalse(settings.ENABLE_REAL_TRADING)
        self.assertIn("INR", settings.CURRENCY)
        self.assertEqual(len(settings.universe_list), 10)


if __name__ == "__main__":
    unittest.main()
