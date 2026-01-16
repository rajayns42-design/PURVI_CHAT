from pyrogram import Client, filters
from config import *
from database import users
from relationship_engine import add_xp, decay_relationship
from jealousy_engine import check_jealousy, jealousy_reply
from breakup_engine import trigger_breakup, breakup_reply
from payment_engine import create_stripe_session
from ui import main_menu
from ai_engine import build_prompt
import httpx

app = Client("gfbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.private & filters.text)
async def chat_handler(client, message):
    uid = message.from_user.id
    user = users.find_one({"_id": uid}) or {
        "_id": uid,
        "xp": 0,
        "level": "stranger",
        "status": "normal",
        "locked_romance": False,
        "premium": False,
        "bot_name": BOT_NAME
    }

    user = decay_relationship(user)

    if user.get("status") == "broken":
        await message.reply(breakup_reply())
        return

    if check_jealousy(message.text):
        await message.reply(jealousy_reply(message.from_user.first_name))
        return

    user = add_xp(user, 20)
    users.update_one({"_id": uid}, {"$set": user}, upsert=True)

    prompt = build_prompt(user, message.text, "romantic")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
            json={"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}]}
        )
        reply = r.json()["choices"][0]["message"]["content"]

    await message.reply(reply, reply_markup=main_menu())

app.run()
