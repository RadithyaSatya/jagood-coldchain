# JaGOOD Hackathon Demo Runbook

Panduan ini dirancang untuk demo 5–8 menit. Tujuannya adalah menunjukkan execution path yang
benar-benar tersedia di repository, termasuk fallback, tanpa mengklaim akurasi produksi.

## 1. Narasi singkat

JaGOOD adalah prototipe decision-support sebelum pengiriman. Route planner membuat kandidat rute,
menjalankan preprocessing dan model XGBoost, mengurutkan kandidat, lalu menghitung faktor SHAP.
Scenario Simulator menjalankan ulang pipeline yang sama untuk kondisi counterfactual. AI Explain
hanya menjelaskan hasil terstruktur tersebut; LLM tidak menghitung rute atau risiko.

Data training dan label risiko bersifat sintetis. Profil komoditas saat ini adalah asumsi `DEMO`.
Output menunjukkan integrasi dan perilaku sistem, bukan probabilitas kerusakan yang sudah
tervalidasi di dunia nyata.

## 2. Persiapan sebelum presentasi

Jalankan dari root repository. Jangan mengubah port default karena CORS planner saat ini
mengizinkan `http://localhost:3000`.

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

`ORS_API_KEY` boleh kosong; route planner akan memakai fallback estimasi yang diberi label. Pada
macOS, Ollama native memberikan respons paling cepat:

```bash
brew services start ollama
ollama pull qwen3:1.7b
```

Jika Ollama tidak tersedia, lanjutkan demo. AI Explain tetap hidup dan mengembalikan ringkasan
deterministik berbasis fakta.

### Preflight wajib

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/commodities/provenance
curl -sS http://localhost:8001/health
curl -i http://localhost:8001/ready
```

Hasil yang dapat diterima:

- route planner `/health`: HTTP 200 dan `{"status":"ok"}`;
- commodity provenance: `classification` bernilai `DEMO` dan `foodkeeper_derived` bernilai
  `false`;
- AI Explain `/health`: HTTP 200;
- AI Explain `/ready`: HTTP 200 jika LLM siap, atau HTTP 503 dengan
  `fallback_available: true` jika LLM tidak tersedia.

Buka sebelum presentasi:

- dashboard utama: <http://localhost:3000>
- route-planner Swagger: <http://localhost:8000/docs>
- AI Explain Swagger: <http://localhost:8001/docs>

## 3. Alur demo utama

### Langkah A — Smart Route Planner

Di dashboard utama pilih:

| Input | Nilai demo |
|---|---|
| Asal | Jakarta |
| Tujuan | Makassar |
| Komoditas | Salmon Segar |
| Waktu | besok, dibulatkan ke jam terdekat |
| Moda | Semua |
| Urutan | Risiko kerusakan terendah |
| Cold chain | Reefer |

Klik **Cari Rute**.

Tunjukkan bahwa:

1. peta menampilkan kandidat rute;
2. tabel perbandingan membedakan rute direkomendasikan, tercepat, dan skor model terendah;
3. trade-off risiko, durasi, jarak, routing fallback, dan kualitas data lingkungan terlihat
   berdampingan;
4. kartu detail memuat risk score, confidence, serta faktor SHAP;
5. `environmental_data_quality` menjelaskan apakah input merupakan prakiraan, sebagian fallback,
   fallback netral, atau default terkonfigurasi.

Kalimat aman untuk juri:

> “Backend benar-benar menjalankan pipeline preprocessing, XGBoost, ranking, dan SHAP. Namun
> model dilatih dengan label sintetis, jadi skor ini dipakai untuk membandingkan skenario MVP,
> bukan sebagai probabilitas kerusakan yang sudah tervalidasi.”

### Langkah B — Bandingkan preferensi

Ubah **Urutkan Rute Berdasarkan** menjadi **Waktu tempuh tercepat**, lalu klik **Cari Rute** lagi.

Gunakan tabel perbandingan untuk menunjukkan apakah pilihan berubah dan berapa trade-off jam
terhadap skor model. Jika kandidat tercepat juga berskor terendah, sampaikan hasil tersebut apa
adanya; jangan menjanjikan bahwa rekomendasi selalu berubah.

### Langkah C — Scenario Simulator

Kembalikan urutan ke risiko bila perlu. Pada Scenario Simulator gunakan:

| Perubahan | Nilai demo |
|---|---|
| Delay tambahan | 12 jam |
| Moda | tetap seperti baseline |
| Cold chain | Pendingin pasif |
| Insulasi | Buruk |

Klik **Jalankan Simulasi**.

Tunjukkan baseline dan hasil gangguan, `risk_delta`, perubahan suhu kargo, faktor yang berubah,
dan rekomendasi deterministik. Jelaskan bahwa simulator menjalankan ulang model yang sama; ini
bukan Monte Carlo dan bukan model scenario terpisah.

### Langkah D — AI Explain

Klik **Jelaskan** pada hasil scenario.

- Jika LLM siap, UI menampilkan nama model.
- Jika LLM gagal/tidak tersedia, UI menampilkan **Ringkasan fallback tanpa LLM**.

Keduanya merupakan hasil demo yang valid. Tunjukkan bahwa jawaban menyebut nilai scenario yang
sama dengan hasil analitik. AI Explain tidak boleh memperkenalkan skor atau fakta baru.

## 4. Jalur aman tanpa layanan eksternal

Jika koneksi ORS/BMKG/Open-Meteo tidak stabil, gunakan:

| Input | Nilai aman |
|---|---|
| Asal | Jakarta |
| Tujuan | Surabaya |
| Komoditas | Salmon Segar |
| Moda | Darat saja |
| Cold chain | Reefer |
| Urutan | Risiko kerusakan terendah |

Jalur ini menghindari BMKG maritim dan Open-Meteo. Jika ORS gagal, jarak/waktu memakai fallback
estimasi dan UI menandainya. Model inference, ranking, SHAP, scenario comparison, dan AI Explain
fallback tetap berjalan.

Golden test menggunakan prinsip yang sama dan sengaja mematikan ORS serta LLM:

```bash
pytest -q tests/golden_demo
```

Command tersebut dijalankan setelah dependensi route planner dan package AI Explain terpasang.
GitHub Actions juga menjalankannya melalui job `offline golden demo / pytest`.

## 5. Troubleshooting cepat

### Container belum sehat

```bash
docker compose ps
docker compose logs --tail=100 postgres route-planner ai-explain planner-web
```

Pastikan PostgreSQL sehat sebelum route planner. Bangun ulang bila kontrak API/frontend baru saja
berubah:

```bash
docker compose up --build -d
```

### Dashboard gagal memuat komoditas

Periksa `http://localhost:8000/health` dan browser console. Gunakan port default `3000` dan `8000`
agar sesuai build-time API URL serta konfigurasi CORS.

