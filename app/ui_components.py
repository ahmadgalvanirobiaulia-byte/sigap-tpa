"""Komponen visual dasbor SIGAP-TPA: gaya, kartu status, grafik, peta, dan tabel.

Modul ini hanya menata tampilan. Seluruh angka (IRKT, ambang, status) dihitung di paket
`sigap` dan diterima di sini apa adanya.
"""
from __future__ import annotations
import math
import altair as alt, numpy as np, pandas as pd, pydeck as pdk, streamlit as st
from sigap.config import AMBANG_KUNING, AMBANG_ORANYE, W_KERING, W_CUACA, W_SAT

BIRU = "#1B4965"
TINTA, TINTA_2, TINTA_3, GARIS = "#1F2933", "#52606D", "#7B8794", "#D9E2EC"
URUTAN = ["HIJAU", "KUNING", "ORANYE", "MERAH"]
STATUS = {
    "HIJAU":  dict(nama="Rendah",   warna="#2CA02C", gelap="#1E7A1E"),
    "KUNING": dict(nama="Sedang",   warna="#F2C200", gelap="#8A6D00"),
    "ORANYE": dict(nama="Tinggi",   warna="#FF7F0E", gelap="#B35400"),
    "MERAH":  dict(nama="Sangat tinggi", warna="#D62728", gelap="#A01C1D"),
}
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]
BULAN3 = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
HARI3 = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


# ----------------------------------------------------------------- utilitas teks
def tgl_panjang(t) -> str:
    return f"{HARI[t.weekday()]}, {t.day} {BULAN[t.month - 1]} {t.year}"


def tgl_sedang(t) -> str:
    return f"{t.day} {BULAN[t.month - 1]}"


def tgl_pendek(t) -> str:
    return f"{t.day} {BULAN3[t.month - 1]}"


def nama_status(level: str) -> str:
    return STATUS[level]["nama"]


def potensi(level: str) -> str:
    return f"potensi kebakaran {STATUS[level]['nama'].lower()}"


def _html(s: str) -> str:
    """Rapatkan HTML agar tidak ditafsirkan sebagai blok kode Markdown."""
    return " ".join(baris.strip() for baris in s.splitlines() if baris.strip())


def tulis_html(s: str):
    st.markdown(_html(s), unsafe_allow_html=True)


def angka(x, desimal: int = 0) -> str:
    """Format angka gaya Indonesia (koma desimal)."""
    if x is None or pd.isna(x):
        return "-"
    return f"{x:.{desimal}f}".replace(".", ",")


