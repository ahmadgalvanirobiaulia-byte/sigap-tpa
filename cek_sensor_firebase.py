import requests

URL = "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app/sigap/Sarimukti/latest.json"

r = requests.get(URL, timeout=30)
r.raise_for_status()

data = r.json()

print("=== DATA TERBARU FIREBASE ===")
print("MQ-4 ADC :", data.get("mq4_adc"))
print("Suhu     :", data.get("suhu"))
print("RH       :", data.get("rh"))
print("Warmup   :", data.get("warmup"))
print("Timestamp:", data.get("ts"))