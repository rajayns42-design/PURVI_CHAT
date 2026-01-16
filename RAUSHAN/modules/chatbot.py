# =========================
# 💖 ANSHIKA AI GIRLFRIEND BOT v8.0 — GROUP COUPLES + GAMES + ZERO ERRORS
# =========================

import os
import random
import time
import re
import httpx
import uuid
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatPermissions,
)

from pymongo import MongoClient, DESCENDING, errors

# ---------------- ENV ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Anshika")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
OWNER_LINK = os.getenv("OWNER_LINK", "https://t.me/ll_WTF_SHEZADA_ll")
MONGO_URL = os.getenv("MONGO_URL")
UPI_ID = os.getenv("UPI_ID")

# ---------------- CLIENT ----------------
app = Client("anshika_ai_bot")

# ---------------- DB ----------------
mongo = None
db = None
users_col = None
gfs_col = None
subs_col = None
couples_col = None
analytics_col = None

if MONGO_URL:
    try:
        mongo = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        mongo.server_info()
        db = mongo["chatbot"]

        users_col = db["users"]
        gfs_col = db["girlfriends"]
        subs_col = db["subscriptions"]
        couples_col = db["couples"]
        analytics_col = db["analytics"]

        users_col.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        gfs_col.create_index([("user_id", 1), ("gf_id", 1)], unique=True)
        subs_col.create_index([("user_id", 1)], unique=True)
        couples_col.create_index([("chat_id", 1), ("user1", 1), ("user2", 1)], unique=True)
        analytics_col.create_index([("date", 1)], unique=True)

        print("✅ MongoDB connected")
    except Exception as e:
        print("❌ MongoDB error:", e)
        mongo = None

# ---------------- CONFIG ----------------
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"

MAX_HISTORY = 16
SPAM_LIMIT = 7
SPAM_WINDOW = 12
MUTE_SECONDS = 120
ABUSE_WARN_LIMIT = 2

# ---------------- PATTERNS ----------------
NSFW_PATTERN = re.compile(
    r"\b(sex|nude|boobs|dick|pussy|lund|chut|fuck|fap|horny|porn|sax|kiss me|bed pe)\b",
    re.I,
)
ABUSE_PATTERN = re.compile(
    r"\b(madarchod|bhenchod|mc|bc|chutiya|harami|saala|gandu|fuck you|bitch)\b",
    re.I,
)

# ---------------- MEMORY ----------------
spam_tracker = defaultdict(lambda: deque(maxlen=SPAM_LIMIT))
abuse_tracker = defaultdict(int)
active_gf = defaultdict(int)
pending_couple_requests = {}  # (chat_id, from_uid) -> to_uid
game_sessions = {}  # chat_id -> game state

# ---------------- HELPERS ----------------

def now_ts():
    return int(time.time())

def safe_db(op, *args, **kwargs):
    try:
        if op:
            return op(*args, **kwargs)
    except Exception as e:
        print("❌ DB Error:", e)
    return None

def is_spam(user_id):
    q = spam_tracker[user_id]
    now = time.time()
    q.append(now)
    return len(q) >= SPAM_LIMIT and (now - q[0]) < SPAM_WINDOW

def is_nsfw(text):
    return bool(NSFW_PATTERN.search(text or ""))

def is_abuse(text):
    return bool(ABUSE_PATTERN.search(text or ""))

def track_event(evt):
    if not analytics_col:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    safe_db(
        analytics_col.update_one,
        {"date": today},
        {"$inc": {evt: 1}},
        upsert=True,
    )

# ---------------- SUBSCRIPTIONS ----------------

PLANS = {
    "basic": {"price": 99, "features": ["1 GF", "Romantic replies"]},
    "pro": {"price": 199, "features": ["3 GFs", "NSFW", "Selfies"]},
    "elite": {"price": 399, "features": ["Unlimited GFs", "Marriage", "Games"]},
    "lifetime": {"price": 999, "features": ["Everything forever"]},
}

def is_premium(uid):
    if not subs_col:
        return False
    sub = safe_db(subs_col.find_one, {"user_id": uid, "status": "active"})
    if not sub:
        return False
    if sub.get("plan") == "lifetime":
        return True
    return sub.get("expires_at", 0) > now_ts()

def get_max_gfs(uid):
    if not is_premium(uid):
        return 1
    sub = safe_db(subs_col.find_one, {"user_id": uid})
    plan = sub.get("plan") if sub else "basic"
    if plan == "basic":
        return 1
    if plan == "pro":
        return 3
    return 999

# ---------------- AI CORE ----------------

