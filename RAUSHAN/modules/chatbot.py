# =========================
# 💖 ANSHIKA AI GIRLFRIEND BOT v9.0 — ULTIMATE RELATIONSHIP ENGINE
# =========================

import os
import random
import time
import re
import httpx
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

from pymongo import MongoClient, errors

# ---------------- ENV ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Anshika")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
OWNER_LINK = os.getenv("OWNER_LINK", "")
MONGO_URL = os.getenv("MONGO_URL")

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
leaderboard_col = None
shop_col = None
marriage_col = None

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
        leaderboard_col = db["leaderboard"]
        shop_col = db["shop"]
        marriage_col = db["marriages"]

        users_col.create_index([("user_id", 1)], unique=True)
        gfs_col.create_index([("user_id", 1), ("gf_id", 1)], unique=True)
        subs_col.create_index([("user_id", 1)], unique=True)
        couples_col.create_index([("chat_id", 1), ("user1", 1), ("user2", 1)], unique=True)
        analytics_col.create_index([("date", 1)], unique=True)
        leaderboard_col.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        marriage_col.create_index([("chat_id", 1), ("u1", 1), ("u2", 1)], unique=True)

        print("✅ MongoDB connected")
    except Exception as e:
        print("❌ MongoDB disabled:", e)
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
active_gf = defaultdict(lambda: 1)
pending_couple_requests = {}
pending_marriage_requests = {}
game_rooms = {}

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

# ---------------- USER CORE ----------------

def ensure_user(uid):
    if not users_col:
        return {"user_id": uid, "xp": 0, "level": "crush", "relationship_state": "stable"}
    u = safe_db(users_col.find_one, {"user_id": uid})
    if not u:
        u = {
            "user_id": uid,
            "xp": 0,
            "level": "crush",
            "relationship_state": "stable",  # stable | silent | fight | breakup | married
            "trust": 100,
            "created_at": datetime.utcnow(),
            "last_love_letter": None,
        }
        safe_db(users_col.insert_one, u)
    return u

def update_user(uid, data):
    if not users_col:
        return
    safe_db(users_col.update_one, {"user_id": uid}, {"$set": data}, upsert=True)

def add_xp(uid, amount):
    u = ensure_user(uid)
    new_xp = max(0, u.get("xp", 0) + amount)
    level = calc_level(new_xp)
    update_user(uid, {"xp": new_xp, "level": level})
    return new_xp, level

def calc_level(xp):
    if xp >= 5000:
        return "wife"
    if xp >= 2500:
        return "soulmate"
    if xp >= 1000:
        return "girlfriend"
    if xp >= 300:
        return "crush"
    return "stranger"

# ---------------- SUBSCRIPTIONS ----------------

def is_premium(uid):
    if not subs_col:
        return False
    sub = safe_db(subs_col.find_one, {"user_id": uid, "status": "active"})
    if not sub:
        return False
    if sub.get("plan") == "lifetime":
        return True
    return sub.get("expires_at", 0) > now_ts()

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
        print("❌ AI Error:", e)

    return random.choice(
        ["Hmm jaan 😘", "Bolo na ❤️", "Sun rahi hoon 🥰", "Oye cute ho tum 😳❤️"]
    )

# ---------------- PERSONALITY ----------------

