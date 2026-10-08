import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import math
import requests

APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from sigap.sensor import klasifikasi_metana

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

    return v_pin, v_ao, ppm


response = requests.get(URL, timeout=30)
response.raise_for_status()

data = response.json()

valid = []

for key, item in data.items():

    adc = item.get("mq4_adc")
    warmup = item.get("warmup")

    if adc is None:
        continue

    if warmup is not False:
        continue

    if float(adc) <= 0:
        continue

    adc = float(adc)

    ts = item.get("ts")

    if isinstance(ts, (int, float)):
        waktu = datetime.fromtimestamp(ts / 1000, WIB)
    else:
        waktu = None

    v_pin, v_ao, ppm = hitung_ppm(adc)
    kategori = klasifikasi_metana(ppm)

    valid.append({
        "waktu": waktu,
        "adc": adc,
        "v_ao": v_ao,
        "ppm": ppm,
        "kategori": kategori,
        "suhu": item.get("suhu"),
        "rh": item.get("rh"),
    })


print("Total data Firebase :", len(data))
print("Data valid           :", len(valid))
print()

if not valid:
    print("Tidak ada data valid.")
    raise SystemExit

print("20 data valid pertama:")
print()

for i, item in enumerate(valid[:20], start=1):
    print(
        f"{i}. "
        f"waktu={item['waktu']} | "
        f"ADC={item['adc']:.0f} | "
        f"AO={item['v_ao']:.3f} V | "
        f"metana={item['ppm']:.2f} ppm | "
        f"kategori={item['kategori']} | "
        f"suhu={item['suhu']} °C | "
        f"RH={item['rh']} %"
    )