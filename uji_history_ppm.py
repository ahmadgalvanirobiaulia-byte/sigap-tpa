import sys
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

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

if not data:
    print("Data history tidak tersedia.")
    raise SystemExit

print("Jumlah data history:", len(data))
print()

for i, (key, item) in enumerate(data.items()):

    adc = item.get("mq4_adc")

    if adc is None:
        continue

    adc = float(adc)

    ts = item.get("ts")

    if isinstance(ts, (int, float)):
        waktu = datetime.fromtimestamp(ts / 1000, WIB)
    else:
        waktu = "-"

    v_pin, v_ao, ppm = hitung_ppm(adc)
    kategori = klasifikasi_metana(ppm)

    print(
        f"{i+1}. "
        f"waktu={waktu} | "
        f"ADC={adc:.0f} | "
        f"AO={v_ao:.3f} V | "
        f"metana={ppm:.2f} ppm | "
        f"kategori={kategori} | "
        f"warmup={item.get('warmup')}"
    )

    if i >= 19:
        break