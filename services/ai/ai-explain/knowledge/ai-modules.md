# AI Modules

## Smart Route Planner

Status: tersedia sebagai MVP eksperimental.

Input utamanya adalah asal/tujuan, komoditas, waktu keberangkatan, moda, dan konfigurasi cold
chain. Service membuat kandidat rute, melakukan enrichment, menjalankan model risiko XGBoost,
dan mengurutkan kandidat berdasarkan risiko atau waktu. Outputnya adalah rekomendasi rute beserta
alternatif, skor risiko model, dan faktor SHAP.

Model dilatih menggunakan shipment dan label sintetis. Rekomendasi bukan navigasi presisi atau
jaminan mutu produk.

## Scenario Simulator

Status: tersedia di route-planner sebagai analisis counterfactual deterministik.

Simulator membandingkan baseline dengan perubahan delay, moda, pendingin, atau insulasi. Output
berisi kedua hasil model, selisih risiko, faktor yang berubah, dan rekomendasi berbasis aturan.
Simulator tidak menghitung dampak ekonomi, tidak memakai Monte Carlo, dan bukan model ML terpisah.

## Maritime Monitoring

Status: belum tersedia.

MVP dapat memakai prakiraan maritim BMKG untuk enrichment rute laut sebelum pengiriman, tetapi
tidak menerima GPS, tidak melacak kapal/truk, dan tidak mendeteksi delay shipment secara real-time.

## AI Explain

Status: tersedia dengan Llama 3.2 1B yang di-*fine-tune* menggunakan LoRA dan fallback
deterministik.

AI Explain menerima hasil terstruktur dari planner atau simulator dan mengubahnya menjadi bahasa
natural. LLM tidak menghitung prediction, skor, atau rute. Jika LLM tidak tersedia, service
merangkum fakta terstruktur tanpa mengarang nilai baru. Dataset, adapter, konfigurasi training,
dan evaluasi held-out tersedia di folder `finetuning/`. Evaluasi tersebut mengukur spesialisasi
pada tugas sintetis terstruktur, bukan akurasi operasional pengiriman nyata.