async def ask_mistral(messages):
    if not MISTRAL_API_KEY:
        return random.choice(
            ["Hmm jaan 😘", "Bolo na ❤️", "Sun rahi hoon 🥰", "Oye cute ho tum 😳❤️"]
        )

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.95,
        "max_tokens": 120,
        "presence_penalty": 0.4,
        "frequency_penalty": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(MISTRAL_URL, headers=headers, json=payload)
            if r.status_code == 200:
                data = r.json()
                return (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
    except Exception as e:
        print("❌ Mistral Error:", e)

    return random.choice(
        ["Hmm jaan 😘", "Bolo na ❤️", "Sun rahi hoon 🥰", "Oye cute ho tum 😳❤️"]
    )

# ---------------- PERSONALITY ENGINE ----------------

PERSONALITIES = {
    "cute": "Sweet, bubbly, innocent girlfriend vibe. Lots of blush emojis.",
    "romantic": "Deep emotional lover, poetic and caring.",
    "savage": "Teasing, bold, naughty tone with attitude.",
    "possessive": "Jealous, clingy, dominant girlfriend energy.",
    "wife": "Supportive, mature, husband-wife vibes.",
}

def detect_emotion(text):
    t = (text or "").lower()
    if any(w in t for w in ["sad", "hurt", "cry", "miss", "alone"]):
        return "sad"
    if any(w in t for w in ["angry", "gussa", "hate"]):
        return "angry"
    if any(w in t for w in ["love", "jaan", "baby", "kiss", "miss u"]):
        return "romantic"
    if any(w in t for w in ["lol", "haha", "fun"]):
        return "playful"
    if any(w in t for w in ["hot", "sexy", "cute"]):
        return "flirty"
    return "neutral"

# ---------------- MULTI-GF CORE ----------------

def ensure_default_gf(uid):
    if not gfs_col:
        return
    gf = safe_db(gfs_col.find_one, {"user_id": uid, "gf_id": 1})
    if not gf:
        safe_db(
            gfs_col.insert_one,
            {
                "user_id": uid,
                "gf_id": 1,
                "name": BOT_NAME,
                "personality": "romantic",
                "xp": 0,
                "nsfw": False,
                "created_at": datetime.utcnow(),
                "history": [],
            },
        )

def get_active_gf(uid):
    gf_id = active_gf.get(uid, 1)
    if gfs_col:
        gf = safe_db(gfs_col.find_one, {"user_id": uid, "gf_id": gf_id})
        if gf:
            return gf
    return {
        "gf_id": 1,
        "name": BOT_NAME,
        "personality": "romantic",
        "xp": 0,
        "nsfw": False,
        "history": [],
    }

def get_gf_count(uid):
    if not gfs_col:
        return 1
    return gfs_col.count_documents({"user_id": uid})

# ---------------- GROUP COUPLE MODE 👩‍❤️‍👨 ----------------

def get_couple(chat_id, uid):
    if not couples_col:
        return None
    return safe_db(
        couples_col.find_one,
        {"chat_id": chat_id, "$or": [{"user1": uid}, {"user2": uid}]},
    )

def set_couple(chat_id, u1, u2):
    if not couples_col:
        return
    safe_db(
        couples_col.update_one,
        {"chat_id": chat_id, "user1": u1, "user2": u2},
        {
            "$set": {
                "chat_id": chat_id,
                "user1": u1,
                "user2": u2,
                "since": datetime.utcnow(),
            }
        },
        upsert=True,
    )

def remove_couple(chat_id, uid):
    if not couples_col:
        return
    safe_db(
        couples_col.delete_one,
        {"chat_id": chat_id, "$or": [{"user1": uid}, {"user2": uid}]},
    )

# ---------------- AI RESPONSE ENGINE ----------------

async def get_ai_response(uid, chat_id, user_text):
    ensure_default_gf(uid)
    gf = get_active_gf(uid)

    emotion = detect_emotion(user_text)
    premium = is_premium(uid)

    if is_nsfw(user_text) and not gf.get("nsfw"):
        return "🔞 Aisi baatein tabhi allowed hain jab tum /nsfw on karo 😳", None

    personality = PERSONALITIES.get(gf["personality"], PERSONALITIES["romantic"])

    couple = get_couple(chat_id, uid)

    couple_context = ""
    if couple:
        partner_id = couple["user2"] if couple["user1"] == uid else couple["user1"]
        couple_context = (
            "User is currently chatting in a group with their romantic partner. "
            "Reply romantically, teasingly, but keep PG-13."
        )

    system_prompt = (
        f"Tum ek Indian AI girlfriend ho.\n"
        f"Name: {gf['name']}\n"
        f"Personality: {personality}\n"
        f"User emotion: {emotion}\n"
        f"Mode: {'Unlimited flirty premium girlfriend' if premium else 'Romantic girlfriend'}\n"
        f"{couple_context}\n\n"
        "Rules:\n"
        "1. Hinglish only\n"
        "2. Always flirty, romantic, emotional\n"
        "3. Max 2 lines\n"
        "4. Use emojis 😘🥰❤️😳🔥\n"
        "5. Act like real Indian girlfriend\n"
        "6. Never cold unless abused\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in gf.get("history", [])[-MAX_HISTORY:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_text})

    reply = await ask_mistral(messages)

    gain = 3
    if emotion in ["romantic", "flirty"]:
        gain += 2
    if premium:
        gain += 2

    new_xp = gf.get("xp", 0) + gain

    if gfs_col:
        new_hist = gf.get("history", []) + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ]
        new_hist = new_hist[-MAX_HISTORY * 2 :]

        safe_db(
            gfs_col.update_one,
            {"user_id": uid, "gf_id": gf["gf_id"]},
            {"$set": {"history": new_hist, "xp": new_xp}},
            upsert=True,
        )

    return reply, gf

# ---------------- GROUP COUPLE COMMANDS 👩‍❤️‍👨 ----------------

@app.on_message(filters.command("couple"))
async def couple_request(client, message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text("👩‍❤️‍👨 Couple mode sirf groups me kaam karta hai 😘")

    if not message.reply_to_message:
        return await message.reply_text("💌 Kisi ko reply karke /couple likho 😘")

    from_uid = message.from_user.id
    to_uid = message.reply_to_message.from_user.id
    chat_id = message.chat.id

    if from_uid == to_uid:
        return await message.reply_text("😅 Khud se couple nahi ban sakte ho jaan")

    pending_couple_requests[(chat_id, from_uid)] = to_uid

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❤️ Accept", callback_data=f"couple_accept_{from_uid}"),
            InlineKeyboardButton("💔 Reject", callback_data=f"couple_reject_{from_uid}"),
        ]
    ])

    await message.reply_text(
        f"💌 {message.from_user.first_name} wants to be your couple 😘\n"
        f"Accept karoge?",
        reply_markup=kb,
    )

