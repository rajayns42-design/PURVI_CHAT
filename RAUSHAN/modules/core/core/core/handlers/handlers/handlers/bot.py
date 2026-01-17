from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

app = Client(
    "ai_girlfriend_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

import handlers.private_chat
import handlers.group_chat
import handlers.admin
import handlers.payments
import handlers.games

print("🤖 AI Girlfriend Bot Started...")

app.run()
