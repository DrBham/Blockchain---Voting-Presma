# Panduan Checkpoint Blockchain dengan 2 Laptop

Panduan ini menjalankan seluruh checkpoint `node.py` dan `client.py` melalui dua laptop dalam jaringan yang sama.

## Topologi jaringan yang digunakan

- Laptop A: `192.168.137.1`, node port `5001`
- Laptop B: `192.168.137.253`, node port `5002`
- Difficulty: `4`, sehingga hash Proof of Work harus diawali `0000`

Semua perintah di bawah memakai alamat IPv4 tersebut, bukan `localhost`.

## 1. Persiapan kedua laptop

Salin `node.py` dan `client.py` ke folder yang sama pada kedua laptop. Buka PowerShell pada folder tersebut.

Pasang dependensi:

```powershell
python -m pip install cryptography
```

Cek alamat IPv4:

```powershell
ipconfig
```

Pastikan kedua laptop terhubung ke Wi-Fi atau hotspot yang sama. Uji koneksi dari kedua arah:

```powershell
# Jalankan dari Laptop A
ping 192.168.137.253

# Jalankan dari Laptop B
ping 192.168.137.1
```

Jika Windows Firewall meminta izin, izinkan Python pada jaringan **Private**. Jika tidak muncul, buka PowerShell sebagai Administrator dan jalankan aturan sesuai laptop:

```powershell
# Laptop A
New-NetFirewallRule -DisplayName "Blockchain Node 5001" -Direction Inbound -Protocol TCP -LocalPort 5001 -Action Allow

# Laptop B
New-NetFirewallRule -DisplayName "Blockchain Node 5002" -Direction Inbound -Protocol TCP -LocalPort 5002 -Action Allow
```

## 2. Jalankan dua node

Buka terminal pertama pada Laptop A:

```powershell
python node.py 5001 192.168.137.253:5002 4
```

Buka terminal pertama pada Laptop B:

```powershell
python node.py 5002 192.168.137.1:5001 4
```

Kedua perintah langsung mendaftarkan peer memakai IP jaringan. Jangan gunakan `127.0.0.1` untuk peer di laptop lain.

Setelah node hidup, uji port:

```powershell
# Dari Laptop A
Test-NetConnection 192.168.137.253 -Port 5002

# Dari Laptop B
Test-NetConnection 192.168.137.1 -Port 5001
```

Nilai `TcpTestSucceeded` harus `True`.

## 3. Jalankan seluruh checkpoint

Jalankan perintah berikut dari terminal kedua Laptop A, kecuali jika tertulis lain.

### Checkpoint 1 — Pembuatan identitas pengirim

```powershell
python client.py identitas F55125001
```

Hasil yang diperiksa:

- identitas voter tampil;
- alamat dan potongan public key tampil;
- private key tersimpan lokal dalam `dompet_F55125001.pem`.

### Checkpoint 2 dan 3 — Transaksi ditandatangani dan diverifikasi

Kirim transaksi valid ke node Laptop A:

```powershell
python client.py vote 192.168.137.1:5001 "Paslon 1" F55125001
```

Hasil yang diperiksa:

- client membuat signature menggunakan private key lokal;
- node Laptop A menampilkan `Signature VALID`;
- transaksi masuk ke pool dan disiarkan ke Laptop B.

Uji perubahan transaksi setelah ditandatangani menggunakan NIM baru:

```powershell
python client.py vote_ubah 192.168.137.1:5001 "Paslon 1" "Paslon 2" F55125002
```

Hasil yang diharapkan: transaksi ditolak karena `signature tidak cocok`.

### Checkpoint 4 — Status transaction pool

Periksa pool kedua node:

```powershell
python client.py pool 192.168.137.1:5001
python client.py pool 192.168.137.253:5002
```

Transaksi valid `F55125001 -> Paslon 1` harus terlihat pada kedua node.

### Checkpoint 5, 6, dan 7 — Block candidate, Proof of Work, dan penerimaan block

Tambang pool pada Laptop A:

```powershell
python client.py mine 192.168.137.1:5001
```

