import sys
from pathlib import Path

# Tambahkan folder app ke Python path
APP_DIR = Path(__file__).resolve().parent / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from sigap.sensor import ambil_sensor_terbaru


print("=== HASIL UJI MODUL SENSOR ===")

data = ambil_sensor_terbaru()

if data is None:
    print("Data sensor tidak tersedia.")
else:
    print("MQ-4 ADC      :", data["mq4_adc"])
    print("Tegangan pin  :", round(data["tegangan_pin"], 3), "V")
    print("Tegangan AO   :", round(data["tegangan_ao"], 3), "V")
    print("Methane       :", round(data["methane_ppm"], 2), "ppm")
    print("Kategori      :", data["kategori_metana"])
    print("Suhu          :", data["suhu"], "°C")
    print("RH            :", data["rh"], "%")
    print("Warmup        :", data["warmup"])
    print("Timestamp     :", data["timestamp"])