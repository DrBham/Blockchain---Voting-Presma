# node.py -- Node Voting Blockchain Terdistribusi Universitas Tadulako
#
# Gabungan dari:
#   - blockchain_voting.py : transaksi bertanda tangan (RSA-PSS), transaction pool, validasi chain
#   - node.py lama         : aturan NIM UNTAD, jaringan antar-node, longest-chain rule
#
# Susunan class:
#   Transaksi   -> satu suara, ditandatangani voter
#   Block       -> kumpulan transaksi + previous_hash + nonce + hash
#   Blockchain  -> rantai block, transaction pool, validasi, proof of work
#   Node        -> Blockchain + daftar peer + komunikasi ke node lain
#
# Cara menjalankan:
#   python node.py <port> [peer1,peer2,...] [difficulty]
#   contoh: python node.py 5001 127.0.0.1:5002,127.0.0.1:5003 4

# ============================================================
# PETA CHECKPOINT (Bagian D) -> LOKASI KODE
# Cari tulisan "[CHECKPOINT n]" di file untuk melihat bagian kodenya.
#
#  No  Peristiwa                         Kode          Dimana tercetak
#  1   Pembuatan identitas pengirim      client.py     console client
#  2   Transaksi dibuat & ditandatangani client.py     console client + console node
#  3   Verifikasi signature (+ tolak)    node.py       console node + console client
#  4   Status pool                       node.py       console node (+ perintah pool)
#  5   Block candidate dari pool         node.py       console node
#  6   Proof of work berjalan            node.py       console node
#  7   Block diterima rantai             node.py       console node
#  8   Validasi rantai normal            node.py       perintah validate
#  9   Manipulasi data block lama        node.py       perintah tamper + validate
#  10  Broadcast & sinkronisasi          node.py       console node asal, tujuan, resolve
#  11  Penolakan block tidak sah         node.py       console node + perintah palsu
# ============================================================

import hashlib
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PORT = 0  # diisi saat node dijalankan, dipakai untuk awalan log

# --- Aturan & Konfigurasi Voting UNTAD ---
PASLON_VALID = ["Paslon 1", "Paslon 2"]
ANGKATAN_VALID = ["23", "24", "25"]  # Angkatan 2023 (Sem 7), 2024 (Sem 5), 2025 (Sem 3)
FAKULTAS_UNTAD = ["A", "B", "C", "D", "E", "F", "G", "K", "L", "N", "P"]


def log(pesan):
    """Cetak pesan ke console node dengan awalan [port]."""
    print(f"[{PORT}] {pesan}", flush=True)


def validasi_nim_untad(nim):
    """
    Format NIM UNTAD: [Kode Fakultas][3 Digit Prodi][2 Digit Tahun][3 Digit No Urut]
    Contoh: F55125001 -> Fakultas 'F', Angkatan '25'
    """
    nim = nim.upper().strip()
    if len(nim) < 8:
        return False, "Format NIM terlalu pendek!"

    kode_fakultas = nim[0]
    if kode_fakultas not in FAKULTAS_UNTAD:
        return False, f"Kode Fakultas '{kode_fakultas}' tidak terdaftar di UNTAD!"

    angkatan = nim[4:6] if len(nim) >= 9 else nim[1:3]
    if angkatan not in ANGKATAN_VALID:
        return False, f"Angkatan '20{angkatan}' tidak memenuhi syarat (Hanya Semester 3-7 / Angkatan 2023-2025)!"

    return True, "Valid"


def alamat_dari_pem(public_key_pem):
    """Alamat pengirim = potongan hash SHA-256 dari public key."""
    return hashlib.sha256(public_key_pem.encode()).hexdigest()[:40]


def _padding_pss():
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


# ============================================================
# 1. CLASS TRANSAKSI  (satu suara)
# [FITUR WAJIB: Transaksi bertanda tangan] ditandatangani private key pengirim,
# diverifikasi node sebelum diterima.
# ============================================================

