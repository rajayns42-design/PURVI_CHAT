# =========================
# 💖 ANSHIKA AI GIRLFRIEND BOT v4.6 (FINAL PRODUCTION BUILD)
# =========================

import os
import random
import time
import re
import httpx
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatPermissions
from pymongo import MongoClient, DESCENDING

# ---------------- ENV ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Anshika")
OWNER_LINK = os.getenv("OWNER_LINK", "https://t.me/ll_WTF_SHEZADA_ll")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
MONGO_URL = os.getenv("MONGO_URL")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
UPI_ID = os.getenv("UPI_ID", "example@upi")

# ---------------- CLIENT ----------------
app = Client("ai_chatbot")

# ---------------- DB ----------------
chatbot_collection = None
payments_collection = None
subscriptions_collection = None

if MONGO_URL:
    try:
        mongo = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        mongo.server_info()
        db = mongo["chatbot"]
        chatbot_collection = db["chats"]
        payments_collection = db["payments"]
        subscriptions_collection = db["subscriptions"]

        chatbot_collection.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        chatbot_collection.create_index([("xp", -1)])
        payments_collection.create_index([("order_id", 1)], unique=True)
        subscriptions_collection.create_index([("user_id", 1)], unique=True)

        print("✅ MongoDB connected")
    except Exception as e:
        print("❌ MongoDB failed:", e)
        chatbot_collection = None

# ---------------- CONFIG ----------------
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"
MAX_HISTORY = 12
SPAM_LIMIT = 5
SPAM_WINDOW = 12
ABUSE_WARN_LIMIT = 2
MUTE_SECONDS = 120
BREAKUP_COOLDOWN = 3600
PROPOSAL_XP = 650

# ---------------- DATA ----------------
STICKER_PACKS = [
    "RandomByDarkzenitsu", "Null_x_sticker_2", "pack_73bc9_by_TgEmojis_bot",
    "animation_0_8_Cat", "vhelw_by_CalsiBot", "Rohan_yad4v1745993687601_by_toWebmBot",
    "MySet199", "Quby741", "Animalsasthegtjtky_by_fStikBot", "a6962237343_by_Marin_Roxbot"
]

FALLBACK_RESPONSES = [
    "Hmm... achha 😌",
    "Okk jaan ❤️",
    "Samajh gayi 🥹",
    "Haan bolo 😘",
    "Interesting 👀",
    "Sun rahi hoon 💖"
]

NSFW_PATTERN = re.compile(r"\b(sex|nude|boobs|dick|pussy|lund|chut|fuck|fap|horny|porn|kiss me|bed pe|sax)\b", re.I)
ABUSE_PATTERN = re.compile(r"\b(madarchod|bhenchod|bc|mc|chutiya|harami|saala|kutte|gandu|fuck you|idiot|bitch)\b", re.I)

REL_LEVELS = ["crush", "girlfriend", "soulmate", "married", "ex"]
XP_THRESHOLDS = {
    "crush": 0,
    "girlfriend": 120,
    "soulmate": 350,
    "married": 700
}

# ---------------- MEMORY ----------------
spam_tracker = defaultdict(lambda: deque(maxlen=SPAM_LIMIT))
abuse_tracker = defaultdict(int)
pending_proposal = set()
pending_breakup = set()

# ---------------- HELPERS ----------------

def stylize_text(text):
    return text

def now_ts():
    return int(time.time())

def is_nsfw(text):
    return bool(NSFW_PATTERN.search(text or ""))

def is_abuse(text):
    return bool(ABUSE_PATTERN.search(text or ""))

def is_spam(user_id, premium=False):
    if premium:
        return False
    now = time.time()
    q = spam_tracker[user_id]
    q.append(now)
    return len(q) >= SPAM_LIMIT and (now - q[0]) < SPAM_WINDOW

