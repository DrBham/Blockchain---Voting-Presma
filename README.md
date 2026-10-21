# Praktikum 1B — Blockchain Voting (Versi Gabungan)

Program simulasi **sistem voting berbasis Blockchain** menggunakan Python. Sistem terdiri dari beberapa node yang saling terhubung melalui HTTP untuk menyimpan data voting.

Versi ini menggabungkan dua sumber:

* **Jaringan multi-node** dari praktikum sebelumnya: broadcast antar-node, validasi block, dan **Longest-Chain Rule**.
* **Kriptografi dan struktur block** dari `blockchain_voting.py`: suara **bertanda tangan digital (RSA-PSS)**, **transaction pool**, **Proof of Work**, dan validasi seluruh rantai.

Program **tidak menjalankan demo otomatis**. Node berjalan sebagai server, lalu semua aksi (membuat identitas, voting, menambang, validasi, dan seterusnya) dilakukan dengan mengetik perintah `client.py` di terminal.

## 📁 Struktur Direktori

```text
praktikum1b/
├── node.py                 # Node blockchain: Transaksi, Block, Blockchain, Node, HTTP
├── client.py               # CLI: Dompet (kunci voter) + semua perintah
├── Dockerfile              # Konfigurasi Docker image
├── docker-compose.yml      # Konfigurasi jaringan multi-node
└── README.md               # Dokumentasi penggunaan
```

`client.py` mengimpor class dari `node.py`, jadi **keduanya harus berada di folder yang sama**.

## 🧩 Susunan Program

| Class | File | Fungsi |
| --- | --- | --- |
| `Transaksi` | `node.py` | Satu suara: NIM, pilihan, public key, timestamp, signature |
| `Block` | `node.py` | index, timestamp, daftar transaksi, previous hash, nonce, hash, dan proses penambangan |
| `Blockchain` | `node.py` | Rantai block, transaction pool, validasi, dan Proof of Work |
| `Node` | `node.py` | Blockchain + daftar peer, broadcast, dan resolve |
| `Dompet` | `client.py` | Membuat dan menyimpan kunci voter, serta menandatangani suara |

---

# ⚙️ 0. Persiapan

Python 3.8 atau lebih baru, dan library `cryptography`:

```powershell
pip install cryptography
```

---

# 🚀 1. Menjalankan Node di Terminal Lokal

Buka **3 jendela terminal** di dalam folder `praktikum1b/`.

Format perintah:

```text
python node.py <port> [peer1,peer2,...] [difficulty]
```

`difficulty` adalah jumlah angka nol di awal hash hasil Proof of Work (default `4`). Angka lebih besar membuat penambangan lebih lama.

### Terminal 1 — Node 1

```powershell
python node.py 5001 localhost:5002,localhost:5003
```

### Terminal 2 — Node 2

```powershell
python node.py 5002 localhost:5001,localhost:5003
```

### Terminal 3 — Node 3

```powershell
python node.py 5003 localhost:5001,localhost:5002
```

Setelah ketiganya berjalan, terbentuk jaringan **3 node** yang saling terhubung. Semua log kejadian penting (transaksi masuk, pool, penambangan, block diterima atau ditolak) tercetak di terminal node masing-masing.

> Opsional: peer juga bisa ditambahkan setelah node berjalan, misalnya `python client.py add_peer localhost:5001 localhost:5002`. Perintah ini menghubungkan **dua arah** dan hanya cocok untuk node di satu komputer (alamat balik yang dipakai adalah `127.0.0.1`). Untuk Docker atau dua laptop, daftarkan peer saat node dijalankan.

---

# 🖥️ 2. Menggunakan Client CLI

Buka **terminal baru** di folder `praktikum1b/`. Format umum:

```text
python client.py <perintah> <alamat-node> [argumen...]
```

## Alur Kerja Voting

Berbeda dengan versi sebelumnya, **voting tidak langsung membuat block**. Alurnya:

```text
vote  ->  transaksi bertanda tangan masuk POOL (dan disebarkan ke semua node)
mine  ->  block dibentuk dari isi pool + Proof of Work -> block disebarkan
```

Jadi setelah `vote`, jalankan `mine` agar suara tercatat di blockchain. Beberapa suara bisa dikumpulkan dulu di pool, lalu ditambang sekaligus dalam satu block.

## A. Membuat Identitas Voter

```powershell
python client.py identitas F55125001
```

Mencetak alamat dan public key (dipotong). Private key disimpan **lokal** di `dompet_F55125001.pem` dan tidak pernah dikirim ke node. Perintah `vote` otomatis membuat identitas jika belum ada.

## B. Memasukkan Suara Sah

```powershell
python client.py vote localhost:5001 "Paslon 1" "F55125001"
python client.py vote localhost:5001 "Paslon 2" "C10123045"
```

NIM harus memenuhi ketentuan sistem: mahasiswa **Angkatan 2023–2025 / Semester 3–7**.

## C. Melihat Pool (Suara Pending)

```powershell
python client.py pool localhost:5002
```

Suara yang masuk di Node 1 juga muncul di pool Node 2 dan Node 3.

## D. Menambang Block

```powershell
python client.py mine localhost:5001
```

Pembentukan block candidate, Proof of Work (jumlah percobaan, nonce, hash, lama waktu), dan block diterima rantai tercetak di terminal node.

## E. Melihat Isi Blockchain

```powershell
python client.py chain localhost:5002
```

## F. Rekapitulasi Suara

```powershell
python client.py tally localhost:5002
```

## G. Validasi Seluruh Rantai

```powershell
python client.py validate localhost:5002
```

Memeriksa hash, previous hash, Proof of Work, signature, dan double voting di seluruh block. Jika ada yang rusak, ditampilkan **index block pertama yang rusak** beserta alasannya.

## H. Longest-Chain Rule

```powershell
python client.py resolve localhost:5003
```

Node mengambil rantai peer, memvalidasinya, lalu memakai rantai valid yang paling panjang.

---

# 🧪 3. Skenario Pengujian

## 3.1 Uji Penolakan Mahasiswa yang Belum Memenuhi Syarat

```powershell
python client.py vote localhost:5001 "Paslon 1" "F55126001"
```

**DITOLAK**: Angkatan 2026 tidak memenuhi syarat.

## 3.2 Uji Penolakan Double Voting

Gunakan NIM yang sudah memilih (baik yang masih di pool maupun yang sudah di blockchain):

```powershell
python client.py vote localhost:5001 "Paslon 2" "F55125001"
```

**DITOLAK**: NIM sudah menggunakan hak pilihnya.

## 3.3 Uji Transaksi yang Diubah Setelah Ditandatangani

```powershell
python client.py vote_ubah localhost:5001 "Paslon 1" "Paslon 2" "F55123003"
```

Suara ditandatangani untuk Paslon 1, lalu isinya diubah menjadi Paslon 2 sebelum dikirim. **DITOLAK**: signature tidak cocok.

## 3.4 Uji Manipulasi Data Block Lama

```powershell
python client.py tamper localhost:5002 1
python client.py validate localhost:5002
```

`tamper` (khusus demo) mengubah pilihan di Block 1 pada Node 2 tanpa menghitung ulang hash. `validate` mendeteksi manipulasi dan menyebutkan block pertama yang rusak. Node lain tetap valid karena hanya Node 2 yang diubah.

## 3.5 Uji Block Palsu (Tanpa Proof of Work)

```powershell
python client.py palsu localhost:5001
```

Client mengirim block dengan transaksi sah tetapi tanpa Proof of Work yang valid. **DITOLAK** dengan status HTTP 409 beserta alasannya.

## 3.6 Uji Node yang Sempat Mati

1. Matikan Node 3 (`Ctrl + C` di terminalnya).
2. Di Node 1, jalankan `vote` lalu `mine`.
3. Jalankan kembali Node 3 dengan perintah semula.
4. Jalankan `python client.py resolve localhost:5003`.
5. Cek dengan `python client.py chain localhost:5003`: rantainya kini sama dengan node lain.

