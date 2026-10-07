"""
SIGAP-TPA | Modul Sensor IoT (prototipe)
Membaca, mengkalibrasi, dan menggabungkan data sensor MQ-4 (metana) dan
DHT22 (suhu, kelembapan) dengan hasil model SIGAP-TPA.

PERINGATAN KALIBRASI:
MQ-4 adalah sensor hobi (bukan instrumen bersertifikat keselamatan gas).
Konstanta kurva di bawah adalah nilai umum dari datasheet produsen untuk
estimasi ppm metana, BELUM dikalibrasi dengan gas referensi. Perlakukan
hasil ppm sebagai TREN RELATIF (naik/turun), bukan angka presisi, dan
JANGAN dijadikan satu-satunya dasar keputusan keselamatan (evakuasi,
larangan sumber api). Gunakan prosedur keselamatan TPA yang berlaku.
"""
from __future__ import annotations
import pandas as pd, numpy as np

# ---------------------------------------------------------------- MQ-4
# Konstanta kurva log-log Rs/R0 vs ppm metana (CH4) dari datasheet MQ-4.
# Nilai umum dipakai komunitas; disarankan diverifikasi ulang dengan
# gas referensi sebelum dipakai untuk klaim kuantitatif di naskah.
_MQ4_M, _MQ4_B = -0.38, 1.133     # ppm = 10 ** ((log10(Rs/R0) - B) / M)
_MQ4_RASIO_UDARA_BERSIH = 4.4     # Rs/R0 khas pada udara bersih (datasheet)


def kalibrasi_r0(v_adc_udara_bersih: float, vcc: float = 3.3, rl_kohm: float = 10.0) -> float:
    """Jalankan sekali saat sensor masih baru dan sudah dipanaskan (burn-in
    24-48 jam), DI UDARA TERBUKA BERSIH (bukan di dekat TPA). Kembalikan nilai
    R0 (kOhm) untuk disimpan dan dipakai pada kalibrasi_mq4()."""
    rs = rl_kohm * (vcc - v_adc_udara_bersih) / max(v_adc_udara_bersih, 1e-6)
    return rs / _MQ4_RASIO_UDARA_BERSIH


def kalibrasi_mq4(v_adc: pd.Series | float, r0_kohm: float,
                   vcc: float = 3.3, rl_kohm: float = 10.0) -> pd.Series:
    """Konversi tegangan ADC mentah MQ-4 menjadi perkiraan ppm metana."""
    v_adc = np.clip(np.asarray(v_adc, dtype=float), 0.01, vcc - 0.01)
    rs = rl_kohm * (vcc - v_adc) / v_adc
    rasio = rs / r0_kohm
    ppm = 10 ** ((np.log10(np.clip(rasio, 1e-3, None)) - _MQ4_B) / _MQ4_M)
    return pd.Series(ppm)


def klasifikasi_metana(ppm: pd.Series | float) -> pd.Series:
    """Klasifikasi TREN kasar untuk dasbor, bukan ambang keselamatan resmi.
    Batas bawah ledakan (LEL) metana di udara adalah 5% volume atau 50.000 ppm."""
    ppm = np.asarray(ppm, dtype=float)
    return pd.Series(np.select(
        [ppm < 1000, ppm < 5000, ppm < 15000],
        ["rendah", "sedang", "tinggi"], default="SANGAT TINGGI - cek prosedur keselamatan"))


# ---------------------------------------------------------------- Log sensor
KOLOM_LOG = ["timestamp", "suhu_C", "kelembapan_persen", "mq4_v_adc"]


def muat_log(path_csv: str, r0_kohm: float, vcc: float = 3.3, rl_kohm: float = 10.0) -> pd.DataFrame:
    """Baca CSV hasil logging ESP32 (lihat firmware SIGAP_ESP32_MQ4_DHT22.ino)."""
    d = pd.read_csv(path_csv)
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d["metana_ppm"] = kalibrasi_mq4(d["mq4_v_adc"], r0_kohm, vcc, rl_kohm)
    d["metana_kelas"] = klasifikasi_metana(d["metana_ppm"])
    return d.sort_values("timestamp").reset_index(drop=True)


def ringkas_harian(log: pd.DataFrame) -> pd.DataFrame:
    """Agregasi log mentah (bisa per menit) menjadi satu baris per hari,
    untuk dibandingkan dengan keluaran harian model SIGAP-TPA."""
    h = log.set_index("timestamp").resample("D").agg(
        suhu_rata=("suhu_C", "mean"), suhu_maks=("suhu_C", "max"),
        kelembapan_rata=("kelembapan_persen", "mean"),
        metana_rata_ppm=("metana_ppm", "mean"), metana_maks_ppm=("metana_ppm", "max"),
        n_bacaan=("suhu_C", "count")).reset_index().rename(columns={"timestamp": "tanggal"})
    return h


def bandingkan_dengan_model(harian_sensor: pd.DataFrame, d_irkt: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan ringkasan sensor dengan keluaran hitung_irkt() pada tanggal
    yang sama, untuk melihat apakah suhu lokal sensor sejalan dengan
    anomali yang diprediksi model (z_prediksi, z_gabungan) dan status IRKT.
    Ini adalah VALIDASI GROUND TRUTH, bukan input balik ke model, karena
    sensor baru terpasang di satu lokasi dan periode pendek."""
    kiri = harian_sensor.copy(); kiri["tanggal"] = pd.to_datetime(kiri["tanggal"]).dt.normalize()
    kanan = d_irkt[["tanggal", "IRKT", "level", "z_prediksi", "z_gabungan"]].copy()
    kanan["tanggal"] = pd.to_datetime(kanan["tanggal"]).dt.normalize()
    return kiri.merge(kanan, on="tanggal", how="left")