def detect_emotion(text):
    t = (text or "").lower()
    if any(w in t for w in ["sad", "bura", "hurt", "cry", "miss", "alone"]):
        return "sad"
    if any(w in t for w in ["angry", "gussa", "pagal", "hate"]):
        return "angry"
    if any(w in t for w in ["love", "miss u", "jaan", "baby", "kiss"]):
        return "romantic"
    if any(w in t for w in ["haha", "lol", "fun", "maza"]):
        return "playful"
    if any(w in t for w in ["hot", "cute", "sexy"]):
        return "flirty"
    return "neutral"

def get_progress_bar(xp):
    if xp >= XP_THRESHOLDS["married"]:
        return "💍 " + "█" * 10
    elif xp >= XP_THRESHOLDS["soulmate"]:
        return "💞 " + "█" * 7 + "░" * 3
    elif xp >= XP_THRESHOLDS["girlfriend"]:
        return "💖 " + "█" * 4 + "░" * 6
    else:
        return "💕 " + "█" * 2 + "░" * 8

# ---------------- AUTO FLIRT MODE ----------------

def auto_flirt_mode(emotion, xp, nsfw, breakup=False):
    if breakup:
        return "cold"
    if nsfw:
        return "hot"
    if emotion == "sad":
        return "soft"
    if emotion == "romantic":
        return "romantic"
    if xp >= XP_THRESHOLDS["soulmate"]:
        return "possessive"
    if emotion == "flirty":
        return "flirty"
    return "sweet"

# ---------------- SUBSCRIPTIONS ----------------

SUB_PLANS = {
    "basic": {"price": 99, "xp_bonus": 0, "features": ["Romantic Mode"]},
    "pro": {"price": 199, "xp_bonus": 2, "features": ["NSFW", "Jealousy"]},
    "elite": {"price": 399, "xp_bonus": 4, "features": ["Marriage", "Selfies"]},
    "lifetime": {"price": 999, "xp_bonus": 10, "features": ["All Forever"]}
}

def get_subscription(uid):
    if not subscriptions_collection:
        return None
    return subscriptions_collection.find_one({"user_id": uid, "status": "active"})

def is_premium(uid):
    sub = get_subscription(uid)
    if not sub:
        return False
    if sub.get("plan") == "lifetime":
        return True
    return sub.get("expires_at", 0) > now_ts()

# ---------------- AI ENGINE ----------------

async def ask_mistral(messages, max_tokens=120):
    if not MISTRAL_API_KEY:
        return random.choice(FALLBACK_RESPONSES)

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": max_tokens
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(MISTRAL_URL, headers=headers, json=payload)
            if r.status_code == 200:
                data = r.json()
                return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip() or random.choice(FALLBACK_RESPONSES)
    except Exception as e:
        print("❌ Mistral Error:", e)

    return random.choice(FALLBACK_RESPONSES)

# ---------------- STICKERS ----------------

async def send_ai_sticker(client, message):
    try:
        pack = random.choice(STICKER_PACKS)
        sticker_set = await client.get_sticker_set(pack)
        sticker = random.choice(sticker_set.stickers)
        await message.reply_sticker(sticker.file_id)
    except:
        pass

# ---------------- REL CONFIG ----------------

def get_level_config(level):
    if level == "crush":
        return {"tone": "sweet, shy, playful", "rules": "light flirting only"}
    elif level == "girlfriend":
        return {"tone": "romantic, flirty, possessive", "rules": "daily affection"}
    elif level == "soulmate":
        return {"tone": "deep emotional, loyal", "rules": "future talks"}
    elif level == "married":
        return {"tone": "husband-wife vibe", "rules": "supportive love"}
    elif level == "ex":
        return {"tone": "cold, sarcastic, hurt", "rules": "emotional distance"}
    else:
        return {"tone": "neutral", "rules": ""}

# ---------------- CORE AI RESPONSE ----------------