# ----------------------------------------------------------------- gaya halaman
CSS = f"""
<style>
.block-container {{padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1240px;}}
.sg-header {{display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  flex-wrap: wrap; margin-bottom: 40px;}}
.sg-header .kiri {{display: flex; gap: 14px; align-items: center; flex: 1 1 520px; min-width: 0;}}
.sg-mono {{width: 40px; height: 40px; border-radius: 3px; background: {TINTA}; color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 600;
  font-size: 14px; letter-spacing: .5px; flex: none;}}
.sg-nama {{font-size: 22px; font-weight: 600; color: {TINTA}; line-height: 1.15; letter-spacing: .2px;}}
.sg-nama span {{font-weight: 400; color: {TINTA_2};}}
.sg-desk {{font-size: 13px; color: {TINTA_2}; margin-top: 3px;}}
.sg-tgl {{text-align: right; font-size: 12px; color: {TINTA_3}; text-transform: uppercase;
  letter-spacing: .8px; flex: none;}}
.sg-tgl b {{display: block; font-size: 15px; color: {TINTA}; font-weight: 600;
  text-transform: none; letter-spacing: 0; margin-top: 2px;}}

.sg-lbl {{font-size: 12px; font-weight: 600; color: {TINTA_3}; text-transform: uppercase; letter-spacing: 1px;}}

.sg-atas {{display: grid; grid-template-columns: minmax(0, 1.9fr) minmax(0, 1fr); column-gap: 56px;}}
@media (max-width: 900px) {{.sg-atas {{grid-template-columns: 1fr; row-gap: 32px;}}
  .sg-indikator {{border-left: none !important; padding-left: 0 !important;}}}}
.sg-status .tingkat {{display: flex; align-items: center; gap: 10px; margin-top: 14px;
  font-size: 26px; font-weight: 600; line-height: 1;}}
.sg-status .tingkat i {{width: 14px; height: 14px; border-radius: 50%; display: inline-block; flex: none;}}
.sg-status .skor {{font-size: 112px; font-weight: 600; color: {TINTA}; line-height: .95;
  letter-spacing: -3px; margin-top: 10px; font-variant-numeric: tabular-nums;}}
.sg-status .skor span {{font-size: 28px; font-weight: 400; color: {TINTA_3}; letter-spacing: 0; margin-left: 6px;}}
.sg-status .lokasi {{margin-top: 14px; font-size: 18px; color: {TINTA}; font-weight: 600;}}
.sg-status .lokasi span {{display: block; font-size: 15px; font-weight: 400; color: {TINTA_2}; margin-top: 2px;}}

.sg-skala {{margin-top: 34px; max-width: 640px;}}
.sg-skala .jalur {{position: relative; height: 10px; display: flex; gap: 2px;}}
.sg-skala .seg {{height: 10px;}}
.sg-skala .penanda {{position: absolute; top: -9px; width: 2px; height: 28px; background: {TINTA};}}
.sg-skala .penanda b {{position: absolute; top: -20px; left: 50%; transform: translateX(-50%);
  font-size: 13px; font-weight: 600; color: {TINTA}; white-space: nowrap;}}
.sg-skala .nama {{display: flex; gap: 2px; margin-top: 10px;}}
.sg-skala .nama div {{font-size: 12px; color: {TINTA_3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.sg-skala .nama div.aktif {{color: {TINTA}; font-weight: 600;}}
.sg-skala .angka {{position: relative; height: 16px; margin-top: 2px;}}
.sg-skala .angka span {{position: absolute; transform: translateX(-50%); font-size: 11px; color: {TINTA_3};
  font-variant-numeric: tabular-nums;}}

.sg-rek {{margin-top: 30px; max-width: 640px;}}
.sg-rek p {{font-size: 17px; color: {TINTA}; line-height: 1.5; margin: 6px 0 0 0;}}

.sg-indikator {{border-left: 1px solid {GARIS}; padding-left: 40px;}}
.sg-indikator .item {{padding: 18px 0; border-bottom: 1px solid {GARIS};}}
.sg-indikator .item:last-child {{border-bottom: none;}}
.sg-indikator .v {{font-size: 34px; font-weight: 600; color: {TINTA}; line-height: 1.1;
  font-variant-numeric: tabular-nums;}}
.sg-indikator .v span {{font-size: 16px; font-weight: 400; color: {TINTA_2}; margin-left: 4px;}}
.sg-indikator .j {{font-size: 15px; font-weight: 600; color: {TINTA}; margin-top: 4px;}}
.sg-indikator .k {{font-size: 13px; color: {TINTA_2}; margin-top: 2px; line-height: 1.4;}}

.sg-linimasa {{margin-top: 56px; padding-top: 28px; border-top: 1px solid {GARIS};}}
.sg-linimasa .simpul {{font-size: 19px; color: {TINTA}; line-height: 1.45; margin: 8px 0 22px 0; max-width: 900px;}}
.sg-linimasa .simpul b {{font-weight: 600;}}
.sg-plot {{display: grid; grid-template-columns: repeat(15, minmax(0, 1fr)) 104px;}}
.sg-plot .area {{grid-column: 1 / 16; position: relative; height: 150px;
  border-bottom: 1px solid {TINTA_3};}}
.sg-plot .zona {{position: absolute; left: 0; right: 0;}}
.sg-plot .kolom {{position: absolute; top: 0; bottom: 0;}}
.sg-plot .kolom:hover {{background: rgba(31,41,51,.04);}}
.sg-plot .kolom.kini {{background: rgba(31,41,51,.07);}}
.sg-plot .titik {{position: absolute; left: 50%; width: 12px; height: 12px; border-radius: 50%;
  transform: translate(-50%, -50%); border: 2px solid #fff;}}
.sg-plot .kini .titik {{width: 18px; height: 18px;}}
.sg-plot .nilai {{position: absolute; left: 50%; transform: translate(-50%, -100%); margin-top: -12px;
  font-size: 12px; color: {TINTA_2}; font-variant-numeric: tabular-nums;}}
.sg-plot .kini .nilai {{color: {TINTA}; font-weight: 600; margin-top: -15px;}}
.sg-plot .ambang {{position: absolute; left: 0; right: 0; border-top: 1px dashed {STATUS['MERAH']['warna']};}}
.sg-plot .sisi {{position: relative; height: 150px;}}
.sg-plot .sisi span {{position: absolute; left: 12px; transform: translateY(-50%); font-size: 11px;
  color: {TINTA_3}; white-space: nowrap; line-height: 1.2;}}
.sg-plot .sisi span.merah {{color: {STATUS['MERAH']['gelap']};}}
.sg-plot .t {{font-size: 12px; color: {TINTA_2}; line-height: 1.3; text-align: center;
  padding: 8px 0 10px 0; white-space: nowrap;}}
.sg-plot .t small {{display: block; font-size: 11px; color: {TINTA_3};}}
.sg-plot .t.kini {{color: {TINTA}; font-weight: 600; background: rgba(31,41,51,.07);}}
.sg-plot .t.kini small {{color: {TINTA}; font-weight: 600;}}
@media (max-width: 700px) {{.sg-plot {{grid-template-columns: repeat(15, minmax(0, 1fr)) 64px;}}
  .sg-plot .t, .sg-plot .nilai {{font-size: 9px;}} .sg-plot .t small {{font-size: 8px;}}}}
.sg-legenda {{display: flex; gap: 20px; flex-wrap: wrap; margin-top: 6px; font-size: 12px; color: {TINTA_2};}}
.sg-legenda i {{display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  vertical-align: 0; margin-right: 6px;}}

.sg-gradasi {{height: 10px; margin-top: 6px;
  background: linear-gradient(90deg, #2CA02C, #F2C200, #FF7F0E, #D62728);}}
.sg-gradasi-lbl {{display: flex; justify-content: space-between; font-size: 12px; color: {TINTA_2}; margin-top: 4px;}}
div[data-testid="stTabs"] {{margin-top: 48px;}}
div[data-testid="stTabs"] button p {{font-size: 15px; font-weight: 600;}}
</style>
"""


