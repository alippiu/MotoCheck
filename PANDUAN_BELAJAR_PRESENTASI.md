# Panduan Belajar dan Presentasi MotoCheck V2

Panduan ini menjelaskan **kode yang benar-benar ada** di workspace MotoCheck. Aplikasi memakai aturan penyaringan awal, bukan AI dan bukan alat diagnosis bengkel. Baca batasan dan keselamatan sebelum menyampaikan contoh hasil.

## 1. Ringkasan cepat

MotoCheck adalah aplikasi web Python Flask untuk membantu pemilik motor mencatat gejala, melihat beberapa area yang mungkin perlu diperiksa, dan menentukan langkah aman berikutnya. Pengguna memilih kendaraan, gejala, serta jawaban kondisi tambahan. Aplikasi mencocokkan masukan tersebut dengan aturan yang tersimpan di JSON dan menampilkan laporan awal.

Fakta dari source saat panduan ini diperiksa:

- Python: **3.13.5**
- Flask: **3.1.3**
- Requests: **2.34.2**
- pytest: **9.2.0**
- **31** gejala dalam **5** kelompok.
- **11** aturan diagnosis; semuanya `general_guide`, dan **0** yang berstatus `external_verified`.
- **24** gejala tercantum pada setidaknya satu aturan; **7** belum tercakup aturan analisis.
- Katalog: **5** entri model dan **13** varian. Ini bukan berarti seluruh konfigurasi setiap varian sudah diketahui.
- Tes otomatis yang dijalankan untuk panduan ini: **30 passed, 81 subtests passed**.
- Uji langsung pencarian bengkel saat panduan ini diperiksa: **gagal**; aplikasi melaporkan penyedia OpenStreetMap tidak dapat dihubungi. Ini bukan hasil pengujian mock.

**Kalimat kunci saat presentasi:** “MotoCheck membantu pemeriksaan awal dan edukasi. Hasilnya bukan kepastian kerusakan, dan aturan diagnosis saat ini adalah panduan umum yang belum divalidasi terhadap manual pabrikan.”

## 2. Struktur project

| Bagian | Isi dan perannya |
|---|---|
| [`app.py`](./app.py) | Membuat Flask app, route halaman, validasi formulir, dan menghubungkan modul-modul. |
| [`motocheck/catalog.py`](./motocheck/catalog.py) | Memuat data katalog JSON dan membangun identitas/configuration kendaraan yang membedakan sumber resmi dengan isian pengguna. |
| [`motocheck/diagnosis.py`](./motocheck/diagnosis.py) | Memvalidasi relasi aturan-sumber, mendefinisikan pertanyaan dan keselamatan, mencocokkan aturan, mengurutkan kandidat, dan membuat ringkasan. |
| [`motocheck/knowledge.py`](./motocheck/knowledge.py) | Mencari artikel pengetahuan berdasarkan kata kunci dan kategori. |
| [`motocheck/workshops.py`](./motocheck/workshops.py) | Menghubungi Overpass API dengan Requests, memeriksa data tempat, mengurutkan jarak, dan menyimpan cache singkat. |
| [`motocheck/data/vehicles.json`](./motocheck/data/vehicles.json) | Pilihan merek, model, varian, pilihan konfigurasi, dan catatan sumber. |
| [`motocheck/data/symptoms.json`](./motocheck/data/symptoms.json) | 31 pilihan gejala dan kelompoknya. |
| [`motocheck/data/rules.json`](./motocheck/data/rules.json) | Sebelas aturan penyaringan awal. |
| [`motocheck/data/sources.json`](./motocheck/data/sources.json) | Metadata sumber yang dirujuk katalog dan aturan. |
| [`motocheck/data/knowledge.json`](./motocheck/data/knowledge.json) | Artikel singkat untuk halaman pengetahuan. |
| [`templates/`](./templates) | HTML/Jinja untuk beranda dan wizard, hasil, pengetahuan, serta pencari bengkel. |
| [`static/css/style.css`](./static/css/style.css) | Tema, tata letak, breakpoint layar, aksesibilitas fokus, reduced motion, dan cetak. |
| [`static/js/wizard.js`](./static/js/wizard.js) | Interaksi bertahap pada wizard sisi browser. |
| [`static/js/workshops.js`](./static/js/workshops.js) | Izin lokasi, permintaan pencarian, hasil/peta, serta tautan fallback Google Maps. |
| [`static/images/garage-bike.svg`](./static/images/garage-bike.svg) | Ilustrasi motor vektor lokal yang disertakan dalam project. |
| [`tests/test_app.py`](./tests/test_app.py) | Tes route, katalog, aturan, keselamatan, validasi, dan Workshop Finder. |
| [`requirements.txt`](./requirements.txt) | Flask, Requests, dan pytest dengan versi yang dipatok. |