class Transaksi:
    def __init__(self, voter_id, kandidat, public_key, timestamp=None, signature=""):
        self.voter_id = voter_id          # NIM
        self.kandidat = kandidat          # "Paslon 1" / "Paslon 2"
        self.public_key = public_key      # public key voter (teks PEM)
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.signature = signature        # tanda tangan dalam bentuk hex

    def pesan(self):
        """Isi yang ditandatangani. Kalau salah satu isinya diubah, signature jadi tidak cocok."""
        return json.dumps({
            "voter_id": self.voter_id,
            "kandidat": self.kandidat,
            "timestamp": self.timestamp,
        }, sort_keys=True).encode()

    # [CHECKPOINT 2] Transaksi ditandatangani dengan private key pengirim (dipanggil dari client.py)
    def tanda_tangani(self, private_key):
        """Dipanggil di sisi client (private key tidak pernah dikirim ke node)."""
        self.signature = private_key.sign(self.pesan(), _padding_pss(), hashes.SHA256()).hex()

    # [CHECKPOINT 3] Node memverifikasi signature saat transaksi masuk
    def verifikasi(self):
        """Dipanggil node: benarkah signature dibuat oleh pemilik public key ini?"""
        try:
            kunci = serialization.load_pem_public_key(self.public_key.encode())
            kunci.verify(bytes.fromhex(self.signature), self.pesan(), _padding_pss(), hashes.SHA256())
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    def alamat(self):
        return alamat_dari_pem(self.public_key)

    def to_dict(self):
        return {
            "voter_id": self.voter_id,
            "kandidat": self.kandidat,
            "timestamp": self.timestamp,
            "public_key": self.public_key,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["voter_id"], d["kandidat"], d["public_key"], d["timestamp"], d["signature"])


# [CHECKPOINT 3] Aturan penerimaan transaksi. Transaksi yang isinya diubah setelah
# ditandatangani GAGAL di sini dan ditolak dengan alasan yang dikembalikan.
def validasi_transaksi(tx):
    """Aturan satu transaksi (dipakai saat masuk pool maupun saat memeriksa block)."""
    if tx.kandidat not in PASLON_VALID:
        return False, f"Kandidat '{tx.kandidat}' tidak valid. Pilihan resmi: {', '.join(PASLON_VALID)}"
    nim_valid, pesan_err = validasi_nim_untad(str(tx.voter_id))
    if not nim_valid:
        return False, f"NIM '{tx.voter_id}' ditolak: {pesan_err}"
    if not tx.verifikasi():
        return False, "signature tidak cocok (isi transaksi diubah setelah ditandatangani atau kunci salah)"
    return True, "valid"


# ============================================================
# 2. CLASS BLOCK
# ============================================================

# [FITUR WAJIB: Struktur block] index, timestamp, daftar transaksi, previous hash, nonce, hash
class Block:
    def __init__(self, index, transaksi, previous_hash, timestamp=None, nonce=0, hash_nilai=None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transaksi = transaksi          # list objek Transaksi
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash_nilai if hash_nilai is not None else self.hitung_hash()

    def hitung_hash(self):
        data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transaksi": [t.to_dict() for t in self.transaksi],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    # [FITUR WAJIB: Proof of Work] nonce dicari terhadap difficulty, disimpan sebagai atribut block
    # [CHECKPOINT 6] Mengembalikan jumlah percobaan dan lama waktu untuk dicetak di tambang_pool()
    def tambang(self, difficulty):
        """Proof of Work: naikkan nonce sampai hash diawali nol sebanyak difficulty.
        Mengembalikan (jumlah percobaan, lama detik)."""
        target = "0" * difficulty
        mulai = time.time()
        self.nonce = 0
        while True:
            self.hash = self.hitung_hash()
            if self.hash.startswith(target):
                break
            self.nonce += 1
        return self.nonce + 1, time.time() - mulai

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transaksi": [t.to_dict() for t in self.transaksi],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            index=d["index"],
            transaksi=[Transaksi.from_dict(t) for t in d["transaksi"]],
            previous_hash=d["previous_hash"],
            timestamp=d["timestamp"],
            nonce=d["nonce"],
            hash_nilai=d["hash"],
        )


