# 🧠 SKeptic Bot – Invite-Only Scientific Reasoning Chatbot

This project is a lightweight, session-based GPT chatbot designed to foster scientific curiosity through critical thinking. It uses OpenAI's GPT API and assigns each user a unique ID and secure token for temporary session-based access.

---

## 🚀 Features

- Invite-only access using user_id + HMAC-based token
- Stateless deployment – no need for a database
- Per-user chat session memory using in-memory queues
- Token limit management and message pruning
- Built with Gradio for a simple web interface

---

## 📦 Requirements

- Python 3.9 or higher
- Internet connection
- OpenAI API key
- A secret key to sign and verify user HMACs

---

## 🖥️ Installation

### 🔹 1. Install Python

- **macOS**: Install Homebrew (if not already):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Then install Python:
```bash
brew install python
```

- **Windows**: Download Python from the official site: https://www.python.org/downloads/
  Make sure to check ✅ **"Add Python to PATH"** during installation.

### 🔹 2. Set up Virtual Environment

- **macOS/Linux**:
```bash
python3 -m venv venv
source venv/bin/activate
```

- **Windows**:
```bash
python -m venv venv
.\venv\Scripts\activate
```

### 🔹 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 🔐 Setup Environment Variables

Please update the `api_key` in `app3.py` with you OpenAI API key and `SECRET_KEY` in `app3.py` and `generate_users.py` with a secret key of your choice. This key is used to sign and verify HMAC tokens.

## 👥 Generate Users

Run this script to generate user IDs and their HMAC tokens:
```bash
python generate_users.py
```

- This will generate a file `valid_users.json` containing valid `user_id` and `token` pairs.
- Share the `user_id` and `token` with the user. Keep `valid_users.json` private and secure.

## 💬 Run the Chatbot

To launch the Gradio web interface locally:
```bash
python app3.py
```
This will start a local server and open the chat UI in your browser.

## 📌 Notes

- The user must enter their **User ID** and **Token** exactly as given to gain access.
- Each session is maintained in memory. Restarting the app will clear all user chat history.
- The script handles token pruning to stay within GPT model context limits.

## ✅ Example User Credentials

When generating users, you will get output like this:
```json
{
  "hawk-rider-102": "ea3a48c9d9b47...c91d"
}
```

Share the following with the user:
```yaml
User ID: hawk-rider-102
Token: ea3a48c9d9b47...c91d
```

## 📂 Project Structure

```bash
.
├── chatbot.py          # Main Gradio app with HMAC validation
├── generate_users.py   # UUID + HMAC generator
├── valid_users.json    # Auto-generated user registry
├── .env                # Secret and API key (not tracked in Git)
├── requirements.txt
└── README.md
```