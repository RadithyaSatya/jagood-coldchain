# PRD — JaGOOD Smart Route Planner
### AI-Powered Route Recommendation untuk Cold Chain Logistics

**Versi:** 1.0
**Modul:** AI 2 — Smart Route Recommendation (bagian dari platform JaGOOD)
**Target implementasi:** MVP Hackathon (vibecoding-ready)
**Model AI:** XGBoost Classifier (Risk-based Ranking)

---

## 1. Latar Belakang & Masalah

Pengiriman produk cold chain (makanan segar/beku) melalui jalur laut dan darat rentan mengalami **penurunan mutu (food loss)** akibat faktor yang sering tidak diperhitungkan di awal perjalanan: cuaca buruk, gelombang tinggi, keterlambatan pelabuhan, dan pemilihan rute yang tidak mempertimbangkan sensitivitas suhu komoditas.

Sistem cold chain konvensional bersifat **reaktif** — memonitor suhu *setelah* pengiriman berjalan. JaGOOD Smart Route Planner bersifat **prediktif** — merekomendasikan rute *sebelum* pengiriman dimulai, dengan mempertimbangkan risiko penurunan mutu produk, bukan sekadar jarak/waktu tercepat.

## 2. Tujuan (Goals)

1. Memberikan **rekomendasi rute** (dari beberapa kandidat) yang meminimalkan risiko kerusakan/penurunan mutu produk selama distribusi.
2. Mempertimbangkan kendala dinamis (cuaca buruk, gelombang tinggi, potensi pelabuhan tidak beroperasi) secara otomatis dalam skoring rute.
3. Menyediakan penjelasan (explainability) atas rekomendasi yang diberikan.
4. Menjadi modul yang bisa berdiri sendiri (standalone) namun terintegrasi dengan AI 1 (Risk Prediction) dan Recommendation Engine JaGOOD.

## 3. Non-Goals (Di Luar Scope MVP)

- Tidak melakukan booking/eksekusi pengiriman otomatis (hanya rekomendasi).
- Tidak menghitung biaya logistik/tarif pengiriman.
- Tidak melakukan real-time tracking GPS kapal/truk (di luar cakupan data yang tersedia gratis).
- Tidak menjamin akurasi navigasi maritim (data laut bersifat estimasi visualisasi, bukan untuk navigasi kapal sungguhan).

## 4. User & Use Case

**Primary user:** Operator/perencana pengiriman di perusahaan logistik cold chain.

**Use case utama:**
> Sebagai operator pengiriman, saya input asal, tujuan, jenis komoditas, dan waktu keberangkatan → sistem menghasilkan beberapa opsi rute beserta skor risiko, estimasi waktu tiba, dan penjelasan alasan rekomendasi → saya memilih rute terbaik atau melihat rute alternatif jika ada kendala (cuaca buruk/gelombang tinggi).

---

## 5. Functional Requirements

### FR-1: Input Pengiriman
Sistem menerima input:
- `origin` (nama lokasi / koordinat lat-long)
- `destination` (nama lokasi / koordinat lat-long)
- `commodity_type` (dropdown: Salmon, Udang, Ayam, dst — dari Commodity Database)
- `departure_time` (datetime)
- `transport_mode_preference` (opsional: darat saja / laut saja / kombinasi / semua)

### FR-2: Generate Kandidat Rute
Sistem menghasilkan **minimal 2–3 kandidat rute** berbeda untuk pasangan origin-destination yang sama, dengan kombinasi:
- Rute darat penuh (jika origin-destination memungkinkan)
- Rute darat + laut (multi-modal, via pelabuhan terdekat)
- Rute alternatif (pelabuhan/jalur berbeda) jika tersedia

### FR-3: Enrichment Data per Kandidat Rute
Setiap kandidat rute diperkaya dengan fitur:
- Jarak & estimasi durasi (darat: OpenRouteService/OSRM; laut: searoute-py)
- Cuaca & tinggi gelombang di jalur laut yang dilalui (BMKG API)
- Status pelabuhan (derived dari kategori gelombang BMKG)
- Histori delay & histori kerusakan pada rute tersebut (data historis/sintetis)
- Karakteristik komoditas (suhu ideal, shelf life, toleransi delay dari Commodity Database)

### FR-4: Prediksi Risiko per Kandidat Rute (Model AI)
Model XGBoost memprediksi `risk_level` (Low/Medium/High) dan `risk_probability` (0–1) untuk **setiap kandidat rute**.

### FR-5: Ranking & Rekomendasi
Sistem meranking seluruh kandidat rute berdasarkan risk_probability (ascending), dengan tie-breaker berdasarkan estimasi durasi. Output: 1 rute utama (recommended) + rute alternatif.

### FR-6: Handling Kendala Dinamis
Jika kondisi ekstrem terdeteksi pada rute laut (misal `wave_category` = Tinggi/Sangat Tinggi/Ekstrem, atau `port_status` = berisiko tutup):
- Rute tersebut otomatis mendapat skor risiko lebih tinggi (bukan hard-block, tetap ditampilkan tapi diberi warning)
- Sistem mengangkat rute alternatif (darat, atau jalur laut lain) sebagai rekomendasi utama
- Field `trigger_reason` diisi dengan alasan spesifik (misal `"gelombang_tinggi_rute_A"`)

