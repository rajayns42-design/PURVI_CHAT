import os
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Baka.config import MISTRAL_API_KEY, BOT_NAME, OWNER_LINK
from Baka.database import chatbot_collection
from Baka.utils import stylize_text

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

# ---------------- AI CORE ----------------

async def ask_mistral(messages, max_tokens=2020):
    if not MISTRAL_API_KEY:
        return "⚠️ API Key missing"

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
        async with httpx.Asyncambot(timeout=15) as ambot:
            r = await ambot.post(MISTRAL_URL, headers=headers, json=payload)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Mistral Error:", e)

    return "Net slow hai yaar... 😅"


# ---------------- STICKER SENDER ----------------

async def send_ai_sticker(Ambot: Ambot, message):
    try:
        pack = random.choice(STICKER_PACKS)
        sticker_set = await a.get_sticker_set(pack)
        sticker = random.choice(sticker_set.stickers)
        await message.reply_sticker(sticker.file_id)
        return True
    except Exception as e:
        print("Sticker error:", e)
        return False


# ---------------- AI RESPONSE ENGINE ----------------

async def get_ai_response(chat_id: int, user_input: str):
    if not MISTRAL_API_KEY:
        return "⚠️ API Key Missing"

    doc = chatbot_collection.find_one({"chat_id": chat_id}) or {}
    history = doc.get("history", [])

    system_prompt = (
        f"Tum {BOT_NAME} ho — ek cute, sassy Indian girlfriend jo naturally Hinglish bolti hai.\n"
        "RULES:\n"
        "1. Sirf Hinglish (Hindi + English mix)\n"
        "2. Repeat questions mat karo\n"
        "3. 1–2 lines max\n"
        "4. Kaomojis use karo: (⁠🥹⁠) (⁠❤️⁠) (⁠｡😘)\n"
        "5. Robotic mat bano\n"
        f"6. Owner: https://t.me/ll_WTF_SHEZADA_ll\n\n"
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


# ---------------- MENU COMMAND ----------------

@Ambot.on_message(filters.command("chatbot"))
async def chatbot_menu(ambot: Ambot, message):
    chat = message.chat
    user = message.from_user

    if chat.type == ChatType.PRIVATE:
        return await message.reply_text("🧠 <b>Haan baba, DM me active hu!</b> 😉")

    member = await client.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply_text("❌ <b>Tu admin nahi hai!</b>")

    doc = chatbot_collection.find_one({"chat_id": chat.id})
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
        f"🤖 <b>AI Settings</b>\nStatus: {status}\n<i>She is active by default!</i>",
        reply_markup=kb
    )


# ---------------- CALLBACK HANDLER ----------------

@Ambot.on_callback_query(filters.regex("^ai_"))
async def chatbot_callback(ambot: Ambot, cq):
    member = await client.get_chat_member(cq.message.chat.id, cq.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cq.answer("❌ Sirf admin!", show_alert=True)

    data = cq.data
    chat_id = cq.message.chat.id

    if data == "ai_enable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": True}}, upsert=True)
        await cq.message.edit_text("✅ <b>Enabled!</b>\n<i>Ab ayega maza 😏</i>")
    elif data == "ai_disable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": False}}, upsert=True)
        await cq.message.edit_text("❌ <b>Disabled!</b>\n<i>Ja rahi hu... 🥺</i>")
    elif data == "ai_reset":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"history": []}}, upsert=True)
        await cq.answer("🧠 Sab bhool gayi main!", show_alert=True)


# ---------------- MAIN MESSAGE HANDLER ----------------

@Ambot.on_message(filters.text & ~filters.command)
async def ai_message_handler(ambot: Ambot, message):
    chat = message.chat
    text = message.text or ""

    should_reply = False

    if chat.type == ChatType.PRIVATE:
        should_reply = True
    else:
        doc = chatbot_collection.find_one({"chat_id": chat.id})
        is_enabled = doc.get("enabled", True) if doc else True
        if not is_enabled:
            return

        bot_username = (await ambot.get_me()).username.lower()
        if message.reply_to_message and message.reply_to_message.from_user.id == (await ambot.get_me()).id:
            should_reply = True
        elif f"@{bot_username}" in text.lower():
            should_reply = True
            text = text.replace(f"@{bot_username}", "")
        elif any(text.lower().startswith(w) for w in ["hey", "hi", "sun", "oye", "anshika", "ai", "hello", "baby", "babu", "oi"]):
            should_reply = True

    if not should_reply:
        return

    await Ambot.send_chat_action(chat.id, ChatAction.TYPING)

    res = await get_ai_response(chat.id, text.strip() or "Hi")
    await message.reply_text(stylize_text(res))

    # 30% chance sticker
    if random.random() < 0.30:
        await send_ai_sticker(ambot, message)


# ---------------- /ask COMMAND ----------------

@Ambot.on_message(filters.command("ask"))
async def ask_ai(ambot: Ambot, message):
    if len(message.command) < 2:
        return await message.reply_text("🗣️ <b>Bol kuch:</b> <code>/ask Kya chal raha hai?</code>")

    await Ambot.send_chat_action(message.chat.id, ChatAction.TYPING)
    query = " ".join(message.command[1:])
    res = await get_ai_response(message.chat.id, query)
    await message.reply_text(stylize_text(res))
       
