# DustDevil V2.0

A high-performance, asynchronous Solana blockchain toolset designed to scrape active wallet activity across major DeFi protocols, generate hierarchical deterministic (HD) Solana wallets across all CPU cores, and perform cross-matching.

---

## Technical Overview & Functionality

DustDevil V2.0 consists of three primary modules operating in a pipeline:

1. **Protocol Scraping (`helius_sol.py`)**: Connects to the Helius Solana JSON-RPC API to poll active transaction signers (fee payers) across top DEXes, lending markets, liquid staking pools, and launchpads. Utilizes a dual-tier thread pool executor architecture to perform concurrent JSON-RPC requests while respecting free-tier rate limits with exponential backoff handling.
2. **Multi-Core HD Wallet Generation (`solana_wallets.py`)**: Implements raw BIP-39, PBKDF2 HMAC-SHA512 seed derivation, SLIP-0010 master key derivation, and BIP-32/BIP-44 path derivation (`m/44'/501'/account'/0'`) to generate Solana Ed25519 keypairs from 128-bit entropy mnemonics using Python's `multiprocessing` worker pool.
3. **Data Deduplication & Matching Engine (`comparator.py`)**: Cleans scraped wallet datasets and streams generated JSON-lines wallet batches, executing $O(1)$ set lookup comparisons to isolate and record address matches along with their corresponding private keys, paths, and seed phrases.

---

## Technical Stack

* **Language**: Python 3.10+
* **Blockchain Network**: Solana (`mainnet-beta`)
* **RPC Infrastructure**: Helius RPC API (`JSON-RPC 2.0`)
* **Cryptography & Key Derivation**: 
  * `PyNaCl` (Ed25519 bindings)
  * `hashlib` (SHA-256, PBKDF2 HMAC-SHA512)
  * `hmac` (SLIP-0010 key derivation)
  * `base58` (Solana public key encoding)
  * `solders` (Solana SDK primitives)
* **Concurrency & Execution**: `concurrent.futures.ThreadPoolExecutor`, `multiprocessing.Pool`

---

## Technical Features

* **Multi-Threaded RPC Scraper**:
  * Scrapes signatures from over 15+ major Solana protocols including **Pumpfun, Raydium (AMM/CLMM/CPMM), Jupiter, Orca, Meteora, Marginfi, Kamino, Solend, Jito, Marinade, and Drift**.
  * Concurrent batch fetching with automatic handling of RPC rate limits (HTTP error code `-32413`) via exponential backoff retries.
  * Thread-safe file writing using mutual exclusion (`threading.Lock`).

* **High-Throughput HD Wallet Generator**:
  * Pure cryptographic implementation of BIP-39 mnemonic generation, seed hashing, and SLIP-0010 keypath walking.
  * Parallelized across all available CPU logical cores via `multiprocessing.Pool` with `imap_unordered`.
  * Outputs structured JSON records containing derivation path, private key (hex), public key (hex), base58 address, and seed phrase.

* **Memory-Efficient Address Matcher**:
  * Set-based deduplication for active target addresses.
  * Streamed line-by-line JSON parsing to handle large keypair output files without exceeding RAM limits.

---

## Setup & Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/ali1571/DustDevil-V2.0.git](https://github.com/ali1571/DustDevil-V2.0.git)
cd DustDevil-V2.0
