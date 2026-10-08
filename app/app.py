"""SIGAP-TPA: dasbor prakiraan bahaya kebakaran TPA (Streamlit)."""
import datetime as dt
import numpy as np
import pandas as pd, streamlit as st
from pathlib import Path
from sigap.config import TPA, AKSI, DATA_DIR
from sigap import weather, satellite, index as idx, iot
from sigap.model import ModelTimbunan
from sigap.alert import pesan
import ui_components as ui

st.set_page_config(page_title="SIGAP-TPA", page_icon="🔥", layout="wide")

# ----------------------------------------------------------------- Konfigurasi Firebase & IoT
def _firebase_config():
    """Ambil konfigurasi Firebase dari secrets, environment, atau default."""
    default_url = "https://sigap-tpa-default-rtdb.asia-southeast1.firebasedatabase.app"
    default_path = "sigap/Sarimukti/history"
    default_r0 = 10.0
    try:
        fb = st.secrets["FIREBASE"]
        return (
            fb.get("database_url", default_url),
            fb.get("sensor_path", default_path),
            float(fb.get("r0_kohm", default_r0)),
        )
    except Exception:
        import os
        return (
            os.environ.get("FIREBASE_DATABASE_URL", default_url),
            os.environ.get("FIREBASE_SENSOR_PATH", default_path),
            float(os.environ.get("FIREBASE_R0_KOHM", default_r0)),
        )


FIREBASE_DATABASE_URL, FIREBASE_SENSOR_PATH, R0_KOHM_SEMENTARA = _firebase_config()

MIN_BACAAN = 20  # Jumlah minimum pembacaan valid untuk data sensor asli


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
    return d, ambang, landsat, modis, dt.datetime.now(), fitur


@st.cache_data(ttl=3600, show_spinner=False)
def zonasi(nama: str):
    zon = satellite.muat_zonasi(nama)
    return None if zon is None or zon.IZR.notna().sum() == 0 else ui.siapkan_zonasi(zon)


# ----------------------------------------------------------------- Cache Firebase
@st.cache_data(ttl=30, show_spinner=False)
def ambil_sensor_firebase(database_url: str, sensor_path: str):
    """Ambil data sensor Firebase dengan cache 30 detik."""
    return iot.muat_data_firebase(
        database_url=database_url,
        path=sensor_path,
        timeout=10.0,
    )


# ----------------------------------------------------------------- Data demo
def buat_data_demo_dari_sarimukti(
    fitur_sarimukti: pd.DataFrame,
    n_hari: int = 30,
) -> pd.DataFrame:
    """Membuat data demo sensor berdasarkan data cuaca TPA Sarimukti.

    Data tidak dibuat dari angka acak tanpa hubungan dengan data cuaca Sarimukti.
    Menggunakan random seed tetap agar hasil tidak berubah setiap rerun.
    Tanggal menggunakan n_hari terakhir dari data Sarimukti (historis, tidak digeser).
    """
    rng = np.random.default_rng(seed=42)

    # Ambil n_hari terakhir dari fitur Sarimukti
    fitur = fitur_sarimukti.tail(n_hari).copy().reset_index(drop=True)

    if fitur.empty:
        return pd.DataFrame()

    n_bacaan = 288  # Asumsi pembacaan setiap 5 menit

    rows = []
    for _, baris in fitur.iterrows():
        tanggal = baris["tanggal"]
        tmax = baris["tmax"]
        rhmin = baris.get("rhmin", 70.0)
        kbdi_n = baris.get("kbdi_n", 0.3)

        # Suhu: tmax - 3 + noise ±0.5 °C
        suhu_rata = tmax - 3.0 + rng.uniform(-0.5, 0.5)
        suhu_min = suhu_rata - rng.uniform(3.0, 5.0)
        suhu_maks = suhu_rata + rng.uniform(0.5, 2.0)

        # Kelembapan: rhmin + noise kecil, clamp 0-100
        kelembapan_rata = np.clip(rhmin + rng.uniform(-3.0, 3.0), 0, 100)
        kelembapan_min = np.clip(kelembapan_rata - rng.uniform(5.0, 12.0), 0, 100)
        kelembapan_maks = np.clip(kelembapan_rata + rng.uniform(5.0, 12.0), 0, 100)

        # Metana: berdasarkan kbdi_n, semakin kering semakin tinggi
        # Rentang dasar 400-2000 ppm, naik dengan kekeringan
        metana_dasar = 400 + 1600 * float(np.clip(kbdi_n, 0, 1))
        metana_rata = metana_dasar + rng.uniform(-50, 50)
        metana_min = max(0.0, metana_rata - rng.uniform(100, 300))
        metana_maks = metana_rata + rng.uniform(50, 300)

        rows.append({
            "tanggal": pd.Timestamp(tanggal).normalize(),
            "suhu_min": round(suhu_min, 1),
            "suhu_rata": round(suhu_rata, 1),
            "suhu_maks": round(suhu_maks, 1),
            "kelembapan_min": round(kelembapan_min, 1),
            "kelembapan_rata": round(kelembapan_rata, 1),
            "kelembapan_maks": round(kelembapan_maks, 1),
            "metana_min_ppm": round(metana_min, 1),
            "metana_rata_ppm": round(metana_rata, 1),
            "metana_maks_ppm": round(metana_maks, 1),
            "n_bacaan": n_bacaan,
            "sumber": "demo (duplikat Sarimukti)",
        })

    harian = pd.DataFrame(rows)
    harian["metana_kelas"] = iot.klasifikasi_metana(harian["metana_rata_ppm"])
    return harian


