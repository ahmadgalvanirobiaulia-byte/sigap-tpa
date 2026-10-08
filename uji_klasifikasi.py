from sigap_iot import klasifikasi_metana

ppm = 23.49

kategori = klasifikasi_metana(ppm)[0]

print("=== KLASIFIKASI METANA ===")
print("Methane :", ppm, "ppm")
print("Kategori:", kategori)