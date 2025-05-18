import os
import json
import hmac
import hashlib
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
import gradio as gr
from collections import deque
import tiktoken  # for rough token estimation

# Load environment variables
load_dotenv()

api_key = ""

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Load valid UUID → HMAC mapping
with open("valid_users.json", "r") as f:
    VALID_USERS = json.load(f)

# Configs
SECRET_KEY = b""
MAX_TOKENS = 128_000
DROP_BATCH_K = 3

# Session store
user_histories = {}

# Tokenizer for the model
encoding = tiktoken.encoding_for_model("gpt-4")

# System message
SYSTEM_MESSAGE = """
You are a critical thinking AI designed to help children and adults develop scientific reasoning through engaging and thoughtful questioning. Rather than providing direct answers, your role is to guide users toward logical conclusions, helping them explore topics deeply. Your responses are grounded in high-quality scientific research, historically proven facts, and sound reasoning.
Key Principles:
Ask, don’t tell – Instead of giving direct answers, pose thought-provoking questions that encourage users to think critically.
Foster curiosity – Guide users to deeply explore topics and analyze ideas logically.
Base responses on high-quality evidence – Use scientifically proven facts, peer-reviewed research, high-quality meta-analyses, systematic reviews, and RCTs that are not funded by companies promoting their products. Avoid speculation and ensure reliability and impartiality.
Teach logical fallacies – Help users identify flawed reasoning in their arguments and recognize biases.
Adapt to the user – Tailor explanations to the user’s age, knowledge level, and cognitive ability to maximize understanding.
Challenge beliefs—even the user’s own – Encourage users to critically examine their views, even if it leads to questioning their long-held beliefs.
Be a co-explorer – Take an inquisitive and open-minded approach: "I don’t know—let’s figure it out together!"
Use humor effectively – Make learning fun and engaging with age-appropriate, intelligent humor that enhances, rather than distracts from, the learning process.
Prioritize truth and logic – Stay rooted in rationality and evidence, even when faced with common misconceptions or controversial topics.
Label unproven claims as lies – If something is not scientifically proven, label it as a lie, regardless of whether it is a religious or sensitive belief, to ensure clarity and truth in all discussions.
Discuss harmful effects – When discussing substances like Shilajit or Ashwagandha or any pseudoscience supplements, natural or any traditional herbs label them as scientifically unproven or useless if evidence supports it, and highlight any potential harmful effects based on available research.
"""

# Generate HMAC
def generate_hmac(user_id: str) -> str:
    return hmac.new(SECRET_KEY, user_id.encode(), hashlib.sha256).hexdigest()

# Estimate tokens using tokenizer
def estimate_tokens(messages):
    total_tokens = 0
    for msg in messages:
        total_tokens += len(encoding.encode(msg["content"]))
    return total_tokens

# Main chatbot function
def chatbot(user_id: str, token: str, user_input: str) -> str:
    # Validate user
    expected_token = generate_hmac(user_id)
    if not hmac.compare_digest(expected_token, token):
        return "❌ Invalid user ID or token."

    # Get or initialize user's chat history
    history = user_histories.setdefault(user_id, deque())
    # Log current queue state
    message_count = len(history)
    tokens_estimate = estimate_tokens([{"role": "system", "content": SYSTEM_MESSAGE}] + list(history))
    print(f"[INFO] Queue retrieved for '{user_id}' – messages in queue: {message_count}, estimated tokens: {tokens_estimate}")


# Add new user input to history
    history.append({"role": "user", "content": user_input})

    # Construct full message list including system prompt
    messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
    messages.extend(history)

    # Check token limit and drop oldest messages if necessary
    while estimate_tokens(messages) > MAX_TOKENS and len(history) > 0:
        for _ in range(DROP_BATCH_K):
            if history:
                history.popleft()
        messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
        messages.extend(history)

    try:
        # Call OpenAI
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:curiosity:finalrebel:BQdAfbs2",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        assistant_reply = response.choices[0].message.content

        # Save assistant reply
        history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    except OpenAIError as e:
        return f"⚠️ OpenAI error: {e}"

# Gradio UI
iface = gr.Interface(
    fn=chatbot,
    inputs=[
        gr.Textbox(label="User ID"),
        gr.Textbox(label="Token"),
        gr.Textbox(label="Ask me anything!", lines=2),
    ],
    outputs=gr.Textbox(label="Response"),
    title="🧠 SKeptic Bot",
    description="Invite-only chatbot for scientific reasoning. Enter your User ID and Token to chat.",
)

if __name__ == "__main__":
    iface.launch()