def pasang_gaya():
    st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------- header
def header(tanggal):
    tulis_html(f"""
    <div class="sg-header">
      <div class="kiri">
        <div class="sg-mono">ST</div>
        <div>
          <div class="sg-nama">SIGAP-TPA <span>Sistem Informasi Geospasial Antisipasi Api TPA</span></div>
          <div class="sg-desk">Prakiraan tingkat bahaya kebakaran timbunan sampah 15 hari ke depan.
            Sumber data: Landsat 8/9, MODIS, Open-Meteo.</div>
        </div>
      </div>
      <div class="sg-tgl">Tanggal pemantauan<b>{tgl_panjang(tanggal)}</b></div>
    </div>""")


# ----------------------------------------------------------------- status utama
def _skala_risiko(skor: float, level: str, ambang: float) -> str:
    batas = [0, AMBANG_KUNING, AMBANG_ORANYE, ambang, 100]
    seg, nama = [], []
    for k, a, b in zip(URUTAN, batas, batas[1:]):
        lebar = b - a
        aktif = k == level
        seg.append(f'<div class="seg" style="flex:{lebar} 0 0; background:{STATUS[k]["warna"]};'
                   f'opacity:{1 if aktif else .28}"></div>')
        nama.append(f'<div class="{"aktif" if aktif else ""}" style="flex:{lebar} 0 0">{STATUS[k]["nama"]}</div>')
    posisi = float(np.clip(skor, 0, 100))
    angka_batas = "".join(f'<span style="left:{v}%">{v:.0f}</span>' for v in batas[1:-1])
    return f"""
    <div class="sg-skala">
      <div class="jalur">{"".join(seg)}
        <div class="penanda" style="left:calc({posisi}% - 1px)"><b>{skor:.0f}</b></div>
      </div>
      <div class="nama">{"".join(nama)}</div>
      <div class="angka">{angka_batas}</div>
    </div>"""


def _indikator(nilai: str, satuan: str, judul: str, ket: str) -> str:
    sat = f"<span>{satuan}</span>" if satuan else ""
    return (f'<div class="item"><div class="v">{nilai}{sat}</div>'
            f'<div class="j">{judul}</div><div class="k">{ket}</div></div>')


