import hmac
import hashlib
import secrets
import json
import random

# Secret key to generate HMACs – keep this private!
SECRET_KEY = b''

# Word lists for readable ID generation
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

def generate_hmac(user_id: str) -> str:
    return hmac.new(SECRET_KEY, user_id.encode(), hashlib.sha256).hexdigest()

def create_invite_tokens(n=10):
    invites = {}
    for _ in range(n):
        user_id = generate_readable_user_id()
        while user_id in invites:
            user_id = generate_readable_user_id()  # Avoid duplicates
        hmac_val = generate_hmac(user_id)
        invites[user_id] = hmac_val
    return invites

if __name__ == "__main__":
    invites = create_invite_tokens(n=20)  # generate 20 users
    with open("valid_users.json", "w") as f:
        json.dump(invites, f, indent=2)
    print("✅ Generated user IDs and saved to valid_users.json")
