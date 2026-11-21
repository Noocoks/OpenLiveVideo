from __future__ import annotations

import logging

from .config import configure_logging
from .runtime import configure_runtime_paths


def main() -> None:
    configure_runtime_paths()
    configure_logging()
    logging.getLogger(__name__).info("Iniciando OLV empaquetado.")
    from .gui import launch
    launch()


if __name__ == "__main__":
    main()
