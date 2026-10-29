import os
import time
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ─────────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("HELIUS_API_KEY", "e677f341-1aea-4192-82c2-1191ae8643cc")
API_URL  = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"
OUT_FILE = "active_wallets.txt"

RUNNER_WORKERS = 2   # parallel programs  \
BATCH_WORKERS  = 5   # parallel tx fetches  → 10 concurrent requests total (free tier safe)
SIG_LIMIT      = 1000

PROGRAMS = {
    # DEXes
    "Pumpfun":          "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "Raydium AMM":      "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "Raydium CLMM":     "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "Raydium CPMM":     "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "Jupiter":          "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "Orca":             "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "Meteora":          "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",

    # Lending
    "Marginfi":         "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA",
    "Kamino":           "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD",
    "Solend":           "So1endDq2YkqhipRh3WViPa8hdiSpxWy6z3Z6tMCpAo",

    # Launchpads
    "Moonshot":         "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG",

    # Liquid Staking
    "Marinade":         "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD",
    "Jito":             "SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy",

    # Perps
    "Drift":            "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",

    # Token
    "USDT":             "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
}

# ── Shared state ───────────────────────────────────────────────────────────────

seen_lock = Lock()

# ── Core functions ─────────────────────────────────────────────────────────────

def load_existing_wallets():
    try:
        with open(OUT_FILE, "r") as f:
            wallets = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(wallets)} existing wallets from file")
        return wallets
    except FileNotFoundError:
        print("No existing wallet file found — starting fresh")
        return set()


def get_signatures(program_address):
    payload = {
        "jsonrpc": "2.0", "id": "1",
        "method": "getSignaturesForAddress",
        "params": [program_address, {"limit": SIG_LIMIT}]
    }
    try:
        r = requests.post(API_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        results = r.json().get("result", [])
        return [item["signature"] for item in results if item.get("err") is None]
    except Exception as e:
        print(f"  Failed to fetch signatures: {e}")
        return []


def fetch_single(sig):
    """Fetch one transaction and return the fee payer pubkey, or None."""
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTransaction",
        "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
    }

    retries = 0
    while retries < 5:
        try:
            r = requests.post(API_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            result = r.json()
        except Exception as e:
            print(f"\n  Request failed: {e}")
            time.sleep(2)
            retries += 1
            continue

        # rate limit
        if isinstance(result, dict) and result.get("error", {}).get("code") == -32413:
            wait = 2 ** retries
            print(f"\n  Rate limited — waiting {wait}s")
            time.sleep(wait)
            retries += 1
            continue

        tx = result.get("result")
        if tx:
            keys = tx["transaction"]["message"]["accountKeys"]
            signers = [k["pubkey"] for k in keys if k.get("signer")]
            if signers:
                return signers[0]
        return None

    return None  # exhausted retries


def batch_get_transactions(signatures, seen_wallets):
    """Fetch all signatures concurrently, save new wallets immediately."""
    total   = len(signatures)
    saved   = 0
    done    = 0

    with ThreadPoolExecutor(max_workers=BATCH_WORKERS) as executor:
        futures = {executor.submit(fetch_single, sig): sig for sig in signatures}

        for future in as_completed(futures):
            done += 1
            print(f"\r    Fetched {done}/{total} — {saved} new", end="", flush=True)

            wallet = future.result()
            if wallet:
                with seen_lock:
                    if wallet not in seen_wallets:
                        seen_wallets.add(wallet)
                        with open(OUT_FILE, "a") as f:
                            f.write(wallet + "\n")
                        saved += 1

    print()  # newline after \r
    return saved


def scrape_program(name, address, seen_wallets):
    print(f"\n  [{name}] Fetching signatures...")
    sigs = get_signatures(address)
    print(f"  [{name}] {len(sigs)} signatures — fetching transactions...")

    saved = batch_get_transactions(sigs, seen_wallets)
    print(f"  [{name}] +{saved} new | {len(seen_wallets)} total unique")


def runner(seen_wallets):
    with ThreadPoolExecutor(max_workers=RUNNER_WORKERS) as executor:
        futures = {
            executor.submit(scrape_program, name, addr, seen_wallets): name
            for name, addr in PROGRAMS.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"\n  [{name}] crashed: {e}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    seen_wallets = load_existing_wallets()

    iteration = 0
    while True:
        starttime = time.time()
        iteration += 1
        print(f"\n{'='*50}")
        print(f"Iteration {iteration} — {len(PROGRAMS)} programs — {len(seen_wallets)} wallets so far")
        print(f"{'='*50}")

        runner(seen_wallets)

        print(f"\nIteration {iteration} complete — {len(seen_wallets)} total unique wallets")
        print("Sleeping 10s before next run...")
        endtime = time.time()
        t_time = endtime - starttime
        print(t_time)
        time.sleep(10)