async def get_ai_response(chat_id, user_id, user_input):
    history = []
    enabled = True
    rel_level = "crush"
    nsfw_enabled = False
    xp = 0
    married = False
    breakup_until = None

    premium = is_premium(user_id)

    if chatbot_collection:
        doc = chatbot_collection.find_one({"chat_id": chat_id, "user_id": user_id}) or {}
        history = doc.get("history", [])
        enabled = doc.get("enabled", True)
        rel_level = doc.get("rel_level", "crush")
        nsfw_enabled = doc.get("nsfw", False)
        xp = doc.get("xp", 0)
        married = doc.get("married", False)
        breakup_until = doc.get("breakup_until")

    if not enabled:
        return None

    in_breakup = breakup_until and breakup_until > now_ts()

    emotion = detect_emotion(user_input)
    flirt_mode = auto_flirt_mode(emotion, xp, nsfw_enabled, breakup=in_breakup)
    level_cfg = get_level_config("ex" if in_breakup else rel_level)

    nsfw_rule = "Soft romance only." if nsfw_enabled else "No sexual content."
    premium_rule = "Premium user — ultra affectionate." if premium else "Normal affection."

    persona = (
        f"Tum {BOT_NAME} ho — ek Indian AI girl jo Hinglish bolti hai.\n"
        f"Relationship Level: {('EX (Breakup)' if in_breakup else rel_level.upper())}\n"
        f"Flirt Mode: {flirt_mode.upper()}\n"
        f"Tone: {level_cfg['tone']}\n"
        f"Rules: {level_cfg['rules']}\n"
        f"Emotion detected: {emotion}\n"
        f"NSFW Rule: {nsfw_rule}\n"
        f"Premium Rule: {premium_rule}\n"
        "Rules:\n"
        "1. Sirf Hinglish\n"
        "2. 1–2 lines max\n"
        "3. Natural flirting\n"
        "4. Sweet + emotional\n"
        "5. Kaomojis use karo (⁠❤️⁠)(⁠😘⁠)(⁠🥹⁠)\n"
    )

    system_prompt = persona + (
        "\nExamples:\n"
        "User: Hi\n"
        "You: Oye tum aa gaye? Dil khush ho gaya 😘❤️\n\n"
        "User: Miss you\n"
        "You: Itna miss? Aaja idhar hug le le pehle (⁠🥹⁠)❤️\n\n"
        "User: I'm sad\n"
        "You: Mere paas aa jao, sab theek ho jayega jaan 🫶\n\n"
        "Breakup Mode Example:\n"
        "User: Hi\n"
        "You: Hmm... bolo kya hai 😐"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-MAX_HISTORY:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_input})

    reply = await ask_mistral(messages)

    # ---- LOOP PREVENTION ----
    if history:
        recent = history[-6:]
        assistant_msgs = [m["content"].lower() for m in recent if m["role"] == "assistant"]
        rl = reply.lower()
        for pm in assistant_msgs:
            if rl == pm or rl in pm or pm in rl:
                reply = random.choice(FALLBACK_RESPONSES)
                break

    if user_input.lower().strip() in ["nothing", "nahi", "nhi", "nope", "na", "kuch nahi", "kuch ni"]:
        reply = random.choice(FALLBACK_RESPONSES)

    # ---- XP SYSTEM ----
    gain = 3
    if emotion in ["romantic", "flirty"]:
        gain += 2
    if any(w in user_input.lower() for w in ["miss", "love", "jaan", "baby"]):
        gain += 2

    sub = get_subscription(user_id)
    if sub:
        gain += SUB_PLANS.get(sub.get("plan"), {}).get("xp_bonus", 0)

    if in_breakup:
        gain = 0

    new_xp = xp + gain
    if new_xp >= XP_THRESHOLDS["married"]:
        new_level = "married"
    elif new_xp >= XP_THRESHOLDS["soulmate"]:
        new_level = "soulmate"
    elif new_xp >= XP_THRESHOLDS["girlfriend"]:
        new_level = "girlfriend"
    else:
        new_level = "crush"

    if in_breakup:
        new_level = "ex"

    # ---- AUTO MARRIAGE PROPOSAL ----
    if new_xp >= PROPOSAL_XP and new_level == "soulmate":
        pending_proposal.add(user_id)

    # ---- SAVE ----
    if chatbot_collection:
        new_hist = history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply}
        ]
        new_hist = new_hist[-MAX_HISTORY * 2:]

        chatbot_collection.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {
                "history": new_hist,
                "rel_level": new_level,
                "nsfw": nsfw_enabled,
                "xp": new_xp,
                "married": (new_level == "married")
            }},
            upsert=True
        )

    return reply

