import { RISK_LABELS, riskColor } from "@/lib/riskPalette";

const WAVE_SCALE = [
  { label: "Tenang", range: "0 - 0.5 m" },
  { label: "Rendah", range: "0.5 - 1.25 m" },
  { label: "Sedang", range: "1.25 - 2.5 m" },
  { label: "Tinggi", range: "2.5 - 4.0 m" },
  { label: "Sangat Tinggi", range: "4.0 - 6.0 m" },
  { label: "Ekstrem", range: "6.0 - 9.0 m" },
  { label: "Sangat Ekstrem", range: "> 9.0 m" },
];

function Dot({ color }: { color: string }) {
  return <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />;
}

export default function ParameterLegend() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Keterangan Peta &amp; Parameter
      </h2>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 font-medium text-zinc-800 dark:text-zinc-200">Warna garis rute = tingkat risiko</h3>
          <ul className="space-y-1.5 text-zinc-600 dark:text-zinc-400">
            {(["Low", "Medium", "High"] as const).map((level) => (
              <li key={level} className="flex items-center gap-2">
                <Dot color={riskColor(level)} />
                <strong className="text-zinc-800 dark:text-zinc-200">{RISK_LABELS[level]}</strong>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-zinc-500 dark:text-zinc-400">
            Garis tebal = rute yang direkomendasikan. Garis putus-putus = sebagian jarak/waktu
            memakai fallback estimasi untuk sebagian jarak/waktu, lihat <code>data_quality</code>.
            Indikator ini hanya menjelaskan fallback routing, bukan seluruh input model.
            Kualitas prakiraan lingkungan ditampilkan terpisah pada kartu rute.
            Nilai <code>fallback</code> atau <code>configured</code> bukan observasi lingkungan live.
          </p>
        </div>

        <div>
          <h3 className="mb-2 font-medium text-zinc-800 dark:text-zinc-200">Ikon di peta</h3>
          <ul className="space-y-1.5 text-zinc-600 dark:text-zinc-400">
            <li><strong className="text-zinc-800 dark:text-zinc-200">A / B</strong> -- titik asal / tujuan pengiriman</li>
            <li><span style={{ color: "#2a78d6" }}>&#9679;</span> -- pelabuhan muat/bongkar (rute kombinasi darat+laut)</li>
            <li><span style={{ color: "#d03b3b" }}>&#9679;</span> <strong className="text-zinc-800 dark:text-zinc-200">!</strong> -- titik risiko: lokasi persis di sepanjang rute laut dengan kondisi terburuk (gelombang/cuaca), klik untuk detail</li>
          </ul>
        </div>

        <div>
          <h3 className="mb-2 font-medium text-zinc-800 dark:text-zinc-200">Skala kategori gelombang (BMKG)</h3>
          <ul className="space-y-1 text-zinc-600 dark:text-zinc-400">
            {WAVE_SCALE.map((w) => (
              <li key={w.label} className="flex justify-between gap-4">
                <span>{w.label}</span>
                <span className="text-zinc-400 dark:text-zinc-500">{w.range}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-zinc-500 dark:text-zinc-400">
            Kategori Tinggi ke atas otomatis menurunkan prioritas rute (FR-6) dan memicu peringatan (<code>trigger_reason</code>),
            tapi rute tetap ditampilkan sebagai alternatif -- tidak diblokir.
          </p>
        </div>

        <div>
          <h3 className="mb-2 font-medium text-zinc-800 dark:text-zinc-200">Arti angka lain per rute</h3>
          <dl className="space-y-2 text-zinc-600 dark:text-zinc-400">
            <div>
              <dt className="font-medium text-zinc-800 dark:text-zinc-200">Skor risiko (risk_probability)</dt>
              <dd>Perkiraan gabungan peluang rute ini Sedang/Tinggi risikonya (0-100%). Dipakai untuk mengurutkan rute.</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-800 dark:text-zinc-200">Confidence</dt>
              <dd>Seberapa yakin model AI terhadap prediksinya sendiri (0-100%), bukan seberapa aman rutenya.</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-800 dark:text-zinc-200">Estimasi keterlambatan/kerusakan historis</dt>
              <dd>Perkiraan rata-rata keterlambatan (jam) dan tingkat kerusakan kargo untuk profil jarak/moda rute ini -- bukan riwayat pengiriman ini secara spesifik (data historis bersifat sintetis untuk MVP).</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-800 dark:text-zinc-200">Suhu udara pelabuhan (port_ambient_temp_c)</dt>
              <dd>
                Prakiraan suhu udara BMKG di pelabuhan muat/bongkar terpanas pada rute kombinasi -- bukan suhu kargo. Ini proxy risiko
                mesin pendingin (reefer) kepayahan saat kontainer idle lama di pelabuhan yang panas, bukan asumsi kargo langsung
                ikut memanas. Rute darat tanpa singgah pelabuhan pakai nilai netral (30&deg;C) yang tidak menambah risiko.
              </dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-800 dark:text-zinc-200">Reefer vs Pasif</dt>
              <dd>
                <strong>Reefer</strong> (pendingin aktif): kargo diasumsikan tetap di suhu ideal sepanjang perjalanan.{" "}
                <strong>Pasif</strong> (tanpa pendingin aktif, misal cooler box + insulasi saja): suhu kargo disimulasikan
                mengikuti prakiraan suhu udara sepanjang rute (Open-Meteo, dengan fallback sintetis) memakai model perpindahan panas, dan laju kerusakan
                dipercepat mengikuti prinsip Q10 (tiap ~10&deg;C di atas suhu ideal, laju kerusakan kira-kira berlipat).
                Grafik suhu kargo hanya muncul untuk rute pasif.
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