def kartu_status(kini: pd.Series, ambang: float, depan: pd.DataFrame, nama: str,
                 wilayah: str, aksi: str):
    s = STATUS[kini.level]
    puncak = depan.loc[depan.IRKT.idxmax()]
    if pd.isna(kini.umur_landsat):
        citra = _indikator("Belum ada", "", "Citra satelit terakhir",
                           "Citra Landsat untuk TPA ini belum tersedia")
    else:
        tgl_citra = kini.tanggal - pd.Timedelta(days=int(kini.umur_landsat))
        modis = ("" if pd.isna(kini.umur_modis)
                 else f"<br>Suhu malam MODIS {kini.umur_modis:.0f} hari lalu")
        citra = _indikator(f"{kini.umur_landsat:.0f}", "hari lalu", "Citra satelit terakhir",
                           f"Landsat, {tgl_sedang(tgl_citra)} {tgl_citra.year}{modis}")
    tgl_puncak = "Hari ini" if puncak.tanggal == kini.tanggal else tgl_panjang(puncak.tanggal)
    tulis_html(f"""
    <div class="sg-atas">
      <div class="sg-status">
        <div class="sg-lbl">Potensi kebakaran hari ini</div>
        <div class="tingkat" style="color:{s['gelap']}"><i style="background:{s['warna']}"></i>{s['nama']}</div>
        <div class="skor">{kini.IRKT:.0f}<span>/ 100</span></div>
        <div class="lokasi">TPA {nama}<span>{wilayah}</span></div>
        {_skala_risiko(kini.IRKT, kini.level, ambang)}
        <div class="sg-rek"><div class="sg-lbl">Rekomendasi</div><p>{aksi}</p></div>
      </div>
      <div class="sg-indikator">
        <div class="sg-lbl">Indikator utama</div>
        {_indikator(f"{puncak.IRKT:.0f}", "/ 100", "Puncak 15 hari ke depan",
                    f"{tgl_puncak}, {potensi(puncak.level)}")}
        {_indikator(f"{ambang:.0f}", "/ 100", "Batas potensi sangat tinggi",
                    "Ambang khusus untuk TPA ini, disusun dari catatan musim kemarau setempat")}
        {citra}
      </div>
    </div>""")


# ----------------------------------------------------------------- linimasa 15 hari
def legenda_status() -> str:
    return ('<div class="sg-legenda">'
            + "".join(f'<span><i style="background:{STATUS[k]["warna"]}"></i>Potensi {STATUS[k]["nama"].lower()}</span>'
                      for k in URUTAN) + "</div>")


def kalimat_kesimpulan(kini: pd.Series, depan: pd.DataFrame, hari_ini) -> str:
    rank = [URUTAN.index(x) for x in depan.level]
    r0 = URUTAN.index(kini.level)
    n = len(depan)
    puncak = depan.loc[depan.IRKT.idxmax()]
    tgl_puncak = ("hari ini" if puncak.tanggal == hari_ini
                  else f"{HARI[puncak.tanggal.weekday()]}, {tgl_sedang(puncak.tanggal)}")
    ekor = f", dengan puncak bahaya pada {tgl_puncak} (tingkat {puncak.IRKT:.0f})."
    if max(rank) > r0:
        j = rank.index(max(rank))
        return (f"Potensi kebakaran diperkirakan <b>naik</b> dari {nama_status(kini.level).lower()} menjadi "
                f"<b>{nama_status(URUTAN[max(rank)]).lower()}</b> mulai {tgl_sedang(depan.tanggal.iloc[j])}" + ekor)
    if min(rank) < r0:
        j = next(i for i, x in enumerate(rank) if x < r0)
        return (f"Potensi kebakaran diperkirakan <b>turun</b> dari {nama_status(kini.level).lower()} menjadi "
                f"<b>{nama_status(URUTAN[rank[j]]).lower()}</b> mulai {tgl_sedang(depan.tanggal.iloc[j])}" + ekor)
    return (f"Potensi kebakaran <b>tetap {nama_status(kini.level).lower()}</b> selama "
            f"{n} hari ke depan" + ekor)


