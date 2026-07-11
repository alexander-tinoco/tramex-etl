import json
import logging
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Formateador de logs personalizado que convierte la salida estándar a formato JSON.
    Facilita la agregación y el análisis de logs en herramientas externas.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Estructura básica del log JSON
        log_record: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Incluir traza de excepciones si existen
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Mapeo dinámico de atributos adicionales pasados al log (ej. en peticiones HTTP)
        extra_keys = ["client", "method", "path", "status_code", "duration"]
        for key in extra_keys:
            if hasattr(record, key):
                log_record[key] = getattr(record, key)

        return json.dumps(log_record)


def setup_logging() -> None:
    """Configura el logger raíz para utilizar el formateador estructurado JSON."""
    root_logger = logging.getLogger()
    
    # Remover handlers previos para evitar duplicidad de salidas
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configurar handler de consola estándar
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # También re-formateamos los logs por defecto de uvicorn para coherencia
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True