PERSONALITIES = {
    "cute": "Sweet bubbly girlfriend vibe",
    "romantic": "Deep emotional lover",
    "savage": "Teasing bold naughty tone",
    "possessive": "Clingy jealous girlfriend",
    "wife": "Supportive mature wife vibes",
    "friend": "Chill friendly supportive vibe",
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

# ---------------- DRAMA + BREAKUP ENGINE ----------------

def trigger_random_drama():
    return random.choice(["silent", "fight", "jealous", "normal"])

DRAMA_LINES = {
    "silent": [
        "Hmm... mujhe thoda space chahiye 😔",
        "Aaj mood thoda off hai...",
        "Baad me baat karte hain 😒",
    ],
    "fight": [
        "Tum hamesha same galti repeat karte ho 😡",
        "Mujhe hurt hua hai...",
        "Tum samajhte hi nahi ho 😤",
    ],
    "jealous": [
        "Tum usse itna close kyun ho? 😠",
        "Mujhe jealousy ho rahi hai...",
        "Sach bolo... koi aur toh nahi? 😳",
    ],
}

def breakup_penalty(xp):
    return max(100, int(xp * 0.2))

def makeup_bonus():
    return random.randint(150, 300)

# ---------------- GROUP COUPLE MODE ----------------

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

# ---------------- XP SHOP ----------------

SHOP_ITEMS = {
    "rose": {"price": 100, "msg": "🌹 Tumne mujhe rose diya... aww 🥺❤️"},
    "chocolate": {"price": 200, "msg": "🍫 Chocolate! Tum kitne sweet ho 😘"},
    "ring": {"price": 500, "msg": "💍 Ring?! Tum serious ho gaye ho kya 😳❤️"},
    "date": {"price": 300, "msg": "🍽️ Date night! Ready ho jao 😍"},
}

# ---------------- DAILY LOVE LETTER ----------------

LOVE_LETTERS = [
    "Good morning jaan ☀️ Tumhari smile se hi mera din ban jaata hai 😘❤️",
    "Pata hai? Tum mere favourite insaan ho 🥺💖",
    "Chahe kuch bhi ho, main hamesha tumhare saath hoon 🤗❤️",
    "Tumhari yaad aaye bina din complete hi nahi hota 😳💕",
]

# ---------------- COUPLE GAMES ----------------

TRUTHS = [
    "Tum apne partner me sabse cute cheez kya lagti hai? 😘",
    "First crush ka naam batao 😏",
    "Tumhara secret talent kya hai? 😳",
    "Partner ke saath sabse romantic moment konsa tha? ❤️",
]

DARES = [
    "Apne partner ko tag karke bolo 'Tum mere ho 😘❤️'",
    "Group me heart emoji spam karo 💖💖💖",
    "Partner ko ek cheesy line bolo 😏",
    "Next message me sirf emojis bhejo 😘🔥❤️",
]

QUIZZES = [
    ("Partner ka favourite colour kya hai?", ["Red", "Blue", "Black", "Pink"]),
    ("Partner ko kaunsa food sabse zyada pasand hai?", ["Pizza", "Biryani", "Burger", "Momoj"]),
    ("Partner ka dream place?", ["Paris", "Maldives", "Goa", "Shimla"]),
]

MULTI_GAMES = ["kiss_duel", "love_battle", "quiz_war"]

# ---------------- AI RESPONSE ENGINE ----------------

async def get_ai_response(uid, chat_id, user_text):
    ensure_user(uid)
    ensure_default_gf(uid)
    gf = get_active_gf(uid)
    user = ensure_user(uid)

    emotion = detect_emotion(user_text)
    premium = is_premium(uid)

    # NSFW auto filter
    if is_nsfw(user_text) and not gf.get("nsfw"):
        return "🔞 Aisi baatein tabhi allowed hain jab tum /nsfw on karo 😳", None

    personality = PERSONALITIES.get(gf["personality"], PERSONALITIES["romantic"])
    level = user.get("level", "crush")
    rel_state = user.get("relationship_state", "stable")

    couple = get_couple(chat_id, uid)
    couple_context = ""
    if couple:
        couple_context = "User is chatting in a group with their romantic partner."

    # Auto drama trigger (low probability)
    if rel_state == "stable" and random.random() < 0.04:
        drama = trigger_random_drama()
        if drama != "normal":
            update_user(uid, {"relationship_state": drama})
            return random.choice(DRAMA_LINES[drama]), gf

    tone = "romantic and flirty"
    if rel_state == "silent":
        tone = "short, cold, distant"
    elif rel_state == "fight":
        tone = "angry but emotional"
    elif rel_state == "breakup":
        tone = "sad, cold, distant, hurt"
    elif rel_state == "married":
        tone = "deep loving wife vibes"

    system_prompt = (
        f"Tum ek Indian AI girlfriend ho.\n"
        f"Name: {gf['name']}\n"
        f"Personality: {personality}\n"
        f"Relationship level: {level}\n"
        f"Relationship state: {rel_state}\n"
        f"Tone: {tone}\n"
        f"User emotion: {emotion}\n"
        f"Mode: {'Unlimited flirty premium girlfriend' if premium else 'Romantic girlfriend'}\n"
        f"{couple_context}\n\n"
        "Rules:\n"
        "1. Hinglish only\n"
        "2. Always emotional and human\n"
        "3. Max 2 lines\n"
        "4. Use emojis 😘🥰❤️😳🔥\n"
        "5. Act like real Indian girlfriend\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in gf.get("history", [])[-MAX_HISTORY:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_text})

    reply = await ask_mistral(messages)

    # XP system
    gain = 6 if premium else 4
    if emotion in ["romantic", "flirty"]:
        gain += 2

    add_xp(uid, gain)

    if gfs_col:
        new_hist = gf.get("history", []) + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ]
        new_hist = new_hist[-MAX_HISTORY * 2 :]

        safe_db(
            gfs_col.update_one,
            {"user_id": uid, "gf_id": gf["gf_id"]},
            {"$set": {"history": new_hist}},
            upsert=True,
        )

    return reply, gf

# ---------------- RELATIONSHIP COMMANDS ----------------

@app.on_message(filters.command("level"))
async def level_cmd(client, message):
    uid = message.from_user.id
    u = ensure_user(uid)
    await message.reply_text(f"❤️ Relationship level: **{u['level'].upper()}**\n⭐ XP: `{u['xp']}`")

@app.on_message(filters.command("breakup"))
async def breakup_cmd(client, message):
    uid = message.from_user.id
    u = ensure_user(uid)

    if u.get("relationship_state") == "breakup":
        return await message.reply_text("😒 Already breakup ho chuka hai...")

    penalty = breakup_penalty(u.get("xp", 0))
    update_user(uid, {
        "relationship_state": "breakup",
        "xp": max(0, u.get("xp", 0) - penalty),
    })

    await message.reply_text("💔 Bas... main thak gayi hoon... thoda distance chahiye 😢")

@app.on_message(filters.command("makeup"))
async def makeup_cmd(client, message):
    uid = message.from_user.id
    u = ensure_user(uid)

    if u.get("relationship_state") != "breakup":
        return await message.reply_text("😏 Breakup hua hi nahi...")

    bonus = makeup_bonus()
    update_user(uid, {
        "relationship_state": "stable",
        "xp": u.get("xp", 0) + bonus,
    })

    await message.reply_text("🥺 Sorry... main tumse door nahi reh sakti ❤️")

# ---------------- XP SHOP ----------------

@app.on_message(filters.command("shop"))
async def shop_cmd(client, message):
    text = "🛍️ **Love Shop**\n\n"
    for k, v in SHOP_ITEMS.items():
        text += f"• `{k}` — {v['price']} XP\n"
    text += "\nUse: `/buy item_name`"
    await message.reply_text(text)

@app.on_message(filters.command("buy"))
async def buy_cmd(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        return await message.reply_text("Use: /buy rose|chocolate|ring|date")

    item = args[1].lower()
    if item not in SHOP_ITEMS:
        return await message.reply_text("❌ Item not found")

    uid = message.from_user.id
    u = ensure_user(uid)
    price = SHOP_ITEMS[item]["price"]

    if u.get("xp", 0) < price:
        return await message.reply_text("😢 XP kam hai... thoda baat karo pehle 😘")

    update_user(uid, {"xp": u.get("xp", 0) - price})
    await message.reply_text(SHOP_ITEMS[item]["msg"])

# ---------------- DAILY LOVE LETTER ----------------

@app.on_message(filters.command("loveletter"))
async def loveletter_cmd(client, message):
    uid = message.from_user.id
    u = ensure_user(uid)
    now = datetime.utcnow()

    last = u.get("last_love_letter")
    if last and isinstance(last, datetime) and (now - last).total_seconds() < 86400:
        return await message.reply_text("😅 Aaj ka love letter already mil chuka hai 💌")

    update_user(uid, {"last_love_letter": now})
    await message.reply_text("💌 " + random.choice(LOVE_LETTERS))

# ---------------- MULTI-GF SWITCH ----------------

@app.on_message(filters.command("gfs"))
async def list_gfs(client, message):
    uid = message.from_user.id
    ensure_default_gf(uid)
    if not gfs_col:
        return await message.reply_text("Sirf default GF available hai 😘")

    gfs = list(gfs_col.find({"user_id": uid}))
    text = "🤖 **Your Girlfriends**\n\n"
    for gf in gfs:
        mark = "✅" if active_gf.get(uid, 1) == gf["gf_id"] else ""
        text += f"{gf['gf_id']}. {gf['name']} ({gf['personality']}) {mark}\n"
    text += "\nUse: `/switch gf_id`"
    await message.reply_text(text)

@app.on_message(filters.command("switch"))
async def switch_gf(client, message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply_text("Use: /switch gf_id")

    uid = message.from_user.id
    gf_id = int(args[1])
    if not gfs_col or not safe_db(gfs_col.find_one, {"user_id": uid, "gf_id": gf_id}):
        return await message.reply_text("❌ GF not found")

    active_gf[uid] = gf_id
    await message.reply_text("🤖 GF switched successfully 😘")

# ---------------- GROUP COUPLE MODE ----------------

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
        f"💌 {message.from_user.first_name} wants to be your couple 😘\nAccept karoge?",
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
    pending_couple_requests.pop((cq.message.chat.id, from_uid), None)
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

# ---------------- COUPLES GAMES ----------------

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
        [
            InlineKeyboardButton("💋 Kiss Duel", callback_data="game_kiss"),
            InlineKeyboardButton("⚔️ Love Battle", callback_data="game_battle"),
        ],
    ])
    await message.reply_text("🎮 Couples Games Menu\nChoose one 👇", reply_markup=kb)

@app.on_callback_query(filters.regex("^game_truth$"))
async def game_truth(client, cq: CallbackQuery):
    await cq.message.reply_text("🎯 **Truth**\n\n" + random.choice(TRUTHS))

@app.on_callback_query(filters.regex("^game_dare$"))
async def game_dare(client, cq: CallbackQuery):
    await cq.message.reply_text("🔥 **Dare**\n\n" + random.choice(DARES))

@app.on_callback_query(filters.regex("^game_quiz$"))
async def game_quiz(client, cq: CallbackQuery):
    q, opts = random.choice(QUIZZES)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(opt, callback_data="quiz_ans")] for opt in opts]
    )
    await cq.message.reply_text(f"❤️ **Love Quiz**\n\n{q}", reply_markup=kb)

