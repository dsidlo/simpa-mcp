"""Logging configuration for SIMPA MCP service.

File-based logging that does NOT interfere with MCP stdio communication.
All logs go to file only - never to stdout/stderr when running in MCP mode.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Literal

import structlog
from structlog.types import EventDict, WrappedLogger

# Add custom TRACE level (below DEBUG)
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


def trace(self, message, *args, **kwargs):
    """Log at TRACE level (more verbose than DEBUG)."""
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)


# Monkey-patch Logger to add trace method
logging.Logger.trace = trace

LogLevel = Literal[
    "trace", "debug", "info", "warn", "warning", "error", "fatal", "critical"
]

LOG_LEVEL_MAP: dict[str, int] = {
    "trace": TRACE_LEVEL,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "critical": logging.CRITICAL,
}

# Custom level name mapping that includes TRACE
NAME_TO_LEVEL = {
    "trace": TRACE_LEVEL,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "critical": logging.CRITICAL,
}


def filter_by_level(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Custom level filter that supports TRACE level.
    
    This is a drop-in replacement for structlog.stdlib.filter_by_level
    that includes support for the custom TRACE log level.
    """
    # Get the effective level from the underlying logger
    effective_level = logger.getEffectiveLevel()
    
    # Get the level for the current method
    method_level = NAME_TO_LEVEL.get(method_name, logging.DEBUG)
    
    # Drop event if method level is below effective level
    if method_level < effective_level:
        raise structlog.DropEvent
    
    return event_dict


# Define a custom BoundLogger class that supports trace
class BoundLoggerWithTrace(structlog.stdlib.BoundLogger):
    """BoundLogger with TRACE level support."""
    
    def trace(self, event: str, **kw) -> None:
        """Log at TRACE level."""
        self._proxy_to_logger("trace", event, **kw)


def setup_logging(
    level: LogLevel = "info",
    log_file: str = "/tmp/simpa-mcp.log",
    console_output: bool = False,
) -> None:
    """Configure logging for SIMPA.
    
    Args:
        level: Log level (debug, info, warn, error, fatal)
        log_file: Path to log file
        console_output: If True, also log to console (for non-MCP modes)
    """
    # CRITICAL: Set environment variables BEFORE any imports that use them
    os.environ["LITELLM_LOG"] = "ERROR"  # Silence LiteLLM to prevent stdout pollution
    
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    log_level = LOG_LEVEL_MAP.get(level.lower(), logging.INFO)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    handlers: list[logging.Handler] = []
    
    # File handler - always add this
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(log_level)
    handlers.append(file_handler)
    
    # Console handler - only if explicitly requested (not for MCP stdio mode)
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        handlers.append(console_handler)
    
    # Configure structlog
    shared_processors = [
        filter_by_level,  # Use our custom filter that supports TRACE
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    structlog.configure(
        processors=shared_processors + [structlog.dev.ConsoleRenderer()],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=BoundLoggerWithTrace,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=log_level,
        handlers=handlers,
        force=True,
    )
    
    # CRITICAL: Silence noisy loggers that pollute stdout/stderr
    # These MUST be suppressed for MCP stdio mode to work
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    logging.getLogger("litellm").setLevel(logging.ERROR)
    logging.getLogger("litellm_logging").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Suppress MCP/FastMCP internal logging
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("mcp.server").setLevel(logging.WARNING)
    logging.getLogger("fastmcp").setLevel(logging.WARNING)
    
    # Get logger and log setup
    logger = structlog.get_logger()
    logger.info(
        "logging_configured",
        level=level,
        log_file=str(log_path),
        console_output=console_output,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_trace(logger, event: str, **kwargs) -> None:
    """Safely log at TRACE level if available, otherwise DEBUG.
    
    This handles the case where structlog is not fully configured yet
    (lazy proxy returns BoundLoggerFilteringAtNotset).
    """
    try:
        # Check if trace method exists and is callable
        if hasattr(logger, 'trace') and callable(getattr(logger, 'trace', None)):
            logger.trace(event, **kwargs)
        else:
            logger.debug(event, **kwargs)
    except (AttributeError, TypeError):
        # Fall back to debug if trace fails
        try:
            logger.debug(event, **kwargs)
        except Exception:
            # If even debug fails, silently ignore
            pass
