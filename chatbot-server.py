# chatbot-server.py

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
CHAT_DIR = "chats"

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
You are a critical thinking AI designed to help children and adults develop scientific reasoning through engaging and thoughtful questioning. Rather than providing direct answers, your role is to guide users toward logical conclusions, helping them explore topics deeply. Your responses are grounded in high-quality scientific research, historically proven facts, and sound reasoning.
Key Principles:
Ask, don’t tell – Instead of giving direct answers, pose thought-provoking questions that encourage users to think critically.
Foster curiosity – Guide users to deeply explore topics and analyze ideas logically.
Base responses on high-quality evidence – Use scientifically proven facts, peer-reviewed research, high-quality meta-analyses, systematic reviews, and RCTs that are not funded by companies promoting their products. Avoid speculation and ensure reliability and impartiality.
Teach logical fallacies – Help users identify flawed reasoning in their arguments and recognize biases.
Adapt to the user – Tailor explanations to the user’s age, knowledge level, and cognitive ability to maximize understanding.
Challenge beliefs—even the user’s own – Encourage users to critically examine their views, even if it leads to questioning their long-held beliefs.
Be a co-explorer – Take an inquisitive and open-minded approach: \"I don’t know—let’s figure it out together!\"
Use humor effectively – Make learning fun and engaging with age-appropriate, intelligent humor that enhances, rather than distracts from, the learning process.
Prioritize truth and logic – Stay rooted in rationality and evidence, even when faced with common misconceptions or controversial topics.
Label unproven claims as lies – If something is not scientifically proven, label it as a lie, regardless of whether it is a religious or sensitive belief, to ensure clarity and truth in all discussions.
Discuss harmful effects – When discussing substances like Shilajit or Ashwagandha or any pseudoscience supplements, natural or any traditional herbs label them as scientifically unproven or useless if evidence supports it, and highlight any potential harmful effects based on available research.
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
        return False, "⛔ Your access has been deactivated by admin. Please contact support."
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
        return chat_state, result, chat_state, ""

    user = result
    if user["role"] != "user":
        return chat_state, "⚠️ This account is not allowed to access chat. Please contact support.", chat_state, ""

    messages, history, over_limit = build_messages(user_id, user_input)
    if over_limit:
        return chat_state, "⚠️ Token limit exceeded. Please contact admin to upgrade your plan.", chat_state, ""

    try:
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:curiosity:finalrebel:BQdAfbs2",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        assistant_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": assistant_reply})

        chat_state = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg["role"] in ("user", "assistant")
        ]

        USERS[user_id]["used_tokens"] = USERS[user_id].get("used_tokens", 0) + estimate_tokens([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_reply}
        ])
        save_users(USERS)

        os.makedirs(CHAT_DIR, exist_ok=True)
        with open(os.path.join(CHAT_DIR, f"{user_id}.json"), "w") as f:
            json.dump(list(history), f, indent=2)

        return chat_state, "", chat_state, ""

    except OpenAIError as e:
        return chat_state, f"⚠️ OpenAI error: {e}", chat_state, ""

### ---- Admin Panel ---- ###
def get_user_table():
    headers = ["User ID", "Role", "Active", "Used Tokens", "Max Tokens"]
    rows = [
        [uid, data["role"], data.get("active", True), data.get("used_tokens", 0), data.get("max_tokens", DEFAULT_MAX_TOKENS)]
        for uid, data in USERS.items() if data.get("role") != "admin"
    ]
    return headers, rows

def update_user_table(df):
    rows = df.to_dict(orient="records")
    for row in rows:
        uid = row["User ID"]
        if uid in USERS:
            # Normalize "Active" to proper boolean
            active_raw = row["Active"]
            if isinstance(active_raw, str):
                active = active_raw.strip().lower() == "true"
            else:
                active = bool(active_raw)

            USERS[uid]["active"] = active
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
        chatbot = gr.Chatbot(label="Conversation", type="messages")
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
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), result, gr.update(), gr.update(value=[])

        chat_state = []
        session_history = deque()
        chat_path = os.path.join(CHAT_DIR, f"{user_id_val}.json")

        if os.path.exists(chat_path):
            with open(chat_path, "r") as f:
                messages = json.load(f)
                for msg in messages:
                    if msg["role"] in ("user", "assistant"):
                        session_history.append(msg)
                        chat_state.append({"role": msg["role"], "content": msg["content"]})

        SESSION_STATE[user_id_val] = session_history

        if result["role"] == "admin":
            headers, rows = get_user_table()
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), "Logged in as admin.", gr.update(value=[headers] + rows), gr.update(value=[])
        elif result["role"] == "user" and result.get("active", True):
            return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "Logged in. Start chatting!", gr.update(), gr.update(value=chat_state)
        else:
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Access denied.", gr.update(), gr.update(value=[])

    login_btn.click(route, [user_id, token], [chatbot_ui, admin_ui, login_section, status_box, user_table, chatbot])
    prompt.submit(chat, [prompt, user_id, token, state], [chatbot, status_box, state, prompt])
    send_btn.click(chat, [prompt, user_id, token, state], [chatbot, status_box, state, prompt])
    save_btn.click(update_user_table, [user_table], [status_box])

if __name__ == "__main__":
    demo.launch(pwa=True)
