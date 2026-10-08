"""SIGAP-TPA: dasbor prakiraan bahaya kebakaran TPA (Streamlit)."""
import datetime as dt
import pandas as pd, streamlit as st
from sigap.config import TPA, AKSI
from sigap import weather, satellite, index as idx, sensor
from sigap.model import ModelTimbunan
from sigap.alert import pesan
import ui_components as ui

st.set_page_config(page_title="SIGAP-TPA", page_icon="🔥", layout="wide")


class CuacaGagal(Exception):
    """Open-Meteo tidak dapat diakses atau mengembalikan data kosong."""


@st.cache_data(ttl=3600, show_spinner="Mengambil data cuaca dan citra satelit...")
def siapkan(nama: str):
    info = TPA[nama]
    batas = (pd.Timestamp.today() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        hist = weather.historis(info["lat"], info["lon"], "2019-01-01", batas, kunci=nama)
        fc = weather.prakiraan(info["lat"], info["lon"], kunci=nama)
        cuaca = weather.sambung(hist, fc)
    except Exception as e:
        raise CuacaGagal(str(e)) from e
    fitur = idx.fitur_harian(cuaca, info["hujan_tahunan_mm"])
    landsat = satellite.muat_landsat(nama, info["kejadian"])
    modis = satellite.muat_modis(nama, info["kejadian"])
    model = ModelTimbunan.muat()
    d = idx.hitung_irkt(fitur, model, landsat, modis)
    ambang = idx.ambang_merah(d, info["kejadian"])
    d["level"] = idx.level(d.IRKT.values, ambang)
    return d, ambang, landsat, modis, dt.datetime.now()


@st.cache_data(ttl=3600, show_spinner=False)
def zonasi(nama: str):
    zon = satellite.muat_zonasi(nama)
    return None if zon is None or zon.IZR.notna().sum() == 0 else ui.siapkan_zonasi(zon)


ui.pasang_gaya()
hari_ini = pd.Timestamp.today().normalize()

with st.sidebar:
    st.markdown("### Pengaturan")
    nama = st.selectbox("Pilih TPA", list(TPA))
    data_sensor = sensor.ambil_sensor_terbaru()
    hari_riwayat = st.slider("Panjang riwayat pada grafik (hari)", 30, 365, 90, 30)
    info = TPA[nama]
    st.divider()
    st.markdown(f"**TPA {nama}**  \nWilayah: {info['wilayah']}  \nLanskap: {info['lanskap']}  \n"
                f"Koordinat: {info['lat']:.4f}, {info['lon']:.4f}")

ui.header(hari_ini)
st.markdown("### Pemantauan Sensor Lapangan")

if data_sensor is None:
    st.warning("Data sensor belum tersedia.")
else:
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Metana",
            f"{data_sensor['methane_ppm']:.2f} ppm"
        )

    with c2:
        st.metric(
            "Kategori",
            data_sensor["kategori_metana"]
        )

    with c3:
        st.metric(
            "Suhu",
            f"{data_sensor['suhu']:.1f} °C"
        )

    with c4:
        st.metric(
            "Kelembapan",
            f"{data_sensor['rh']:.1f} %"
        )
try:
    d, ambang, landsat, modis, waktu = siapkan(nama)
except CuacaGagal as e:
    st.error("Data cuaca dari Open-Meteo belum dapat diambil, sehingga prakiraan belum bisa "
             "dihitung. Periksa sambungan internet, lalu muat ulang halaman ini beberapa saat lagi.")
    with st.expander("Rincian teknis untuk pengelola sistem"):
        st.code(str(e) or type(e.__cause__).__name__)
    st.stop()
except Exception as e:
    st.error("Terjadi kendala saat menyiapkan data TPA ini. Coba pilih TPA lain atau muat ulang halaman.")
    with st.expander("Rincian teknis untuk pengelola sistem"):
        st.code(f"{type(e).__name__}: {e}")
    st.stop()

