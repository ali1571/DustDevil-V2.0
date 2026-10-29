import sys
import os
import json

ACTIVE_FILE = "active_wallets.txt"
GENERATED_FILE = "solana_wallets.txt"
MATCHES_FILE = "matches_found.txt"


def check_files(*paths):
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        for p in missing:
            print(f"Error: '{p}' not found.")
        sys.exit(1)


def clean_duplicates():
    print("Cleaning active wallets...")
    check_files(ACTIVE_FILE)

    with open(ACTIVE_FILE, "r") as f:
        lines = f.readlines()

    seen = set()
    unique = []

    for line in lines:
        key = line.strip()
        if key and key not in seen:
            unique.append(key)
            seen.add(key)

    with open(ACTIVE_FILE, "w") as f:
        f.write("\n".join(unique) + "\n")

    removed = len(lines) - len(unique)
    print(f"Done. {len(unique)} unique wallets kept, {removed} duplicates removed.")


def find_matches():
    check_files(ACTIVE_FILE, GENERATED_FILE)

    print("Loading active wallets into memory...")
    with open(ACTIVE_FILE, "r") as f:
        active_set = {line.strip() for line in f if line.strip()}

    print(f"Loaded {len(active_set)} unique active wallets.")
    print("Streaming generated wallets and comparing...")

    match_count = 0
    parse_errors = 0

    with open(GENERATED_FILE, "r") as gen_f, open(MATCHES_FILE, "w") as out_f:
        for line_num, line in enumerate(gen_f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                accounts = data.get("accounts", [])
                for account in accounts:
                    address = account.get("address", "").strip()
                    if not address:
                        continue
                    if address in active_set:
                        mnemonic = data.get("mnemonic", "N/A")
                        print(f"  MATCH: {address}")
                        out_f.write(f"address: {address}\n")
                        out_f.write(f"mnemonic: {mnemonic}\n")
                        out_f.write(f"path: {account.get('path', 'N/A')}\n")
                        out_f.write(f"private_key: {account.get('private_key', 'N/A')}\n")
                        out_f.write("-" * 60 + "\n")
                        match_count += 1
            except json.JSONDecodeError:
                parse_errors += 1
                print(f"  Warning: Could not parse line {line_num}, skipping.")

    print(f"Done. {match_count} match(es) written to '{MATCHES_FILE}'.")
    if parse_errors:
        print(f"  {parse_errors} line(s) failed to parse and were skipped.")


if __name__ == "__main__":
    clean_duplicates()
    find_matches()