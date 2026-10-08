import requests
import statistics as st
from datetime import datetime, timedelta, timezone

from sigap_iot import kalibrasi_r0, kalibrasi_mq4


URL = "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app/sigap/Sarimukti/history.json"

WIB = timezone(timedelta(hours=7))

MULAI = datetime(2026, 10, 8, 2, 0, tzinfo=WIB)
SELESAI = datetime(2026, 10, 8, 4, 0, tzinfo=WIB)


r = requests.get(
    URL + '?orderBy="$key"&limitToLast=1000',
    timeout=30
).json()


adc = []

for v in r.values():
    if "mq4_adc" in v and "ts" in v:
        t = datetime.fromtimestamp(v["ts"] / 1000, WIB)

        if MULAI <= t < SELESAI:
            adc.append(v["mq4_adc"])


med = st.median(adc)

sebaran = 100 * (max(adc) - min(adc)) / med


# ADC pin ESP32 → tegangan pin
v_pin = med / 4095 * 3.3

# Karena rangkaian voltage divider 10k/10k,
# tegangan AO sensor = 2 × tegangan pin
v_ao = v_pin * 2


# Hitung R0 sementara
r0 = kalibrasi_r0(
    v_ao,
    vcc=5.0,
    rl_kohm=10.0
)


# Hitung output ppm pada kondisi baseline
ppm0 = float(
    kalibrasi_mq4(
        v_ao,
        r0,
        vcc=5.0,
        rl_kohm=10.0
    )[0]
)


print("Jumlah data       :", len(adc))
print("ADC median        :", med)
print("Sebaran           :", round(sebaran, 1), "% (target di bawah 5%)")
print("Tegangan di pin   :", round(v_pin, 3), "V")
print("Tegangan AO       :", round(v_ao, 3), "V")
print("R0 sementara      :", round(r0, 2), "kOhm")
print("ppm pada baseline:", round(ppm0, 1),
      "(titik nol sensor, bukan kadar metana asli)")