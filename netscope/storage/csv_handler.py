"""
CSV file handling for test results.
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Any
from loguru import logger


class CSVHandler:
    """Handle CSV file operations for test results."""
    
    def __init__(self, csv_file: Path):
        """
        Initialize CSV handler.
        
        Args:
            csv_file: Path to CSV file
        """
        self.csv_file = csv_file
        self.fieldnames = [
            'timestamp',
            'test_name',
            'target',
            'metric',
            'value',
            'status',
            'details',
        ]
        
        # Create CSV file with headers if it doesn't exist
        if not csv_file.exists():
            self._create_csv()
    
    def _create_csv(self):
        """Create CSV file with headers."""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
        
        logger.debug(f"Created CSV file: {self.csv_file}")
    
    def write_result(
        self,
        timestamp: datetime,
        test_name: str,
        target: str,
        metric: str,
        value: Any,
        status: str,
        details: str = "",
    ):
        """
        Write a test result to CSV.
        
        Args:
            timestamp: Test timestamp
            test_name: Name of the test
            target: Target host/IP
            metric: Metric name
            value: Metric value
            status: Test status (success/warning/failure)
            details: Additional details
        """
        row = {
            'timestamp': timestamp.isoformat(),
            'test_name': test_name,
            'target': target,
            'metric': metric,
            'value': str(value),
            'status': status,
            'details': details,
        }
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(row)
        
        logger.debug(f"Wrote result to CSV: {metric}={value}")
    
    def read_results(self) -> list:
        """
        Read all results from CSV.
        
        Returns:
            List of result dictionaries
        """
        results = []
        
        if not self.csv_file.exists():
            return results
        
        with open(self.csv_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            results = list(reader)
        
        return results