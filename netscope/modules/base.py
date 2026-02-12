"""
Base test class and models.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestResult(BaseModel):
    """Test result model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    test_name: str
    target: str
    status: str  # 'success', 'warning', 'failure'
    timestamp: datetime
    duration: float
    metrics: Dict[str, Any] = {}
    summary: Optional[str] = None
    raw_output: Optional[str] = None
    error: Optional[str] = None


class BaseTest(ABC):
    """Base class for all network tests."""
    
    def __init__(self, executor, csv_handler):
        self.executor = executor
        self.csv_handler = csv_handler
    
    @abstractmethod
    def run(self, target: str) -> TestResult:
        """
        Run the test.
        
        Args:
            target: Target IP or hostname
            
        Returns:
            TestResult object
        """
        pass
    
    @abstractmethod
    def parse_output(self, output: str) -> Dict[str, Any]:
        """
        Parse command output.
        
        Args:
            output: Raw command output
            
        Returns:
            Parsed metrics dictionary
        """
        pass