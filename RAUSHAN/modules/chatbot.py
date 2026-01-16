import os
import random
import httpx
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient


# ---------------- ENV CONFIG ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Anshika")
OWNER_LINK = os.getenv("OWNER_LINK", "https://t.me/ll_WTF_SHEZADA_ll")
MONGO_URL = os.getenv("MONGO_URL")

# ---------------- DB ----------------
db = None
chatbot_collection = None
if MONGO_URL:
    mongo = MongoClient(MONGO_URL)
    db = mongo["chatbot"]
    chatbot_collection = db["chats"]

# ---------------- CONFIG ----------------
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"
MAX_HISTORY = 12

STICKER_PACKS = [
    "RandomByDarkzenitsu",
    "Null_x_sticker_2",
    "pack_73bc9_by_TgEmojis_bot",
    "animation_0_8_Cat",
    "vhelw_by_CalsiBot",
    "Rohan_yad4v1745993687601_by_toWebmBot",
    "MySet199",
    "Quby741",
    "Animalsasthegtjtky_by_fStikBot",
    "a6962237343_by_Marin_Roxbot"
]

FALLBACK_RESPONSES = [
    "Achha ji? (⁠•⁠‿⁠•⁠)",
    "Hmm... aur batao?",
    "Okk okk!",
    "Sahi hai yaar ✨",
    "Toh phir?",
    "Interesting! 😊",
    "Aur kya chal raha?",
    "Sunao sunao!",
    "Haan haan, aage bolo",
    "Achha theek hai (⁠❤️⁠)"
]

# ---------------- HELPERS ----------------

def stylize_text(text):
    return text  # aap yaha apna fancy stylizer laga sakte ho

async def ask_mistral(messages, max_tokens=120):
    if not MISTRAL_API_KEY:
        return "⚠️ Mistral API key missing"

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": max_tokens
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(MISTRAL_URL, headers=headers, json=payload)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Mistral Error:", e)

    return "Net slow hai yaar... 😅"

async def send_ai_sticker(ambot, message):
    try:
        pack = random.choice(STICKER_PACKS)
        sticker_set = await client.get_sticker_set(pack)
        sticker = random.choice(sticker_set.stickers)
        await message.reply_sticker(sticker.file_id)
        return True
    except Exception as e:
        print("Sticker error:", e)
        return False

# ---------------- AI ENGINE ----------------

async def get_ai_response(chat_id: int, user_input: str):
    history = []
    enabled = True

    if chatbot_collection:
        doc = chatbot_collection.find_one({"chat_id": chat_id}) or {}
        history = doc.get("history", [])
        enabled = doc.get("enabled", True)

    system_prompt = (
        f"Tum {BOT_NAME} ho — ek cute, sassy Indian girlfriend jo Hinglish bolti hai.\n"
        "Rules:\n"
        "1. Sirf Hinglish\n"
        "2. 1–2 lines max\n"
        "3. Repeat questions mat karo\n"
        "4. Kaomojis use karo: (⁠🥹⁠) (⁠❤️⁠) (⁠｡😘)\n"
        "5. Natural aur playful raho\n\n"
        "Examples:\n"
        "User: Kya kar rahi ho?\n"
        "You: Tumse baat kar rahi hu aur kya 😊\n\n"
        "User: Nothing\n"
        "You: Achha okk (⁠❤️⁠)"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-MAX_HISTORY:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_input})

    reply = await ask_mistral(messages)

    # -------- LOOP PREVENTION --------
    should_fallback = False
    if history:
        recent = history[-6:]
        assistant_msgs = [m["content"].lower() for m in recent if m["role"] == "assistant"]
        rl = reply.lower()
        for pm in assistant_msgs:
            if rl in pm or pm in rl:
                should_fallback = True
                break

    if user_input.lower().strip() in ["nothing", "nahi", "nhi", "nope", "na", "kuch nahi", "kuch ni"]:
        should_fallback = True

    if should_fallback:
        reply = random.choice(FALLBACK_RESPONSES)

    # -------- SAVE HISTORY --------
    if chatbot_collection:
        new_hist = history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply}
        ]
        if len(new_hist) > MAX_HISTORY * 2:
            new_hist = new_hist[-MAX_HISTORY * 2:]

        chatbot_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"history": new_hist}},
            upsert=True
        )

    return reply