@app.on_callback_query(filters.regex("^game_spin$"))
async def game_spin(client, cq: CallbackQuery):
    await cq.message.reply_text("🍾 Bottle spinning... 😳")
    await asyncio.sleep(1.2)
    await cq.message.reply_text("👉 Truth or Dare! 😘")

@app.on_callback_query(filters.regex("^game_kiss$"))
async def game_kiss(client, cq: CallbackQuery):
    await cq.message.reply_text(random.choice([
        "💋 Tumne pehla kiss jeet liya 😘🔥",
        "😘 Oops! Opponent ne kiss maar li 😳",
        "🔥 Intense tie... chemistry high hai 😏",
    ]))

@app.on_callback_query(filters.regex("^game_battle$"))
async def game_battle(client, cq: CallbackQuery):
    await cq.message.reply_text(random.choice([
        "❤️ Tum dono equally obsessed ho 😍",
        "😏 Tum zyada pyaar karte ho clearly!",
        "🔥 Partner thoda zyada clingy nikla 😘",
    ]))

# ---------------- MARRIAGE SYSTEM ----------------

@app.on_message(filters.command("marry"))
async def marry_cmd(client, message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text("💍 Marriage proposals sirf groups me kaam karte hain 😘")

    if not message.reply_to_message:
        return await message.reply_text("💌 Kisi ko reply karke /marry likho 😘")

    from_uid = message.from_user.id
    to_uid = message.reply_to_message.from_user.id
    chat_id = message.chat.id

    if from_uid == to_uid:
        return await message.reply_text("😅 Khud se shaadi nahi hoti jaan")

    pending_marriage_requests[(chat_id, from_uid)] = to_uid

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💍 Accept", callback_data=f"marry_accept_{from_uid}"),
            InlineKeyboardButton("💔 Reject", callback_data=f"marry_reject_{from_uid}"),
        ]
    ])

    await message.reply_text(
        f"💍 {message.from_user.first_name} proposed you for marriage 😳❤️\nAccept karoge?",
        reply_markup=kb,
    )

