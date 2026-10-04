/*********************************************************************
 * Landsat 30 m memakai tiga lapis informasi:
 *   1. Anomali panas rata-rata kemarau terhadap keseluruhan TPA
 *   2. Persistensi, yaitu berapa persen citra memperlihatkan piksel itu panas
 *   3. Tren pemanasan antar-tahun (derajat C per tahun)
 * Ketiganya digabung menjadi Indeks Zonasi Risiko (IZR, 0-100).
 *
 * KELUARAN
 *   - Peta zonasi 4 kelas, siap dijadikan gambar di naskah
 *   - Tabel peringkat sel 90 m (CSV) untuk prioritas patroli dan penyiraman
 *   - GeoTIFF IZR untuk diolah lebih lanjut di QGIS
 *
 * CARA PAKAI
 * 1. Gambar poligon batas timbunan sampah (nama default: geometry).
 * 2. Isi NAMA_TPA dan TAHUN_KEBAKARAN di bawah.
 * 3. Run, lalu jalankan tugas di tab Tasks.
 *********************************************************************/

// ===================== PENGATURAN =====================
var NAMA_TPA = 'Jatiwaringin';
var TAHUN_KEBAKARAN = [2026];     // tahun dengan kebakaran, dikeluarkan dari baseline
var MULAI = '2019-01-01';
var SELESAI = '2026-12-31';
var BULAN_KEMARAU = [6, 10];      // Juni sampai Oktober
var SEL_METER = 90;               // ukuran sel peringkat zona

// koordinat TPA (sama dengan sigap/config.py), untuk memeriksa letak poligon
var TITIK_TPA = {
  Sarimukti: [107.3512, -6.7989], Jatiwaringin: [106.5433, -6.1020],
  RawaKucing: [106.6183, -6.1373], Suwung: [115.2225, -8.7207], Pakusari: [113.7617, -8.1697]
};

