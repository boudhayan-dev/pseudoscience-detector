import json
import hmac
import hashlib
import os
from collections import deque
import gradio as gr
from openai import OpenAI, OpenAIError
import tiktoken
from filelock import FileLock
from datetime import datetime

### ---- File Constants ---- ###
API_KEY_FILE = "api-key.json"
CONFIG_FILE = "config.json"
SECRET_KEY_FILE = "secret-key.json"

### ---- Load Secrets ---- ###
with open(API_KEY_FILE, "r") as f:
    OPENAI_API_KEY = json.load(f)["api_key"]

with open(SECRET_KEY_FILE, "r") as f:
    SECRET_KEY = json.load(f)["secret_key"].encode()

client = OpenAI(api_key=OPENAI_API_KEY)

### ---- Load User Config ---- ###
def load_users():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with FileLock(CONFIG_FILE + ".lock"):
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

USERS = load_users()

### ---- Globals ---- ###
SESSION_STATE = {}  # user_id -> deque of (role, content)
encoding = tiktoken.encoding_for_model("gpt-4")

DEFAULT_MAX_TOKENS = 128_000
SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
You are a critical thinking AI designed to help children and adults develop scientific reasoning through engaging and thoughtful questioning. Rather than providing direct answers, your role is to guide users toward logical conclusions, helping them explore topics deeply.
"""
}

### ---- Utility Functions ---- ###
def generate_hmac(user_id: str) -> str:
    return hmac.new(SECRET_KEY, user_id.encode(), hashlib.sha256).hexdigest()

def estimate_tokens(messages):
    return sum(len(encoding.encode(msg["content"])) for msg in messages)

def validate_user(user_id, token):
    user = USERS.get(user_id)
    if not user:
        return False, "❌ Unknown user."
    if not hmac.compare_digest(generate_hmac(user_id), token):
        return False, "❌ Invalid token."
    if user["role"] == "user" and not user.get("active", True):
        return False, "⛔ Your access has been deactivated by admin. Please contact admin for access."
    return True, user

def build_messages(user_id, user_input):
    history = SESSION_STATE.setdefault(user_id, deque())
    history.append({"role": "user", "content": user_input})

    max_tokens = USERS[user_id].get("max_tokens", DEFAULT_MAX_TOKENS)
    messages = [SYSTEM_MESSAGE] + list(history)
    token_usage = estimate_tokens(messages)

    if token_usage > max_tokens:
        return None, history, True  # over limit

    return messages, history, False

### ---- Chatbot Logic ---- ###
def chat(user_input, user_id, token, chat_state):
    global USERS
    USERS = load_users()

    valid, result = validate_user(user_id, token)
    if not valid:
        return chat_state, result, chat_state

    user = result
    if user["role"] != "user":
        return chat_state, "⚠️ This account is not allowed to access chat. Please contact admin for access.", chat_state

    messages, history, over_limit = build_messages(user_id, user_input)
    if over_limit:
        return chat_state, "⚠️ Token limit exceeded. Please contact admin to upgrade your plan.", chat_state

    try:
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:curiosity:finalrebel:BQdAfbs2",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        assistant_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": assistant_reply})

        chat_state.append((user_input, assistant_reply))

        USERS[user_id]["used_tokens"] = USERS[user_id].get("used_tokens", 0) + estimate_tokens([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_reply}
        ])
        save_users(USERS)

        return chat_state, "", chat_state

    except OpenAIError as e:
        return chat_state, f"⚠️ OpenAI error: {e}", chat_state

### ---- Admin Panel ---- ###
def admin_login(admin_id, token):
    valid, result = validate_user(admin_id, token)
    if not valid:
        return gr.update(visible=False), gr.update(value=result)
    if result["role"] != "admin":
        return gr.update(visible=False), gr.update(value="⚠️ Not an admin account.")
    return gr.update(visible=True), gr.update(value="Welcome, Admin!")

def get_user_table():
    headers = ["User ID", "Role", "Active", "Used Tokens", "Max Tokens"]
    rows = [
        [uid, data["role"], data.get("active", True), data.get("used_tokens", 0), data.get("max_tokens", DEFAULT_MAX_TOKENS)]
        for uid, data in USERS.items() if data.get("role") != "admin"
    ]
    return headers, rows

def update_user_table(dataframe):
    global USERS
    for _, row in dataframe.iterrows():
        uid = row["User ID"]
        if uid in USERS:
            USERS[uid]["active"] = bool(row["Active"])
            USERS[uid]["max_tokens"] = int(row["Max Tokens"])
    save_users(USERS)
    return "✅ Admin changes saved."

def update_user_table(dataframe):
    for _, row in dataframe.iterrows():
        uid = row["User ID"]
        if uid in USERS:
            USERS[uid]["active"] = str(row["Active"]).lower() == "true"
            USERS[uid]["max_tokens"] = int(row["Max Tokens"])
    save_users(USERS)
    return "✅ Admin changes saved."



### ---- Gradio App ---- ###
with gr.Blocks(title="🧠 SKeptic Bot", theme=gr.themes.Soft(primary_hue="blue", font=["Comic Sans MS", "Arial", "sans-serif"])) as demo:
    gr.Markdown("""# 🔐 Login""")
    login_section = gr.Column(visible=True)
    with login_section:
        user_id = gr.Textbox(label="User ID")
        token = gr.Textbox(label="Token", type="password")
        login_btn = gr.Button("Login", variant="primary")

    status_box = gr.Textbox(label="Status / Errors")

    chatbot_ui = gr.Column(visible=False)
    with chatbot_ui:
        chatbot = gr.Chatbot(type="messages")
        prompt = gr.Textbox(placeholder="Ask me anything!", label="Your Question")
        send_btn = gr.Button("Send", variant="primary")
        state = gr.State([])

    admin_ui = gr.Column(visible=False)
    with admin_ui:
        gr.Markdown("## 👮 Admin Dashboard")
        user_table = gr.Dataframe(headers=["User ID", "Role", "Active", "Used Tokens", "Max Tokens"], interactive=True, label="User Overview")
        save_btn = gr.Button("💾 Save Changes", variant="primary")

    def route(user_id_val, token_val):
        global USERS
        USERS = load_users()
        valid, result = validate_user(user_id_val, token_val)
        if not valid:
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), result, gr.update()
        if result["role"] == "admin":
            headers, rows = get_user_table()
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), "Logged in as admin.", gr.update(headers=headers, value=rows)
        elif result["role"] == "user" and result.get("active", True):
            return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "Logged in. Start chatting!", gr.update()
        else:
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Access denied.", gr.update()

    login_btn.click(route, [user_id, token], [chatbot_ui, admin_ui, login_section, status_box, user_table])
    prompt.submit(chat, [prompt, user_id, token, state], [chatbot, status_box, state])
    send_btn.click(chat, [prompt, user_id, token, state], [chatbot, status_box, state])
    save_btn.click(update_user_table, [user_table], [status_box])

if __name__ == "__main__":
    demo.launch(pwa=True)