# [CHECKPOINT 11] Block tanpa proof of work valid ditolak di sini (alasan dikembalikan).
# [CHECKPOINT 9] Pemeriksaan hash/previous hash di sini juga yang mendeteksi data block yang diubah.
def validasi_block(block, induk, difficulty, voters_sebelumnya):
    """Periksa satu block terhadap block sebelumnya. Mengembalikan (ok, alasan)."""
    if block.index != induk.index + 1:
        if block.index > induk.index + 1:
            return False, f"index {block.index} melompat, node ini tertinggal (jalankan resolve)"
        return False, f"index {block.index} tidak sesuai, seharusnya {induk.index + 1}"
    if block.previous_hash != induk.hash:
        return False, "previous hash tidak cocok dengan hash block sebelumnya"
    if block.hash != block.hitung_hash():
        return False, "hash tidak cocok dengan isi block (data berubah)"
    target = "0" * difficulty
    if not block.hash.startswith(target):
        return False, f"proof of work tidak valid (hash tidak diawali {target})"
    if not block.transaksi:
        return False, "block tidak berisi transaksi"

    dilihat = set(voters_sebelumnya)
    for tx in block.transaksi:
        ok, alasan = validasi_transaksi(tx)
        if not ok:
            return False, alasan
        if tx.voter_id in dilihat:
            return False, f"NIM '{tx.voter_id}' memilih lebih dari sekali"
        dilihat.add(tx.voter_id)
    return True, "valid"


# [FITUR WAJIB: Validasi chain]
# [CHECKPOINT 8] Rantai normal -> (True, None, ...)
# [CHECKPOINT 9] Rantai dimanipulasi -> (False, index block pertama yang rusak, alasan)
def validasi_rantai(chain, difficulty):
    """Periksa seluruh rantai. Mengembalikan (ok, index_block_pertama_yang_rusak, alasan)."""
    genesis = Blockchain.buat_genesis()
    if not chain or chain[0].hash != genesis.hash or chain[0].hash != chain[0].hitung_hash():
        return False, 0, "genesis block tidak sah"

    voters = set()
    for i in range(1, len(chain)):
        ok, alasan = validasi_block(chain[i], chain[i - 1], difficulty, voters)
        if not ok:
            return False, i, alasan
        for tx in chain[i].transaksi:
            voters.add(tx.voter_id)
    return True, None, "rantai valid"


# ============================================================
# 3. CLASS BLOCKCHAIN
# ============================================================