def linimasa_15_hari(depan: pd.DataFrame, hari_ini, ambang: float, kalimat: str):
    d15 = depan.head(15)
    n = len(d15)
    # Skala vertikal mengikuti rentang nilai 15 hari agar perbedaan antarhari terlihat.
    lo = max(0.0, math.floor((min(d15.IRKT.min(), ambang) - 8) / 5) * 5)
    hi = min(100.0, math.ceil((max(d15.IRKT.max(), ambang) + 6) / 5) * 5)
    if hi - lo < 20:
        lo = max(0.0, hi - 20)
    TINGGI, TEPI = 150, 26              # tinggi area (px) dan ruang atas untuk label angka

    def y(v):                           # nilai -> posisi dari atas (px)
        return TEPI + (hi - float(np.clip(v, lo, hi))) / (hi - lo) * (TINGGI - TEPI - 10)

    batas = [0, AMBANG_KUNING, AMBANG_ORANYE, ambang, 100]
    zona, label_zona = [], []
    for k, a, b in zip(URUTAN, batas, batas[1:]):
        a2, b2 = max(a, lo), min(b, hi)
        if b2 <= a2:
            continue
        atas = 0 if b2 >= hi else y(b2)
        bawah = TINGGI if a2 <= lo else y(a2)
        zona.append(f'<div class="zona" style="top:{atas:.0f}px; height:{bawah - atas:.0f}px;'
                    f'background:{STATUS[k]["warna"]}; opacity:.09"></div>')
        tengah = (atas + bawah) / 2
        if bawah - atas >= 14 and not (lo <= ambang <= hi and abs(tengah - y(ambang)) < 16):
            label_zona.append(f'<span style="top:{tengah:.0f}px">{STATUS[k]["nama"]}</span>')

    kolom, tanggal = [], []
    for i, (_, r) in enumerate(d15.iterrows()):
        kini = r.tanggal == hari_ini
        kls = " kini" if kini else ""
        kolom.append(
            f'<div class="kolom{kls}" style="left:{100 * i / n:.4f}%; width:{100 / n:.4f}%" '
            f'title="{tgl_panjang(r.tanggal)}: tingkat bahaya {r.IRKT:.0f}, {potensi(r.level)}">'
            f'<div class="nilai" style="top:{y(r.IRKT):.0f}px">{r.IRKT:.0f}</div>'
            f'<div class="titik" style="top:{y(r.IRKT):.0f}px; background:{STATUS[r.level]["warna"]}"></div></div>')
        hari = "Hari ini" if kini else HARI3[r.tanggal.weekday()]
        tanggal.append(f'<div class="t{kls}">{tgl_pendek(r.tanggal)}<small>{hari}</small></div>')

    garis_ambang = ""
    if lo <= ambang <= hi:
        garis_ambang = f'<div class="ambang" style="top:{y(ambang):.0f}px"></div>'
        label_zona.append(f'<span class="merah" style="top:{y(ambang):.0f}px">Batas {ambang:.0f}</span>')
    tulis_html(f"""
    <div class="sg-linimasa">
      <div class="sg-lbl">Prakiraan 15 hari ke depan</div>
      <div class="simpul">{kalimat}</div>
      <div class="sg-plot">
        <div class="area">{"".join(zona)}{garis_ambang}{"".join(kolom)}</div>
        <div class="sisi">{"".join(label_zona)}</div>
        {"".join(tanggal)}<div></div>
      </div>
      {legenda_status()}
    </div>""")


# ----------------------------------------------------------------- grafik
def _sumbu_x(awal, akhir):
    minggu = max(1, math.ceil((akhir - awal).days / 7 / 12))
    bulan = "[" + ",".join(f"'{b}'" for b in BULAN3) + "]"
    return alt.X("tanggal:T", title=None, scale=alt.Scale(domain=[awal.isoformat(), akhir.isoformat()]),
                 axis=alt.Axis(tickCount={"interval": "week", "step": minggu}, labelAngle=0,
                               labelExpr=f"date(datum.value) + ' ' + {bulan}[month(datum.value)]",
                               grid=False, labelColor=TINTA_2, tickColor=GARIS, domainColor=GARIS,
                               labelFontSize=12))