### AI Explain lama atau gagal

Periksa `http://localhost:8001/ready`. HTTP 503 dengan `fallback_available: true` berarti demo
dapat dilanjutkan. Jika ingin respons LLM, pastikan model pada `.env` sama dengan hasil
`ollama list`.

### Rute maritim memakai fallback

Ini bukan alasan menghentikan demo. Tunjukkan label `environmental_data_quality` dan jelaskan bahwa
nilai netral menjaga continuity ketika BMKG gagal, tetapi tidak dianggap setara dengan observasi.

## 6. Klaim yang boleh dan tidak boleh disampaikan

### Boleh

- XGBoost inference dan preprocessing benar-benar dijalankan.
- SHAP benar-benar dihitung sebagai penjelasan faktor kualitatif.
- Scenario Simulator membandingkan dua hasil pipeline analitik.
- ORS, BMKG, Open-Meteo, dan LLM memiliki strategi continuity/fallback sesuai batas masing-masing.
- Data sintetis dan asumsi demo diberi label secara eksplisit.

### Jangan diklaim

- akurasi kerusakan atau food-safety sudah tervalidasi di dunia nyata;
- profil komoditas berasal dari FoodKeeper;
- sistem memantau GPS/IoT atau shipment aktif;
- sistem mempunyai model prediksi delay terpisah;
- sistem menghitung remaining shelf life atau economic loss;
- scenario menggunakan Monte Carlo;
- status pelabuhan adalah status operasional resmi;
- geometri `searoute-py` layak untuk navigasi kapal.

## 7. Checklist 15 menit sebelum demo

- [ ] Working tree/branch yang dipresentasikan sudah benar.
- [ ] Semua container yang dibutuhkan berstatus running/healthy.
- [ ] Dashboard dan dua halaman Swagger sudah terbuka.
- [ ] `/commodities/provenance` menunjukkan data `DEMO`.
- [ ] Jalur Jakarta–Makassar sudah dicoba sekali.
- [ ] Jalur aman Jakarta–Surabaya sudah dicoba sekali.
- [ ] Status `/ready` AI Explain sudah diketahui: LLM atau fallback.
- [ ] Tidak ada klaim monitoring, data nyata, atau akurasi produksi dalam narasi.
