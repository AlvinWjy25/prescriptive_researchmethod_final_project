
import argparse
import csv
import logging
import os
import sys
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path

#Citi-Bike ingestion Requirements:
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs" / "ingestion"
DELETE_CACHE_CONFIG = ROOT_DIR / "config" / "__pycache__"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_GBFS_URL = "https://gbfs.citibikenyc.com/gbfs/gbfs.json"
DEFAULT_LANG = "en"

STATION_INFO_CSV = DATA_DIR / "station_information.csv"
STATION_STATUS_CSV = DATA_DIR / "station_status_log.csv"
LOG_FILE = LOG_DIR / "ingestion.log"

REQUEST_TIMEOUT = 15  # detik
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# Kolom yang kita simpan dari station_status.
# (GBFS versi berbeda-beda punya field tambahan seperti num_ebikes_available;
#  kita ambil yang paling umum + fallback 0 kalau field tidak ada.)

STATUS_FIELDS = [
    "station_id",
    "num_bikes_available",
    "num_bikes_disabled",
    "num_docks_available",
    "num_docks_disabled",
    "num_ebikes_available",
    "is_installed",
    "is_renting",
    "is_returning",
    "last_reported",
]

INFO_FIELDS = [
    "station_id",
    "name",
    "lat",
    "lon",
    "capacity",
    "region_id",
]

# --------------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

def delete_cache(file_to_delete):
    time.sleep(3)

    try:
        logger.info("[!FINALIZING]: Deleting local cache...")
        shutil.rmtree(file_to_delete, ignore_errors=True)
        logger.info("[!FINALIZING]: Cache deleted succesfully!")
        logger.info("[FINALIZED]: Pipeline executed succesfully!")
    except Exception as e:
        logger.info("[!ERROR]: Error deleting cache")
        raise e

if __name__ == "__main__":
    delete_cache(DELETE_CACHE_CONFIG)

    