Project ini tidak menggunakan database. Data disimpan dalam file JSON. Folder `.venv/`, `__pycache__/`, dan cache pytest adalah alat/runtime, bukan fitur aplikasi; `.venv/` dan `__pycache__/` sudah masuk `.gitignore`.

## 3. Cara menjalankan dan menguji

Buka PowerShell di `E:\Projects\MotoCheck`.

**Menjalankan aplikasi lokal:**

```powershell
.\.venv\Scripts\python.exe app.py
```

Kemudian buka `http://127.0.0.1:5000`. Server berjalan dengan `debug=True` dan hanya bind ke `127.0.0.1` pada source saat ini. Mode debug hanya untuk pengembangan lokal, bukan server publik.

**Menjalankan tes otomatis:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Hasil yang baru dijalankan saat membuat panduan:

```text
30 passed, 81 subtests passed in 1.19s
```

Tes memakai `unittest.TestCase` yang ditemukan pytest. Tes Workshop Finder memakai respons tiruan untuk sebagian besar kasus jaringan; tes itu memeriksa perilaku kode ketika menerima respons/error tertentu, **bukan** bukti bahwa layanan live tersedia.

## 4. Alur aplikasi dari browser sampai hasil

1. Browser meminta halaman utama dengan `GET /`.
2. Flask memanggil `_render_home`, memuat data untuk template, lalu Jinja merender `templates/index.html`.
3. Pengguna memilih kendaraan dan gejala. `wizard.js` mengatur langkah, validasi sisi browser, pencarian gejala, dan pertanyaan yang ditampilkan.
4. Form dikirim sebagai `POST /periksa`. `request.form` membawa input ke Flask.
5. Backend memeriksa gejala, gejala utama, kendaraan, konfigurasi, dan jawaban. Input yang tidak valid membuat halaman beranda dirender kembali dengan pesan dan status HTTP 400.
6. Untuk input yang lolos validasi, backend memanggil `diagnose(...)` dan menampilkan `templates/hasil.html`.
7. Halaman lain memakai route `GET /pengetahuan`, `GET /bengkel`, serta `POST /api/bengkel` untuk permintaan data tempat.