# ----------------------------------------------------------------- Halaman utama
ui.pasang_gaya()
hari_ini = pd.Timestamp.today().normalize()

with st.sidebar:
    st.markdown("### Pengaturan")
    nama = st.selectbox("Pilih TPA", list(TPA))
    hari_riwayat = st.slider("Panjang riwayat pada grafik (hari)", 30, 365, 90, 30)
    info = TPA[nama]
    st.divider()
    st.markdown(f"**TPA {nama}**  \nWilayah: {info['wilayah']}  \nLanskap: {info['lanskap']}  \n"
                f"Koordinat: {info['lat']:.4f}, {info['lon']:.4f}")

ui.header(hari_ini)

try:
    d, ambang, landsat, modis, waktu, fitur = siapkan(nama)
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
ui.linimasa_15_hari(depan, hari_ini, ambang, ui.kalimat_kesimpulan(kini, depan, hari_ini))

tab1, tab2, tab3, tab4 = st.tabs(["Prakiraan", "Komponen indeks", "Zonasi dalam TPA",
                                   "Sensor IoT (Prototipe)"])
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

# ================================================================= TAB SENSOR IoT
@st.fragment(run_every=30)
def render_sensor_iot(nama, fitur, d):
    import altair as alt

    WARNA_AMAN = "#2CA02C"
    WARNA_WASPADA = "#F2C200"
    WARNA_BAHAYA = "#D62728"
    TINTA = "#1F2933"
    TINTA_2 = "#52606D"

    # Ambang metana dari modul iot (sumber kebenaran jurnal ilmiah)
    # Aman < 500 ppm, Waspada 500 - 1000 ppm, Bahaya > 1000 ppm
    A_AMAN, A_WASPADA = iot.AMBANG_METANA
    WARNA_KELAS = {
        "aman": WARNA_AMAN,
        "waspada": WARNA_WASPADA,
        "bahaya": WARNA_BAHAYA,
    }


    # ----- Pemilihan sumber data -----
    pakai_demo = True
    sumber_sensor = "demo"
    harian_sensor = pd.DataFrame()
    log_mentah = pd.DataFrame()
    n_total = 0

    # 1. Coba Firebase (prioritaskan path TPA aktif, lalu default)
    if FIREBASE_DATABASE_URL:
        jalur_kandidat = [f"sigap/{nama}/history"]
        if FIREBASE_SENSOR_PATH not in jalur_kandidat:
            jalur_kandidat.append(FIREBASE_SENSOR_PATH)

        for jalur in jalur_kandidat:
            try:
                log_firebase = ambil_sensor_firebase(FIREBASE_DATABASE_URL, jalur)
                if len(log_firebase) >= MIN_BACAAN:
                    log_mentah = iot.proses_log_dataframe(
                        log_firebase,
                        r0_kohm=R0_KOHM_SEMENTARA,
                        vcc=3.3,
                        rl_kohm=10.0,
                    )
                    if len(log_mentah) >= MIN_BACAAN:
                        harian_sensor = iot.ringkas_harian(log_mentah)
                        harian_sensor["sumber"] = "sensor asli"
                        sumber_sensor = f"Firebase ({jalur})"
                        n_total = len(log_mentah)
                        pakai_demo = False
                        break
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Gagal memuat Firebase %s: %s", jalur, e)

    # 2. Fallback CSV
    if pakai_demo:
        path_log = DATA_DIR / "sensor_log.csv"
        if path_log.exists():
            try:
                log_mentah = iot.muat_log(
                    str(path_log),
                    r0_kohm=R0_KOHM_SEMENTARA,
                    vcc=3.3,
                    rl_kohm=10.0,
                )
                if len(log_mentah) >= MIN_BACAAN:
                    harian_sensor = iot.ringkas_harian(log_mentah)
                    harian_sensor["sumber"] = "sensor asli"
                    sumber_sensor = "CSV lokal"
                    n_total = len(log_mentah)
                    pakai_demo = False
            except Exception:
                pass

    # 3. Demo
    if pakai_demo:
        harian_sensor = buat_data_demo_dari_sarimukti(fitur, n_hari=30)
        sumber_sensor = "Demo Sarimukti"
        n_total = 0

    # ----- A. Banner status data -----
    if pakai_demo:
        st.warning(
            "**DATA CONTOH**\n\n"
            "Data ini diduplikasi dari data cuaca TPA Sarimukti. "
            "Menunggu data sensor MQ-4 dan DHT22 sungguhan dari prototipe di lapangan.",
            icon="⚠️",
        )

    if harian_sensor.empty:
        st.info("Belum ada data sensor yang dapat ditampilkan.")
    else:
        # ----- B. Tiga kartu ringkas -----
        baris_terakhir = harian_sensor.iloc[-1]
        suhu_terkini = baris_terakhir.get("suhu_rata", float("nan"))
        suhu_min_terkini = baris_terakhir.get("suhu_min", suhu_terkini)
        suhu_maks_terkini = baris_terakhir.get("suhu_maks", suhu_terkini)

        rh_terkini = baris_terakhir.get("kelembapan_rata", float("nan"))
        rh_min_terkini = baris_terakhir.get("kelembapan_min", rh_terkini)
        rh_maks_terkini = baris_terakhir.get("kelembapan_maks", rh_terkini)

        metana_terkini = baris_terakhir.get("metana_rata_ppm", float("nan"))
        metana_min_terkini = baris_terakhir.get("metana_min_ppm", 0.0)
        metana_maks_terkini = baris_terakhir.get("metana_maks_ppm", metana_terkini)
        kelas_terkini = str(baris_terakhir.get("metana_kelas", ""))

        warna_metana = WARNA_KELAS.get(kelas_terkini, TINTA_2)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Suhu rata-rata terbaru", f"{suhu_terkini:.1f} °C")
            st.caption(f"Min: **{suhu_min_terkini:.1f} °C** — Maks: **{suhu_maks_terkini:.1f} °C**")
        with c2:
            st.metric("Kelembapan rata-rata terbaru", f"{rh_terkini:.1f} %")
            st.caption(f"Min: **{rh_min_terkini:.1f} %** — Maks: **{rh_maks_terkini:.1f} %**")
        with c3:
            st.markdown(
                f'<div style="font-size:14px;color:{TINTA_2};margin-bottom:4px;">Metana (Rata-rata)</div>'
                f'<div style="font-size:28px;font-weight:600;color:{TINTA};">{metana_terkini:,.0f} ppm</div>'
                f'<div style="font-size:16px;font-weight:600;color:{warna_metana};'
                f'text-transform:uppercase;margin-top:4px;">{kelas_terkini}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Min: **{metana_min_terkini:,.0f} ppm** — Maks: **{metana_maks_terkini:,.0f} ppm**")

        st.divider()

        # ----- C. Grafik suhu dan kelembapan -----
        st.markdown("**Suhu dan kelembapan harian**")
        g_kiri, g_kanan = st.columns(2)

        with g_kiri:
            if "tanggal" in harian_sensor.columns and "suhu_rata" in harian_sensor.columns:
                grafik_suhu = (
                    alt.Chart(harian_sensor)
                    .mark_line(color="#1B4965", strokeWidth=2.2, point=alt.OverlayMarkDef(size=40))
                    .encode(
                        x=alt.X("tanggal:T", title=None,
                                axis=alt.Axis(labelAngle=0, grid=False, labelColor=TINTA_2)),
                        y=alt.Y("suhu_rata:Q", title="Suhu rata-rata (°C)",
                                axis=alt.Axis(gridColor="#EEF2F6", labelColor=TINTA_2,
                                              titleColor=TINTA)),
                        tooltip=[
                            alt.Tooltip("tanggal:T", title="Tanggal", format="%d %b %Y"),
                            alt.Tooltip("suhu_min:Q", title="Suhu min (°C)", format=".1f"),
                            alt.Tooltip("suhu_rata:Q", title="Suhu rata-rata (°C)", format=".1f"),
                            alt.Tooltip("suhu_maks:Q", title="Suhu maks (°C)", format=".1f"),
                        ],
                    )
                    .properties(height=260, title="Suhu rata-rata harian")
                    .configure_view(stroke=None)
                )
                st.altair_chart(grafik_suhu, use_container_width=True, key="grafik_suhu_iot")

        with g_kanan:
            if "tanggal" in harian_sensor.columns and "kelembapan_rata" in harian_sensor.columns:
                grafik_rh = (
                    alt.Chart(harian_sensor)
                    .mark_line(color="#62B6CB", strokeWidth=2.2, point=alt.OverlayMarkDef(size=40))
                    .encode(
                        x=alt.X("tanggal:T", title=None,
                                axis=alt.Axis(labelAngle=0, grid=False, labelColor=TINTA_2)),
                        y=alt.Y("kelembapan_rata:Q", title="Kelembapan rata-rata (%)",
                                scale=alt.Scale(domain=[0, 100]),
                                axis=alt.Axis(gridColor="#EEF2F6", labelColor=TINTA_2,
                                              titleColor=TINTA)),
                        tooltip=[
                            alt.Tooltip("tanggal:T", title="Tanggal", format="%d %b %Y"),
                            alt.Tooltip("kelembapan_min:Q", title="Kelembapan min (%)", format=".1f"),
                            alt.Tooltip("kelembapan_rata:Q", title="Kelembapan rata-rata (%)", format=".1f"),
                            alt.Tooltip("kelembapan_maks:Q", title="Kelembapan maks (%)", format=".1f"),
                        ],
                    )
                    .properties(height=260, title="Kelembapan rata-rata harian")
                    .configure_view(stroke=None)
                )
                st.altair_chart(grafik_rh, use_container_width=True, key="grafik_rh_iot")

        st.divider()

        # ----- D. Grafik metana -----
        st.markdown("**Konsentrasi metana harian**")

        if "tanggal" in harian_sensor.columns and "metana_rata_ppm" in harian_sensor.columns:
            # Pita ambang latar berdasarkan jurnal ilmiah
            maks_ppm = min(max(harian_sensor["metana_rata_ppm"].max() * 1.2, A_WASPADA * 1.5), 20_000)
            pita_metana = pd.DataFrame({
                "y0": [0, A_AMAN, A_WASPADA],
                "y1": [A_AMAN, A_WASPADA, maks_ppm],
                "kelas": ["Aman", "Waspada", "Bahaya"],
                "warna": [WARNA_AMAN, WARNA_WASPADA, WARNA_BAHAYA],
            })

            lapis_pita = (
                alt.Chart(pita_metana)
                .mark_rect(opacity=0.12)
                .encode(
                    y="y0:Q", y2="y1:Q",
                    color=alt.Color("warna:N", scale=None),
                )
            )

            # Label pita di sisi kanan
            pita_metana["tengah"] = (pita_metana["y0"] + pita_metana["y1"]) / 2
            pita_metana["tanggal_label"] = harian_sensor["tanggal"].max()
            label_pita = (
                alt.Chart(pita_metana)
                .mark_text(align="left", dx=8, fontSize=11, fontWeight="bold")
                .encode(
                    x="tanggal_label:T",
                    y=alt.Y("tengah:Q"),
                    text="kelas:N",
                    color=alt.Color("warna:N", scale=None),
                )
            )

            garis_metana = (
                alt.Chart(harian_sensor)
                .mark_line(color=TINTA, strokeWidth=2.2, point=alt.OverlayMarkDef(size=50, color=TINTA))
                .encode(
                    x=alt.X("tanggal:T", title=None,
                            axis=alt.Axis(labelAngle=0, grid=False, labelColor=TINTA_2)),
                    y=alt.Y("metana_rata_ppm:Q", title="Metana rata-rata (ppm)",
                            scale=alt.Scale(domain=[0, maks_ppm], nice=False),
                            axis=alt.Axis(gridColor="#EEF2F6", labelColor=TINTA_2,
                                          titleColor=TINTA)),
                    tooltip=[
                        alt.Tooltip("tanggal:T", title="Tanggal", format="%d %b %Y"),
                        alt.Tooltip("metana_min_ppm:Q", title="Metana min (ppm)", format=",.0f"),
                        alt.Tooltip("metana_rata_ppm:Q", title="Metana rata-rata (ppm)", format=",.0f"),
                        alt.Tooltip("metana_maks_ppm:Q", title="Metana maks (ppm)", format=",.0f"),
                        alt.Tooltip("metana_kelas:N", title="Status"),
                    ],
                )
            )

            grafik_ch4 = (
                alt.layer(lapis_pita, label_pita, garis_metana)
                .properties(height=320, padding={"right": 100})
                .configure_view(stroke=None)
            )
            st.altair_chart(grafik_ch4, use_container_width=True, key="grafik_metana_iot")

            st.caption(
                "Pita warna di latar menunjukkan indikator konsentrasi gas metana (MQ-4) berdasarkan jurnal ilmiah: "
                "**Aman** < {:,} ppm, **Waspada** {:,} - {:,} ppm, "
                "**Bahaya** > {:,} ppm (berisiko kebakaran dalam 8 jam).".format(
                    A_AMAN, A_AMAN, A_WASPADA, A_WASPADA
                )
            )

        st.divider()

        # ----- E. Tabel 7 hari terakhir -----
        st.markdown("**Data 7 hari terakhir**")
        tujuh_hari = harian_sensor.sort_values("tanggal", ascending=False).head(7).copy()

        def _ambil_kolom(df, col, default_val=0.0):
            return df[col] if col in df.columns else default_val

        tabel = pd.DataFrame({
            "Tanggal": tujuh_hari["tanggal"].dt.strftime("%d-%m-%Y"),
            "Suhu min (°C)": _ambil_kolom(tujuh_hari, "suhu_min", tujuh_hari["suhu_rata"]).round(1),
            "Suhu rata-rata (°C)": tujuh_hari["suhu_rata"].round(1),
            "Suhu maksimum (°C)": tujuh_hari["suhu_maks"].round(1),
            "Kelembapan min (%)": _ambil_kolom(tujuh_hari, "kelembapan_min", tujuh_hari["kelembapan_rata"]).round(1),
            "Kelembapan rata-rata (%)": tujuh_hari["kelembapan_rata"].round(1),
            "Kelembapan maksimum (%)": _ambil_kolom(tujuh_hari, "kelembapan_maks", tujuh_hari["kelembapan_rata"]).round(1),
            "Metana min (ppm)": _ambil_kolom(tujuh_hari, "metana_min_ppm", 0.0).round(0).astype(int),
            "Metana rata-rata (ppm)": tujuh_hari["metana_rata_ppm"].round(0).astype(int),
            "Metana maksimum (ppm)": tujuh_hari["metana_maks_ppm"].round(0).astype(int),
            "Jumlah pembacaan": tujuh_hari["n_bacaan"].astype(int),
            "Status metana": tujuh_hari["metana_kelas"].str.capitalize(),
        }).reset_index(drop=True)

        # Warnai status metana
        kelas_list = tujuh_hari["metana_kelas"].tolist()

        def warnai_metana(kolom):
            return [
                f"color: {WARNA_KELAS.get(k, TINTA_2)}; font-weight: 600"
                for k in kelas_list
            ]

        gaya_tabel = tabel.style.apply(warnai_metana, subset=["Status metana"])
        st.dataframe(gaya_tabel, hide_index=True, use_container_width=True,
                     height=38 + 35 * len(tabel))

        st.divider()

        # ----- F. Panel perbandingan dengan model IRKT -----
        st.markdown("**Perbandingan data sensor dengan model IRKT**")

        perbandingan = iot.bandingkan_dengan_model(harian_sensor, d)

        if perbandingan.empty:
            st.info("Belum terdapat tanggal yang sama antara data sensor dan periode model.")
        else:
            # Normalisasi suhu sensor: anomali terhadap rata-rata periode
            rata_suhu = perbandingan["suhu_rata"].mean()
            perbandingan["suhu_anomali"] = perbandingan["suhu_rata"] - rata_suhu

            # Normalisasi z_prediksi ke skala serupa untuk perbandingan visual
            rata_z = perbandingan["z_prediksi"].mean()
            std_z = perbandingan["z_prediksi"].std()
            std_suhu = perbandingan["suhu_anomali"].std()

            if std_z > 0 and std_suhu > 0:
                perbandingan["z_pred_norm"] = (
                    (perbandingan["z_prediksi"] - rata_z) / std_z * std_suhu
                )
            else:
                perbandingan["z_pred_norm"] = perbandingan["z_prediksi"] - rata_z

            # Siapkan data untuk grafik
            df_vis = perbandingan[["tanggal", "suhu_anomali", "z_pred_norm"]].melt(
                id_vars="tanggal",
                var_name="seri",
                value_name="nilai",
            )
            df_vis["Seri"] = df_vis["seri"].map({
                "suhu_anomali": "Anomali suhu sensor (°C)",
                "z_pred_norm": "z prediksi model (dinormalisasi)",
            })

            grafik_banding = (
                alt.Chart(df_vis)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("tanggal:T", title=None,
                            axis=alt.Axis(labelAngle=0, grid=False, labelColor=TINTA_2)),
                    y=alt.Y("nilai:Q", title="Nilai (dinormalisasi)",
                            axis=alt.Axis(gridColor="#EEF2F6", labelColor=TINTA_2,
                                          titleColor=TINTA)),
                    color=alt.Color("Seri:N",
                                    scale=alt.Scale(
                                        domain=["Anomali suhu sensor (°C)",
                                                "z prediksi model (dinormalisasi)"],
                                        range=["#1B4965", "#9C6ADE"]),
                                    legend=alt.Legend(orient="bottom", title=None,
                                                      labelFontSize=13)),
                    tooltip=[
                        alt.Tooltip("tanggal:T", title="Tanggal", format="%d %b %Y"),
                        alt.Tooltip("Seri:N", title="Seri"),
                        alt.Tooltip("nilai:Q", title="Nilai", format=".2f"),
                    ],
                )
                .properties(height=300)
                .configure_view(stroke=None)
            )
            st.altair_chart(grafik_banding, use_container_width=True,
                            key="grafik_banding_sensor_model")

            st.caption(
                "Grafik ini digunakan untuk melihat pola pergerakan data sensor dan prediksi "
                "model pada tanggal yang sama. Kesamaan arah tidak berarti sensor menjadi "
                "variabel langsung dalam perhitungan IRKT."
            )


with tab4:
    render_sensor_iot(nama, fitur, d)


