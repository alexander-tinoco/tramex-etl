import json
import logging
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Custom log formatter that converts the standard output into JSON.
    Makes it easier to aggregate and analyze logs in external tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Basic structure of the JSON log
        log_record: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception traceback if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Dynamic mapping of extra attributes passed to the log call (e.g. on HTTP requests)
        extra_keys = ["client", "method", "path", "status_code", "duration"]
        for key in extra_keys:
            if hasattr(record, key):
                log_record[key] = getattr(record, key)

        return json.dumps(log_record)


def setup_logging() -> None:
    """Configures the root logger to use the structured JSON formatter."""
    root_logger = logging.getLogger()

    # Remove previous handlers to avoid duplicate output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set up the standard console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())

    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # Also reformat uvicorn's default logs for consistency
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True
