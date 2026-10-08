from sigap_iot import kalibrasi_mq4

# Hasil baseline yang kita dapatkan
R0 = 5.33

# Contoh ADC median baseline
ADC = 927

# ADC ESP32 → tegangan pada GPIO 34
v_pin = ADC / 4095 * 3.3

# Voltage divider 10k/10k:
# tegangan AO MQ-4 = 2 × tegangan yang masuk ke ESP32
v_ao = v_pin * 2

# Konversi tegangan AO menjadi perkiraan ppm metana
ppm = float(
    kalibrasi_mq4(
        v_ao,
        R0,
        vcc=5.0,
        rl_kohm=10.0
    )[0]
)

print("=== TES KALIBRASI MQ-4 ===")
print("ADC              :", ADC)
print("Tegangan pin     :", round(v_pin, 3), "V")
print("Tegangan AO      :", round(v_ao, 3), "V")
print("R0               :", R0, "kOhm")
print("Methane          :", round(ppm, 2), "ppm")