class Blockchain:
    def __init__(self, difficulty=4):
        self.difficulty = difficulty
        self.chain = [self.buat_genesis()]
        self.pool = []                      # transaction pool (antrean suara pending)
        self.lock = threading.RLock()       # agar request yang datang bersamaan tidak saling tabrak

    @staticmethod
    def buat_genesis():
        # Timestamp dibuat tetap (0) supaya genesis SAMA di semua node.
        return Block(index=0, transaksi=[], previous_hash="0", timestamp=0)

    def terakhir(self):
        return self.chain[-1]

    def voters_di_rantai(self):
        return {tx.voter_id for b in self.chain for tx in b.transaksi}

    def sudah_memilih(self, voter_id):
        if voter_id in self.voters_di_rantai():
            return True
        return any(tx.voter_id == voter_id for tx in self.pool)

    # --- Transaksi & pool ---

    def tambah_transaksi(self, tx):
        """Mengembalikan (ok, pesan, baru). baru=False kalau transaksi ini sudah ada di pool."""
        with self.lock:
            if any(p.signature == tx.signature for p in self.pool):
                return True, "transaksi sudah ada di pool", False

            # [CHECKPOINT 2] Isi transaksi + potongan signature tercetak di console node
            log("=== TRANSAKSI MASUK ===")
            log(f"Pengirim : {tx.voter_id} (alamat {tx.alamat()[:12]}...)")
            log(f"Pilihan  : {tx.kandidat}")
            log(f"Signature: {tx.signature[:32]}...")

            # [CHECKPOINT 3] Verifikasi signature; kalau gagal, alasan penolakan dicetak
            ok, alasan = validasi_transaksi(tx)
            if not ok:
                log(f"DITOLAK: {alasan}")
                return False, alasan, False
            log("Signature VALID, transaksi sesuai aturan")

            if self.sudah_memilih(tx.voter_id):
                alasan = f"NIM '{tx.voter_id}' sudah menggunakan hak pilihnya!"
                log(f"DITOLAK: {alasan}")
                return False, alasan, False

            # [CHECKPOINT 4] Status pool: jumlah transaksi pending bertambah setiap transaksi sah masuk
            self.pool.append(tx)
            log(f"Transaksi masuk pool. Transaksi pending sekarang: {len(self.pool)}")
            return True, "transaksi diterima ke pool", True

    # --- Membentuk & menambang block ---

    def tambang_pool(self):
        """Bentuk block dari isi pool, jalankan PoW, tambahkan ke rantai. Mengembalikan block atau None."""
        with self.lock:
            if not self.pool:
                return None

            induk = self.terakhir()
            block = Block(index=len(self.chain), transaksi=list(self.pool), previous_hash=induk.hash)

            # [CHECKPOINT 5] Block candidate: daftar transaksi dan previous hash yang dipakai
            log("=== BLOCK CANDIDATE ===")
            log(f"Index         : {block.index}")
            log(f"Previous hash : {block.previous_hash[:20]}...")
            log(f"Transaksi ({len(block.transaksi)}):")
            for tx in block.transaksi:
                log(f"   - {tx.voter_id} -> {tx.kandidat} | sig {tx.signature[:16]}...")

            # [CHECKPOINT 6] Proof of work: jumlah percobaan, nonce, hash hasil, lama penambangan
            log(f"=== PROOF OF WORK (target: hash diawali {'0' * self.difficulty}) ===")
            percobaan, detik = block.tambang(self.difficulty)
            log(f"Percobaan nonce : {percobaan}")
            log(f"Nonce ditemukan : {block.nonce}")
            log(f"Hash hasil      : {block.hash}")
            log(f"Lama menambang  : {detik:.3f} detik")

            # [CHECKPOINT 7] Block diterima rantai: index baru, rantai bertambah panjang, pool dikosongkan
            self.chain.append(block)
            self.pool = []
            log("=== BLOCK DITERIMA RANTAI ===")
            log(f"Index block baru : {block.index}")
            log(f"Panjang rantai   : {len(self.chain)} block")
            log(f"Pool sekarang    : {len(self.pool)} transaksi (kosong)")
            return block

    # --- Menerima block dari node lain ---

    def terima_block(self, block):
        with self.lock:
            ok, alasan = validasi_block(block, self.terakhir(), self.difficulty, self.voters_di_rantai())
            if not ok:
                # [CHECKPOINT 11] Status penolakan block tidak sah tercetak (409)
                log(f"block {block.index} DITOLAK: {alasan} (status 409)")
                return False, alasan

            self.chain.append(block)
            suara_masuk = {tx.voter_id for tx in block.transaksi}
            self.pool = [tx for tx in self.pool if tx.voter_id not in suara_masuk]
            # [CHECKPOINT 10] Log PENERIMAAN di node tujuan
            log(f"block {block.index} DITERIMA dari peer | hash {block.hash[:20]}...")
            log(f"Panjang rantai: {len(self.chain)} | pool: {len(self.pool)} transaksi")
            return True, "block diterima"

    # --- Integritas ---

    # [CHECKPOINT 8 dan 9] Validasi rantai; hasilnya dicetak (valid, atau index block rusak + alasan)
    def periksa(self):
        with self.lock:
            ok, rusak, alasan = validasi_rantai(self.chain, self.difficulty)
        if ok:
            log(f"VALIDASI RANTAI: rantai valid untuk seluruh {len(self.chain)} block")
        else:
            log(f"VALIDASI RANTAI: TIDAK VALID. Block pertama yang rusak: index {rusak}. Alasan: {alasan}")
        return ok, rusak, alasan

    def rekap(self):
        hasil = {p: 0 for p in PASLON_VALID}
        total = 0
        with self.lock:
            for b in self.chain:
                for tx in b.transaksi:
                    if tx.kandidat in hasil:
                        hasil[tx.kandidat] += 1
                    total += 1
        return total, hasil

    # [CHECKPOINT 9] Memanipulasi data block lama (khusus demo), hash sengaja TIDAK dihitung ulang
    def ubah_data_demo(self, index):
        """HANYA UNTUK DEMO: mengubah pilihan di block lama tanpa menghitung ulang hash."""
        with self.lock:
            if index < 1 or index >= len(self.chain) or not self.chain[index].transaksi:
                return False, "index block tidak ada atau tidak berisi transaksi"
            tx = self.chain[index].transaksi[0]
            lama = tx.kandidat
            tx.kandidat = "Paslon 2" if lama == "Paslon 1" else "Paslon 1"
            log(f"DEMO MANIPULASI: block {index}, suara {tx.voter_id} diubah dari '{lama}' menjadi '{tx.kandidat}'")
            return True, f"suara di block {index} diubah dari '{lama}' menjadi '{tx.kandidat}'"


