"""
ingestion.py
============
Data ingestion script untuk topik final project:
"Simulation & Decision under Uncertainty" (Prescriptive Data Science)
+ Research Methodology paper.

Tujuan:
    Melakukan polling berkala ke Citi Bike GBFS API (public, no API key)
    untuk membangun time series jumlah bike/dock tersedia per stasiun.
    Data ini dipakai sebagai proxy untuk "inventory level under demand
    uncertainty" -- analog dengan sistem inventory riil (stok = bikes,
    kapasitas = docks).

Sumber data (GBFS - General Bikeshare Feed Specification, standar terbuka):
    - station_information : data statis (nama, lokasi, kapasitas)
    - station_status      : data dinamis (jumlah bike/dock tersedia, timestamp)

Cara pakai:
    # Sekali jalan (satu snapshot):
    python ingestion.py --once

    # Polling terus-menerus setiap N menit (default 15 menit):
    python ingestion.py --interval 15

    # Ganti kota/sistem GBFS lain (lihat daftar di systems.csv MobilityData):
    python ingestion.py --gbfs-url https://gbfs.citibikenyc.com/gbfs/gbfs.json

Output:
    - data/station_information.csv  (snapshot sekali, di-refresh berkala)
    - data/station_status_log.csv   (time series, di-APPEND tiap polling)
    - ingestion.log                 (log aktivitas & error)
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from config.config_script import (DEFAULT_GBFS_URL, DEFAULT_LANG, DATA_DIR, STATION_INFO_CSV, STATION_STATUS_CSV, LOG_FILE,
                                  REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_SECONDS, STATUS_FIELDS, INFO_FIELDS, 
                                  logger, delete_cache)

# --------------------------------------------------------------------------
# HTTP helper dengan retry
# --------------------------------------------------------------------------
 
def fetch_json(url: str) -> dict:
    """Fetch URL dan return JSON, dengan retry sederhana untuk menangani
    kegagalan jaringan sementara (penting untuk polling jangka panjang)."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            last_error = e
            logger.warning(
                "Gagal fetch %s (percobaan %d/%d): %s", url, attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS)
    raise RuntimeError(f"Gagal fetch {url} setelah {MAX_RETRIES} percobaan") from last_error
 
 
def discover_feed_urls(gbfs_url: str, lang: str = DEFAULT_LANG) -> dict:
    """Ambil auto-discovery file GBFS utama dan kembalikan dict
    {feed_name: feed_url}, contoh: {"station_status": "https://..."}"""
    root = fetch_json(gbfs_url)
 
    data = root.get("data", {})
    # Beberapa sistem GBFS tidak pakai key bahasa (langsung "feeds" di root data)
    if lang in data:
        feeds = data[lang].get("feeds", [])
    elif "feeds" in data:
        feeds = data.get("feeds", [])
    else:
        # fallback: ambil bahasa pertama yang tersedia
        first_lang = next(iter(data), None)
        if first_lang is None:
            raise RuntimeError("Struktur GBFS tidak dikenali: tidak ada 'feeds'")
        feeds = data[first_lang].get("feeds", [])
 
    return {feed["name"]: feed["url"] for feed in feeds}
 
 
# --------------------------------------------------------------------------
# CSV helpers
# --------------------------------------------------------------------------
 
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
 
 
def write_station_information(stations: list[dict]):
    """Overwrite station_information.csv -- ini snapshot data statis,
    tidak perlu di-append karena isinya jarang berubah (bisa berubah
    kalau ada stasiun baru/ditutup)."""
    ensure_data_dir()
    with open(STATION_INFO_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INFO_FIELDS)
        writer.writeheader()
        for s in stations:
            row = {field: s.get(field, "") for field in INFO_FIELDS}
            writer.writerow(row)
    logger.info("station_information.csv ditulis: %d stasiun", len(stations))
 
 
