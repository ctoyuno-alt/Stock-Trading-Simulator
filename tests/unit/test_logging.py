"""
Unit tests for structured logging and secret masking.
"""

import json
import logging
import unittest
from backend.app.core.logging import MaskingJSONFormatter


class TestStructuredLogging(unittest.TestCase):

    def test_json_formatter_masks_secrets(self):
        formatter = MaskingJSONFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=15,
            msg="User login attempted with password=mysecretpass and api_key=AIzaSyTest1234567890123456789012345",
            args=(),
            exc_info=None,
        )
        record.extra_context = {
            "gemini_api_key": "AIzaSyTestKeyHere",
            "db_password": "supersecretpassword",
            "normal_field": "public_data",
        }

        formatted = formatter.format(record)
        data = json.loads(formatted)

        self.assertEqual(data["service"], "test-service")
        self.assertEqual(data["level"], "INFO")
        self.assertIn("context", data)
        self.assertEqual(data["context"]["gemini_api_key"], "********")
        self.assertEqual(data["context"]["db_password"], "********")
        self.assertEqual(data["context"]["normal_field"], "public_data")
        # Check that AIza key pattern in message was masked
        self.assertNotIn("AIzaSyTest1234567890123456789012345", data["message"])
        self.assertIn("********", data["message"])


if __name__ == "__main__":
    unittest.main()
