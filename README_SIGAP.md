# SIGAP-TPA

Sistem Informasi Geospasial Antisipasi Api TPA: prakiraan tingkat bahaya kebakaran
Tempat Pemrosesan Akhir sampah hingga 15 hari ke depan, berbasis fusi citra termal
satelit, indeks kekeringan timbunan, dan prakiraan cuaca.

## Struktur

```
sigap/config.py      daftar TPA, bobot indeks, ambang status
sigap/weather.py     Open-Meteo (historis dan prakiraan) dengan cache berkas
sigap/satellite.py   pembacaan CSV Landsat, MODIS, dan zonasi hasil Earth Engine
sigap/index.py       KBDI, fitur harian, perhitungan IRKT, ambang dan level
sigap/model.py       model kondisi timbunan, kalibrasi Nelder-Mead, simpan/muat parameter
sigap/alert.py       pesan peringatan siap kirim
app.py               dasbor Streamlit
data/                CSV hasil Earth Engine dan params.json
```

## Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Aplikasi tidak memerlukan kredensial Earth Engine. Data satelit disiapkan lebih dulu
melalui script Earth Engine, lalu CSV-nya diletakkan di folder `data/` dengan nama:

```
SIGAP_TPA_<nama>_LST.csv
SIGAP_MODIS_<nama>.csv
SIGAP_ZONASI_<nama>_sel.csv     (opsional, untuk peta zonasi)
```

Data cuaca diambil langsung dari Open-Meteo saat aplikasi dijalankan dan disimpan
sementara di `data/cache/`.

## Kalibrasi ulang

```python
from sigap import weather, satellite, index as idx
from sigap.model import ModelTimbunan, pasangkan
from sigap.config import TPA

data = []
for nama, info in TPA.items():
    ls = satellite.muat_landsat(nama, info["kejadian"])
    if ls is None:
        continue
    cuaca = weather.historis(info["lat"], info["lon"], "2019-01-01", "2026-09-01", kunci=nama)
    fitur = idx.fitur_harian(cuaca, info["hujan_tahunan_mm"])
    data.append(pasangkan(fitur, ls, info["kejadian"]))

ModelTimbunan().latih(data).simpan()
```

## Catatan

Sistem ini merupakan prototipe penelitian. Keluarannya berupa tingkat bahaya, bukan
prediksi kepastian terjadinya kebakaran, dan belum dapat menggantikan pemantauan lapangan.
