"""Perhitungan fitur harian dan Indeks Risiko Kebakaran TPA (IRKT)."""
from __future__ import annotations
import numpy as np, pandas as pd
from .config import (W_KERING, W_CUACA, W_SAT, AMBANG_KUNING, AMBANG_ORANYE,
                     LANTAI_MERAH, PARUH_LANDSAT, PARUH_MODIS, BOBOT_MODIS)

FITUR = ["kbdi_n", "cuaca7"]


def kbdi(df: pd.DataFrame, hujan_tahunan_mm: float, q_awal: float = 0.0) -> np.ndarray:
    """Keetch-Byram Drought Index metrik (0 hingga 203,2 mm)."""
    q, akum, hasil = q_awal, 0.0, []
    for tmax, p in zip(df["tmax"], df["hujan"]):
        if p > 0:
            sebelum = akum; akum += p
            q = max(0.0, q - (max(0.0, akum - 5.1) - max(0.0, sebelum - 5.1)))
        else:
            akum = 0.0
        dq = ((203.2 - q) * (0.968 * np.exp(0.0875 * tmax + 1.5552) - 8.30) * 1e-3
              / (1 + 10.88 * np.exp(-0.001736 * hujan_tahunan_mm)))
        q = min(203.2, q + max(0.0, dq)); hasil.append(q)
    return np.array(hasil)


def fitur_harian(df: pd.DataFrame, hujan_tahunan_mm: float) -> pd.DataFrame:
    d = df.copy()
    d["kbdi"] = kbdi(d, hujan_tahunan_mm)
    d["kbdi_n"] = np.clip(d.kbdi / 150.0, 0, 1)
    s_suhu = np.clip((d.tmax - 28) / 8, 0, 1)
    s_rh = np.clip((70 - d.rhmin) / 35, 0, 1)
    s_angin = np.clip(d.angin / 30, 0, 1)
    d["s_cuaca"] = 0.4 * s_suhu + 0.4 * s_rh + 0.2 * s_angin
    d["cuaca7"] = d.s_cuaca.rolling(7, min_periods=1).mean()
    return d


def _obs_terakhir(tanggal, sat, kolom):
    if sat is None or len(sat) == 0:
        return np.nan, np.nan
    i = sat.date.searchsorted(tanggal, side="right") - 1
    if i < 0:
        return np.nan, np.nan
    return sat[kolom].iloc[i], (tanggal - sat.date.iloc[i]).days


def skor_z(z):
    return np.clip((np.asarray(z, dtype=float) + 1) / 4, 0, 1)


def hitung_irkt(fitur: pd.DataFrame, model=None, landsat=None, modis=None) -> pd.DataFrame:
    d = fitur.copy()
    d["z_prediksi"] = model.prediksi(d) if model is not None else 0.0
    L = [_obs_terakhir(t, landsat, "z_hot") for t in d.tanggal]
    M = [_obs_terakhir(t, modis, "z_malam") for t in d.tanggal]
    zL = np.array([x[0] for x in L], float); uL = np.array([x[1] for x in L], float)
    zM = np.array([x[0] for x in M], float); uM = np.array([x[1] for x in M], float)
    wL = np.where(np.isnan(zL), 0, 0.5 ** (np.nan_to_num(uL) / PARUH_LANDSAT))
    wM = np.where(np.isnan(zM), 0, BOBOT_MODIS * 0.5 ** (np.nan_to_num(uM) / PARUH_MODIS))
    tot = wL + wM
    skala = np.where(tot > 1, 1 / np.maximum(tot, 1e-9), 1.0)
    wL, wM = wL * skala, wM * skala
    d["umur_landsat"], d["umur_modis"] = uL, uM
    d["z_gabungan"] = wL * np.nan_to_num(zL) + wM * np.nan_to_num(zM) + (1 - wL - wM) * d.z_prediksi
    d["s_satelit"] = skor_z(d.z_gabungan)
    d["IRKT"] = 100 * (W_KERING * d.kbdi_n + W_CUACA * d.s_cuaca + W_SAT * d.s_satelit)
    return d


def ambang_merah(riwayat: pd.DataFrame, kejadian, kecuali_tahun=None) -> float:
    th = {pd.Timestamp(k).year for k in (kejadian or [])}
    k = riwayat[riwayat.tanggal.dt.month.between(6, 10) & ~riwayat.tanggal.dt.year.isin(th)]
    if kecuali_tahun is not None:
        k = k[k.tanggal.dt.year != kecuali_tahun]
    return 65.0 if len(k) < 120 else max(LANTAI_MERAH, float(np.percentile(k.IRKT, 90)))


def level(irkt, ambang: float):
    return np.select([np.asarray(irkt) >= ambang, np.asarray(irkt) >= AMBANG_ORANYE,
                      np.asarray(irkt) >= AMBANG_KUNING], ["MERAH", "ORANYE", "KUNING"], "HIJAU")
