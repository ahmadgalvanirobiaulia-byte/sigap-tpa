import requests
from datetime import datetime, timezone, timedelta

URL = (
    "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app"
    "/sigap/Sarimukti/history.json"
)

WIB = timezone(timedelta(hours=7))

response = requests.get(URL, timeout=30)
response.raise_for_status()

data = response.json()

if not data:
    print("Data history tidak tersedia.")
    raise SystemExit

print("Jumlah data history:", len(data))
print()

for i, (key, item) in enumerate(data.items()):
    ts = item.get("ts")

    if isinstance(ts, (int, float)):
        waktu = datetime.fromtimestamp(ts / 1000, WIB)
    else:
        waktu = "-"

    print(
        f"{i+1}. "
        f"waktu={waktu} | "
        f"ADC={item.get('mq4_adc')} | "
        f"suhu={item.get('suhu')} °C | "
        f"RH={item.get('rh')} % | "
        f"warmup={item.get('warmup')}"
    )

    if i >= 19:
        break