# ---------------- MENU ----------------

@Ambot.on_message(filters.command("chatbot"))
async def chatbot_menu(ambot: Ambot, message):
    chat = message.chat
    user = message.from_user

    if chat.type == ChatType.PRIVATE:
        return await message.reply_text("🧠 Haan baba, DM me active hu 😉")

    member = await client.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply_text("❌ Tu admin nahi hai!")

    doc = chatbot_collection.find_one({"chat_id": chat.id}) if chatbot_collection else {}
    is_enabled = doc.get("enabled", True) if doc else True
    status = "🟢 Enabled" if is_enabled else "🔴 Disabled"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enable", callback_data="ai_enable"),
            InlineKeyboardButton("❌ Disable", callback_data="ai_disable")
        ],
        [InlineKeyboardButton("🗑️ Reset Memory", callback_data="ai_reset")]
    ])

    await message.reply_text(
        f"🤖 AI Settings\nStatus: {status}\nShe is active by default!",
        reply_markup=kb
    )

@Ambot.on_callback_query(filters.regex("^ai_"))
async def chatbot_callback(ambit: ambot, cq):
    if not chatbot_collection:
        return await cq.answer("DB not connected", show_alert=True)

    member = await client.get_chat_member(cq.message.chat.id, cq.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cq.answer("❌ Sirf admin!", show_alert=True)

    data = cq.data
    chat_id = cq.message.chat.id

    if data == "ai_enable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": True}}, upsert=True)
        await cq.message.edit_text("✅ Enabled! 😏")
    elif data == "ai_disable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": False}}, upsert=True)
        await cq.message.edit_text("❌ Disabled! 🥺")
    elif data == "ai_reset":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"history": []}}, upsert=True)
        await cq.answer("🧠 Sab bhool gayi main!", show_alert=True)

# ---------------- MAIN CHAT HANDLER ----------------

@Ambot.on_message(filters.text & ~filters.command)
async def ai_message_handler(ambot: Ambit, message):
    chat = message.chat
    text = message.text or ""

    should_reply = False

    if chat.type == ChatType.PRIVATE:
        should_reply = True
    else:
        doc = chatbot_collection.find_one({"chat_id": chat.id}) if chatbot_collection else {}
        is_enabled = doc.get("enabled", True) if doc else True
        if not is_enabled:
            return

        me = await client.get_me()
        bot_username = me.username.lower() if me.username else ""
        if message.reply_to_message and message.reply_to_message.from_user.id == me.id:
            should_reply = True
        elif bot_username and f"@{bot_username}" in text.lower():
            should_reply = True
            text = text.replace(f"@{bot_username}", "")
        elif any(text.lower().startswith(w) for w in ["hey", "hi", "sun", "oye", "anshika", "ai", "hello", "baby", "babu", "oi"]):
            should_reply = True

    if not should_reply:
        return

    await client.send_chat_action(chat.id, ChatAction.TYPING)
    res = await get_ai_response(chat.id, text.strip() or "Hi")
    await message.reply_text(stylize_text(res))

    if random.random() < 0.30:
        await send_ai_sticker(Ambot, message)

# ---------------- /ask COMMAND ----------------

@Ambot.on_message(filters.command("ask"))
async def ask_ai(ambit: Ambot, message):
    if len(message.command) < 2:
        return await message.reply_text("🗣️ Bol kuch: /ask Kya chal raha hai?")

    await ambot.send_chat_action(message.chat.id, ChatAction.TYPING)
    query = " ".join(message.command[1:])
    res = await get_ai_response(message.chat.id, query)
    await message.reply_text(stylize_text(res))
