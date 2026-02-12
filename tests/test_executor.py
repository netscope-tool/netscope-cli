"""Tests for the command executor (with mocked subprocess)."""
from unittest.mock import MagicMock, patch

import pytest

from netscope.core.detector import SystemInfo
from netscope.core.executor import CommandResult, TestExecutor as Executor


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def system_info():
    return SystemInfo(
        os_type="Darwin",
        platform="macOS-14.0",
        python_version="3.11.0",
        hostname="testhost",
    )


@pytest.fixture
def executor(system_info, mock_logger):
    return Executor(system_info, mock_logger)


def test_run_command_success(executor):
    """run_command returns CommandResult with success=True when process returns 0."""
    with patch("netscope.core.executor.subprocess.run") as m_run:
        m_run.return_value = MagicMock(
            returncode=0,
            stdout="ping output",
            stderr="",
        )
        result = executor.run_command(["ping", "-c", "1", "127.0.0.1"])
    assert isinstance(result, CommandResult)
    assert result.success is True
    assert result.return_code == 0
    assert "ping" in result.command
    assert result.stdout == "ping output"


def test_run_command_failure(executor):
    """run_command returns success=False when process returns non-zero."""
    with patch("netscope.core.executor.subprocess.run") as m_run:
        m_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="connect: Network is unreachable",
        )
        result = executor.run_command(["ping", "-c", "1", "192.0.2.1"])
    assert result.success is False
    assert result.return_code == 1
    assert "Network is unreachable" in result.stderr
