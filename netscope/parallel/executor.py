"""
Parallel test execution infrastructure.
Supports concurrent testing of multiple targets with resource management.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from netscope.modules.base import TestResult


@dataclass
class ParallelTestConfig:
    """Configuration for parallel test execution."""
    max_workers: int = 10
    timeout: int = 30
    rate_limit: Optional[float] = None  # Requests per second
    retry_failed: bool = False
    retry_count: int = 3


class ParallelTestExecutor:
    """
    Execute tests in parallel across multiple targets.
    """
    
    def __init__(self, config: Optional[ParallelTestConfig] = None):
        """
        Initialize parallel executor.
        
        Args:
            config: Parallel execution configuration
        """
        self.config = config or ParallelTestConfig()
        self.results: List[TestResult] = []
    
    def execute_parallel(
        self,
        test_func: Callable,
        targets: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TestResult]:
        """
        Execute test function in parallel across multiple targets.
        
        Args:
            test_func: Test function to execute (takes target as argument)
            targets: List of targets to test
            progress_callback: Optional callback for progress updates (completed, total)
            
        Returns:
            List of TestResult objects
        """
        results = []
        total = len(targets)
        completed = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_target = {
                executor.submit(self._execute_with_timeout, test_func, target): target
                for target in targets
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Create error result
                    error_result = TestResult(
                        test_name="parallel_test",
                        target=target,
                        status="error",
                        timestamp=datetime.now(),
                        duration=0.0,
                        summary=f"Test failed: {str(e)}",
                        error=str(e),
                        metrics={},
                        raw_output=str(e),
                    )
                    results.append(error_result)
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
        
        self.results = results
        return results
    
    def execute_parallel_async(
        self,
        async_test_func: Callable,
        targets: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TestResult]:
        """
        Execute async test function in parallel across multiple targets.
        
        Args:
            async_test_func: Async test function to execute
            targets: List of targets to test
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of TestResult objects
        """
        return asyncio.run(
            self._execute_async_batch(async_test_func, targets, progress_callback)
        )
    
    async def _execute_async_batch(
        self,
        async_test_func: Callable,
        targets: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TestResult]:
        """Execute async tests in batch."""
        results = []
        total = len(targets)
        completed = 0
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.config.max_workers)
        
        async def execute_with_semaphore(target: str) -> TestResult:
            async with semaphore:
                # Rate limiting
                if self.config.rate_limit:
                    await asyncio.sleep(1.0 / self.config.rate_limit)
                
                try:
                    result = await asyncio.wait_for(
                        async_test_func(target),
                        timeout=self.config.timeout,
                    )
                    return result
                except asyncio.TimeoutError:
                    return TestResult(
                        test_name="parallel_test",
                        target=target,
                        status="error",
                        timestamp=datetime.now(),
                        duration=0.0,
                        summary="Test timed out",
                        error="Timeout",
                        metrics={},
                        raw_output="Timeout",
                    )
                except Exception as e:
                    return TestResult(
                        test_name="parallel_test",
                        target=target,
                        status="error",
                        timestamp=datetime.now(),
                        duration=0.0,
                        summary=f"Test failed: {str(e)}",
                        error=str(e),
                        metrics={},
                        raw_output=str(e),
                    )
        
        # Execute all tasks
        tasks = [execute_with_semaphore(target) for target in targets]
        
        # Gather results with progress tracking
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
        
        self.results = results
        return results
    
    def _execute_with_timeout(
        self,
        test_func: Callable,
        target: str,
    ) -> TestResult:
        """Execute test with timeout."""
        try:
            # Use concurrent.futures for timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(test_func, target)
                result = future.result(timeout=self.config.timeout)
                return result
        except concurrent.futures.TimeoutError:
            return TestResult(
                test_name="parallel_test",
                target=target,
                status="error",
                timestamp=datetime.now(),
                duration=0.0,
                summary="Test timed out",
                error="Timeout",
                metrics={},
                raw_output="Timeout",
            )
        except Exception as e:
            return TestResult(
                test_name="parallel_test",
                target=target,
                status="error",
                timestamp=datetime.now(),
                duration=0.0,
                summary=f"Test failed: {str(e)}",
                error=str(e),
                metrics={},
                raw_output=str(e),
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of parallel test results.
        
        Returns:
            Dictionary with summary statistics
        """
        if not self.results:
            return {
                "total": 0,
                "success": 0,
                "warning": 0,
                "error": 0,
                "success_rate": 0.0,
            }
        
        total = len(self.results)
        success = sum(1 for r in self.results if r.status == "success")
        warning = sum(1 for r in self.results if r.status == "warning")
        error = sum(1 for r in self.results if r.status == "error")
        
        return {
            "total": total,
            "success": success,
            "warning": warning,
            "error": error,
            "success_rate": (success / total) * 100 if total > 0 else 0.0,
        }


