"""
Core Process Telemetry and Resource Monitoring Utilities.
"""

import resource
import time

SERVICE_START_TIME = time.time()


def get_process_memory_mb() -> float:
    """Returns the resident set size (RSS) memory consumption of the Python process in MB."""
    usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(usage_kb / 1024.0, 2)


def get_service_uptime_seconds() -> float:
    """Returns total elapsed seconds since service initialization."""
    return round(time.time() - SERVICE_START_TIME, 1)