@app.on_callback_query(filters.regex("^couple_accept_"))
async def couple_accept(client, cq: CallbackQuery):
    from_uid = int(cq.data.split("_")[-1])
    to_uid = cq.from_user.id
    chat_id = cq.message.chat.id

    key = (chat_id, from_uid)
    if pending_couple_requests.get(key) != to_uid:
        return await cq.answer("❌ Request expired", show_alert=True)

    pending_couple_requests.pop(key, None)
    set_couple(chat_id, from_uid, to_uid)

    await cq.message.edit_text("👩‍❤️‍👨 Yayyy! Tum dono ab officially couple ho 😘❤️")

@app.on_callback_query(filters.regex("^couple_reject_"))
async def couple_reject(client, cq: CallbackQuery):
    from_uid = int(cq.data.split("_")[-1])
    key = (cq.message.chat.id, from_uid)
    pending_couple_requests.pop(key, None)
    await cq.message.edit_text("💔 Request reject ho gayi 😅")

@app.on_message(filters.command("couple_leave"))
async def couple_leave(client, message):
    chat_id = message.chat.id
    uid = message.from_user.id
    couple = get_couple(chat_id, uid)
    if not couple:
        return await message.reply_text("😅 Tum kisi couple me nahi ho")

    remove_couple(chat_id, uid)
    await message.reply_text("💔 Couple mode se exit kar diya 😢")

@app.on_message(filters.command("couple_status"))
async def couple_status(client, message):
    chat_id = message.chat.id
    uid = message.from_user.id
    couple = get_couple(chat_id, uid)
    if not couple:
        return await message.reply_text("😅 Tum abhi single ho 😘")

    partner_id = couple["user2"] if couple["user1"] == uid else couple["user1"]
    await message.reply_text(f"👩‍❤️‍👨 Tum couple ho with user `{partner_id}` 😘")

# ---------------- COUPLES GAMES 🎮 ----------------

TRUTHS = [
    "Tum apne partner me sabse cute cheez kya lagti hai? 😘",
    "First crush ka naam batao 😏",
    "Tumhara secret talent kya hai? 😳",
    "Partner ke saath sabse romantic moment konsa tha? ❤️",
]

