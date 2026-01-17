from pyrogram import filters
from bot import app
from config import OWNER_ID
from database.mongo import users_col

@app.on_message(filters.user(OWNER_ID) & filters.command("stats"))
async def stats(client, message):
    total = users_col.count_documents({})
    premium = users_col.count_documents({"premium": True})
    await message.reply(
        f"""
📊 Admin Dashboard
👥 Total Users: {total}
💎 Premium Users: {premium}
"""
    )
