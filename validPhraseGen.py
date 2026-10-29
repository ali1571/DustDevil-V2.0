import os
import hashlib

def generate_mnemonic(wordlist):
    # 1. Generate 128 bits of secure entropy
    entropy = os.urandom(16)  # 16 bytes = 128 bits
    #print (entropy)

    # 2. SHA256 hash → first 4 bits = checksum
    digest = hashlib.sha256(entropy).digest()
    #print(digest)
    checksum_bits = f"{digest[0]:08b}"[:4]
    #print(checksum_bits)

    # 3. entropy bits + checksum = 132 bits
    entropy_bits = bin(int.from_bytes(entropy, 'big'))[2:].zfill(128)
    #print(entropy_bits)
    full_bits = entropy_bits + checksum_bits  # always 132 bits
    #print(full_bits)

    # 4. Split into 12 groups of 11 bits → index into wordlist
    mnemonic = []
    for i in range(12):
        index = int(full_bits[i*11:(i+1)*11], 2)  # 0–2047
        mnemonic.append(wordlist[index])

    mnemonic_string = " ".join(mnemonic)  # join list into single space-separated string

    with open("mnemonics.txt", "a") as f:
        f.write(mnemonic_string + "\n")  # each mnemonic on its own line

    return mnemonic_string


with open("KEYTOWORD.txt") as f:
    wordlist = f.read().split()
for i in range(10000):
    print(generate_mnemonic(wordlist))