kini = d[d.tanggal <= hari_ini].iloc[-1]
depan = d[d.tanggal >= hari_ini]
if depan.empty:
    st.error("Prakiraan cuaca untuk hari ini dan ke depan belum tersedia. Muat ulang halaman beberapa saat lagi.")
    st.stop()
zon = zonasi(nama)

with st.sidebar:
    st.divider()
    st.markdown("**Ketersediaan data**")
    if landsat is not None:
        st.markdown(f"Citra Landsat: **{len(landsat)} citra**, terakhir "
                    f"{ui.tgl_sedang(landsat.date.max())} {landsat.date.max().year}")
    else:
        st.markdown("Citra Landsat: **belum ada**")
    st.markdown(f"Suhu malam MODIS: **{len(modis)} hari**" if modis is not None
                else "Suhu malam MODIS: **belum ada**")
    st.markdown(f"Peta zonasi: **{len(zon)} sel**" if zon is not None else "Peta zonasi: **belum ada**")
    st.markdown(f"Prakiraan cuaca Open-Meteo sampai **{ui.tgl_sedang(d.tanggal.max())}**")
    st.caption(f"Data diperbarui {ui.tgl_panjang(waktu)} pukul {waktu:%H.%M}. "
               "Data disegarkan otomatis setiap satu jam.")

if landsat is None:
    st.warning("Citra Landsat untuk TPA ini belum tersedia, sehingga bagian kondisi termal dari "
               "satelit belum memakai pengamatan langsung. Potensi kebakaran tetap dapat dibaca, namun kurang peka.")

ui.kartu_status(kini, ambang, depan, nama, info["wilayah"], AKSI[kini.level])
st.markdown("### Indikator Lapangan Pendukung")
st.markdown("### Interpretasi IRKT dan Indikator Lapangan")

if data_sensor is not None:
    irkt_level = str(kini.level)
    metana_level = str(data_sensor["kategori_metana"])

    if irkt_level == "HIJAU":
        interpretasi = (
            "Status IRKT berada pada tingkat HIJAU. "
            "Indikator metana lapangan ditampilkan sebagai informasi "
            "pendukung kondisi aktual saat pengukuran."
        )

    elif irkt_level == "KUNING":
        interpretasi = (
            "Status IRKT berada pada tingkat KUNING. "
            "Indikator metana digunakan sebagai informasi tambahan "
            "untuk membantu melihat kondisi lapangan saat pengukuran."
        )

    elif irkt_level == "ORANYE":
        interpretasi = (
            "Status IRKT berada pada tingkat ORANYE. "
            "Indikator metana memberikan informasi kondisi lapangan "
            "yang dapat dipertimbangkan bersama hasil model."
        )

    elif irkt_level == "MERAH":
        interpretasi = (
            "Status IRKT berada pada tingkat MERAH. "
            "Indikator metana tetap digunakan sebagai informasi kondisi "
            "lapangan dan tidak menggantikan hasil penilaian IRKT."
        )

    else:
        interpretasi = (
            "Status IRKT dan indikator metana ditampilkan sebagai "
            "dua informasi pendukung yang dibaca secara bersamaan."
        )

    st.info(
        f"**IRKT:** {irkt_level}  |  "
        f"**Metana:** {metana_level}\n\n"
        f"{interpretasi}"
    )
else:
    st.warning("Interpretasi belum tersedia karena data sensor belum tersedia.")

if data_sensor is not None:
    st.info(
        f"Sensor MQ-4 mencatat konsentrasi metana "
        f"**{data_sensor['methane_ppm']:.2f} ppm** "
        f"dengan kategori **{data_sensor['kategori_metana']}**. "
        f"Data ini digunakan sebagai informasi kondisi lapangan "
        f"pendukung pembacaan tingkat risiko kebakaran TPA."
    )
else:
    st.warning("Data sensor lapangan belum tersedia.")
