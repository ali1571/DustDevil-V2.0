import hashlib
import hmac
import base58
import os
import sys
from nacl.signing import SigningKey
from nacl.encoding import RawEncoder
from solders.pubkey import Pubkey
from multiprocessing import Pool, cpu_count
import time

# ── Base directory ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
WORDLIST_PATH   = os.path.join(BASE_DIR, "KEYTOWORD.txt")
OUTPUT_LOG_PATH = os.path.join(BASE_DIR, "solana_wallets.txt")


# ── Load wordlist once at module level (shared across processes) ───────────────
def load_wordlist():
    with open(WORDLIST_PATH, "r") as f:
        words = f.read().split()
    assert len(words) == 2048, f"Wordlist must have 2048 words, got {len(words)}"
    return words

WORDLIST = load_wordlist()


# ── BIP39: Generate mnemonic ───────────────────────────────────────────────────
def generate_mnemonic():
    entropy = os.urandom(16)
    digest = hashlib.sha256(entropy).digest()
    checksum_bits = f"{digest[0]:08b}"[:4]
    entropy_bits = bin(int.from_bytes(entropy, 'big'))[2:].zfill(128)
    full_bits = entropy_bits + checksum_bits
    mnemonic = [WORDLIST[int(full_bits[i*11:(i+1)*11], 2)] for i in range(12)]
    return " ".join(mnemonic)


# ── BIP39: Mnemonic → 512-bit seed ────────────────────────────────────────────
def mnemonic_to_seed(mnemonic, passphrase=""):
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        ("mnemonic" + passphrase).encode("utf-8"),
        iterations=2048,
        dklen=64
    )


# ── SLIP-0010: Seed → master Ed25519 keys ─────────────────────────────────────
def derive_master_keys(seed):
    master = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    return master[:32], master[32:]


# ── BIP32: Hardened child key derivation ──────────────────────────────────────
def derive_child_key(parent_key, parent_chain_code, index):
    if index < 0x80000000:
        index += 0x80000000
    data = b'\x00' + parent_key + index.to_bytes(4, 'big')
    child = hmac.new(parent_chain_code, data, hashlib.sha512).digest()
    return child[:32], child[32:]


# ── Walk derivation path ───────────────────────────────────────────────────────
def derive_path(seed, path):
    private_key, chain_code = derive_master_keys(seed)
    for part in path.replace('m/', '').split('/'):
        index = int(part[:-1]) if part.endswith("'") else int(part)
        private_key, chain_code = derive_child_key(private_key, chain_code, index)
    return private_key


# ── Private key → Solana address ──────────────────────────────────────────────
def private_key_to_address(private_key_bytes):
    signing_key = SigningKey(private_key_bytes)
    pub = signing_key.verify_key.encode(encoder=RawEncoder)
    return pub.hex(), base58.b58encode(pub).decode('utf-8')


# ── Single wallet generation — runs inside each worker process ─────────────────
def generate_single_wallet(account_gap_limit):
    mnemonic = generate_mnemonic()
    seed     = mnemonic_to_seed(mnemonic)
    accounts = []

    for account in range(account_gap_limit):
        path             = f"m/44'/501'/{account}'/0'"
        priv             = derive_path(seed, path)
        pub_hex, address = private_key_to_address(priv)
        accounts.append({
            "path":        path,
            "private_key": priv.hex(),
            "public_key":  pub_hex,
            "address":     address,
        })

    return {"mnemonic": mnemonic, "accounts": accounts}


# ── Batch generation with multiprocessing + live progress bar ─────────────────
def generate_wallets(n, account_gap_limit=1):
    workers   = cpu_count()
    bar_width = 40
    wallets   = []
    done      = 0

    print(f"Using {workers} CPU cores...\n")

    with Pool(processes=workers) as pool:
        args = [account_gap_limit] * n
        for wallet in pool.imap_unordered(generate_single_wallet, args, chunksize=50):
            wallets.append(wallet)
            done += 1
            filled = int(bar_width * done / n)
            bar    = "█" * filled + "░" * (bar_width - filled)
            print(f"\r[{bar}] {done}/{n} ({done/n*100:.1f}%)", end="", flush=True)

    print()
    return wallets


# ── Save wallets to file ───────────────────────────────────────────────────────
import json

def save_wallets(wallets):
    with open(OUTPUT_LOG_PATH, "a") as f:
        for w in wallets:
            f.write(json.dumps(w) + "\n")  # one line per wallet


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Solana HD Wallet Generator")
    print("=" * 60)

    n   = int(input("\nHow many wallets to generate? ").strip())
    gap = int(input("Accounts per wallet (default 1): ").strip() or "1")
    start_time = time.time()
    wallets = generate_wallets(n, account_gap_limit=gap)

    # Print first 5 only — avoid flooding terminal for large batches
    for i, w in enumerate(wallets[:5]):
        print(f"\nWallet {i+1}: {w['mnemonic']}")
        for acc in w["accounts"]:
            print(f"  {acc['address']}")
    if n > 5:
        print(f"\n  ... and {n - 5} more. Check {OUTPUT_LOG_PATH}")

    save_wallets(wallets)
    endtime = time.time()
    print(endtime -start_time)


if __name__ == "__main__":
    main()