class BatchTestRunner:
    """
    Run multiple different tests in parallel.
    """
    
    def __init__(self, config: Optional[ParallelTestConfig] = None):
        """
        Initialize batch test runner.
        
        Args:
            config: Parallel execution configuration
        """
        self.config = config or ParallelTestConfig()
        self.executor = ParallelTestExecutor(config)
    
    def run_batch(
        self,
        tests: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, List[TestResult]]:
        """
        Run batch of different tests.
        
        Args:
            tests: List of test dictionaries with 'name', 'func', and 'target'
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping test names to results
        """
        results = {}
        total = len(tests)
        completed = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_test = {
                executor.submit(test['func'], test['target']): test['name']
                for test in tests
            }
            
            for future in concurrent.futures.as_completed(future_to_test):
                test_name = future_to_test[future]
                try:
                    result = future.result(timeout=self.config.timeout)
                    if test_name not in results:
                        results[test_name] = []
                    results[test_name].append(result)
                except Exception as e:
                    if test_name not in results:
                        results[test_name] = []
                    results[test_name].append(TestResult(
                        test_name=test_name,
                        target="unknown",
                        status="error",
                        timestamp=datetime.now(),
                        duration=0.0,
                        summary=f"Test failed: {str(e)}",
                        error=str(e),
                        metrics={},
                        raw_output=str(e),
                    ))
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
        
        return results


class ContinuousMonitor:
    """
    Continuous network monitoring with periodic testing.
    """
    
    def __init__(
        self,
        test_func: Callable,
        targets: List[str],
        interval: int = 60,
        config: Optional[ParallelTestConfig] = None,
    ):
        """
        Initialize continuous monitor.
        
        Args:
            test_func: Test function to execute
            targets: List of targets to monitor
            interval: Test interval in seconds
            config: Parallel execution configuration
        """
        self.test_func = test_func
        self.targets = targets
        self.interval = interval
        self.executor = ParallelTestExecutor(config)
        self.running = False
        self.history: List[Dict[str, Any]] = []
    
    async def start(
        self,
        duration: Optional[int] = None,
        callback: Optional[Callable[[List[TestResult]], None]] = None,
    ) -> None:
        """
        Start continuous monitoring.
        
        Args:
            duration: Optional duration in seconds (None for indefinite)
            callback: Optional callback for each test cycle
        """
        self.running = True
        start_time = datetime.now()
        
        while self.running:
            # Run tests
            results = self.executor.execute_parallel(self.test_func, self.targets)
            
            # Store in history
            self.history.append({
                "timestamp": datetime.now(),
                "results": results,
                "summary": self.executor.get_summary(),
            })
            
            # Call callback if provided
            if callback:
                callback(results)
            
            # Check duration
            if duration:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration:
                    break
            
            # Wait for next interval
            await asyncio.sleep(self.interval)
    
    def stop(self) -> None:
        """Stop continuous monitoring."""
        self.running = False
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get monitoring history.
        
        Args:
            limit: Optional limit on number of entries
            
        Returns:
            List of history entries
        """
        if limit:
            return self.history[-limit:]
        return self.history
