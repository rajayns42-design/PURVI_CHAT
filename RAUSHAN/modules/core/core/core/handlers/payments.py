from pyrogram import filters
from bot import app
from database.users import add_premium

@app.on_message(filters.command("premium"))
async def premium(client, message):
    add_premium(message.from_user.id, 30)
    await message.reply("💎 Premium activated for 30 days baby 😘")
