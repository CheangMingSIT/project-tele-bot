from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
from starlette.middleware.cors import CORSMiddleware
import httpx
import telegramify_markdown
from telegramify_markdown.customize import get_runtime_config
from openai import OpenAI
import base64
from mangum import Mangum
import uvicorn

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not api_key:
    raise EnvironmentError("OPENAI_API_KEY not found. Make sure it's set in your .env file.")

client = OpenAI(api_key=api_key)
app = FastAPI()

# CORS middleware (optional)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Markdown customization
markdown_symbol = get_runtime_config().markdown_symbol
markdown_symbol.head_level_1 = "📍"
markdown_symbol.link = "🔗"

@app.get("/")
def read_root():
   return {"Welcome to": "My first FastAPI depolyment using Docker image"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    # print("⚡ Received Telegram update:", data)

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    # reply_to = message.get("reply_to_message", {})
    # print("reply_to", reply_to)

    if not chat_id:
        print("⚠️ Missing chat ID")
        return {"ok": True}

    photo = message.get("photo")
    text = message.get("text", "")

    async with httpx.AsyncClient() as http_client:
        # 🟡 Show typing indicator
        await http_client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"}
        )

        # 📌 Check for /start command
        if text == "/start":
            reply = (
                "👋 Hello! I’m your friendly *Math Tutor Bot*.\n\n"
                "📌 Send me a math question as *text* or *image*, and I’ll explain it step-by-step.\n"
                "📷 Just snap a photo of your worksheet, and I’ll handle the rest!\n\n"
                "Let’s solve some math together! 🧠💡"
            )

        elif photo:
            # 🖼 Get the highest resolution image
            file_id = photo[-1]["file_id"]

            # Step 1: Get file path
            file_info = await http_client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            )
            file_path = file_info.json()["result"]["file_path"]

            # Step 2: Download the image
            image_response = await http_client.get(
                f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            )
            image_bytes = image_response.content
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")

            # Step 3: Send to GPT-4o Vision
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful elementary math tutor. Read the image and solve the math problem. "
                            "You are here to assist students with topics related to mathematics only. "
                            "Politely decline anything else. Answer step by step as this is for elementary school students."
                            "keep the answer short and simple and understandable for elementary school students."
                            "If the image is not clear, please ask the user to send a clearer image."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            reply = response.choices[0].message.content

        elif text:
            # ✍️ Handle plain text math questions
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful math tutor. Read and solve the math problem. "
                            "You are here to assist students with topics related to mathematics only. "
                            "Politely decline anything else. Answer step by step as this is for elementary school students."
                        )
                    },
                    {"role": "user", "content": text}
                ]
            )
            reply = response.choices[0].message.content

        else:
            reply = "❗Please send a math question either as *text* or an *image*."

        # Format reply for Telegram
        reply = telegramify_markdown.standardize(reply)

        # 📩 Send reply
        await http_client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "MarkdownV2"
            }
        )

    return {"ok": True}


handler = Mangum(app)

if __name__ == "__main__":
   uvicorn.run(app, host="0.0.0.0", port=8080)