def grafik_irkt(tampil: pd.DataFrame, hari_ini, ambang: float) -> alt.Chart:
    df = tampil[["tanggal", "IRKT", "level", "hujan", "rhmin"]].copy()
    df["Tanggal"] = df.tanggal.map(tgl_panjang)
    df["Tingkat bahaya"] = df.IRKT.round(0).astype(int)
    df["Potensi kebakaran"] = df.level.map(nama_status)
    df["Hujan (mm)"] = df.hujan.round(1)
    df["Kelembapan minimum (%)"] = df.rhmin.round(0)
    awal, akhir = df.tanggal.min(), df.tanggal.max()
    x = _sumbu_x(awal, akhir)
    y = alt.Y("IRKT:Q", title="Tingkat bahaya (0 sampai 100)",
              scale=alt.Scale(domain=[0, 100], nice=False),
              axis=alt.Axis(values=[0, 20, 40, 60, 80, 100], labelColor=TINTA_2, titleColor=TINTA,
                            titleFontSize=13, labelFontSize=12, gridColor="#EEF2F6",
                            domain=False, ticks=False))

    pita = pd.DataFrame({
        "y0": [0, AMBANG_KUNING, AMBANG_ORANYE, ambang],
        "y1": [AMBANG_KUNING, AMBANG_ORANYE, ambang, 100],
        "level": URUTAN})
    pita["warna"] = pita.level.map(lambda k: STATUS[k]["warna"])
    pita["gelap"] = pita.level.map(lambda k: STATUS[k]["gelap"])
    pita["nama"] = pita.level.map(nama_status)
    pita["tengah"] = (pita.y0 + pita.y1) / 2
    pita["tanggal"] = akhir
    lapis_pita = alt.Chart(pita).mark_rect(opacity=0.13).encode(
        y="y0:Q", y2="y1:Q", color=alt.Color("warna:N", scale=None))
    label_pita = alt.Chart(pita).mark_text(align="left", dx=10, fontSize=13, fontWeight="bold").encode(
        x=x, y=alt.Y("tengah:Q"), text="nama:N", color=alt.Color("gelap:N", scale=None))

    riwayat = df[df.tanggal <= hari_ini]
    prakiraan = df[df.tanggal >= hari_ini]
    garis_r = alt.Chart(riwayat).mark_line(color=BIRU, strokeWidth=2.2).encode(x=x, y=y)
    garis_p = alt.Chart(prakiraan).mark_line(color=BIRU, strokeWidth=2.2, strokeDash=[6, 4]).encode(x=x, y=y)

    penanda = pd.DataFrame({"tanggal": [hari_ini], "IRKT": [97], "teks": ["Hari ini"]})
    garis_kini = alt.Chart(penanda).mark_rule(color=TINTA_2, strokeWidth=1.5).encode(x=x)
    label_kini = alt.Chart(penanda).mark_text(align="left", dx=5, fontSize=12, fontWeight="bold",
                                              color=TINTA).encode(x=x, y=y, text="teks:N")

    ab = pd.DataFrame({"IRKT": [ambang], "tanggal": [awal],
                       "teks": [f"Batas potensi sangat tinggi: {ambang:.0f}"]})
    garis_ab = alt.Chart(ab).mark_rule(color=STATUS["MERAH"]["warna"], strokeWidth=1.5,
                                       strokeDash=[3, 3]).encode(y=y)
    label_ab = alt.Chart(ab).mark_text(align="left", dx=6, dy=-8, fontSize=12, fontWeight="bold",
                                       color=STATUS["MERAH"]["gelap"]).encode(x=x, y=y, text="teks:N")

    sorot = alt.selection_point(name="sorot", fields=["tanggal"], nearest=True, on="pointerover",
                                clear="pointerout", empty=False)
    tip = ["Tanggal:N", "Tingkat bahaya:Q", "Potensi kebakaran:N", "Hujan (mm):Q", "Kelembapan minimum (%):Q"]
    pemicu = alt.Chart(df).mark_point(opacity=0, size=200).encode(x=x, y=y, tooltip=tip).add_params(sorot)
    garis_sorot = alt.Chart(df).mark_rule(color=TINTA_3).encode(
        x=x, opacity=alt.condition(sorot, alt.value(0.7), alt.value(0)), tooltip=tip)
    titik = alt.Chart(df).mark_circle(size=70, color=BIRU, stroke="white", strokeWidth=2).encode(
        x=x, y=y, opacity=alt.condition(sorot, alt.value(1), alt.value(0)), tooltip=tip)

    return (alt.layer(lapis_pita, label_pita, garis_ab, label_ab, garis_kini, label_kini,
                      garis_r, garis_p, garis_sorot, pemicu, titik)
            .properties(height=360, padding={"left": 5, "right": 110, "top": 10, "bottom": 5})
            .configure_view(stroke=None))


