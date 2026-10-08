import requests
import numpy as np


# =========================================================
# KONFIGURASI FIREBASE
# =========================================================

FIREBASE_URL = (
    "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app"
    "/sigap/Sarimukti/latest.json"
)


# =========================================================
# PARAMETER KALIBRASI MQ-4
# =========================================================

# R0 sementara hasil kalibrasi
R0 = 5.33

# Load resistance
RL_KOHM = 10.0

# Tegangan sistem sensor MQ-4
VCC = 5.0

# Karakteristik kurva MQ-4
MQ4_M = -0.38
MQ4_B = 1.133


# =========================================================
# KLASIFIKASI METANA
# =========================================================

def klasifikasi_metana(ppm):
    """
    Mengelompokkan konsentrasi metana berdasarkan nilai ppm.
    """

    if ppm < 1000:
        return "rendah"

    elif ppm < 5000:
        return "sedang"

    elif ppm < 15000:
        return "tinggi"

    else:
        return "SANGAT TINGGI - cek prosedur keselamatan"


# =========================================================
# MENGAMBIL DATA SENSOR TERBARU
# =========================================================

def ambil_sensor_terbaru():
    """
    Mengambil data sensor terbaru dari Firebase,
    kemudian mengubah ADC MQ-4 menjadi methane_ppm.
    """

    # -----------------------------------------------------
    # 1. Ambil data Firebase
    # -----------------------------------------------------

    response = requests.get(
        FIREBASE_URL,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return None


    # -----------------------------------------------------
    # 2. Ambil nilai ADC MQ-4
    # -----------------------------------------------------

    adc = data.get("mq4_adc")

    if adc is None:
        return None


    adc = float(adc)


    # -----------------------------------------------------
    # 3. ADC ESP32 -> tegangan pin ESP32
    # -----------------------------------------------------

    v_pin = adc / 4095.0 * 3.3


    # -----------------------------------------------------
    # 4. Koreksi voltage divider 10k / 10k
    #
    # Tegangan AO sensor = 2 x tegangan pin ESP32
    # -----------------------------------------------------

    v_ao = v_pin * 2.0


    # -----------------------------------------------------
    # 5. Hitung Rs MQ-4
    # -----------------------------------------------------

    v_ao_aman = np.clip(
        v_ao,
        0.01,
        VCC - 0.01
    )

    rs = RL_KOHM * (
        VCC - v_ao_aman
    ) / v_ao_aman


    # -----------------------------------------------------
    # 6. Hitung rasio Rs/R0
    # -----------------------------------------------------

    rasio = rs / R0


    # -----------------------------------------------------
    # 7. Konversi Rs/R0 -> methane ppm
    # -----------------------------------------------------

    methane_ppm = 10 ** (
        (
            np.log10(
                max(rasio, 1e-3)
            ) - MQ4_B
        ) / MQ4_M
    )


    # -----------------------------------------------------
    # 8. Klasifikasi metana
    # -----------------------------------------------------

    kategori = klasifikasi_metana(
        methane_ppm
    )


    # -----------------------------------------------------
    # 9. Kembalikan seluruh data
    # -----------------------------------------------------

    return {
        "mq4_adc": adc,

        "tegangan_pin": v_pin,

        "tegangan_ao": v_ao,

        "methane_ppm": float(methane_ppm),

        "kategori_metana": kategori,

        "suhu": data.get("suhu"),

        "rh": data.get("rh"),

        "warmup": data.get("warmup"),

        "timestamp": data.get("ts"),
    }