Periksa terminal node Laptop A. Terminal harus menampilkan:

- `BLOCK CANDIDATE`;
- jumlah percobaan nonce;
- nonce yang ditemukan;
- hash yang diawali `0000`;
- `BLOCK DITERIMA RANTAI`.

Periksa rantai kedua node:

```powershell
python client.py chain 192.168.137.1:5001
python client.py chain 192.168.137.253:5002
```

Block baru harus tampil pada kedua node. Terminal Laptop B juga harus mencatat penerimaan block dari peer.

### Checkpoint 8 — Validasi rantai normal

```powershell
python client.py validate 192.168.137.1:5001
python client.py validate 192.168.137.253:5002
```

Hasil yang diharapkan: `Rantai VALID` pada kedua node.

### Checkpoint 10 — Broadcast dan sinkronisasi longest-chain

Broadcast transaksi dan block sudah terlihat pada Checkpoint 2–7. Gunakan langkah berikut untuk menguji node yang tertinggal.

1. Hentikan node Laptop B dengan `Ctrl+C`.
2. Saat Laptop B mati, jalankan pada Laptop A:

```powershell
python client.py vote 192.168.137.1:5001 "Paslon 2" F55125003
python client.py mine 192.168.137.1:5001
```

3. Jalankan kembali node Laptop B:

```powershell
python node.py 5002 192.168.137.1:5001 4
```

4. Pada terminal kedua Laptop B, ambil rantai terpanjang dari Laptop A:

```powershell
python client.py resolve 192.168.137.253:5002
python client.py chain 192.168.137.253:5002
python client.py validate 192.168.137.253:5002
```

Hasil yang diharapkan: rantai Laptop B diganti dengan rantai valid dan lebih panjang milik Laptop A.

> Data blockchain hanya disimpan di memori. Node yang dimatikan lalu dijalankan kembali mulai dari genesis block dan perlu menjalankan `resolve`.

### Checkpoint 11 — Penolakan block tanpa Proof of Work valid

Jalankan terhadap node Laptop A yang masih memiliki rantai valid:

```powershell
python client.py palsu 192.168.137.1:5001
```

Hasil yang diharapkan:

- block palsu ditolak;
- status HTTP `409`;
- alasan menyebut Proof of Work tidak valid.

### Checkpoint 9 — Deteksi manipulasi data block lama

Jalankan terakhir karena perintah ini sengaja merusak rantai pada Laptop B:

```powershell
python client.py tamper 192.168.137.253:5002 1
python client.py validate 192.168.137.253:5002
```

Hasil yang diharapkan:

- pilihan dalam block index `1` berubah;
- hash tersimpan tidak lagi cocok dengan isi block;
- validasi menampilkan `Rantai TIDAK VALID` dan index block pertama yang rusak.

Rantai Laptop A tetap valid karena manipulasi hanya dilakukan pada Laptop B.

## 4. Perintah pemeriksaan tambahan

```powershell
# Daftar peer
Invoke-RestMethod http://192.168.137.1:5001/peers

# Rekap suara Laptop A
python client.py tally 192.168.137.1:5001

# Rekap suara Laptop B
python client.py tally 192.168.137.253:5002
```

## 5. Masalah umum

### `ModuleNotFoundError: No module named 'cryptography'`

```powershell
python -m pip install cryptography
```

### `TcpTestSucceeded : False`

Pastikan:

- kedua laptop memakai jaringan yang sama;
- IP tujuan benar;
- kedua node masih berjalan;
- port `5001` dan `5002` diizinkan Windows Firewall;
- jaringan tidak mengaktifkan client isolation atau AP isolation.

### `Tidak dapat terhubung ke node`

Gunakan `127.0.0.1` hanya untuk node pada laptop yang sedang dipakai. Gunakan IPv4 laptop tujuan untuk koneksi antarlaptop.

### Transaksi ditolak karena NIM sudah memilih

Gunakan NIM valid yang berbeda untuk setiap transaksi baru, misalnya `F55125001`, `F55125002`, dan `F55125003`.