KOMPONEN = {
    "kbdi_n": (f"Kekeringan timbunan ({W_KERING:.0%})".replace("%", " persen"), "#1B4965"),
    "s_cuaca": (f"Cuaca harian ({W_CUACA:.0%})".replace("%", " persen"), "#62B6CB"),
    "s_satelit": (f"Kondisi termal dari satelit ({W_SAT:.0%})".replace("%", " persen"), "#9C6ADE"),
}


def grafik_komponen(tampil: pd.DataFrame, hari_ini) -> alt.Chart:
    df = tampil[["tanggal", *KOMPONEN]].melt("tanggal", var_name="k", value_name="nilai")
    df["Komponen"] = df.k.map(lambda k: KOMPONEN[k][0])
    df["Skor"] = (df.nilai * 100).round(0)
    df["Tanggal"] = df.tanggal.map(tgl_panjang)
    awal, akhir = tampil.tanggal.min(), tampil.tanggal.max()
    x = _sumbu_x(awal, akhir)
    warna = alt.Color("Komponen:N", scale=alt.Scale(domain=[v[0] for v in KOMPONEN.values()],
                                                    range=[v[1] for v in KOMPONEN.values()]),
                      legend=alt.Legend(orient="bottom", title=None, labelFontSize=13, symbolStrokeWidth=3,
                                        labelLimit=0, columnPadding=24))
    garis = alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=x, y=alt.Y("Skor:Q", title="Skor komponen (0 sampai 100)",
                     scale=alt.Scale(domain=[0, 110], nice=False),
                     axis=alt.Axis(values=[0, 25, 50, 75, 100], labelColor=TINTA_2, titleColor=TINTA,
                                   gridColor="#EEF2F6", domain=False, ticks=False)),
        color=warna, tooltip=["Tanggal:N", "Komponen:N", "Skor:Q"])
    kini = alt.Chart(pd.DataFrame({"tanggal": [hari_ini]})).mark_rule(color=TINTA_2).encode(x=x)
    return alt.layer(kini, garis).properties(height=300).configure_view(stroke=None)


# ----------------------------------------------------------------- tabel
def tabel_prakiraan(depan: pd.DataFrame):
    t = pd.DataFrame({
        "Tanggal": depan.tanggal.map(lambda d: f"{HARI3[d.weekday()]}, {tgl_pendek(d)} {d.year}"),
        "Potensi kebakaran": depan.level.map(lambda k: f"●  {nama_status(k)}"),
        "Tingkat bahaya": depan.IRKT.round(0).astype(int),
        "Hujan (mm)": depan.hujan.round(1),
        "Kelembapan minimum (%)": depan.rhmin.round(0).astype(int),
        "Suhu maksimum (C)": depan.tmax.round(1),
    }).reset_index(drop=True)
    lv = depan.level.tolist()

    def warnai(kolom):
        return [f"color: {STATUS[k]['gelap']}; font-weight: 600" for k in lv]
    gaya = (t.style.apply(warnai, subset=["Potensi kebakaran"])
            .format({"Hujan (mm)": "{:.1f}", "Suhu maksimum (C)": "{:.1f}"}, decimal=","))
    st.dataframe(gaya, hide_index=True, width="stretch", height=38 + 35 * len(t))


# ----------------------------------------------------------------- peta zonasi
_STOP = [(0.0, (44, 160, 44)), (1 / 3, (242, 194, 0)), (2 / 3, (255, 127, 14)), (1.0, (214, 39, 40))]


def _warna_gradasi(t: float) -> list[int]:
    for (a, ca), (b, cb) in zip(_STOP, _STOP[1:]):
        if t <= b:
            f = 0 if b == a else (t - a) / (b - a)
            return [round(ca[i] + f * (cb[i] - ca[i])) for i in range(3)] + [215]
    return list(_STOP[-1][1]) + [215]


def kelas_izr(v: float) -> str:
    return "Sangat tinggi" if v >= 70 else "Tinggi" if v >= 50 else "Sedang" if v >= 30 else "Rendah"


