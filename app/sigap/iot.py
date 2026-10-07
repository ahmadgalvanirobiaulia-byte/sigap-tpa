"""Modul sensor IoT prototipe SIGAP-TPA.

Memproses data dari sensor MQ-4 (metana) dan DHT22 (suhu, kelembapan)
yang dikirim oleh ESP32 ke Firebase Realtime Database.

Kalibrasi MQ-4
--------------
Sensor MQ-4 mengukur konduktansi gas.  Rasio Rs/R0 dikonversi menjadi
estimasi konsentrasi metana (ppm) berdasarkan kurva khas datasheet:

    ppm = 1012.7 * (Rs / R0) ** (-2.786)

R0 adalah resistansi sensor di udara bersih (referensi ~1 000 ppm CH4).
Sebelum kalibrasi dengan gas referensi, gunakan nilai R0 sementara dan
perlakukan hasil ppm sebagai indikasi tren, bukan angka presisi.

Ambang klasifikasi metana
-------------------------
Rendah        :     < 1 000 ppm
Sedang        : 1 000 - < 5 000 ppm
Tinggi        : 5 000 - < 15 000 ppm
Sangat tinggi : >= 15 000 ppm
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------- konstanta
AMBANG_METANA = [1_000, 5_000, 15_000]
LABEL_METANA = ["rendah", "sedang", "tinggi", "sangat tinggi"]

# Mapping field Firebase -> kolom standar internal.
# Struktur Firebase aktual:
#   { "mq4_adc": int, "rh": float, "suhu": float, "ts": int(epoch_ms), "warmup": bool }
_FIREBASE_MAP = {
    "ts": "timestamp",
    "suhu": "suhu_C",
    "rh": "kelembapan_persen",
    "mq4_adc": "mq4_v_adc",
}


# ----------------------------------------------------------------- kalibrasi
def _rs_kohm(v_adc: np.ndarray, vcc: float = 3.3, rl_kohm: float = 10.0) -> np.ndarray:
    """Hitung resistansi sensor (Rs) dalam kohm dari tegangan ADC."""
    v = np.clip(np.asarray(v_adc, dtype=float), 1e-6, vcc - 1e-6)
    return rl_kohm * (vcc - v) / v


def _ppm(rs: np.ndarray, r0_kohm: float) -> np.ndarray:
    """Konversi Rs/R0 ke estimasi ppm CH4 menggunakan kurva datasheet MQ-4."""
    rasio = np.clip(rs / r0_kohm, 1e-6, None)
    return 1012.7 * np.power(rasio, -2.786)


# ----------------------------------------------------------------- klasifikasi
def klasifikasi_metana(ppm: pd.Series) -> pd.Series:
    """Klasifikasikan konsentrasi metana ke empat tingkat."""
    return pd.cut(
        ppm,
        bins=[-np.inf] + AMBANG_METANA + [np.inf],
        labels=LABEL_METANA,
        right=False,
    ).astype(str)


# ----------------------------------------------------------------- loader CSV
def muat_log(
    path_csv: str,
    r0_kohm: float,
    vcc: float = 3.3,
    rl_kohm: float = 10.0,
) -> pd.DataFrame:
    """Muat log sensor dari CSV lokal.

    CSV diharapkan memiliki kolom minimal:
        timestamp, suhu_C, kelembapan_persen, mq4_v_adc

    Mengembalikan DataFrame dengan kolom tambahan:
        metana_ppm, metana_kelas
    """
    df = pd.read_csv(path_csv)

    # Normalisasi nama kolom (jika Firebase dump punya nama berbeda)
    rename = {}
    for src, dst in _FIREBASE_MAP.items():
        if src in df.columns and dst not in df.columns:
            rename[src] = dst
    if rename:
        df = df.rename(columns=rename)

    return proses_log_dataframe(df, r0_kohm, vcc, rl_kohm)


def proses_log_dataframe(
    df: pd.DataFrame,
    r0_kohm: float,
    vcc: float = 3.3,
    rl_kohm: float = 10.0,
) -> pd.DataFrame:
    """Proses DataFrame mentah sensor menjadi DataFrame siap analisis.

    Langkah:
    1. Validasi kolom minimal.
    2. Konversi timestamp.
    3. Konversi numerik.
    4. Hapus baris tidak valid.
    5. Hitung Rs, ppm, dan kelas metana.
    6. Urutkan berdasarkan timestamp.
    """
    kolom_wajib = {"timestamp", "suhu_C", "kelembapan_persen", "mq4_v_adc"}
    tersedia = set(df.columns)
    kurang = kolom_wajib - tersedia
    if kurang:
        logger.warning("Kolom tidak lengkap: %s", kurang)
        return pd.DataFrame()

    df = df.copy()

    # Timestamp: coba epoch milisecond dulu, lalu parsing string
    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        # Epoch ms -> datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Jakarta").dt.tz_localize(None)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Numerik
    for col in ["suhu_C", "kelembapan_persen", "mq4_v_adc"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Filter warmup jika kolom ada
    if "warmup" in df.columns:
        df = df[df["warmup"] != True]  # noqa: E712

    # Hapus baris tidak valid
    df = df.dropna(subset=["timestamp", "suhu_C", "kelembapan_persen", "mq4_v_adc"])

    if df.empty:
        return df

    # Jika mq4_v_adc berisi nilai ADC mentah (integer besar, misalnya 0-4095),
    # konversi ke tegangan dulu. ESP32 ADC 12-bit, range 0-4095 => 0-3.3V.
    if df["mq4_v_adc"].max() > vcc * 1.5:
        df["mq4_v_adc"] = df["mq4_v_adc"] / 4095.0 * vcc

    # Hitung MQ-4
    rs = _rs_kohm(df["mq4_v_adc"].values, vcc, rl_kohm)
    df["metana_ppm"] = _ppm(rs, r0_kohm)
    df["metana_kelas"] = klasifikasi_metana(df["metana_ppm"])

    # Urutkan
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ----------------------------------------------------------------- loader Firebase
def muat_data_firebase(
    database_url: str,
    path: str = "sigap/Sarimukti/history",
    limit: Optional[int] = None,
    timeout: float = 10.0,
) -> pd.DataFrame:
    """Ambil data sensor dari Firebase Realtime Database (REST API).

    Mengembalikan DataFrame mentah dengan kolom standar:
        timestamp, suhu_C, kelembapan_persen, mq4_v_adc

    Tidak menyebabkan aplikasi berhenti jika Firebase gagal;
    mengembalikan DataFrame kosong pada error.
    """
    import requests

    url = f"{database_url.rstrip('/')}/{path}.json"
    params = {}
    if limit is not None:
        # Firebase REST limitToLast memerlukan orderBy
        params["orderBy"] = '"$key"'
        params["limitToLast"] = str(limit)

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Firebase tidak dapat diakses: %s", e)
        return pd.DataFrame()

    if not data or not isinstance(data, dict):
        return pd.DataFrame()

    # data berupa { push_key: { field: value, ... }, ... }
    records = []
    for key, val in data.items():
        if isinstance(val, dict):
            records.append(val)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Mapping nama field Firebase -> kolom standar
    rename = {}
    for src, dst in _FIREBASE_MAP.items():
        if src in df.columns and dst not in df.columns:
            rename[src] = dst
    if rename:
        df = df.rename(columns=rename)

    # Pastikan kolom minimal ada
    kolom_wajib = {"timestamp", "suhu_C", "kelembapan_persen", "mq4_v_adc"}
    if not kolom_wajib.issubset(set(df.columns)):
        kurang = kolom_wajib - set(df.columns)
        logger.warning("Kolom Firebase tidak lengkap: %s", kurang)
        return pd.DataFrame()

    # Konversi timestamp (epoch ms)
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Jakarta").dt.tz_localize(None)

    # Konversi numerik
    for col in ["suhu_C", "kelembapan_persen", "mq4_v_adc"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Filter warmup
    if "warmup" in df.columns:
        df = df[df["warmup"] != True]  # noqa: E712

    # Hapus baris tidak valid
    df = df.dropna(subset=["timestamp", "suhu_C", "kelembapan_persen", "mq4_v_adc"])

    # Urutkan
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ----------------------------------------------------------------- ringkasan harian
def ringkas_harian(log: pd.DataFrame) -> pd.DataFrame:
    """Ringkasan statistik harian dari log sensor.

    Input: DataFrame hasil muat_log() atau proses_log_dataframe().
    Output: DataFrame dengan satu baris per hari.
    """
    if log.empty:
        return pd.DataFrame()

    log = log.copy()
    log["tanggal"] = log["timestamp"].dt.normalize()

    agg = log.groupby("tanggal").agg(
        suhu_rata=("suhu_C", "mean"),
        suhu_maks=("suhu_C", "max"),
        kelembapan_rata=("kelembapan_persen", "mean"),
        metana_rata_ppm=("metana_ppm", "mean"),
        metana_maks_ppm=("metana_ppm", "max"),
        n_bacaan=("suhu_C", "count"),
    ).reset_index()

    agg["metana_kelas"] = klasifikasi_metana(agg["metana_rata_ppm"])
    return agg


# ----------------------------------------------------------------- perbandingan model
def bandingkan_dengan_model(
    harian_sensor: pd.DataFrame,
    d_irkt: pd.DataFrame,
) -> pd.DataFrame:
    """Gabungkan ringkasan sensor harian dengan hasil model IRKT.

    Mengembalikan DataFrame berisi tanggal-tanggal yang memiliki
    data sensor dan data model sekaligus.
    """
    if harian_sensor.empty or d_irkt.empty:
        return pd.DataFrame()

    sensor = harian_sensor[["tanggal", "suhu_rata", "suhu_maks",
                             "kelembapan_rata", "metana_rata_ppm",
                             "metana_kelas"]].copy()

    model = d_irkt[["tanggal", "IRKT", "z_prediksi", "kbdi_n",
                      "s_cuaca", "s_satelit"]].copy()
    model = model.rename(columns={"IRKT": "irkt"})
    if "level" in d_irkt.columns:
        model["level"] = d_irkt["level"].values

    gabung = sensor.merge(model, on="tanggal", how="inner")
    return gabung.sort_values("tanggal").reset_index(drop=True)
