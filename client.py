# client.py -- Alat bantu perintah voting UNTAD
#
# Private key voter dibuat dan disimpan LOKAL di file dompet_<NIM>.pem.
# Yang dikirim ke node hanya transaksi yang sudah ditandatangani + public key.
#
# File ini mengimpor class dari node.py, jadi letakkan keduanya di folder yang sama.
#
# Bagian client dari peta checkpoint (peta lengkap ada di node.py):
#  CP1  identitas -> Dompet.tampilkan_identitas   CP2  tanda tangan -> Dompet.buat_transaksi
#  CP3  perintah vote / vote_ubah   CP4  perintah pool   CP5-7 perintah mine
#  CP8  perintah validate   CP9  perintah tamper + validate
#  CP10 perintah add_peer / resolve   CP11 perintah palsu

import json
import os
import sys
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from node import Block, Transaksi, alamat_dari_pem


# ============================================================
# CLASS DOMPET  (identitas + kunci voter)
# ============================================================

class Dompet:
    def __init__(self, nim):
        self.nim = nim.upper().strip()
        self.berkas = f"dompet_{self.nim}.pem"

        if os.path.exists(self.berkas):
            with open(self.berkas, "rb") as f:
                self.private_key = serialization.load_pem_private_key(f.read(), password=None)
            self.baru = False
        else:
            self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with open(self.berkas, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            try:
                os.chmod(self.berkas, 0o600)
            except OSError:
                pass
            self.baru = True

        self.public_key_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def alamat(self):
        return alamat_dari_pem(self.public_key_pem)

    # [CHECKPOINT 1] Pembuatan identitas: alamat/public key (dipotong) tercetak,
    # beserta keterangan private key disimpan lokal
    def tampilkan_identitas(self):
        isi_kunci = "".join(self.public_key_pem.strip().splitlines()[1:-1])
        status = "dibuat" if self.baru else "dipakai kembali"
        print(f"Identitas voter {self.nim} ({status})")
        print(f"  Alamat     : {self.alamat()}")
        print(f"  Public key : {isi_kunci[:40]}...")
        print(f"  Private key: disimpan lokal di '{self.berkas}' (tidak dikirim ke node)")

    # [CHECKPOINT 2] Transaksi dibuat dan ditandatangani dengan private key lokal
    def buat_transaksi(self, kandidat):
        tx = Transaksi(self.nim, kandidat, self.public_key_pem)
        tx.tanda_tangani(self.private_key)
        return tx


# ============================================================
# KOMUNIKASI KE NODE
# ============================================================

def panggil(url, data=None):
    """Mengembalikan (kode_http, isi_json). Tidak melempar error untuk status 4xx/5xx."""
    if data is None:
        permintaan = urllib.request.Request(url)
    else:
        permintaan = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(permintaan, timeout=120) as balasan:
            return balasan.status, json.loads(balasan.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {}


def ringkas(chain):
    for b in chain:
        print(f"  Block {b['index']} | nonce: {str(b['nonce']).ljust(8)} "
              f"| prev: {b['previous_hash'][:12]}... | hash: {b['hash'][:12]}... "
              f"| {len(b['transaksi'])} transaksi")
        for t in b["transaksi"]:
            print(f"      - {t['voter_id']} -> {t['kandidat']} | sig {t['signature'][:16]}...")


# [CHECKPOINT 3] Hasil verifikasi dari node: diterima ke pool, atau ditolak beserta alasannya
# [CHECKPOINT 4] Jumlah transaksi pending di pool ikut tercetak
def kirim_transaksi(alamat, tx):
    kode, hasil = panggil(f"http://{alamat}/transaksi", tx.to_dict())
    if kode in (200, 201):
        print(f"Transaksi DITERIMA node: {hasil['pesan']} (pending di pool: {hasil['pool']})")
    else:
        print(f"Transaksi DITOLAK node (HTTP {kode}): {hasil.get('error')}")


# ============================================================
# PERINTAH
# ============================================================

BANTUAN = """Perintah:
  identitas <NIM>                               buat/lihat identitas voter
  vote <node> <Paslon> <NIM>                    buat, tanda tangani, kirim suara ke pool
  vote_ubah <node> <Paslon> <PaslonDiubah> <NIM>  suara diubah SETELAH ditandatangani (harus ditolak)
  pool <node>                                   lihat transaksi pending
  mine <node>                                   bentuk block dari pool + proof of work
  chain <node>                                  lihat rantai
  validate <node>                               validasi seluruh rantai
  tally <node>                                  rekap suara
  tamper <node> <index>                         DEMO: ubah suara di block lama
  add_peer <node> <peer>                        hubungkan dua node (dua arah)
  resolve <node>                                longest-chain rule
  palsu <node>                                  kirim block tanpa PoW valid (harus ditolak)"""


def main():
    if len(sys.argv) < 3:
        print(BANTUAN)
        return

    perintah = sys.argv[1]
    arg = sys.argv[2:]

    if perintah == "identitas":
        Dompet(arg[0]).tampilkan_identitas()
        return

    alamat = arg[0]

    if perintah == "vote":
        kandidat = arg[1] if len(arg) > 1 else "Paslon 1"
        nim = arg[2] if len(arg) > 2 else "F55125001"
        dompet = Dompet(nim)
        dompet.tampilkan_identitas()
        tx = dompet.buat_transaksi(kandidat)
        print(f"Transaksi dibuat dan ditandatangani: {tx.voter_id} -> {tx.kandidat}")
        print(f"  Signature: {tx.signature[:32]}...")
        kirim_transaksi(alamat, tx)

    # [CHECKPOINT 3] Transaksi diubah SETELAH ditandatangani -> harus ditolak node
    elif perintah == "vote_ubah":
        asli, diubah, nim = arg[1], arg[2], arg[3]
        dompet = Dompet(nim)
        tx = dompet.buat_transaksi(asli)
        print(f"Transaksi ditandatangani untuk '{asli}', lalu isinya diubah menjadi '{diubah}'")
        tx.kandidat = diubah
        kirim_transaksi(alamat, tx)

    # [CHECKPOINT 4] Status pool
    elif perintah == "pool":
        _, hasil = panggil(f"http://{alamat}/pool")
        print(f"Transaksi pending di {alamat}: {hasil['jumlah']}")
        for t in hasil["transaksi"]:
            print(f"  - {t['voter_id']} -> {t['kandidat']} | sig {t['signature'][:16]}...")

    # [CHECKPOINT 5, 6, 7] Membentuk block dari pool, proof of work, block diterima rantai
    # (rincian lengkapnya tercetak di console node)
    elif perintah == "mine":
        kode, hasil = panggil(f"http://{alamat}/mine", {})
        if kode == 201:
            b = hasil["block"]
            print(f"{hasil['pesan']}: Block {b['index']} (nonce {b['nonce']}, hash {b['hash'][:20]}...)")
        else:
            print(f"Gagal menambang: {hasil.get('error')}")

    elif perintah == "chain":
        _, hasil = panggil(f"http://{alamat}/chain")
        print(f"Panjang rantai di {alamat}: {hasil['panjang']} block")
        ringkas(hasil["chain"])

    # [CHECKPOINT 8] Rantai normal -> valid. [CHECKPOINT 9] Setelah tamper -> index block rusak + alasan
    elif perintah == "validate":
        _, hasil = panggil(f"http://{alamat}/validate")
        if hasil["valid"]:
            print(f"Rantai VALID untuk seluruh {hasil['panjang']} block")
        else:
            print(f"Rantai TIDAK VALID. Block pertama yang rusak: index {hasil['index_rusak']}")
            print(f"Alasan: {hasil['alasan']}")

    elif perintah == "tally":
        _, hasil = panggil(f"http://{alamat}/tally")
        print(f"Total Suara Masuk: {hasil['total_suara']}")
        print("Hasil Rekapitulasi Suara:")
        for k, v in hasil["rekap_suara"].items():
            print(f"  - {k}: {v} suara")

    # [CHECKPOINT 9] Manipulasi data block lama (khusus demo)
    elif perintah == "tamper":
        kode, hasil = panggil(f"http://{alamat}/tamper", {"index": int(arg[1])})
        print(hasil.get("pesan") or hasil.get("error"))

    # [CHECKPOINT 10] Menghubungkan node (syarat broadcast antar-node)
    elif perintah == "add_peer":
        kode, hasil = panggil(f"http://{alamat}/peers", {"peer": arg[1]})
        print(hasil.get("pesan") or hasil.get("error"))

    # [CHECKPOINT 10] Sinkronisasi: node yang tertinggal mengambil rantai terpanjang
    elif perintah == "resolve":
        _, hasil = panggil(f"http://{alamat}/resolve")
        if hasil["rantai_diganti"]:
            print(f"Rantai diganti. Panjang sekarang: {hasil['panjang']} block")
        else:
            print(f"Rantai tidak berubah. Panjang: {hasil['panjang']} block")

    # [CHECKPOINT 11] Block tanpa proof of work valid -> harus ditolak node
    elif perintah == "palsu":
        _, data = panggil(f"http://{alamat}/chain")
        terakhir = Block.from_dict(data["chain"][-1])
        target = "0" * data["difficulty"]

        # Block ini rapi dan transaksinya bertanda tangan sah; satu-satunya yang salah: tidak ada PoW.
        tx = Dompet("F55125999").buat_transaksi("Paslon 1")
        block = Block(terakhir.index + 1, [tx], terakhir.hash)
        block.nonce = 1
        block.hash = block.hitung_hash()
        while block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.hitung_hash()

        kode, hasil = panggil(f"http://{alamat}/block", block.to_dict())
        if kode == 200:
            print("Block palsu DITERIMA -- validasi node bermasalah.")
        else:
            print(f"Block palsu DITOLAK oleh node. Status HTTP: {kode}")
            print(f"Alasan: {hasil.get('error')}")

    else:
        print(BANTUAN)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"Tidak dapat terhubung ke node ({e.reason}). Pastikan node sudah berjalan.")
    except IndexError:
        print("Argumen kurang.\n")
        print(BANTUAN)