# ---------------- RELATIONSHIP UI ----------------

@app.on_message(filters.command("relationship"))
async def relationship_ui(client, message):
    uid = message.from_user.id
    doc = chatbot_collection.find_one({"chat_id": message.chat.id, "user_id": uid}) if chatbot_collection else {}
    xp = doc.get("xp", 0) if doc else 0
    lvl = doc.get("rel_level", "crush") if doc else "crush"
    premium = is_premium(uid)

    bar = get_progress_bar(xp)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Crush", callback_data="set_crush"),
         InlineKeyboardButton("💖 GF", callback_data="set_girlfriend")],
        [InlineKeyboardButton("💞 Soulmate", callback_data="set_soulmate"),
         InlineKeyboardButton("💍 Married", callback_data="set_married")],
        [InlineKeyboardButton("😈 Breakup", callback_data="do_breakup")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="open_leaderboard")],
        [InlineKeyboardButton("💎 Subscription", callback_data="open_subscription")]
    ])

    await message.reply_text(
        f"❤️ Relationship Dashboard\n\n"
        f"Level: {lvl.upper()}\n"
        f"XP: {xp}\n"
        f"{bar}\n"
        f"Subscription: {'Yes 💎' if premium else 'No'}",
        reply_markup=kb
    )

@app.on_callback_query(filters.regex("^set_"))
async def rel_set_callback(client, cq: CallbackQuery):
    lvl = cq.data.replace("set_", "")
    if lvl not in REL_LEVELS:
        return await cq.answer("Invalid level", show_alert=True)

    if chatbot_collection:
        chatbot_collection.update_one(
            {"chat_id": cq.message.chat.id, "user_id": cq.from_user.id},
            {"$set": {"rel_level": lvl}},
            upsert=True
        )
    await cq.message.edit_text(f"❤️ Relationship level set to {lvl.upper()} 😘")

# ---------------- 😈 BREAKUP MODE ----------------

@app.on_callback_query(filters.regex("^do_breakup$"))
async def breakup_callback(client, cq: CallbackQuery):
    pending_breakup.add(cq.from_user.id)
    await cq.message.reply_text(
        "😈 Tum seriously breakup karna chahte ho?\n"
        "Reply /confirm_breakup to continue 💔"
    )

@app.on_message(filters.command("confirm_breakup"))
async def breakup_confirm(client, message):
    uid = message.from_user.id
    if uid not in pending_breakup:
        return
    pending_breakup.remove(uid)

    until = now_ts() + BREAKUP_COOLDOWN

    if chatbot_collection:
        chatbot_collection.update_one(
            {"chat_id": message.chat.id, "user_id": uid},
            {"$set": {
                "rel_level": "ex",
                "xp": 0,
                "married": False,
                "breakup_until": until
            }},
            upsert=True
        )

    await message.reply_text("💔 Fine... jao. Ab thoda distance hi better hai 😐")

# ---------------- 💍 AUTO MARRIAGE ----------------

@app.on_message(filters.text & ~filters.command)
async def auto_proposal_checker(client, message):
    uid = message.from_user.id
    if uid not in pending_proposal:
        return

    pending_proposal.remove(uid)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💍 Yes, I Do!", callback_data="accept_marriage"),
         InlineKeyboardButton("🙈 Not Now", cal