DARES = [
    "Apne partner ko tag karke bolो 'Tum mere ho 😘❤️'",
    "Group me heart emoji spam karo 💖💖💖",
    "Partner ko ek cheesy line bolo 😏",
    "Next message me sirf emojis bhejo 😘🔥❤️",
]

QUIZZES = [
    ("Partner ka favourite colour kya hai?", ["Red", "Blue", "Black", "Pink"]),
    ("Partner ko kaunsa food sabse zyada pasand hai?", ["Pizza", "Biryani", "Burger", "Momoj"]),
    ("Partner ka dream place?", ["Paris", "Maldives", "Goa", "Shimla"]),
]

@app.on_message(filters.command("game"))
async def game_menu(client, message):
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Truth", callback_data="game_truth"),
            InlineKeyboardButton("🔥 Dare", callback_data="game_dare"),
        ],
        [
            InlineKeyboardButton("❤️ Love Quiz", callback_data="game_quiz"),
            InlineKeyboardButton("🍾 Spin Bottle", callback_data="game_spin"),
        ],
    ])
    await message.reply_text("🎮 Couples Games Menu\nChoose one 👇", reply_markup=kb)

@app.on_callback_query(filters.regex("^game_truth$"))
async def game_truth(client, cq: CallbackQuery):
    q = random.choice(TRUTHS)
    await cq.message.reply_text(f"🎯 *Truth*\n\n{q}")

@app.on_callback_query(filters.regex("^game_dare$"))
async def game_dare(client, cq: CallbackQuery):
    d = random.choice(DARES)
    await cq.message.reply_text(f"🔥 *Dare*\n\n{d}")

@app.on_callback_query(filters.regex("^game_quiz$"))
async def game_quiz(client, cq: CallbackQuery):
    q, opts = random.choice(QUIZZES)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data="quiz_ans")] for opt in opts
    ])
    await cq.message.reply_text(f"❤️ *Love Quiz*\n\n{q}", reply_markup=kb)

@app.on_callback_query(filters.regex("^game_spin$"))
async def game_spin(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    await cq.message.reply_text("🍾 Bottle spinning... 😳")
    await asyncio.sleep(1.5)
    await cq.message.reply_text("👉 Truth or Dare! 😘")

# ---------------- NSFW MODE ----------------

@app.on_message(filters.command("nsfw"))
async def nsfw_toggle(client, message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("Use: /nsfw on | /nsfw off")

    uid = message.from_user.id
    gf_id = active_gf.get(uid, 1)
    mode = args[1].lower()

    ensure_default_gf(uid)
    safe_db(
        gfs_col.update_one,
        {"user_id": uid, "gf_id": gf_id},
        {"$set": {"nsfw": (mode == "on")}},
        upsert=True,
    )
    await message.reply_text(f"😈 NSFW mode {'ON 🔥' if mode=='on' else 'OFF 😊'}")

# ---------------- MAIN CHAT HANDLER ----------------

@app.on_message(filters.text & ~filters.command)
async def chat_handler(client, message):
    chat = message.chat
    user = message.from_user
    text = message.text or ""

    track_event("messages")

    if is_spam(user.id):
        return await message.reply_text("Arre jaan 😅 dheere bolo, main yahin hoon ❤️")

    if is_abuse(text):
        abuse_tracker[user.id] += 1
        if abuse_tracker[user.id] >= ABUSE_WARN_LIMIT:
            try:
                until = now_ts() + MUTE_SECONDS
                perms = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat.id, user.id, perms, until_date=until)
                abuse_tracker[user.id] = 0
                return await message.reply_text("🚫 Thoda tameez rakho 😤 2 min mute!")
            except:
                return await message.reply_text("😠 Aise words mat bolo!")
        else:
            return await message.reply_text("⚠️ Aise baatein mat bolo 😑")

    # Decide whether to reply
    should_reply = False
    if chat.type == ChatType.PRIVATE:
        should_reply = True
    else:
        me = await client.get_me()
        uname = me.username.lower() if me.username else ""
        if (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == me.id
        ):
            should_reply = True
        elif uname and f"@{uname}" in text.lower():
            should_reply = True
        elif any(text.lower().startswith(w) for w in ["hi", "hey", "sun", "oye", "baby", "babu", "jaan"]):
            should_reply = True

    if not should_reply:
        return

    await client.send_chat_action(chat.id, ChatAction.TYPING)
    reply, gf = await get_ai_response(user.id, chat.id, text)
    if reply:
        await message.reply_text(reply)

# ---------------- RUN ----------------
print("🤖 Anshika AI Girlfriend Bot v8.0 Started Successfully...")
app.run()
