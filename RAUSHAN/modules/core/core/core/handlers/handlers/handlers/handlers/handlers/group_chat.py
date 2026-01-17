from pyrogram import filters
from pyrogram.enums import ChatType
from bot import app
from core.games_engine import truth, dare

@app.on_message(filters.group & filters.text)
async def group_handler(client, message):
    text = message.text.lower()

    if text == "/truth":
        await message.reply("🎯 Truth:\n" + truth())
    elif text == "/dare":
        await message.reply("🔥 Dare:\n" + dare())