def siapkan_zonasi(zon: pd.DataFrame) -> pd.DataFrame:
    z = zon.dropna(subset=["IZR", "bujur", "lintang"]).copy()
    lo, hi = z.IZR.min(), z.IZR.max()
    z["relatif"] = 0.5 if hi - lo < 1e-9 else (z.IZR - lo) / (hi - lo)
    z["warna"] = z.relatif.map(_warna_gradasi)
    # Sel penuh berukuran 90 m (0,81 ha); sel di tepi TPA terpotong batas sehingga lebih kecil.
    sisi = np.minimum(90.0, np.sqrt(z.luas_ha.fillna(0.81).clip(lower=0.01) * 1e4)) / 2
    dlat = sisi / 111_320
    dlon = sisi / (111_320 * np.cos(np.radians(z.lintang)))
    z["poligon"] = [[[x - a, y - b], [x + a, y - b], [x + a, y + b], [x - a, y + b]]
                    for x, y, a, b in zip(z.bujur, z.lintang, dlon, dlat)]
    z["izr_teks"] = z.IZR.map(lambda v: angka(v, 1))
    z["kelas"] = z.IZR.map(kelas_izr)
    z["koord"] = [f"{y:.5f}, {x:.5f}" for x, y in zip(z.bujur, z.lintang)]
    return z


def peta_zonasi(z: pd.DataFrame) -> pdk.Deck:
    lat, lon = z.lintang.mean(), z.bujur.mean()
    bentang = max((z.lintang.max() - z.lintang.min()) * 111_320,
                  (z.bujur.max() - z.bujur.min()) * 111_320 * math.cos(math.radians(lat)), 150) + 250
    # deck.gl memakai ubin 512 piksel: satu piksel pada zoom z = 78 271 * cos(lintang) / 2^z meter
    zoom = float(np.clip(math.log2(78_271 * math.cos(math.radians(lat)) * 480 / bentang), 14, 17))
    r = 0.02
    citra = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
             f"?bbox={lon - r},{lat - r},{lon + r},{lat + r}&bboxSR=4326&imageSR=4326"
             "&size=2048,2048&format=jpg&f=image")
    lapis_citra = pdk.Layer("BitmapLayer", image=citra, bounds=[lon - r, lat - r, lon + r, lat + r])
    lapis_sel = pdk.Layer(
        "PolygonLayer", data=z[["poligon", "warna", "izr_teks", "kelas", "koord"]],
        get_polygon="poligon", get_fill_color="warna", get_line_color=[255, 255, 255, 230],
        line_width_min_pixels=1, stroked=True, filled=True, pickable=True, auto_highlight=True,
        highlight_color=[27, 73, 101, 160])
    tooltip = {"html": "<b>Indeks Zonasi Risiko: {izr_teks}</b><br/>Kelas: {kelas}<br/>"
                       "Koordinat: {koord}",
               "style": {"backgroundColor": "#FFFFFF", "color": TINTA, "fontSize": "13px",
                         "border": f"1px solid {GARIS}", "borderRadius": "6px"}}
    return pdk.Deck(layers=[lapis_citra, lapis_sel], tooltip=tooltip, map_style=None,
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom))


def legenda_zonasi(z: pd.DataFrame):
    tulis_html(f"""
    <div style="max-width:520px; margin-top:6px;">
      <div style="font-size:13px; font-weight:600; color:{TINTA};">Warna sel: Indeks Zonasi Risiko, dibandingkan antarsel di TPA ini</div>
      <div class="sg-gradasi"></div>
      <div class="sg-gradasi-lbl"><span>Paling rendah ({angka(z.IZR.min(), 1)})</span>
        <span>Paling tinggi ({angka(z.IZR.max(), 1)})</span></div>
    </div>""")


def tabel_prioritas(z: pd.DataFrame):
    t = z.sort_values("IZR", ascending=False).head(10).reset_index(drop=True)
    tabel = pd.DataFrame({
        "Peringkat": range(1, len(t) + 1),
        "Indeks Zonasi Risiko": t.IZR.round(1),
        "Kelas": t.kelas,
        "Lintang": t.lintang.round(5),
        "Bujur": t.bujur.round(5),
        "Luas (ha)": t.luas_ha.round(2),
        "Lokasi": [f"https://www.google.com/maps?q={a:.6f},{b:.6f}" for a, b in zip(t.lintang, t.bujur)],
    })
    st.dataframe(tabel, hide_index=True, width="stretch", column_config={
        "Indeks Zonasi Risiko": st.column_config.ProgressColumn(
            "Indeks Zonasi Risiko", min_value=0, max_value=100, format="%.1f"),
        "Lintang": st.column_config.NumberColumn(format="%.5f"),
        "Bujur": st.column_config.NumberColumn(format="%.5f"),
        "Lokasi": st.column_config.LinkColumn("Lokasi", display_text="Buka peta"),
    })