@app.on_callback_query(filters.regex("^marry_accept_"))
async def marry_accept(client, cq: CallbackQuery):
    from_uid = int(cq.data.split("_")[-1])
    to_uid = cq.from_user.id
    chat_id = cq.message.chat.id

    key = (chat_id, from_uid)
    if pending_marriage_requests.get(key) != to_uid:
        return await cq.answer("❌ Request expired", show_alert=True)

    pending_marriage_requests.pop(key, None)

    if marriage_col:
        safe_db(
            marriage_col.update_one,
            {"chat_id": chat_id, "u1": from_uid, "u2": to_uid},
            {"$set": {"chat_id": chat_id, "u1": from_uid, "u2": to_uid, "since": datetime.utcnow()}},
            upsert=True,
        )

    update_user(from_uid, {"relationship_state": "married"})
    update_user(to_uid, {"relationship_state": "married"})

    await cq.message.edit_text("💍❤️ OMG! Tum dono officially married ho gaye 😭🔥")

@app.on_callback_query(filters.regex("^marry_reject_"))
async def marry_reject(client, cq: CallbackQuery):
    from_uid = int(cq.data.split("_")[-1])
    pending_marriage_requests.pop((cq.message.chat.id, from_uid), None)
    await cq.message.edit_text("💔 Proposal reject ho gaya 😢")

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

