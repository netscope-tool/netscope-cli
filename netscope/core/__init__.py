"""
Core functionality components.
"""

from netscope.core.config import AppConfig
from netscope.core.detector import SystemDetector, SystemInfo
from netscope.core.executor import TestExecutor, CommandResult

__all__ = [
    "AppConfig",
    "SystemDetector",
    "SystemInfo",
    "TestExecutor",
    "CommandResult",
]