"""Pengambilan data cuaca Open-Meteo, dengan cache berkas agar hemat kuota."""
from __future__ import annotations
import json, time
from pathlib import Path
import pandas as pd, requests
from .config import DATA_DIR

DAILY = "temperature_2m_max,relative_humidity_2m_min,wind_speed_10m_max,precipitation_sum"
CACHE = DATA_DIR / "cache"
KOLOM = {"time": "tanggal", "temperature_2m_max": "tmax", "relative_humidity_2m_min": "rhmin",
         "wind_speed_10m_max": "angin", "precipitation_sum": "hujan"}


def _ke_df(js: dict) -> pd.DataFrame:
    d = pd.DataFrame(js["daily"]).rename(columns=KOLOM)
    d["tanggal"] = pd.to_datetime(d["tanggal"])
    return d.fillna({"hujan": 0}).ffill().bfill()


def _ambil(url: str, cache_key: str | None = None, umur_jam: float = 6) -> dict:
    if cache_key:
        CACHE.mkdir(parents=True, exist_ok=True)
        f = CACHE / f"{cache_key}.json"
        if f.exists() and (time.time() - f.stat().st_mtime) < umur_jam * 3600:
            return json.loads(f.read_text())
    try:
        res = requests.get(url, timeout=30)
        js = res.json()
        if js.get("error"):
            raise RuntimeError(f"Open-Meteo API error: {js.get('reason')}")
        if cache_key:
            (CACHE / f"{cache_key}.json").write_text(json.dumps(js))
        return js
    except Exception as e:
        if cache_key:
            f = CACHE / f"{cache_key}.json"
            if f.exists():
                try:
                    cached = json.loads(f.read_text())
                    if not cached.get("error") and "daily" in cached:
                        return cached
                except Exception:
                    pass
            # Cari cache berkas sejenis untuk TPA yang sama
            bagian = cache_key.split("_")
            if len(bagian) >= 2:
                prefix = f"{bagian[0]}_{bagian[1]}"
                alternatif = sorted(CACHE.glob(f"{prefix}*.json"), key=lambda p: p.stat().st_mtime)
                for alt in reversed(alternatif):
                    try:
                        cached = json.loads(alt.read_text())
                        if not cached.get("error") and "daily" in cached:
                            return cached
                    except Exception:
                        pass
        raise e


def historis(lat: float, lon: float, mulai: str, selesai: str, kunci: str = "") -> pd.DataFrame:
    url = ("https://archive-api.open-meteo.com/v1/archive"
           f"?latitude={lat}&longitude={lon}&daily={DAILY}"
           f"&start_date={mulai}&end_date={selesai}&timezone=Asia%2FJakarta")
    return _ke_df(_ambil(url, f"hist_{kunci}_{mulai}_{selesai}", umur_jam=24 * 7))


def prakiraan(lat: float, lon: float, hari_lalu: int = 92, hari_depan: int = 15,
              kunci: str = "") -> pd.DataFrame:
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}&daily={DAILY}"
           f"&past_days={hari_lalu}&forecast_days={hari_depan}&timezone=Asia%2FJakarta")
    return _ke_df(_ambil(url, f"fc_{kunci}", umur_jam=6))


def sambung(hist: pd.DataFrame, fc: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([hist[hist.tanggal < fc.tanggal.min()], fc], ignore_index=True)
