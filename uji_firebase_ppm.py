import requests
from sigap_iot import kalibrasi_mq4

URL = "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app/sigap/Sarimukti/latest.json"

# R0 sementara hasil kalibrasi
R0 = 5.33

# Ambil data terbaru Firebase
r = requests.get(URL, timeout=30)
r.raise_for_status()

data = r.json()

# Ambil ADC MQ-4
adc = data.get("mq4_adc")

if adc is None:
    raise ValueError("mq4_adc tidak ditemukan di Firebase.")

# ADC ESP32 -> tegangan pin ESP32
v_pin = adc / 4095 * 3.3

# Karena ada voltage divider 10k/10k:
# tegangan AO sensor = 2 x tegangan yang dibaca ESP32
v_ao = v_pin * 2

# Hitung methane ppm menggunakan R0
ppm = float(
    kalibrasi_mq4(
        v_ao,
        R0,
        vcc=5.0,
        rl_kohm=10.0
    )[0]
)

print("=== HASIL KONVERSI DATA FIREBASE ===")
print("MQ-4 ADC      :", adc)
print("Tegangan pin  :", round(v_pin, 3), "V")
print("Tegangan AO   :", round(v_ao, 3), "V")
print("R0            :", R0, "kOhm")
print("Methane       :", round(ppm, 2), "ppm")
print("Suhu          :", data.get("suhu"), "°C")
print("RH            :", data.get("rh"), "%")