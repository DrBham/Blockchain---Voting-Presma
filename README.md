# Prototipe Blockchain Sederhana dengan Python — E-Voting Presma UNTAD

Proyek **Kelompok 4, Teknik Informatika Universitas Tadulako (2026)** ini merupakan prototipe sistem pemungutan suara elektronik (*e-voting*) untuk simulasi **Pemilihan Presiden Mahasiswa (Presma)**. Sistem dibangun menggunakan Python dan blockchain terdistribusi dengan transaksi bertanda tangan digital, *Proof of Work* (PoW), serta sinkronisasi antarnode.

> **Status:** prototipe untuk pembelajaran dan pengujian. Sistem **belum siap digunakan untuk pemilihan resmi** dan belum menjamin kerahasiaan pilihan suara atau kepemilikan NIM yang terverifikasi melalui sistem akademik.

## Panduan membaca

- Baru mencoba: ikuti [instalasi](#5-instalasi-dan-persiapan), lalu demo satu node di bagian tersebut.
- Menguji distribusi blockchain: lanjutkan ke [jaringan tiga node](#6-menjalankan-jaringan-tiga-node).
- Mencari perintah: buka [penggunaan client CLI](#7-penggunaan-client-cli) atau [endpoint HTTP](#9-daftar-endpoint-http).
- Menyiapkan demonstrasi: gunakan [skenario pengujian](#8-pengujian-sesuai-checkpoint-laporan).
- Mengalami kendala: lihat [pemecahan masalah](#13-pemecahan-masalah).

**Hal yang perlu diketahui sebelum mencoba:** aplikasi menggunakan terminal, belum menyediakan antarmuka web. Suara masuk ke antrean (*pool*) sebelum ditambang dan baru masuk rekap setelah tercatat dalam blok. Blockchain dan pool disimpan di memori, sehingga data node hilang ketika proses berhenti; file dompet tetap tersimpan di komputer client.

## 1. Tujuan dan ruang lingkup

Sesuai laporan proyek, sistem bertujuan mendemonstrasikan:

- pencatatan suara secara terstruktur ke dalam blok yang saling terhubung;
- pemeriksaan tanda tangan digital dan validitas transaksi;
- pencegahan *double voting* berdasarkan NIM dalam riwayat/pool yang diketahui node;
- proses penambangan blok menggunakan PoW;
- penyebaran transaksi dan blok antarnode, serta pemulihan ketertinggalan rantai dengan *longest-chain rule*;
- deteksi perubahan data dan penolakan blok tidak valid.

**Aktor:** pemilih (mahasiswa UNTAD yang memenuhi aturan NIM/angkatan pada prototipe), kandidat (`Paslon 1` atau `Paslon 2`), dan node jaringan yang menyimpan serta memvalidasi blockchain.

Aturan yang saat ini ditetapkan dalam `node.py`:

| Aturan | Nilai |
| --- | --- |
| Kandidat | `Paslon 1` dan `Paslon 2`; penulisan harus sesuai |
| Angkatan | `23`, `24`, dan `25` (2023–2025) |
| Kode fakultas | `A`, `B`, `C`, `D`, `E`, `F`, `G`, `K`, `L`, `N`, `P` |
| Contoh NIM | `F55125001`: kode fakultas `F`, kode prodi `551`, tahun `25`, nomor urut `001` |
| Hak pilih | Satu NIM tidak boleh muncul kembali dalam pool atau rantai yang diketahui node |

Angkatan yang diterima merupakan konfigurasi tetap dan **tidak bergeser otomatis mengikuti tahun berjalan**. Validator memeriksa panjang minimum, kode fakultas, dan potongan tahun; belum memeriksa seluruh pola NIM secara ketat atau mencocokkannya dengan database mahasiswa. Pembuatan dompet juga tidak membuktikan kepemilikan NIM.

## 2. Teknologi dan konsep

| Komponen | Implementasi |
| --- | --- |
| Bahasa | Python 3.8+ |
| Kriptografi identitas | Pasangan kunci RSA-2048, disimpan di client |
| Tanda tangan transaksi | RSA-PSS dengan SHA-256 |
| Hash blok | SHA-256 atas representasi JSON terurut |
| Konsensus demonstrasi | Proof of Work, difficulty default `4` (hash diawali `0000`) |
| Komunikasi jaringan | HTTP antarnode dengan endpoint JSON |
| Sinkronisasi | Pemeriksaan rantai valid terpanjang (*longest-chain rule*) |
| Deployment opsional | Docker dan Docker Compose |

Setiap blok menyimpan `index`, `timestamp`, `transaksi`, `previous_hash`, `nonce`, dan `hash`. Blok genesis menggunakan `timestamp = 0` agar identik pada semua node. Perubahan isi blok tanpa menghitung ulang dan memenuhi kembali aturan validasi menyebabkan rantai dinyatakan tidak valid.

## 3. Struktur repository

```text
Blockchain---Voting-Presma/
├── node.py              # Transaksi, Block, Blockchain, Node, HTTP, validasi
├── client.py            # CLI pemilih, dompet lokal, dan perintah pengujian
├── Dockerfile           # Image Python untuk node
├── docker-compose.yml  # Tiga node dalam satu jaringan Docker
└── README.md            # Dokumentasi proyek
```

`client.py` menggunakan kelas dari `node.py`; jalankan perintah di direktori yang berisi kedua berkas tersebut.

| Komponen | Berkas | Fungsi |
| --- | --- | --- |
| `Transaksi` | `node.py` | Data suara, tanda tangan, verifikasi, serialisasi JSON |
| `Block` | `node.py` | Struktur blok, penghitungan hash, penambangan nonce |
| `Blockchain` | `node.py` | Rantai, *transaction pool*, penambangan, validasi, rekapitulasi |
| `Node` | `node.py` | Daftar *peer*, broadcast transaksi/blok, sinkronisasi |
| `NodeHandler` | `node.py` | Server HTTP dan endpoint |
| `Dompet` | `client.py` | Membuat/memuat kunci pemilih dan menandatangani suara |

## 4. Alur kerja sistem

```text
Pemilih membuat identitas RSA-2048
             |
             v
Client membuat dan menandatangani transaksi suara
             |
             v
POST /transaksi ke node
             |
             v
Validasi NIM + kandidat + signature + double voting
             |
     +-------+-------+
     |               |
   Ditolak         Diterima
                     |
                     v
                Transaction pool
                     |
           POST /mine (Proof of Work)
                     |
                     v
             Blok masuk blockchain
                     |
                     v
         Broadcast blok ke node peer
                     |
                     v
       Validasi peer / GET /resolve
```

Transaksi suara memuat NIM (`voter_id`), kandidat, waktu, *public key*, dan *signature*. **Perintah `vote` tidak langsung memasukkan suara ke blok**: transaksi masuk ke *pool* lebih dahulu, lalu dicatat ke blockchain ketika `mine` dijalankan.

### Validasi blok

Pemeriksaan yang dijelaskan dalam laporan meliputi: urutan `index`, kecocokan `previous_hash`, hash hasil perhitungan ulang, target PoW, blok tidak kosong, validitas seluruh transaksi, dan tidak adanya NIM yang memilih dua kali. Jika rantai rusak, sistem melaporkan indeks blok pertama yang tidak valid beserta alasannya.

## 5. Instalasi dan persiapan

Siapkan Python dan `pip`. Python 3.12 disarankan agar sama dengan versi pada Dockerfile. Docker beserta Docker Compose hanya diperlukan jika memilih cara menjalankan node melalui container.

```bash
git clone https://github.com/DrBham/Blockchain---Voting-Presma.git
cd Blockchain---Voting-Presma
python -m pip install cryptography
```

Untuk memeriksa bantuan perintah, jalankan:

```bash
python client.py
```

> File `dompet_<NIM>.pem` berisi **private key tanpa enkripsi** dan dibuat di komputer client. Jangan unggah, *commit*, atau bagikan berkas dompet. Untuk penggunaan di luar demonstrasi diperlukan proteksi kunci dan autentikasi identitas yang lebih kuat.

### Demo cepat dengan satu node

Jalankan dari folder repository. Pada **terminal pertama**, nyalakan server dan biarkan tetap berjalan:

```bash
python node.py 5001
```

Pada **terminal kedua**, jalankan perintah berikut secara berurutan:

```bash
python client.py identitas F55125001
python client.py vote localhost:5001 "Paslon 1" F55125001
python client.py pool localhost:5001
python client.py mine localhost:5001
python client.py validate localhost:5001
python client.py tally localhost:5001
```

Pada node yang baru dijalankan, hasil yang diharapkan:

1. Dompet dibuat atau dimuat dari `dompet_F55125001.pem`.
2. Transaksi diterima dan pool berisi satu suara.
3. Penambangan membuat blok indeks `1`; panjang rantai menjadi dua blok, termasuk genesis.
4. Rantai dinyatakan valid dan rekap menunjukkan satu suara untuk `Paslon 1`.

`identitas` bersifat opsional sebelum `vote`, karena `vote` juga membuat atau memuat dompet. Gunakan `Ctrl+C` pada terminal server untuk menghentikan node. Untuk mengulangi demo dari rantai kosong, jalankan ulang node; tidak perlu menghapus dompet.

## 6. Menjalankan jaringan tiga node

Buka tiga terminal terpisah di folder repository.

**Terminal 1 — Node 1 (port 5001)**

```bash
python node.py 5001 localhost:5002,localhost:5003
```

**Terminal 2 — Node 2 (port 5002)**

```bash
python node.py 5002 localhost:5001,localhost:5003
```

**Terminal 3 — Node 3 (port 5003)**

```bash
python node.py 5003 localhost:5001,localhost:5002
```

Format:

```text
python node.py <port> [peer1,peer2,...] [difficulty]
```

Default `difficulty` adalah `4`. Log transaksi, penambangan, validasi, broadcast, dan sinkronisasi ditampilkan pada terminal node.

Gunakan difficulty yang sama pada semua node. Untuk demonstrasi yang lebih cepat, misalnya gunakan `2` sebagai argumen terakhir:

```bash
python node.py 5001 localhost:5002,localhost:5003 2
```

Jalankan node 2 dan 3 dengan difficulty `2` juga. Hindari menambang secara bersamaan pada beberapa node saat mengikuti demo dasar agar tidak membentuk cabang rantai dengan panjang sama.

### Alternatif menggunakan Docker Compose

```bash
docker compose up --build
```

Berkas `docker-compose.yml` menyediakan tiga node: `localhost:5001`, `localhost:5002`, dan `localhost:5003` dari komputer host. Di dalam container, masing-masing server berjalan pada port `5000`.

Jalankan `client.py` dari komputer host pada terminal lain; Python dan paket `cryptography` tetap diperlukan di host. Image Docker hanya menyalin `node.py`. Jangan menjalankan node Python lokal pada port yang sama saat Compose aktif.

Untuk menjalankan container di latar belakang, memeriksa log, dan menghentikan jaringan:

```bash
docker compose up --build -d
docker compose logs -f
```

Tekan `Ctrl+C` untuk keluar dari tampilan log. Setelah selesai menggunakan jaringan:

```bash
docker compose down
```

Konfigurasi ini belum menyimpan blockchain ke disk atau volume. Restart proses/container mengembalikan node ke genesis; node dapat mengambil kembali rantai dari peer yang masih memiliki data melalui `resolve`.

## 7. Penggunaan client CLI

Format perintah yang mengakses node:

```text
python client.py <perintah> <alamat-node> [argumen...]
```

Gunakan alamat berbentuk `host:port`, **tanpa** awalan `http://` karena client menambahkannya otomatis. Khusus identitas lokal, formatnya `python client.py identitas <NIM>` dan tidak memerlukan node aktif.

Contoh berikut menggunakan NIM **data simulasi** dan jaringan lokal. Jalankan dari terminal baru.

**1. Membuat identitas pemilih**

```bash
python client.py identitas F55124055
```

Program membuat/memuat pasangan kunci RSA dan menyimpan *private key* pada `dompet_F55124055.pem` di sisi client.

**2. Mengirimkan transaksi voting**

```bash
python client.py vote localhost:5001 "Paslon 1" F55124055
python client.py vote localhost:5001 "Paslon 2" F55124056
```

Node memvalidasi transaksi dan menyimpannya dalam *pool* jika sah. Gunakan NIM berbeda untuk setiap suara.

**3. Melihat transaksi yang menunggu ditambang**

```bash
python client.py pool localhost:5001
```

**4. Menambang blok**

```bash
python client.py mine localhost:5001
```

Node membentuk kandidat blok dari *pool*, mencari `nonce` sesuai kesulitan PoW, menambahkan blok ke rantai, mengosongkan transaksi yang telah dicatat dari *pool*, dan mengirim blok ke *peer*.

**5. Melihat rantai blockchain**

```bash
python client.py chain localhost:5001
```

**6. Memvalidasi rantai**

```bash
python client.py validate localhost:5001
```

**7. Melihat hasil rekapitulasi suara**

```bash
python client.py tally localhost:5001
```

Rekap hanya menghitung suara yang sudah berada dalam blockchain; suara di pool belum dihitung. Jalankan `validate` sebelum membaca hasil, terutama setelah pengujian manipulasi, karena `tally` tidak memvalidasi rantai secara otomatis.

**8. Sinkronisasi node**

```bash
python client.py resolve localhost:5002
python client.py chain localhost:5002
```

Node memeriksa rantai milik *peer* dan memilih rantai valid yang lebih panjang jika tersedia.

**9. Menambah peer pada node yang sudah berjalan**

```bash
python client.py add_peer localhost:5001 localhost:5002
```

Perintah ini mencoba mendaftarkan koneksi dua arah. Pendaftaran balik pada kode saat ini menggunakan `127.0.0.1:<port-node>`, sehingga cocok untuk demo proses lokal. Untuk dua laptop atau container, tetapkan daftar peer yang dapat dijangkau melalui argumen saat menjalankan node atau konfigurasi Compose.

## 8. Pengujian sesuai checkpoint laporan

Pengujian dilakukan **secara manual** dengan menjalankan `client.py`; program tidak menjalankan semua skenario secara otomatis. Beberapa uji perlu dilakukan dalam kondisi rantai baru dan/atau menggunakan NIM yang belum tercatat.

| Checkpoint | Pengujian | Bukti yang diamati |
| --- | --- | --- |
| 1 | Pembuatan identitas | Public key dan lokasi dompet lokal |
| 2 | Pembuatan dan penandatanganan transaksi | Ringkasan suara dan signature |
| 3 | Verifikasi signature | Transaksi sah diterima; transaksi yang diubah ditolak |
| 4 | Status pool | Jumlah dan daftar suara pending |
| 5 | Pembentukan kandidat blok | Index, previous hash, dan transaksi dalam blok |
| 6 | Proof of Work | Percobaan nonce, hasil hash, lama penambangan |
| 7 | Penerimaan blok | Panjang rantai bertambah dan pool berkurang |
| 8 | Validasi kondisi normal | Seluruh rantai dinyatakan valid |
| 9 | Manipulasi blok lama | Indeks blok rusak dan ketidakcocokan hash |
| 10 | Broadcast dan sinkronisasi | Penerimaan data antarnode dan hasil resolve |
| 11 | Penolakan blok tidak sah | HTTP 409 untuk blok dengan PoW tidak valid |

### 8.1 Menguji signature yang dimanipulasi

```bash
python client.py vote_ubah localhost:5001 "Paslon 1" "Paslon 2" F55124057
```

Transaksi ditandatangani untuk satu kandidat, lalu pilihan diubah sebelum dikirim. Node diharapkan menolak karena signature tidak cocok.

### 8.2 Menguji double voting

Setelah NIM `F55124055` berhasil memilih, ulangi voting dengan NIM yang sama:

```bash
python client.py vote localhost:5001 "Paslon 2" F55124055
```

Node diharapkan menolak karena NIM tersebut sudah tercatat sebagai pemilih.

### 8.3 Menguji manipulasi blok lama

**Khusus lingkungan demo.** Pastikan blok indeks `1` sudah ada. Jangan menjalankan uji ini pada node yang ingin dipertahankan sebagai data valid.

```bash
python client.py tamper localhost:5001 1
python client.py validate localhost:5001
```

Perubahan transaksi di dalam blok tanpa memperbarui hash akan terdeteksi sebagai rantai tidak valid.

### 8.4 Menguji blok palsu

```bash
python client.py palsu localhost:5001
```

Node diharapkan menolak blok yang tidak memenuhi persyaratan PoW, dengan status HTTP `409`.

### 8.5 Menguji sinkronisasi

Jalankan beberapa node, tambang blok pada node yang aktif, lalu pada node lain jalankan:

```bash
python client.py resolve localhost:5002
python client.py chain localhost:5002
```

Node mengambil rantai valid terpanjang yang tersedia dari *peer*. Pastikan alamat peer dapat diakses.

Agar perubahan mudah diamati, hentikan node 2, kirim suara dengan NIM baru dan tambang di node 1, lalu jalankan kembali node 2 dengan daftar peer semula. Node 2 mulai dari genesis; jalankan `resolve` pada node 2 dan bandingkan `chain` serta `tally` dengan node 1.

`resolve` dipicu secara manual dan hanya mengganti rantai dengan rantai valid yang **lebih panjang**. Rantai dengan panjang sama tidak menggantikan rantai lokal, termasuk ketika rantai lokal telah dimanipulasi. Pool yang tertinggal juga tidak diunduh dari peer melalui perintah ini.

## 9. Daftar endpoint HTTP

| Metode | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/chain` | Melihat blockchain |
| GET | `/pool` | Melihat transaksi yang belum ditambang |
| GET | `/tally` | Rekapitulasi suara |
| GET | `/peers` | Melihat node peer |
| GET | `/validate` | Memvalidasi rantai blockchain |
| GET | `/resolve` | Sinkronisasi mengikuti rantai valid terpanjang |
| POST | `/transaksi` | Mengirim transaksi voting bertanda tangan |
| POST | `/mine` | Menambang transaksi dari pool |
| POST | `/block` | Menerima blok dari node lain |
| POST | `/peers` | Menambah peer |
| POST | `/tamper` | Simulasi manipulasi data, **khusus demo** |

## 10. Uji lintas mesin (dua laptop)

Laporan proyek juga mendokumentasikan percobaan jaringan dengan dua laptop, meliputi pengiriman suara, penambangan, rekapitulasi, tampilan rantai, penolakan *double voting*, dan proses *resolve*.

Contoh alamat pada laporan menggunakan `192.168.137.1:5001` dan `192.168.137.253:5002`. **Alamat tersebut hanya contoh dari lingkungan pengujian laporan**; ganti sesuai alamat IP yang benar pada jaringan lokal yang sedang dipakai.

Pada laptop pertama:

```bash
python node.py 5001 192.168.137.253:5002
```

Pada laptop kedua:

```bash
python node.py 5002 192.168.137.1:5001
```

Dari komputer yang dapat mengakses server, misalnya:

```bash
python client.py vote 192.168.137.1:5001 "Paslon 1" F55125001
python client.py mine 192.168.137.1:5001
python client.py tally 192.168.137.253:5002
python client.py resolve 192.168.137.253:5002
```

Kedua laptop harus berada di jaringan yang saling terhubung; periksa IP masing-masing laptop, firewall, dan port yang digunakan. Kesalahan koneksi antarnode dapat menghambat broadcast dan sinkronisasi.

## 11. Keterbatasan dan pengembangan

Sesuai bagian keterbatasan laporan, prototipe masih memerlukan pengujian lebih lanjut terhadap manipulasi data, perbedaan rantai antarnode, dan gangguan jaringan. Selain itu:

- validasi NIM belum membuktikan kepemilikan identitas mahasiswa melalui layanan akademik resmi;
- isi suara pada blockchain tidak dirancang sebagai sistem pemilihan rahasia end-to-end;
- private key tersimpan secara lokal tanpa enkripsi berkas;
- kesesuaian rantai berdasarkan *longest-chain rule* pada prototipe tidak dengan sendirinya menjamin keamanan jaringan produksi;
- layanan HTTP dan antarmuka uji (`/tamper`) tidak sesuai untuk dibuka ke jaringan publik tanpa pengamanan tambahan.

Rencana pengembangan pada Sub-CPMK 6 mencakup pengujian multi-node lanjutan, validasi penerimaan blok, pemulihan node ketika rantai berbeda, dan pengujian transaksi tidak sah serta *double voting*.

## 12. Kontribusi kelompok

| Nama | NIM | Peran dalam laporan |
| --- | --- | --- |
| Dimas Reginald Bhamakerti | F55124055 | Perancangan sistem blockchain dan struktur blok |
| Dimas Setiawan | F55124082 | Pengembangan transaksi dan tanda tangan digital |
| I Made Aditya Pramana | F55124087 | Pengujian blockchain dan penyusunan laporan |
| Moh Magribi Ramadhan | F55124104 | Pengujian PoW dan validasi rantai |
| Moh Fiqhi | F55124108 | Dokumentasi proyek dan hasil pengujian |

**Dosen pengampu:** Rizka Ardiansyah, S.Kom., M.Kom.  
**Program studi:** S1 Teknik Informatika, Fakultas Teknik, Universitas Tadulako.  
**Tahun:** 2026.

## 13. Pemecahan masalah

| Gejala | Penyebab atau langkah penanganan |
| --- | --- |
| `No module named 'cryptography'` | Jalankan `python -m pip install cryptography` dengan interpreter Python yang dipakai menjalankan aplikasi. |
| Client tidak dapat terhubung | Pastikan node aktif, alamat memakai `host:port`, dan port sesuai. Untuk lintas laptop, gunakan IP LAN serta periksa firewall. |
| Port sudah digunakan | Hentikan proses node sebelumnya atau pilih port lain. Node lokal dan Docker tidak dapat memakai port host yang sama bersamaan. |
| NIM atau kandidat ditolak | Cocokkan dengan aturan pada bagian 1. Gunakan tanda kutip pada nama kandidat, misalnya `"Paslon 1"`. |
| NIM sudah menggunakan hak pilih | Gunakan NIM simulasi lain yang belum ada dalam pool/rantai. Membuat ulang dompet tidak menghapus riwayat suara. |
| `pool kosong` saat menambang | Kirim transaksi valid terlebih dahulu. Periksa apakah suara sudah masuk blok dari peer. |
| Rekap masih nol setelah `vote` | Jalankan `mine`; suara di pool belum termasuk hasil rekap. |
| Broadcast gagal | Pastikan semua peer sudah aktif dan alamatnya dapat dijangkau dari node pengirim. Setelah node tertinggal aktif kembali, jalankan `resolve` untuk mengambil blok. |
| `resolve` tidak mengubah rantai | Periksa apakah peer memiliki rantai valid yang benar-benar lebih panjang dan difficulty yang sama. Panjang sama tidak memicu penggantian. |
| Rantai tidak valid setelah `tamper` | Ini hasil yang diharapkan dari uji manipulasi. Untuk demo baru yang bersih, hentikan lalu jalankan ulang seluruh node. |
| Suara hilang setelah restart | Data blockchain dan pool hanya disimpan di memori. Pemulihan memerlukan peer yang masih memiliki rantai valid. |

Untuk pemeriksaan langsung tanpa perintah client, buka `http://localhost:5001/chain`, `http://localhost:5001/pool`, atau `http://localhost:5001/peers` pada browser saat node berjalan. Endpoint tersebut mengembalikan JSON, bukan halaman aplikasi.