if (typeof geometry === 'undefined') {
  print('BELUM ADA POLIGON. Gambar batas timbunan sampah lalu Run lagi.');
} else if (geometry.distance(ee.Geometry.Point(TITIK_TPA[NAMA_TPA]), 1).getInfo() > 2000) {
  print('POLIGON TIDAK BERADA DI TPA ' + NAMA_TPA + '. Hapus poligon lama, gambar ulang di lokasi yang benar, lalu Run lagi.');
} else {
  var tpa = geometry;
  print('Luas TPA (ha):', tpa.area(1).divide(1e4));

  // ===================== KOLEKSI LANDSAT =====================
  function prep(img) {
    var qa = img.select('QA_PIXEL');
    var clear = qa.bitwiseAnd(1 << 1).eq(0).and(qa.bitwiseAnd(1 << 3).eq(0))
      .and(qa.bitwiseAnd(1 << 4).eq(0)).and(img.select('ST_B10').gt(0));
    var lst = img.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).rename('LST');
    return lst.updateMask(clear)
      .set('system:time_start', img.get('system:time_start'))
      .set('tahun', ee.Date(img.get('system:time_start')).get('year'));
  }

  var semua = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
    .filterBounds(tpa).filterDate(MULAI, SELESAI).map(prep)
    .filter(ee.Filter.calendarRange(BULAN_KEMARAU[0], BULAN_KEMARAU[1], 'month'));

  // citra kemarau di luar tahun kebakaran, untuk menyusun kondisi dasar
  var dasar = semua.filter(ee.Filter.inList('tahun', TAHUN_KEBAKARAN).not());
  print('Jumlah citra kemarau seluruhnya:', semua.size(), '| tanpa tahun kebakaran:', dasar.size());

  // ===================== 1. ANOMALI PANAS PER PIKSEL =====================
  // Tiap citra dinormalkan terhadap rata-rata TPA pada citra itu sendiri,
  // sehingga perbedaan cuaca antar-tanggal tidak memengaruhi hasil.
  function relatif(img) {
    var rata = ee.Number(img.reduceRegion({
      reducer: ee.Reducer.mean(), geometry: tpa, scale: 30, maxPixels: 1e9
    }).get('LST'));
    return img.subtract(ee.Image.constant(rata)).rename('dLST')
      .copyProperties(img, ['system:time_start', 'tahun']);
  }
  var rel = dasar.map(relatif);
  var anomali = rel.mean().rename('anomali').clip(tpa);

  // ===================== 2. PERSISTENSI =====================
  // Persentase citra yang memperlihatkan piksel ini lebih panas 2 derajat C
  // dari rata-rata TPA pada tanggal yang sama.
  var panas = rel.map(function (i) { return ee.Image(i).gt(2).rename('panas'); });
  var persistensi = panas.mean().multiply(100).rename('persistensi').clip(tpa);

  // ===================== 3. TREN ANTAR-TAHUN =====================
  var denganWaktu = rel.map(function (i) {
    var t = ee.Image(ee.Number(ee.Date(ee.Image(i).get('system:time_start')).difference(
      ee.Date(MULAI), 'year'))).float().rename('t');
    return t.addBands(ee.Image(i)).set('system:time_start', ee.Image(i).get('system:time_start'));
  });
  var tren = denganWaktu.select(['t', 'dLST']).reduce(ee.Reducer.linearFit())
    .select('scale').rename('tren').clip(tpa);   // derajat C per tahun

  // ===================== INDEKS ZONASI RISIKO (IZR) =====================
  function skala(img, lo, hi) {
    return img.subtract(lo).divide(hi - lo).clamp(0, 1);
  }
  var izr = skala(anomali, 0, 6).multiply(0.45)
    .add(skala(persistensi, 0, 60).multiply(0.35))
    .add(skala(tren, 0, 0.6).multiply(0.20))
    .multiply(100).rename('IZR').clip(tpa);

  var kelas = izr.expression(
    "b('IZR') >= 70 ? 4 : b('IZR') >= 50 ? 3 : b('IZR') >= 30 ? 2 : 1").rename('kelas').clip(tpa);

  // ===================== PETA =====================
  Map.centerObject(tpa, 16);
  Map.setOptions('SATELLITE');
  var visAnom = { min: -3, max: 6, palette: ['0000ff', '00ffff', 'ffff00', 'ff8800', 'ff0000'] };
  Map.addLayer(anomali, visAnom, '1. Anomali panas rata-rata (derajat C)', false);
  Map.addLayer(persistensi, { min: 0, max: 60, palette: ['ffffff', 'ffcc00', 'ff3300'] }, '2. Persistensi (%)', false);
  Map.addLayer(tren, { min: -0.5, max: 0.5, palette: ['0000ff', 'ffffff', 'ff0000'] }, '3. Tren (derajat C/tahun)', false);
  Map.addLayer(kelas, { min: 1, max: 4, palette: ['2ca02c', 'f2c200', 'ff7f0e', 'd62728'] },
    'ZONASI RISIKO (hijau-kuning-oranye-merah)');
  Map.addLayer(ee.FeatureCollection([ee.Feature(tpa)]).style({ color: 'ffffff', fillColor: '00000000', width: 2 }),
    {}, 'Batas TPA');

  // ===================== RINGKASAN LUAS TIAP KELAS =====================
  var luas = ee.Image.pixelArea().divide(1e4).addBands(kelas).reduceRegion({
    reducer: ee.Reducer.sum().group({ groupField: 1, groupName: 'kelas' }),
    geometry: tpa, scale: 30, maxPixels: 1e9
  });
  print('Luas tiap kelas zonasi (ha), kelas 1 rendah s.d. 4 tinggi:', luas);

  // ===================== PERINGKAT SEL UNTUK PATROLI =====================
  var sel = izr.addBands(kelas).reduceResolution({ reducer: ee.Reducer.mean(), maxPixels: 256 })
    .reproject({ crs: 'EPSG:4326', scale: SEL_METER });
  // reduceToVectors memakai band pertama sebagai label segmen dan hanya mereduksi
  // band sesudahnya, jadi band pertama berupa nomor unik tiap sel 90 m dan IZR di band kedua.
  var xy = ee.Image.pixelCoordinates(sel.projection()).floor();
  var idSel = xy.select('x').multiply(1e6).add(xy.select('y')).toInt64().rename('id');
  var vektor = idSel.addBands(sel.select('IZR')).reduceToVectors({
    geometry: tpa, crs: sel.projection(), scale: SEL_METER, geometryType: 'polygon',
    reducer: ee.Reducer.mean(), labelProperty: 'zona', maxPixels: 1e9
  })
    .map(function (f) {
      var c = f.geometry().centroid(1).coordinates();
      return f.set({
        IZR: f.get('mean'), bujur: c.get(0), lintang: c.get(1),
        luas_ha: f.geometry().area(1).divide(1e4)
      });
    }).sort('IZR', false);
  print('10 sel paling berisiko:', vektor.limit(10));
  Map.addLayer(vektor.limit(10).style({ color: 'ff00ff', fillColor: '00000000', width: 2 }),
    {}, '10 sel prioritas patroli');

  // ===================== EKSPOR =====================
  Export.table.toDrive({
    collection: vektor, description: 'SIGAP_ZONASI_' + NAMA_TPA + '_sel', fileFormat: 'CSV',
    selectors: ['IZR', 'bujur', 'lintang', 'luas_ha']
  });

  Export.image.toDrive({
    image: izr.addBands(anomali).addBands(persistensi).addBands(tren).toFloat(),
    description: 'SIGAP_ZONASI_' + NAMA_TPA + '_raster', region: tpa, scale: 30,
    crs: 'EPSG:4326', maxPixels: 1e9, fileFormat: 'GeoTIFF'
  });

  print('Buka tab Tasks untuk mengunduh CSV sel dan GeoTIFF zonasi.');
}