# ============================================================
# 4. CLASS NODE  (Blockchain + jaringan)
# ============================================================

def kirim_json(url, isi):
    data = json.dumps(isi).encode("utf-8")
    permintaan = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(permintaan, timeout=5) as balasan:
        return json.loads(balasan.read().decode("utf-8"))


def ambil_json(url):
    with urllib.request.urlopen(url, timeout=5) as balasan:
        return json.loads(balasan.read().decode("utf-8"))


class Node:
    def __init__(self, port, peers, difficulty):
        self.port = port
        self.peers = list(peers)
        self.blockchain = Blockchain(difficulty)

    # [CHECKPOINT 10] Broadcast transaksi antar-node (log pengiriman tercetak)
    def broadcast_transaksi(self, tx):
        isi = tx.to_dict()
        isi["diteruskan"] = True  # penanda agar penerima tidak menyebarkan ulang (hindari putaran tak berujung)
        for peer in self.peers:
            try:
                kirim_json(f"http://{peer}/transaksi", isi)
                log(f" -> transaksi {tx.voter_id} dikirim ke {peer}")
            except Exception as e:
                log(f" !! gagal mengirim transaksi ke {peer} ({e})")

    # [CHECKPOINT 10] Broadcast block antar-node: log PENGIRIMAN di node asal
    def broadcast_block(self, block):
        for peer in self.peers:
            try:
                kirim_json(f"http://{peer}/block", block.to_dict())
                log(f" -> block {block.index} dikirim ke {peer} (diterima)")
            except Exception as e:
                log(f" !! block {block.index} ke {peer} tidak diterima ({e})")

    def tambah_peer(self, peer, timbal_balik=True):
        if not peer or peer in self.peers:
            return False
        self.peers.append(peer)
        log(f"peer baru ditambahkan: {peer}")
        if timbal_balik:
            try:
                kirim_json(f"http://{peer}/peers", {"peer": f"127.0.0.1:{self.port}", "timbal_balik": False})
            except Exception as e:
                log(f" !! peer {peer} belum bisa menambahkan node ini ({e})")
        return True

    # [FITUR WAJIB: Longest-chain rule]
    # [CHECKPOINT 10] Sinkronisasi: node yang sempat mati memperoleh rantai terpanjang setelah resolve
    def resolve(self):
        """Longest-chain rule: ambil rantai terpanjang yang VALID dari peer."""
        bc = self.blockchain
        terpanjang = None
        panjang_maks = len(bc.chain)
        for peer in self.peers:
            try:
                data = ambil_json(f"http://{peer}/chain")
                rantai_peer = [Block.from_dict(b) for b in data["chain"]]
                ok, rusak, alasan = validasi_rantai(rantai_peer, bc.difficulty)
                if not ok:
                    log(f" !! rantai dari {peer} ditolak (block {rusak}: {alasan})")
                    continue
                log(f" -> {peer} punya rantai {len(rantai_peer)} block (valid)")
                if len(rantai_peer) > panjang_maks:
                    terpanjang, panjang_maks = rantai_peer, len(rantai_peer)
            except Exception as e:
                log(f" !! gagal menghubungi {peer} ({e})")

        if terpanjang is None:
            log(f"RESOLVE: rantai lokal ({len(bc.chain)} block) sudah yang terpanjang")
            return False

        with bc.lock:
            bc.chain = terpanjang
            sudah = bc.voters_di_rantai()
            bc.pool = [tx for tx in bc.pool if tx.voter_id not in sudah]
        log(f"RESOLVE: rantai diganti dengan rantai terpanjang ({len(terpanjang)} block)")
        return True


# ============================================================
# 5. ANTARMUKA HTTP
# ============================================================

NODE = None


class NodeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # matikan log bawaan http.server agar console bersih

    def _balas(self, kode, isi):
        badan = json.dumps(isi, indent=2).encode("utf-8")
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(badan)))
        self.end_headers()
        self.wfile.write(badan)

    def do_GET(self):
        bc = NODE.blockchain
        if self.path == "/chain":
            with bc.lock:
                self._balas(200, {
                    "panjang": len(bc.chain),
                    "difficulty": bc.difficulty,
                    "chain": [b.to_dict() for b in bc.chain],
                })
        elif self.path == "/pool":
            with bc.lock:
                self._balas(200, {"jumlah": len(bc.pool), "transaksi": [t.to_dict() for t in bc.pool]})
        elif self.path == "/validate":
            ok, rusak, alasan = bc.periksa()
            self._balas(200, {"valid": ok, "index_rusak": rusak, "alasan": alasan, "panjang": len(bc.chain)})
        elif self.path == "/tally":
            total, rekap = bc.rekap()
            self._balas(200, {"total_suara": total, "rekap_suara": rekap})
        elif self.path == "/resolve":
            log("menjalankan longest-chain rule")
            berubah = NODE.resolve()
            self._balas(200, {"rantai_diganti": berubah, "panjang": len(bc.chain)})
        elif self.path == "/peers":
            self._balas(200, {"peers": NODE.peers})
        else:
            self._balas(404, {"error": "endpoint tidak dikenal"})

    def do_POST(self):
        bc = NODE.blockchain
        panjang = int(self.headers.get("Content-Length", 0))
        try:
            isi = json.loads(self.rfile.read(panjang) or b"{}")
        except ValueError:
            self._balas(400, {"error": "isi permintaan bukan JSON"})
            return

        if self.path == "/transaksi":
            try:
                tx = Transaksi.from_dict(isi)
            except (KeyError, TypeError):
                self._balas(400, {"error": "format transaksi tidak lengkap"})
                return
            ok, pesan, baru = bc.tambah_transaksi(tx)
            if not ok:
                self._balas(400, {"error": pesan})
                return
            if baru and not isi.get("diteruskan"):
                NODE.broadcast_transaksi(tx)
            self._balas(201, {"pesan": pesan, "pool": len(bc.pool)})

        elif self.path == "/mine":
            block = bc.tambang_pool()
            if block is None:
                self._balas(400, {"error": "pool kosong, tidak ada transaksi untuk ditambang"})
                return
            NODE.broadcast_block(block)
            self._balas(201, {"pesan": "block berhasil ditambang dan ditambahkan", "block": block.to_dict()})

        elif self.path == "/block":
            try:
                block = Block.from_dict(isi)
            except (KeyError, TypeError):
                self._balas(409, {"pesan": "block ditolak", "error": "format block tidak lengkap"})
                return
            ok, alasan = bc.terima_block(block)
            if ok:
                self._balas(200, {"pesan": "block diterima"})
            else:
                self._balas(409, {"pesan": "block ditolak", "error": alasan})

        elif self.path == "/peers":
            peer_baru = isi.get("peer")
            if NODE.tambah_peer(peer_baru, isi.get("timbal_balik", True)):
                self._balas(200, {"pesan": f"peer {peer_baru} berhasil ditambahkan", "peers": NODE.peers})
            else:
                self._balas(400, {"error": "peer tidak valid atau sudah ada"})

        elif self.path == "/tamper":
            ok, pesan = bc.ubah_data_demo(int(isi.get("index", 0)))
            self._balas(200 if ok else 400, {"pesan" if ok else "error": pesan})

        else:
            self._balas(404, {"error": "endpoint tidak dikenal"})


if __name__ == "__main__":
    PORT = int(sys.argv[1])
    peers_awal = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
    difficulty = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    NODE = Node(PORT, peers_awal, difficulty)
    print(f"Node Voting UNTAD aktif di port {PORT}")
    print("Peers     : " + (", ".join(peers_awal) if peers_awal else "(belum ada)"))
    print(f"Difficulty: {difficulty} (hash harus diawali {'0' * difficulty})")
    print(f"Genesis   : {NODE.blockchain.chain[0].hash[:20]}...", flush=True)

    ThreadingHTTPServer(("0.0.0.0", PORT), NodeHandler).serve_forever()
