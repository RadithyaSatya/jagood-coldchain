# Architecture

Arsitektur MVP yang sudah berjalan:

1. Frontend Next.js mengirim permintaan planning atau scenario ke route-planner FastAPI.
2. Route-planner membuat kandidat rute dan menambahkan profil komoditas, baseline sintetis,
   serta data lingkungan eksternal ketika tersedia.
3. Pipeline preprocessing dan XGBoost menghasilkan klasifikasi/score risiko; SHAP menghasilkan
   faktor penjelas kualitatif.
4. Frontend dapat meneruskan hasil terstruktur ke AI Explain.
5. AI Explain menggunakan LLM lokal untuk menjelaskan fakta atau fallback deterministik saat LLM
   tidak tersedia.

PostgreSQL dipakai untuk cache respons eksternal, bukan sebagai database shipment. Repository
tidak memiliki feature store, pipeline IoT/GPS, atau backend monitoring.
