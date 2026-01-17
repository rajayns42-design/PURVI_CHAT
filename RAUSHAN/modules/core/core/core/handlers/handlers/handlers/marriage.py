from pyrogram import filters
from bot import app
from database.mongo import marriages_col

@app.on_message(filters.command("marry"))
async def marry(client, message):
    marriages_col.insert_one({
        "uid": message.from_user.id,
        "partner": "Anshika",
        "time": message.date
    })
    await message.reply("💍 Haan! Main tumse shaadi karungi 😭❤️")
