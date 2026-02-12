"""
NetScope - Network Diagnostics & Reporting Tool
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from netscope.core.config import AppConfig
from netscope.core.detector import SystemDetector
from netscope.core.executor import TestExecutor

__all__ = [
    "AppConfig",
    "SystemDetector",
    "TestExecutor",
    "__version__",
]