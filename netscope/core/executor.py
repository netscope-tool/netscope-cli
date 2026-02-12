"""
Command execution engine.
"""

import subprocess
import time
from typing import Optional, List
from pydantic import BaseModel
from loguru import logger

from netscope.core.detector import SystemInfo


class CommandResult(BaseModel):
    """Result of a command execution."""
    
    command: str
    return_code: int
    stdout: str
    stderr: str
    duration: float
    success: bool
    
    class Config:
        arbitrary_types_allowed = True


class TestExecutor:
    """Execute system commands and tests."""
    
    def __init__(self, system_info: SystemInfo, app_logger: logger):
        self.system_info = system_info
        self.logger = app_logger
    
    def run_command(
        self,
        command: List[str],
        timeout: int = 30,
        capture_output: bool = True,
    ) -> CommandResult:
        """
        Execute a system command.
        
        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            CommandResult object
        """
        start_time = time.time()
        cmd_str = " ".join(command)
        
        self.logger.info(f"Executing command: {cmd_str}")
        
        try:
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
            )
            
            duration = time.time() - start_time
            
            command_result = CommandResult(
                command=cmd_str,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                success=(result.returncode == 0),
            )
            
            self.logger.info(
                f"Command completed: {cmd_str} "
                f"(return code: {result.returncode}, duration: {duration:.2f}s)"
            )
            
            return command_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.logger.error(f"Command timed out after {timeout}s: {cmd_str}")
            
            return CommandResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration=duration,
                success=False,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Command failed: {cmd_str} - {e}")
            
            return CommandResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
            )