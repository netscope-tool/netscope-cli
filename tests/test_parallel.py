"""Tests for parallel test execution infrastructure."""
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from netscope.parallel.executor import (
    ParallelTestExecutor,
    ParallelTestConfig,
    BatchTestRunner,
    ContinuousMonitor,
)
from netscope.modules.base import TestResult
from netscope.modules.ports import scan_ports


@pytest.fixture
def mock_test_result():
    """Create a mock test result."""
    return TestResult(
        test_name="test",
        target="127.0.0.1",
        status="success",
        timestamp=datetime.now(),
        duration=1.0,
        metrics={},
        summary="Test passed",
    )


@pytest.fixture
def parallel_config():
    """Create a parallel test configuration."""
    return ParallelTestConfig(max_workers=2, timeout=5)


class TestParallelTestConfig:
    """Test ParallelTestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ParallelTestConfig()
        assert config.max_workers == 10
        assert config.timeout == 30
        assert config.rate_limit is None
        assert config.retry_failed is False
        assert config.retry_count == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ParallelTestConfig(
            max_workers=5, timeout=10, rate_limit=2.0, retry_failed=True, retry_count=5
        )
        assert config.max_workers == 5
        assert config.timeout == 10
        assert config.rate_limit == 2.0
        assert config.retry_failed is True
        assert config.retry_count == 5


class TestParallelTestExecutor:
    """Test ParallelTestExecutor."""

    def test_init_default_config(self):
        """Test executor initialization with default config."""
        executor = ParallelTestExecutor()
        assert executor.config.max_workers == 10
        assert executor.results == []

    def test_init_custom_config(self, parallel_config):
        """Test executor initialization with custom config."""
        executor = ParallelTestExecutor(parallel_config)
        assert executor.config == parallel_config

    def test_execute_parallel_success(self, parallel_config, mock_test_result):
        """Test parallel execution with successful results."""
        executor = ParallelTestExecutor(parallel_config)

        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
                summary=f"Test {target}",
            )

        targets = ["127.0.0.1", "8.8.8.8"]
        results = executor.execute_parallel(test_func, targets)

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        assert results[0].target in targets
        assert results[1].target in targets

    def test_execute_parallel_with_progress_callback(self, parallel_config, mock_test_result):
        """Test parallel execution with progress callback."""
        executor = ParallelTestExecutor(parallel_config)
        progress_calls = []

        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
                summary=f"Test {target}",
            )

        def progress_callback(completed: int, total: int):
            progress_calls.append((completed, total))

        targets = ["127.0.0.1", "8.8.8.8"]
        results = executor.execute_parallel(test_func, targets, progress_callback)

        assert len(results) == 2
        assert len(progress_calls) == 2
        assert progress_calls[-1] == (2, 2)

    def test_execute_parallel_with_exception(self, parallel_config):
        """Test parallel execution handles exceptions."""
        executor = ParallelTestExecutor(parallel_config)

        def test_func(target: str) -> TestResult:
            raise ValueError(f"Error for {target}")

        targets = ["127.0.0.1"]
        results = executor.execute_parallel(test_func, targets)

        assert len(results) == 1
        assert results[0].status == "error"
        assert "Error" in results[0].raw_output or "Error" in str(results[0].error)

    def test_execute_parallel_timeout(self, parallel_config):
        """Test parallel execution handles timeout."""
        executor = ParallelTestExecutor(ParallelTestConfig(max_workers=2, timeout=0.1))

        def test_func(target: str) -> TestResult:
            import time
            time.sleep(1)  # Longer than timeout
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        targets = ["127.0.0.1"]
        results = executor.execute_parallel(test_func, targets)

        assert len(results) == 1
        assert results[0].status == "error"

    def test_get_summary_empty(self):
        """Test summary with no results."""
        executor = ParallelTestExecutor()
        summary = executor.get_summary()
        assert summary["total"] == 0
        assert summary["success"] == 0
        assert summary["success_rate"] == 0.0

    def test_get_summary_with_results(self, parallel_config):
        """Test summary with results."""
        executor = ParallelTestExecutor(parallel_config)

        def test_func(target: str) -> TestResult:
            status = "success" if target == "127.0.0.1" else "error"
            return TestResult(
                test_name="test",
                target=target,
                status=status,
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        targets = ["127.0.0.1", "192.0.2.1"]
        executor.execute_parallel(test_func, targets)
        summary = executor.get_summary()

        assert summary["total"] == 2
        assert summary["success"] == 1
        assert summary["error"] == 1
        assert summary["success_rate"] == 50.0

    def test_execute_parallel_async(self, parallel_config):
        """Test async parallel execution."""
        executor = ParallelTestExecutor(parallel_config)

        async def async_test_func(target: str) -> TestResult:
            await asyncio.sleep(0.05)  # Simulate async work
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=0.05,
                metrics={},
                summary=f"Test {target}",
            )

        targets = ["127.0.0.1", "8.8.8.8"]
        results = executor.execute_parallel_async(async_test_func, targets)

        assert len(results) == 2
        assert all(r.status == "success" for r in results)


class TestBatchTestRunner:
    """Test BatchTestRunner."""

    def test_init_default_config(self):
        """Test batch runner initialization with default config."""
        runner = BatchTestRunner()
        assert runner.config.max_workers == 10

    def test_run_batch_success(self, parallel_config):
        """Test batch execution with successful results."""
        runner = BatchTestRunner(parallel_config)

        def test1_func(target: str) -> TestResult:
            return TestResult(
                test_name="test1",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        def test2_func(target: str) -> TestResult:
            return TestResult(
                test_name="test2",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        tests = [
            {"name": "test1", "func": test1_func, "target": "127.0.0.1"},
            {"name": "test2", "func": test2_func, "target": "8.8.8.8"},
        ]
        results = runner.run_batch(tests)

        assert "test1" in results
        assert "test2" in results
        assert len(results["test1"]) == 1
        assert len(results["test2"]) == 1
        assert results["test1"][0].status == "success"
        assert results["test2"][0].status == "success"

    def test_run_batch_with_progress_callback(self, parallel_config):
        """Test batch execution with progress callback."""
        runner = BatchTestRunner(parallel_config)
        progress_calls = []

        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        def progress_callback(completed: int, total: int):
            progress_calls.append((completed, total))

        tests = [
            {"name": "test1", "func": test_func, "target": "127.0.0.1"},
            {"name": "test2", "func": test_func, "target": "8.8.8.8"},
        ]
        results = runner.run_batch(tests, progress_callback)

        assert len(progress_calls) == 2
        assert progress_calls[-1] == (2, 2)

    def test_run_batch_with_exception(self, parallel_config):
        """Test batch execution handles exceptions."""
        runner = BatchTestRunner(parallel_config)

        def test_func(target: str) -> TestResult:
            raise ValueError("Test error")

        tests = [{"name": "test", "func": test_func, "target": "127.0.0.1"}]
        results = runner.run_batch(tests)

        assert "test" in results
        assert len(results["test"]) == 1
        assert results["test"][0].status == "error"


class TestContinuousMonitor:
    """Test ContinuousMonitor."""

    def test_init(self, parallel_config):
        """Test monitor initialization."""
        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        monitor = ContinuousMonitor(test_func, ["127.0.0.1"], interval=60, config=parallel_config)
        assert monitor.test_func == test_func
        assert monitor.targets == ["127.0.0.1"]
        assert monitor.interval == 60
        assert monitor.running is False
        assert monitor.history == []

    def test_stop(self, parallel_config):
        """Test stopping the monitor."""
        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        monitor = ContinuousMonitor(test_func, ["127.0.0.1"], config=parallel_config)
        monitor.stop()
        assert monitor.running is False

    def test_get_history(self, parallel_config):
        """Test getting monitor history."""
        def test_func(target: str) -> TestResult:
            return TestResult(
                test_name="test",
                target=target,
                status="success",
                timestamp=datetime.now(),
                duration=1.0,
                metrics={},
            )

        monitor = ContinuousMonitor(test_func, ["127.0.0.1"], config=parallel_config)
        history = monitor.get_history()
        assert history == []

        history = monitor.get_history(limit=10)
        assert history == []


class TestParallelPortScan:
    """Test parallel port scanning functionality."""

    def test_scan_ports_parallel(self):
        """Test that scan_ports uses parallel execution."""
        # Test with localhost - should find some ports open (at least SSH/22 might be open)
        # We'll test with a small set of ports
        ports = [22, 80, 443, 8080]
        open_ports, closed_ports = scan_ports("127.0.0.1", ports, timeout=1.0)

        # Results should be sorted
        assert open_ports == sorted(open_ports)
        assert closed_ports == sorted(closed_ports)
        # All ports should be accounted for
        assert len(open_ports) + len(closed_ports) == len(ports)

    def test_scan_ports_progress_callback(self):
        """Test scan_ports progress callback."""
        ports = [22, 80, 443]
        progress_calls = []

        def progress_callback(completed: int, total: int):
            progress_calls.append((completed, total))

        scan_ports("127.0.0.1", ports, timeout=1.0, progress_callback=progress_callback)

        assert len(progress_calls) == len(ports)
        assert progress_calls[-1] == (len(ports), len(ports))

    def test_scan_ports_empty_list(self):
        """Test scan_ports with empty port list."""
        open_ports, closed_ports = scan_ports("127.0.0.1", [], timeout=1.0)
        assert open_ports == []
        assert closed_ports == []

    def test_scan_ports_timeout(self):
        """Test scan_ports respects timeout."""
        # Use an unreachable host with short timeout
        ports = [80]
        open_ports, closed_ports = scan_ports("192.0.2.1", ports, timeout=0.1)

        # Should timeout and mark as closed
        assert len(closed_ports) == 1
        assert 80 in closed_ports