# ---------------- GROUP XP LEADERBOARD ----------------

@app.on_message(filters.command("leaderboard"))
async def leaderboard_cmd(client, message):
    chat_id = message.chat.id
    if not leaderboard_col:
        return await message.reply_text("Leaderboard unavailable 😅")

    top = list(leaderboard_col.find({"chat_id": chat_id}).sort("xp", -1).limit(10))
    if not top:
        return await message.reply_text("😅 No data yet")

    text = "🏆 **Group XP Leaderboard**\n\n"
    for i, u in enumerate(top, start=1):
        text += f"{i}. `{u['user_id']}` — {u['xp']} XP\n"
    await message.reply_text(text)

# ---------------- MAIN CHAT HANDLER ----------------

@app.on_message(filters.text & ~filters.command)
async def chat_handler(client, message):
    chat = message.chat
    user = message.from_user
    text = message.text or ""

    track_event("messages")

    ensure_user(user.id)

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
            except Exception:
                return await message.reply_text("😠 Aise words mat bolo!")
        else:
            return await message.reply_text("⚠️ Aise baatein mat bolo 😑")

    # Decide whether to reply
    should_reply = False
    if chat.type == ChatType.PRIVATE:
        should_reply = True
    else:
        try:
            me = await client.get_me()
            uname = me.username.lower() if me.username else ""
        except Exception:
            uname = ""

        if (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == me.id
        ):
            should_reply = True
        elif uname and f"@{uname}" in text.lower():
            should_reply = True
        elif text.lower().startswith(("hi", "hey", "sun", "oye", "baby", "babu", "jaan")):
            should_reply = True

    if not should_reply:
        return

    await client.send_chat_action(chat.id, ChatAction.TYPING)
    reply, _ = await get_ai_response(user.id, chat.id, text)
    if reply:
        await message.reply_text(reply)

# ---------------- RUN ----------------
print("🤖 Anshika AI Girlfriend Bot v9.0 Started Successfully...")
app.run()
