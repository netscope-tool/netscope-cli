"""
Logging configuration using loguru.
"""

from pathlib import Path
from loguru import logger
import sys


def setup_logging(output_dir: Path, verbose: bool = False) -> logger:
    """
    Setup application logging.
    
    Args:
        output_dir: Directory for log files
        verbose: Enable verbose logging
        
    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()
    
    # Console handler
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    
    # File handler - main log
    log_file = output_dir / "netscope.log"
    logger.add(
        log_file,
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    
    # File handler - errors only
    error_log = output_dir / "netscope_errors.log"
    logger.add(
        error_log,
        rotation="10 MB",
        retention="90 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    
    logger.info("Logging initialized")
    logger.debug(f"Log files: {log_file}, {error_log}")
    
    return logger