def load_last_reported_cache() -> dict:
    """Baca station_status_log.csv yang sudah ada dan bangun cache
    {station_id: last_reported_terakhir} untuk keperluan dedup.
 
    Dipanggil sekali di awal tiap siklus ingestion (bukan disimpan
    lintas-proses), supaya tetap benar walau ada proses lain yang
    ikut menulis ke file yang sama (misal rekan satu kelompok
    menjalankan ingestion secara paralel) -- cache selalu dibaca
    ulang dari kondisi file terbaru, bukan dari state in-memory lama.
    """
    cache = {}
    if not os.path.isfile(STATION_STATUS_CSV):
        return cache
 
    with open(STATION_STATUS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_id = row.get("station_id")
            last_reported = row.get("last_reported")
            if station_id is None or last_reported is None:
                continue
            # Simpan last_reported terbesar (paling baru) per stasiun.
            # File di-append kronologis, jadi baris belakangan pun
            # dijamin >= baris sebelumnya untuk stasiun yang sama --
            # tapi kita pakai max() untuk aman terhadap urutan tak terduga.
            prev = cache.get(station_id)
            if prev is None or str(last_reported) > str(prev):
                cache[station_id] = last_reported
    return cache
 
 
def append_station_status(stations: list[dict], polled_at: str):
    """Append satu snapshot status ke log CSV (time series), dengan dedup:
    baris untuk sebuah station_id di-skip kalau last_reported-nya sama
    dengan yang terakhir tersimpan (artinya API belum meng-update data
    stasiun itu sejak polling sebelumnya -- umum terjadi kalau interval
    polling lebih rapat daripada TTL feed, atau kalau ada proses lain
    yang polling ke sumber sama di waktu berdekatan).
 
    File di-buat dengan header kalau belum ada.
    """
    ensure_data_dir()
    file_exists = os.path.isfile(STATION_STATUS_CSV)
 
    last_reported_cache = load_last_reported_cache()
 
    fieldnames = ["polled_at"] + STATUS_FIELDS
    rows_written = 0
    rows_skipped = 0
 
    with open(STATION_STATUS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for s in stations:
            station_id = s.get("station_id")
            last_reported = s.get("last_reported", 0)
 
            prev_last_reported = last_reported_cache.get(station_id)
            if prev_last_reported is not None and str(last_reported) == str(prev_last_reported):
                rows_skipped += 1
                continue
 
            row = {"polled_at": polled_at}
            for field in STATUS_FIELDS:
                row[field] = s.get(field, 0)
            writer.writerow(row)
            rows_written += 1
 
            # Update cache in-memory supaya konsisten dalam satu batch ini
            last_reported_cache[station_id] = last_reported
 
    logger.info(
        "Snapshot status pada %s: %d baris ditulis, %d di-skip (duplikat/belum update)",
        polled_at, rows_written, rows_skipped,
    )
 
 
# --------------------------------------------------------------------------
# Core ingestion logic
# --------------------------------------------------------------------------
 
def run_once(gbfs_url: str, lang: str, refresh_station_info: bool = False):
    """Jalankan satu siklus ingestion: fetch status (+ info kalau diminta)."""
    logger.info("Mulai siklus ingestion...")
 
    feeds = discover_feed_urls(gbfs_url, lang)
 
    if "station_status" not in feeds:
        raise RuntimeError("Feed 'station_status' tidak ditemukan di GBFS ini")
 
    status_data = fetch_json(feeds["station_status"])
    stations_status = status_data.get("data", {}).get("stations", [])
 
    polled_at = datetime.now(timezone.utc).isoformat()
    append_station_status(stations_status, polled_at)
 
    # station_information jarang berubah -> hanya refresh kalau diminta
    # atau kalau file belum ada sama sekali.
    if refresh_station_info or not os.path.isfile(STATION_INFO_CSV):
        if "station_information" in feeds:
            info_data = fetch_json(feeds["station_information"])
            stations_info = info_data.get("data", {}).get("stations", [])
            write_station_information(stations_info)
        else:
            logger.warning("Feed 'station_information' tidak tersedia di sistem ini")
 
    logger.info("Siklus ingestion selesai.")
 
 
def run_loop(gbfs_url: str, lang: str, interval_minutes: int):
    """Polling terus-menerus setiap interval_minutes menit.
    station_information di-refresh sekali per 24 jam saja (datanya statis)."""
    last_info_refresh = 0.0
    info_refresh_interval_sec = 24 * 60 * 60  # 24 jam
 
    logger.info(
        "Memulai polling loop: interval=%d menit, sumber=%s", interval_minutes, gbfs_url
    )
 
    while True:
        now = time.time()
        should_refresh_info = (now - last_info_refresh) >= info_refresh_interval_sec
 
        try:
            run_once(gbfs_url, lang, refresh_station_info=should_refresh_info)
            if should_refresh_info:
                last_info_refresh = now
        except Exception as e:
            # Jangan biarkan satu kegagalan menghentikan seluruh proses
            # polling jangka panjang -- log lalu lanjut ke siklus berikutnya.
            logger.error("Siklus ingestion gagal: %s", e)
 
        logger.info("Menunggu %d menit sebelum polling berikutnya...", interval_minutes)
        time.sleep(interval_minutes * 60)
 
 
# --------------------------------------------------------------------------
# CLI entrypoint
# --------------------------------------------------------------------------
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingestion GBFS bike-share data untuk simulasi decision-under-uncertainty."
    )
    parser.add_argument(
        "--gbfs-url",
        default=DEFAULT_GBFS_URL,
        help=f"URL auto-discovery GBFS (default: {DEFAULT_GBFS_URL}). "
        "Ganti untuk sistem bike-share kota lain (lihat MobilityData systems.csv).",
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LANG,
        help="Kode bahasa feed GBFS (default: en)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Jalankan satu kali snapshot lalu keluar (cocok untuk dijadwalkan via cron).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Interval polling dalam menit jika dijalankan sebagai loop (default: 15).",
    )
    return parser.parse_args()
 
 
def main():
    args = parse_args()
 
    if args.once:
        run_once(args.gbfs_url, args.lang, refresh_station_info=True)
    else:
        try:
            run_loop(args.gbfs_url, args.lang, args.interval)
        except KeyboardInterrupt:
            logger.info("Polling dihentikan oleh user (Ctrl+C).")
 
 
if __name__ == "__main__":
    main()

    DELETE_CACHE_INGESTION = Path(ROOT_DIR / "ingestion" / "__pycache__")
    delete_cache(DELETE_CACHE_INGESTION)