---

# 📋 4. Urutan Demo 11 Checkpoint

Setiap bagian kode di `node.py` dan `client.py` ditandai komentar `[CHECKPOINT n]`.

| No | Peristiwa | Perintah | Dilihat di |
| --- | --- | --- | --- |
| 1 | Pembuatan identitas pengirim | `identitas <NIM>` | Terminal client |
| 2 | Transaksi dibuat dan ditandatangani | `vote ...` | Terminal client dan node |
| 3 | Verifikasi signature (dan penolakan) | `vote ...` dan `vote_ubah ...` | Terminal node dan client |
| 4 | Status pool | `vote ...` berulang, atau `pool ...` | Terminal node |
| 5 | Block candidate dari pool | `mine ...` | Terminal node |
| 6 | Proof of Work berjalan | `mine ...` | Terminal node |
| 7 | Block diterima rantai | `mine ...` | Terminal node |
| 8 | Validasi rantai normal | `validate ...` | Terminal client |
| 9 | Manipulasi data block lama | `tamper ...` lalu `validate ...` | Terminal client dan node |
| 10 | Broadcast dan sinkronisasi | `mine ...` pada Node 1, lalu skenario 3.6 | Terminal node asal dan tujuan |
| 11 | Penolakan block tidak sah | `palsu ...` | Terminal node dan client |

---

# 🐳 5. Menjalankan Menggunakan Docker

Pastikan **Docker Desktop** sudah aktif.

```powershell
docker compose up --build -d     # build dan jalankan semua node
docker compose ps                # cek status container
docker compose logs -f           # lihat log node (checkpoint tercetak di sini)
docker compose down              # hentikan dan hapus container
```

Client tetap dijalankan dari terminal lokal, misalnya:

```powershell
python client.py vote localhost:5001 "Paslon 1" "A11124012"
python client.py mine localhost:5001
python client.py tally localhost:5002
```

### Penyesuaian yang diperlukan untuk versi gabungan

* `Dockerfile` harus memasang library `cryptography` dan menyalin `node.py`, misalnya:

  ```dockerfile
  RUN pip install --no-cache-dir cryptography
  ```

* Daftar peer pada `docker-compose.yml` memakai nama service (misalnya `node2:5002`), bukan `localhost`.
* Perintah `add_peer` tidak cocok untuk Docker, jadi daftarkan peer lewat argumen saat node dijalankan.

---

# 🌐 6. Pengujian Blockchain Voting Menggunakan 2 Laptop

Menguji sistem secara **terdistribusi** menggunakan 2 laptop yang terhubung melalui hotspot.

* **Laptop A (Teman)**: Node 1 dan pembagi hotspot.
* **Laptop B (Kamu)**: terhubung ke hotspot, Node 2.

### Topologi Jaringan

```text
┌──────────────────────────────┐
│       Laptop A (Teman)       │
│  Hotspot, IP: 192.168.137.1  │
│  Node 1, Port: 5001          │
└──────────────┬───────────────┘
               │ Hotspot / Wi-Fi
┌──────────────▼───────────────┐
│        Laptop B (Kamu)       │
│  IP: 192.168.137.161         │
│  Node 2, Port: 5002          │
└──────────────────────────────┘
```

| Perangkat | Peran | IP Address | Port |
| --- | --- | --- | --- |
| Laptop A (Teman) | Node 1 / Hotspot | `192.168.137.1` | `5001` |
| Laptop B (Kamu) | Node 2 / Client | `192.168.137.161` | `5002` |

Cek alamat IP dengan `ipconfig` di masing-masing laptop. Jika berubah setelah hotspot dibuat ulang, gunakan alamat terbaru.

## 6.1 Windows Firewall

Izinkan koneksi masuk TCP pada port `5001` (Laptop A) dan `5002` (Laptop B):