if data_sensor is not None:
    st.markdown("**Perbandingan dengan tingkat risiko IRKT**")

    irkt_level = str(kini.level)
    metana_level = data_sensor["kategori_metana"]

    st.write(
        f"**IRKT:** {irkt_level}  |  "
        f"**Metana lapangan:** {metana_level}"
    )

    st.caption(
        "Perbandingan ini bersifat informatif. Data metana tidak "
        "mengubah nilai atau tingkat IRKT."
    )
ui.linimasa_15_hari(depan, hari_ini, ambang, ui.kalimat_kesimpulan(kini, depan, hari_ini))

tab1, tab2, tab3 = st.tabs(["Prakiraan", "Komponen indeks", "Zonasi dalam TPA"])
tampil = d[d.tanggal >= hari_ini - pd.Timedelta(days=hari_riwayat)]

with tab1:
    st.markdown(f"**Tingkat bahaya kebakaran TPA {nama}, {hari_riwayat} hari terakhir dan 15 hari ke depan**")
    st.altair_chart(ui.grafik_irkt(tampil, hari_ini, ambang), use_container_width=True,
                    key=f"irkt_{nama}_{hari_riwayat}")
    st.caption("Garis penuh: tingkat bahaya yang telah terjadi. Garis putus-putus: prakiraan. "
               "Pita warna di latar menunjukkan batas setiap tingkat potensi kebakaran. Arahkan kursor ke grafik untuk "
               "melihat angka harian.")
    st.markdown("**Rincian prakiraan harian**")
    ui.tabel_prakiraan(depan)
    k1, k2 = st.columns([3, 1])
    with k1:
        st.text_area("Pesan peringatan siap kirim (dapat disalin ke WhatsApp)",
                     pesan(nama, info["wilayah"], depan, ambang), height=210)
    with k2:
        st.markdown("&nbsp;")
        st.download_button("Unduh prakiraan (CSV)", depan.to_csv(index=False).encode(),
                           f"prakiraan_{nama}_{hari_ini:%Y%m%d}.csv", "text/csv", width="stretch")

with tab2:
    st.markdown("**Tiga bagian penyusun tingkat bahaya**")
    st.altair_chart(ui.grafik_komponen(tampil, hari_ini), use_container_width=True,
                    key=f"komponen_{nama}_{hari_riwayat}")
    st.caption("Tiap bagian diberi skor 0 sampai 100, lalu digabung sesuai bobotnya menjadi tingkat "
               "bahaya. Kekeringan timbunan naik saat hari tanpa hujan berlangsung lama. Cuaca harian "
               "naik saat udara panas, kering, dan berangin. Kondisi termal naik saat satelit melihat "
               "timbunan lebih panas dari sekitarnya. Garis tegak menandai hari ini.")
    if landsat is None:
        st.info("Citra Landsat untuk TPA ini belum ada di folder data. Jalankan script Earth Engine, "
                "lalu simpan berkas SIGAP_TPA_<nama>_LST.csv ke folder data.")

with tab3:
    if zon is None:
        st.info("Peta zonasi untuk TPA ini belum tersedia. Jalankan script zonasi di Earth Engine "
                "(gee/zonasi_risiko.js), lalu simpan berkas SIGAP_ZONASI_<nama>_sel.csv ke folder data.")
    else:
        st.markdown(f"**Sebaran Indeks Zonasi Risiko di dalam TPA {nama}**")
        st.pydeck_chart(ui.peta_zonasi(zon), height=520)
        ui.legenda_zonasi(zon)
        st.caption("Setiap kotak mewakili sel berukuran 90 meter. Sel di tepi TPA tampak lebih kecil "
                   "karena terpotong batas TPA. Arahkan kursor ke kotak untuk melihat nilainya. "
                   "Latar: citra satelit Esri World Imagery.")
        st.markdown("**Sepuluh sel prioritas patroli dan penyiraman**")
        ui.tabel_prioritas(zon)

