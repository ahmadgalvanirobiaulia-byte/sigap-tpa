import math
import statistics as st
from datetime import datetime, timezone, timedelta

import requests


URL = (
    "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app"
    "/sigap/Sarimukti/history.json"
)

R0 = 5.33
RL_KOHM = 10.0
VCC = 5.0

MQ4_M = -0.38
MQ4_B = 1.133

WIB = timezone(timedelta(hours=7))


def hitung_ppm(adc):
    v_pin = adc / 4095.0 * 3.3
    v_ao = v_pin * 2.0

    v_ao = max(0.01, min(v_ao, VCC - 0.01))

    rs = RL_KOHM * (VCC - v_ao) / v_ao
    rasio = rs / R0

    ppm = 10 ** (
        (math.log10(max(rasio, 1e-3)) - MQ4_B) / MQ4_M
    )

    return ppm


def klasifikasi(ppm):
    if ppm < 1000:
        return "rendah"
    elif ppm < 5000:
        return "sedang"
    elif ppm < 15000:
        return "tinggi"
    else:
        return "sangat tinggi"


# =========================
# Ambil data Firebase
# =========================

response = requests.get(URL, timeout=30)
response.raise_for_status()

data = response.json()

if not data:
    print("Data Firebase tidak tersedia.")
    raise SystemExit


# =========================
# Filter data valid
# =========================

data_valid = []

for item in data.values():

    adc = item.get("mq4_adc")
    warmup = item.get("warmup")
    ts = item.get("ts")

    if adc is None:
        continue

    if warmup is not False:
        continue

    if float(adc) <= 0:
        continue

    if not isinstance(ts, (int, float)):
        continue

    waktu = datetime.fromtimestamp(ts / 1000, WIB)

    ppm = hitung_ppm(float(adc))

    data_valid.append({
        "waktu": waktu,
        "ppm": ppm
    })


# =========================
# Kelompokkan berdasarkan jam
# =========================

kelompok_jam = {}

for item in data_valid:

    waktu = item["waktu"]

    jam = waktu.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    if jam not in kelompok_jam:
        kelompok_jam[jam] = []

    kelompok_jam[jam].append(item["ppm"])


# =========================
# Tampilkan ringkasan
# =========================

print("Total data Firebase :", len(data))
print("Data valid           :", len(data_valid))
print("Jumlah jam terisi    :", len(kelompok_jam))
print()

print(
    f"{'Jam':<18}"
    f"{'N':>5}"
    f"{'Min':>12}"
    f"{'Median':>12}"
    f"{'Maks':>12}"
    f"{'Kategori':>15}"
)

print("-" * 74)


for jam in sorted(kelompok_jam):

    ppm_data = kelompok_jam[jam]

    minimum = min(ppm_data)
    median = st.median(ppm_data)
    maksimum = max(ppm_data)

    kategori = klasifikasi(median)

    print(
        f"{jam.strftime('%d-%m %H:00'):<18}"
        f"{len(ppm_data):>5}"
        f"{minimum:>12.2f}"
        f"{median:>12.2f}"
        f"{maksimum:>12.2f}"
        f"{kategori:>15}"
    )