* **Opsi A**: nonaktifkan Windows Defender Firewall sementara pada jaringan **Private**, lalu aktifkan kembali setelah pengujian.
* **Opsi B (lebih aman)**: buat **Inbound Rule** untuk port `5001` dan `5002`.

## 6.2 Menjalankan Node

Laptop A:

```powershell
python node.py 5001 192.168.137.161:5002
```

Laptop B:

```powershell
python node.py 5002 192.168.137.1:5001
```

Kedua node mendaftarkan peer **saat dijalankan** (jangan gunakan `add_peer`, karena alamat baliknya `127.0.0.1`).

## 6.3 Skenario

**Skenario 1: Laptop B mengirim suara, Laptop A menambang.**

```powershell
python client.py vote 192.168.137.1:5001 "Paslon 1" "F55125001"
python client.py mine 192.168.137.1:5001
```

Suara masuk pool Node 1 dan disebarkan ke Node 2. Setelah `mine`, block baru ditambang dan disebarkan ke Laptop B.

**Skenario 2: Laptop A mengirim suara ke Laptop B.**

```powershell
python client.py vote 192.168.137.161:5002 "Paslon 2" "C10123045"
python client.py mine 192.168.137.161:5002
```

**Skenario 3: rekapitulasi dan isi rantai** (dari laptop mana pun):

```powershell
python client.py tally 192.168.137.1:5001
python client.py chain 192.168.137.161:5002
```

**Skenario 4: double voting antar-laptop.**

```powershell
python client.py vote 192.168.137.1:5001 "Paslon 2" "F55125001"
```

Harus **DITOLAK**, meskipun NIM tersebut dikirim dari laptop berbeda.

**Skenario 5: Longest-Chain Rule.** Jika rantai kedua node berbeda:

```powershell
python client.py resolve 192.168.137.1:5001
```

> Catatan: file kunci `dompet_<NIM>.pem` tersimpan di laptop tempat `client.py` dijalankan.

---

# 📌 Ringkasan Perintah

| Perintah | Fungsi |
| --- | --- |
| `python node.py <port> [peers] [difficulty]` | Menjalankan node |
| `python client.py identitas <NIM>` | Membuat/melihat identitas voter |
| `python client.py vote <node> <Paslon> <NIM>` | Membuat, menandatangani, dan mengirim suara ke pool |
| `python client.py vote_ubah <node> <Paslon> <PaslonDiubah> <NIM>` | Uji suara yang diubah setelah ditandatangani |
| `python client.py pool <node>` | Melihat suara pending |
| `python client.py mine <node>` | Membentuk block dari pool + Proof of Work |
| `python client.py chain <node>` | Melihat blockchain |
| `python client.py validate <node>` | Validasi seluruh rantai |
| `python client.py tally <node>` | Rekapitulasi suara |
| `python client.py tamper <node> <index>` | Demo: ubah data block lama |
| `python client.py add_peer <node> <peer>` | Menghubungkan dua node (satu komputer) |
| `python client.py resolve <node>` | Longest-Chain Rule |
| `python client.py palsu <node>` | Uji block tanpa Proof of Work |
| `docker compose up --build -d` / `ps` / `down` | Menjalankan, mengecek, dan menghentikan jaringan Docker |

---

# 📝 Catatan

* Jalankan seluruh node sebelum menggunakan `client.py`.
* Setiap node harus menggunakan **port yang berbeda**, dan port tidak boleh dipakai aplikasi lain.
* `vote` hanya memasukkan suara ke pool. Jalankan `mine` agar suara masuk blockchain.
* Hapus file `dompet_*.pem` jika ingin membuat identitas baru. **Jangan membagikan file ini**, karena berisi private key.
* `tamper` hanya untuk demo checkpoint 9, bukan fitur sistem sesungguhnya.
* Node belum memeriksa bahwa NIM benar-benar milik pemilik kunci (hanya memeriksa format NIM dan tanda tangan). Ini keterbatasan yang sebaiknya dicatat di laporan.
* Setelah selesai pengujian dua laptop, aktifkan kembali Windows Defender Firewall jika sebelumnya dinonaktifkan.
