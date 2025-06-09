# init-data.py

import uuid
import hmac
import hashlib
import json
import random
from datetime import datetime
import os

# ---- Config ---- #
CONFIG_FILE = "config.json"
SECRET_KEY_FILE = "secret-key.json"
USER_BATCH_SIZE = 30
DEFAULT_MAX_TOKENS = 128_000

ADJECTIVES = [
    "happy", "sneaky", "brave", "gentle", "proud", "quick", "smart", "calm",
    "mighty", "lazy", "wild", "eager", "tiny", "lucky", "bright", "cool"
]

NOUNS = [
    "rider", "hawk", "pirate", "ninja", "panda", "wizard", "chef", "ranger",
    "robot", "fox", "lion", "whale", "sloth", "otter", "ghost", "alien"
]

def generate_readable_user_id():
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(100, 999)
    return f"{adj}-{noun}-{number}"

def generate_hmac(user_id: str, secret_key: bytes) -> str:
    return hmac.new(secret_key, user_id.encode(), hashlib.sha256).hexdigest()

def load_existing_users():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(CONFIG_FILE, "w") as f:
        json.dump(users, f, indent=2)

def load_or_create_secret():
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "r") as f:
            return json.load(f)["secret_key"].encode()
    else:
        key = uuid.uuid4().hex.encode()
        today = datetime.now().strftime("%Y-%m-%d")
        with open(SECRET_KEY_FILE, "w") as f:
            json.dump({"secret_key": key.decode(), "created": today}, f, indent=2)
        print(f"✅ Secret key created with tag: {today}")
        return key

def generate_users(batch_size=30):
    users = load_existing_users()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    secret_key = load_or_create_secret()

    if "admin-ranger-001" not in users:
        admin_id = "admin-ranger-001"
        users[admin_id] = {
            "token": generate_hmac(admin_id, secret_key),
            "role": "admin",
            "active": True,
            "used_tokens": 0,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "createdDate": now
        }
        print(f"✅ Created admin user: {admin_id}")

    new_users = 0
    while new_users < batch_size:
        user_id = generate_readable_user_id()
        if user_id in users:
            continue
        users[user_id] = {
            "token": generate_hmac(user_id, secret_key),
            "role": "user",
            "active": True,
            "used_tokens": 0,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "createdDate": now
        }
        new_users += 1

    save_users(users)
    print(f"✅ Added {new_users} users with tag: {now}")

if __name__ == "__main__":
    generate_users(USER_BATCH_SIZE)