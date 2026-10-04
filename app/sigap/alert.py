"""Penyusunan pesan peringatan siap kirim."""
from __future__ import annotations
import pandas as pd
from .config import AKSI


def pesan(nama: str, wilayah: str, prakiraan: pd.DataFrame, ambang: float, n_baris: int = 7) -> str:
    puncak = prakiraan.loc[prakiraan.IRKT.idxmax()]
    baris = [f"*SIGAP-TPA | {nama} ({wilayah})*",
             f"Ambang tindakan lokal: {ambang:.0f}",
             f"Puncak risiko {puncak.IRKT:.0f}/100 ({puncak.level}) pada {puncak.tanggal:%d-%m-%Y}.",
             f"Tindakan: {AKSI[puncak.level]}", ""]
    for _, r in prakiraan.head(n_baris).iterrows():
        baris.append(f"{r.tanggal:%d/%m} | {r.level:<6} | IRKT {r.IRKT:4.0f} | "
                     f"hujan {r.hujan:4.1f} mm | RH min {r.rhmin:.0f}%")
    return "\n".join(baris)