Route dan validasinya dapat ditelusuri di [`app.py`](./app.py#L51)–[`app.py`](./app.py#L185). Route pemeriksaan utama ada di [`periksa`](./app.py#L74).

## 5. Python dan library yang digunakan

### Flask

Flask menangani server HTTP dan route. `@app.route("/")` menghubungkan permintaan GET beranda ke fungsi `home()`. `render_template(...)` mengirim data Python ke template HTML. `jsonify(...)` mengirim respons JSON untuk endpoint API.

Contoh ringkas yang mencerminkan route sebenarnya di [`app.py`](./app.py#L74):

```python
@app.route("/periksa", methods=["POST"])
def periksa():
    form = request.form
    selected_ids = form.getlist("symptoms")
    # Backend memvalidasi data sebelum menjalankan aturan.
    ...
```

Form menggunakan `getlist` karena pengguna boleh memilih beberapa checkbox gejala. Python tetap memeriksa input; validasi JavaScript di browser saja tidak cukup.

### Requests

`requests` digunakan oleh [`motocheck/workshops.py`](./motocheck/workshops.py#L161) untuk mengirim query HTTPS ke Overpass. Implementasi memakai `verify=True`, timeout `(3, 8)`, dua percobaan untuk beberapa kegagalan sementara, dan menerjemahkan kegagalan menjadi pesan yang bisa ditangani route Flask. TLS tidak dinonaktifkan.

### pytest

pytest menjalankan suite yang tersedia. Suite tersebut memuat tes unit/integrasi Flask serta mock HTTP. Menjalankan pytest tidak otomatis melakukan uji browser atau menjamin koneksi internet.

### Pustaka standar Python

Project juga menggunakan pustaka bawaan Python—tidak perlu instalasi terpisah—misalnya `json` dan `pathlib` untuk data JSON, `re` untuk validasi, `math` untuk jarak, serta `threading` dan `time` untuk cache.

Leaflet dan peta tile OpenStreetMap digunakan pada sisi web. Leaflet bukan library Python; template bengkel merujuk aset Leaflet dari CDN eksternal, sehingga peta perlu koneksi jaringan.

## 6. Katalog motor dan batas verifikasi

Katalog menyediakan merek Honda, Yamaha, Suzuki, Kawasaki, dan pilihan lain/tidak diketahui. Saat diperiksa, ada 5 entri model dan 13 varian. Pilihan konfigurasi mencakup kategori bodi, transmisi, bahan bakar, pendinginan, penggerak akhir, ABS, serta tipe rem depan/belakang.

`build_vehicle(...)` di [`catalog.py`](./motocheck/catalog.py#L72) memeriksa merek-model-varian yang sesuai, nilai pilihan, serta format tahun. Konfigurasi dari katalog menimpa masukan pengguna untuk field yang memang dinyatakan sumber katalog. Untuk konfigurasi yang tidak tersedia, nilainya tetap belum diketahui atau ditandai sebagai isian pengguna. Tahun tidak boleh diasumsikan hanya dari nama model.

Contoh batasan yang perlu dijelaskan:

- Katalog bisa mengenali model/varian tanpa mengetahui semua spesifikasi teknisnya.
- Halaman produk yang mencantumkan model atau fitur bukan bukti troubleshooting.
- Tahun yang ditulis pengguna tidak otomatis menjadi tahun terverifikasi.
- Manual Honda MotoPub yang tercatat dalam `sources.json` adalah portal/identitas entri model; isi manual belum menjadi bukti aturan diagnosis.
- Lima model katalog bukan klaim bahwa model itu mencakup semua motor populer.

## 7. Bagaimana rule-based diagnosis bekerja

Aturan tersimpan sebagai daftar objek JSON dalam [`rules.json`](./motocheck/data/rules.json). Satu aturan umumnya memiliki ID, status bukti, gejala pendukung, kondisi/jawaban yang relevan, batas konfigurasi, kandidat, alasan, sistem yang perlu dilihat, pemeriksaan aman, urgensi, sumber, dan saran bengkel.

Urutan proses dalam [`diagnose`](./motocheck/diagnosis.py#L223):

1. Memastikan gejala dan jawaban tersedia.
2. Mencari irisan antara gejala yang dipilih dengan gejala pada setiap aturan.
3. Menolak aturan yang tidak cocok dengan konfigurasi kendaraan. Jika aturan membutuhkan CVT, transmisi yang diketahui sebagai manual tidak akan memenuhi aturan CVT.
4. Jika ada aturan `external_verified`, membatasi penerapannya pada model **dan tahun** yang tercantum dalam cakupan; aturan eksternal tidak boleh berlaku untuk kendaraan yang hanya mirip.
5. Membuat urutan heuristik: tiap gejala yang cocok memberi skor internal, lalu jawaban selaras memperkuat urutan dan jawaban yang tidak selaras melemahkannya.
6. Menampilkan alasan kecocokan, kondisi yang belum dijawab, sumber, status bukti, urgensi, dan kandidat.

Potongan inti yang disederhanakan, sesuai kode:

```python
matched_symptoms = selected_symptoms.intersection(rule["symptoms"])
if not matched_symptoms:
    return None

rank = len(matched_symptoms) * 3
# Jawaban kondisi yang cocok menambah urutan; yang tidak cocok menguranginya.
```

Angka tersebut hanya mekanisme pengurutan internal. **Bukan probabilitas dan bukan persentase akurasi.**

### Contoh dua input yang benar-benar dijalankan

Kedua contoh memilih “Motor sulit dihidupkan” dan memakai kendaraan yang konfigurasi modelnya tidak diketahui:

| Jawaban lanjutan | Kandidat teratas | Kandidat berikutnya |
|---|---|---|
| Starter lemah + lampu/klakson ikut melemah | Aki atau rangkaian starter perlu diperiksa | Sistem bahan bakar atau pengapian perlu pemeriksaan |
| Starter berputar normal + tidak ada indikator/perangkat listrik melemah | Sistem bahan bakar atau pengapian perlu pemeriksaan | Aki atau rangkaian starter perlu diperiksa |

Keluaran runtime mencatat urutan rule masing-masing `start_battery` lalu `start_fuel_ignition`, dan sebaliknya. Ini membuktikan jawaban dapat mengubah **urutan panduan**, bukan membuktikan penyebab sebenarnya.

### Bukti aturan saat ini

- Aturan eksternal yang tervalidasi dari troubleshooting manual pabrikan: **0**.
- Aturan panduan umum (`general_guide`): **11**.
- Cakupan aturan: **24** gejala dari 31.
- Gejala tanpa aturan analisis memadai: **7**.

Aturan keselamatan juga bukan bukti penyebab mekanis. Misalnya, aturan dapat menyuruh berhenti berkendara demi kehati-hatian tanpa mengklaim tahu komponen apa yang rusak. Di halaman hasil, bedakan “Panduan umum” dan “Bukti belum cukup” dari hasil yang benar-benar didukung sumber teknis. Pada project saat ini, tidak ada kandidat eksternal yang benar-benar tervalidasi.

## 8. Peringatan keselamatan

`SAFETY_SYMPTOMS` di [`diagnosis.py`](./motocheck/diagnosis.py#L170) mengatur urgensi berhenti untuk gejala berisiko. Termasuk rem, kemudi, kondisi ban tertentu, overheat/kebocoran pendingin/oli, dan kebocoran bahan bakar. Halaman hasil meminta pengguna untuk tidak mengendarai motor yang berstatus “Jangan Dikendarai”; untuk bahan bakar, instruksi juga menghindari menyalakan motor dan sumber api. Mesin harus didinginkan sebelum pemeriksaan; jangan membongkar mesin panas atau membuka tutup radiator saat panas.

Saat demo, jangan melakukan uji rem, uji kestabilan, membuka komponen, atau menyentuh bagian bergerak. Jelaskan hanya teks keselamatan yang ditampilkan aplikasi.

## 9. Workshop Finder: fungsi dan status live

Alur pengguna dimulai setelah menekan “Gunakan Lokasi Saya”, lalu browser meminta izin. Koordinat dikirim ke `/api/bengkel`. Backend mengirim query Overpass, memeriksa elemen/tagnya, alamat, koordinat, URL dan nomor telepon, membatasi hasil sampai radius 5 km, mengurutkan jarak garis lurus, dan memakai cache singkat. Kode utama ada di [`workshops.py`](./motocheck/workshops.py#L21) dan [`find_workshops`](./motocheck/workshops.py#L239); sisi browser ada di [`workshops.js`](./static/js/workshops.js#L117).

Jika pencarian gagal atau tidak menemukan data, halaman menyediakan pencarian kota/area di Google Maps. Fallback tersebut hanya membuat tautan pencarian; MotoCheck tidak mengarang nama bengkel, rating, layanan khusus, atau nomor kontak.

**Status uji live pada sesi pembuatan panduan:** percobaan sungguhan ke `find_workshops` menggunakan koordinat umum pusat Jakarta gagal. Kode mengembalikan “Penyedia data OpenStreetMap tidak dapat dihubungi saat ini.” Dengan demikian pencarian live **belum berhasil diverifikasi pada percobaan ini**. Hasil ini tidak membuktikan penyedia selalu tidak tersedia dan tidak cukup untuk menyimpulkan apakah akar masalahnya jaringan lokal, timeout, atau layanan.

Tes mock tetap lulus untuk parsing data OSM, filter radius, cache, error HTTP, dan verifikasi TLS. Nyatakan sebagai dua hasil terpisah:

- **Otomatis/mock:** perilaku yang diprogram diuji dengan respons tiruan.
- **Live:** gagal di percobaan jaringan nyata ini; gunakan fallback Google Maps bila layanan tidak tersedia.

## 10. HTML, CSS, dan JavaScript

### HTML dan Jinja

Template memakai HTML semantik seperti `<header>`, `<nav>`, `<main>`, `<section>`, `<form>`, `<label>`, dan `<fieldset>`. Jinja mengisi pilihan dari Python:

- `{{ ... }}` menampilkan nilai, dengan escaping otomatis pada output HTML standar.
- `{% for ... %}` mengulang data seperti gejala dan model.
- `{% if ... %}` memilih konten bersyarat.
- `url_for('static', filename='...')` membangun URL aset; ini lebih aman dari menulis jalur aset manual.

Form wizard dan 3 langkahnya ada di [`index.html`](./templates/index.html#L107). Ringkasan kandidat dan sumber ada di [`hasil.html`](./templates/hasil.html#L25). Pencarian bengkel ada di [`workshops.html`](./templates/workshops.html#L28).

### CSS

[`style.css`](./static/css/style.css) memakai variabel warna graphite/merah, tipografi tegas, hero ilustrasi, dan layout grid. Media query mengatur tampilan desktop hingga mobile; beberapa breakpoint utamanya berada sekitar 900, 640, dan 390 px. Aturan `prefers-reduced-motion` mengurangi animasi ketika pengguna mengaktifkan preferensi tersebut. Ada pula aturan cetak untuk laporan.

Ilustrasi lokal `garage-bike.svg` adalah vektor yang disertakan di project, bukan foto pabrikan atau logo MotoGP.

### JavaScript wizard

[`wizard.js`](./static/js/wizard.js#L191) memeriksa kelengkapan kendaraan dan jumlah gejala. Fungsi `showStep` mengubah langkah aktif, label/progress, dan fokus ke heading langkah. Event tombol Lanjut/Kembali berpindah langkah; checkbox yang dipilih memutakhirkan pilihan gejala utama serta pertanyaan relevan.

Penting: validasi JavaScript membantu pengalaman pengguna, tetapi Flask tetap melakukan validasi ulang di server.

### JavaScript Workshop Finder

[`workshops.js`](./static/js/workshops.js#L117) memanggil geolocation setelah klik pengguna, lalu mengirim permintaan ke backend. Tautan dibangun melalui URL API browser dan diisi `textContent` untuk menjaga data provider tetap sebagai teks, bukan HTML mentah. Fungsi fallback Google Maps tersedia untuk pencarian berdasarkan koordinat atau area.

## 11. Hasil pengujian dan batasnya

Tes yang **benar-benar dijalankan** untuk panduan ini: `30 passed, 81 subtests passed`.

Suite mencakup halaman/aset, validasi katalog, seluruh varian katalog, asal konfigurasi, relasi sumber aturan, hasil yang berubah dengan jawaban, gejala tanpa dukungan, input invalid, peringatan keselamatan, pencarian pengetahuan, serta mock Workshop Finder. Rincian ada di [`test_app.py`](./tests/test_app.py#L74).

Batas pengujian:

- Tes otomatis tidak membuktikan akurasi mekanis.
- Tes Workshop Finder yang memakai mock tidak menguji layanan live; satu uji live yang dijalankan untuk panduan ini gagal seperti dijelaskan di atas.
- Pengujian browser dan screenshot sebelumnya merupakan QA tahap UI, bukan pengujian browser yang diulang saat membuat panduan ini. Pada tahap sebelumnya alur wizard diklik normal dan ukuran 1920, 1366, 768, 390, serta 360 px diperiksa untuk overflow. Screenshot tersedia, misalnya [sebelum](./screenshots/before-home-desktop.png) dan [sesudah](./screenshots/after-home-desktop-1366.png).
- Tes tidak memeriksa kendaraan fisik, tidak menggantikan teknisi, dan tidak mengukur sensitivitas/spesifisitas atau akurasi diagnosis.

## 12. Naskah presentasi sekitar lima menit

**Pembukaan (30 detik)**  
“Halo, saya akan mempresentasikan MotoCheck V2, aplikasi web Python Flask untuk pemeriksaan awal gejala sepeda motor. Tujuannya membantu pengguna mencatat keluhan dan mendapatkan arahan pemeriksaan yang aman, bukan menentukan kerusakan pasti.”

**Masalah dan tujuan (40 detik)**  
“Pemilik motor sering kesulitan menjelaskan keluhan atau menentukan area yang perlu diperiksa. MotoCheck mengelompokkan 31 gejala, menerima beberapa keluhan sekaligus, lalu menampilkan alasan kandidat, tindakan aman, urgensi, dan keterbatasan bukti.”

**Cara kerja (1 menit)**  
“Frontend mengirim formulir ke route Flask. Backend memvalidasi kendaraan, gejala, gejala utama, dan jawaban lanjutan. Mesin diagnosis membaca 11 aturan dari JSON, mencocokkan gejala serta konfigurasi, lalu mengurutkan kandidat memakai skor heuristik. Skor itu hanya urutan, bukan persentase akurasi.”

**Demo singkat (1 menit 30 detik)**  
“Saya memilih model lain/tidak diketahui agar tidak menganggap spesifikasi yang belum terverifikasi sebagai fakta. Saya pilih gejala sulit dihidupkan dan jawab starter lemah serta perangkat listrik ikut melemah. Kandidat aki/rangkaian starter muncul lebih dulu. Jika jawaban diubah menjadi starter normal dan tidak ada perangkat yang melemah, kandidat bahan bakar/pengapian berpindah ke urutan pertama. Keduanya tetap dugaan awal dan perlu pemeriksaan langsung.”

**Fitur pendukung dan keselamatan (45 detik)**  
“Halaman pengetahuan memberi penjelasan dasar. Workshop Finder meminta izin lokasi setelah tombol ditekan, mencari data yang dipetakan, dan punya fallback Google Maps. Jika gejala berbahaya seperti rem bermasalah atau kebocoran bahan bakar muncul, hasil meminta pengguna berhenti menggunakan motor.”

**Kejujuran data dan penutup (35 detik)**  
“Semua 11 aturan diagnosis saat ini adalah panduan umum; belum ada aturan yang tervalidasi dari isi troubleshooting manual pabrikan. Ada 7 gejala yang belum memiliki aturan analisis memadai. Tes otomatis lulus, tetapi tes bukan bukti akurasi mekanis. Pengembangan berikutnya perlu meninjau manual model/tahun secara langsung dan menguji aplikasi dengan mekanik serta pengguna.”

## 13. Urutan demonstrasi langsung

1. Buka `http://127.0.0.1:5000`; tunjukkan beranda dan jelaskan hasil bukan diagnosis pasti.
2. Tekan “Mulai Pemeriksaan”.
3. Pilih merek dan “Model lain / tidak diketahui” (atau model katalog tanpa menyatakan konfigurasi yang tidak tersedia).
4. Tekan **Lanjut** secara normal.
5. Cari dan pilih “Motor sulit dihidupkan”; jadikan itu gejala utama.
6. Tekan **Lanjut**; jawab starter lemah dan perangkat listrik ikut melemah.
7. Tekan **Analisis Gejala**. Tunjukkan alasan kandidat, status “Panduan umum”, keterbatasan bukti, dan urgensi.
8. Ulangi dengan jawaban starter normal/tidak ada pelemahan listrik untuk membandingkan urutan kandidat.
9. Jika waktu cukup, tunjukkan halaman pengetahuan. Workshop Finder bisa didemokan tanpa izin lokasi melalui pencarian area; jika menunjukkan live finder, katakan bahwa uji live terakhir belum berhasil dan tunjukkan fallback, bukan hasil bengkel buatan.
10. Jangan memakai gejala darurat untuk simulasi berkendara. Jika memperagakan keselamatan, cukup bacakan pesan dan tegaskan motor tidak boleh dikendarai.

## 14. Tanya-jawab latihan

1. **Apa itu MotoCheck?**  
   Aplikasi Flask untuk pemeriksaan awal gejala sepeda motor dan edukasi langkah aman.

2. **Apakah aplikasi memastikan komponen rusak?**  
   Tidak. Aplikasi menampilkan kemungkinan area pemeriksaan; pemeriksaan langsung tetap diperlukan.

3. **Apa arti rule-based?**  
   Program mencocokkan input dengan aturan yang ditulis sebelumnya, bukan mempelajari pola dari dataset.

4. **Apakah project memakai AI atau machine learning?**  
   Tidak. Diagnosis dijalankan oleh pencocokan aturan Python yang datanya berada di JSON.

5. **Mengapa menggunakan Flask?**  
   Flask menghubungkan route HTTP, logika Python, template HTML, dan endpoint JSON dengan struktur sederhana.

6. **Apa fungsi `@app.route`?**  
   Mengaitkan URL dan metode HTTP dengan fungsi Python yang menanganinya.

7. **Apa beda GET dan POST di aplikasi?**  
   GET menampilkan halaman; POST mengirim data pemeriksaan atau koordinat ke backend.

8. **Mengapa `request.form.getlist("symptoms")`?**  
   Karena checkbox memungkinkan lebih dari satu gejala dikirim dengan nama field yang sama.

9. **Di mana gejala disimpan?**  
   Di `motocheck/data/symptoms.json`; bukan di database.

10. **Di mana aturan diagnosis disimpan?**  
    Di `motocheck/data/rules.json`.

11. **Apa yang dilakukan katalog?**  
    Menyediakan pilihan kendaraan dan membantu memisahkan konfigurasi yang tercantum pada sumber dengan isian pengguna.

12. **Jika model tidak dikenal, bagaimana aplikasi bertindak?**  
    Pengguna dapat memilih model lain/tidak diketahui. Aplikasi tidak membuat spesifikasi resmi dan membatasi aturan konfigurasi yang tidak cocok.

13. **Apakah tahun kendaraan otomatis diketahui dari model?**  
    Tidak. Tahun hanya ditandai terverifikasi jika katalog sumber mendukungnya; input manual tetap dinyatakan belum diverifikasi.

14. **Berapa banyak gejala?**  
    31 gejala dalam lima kelompok sistem.

15. **Berapa aturan diagnosis?**  
    11 aturan saat ini.

16. **Apakah semua aturan memiliki manual pabrikan?**  
    Tidak. Saat diperiksa, 0 aturan `external_verified`; semuanya 11 `general_guide`.

17. **Berapa gejala yang belum memiliki aturan memadai?**  
    Tujuh. Aplikasi menyatakan bukti belum cukup dan tidak memaksakan kandidat penyebab.

18. **Bagaimana jawaban lanjutan memengaruhi hasil?**  
    Jawaban dibandingkan dengan kondisi aturan untuk mengubah urutan kandidat dan menampilkan alasan dukung/tidak selaras.

19. **Apakah skor berarti persentase kerusakan?**  
    Tidak. Nilai hanya untuk mengurutkan kandidat heuristik, bukan probabilitas atau akurasi.

20. **Bagaimana aturan CVT digunakan?**  
    Kandidat CVT hanya berlaku bila konfigurasi transmisi kendaraan yang dipilih cocok dengan aturan CVT.

21. **Apa fungsi status `external_verified`?**  
    Status untuk bukti yang benar-benar ditinjau dan dibatasi pada sumber/model/tahun yang tepat. Belum ada aturan saat ini yang memenuhi status itu.

22. **Mengapa ada validasi di browser dan server?**  
    Validasi browser memberi respons cepat; server tetap wajib memeriksa ulang karena request dapat dikirim tanpa UI.

23. **Apa yang dilakukan jika pengguna mengirim input tidak valid?**  
    Backend menolak, merender pesan yang mudah dipahami, dan mengembalikan HTTP 400.

24. **Bagaimana keselamatan ditangani?**  
    Gejala berbahaya dapat menaikkan urgensi menjadi “Jangan Dikendarai” dan menampilkan saran aman, bukan menyuruh pengguna menguji kendaraan.

25. **Apa fungsi Requests?**  
    Mengirim permintaan HTTPS ke Overpass API dengan timeout, verifikasi TLS, dan penanganan kegagalan.

26. **Apakah pencarian bengkel live berhasil saat ini?**  
    Pada percobaan nyata saat panduan dibuat, tidak. Penyedia tidak dapat dihubungi. Fallback Google Maps tetap tersedia; hasil mock bukan bukti live.

27. **Dari mana data bengkel berasal?**  
    Dari objek OpenStreetMap yang diberi tag bengkel motor. Kelengkapan dan kemutakhirannya tidak dijamin MotoCheck.

28. **Apakah aplikasi menyimpan lokasi?**  
    Source menyatakan lokasi diminta setelah klik pengguna dan hasil pencarian dicache sementara di server; jangan menjanjikan privasi absolut tanpa audit deployment/log hosting.

29. **Apa fungsi HTML/Jinja?**  
    HTML menyusun konten; Jinja mengisi template dengan data Python dan membuat elemen berulang/bersyarat.

30. **Apa yang dilakukan JavaScript wizard?**  
    Mengatur perpindahan langkah, validasi awal, filter gejala, pilihan gejala utama, dan pertanyaan yang relevan.

31. **Apakah aplikasi memiliki database atau login?**  
    Tidak ada database atau autentikasi pengguna dalam scope project saat ini.

32. **Apa arti 30 tes lulus?**  
    Perilaku yang diprogram dan dicakup tes berjalan sesuai ekspektasi tes; itu bukan bukti hasil diagnosis akurat pada semua motor.

33. **Apa pengembangan selanjutnya yang paling penting?**  
    Meninjau isi manual resmi berdasarkan model/tahun untuk klaim diagnosis tertentu dan mengevaluasi aturan bersama mekanik, tanpa menandai bukti yang belum ada sebagai tervalidasi.

## 15. Ringkasan belajar dan jadwal 45–60 menit

### Lima hal yang wajib diingat

1. Flask menangani route dan menghubungkan backend Python dengan template.
2. Gejala, kendaraan, aturan, sumber, dan artikel berasal dari JSON.
3. Mesin diagnosis adalah rule-based dan skor hanya mengurutkan hasil.
4. Saat ini ada 11 aturan umum, 0 aturan tervalidasi dari isi manual, serta 7 gejala tanpa aturan memadai.
5. Keselamatan dan keterbatasan bukti harus dijelaskan lebih dulu daripada kandidat kerusakan.

### Rencana belajar 55 menit

| Menit | Kegiatan |
|---:|---|
| 0–8 | Baca ringkasan, struktur project, dan cara menjalankan aplikasi. |
| 8–18 | Pelajari route `GET /`, `POST /periksa`, validasi, dan render template. |
| 18–30 | Baca satu gejala, satu aturan JSON, dan alur `diagnose`; jelaskan bagaimana jawaban mengubah urutan. |
| 30–38 | Pelajari katalog, sumber, batas `external_verified`, dan pesan bukti belum cukup. |
| 38–45 | Coba demo wizard serta halaman hasil; latihan menyampaikan pesan keselamatan. |
| 45–51 | Jelaskan Workshop Finder, mock vs live, dan fallback Google Maps. |
| 51–55 | Jawab pertanyaan latihan tanpa membaca naskah. Bila ada waktu sampai 60 menit, ulangi bagian yang masih ragu. |

## 16. Hal yang belum selesai dan cara menyampaikannya

- **Belum ada bukti troubleshooting pabrikan yang mendukung aturan diagnosis.** Jangan menyebut hasil sebagai diagnosis berbasis manual.
- **Tujuh gejala belum punya analisis aturan yang memadai.** Aplikasi dengan benar menampilkan keterbatasan ini.
- **Katalog masih kecil dan konfigurasi banyak yang belum diketahui.** Jangan mengklaim cakupan semua model atau spesifikasi lengkap.
- **Workshop Finder live tidak dapat dihubungi pada percobaan terakhir.** Tunjukkan fallback Google Maps dan sebut status ini secara terbuka.
- **Tes otomatis tidak mengukur akurasi diagnosis dan tidak menggantikan uji mekanik.** Evaluasi teknis dengan mekanik dan manual yang benar-benar dibaca masih diperlukan.
- **Hasil browser tidak diulang untuk pembuatan panduan ini.** Pengujian browser dan screenshot yang disebut di atas berasal dari QA UI tahap sebelumnya.

Jawaban yang aman jika ditanya “apakah aplikasi ini akurat?”:  
“Saya belum mengklaim akurasi dalam persentase. Aplikasi ini baru menyaring gejala dengan panduan umum. Pengembangan berikutnya harus menghubungkan setiap aturan ke manual troubleshooting yang benar-benar ditinjau dan mengujinya bersama teknisi.”
