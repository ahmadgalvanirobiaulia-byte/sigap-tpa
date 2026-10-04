"""Pembacaan CSV hasil Google Earth Engine (Landsat dan MODIS)."""
from __future__ import annotations
import re, glob, os
import numpy as np, pandas as pd
from .config import DATA_DIR, JENDELA_API_HARI


def cari_csv(awalan: str) -> str | None:
    pola = [f for f in glob.glob(str(DATA_DIR / "*.csv"))
            if re.sub(r"\s*\(\d+\)", "", os.path.basename(f)).lower() == f"{awalan}.csv".lower()]
    return sorted(pola, key=os.path.getmtime)[-1] if pola else None


def _di_luar_kejadian(tanggal: pd.Series, kejadian) -> pd.Series:
    ok = pd.Series(True, index=tanggal.index)
    for k in (kejadian or []):
        a = pd.Timestamp(k)
        ok &= ~((tanggal >= a) & (tanggal < a + pd.Timedelta(days=JENDELA_API_HARI)))
    return ok


def muat_landsat(nama: str, kejadian=None) -> pd.DataFrame | None:
    f = cari_csv(f"SIGAP_TPA_{nama}_LST")
    if not f:
        return None
    s = pd.read_csv(f, parse_dates=["date"])
    s = s[(s.ring_mean.between(20, 45)) & (s.ring_sd <= 5)].copy()
    s = s.groupby("date", as_index=False)[["hot_excess_C", "dT_C", "ring_sd", "tutupan_bersih"]].mean()
    base = s[s.date.dt.month.between(6, 10) & _di_luar_kejadian(s.date, kejadian)]
    s["z_hot"] = (s.hot_excess_C - base.hot_excess_C.mean()) / base.hot_excess_C.std()
    s["qc_ketat"] = (s.tutupan_bersih >= 0.9 * s.tutupan_bersih.median()) & (s.ring_sd <= 4)
    return s.sort_values("date").reset_index(drop=True)


def muat_modis(nama: str, kejadian=None) -> pd.DataFrame | None:
    f = cari_csv(f"SIGAP_MODIS_{nama}")
    if not f:
        return None
    m = pd.read_csv(f, parse_dates=["date"])
    m["dN"] = m.night_tpa - m.night_ring
    m = m.dropna(subset=["dN"]).groupby("date", as_index=False)["dN"].mean()
    base = m[m.date.dt.month.between(6, 10) & _di_luar_kejadian(m.date, kejadian)]
    m["z_malam"] = (m.dN - base.dN.mean()) / base.dN.std()
    return m.sort_values("date").reset_index(drop=True)


def muat_zonasi(nama: str) -> pd.DataFrame | None:
    f = cari_csv(f"SIGAP_ZONASI_{nama}_sel")
    return pd.read_csv(f) if f else None
