"""Do we really need to pause?"""

import logging

from osmnx.downloader import _get_pause
from osmnx import settings

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


settings.log_console = True
print("Pause:", _get_pause())
