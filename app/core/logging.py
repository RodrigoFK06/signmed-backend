"""Configuracion de logging para toda la aplicacion."""
from __future__ import annotations

import logging
import sys

from app.core.settings import settings

_CONFIGURED = False


def setup_logging() -> None:
    """Configura el logger raiz una unica vez."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Uvicorn ya emite sus propios accesos; evitamos duplicarlos.
    logging.getLogger("uvicorn.access").propagate = False

    _CONFIGURED = True
