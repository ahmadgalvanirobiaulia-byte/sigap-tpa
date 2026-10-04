"""Isi kolom IZR yang kosong pada CSV zonasi dari GeoTIFF zonasi hasil Earth Engine.

Script zonasi versi lama mengekspor IZR kosong karena reduceToVectors tidak mereduksi
band label. GeoTIFF-nya tetap benar, jadi IZR tiap sel 90 m dihitung ulang sebagai
rata-rata piksel 30 m yang pusatnya berada di dalam kotak 90 m di sekitar sentroid sel.

Pemakaian:
    python tools/isi_izr_dari_raster.py ~/Documents/"data TPA"
Hasil ditulis ke app/data/; berkas sumber tidak diubah. Sel yang letaknya lebih dari
2 km dari koordinat TPA di config dianggap salah poligon dan TPA itu dilewati.
"""
import math, sys
from pathlib import Path
import numpy as np, pandas as pd, tifffile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sigap.config import DATA_DIR, TPA

SETENGAH_SEL_M = 45
BATAS_JARAK_KM = 2


def baca_raster(f: Path):
    with tifffile.TiffFile(f) as t:
        p = t.pages[0]
        izr = p.asarray()[..., 0].astype(float)
        sx, sy = p.tags["ModelPixelScaleTag"].value[:2]
        x0, y0 = p.tags["ModelTiepointTag"].value[3:5]
    baris, kolom = np.indices(izr.shape)
    return x0 + (kolom + 0.5) * sx, y0 - (baris + 0.5) * sy, izr


def isi(sumber: Path) -> None:
    for nama, info in TPA.items():
        f_sel = sumber / f"SIGAP_ZONASI_{nama}_sel.csv"
        f_ras = sumber / f"SIGAP_ZONASI_{nama}_raster.tif"
        if not (f_sel.exists() and f_ras.exists()):
            print(f"{nama}: berkas zonasi tidak lengkap, dilewati")
            continue
        z = pd.read_csv(f_sel)
        jarak = np.hypot((z.lintang - info["lat"]) * 111,
                         (z.bujur - info["lon"]) * 111 * math.cos(math.radians(info["lat"])))
        if jarak.max() > BATAS_JARAK_KM:
            print(f"{nama}: sel berjarak {jarak.min():.0f} km dari TPA, poligon salah tempat, dilewati")
            continue
        bujur, lintang, izr = baca_raster(f_ras)
        d_lat = SETENGAH_SEL_M / 111_320
        d_lon = d_lat / math.cos(math.radians(info["lat"]))
        nilai = []
        for lo, la in zip(z.bujur, z.lintang):
            m = (abs(bujur - lo) <= d_lon) & (abs(lintang - la) <= d_lat) & np.isfinite(izr)
            nilai.append(izr[m].mean() if m.any() else np.nan)
        z["IZR"] = nilai
        z.to_csv(DATA_DIR / f_sel.name, index=False)
        print(f"{nama}: {z.IZR.notna().sum()}/{len(z)} sel terisi, IZR {z.IZR.min():.1f}-{z.IZR.max():.1f}")


if __name__ == "__main__":
    isi(Path(sys.argv[1]).expanduser())