### FR-7: Output ke Recommendation Engine / Dashboard
```json
{
  "shipment_id": "string",
  "recommended_route": {
    "route_id": "string",
    "transport_mode": "string",
    "distance_km": 0,
    "estimated_duration_hours": 0,
    "risk_level": "Low|Medium|High",
    "risk_probability": 0.0,
    "confidence_score": 0.0,
    "trigger_reason": "string|null"
  },
  "alternative_routes": [ "...same structure..." ]
}
```

### FR-8: Explainability (opsional, terhubung ke AI Explain/LLM)
Field `trigger_reason` dan feature importance dari model disediakan sebagai bahan mentah untuk lapisan LLM Explain (di luar scope modul ini, tapi outputnya harus kompatibel).

---

## 6. Data & Sumber (Ringkasan)

| Fitur | Sumber | Jenis | Catatan |
|---|---|---|---|
| Jarak & durasi darat | OpenRouteService API (atau OSRM self-host) | Real, gratis (fair-use limit) | Perlu API key gratis dari openrouteservice.org |
| Jarak & waypoint laut | `searoute-py` (Python package) | Real (jalur laut aktual), gratis, lokal | `pip install searoute` — bukan untuk navigasi presisi |
| Cuaca & tinggi gelombang | BMKG Public API (`peta-maritim.bmkg.go.id/public_api`) | Real, gratis resmi pemerintah | Wajib cantumkan atribusi "BMKG" |
| Status pelabuhan | Derived dari `wave_category` BMKG | Proxy/rule-based | Tidak ada API publik resmi (Inaportnet tertutup) |
| Histori delay & histori kerusakan | Dataset internal/sintetis | Sintetis (MVP) | Dibangun dari asumsi realistis + pola musiman BMKG |
| Karakteristik komoditas (suhu ideal, shelf life) | USDA FoodKeeper dataset + literatur FAO | Semi-real (referensial) | Lookup table statis, tidak perlu API real-time |

## 7. Skema Data (Data Contract)

### 7.1 Tabel: `route_candidates` (1 baris = 1 kandidat rute, unit analisis model)

| Kolom | Tipe | Sumber |
|---|---|---|
| `shipment_id` | string | input user |
| `route_id` | string | generator kandidat rute |
| `commodity_type` | category | input user |
| `commodity_temp_ideal_c` | float | Commodity Database |
| `commodity_shelf_life_hours` | float | Commodity Database |
| `commodity_delay_tolerance_hours` | float | Commodity Database |
| `transport_mode` | category (darat/laut/kombinasi) | generator rute |
| `distance_km` | float | ORS / searoute-py |
| `estimated_duration_hours` | float | ORS / searoute-py |
| `wave_height_m` | float | BMKG |
| `wave_category` | category | BMKG |
| `wind_speed_kmh` | float | BMKG |
| `weather_condition` | category | BMKG |
| `port_status_flag` | binary (0/1) | derived dari wave_category |
| `historical_delay_avg_hours` | float | historical/synthetic dataset |
| `historical_damage_rate` | float (0–1) | historical/synthetic dataset |
| `departure_hour` | int (0–23) | input user |
| **`risk_level`** (target) | category (Low/Medium/High) | label training |

### 7.2 Tabel: `commodity_database` (lookup statis)

| Kolom | Tipe |
|---|---|
| `commodity_type` | string (primary key) |
| `temp_ideal_min_c` | float |
| `temp_ideal_max_c` | float |
| `shelf_life_hours_at_ideal_temp` | float |
| `delay_tolerance_hours` | float |
| `temp_sensitivity_level` | category (Low/Medium/High) |

---

## 8. Model AI — Spesifikasi Teknis

| Aspek | Keputusan |
|---|---|
| Problem framing | Klasifikasi multi-kelas per kandidat rute (bukan prediksi 1 output untuk semua rute sekaligus) |
| Algoritma | XGBoost Classifier (`XGBClassifier`, objective=`multi:softprob`) |
| Target | `risk_level`: Low / Medium / High |
| Fitur kategorikal | One-hot encoding: `commodity_type`, `transport_mode`, `weather_condition`, `wave_category` |
| Fitur numerik | Scaling opsional (XGBoost tree-based, umumnya tidak wajib) |
| Feature engineering tambahan | Interaction feature: `wave_height_m × temp_sensitivity_level` (encode numerik) |
| Split data | Time-based split (train pada data lebih lama, test pada data lebih baru) — bukan random split |
| Evaluasi | Precision/Recall/F1 per kelas (fokus recall kelas "High" — false negative mahal), Top-1 ranking accuracy |
| Output tambahan | `predict_proba()` untuk `risk_probability`, feature importance untuk explainability |

