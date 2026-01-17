from pyrogram import filters
from bot import app
from core.games_engine import truth, dare

@app.on_message(filters.command("game"))
async def game(client, message):
    await message.reply("🎮 Choose:\n/truth\n/dare")
