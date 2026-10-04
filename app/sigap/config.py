"""Konfigurasi SIGAP-TPA: daftar TPA, bobot indeks, dan ambang status."""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PARAMS_FILE = DATA_DIR / "params.json"

# Bobot komponen Indeks Risiko Kebakaran TPA (IRKT)
W_KERING, W_CUACA, W_SAT = 0.40, 0.25, 0.35

AMBANG_KUNING, AMBANG_ORANYE, LANTAI_MERAH = 35, 50, 55
PARUH_LANDSAT, PARUH_MODIS, BOBOT_MODIS = 16, 4, 0.5
JENDELA_API_HARI = 90

AKSI = {
    "HIJAU": "Operasi normal.",
    "KUNING": "Tutup tanah pada zona anomali dan periksa probe suhu.",
    "ORANYE": "Penyiraman terjadwal, larangan sumber api, satgas patroli.",
    "MERAH": "Siagakan Damkar dan BPBD, terbitkan peringatan kesehatan warga.",
}

TPA = {
    "Sarimukti":    dict(lat=-6.7989, lon=107.3512, hujan_tahunan_mm=2300,
                         kejadian=["2023-08-19"], lanskap="perbukitan, hutan",
                         wilayah="Kab. Bandung Barat"),
    "Jatiwaringin": dict(lat=-6.1020, lon=106.5433, hujan_tahunan_mm=1700,
                         kejadian=["2026-06-30"], lanskap="dataran rendah, sawah dan permukiman",
                         wilayah="Kab. Tangerang"),
    "RawaKucing":   dict(lat=-6.1373, lon=106.6183, hujan_tahunan_mm=1700,
                         kejadian=["2023-10-20"], lanskap="perkotaan, dekat bandara",
                         wilayah="Kota Tangerang"),
    "Suwung":       dict(lat=-8.7207, lon=115.2225, hujan_tahunan_mm=1600,
                         kejadian=["2019-10-25", "2023-10-12"], lanskap="pesisir, mangrove",
                         wilayah="Kota Denpasar"),
    "Pakusari":     dict(lat=-8.1697, lon=113.7617, hujan_tahunan_mm=2007,
                         kejadian=["2022-08-18", "2026-07-04"], lanskap="pertanian, TPA kecil",
                         wilayah="Kab. Jember"),
    "Bakung":       dict(lat=-5.4589, lon=105.2400, hujan_tahunan_mm=2200,
                         kejadian=["2023-08-24", "2023-10-13"], lanskap="perkotaan pesisir",
                         wilayah="Kota Bandar Lampung"),
    "Bantargebang": dict(lat=-6.3481, lon=106.9977, hujan_tahunan_mm=2000,
                         kejadian=["2023-10-29"], lanskap="perkotaan padat, TPA terbesar",
                         wilayah="Kota Bekasi"),
    "BontoRamba":   dict(lat=-5.6012, lon=119.6824, hujan_tahunan_mm=1600,
                         kejadian=["2024-09-05"], lanskap="pedesaan",
                         wilayah="Kab. Jeneponto"),
    "Cikundul":     dict(lat=-6.9720, lon=106.9001, hujan_tahunan_mm=3000,
                         kejadian=["2023-10-22"], lanskap="perkotaan",
                         wilayah="Kota Sukabumi"),
    "Cipayung":     dict(lat=-6.4157, lon=106.7849, hujan_tahunan_mm=2800,
                         kejadian=["2026-07-16"], lanskap="perkotaan padat",
                         wilayah="Kota Depok"),
    "Kawatuna":     dict(lat=-0.9095, lon=119.9361, hujan_tahunan_mm=1200,
                         kejadian=["2023-08-19", "2023-12-15"], lanskap="perbukitan tropis",
                         wilayah="Kota Palu"),
    "Kopiluhur":    dict(lat=-6.7797, lon=108.5457, hujan_tahunan_mm=1500,
                         kejadian=["2023-09-09", "2023-09-26"], lanskap="tebing curam, dekat tol",
                         wilayah="Kota Cirebon"),
    "Mandung":      dict(lat=-8.5639, lon=115.0932, hujan_tahunan_mm=2100,
                         kejadian=["2023-09-01"], lanskap="pertanian",
                         wilayah="Kab. Tabanan"),
    "Pesalakan":    dict(lat=-6.9635, lon=109.3883, hujan_tahunan_mm=2000,
                         kejadian=["2023-09-01"], lanskap="pedesaan",
                         wilayah="Kab. Pemalang"),
    "Plosojenar":   dict(lat=-6.7342, lon=111.1781, hujan_tahunan_mm=1700,
                         kejadian=["2024-10-18"], lanskap="pedesaan",
                         wilayah="Kab. Pati"),
    "Tamangapa":    dict(lat=-5.1844, lon=119.4905, hujan_tahunan_mm=2800,
                         kejadian=["2024-08-31"], lanskap="perkotaan",
                         wilayah="Kota Makassar"),
    "Temesi":       dict(lat=-8.5525, lon=115.3428, hujan_tahunan_mm=2300,
                         kejadian=["2023-09-01"], lanskap="pertanian/pesisir",
                         wilayah="Kab. Gianyar"),
}