### Ranking Logic (di luar model, post-processing)
```
1. Jalankan model.predict_proba() untuk semua kandidat rute pada 1 shipment
2. Sort ascending berdasarkan risk_probability
3. Jika ada wave_category ekstrem → set trigger_reason, tetap tampilkan tapi turunkan prioritas
4. Ambil top-1 sebagai recommended_route, sisanya sebagai alternative_routes
```

---

## 9. Arsitektur Sistem (High-Level)

```
Frontend (input form: origin, destination, commodity, waktu)
        ↓
Backend API (FastAPI)
        ↓
[1] Route Candidate Generator
     - darat → OpenRouteService API
     - laut  → searoute-py
        ↓
[2] Feature Enrichment Service
     - cuaca/gelombang → BMKG API
     - commodity lookup → Commodity Database (static)
     - historical → historical/synthetic dataset
        ↓
[3] XGBoost Risk Prediction (per kandidat rute)
        ↓
[4] Ranking & Recommendation Logic
        ↓
JSON Response → Frontend Dashboard
```

## 10. Tech Stack yang Disarankan

| Layer | Teknologi |
|---|---|
| Backend | Python, FastAPI |
| Model training | XGBoost, scikit-learn, pandas |
| Model serving | Pickle/joblib model + endpoint FastAPI (`/predict-route`) |
| External API calls | `requests` (BMKG, ORS), `searoute` (pip package) |
| Database | SQLite/PostgreSQL (untuk MVP bisa SQLite) — tabel `commodity_database`, cache hasil BMKG |
| Frontend | React / Next.js (dashboard sederhana: form input + tabel hasil rute) |

## 11. Struktur Folder yang Disarankan (untuk vibecoding)

```
jagood-route-planner/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── routers/
│   │   │   └── route_planner.py     # endpoint /predict-route
│   │   ├── services/
│   │   │   ├── route_generator.py   # generate kandidat rute (ORS + searoute)
│   │   │   ├── weather_service.py   # fetch BMKG API
│   │   │   ├── commodity_service.py # lookup commodity_database
│   │   │   └── ranking_service.py   # ranking & trigger_reason logic
│   │   ├── models/
│   │   │   └── xgboost_model.pkl    # model terlatih
│   │   ├── schemas/
│   │   │   └── route_schema.py      # pydantic models (request/response)
│   │   └── data/
│   │       ├── commodity_database.json
│   │       └── synthetic_historical.csv
│   └── training/
│       ├── generate_synthetic_data.py
│       ├── train_model.py
│       └── evaluate_model.py
├── frontend/
│   └── (React/Next.js app)
└── README.md
```

## 12. API Contract (Endpoint Utama)

**`POST /predict-route`**

Request:
```json
{
  "origin": {"lat": -6.1045, "lon": 106.8829},
  "destination": {"lat": -7.2575, "lon": 112.7521},
  "commodity_type": "Salmon",
  "departure_time": "2026-08-10T08:00:00Z"
}
```

Response: (sesuai FR-7 di atas)

---

## 13. Roadmap Implementasi (MVP Hackathon)

| Tahap | Task | Output |
|---|---|---|
| 1 | Bangun `commodity_database.json` (5–10 komoditas) | Lookup table siap pakai |
| 2 | Bangun `generate_synthetic_data.py` untuk historical delay/damage | Dataset training awal |
| 3 | Integrasi BMKG API + `searoute-py` + OpenRouteService | Fungsi enrichment fitur real |
| 4 | Training XGBoost + evaluasi (precision/recall per kelas) | Model `.pkl` |
| 5 | Bangun endpoint FastAPI `/predict-route` | API berjalan end-to-end |
| 6 | Bangun dashboard frontend sederhana | Demo yang bisa diklik juri |
| 7 | Uji skenario ekstrem (gelombang tinggi, port berisiko tutup) | Validasi FR-6 |

## 14. Risiko & Asumsi

- **Data sintetis** untuk historical delay/damage rate belum tervalidasi dengan data riil — perlu disampaikan secara transparan ke juri sebagai keterbatasan MVP dengan roadmap jelas.
- **searoute-py** menghasilkan rute laut untuk visualisasi realistis, bukan untuk navigasi presisi tinggi — cukup untuk estimasi jarak/durasi MVP.
- **Port status** adalah proxy (bukan status real-time resmi) karena tidak ada API publik Inaportnet.
- Ketergantungan pada rate limit gratis BMKG/ORS — perlu caching hasil API untuk mengurangi jumlah request saat demo.

## 15. Metrik Keberhasilan MVP

- Model mampu membedakan risk level dengan **recall kelas "High" ≥ 80%** pada data uji (menghindari false negative berbahaya).
- Sistem mampu menghasilkan rekomendasi rute end-to-end (input → output JSON) dalam **< 5 detik**.
- Sistem terbukti otomatis mengalihkan rekomendasi saat kondisi cuaca ekstrem disimulasikan (FR-6 tervalidasi).

---

*Dokumen ini dirancang sebagai spesifikasi kerja untuk pengembangan cepat (vibecoding) — setiap bagian (data schema, API contract, struktur folder) dapat langsung dijadikan prompt/instruksi ke AI coding assistant per modul.*