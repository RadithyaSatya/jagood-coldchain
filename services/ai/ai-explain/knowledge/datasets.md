# Dataset

## Commodity Profiles

Klasifikasi: DEMO.

Profil suhu, shelf life, toleransi delay, dan sensitivitas adalah asumsi manual untuk MVP. Data
tersebut bukan turunan FoodKeeper dan belum tervalidasi untuk keputusan keamanan pangan.

## Model Training Data

Klasifikasi: SYNTHETIC.

Shipment, kondisi, delay, damage rate, dan label risiko untuk training/evaluasi dibuat oleh script
deterministik dengan seed. Metrik evaluasi hanya menunjukkan kemampuan model mempelajari fungsi
label sintetis, bukan akurasi pada shipment nyata.

## Runtime Environmental Data

OpenRouteService dipakai untuk rute darat jika tersedia dan memiliki fallback estimasi jarak.
BMKG dipakai untuk prakiraan rute maritim/pelabuhan dan responsnya di-cache; kegagalan jaringan
atau respons tidak valid memakai nilai netral yang ditandai sebagai fallback. Open-Meteo dipakai
untuk suhu ambient pada simulasi pendingin pasif dan memiliki fallback sintetis. Rute darat
memakai kondisi lingkungan netral yang dikonfigurasi.

Tidak ada dataset GPS, IoT, shipment aktual, atau outcome kerusakan nyata di MVP.
