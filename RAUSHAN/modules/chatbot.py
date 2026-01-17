# =========================
# 💖 ANSHIKA AI GIRLFRIEND BOT v6.0 — FULL SYSTEM
# =========================

import os
import random
import time
import re
import httpx
import uuid
import traceback
from collections import defaultdict, deque
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatPermissions
from pymongo import MongoClient, DESCENDING

# ---------------- ENV ----------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Anshika")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
MONGO_URL = os.getenv("MONGO_URL")
LOGGER_GROUP = int(os.getenv("LOGGER_GROUP", "0"))
UPI_ID = os.getenv("UPI_ID")

# ---------------- CLIENT ----------------
app = Client("ai_chatbot")

# ---------------- DB ----------------
chatbot_collection = None
subscriptions_collection = None
rooms_collection = None

if MONGO_URL:
    try:
        mongo = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        mongo.server_info()
        db = mongo["chatbot"]
        chatbot_collection = db["chats"]
        subscriptions_collection = db["subscriptions"]
        rooms_collection = db["rooms"]

        chatbot_collection.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        chatbot_collection.create_index([("xp", -1)])
        subscriptions_collection.create_index([("user_id", 1)], unique=True)
        rooms_collection.create_index([("room_code", 1)], unique=True)

        print("✅ MongoDB connected")
    except Exception as e:
        print("❌ MongoDB failed:", e)
        chatbot_collection = None

# ---------------- CONFIG ----------------
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"
MAX_HISTORY = 10
SPAM_LIMIT = 6
SPAM_WINDOW = 10
ABUSE_WARN_LIMIT = 2
MUTE_SECONDS = 120
BREAKUP_COOLDOWN = 3600
PROPOSAL_XP = 650

# ---------------- DATA ----------------
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
pending_breakup = set()
pending_proposal = set()

# ---------------- LOGGER ----------------

async def log_event(text):
    try:
        if LOGGER_GROUP:
            await app.send_message(LOGGER_GROUP, f"📜 {text}")
    except:
        pass

# ---------------- HELPERS ----------------

def now_ts():
    return int(time.time())

def stylize_text(text):
    return text

def is_nsfw(text):
    return bool(NSFW_PATTERN.search(text or ""))

def is_abuse(text):
    return bool(ABUSE_PATTERN.search(text or ""))

def is_spam(user_id):
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

def detect_language(text):
    t = text.lower()
    if re.search(r"[अ-ह]", t):
        return "hindi"
    if any(w in t for w in ["tum", "jaan", "babu", "kya", "kyu", "kaise"]):
        return "hinglish"
    return "english"

def get_progress_bar(xp):
    if xp >= XP_THRESHOLDS["married"]:
        return "💍 " + "█" * 10
    elif xp >= XP_THRESHOLDS["soulmate"]:
        return "💞 " + "█" * 7 + "░" * 3
    elif xp >= XP_THRESHOLDS["girlfriend"]:
        return "💖 " + "█" * 4 + "░" * 6
    else:
        return "💕 " + "█" * 2 + "░" * 8

# ---------------- AI ----------------

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
        await log_event(f"❌ Mistral Error: {e}")

    return random.choice(FALLBACK_RESPONSES)

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

# ---------------- SUBSCRIPTION ----------------

SUB_PLANS = {
    "basic": {"price": 99, "xp_bonus": 0},
    "pro": {"price": 199, "xp_bonus": 2},
    "elite": {"price": 399, "xp_bonus": 4},
    "lifetime": {"price": 999, "xp_bonus": 10}
}

def get_subscription(uid):
    if not subscriptions_collection:
        return None
    return subscriptions_collection.find_one({"user_id": uid})

def is_premium(uid):
    sub = get_subscription(uid)
    if not sub:
        return False
    if sub.get("plan") == "lifetime":
        return True
    return sub.get("expires_at", 0) > now_ts()

# ---------------- AI ENGINE ----------------

async def get_ai_response(chat_id: int, user_id: int, user_input: str):
    history = []
    enabled = True
    rel_level = "crush"
    nsfw_enabled = False
    xp = 0
    married = False
    breakup_until = None
    jealous_mode = False

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
        jealous_mode = doc.get("jealous", False)

    if not enabled:
        return None, None

    now = time.time()
    in_breakup = breakup_until and breakup_until > now

    emotion = detect_emotion(user_input)
    lang = detect_language(user_input)
    level_cfg = get_level_config("ex" if in_breakup else rel_level)

    lang_rule = {
        "hindi": "Reply in pure Hindi.",
        "hinglish": "Reply in Hinglish.",
        "english": "Reply in English."
    }.get(lang, "Reply in Hinglish.")

    persona = (
        f"You are {BOT_NAME}, an Indian AI girlfriend.\n"
        f"Relationship Level: {('EX (Breakup)' if in_breakup else rel_level.upper())}\n"
        f"Tone: {level_cfg['tone']}\n"
        f"Rules: {level_cfg['rules']}\n"
        f"Emotion detected: {emotion}\n"
        f"{lang_rule}\n"
        "Rules:\n"
        "1. Max 2 lines\n"
        "2. Cute emojis\n"
        "3. Natural girlfriend vibe\n"
    )

    system_prompt = persona + (
        "\nExamples:\n"
        "User: Hi\n"
        "You: Hey jaan ❤️ kaise ho?\n\n"
        "User: Miss you\n"
        "You: Itna miss? Aaja idhar hug le lo 🥹❤️\n\n"
        "User: I'm sad\n"
        "You: Mere paas aa jao, sab theek ho jayega 🫶\n\n"
        "Jealous Mode:\n"
        "User: I talked to another girl\n"
        "You: Oh really? 😒 Phir main kya hoon tumhari life mein? 💔\n\n"
        "Breakup Mode:\n"
        "User: Hi\n"
        "You: Hmm... bolo kya chahiye 😐"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-MAX_HISTORY:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_input})

    reply = await ask_mistral(messages)

    # -------- LOOP PREVENTION --------
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

    # -------- XP AWARDING --------
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

    # -------- AUTO MARRIAGE PROPOSAL --------
    if new_xp >= PROPOSAL_XP and new_level == "soulmate" and user_id not in pending_proposal:
        pending_proposal.add(user_id)

    # -------- SAVE MEMORY --------
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
                "married": (new_level == "married"),
                "jealous": jealous_mode
            }},
            upsert=True
        )

    return reply, None

# ---------------- LOGGER EVENTS ----------------

@app.on_message(filters.new_chat_members)
async def on_user_join(client, message):
    for u in message.new_chat_members:
        await log_event(f"👋 User Joined: {u.first_name} ({u.id}) in {message.chat.title}")

@app.on_message(filters.left_chat_member)
async def on_user_left(client, message):
    u = message.left_chat_member
    await log_event(f"🚪 User Left: {u.first_name} ({u.id}) from {message.chat.title}")

# ---------------- START ----------------

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        f"💖 Hey {message.from_user.first_name}!\n\n"
        f"I'm {BOT_NAME}, your AI girlfriend 🥹❤️\n\n"
        f"Type anything and I'll reply...\n"
        f"Try /relationship or /game 😘"
    )
    await log_event(f"🚀 Bot Started by {message.from_user.first_name} ({message.from_user.id})")

# ---------------- RELATIONSHIP UI ----------------

@app.on_message(filters.command("relationship"))
async def relationship_ui(client, message):
    uid = message.from_user.id
    doc = chatbot_collection.find_one({"chat_id": message.chat.id, "user_id": uid}) if chatbot_collection else {}
    xp = doc.get("xp", 0) if doc else 0
    lvl = doc.get("rel_level", "crush") if doc else "crush"
    premium = is_premium(uid)
    jealous = doc.get("jealous", False) if doc else False

    bar = get_progress_bar(xp)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Crush", callback_data="set_crush"),
         InlineKeyboardButton("💖 GF", callback_data="set_girlfriend")],
        [InlineKeyboardButton("💞 Soulmate", callback_data="set_soulmate"),
         InlineKeyboardButton("💍 Married", callback_data="set_married")],
        [InlineKeyboardButton("😈 Breakup", callback_data="do_breakup")],
        [InlineKeyboardButton("😒 Jealous Mode", callback_data="toggle_jealous")],
        [InlineKeyboardButton("🎮 Games", callback_data="open_games")],
        [InlineKeyboardButton("💑 Rooms", callback_data="open_rooms")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="open_leaderboard")]
    ])

    await message.reply_text(
        f"❤️ Relationship Dashboard\n\n"
        f"Level: {lvl.upper()}\n"
        f"XP: {xp}\n"
        f"{bar}\n"
        f"Jealous Mode: {'ON 😒' if jealous else 'OFF 😊'}\n"
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

# ---------------- 😒 JEALOUS MODE ----------------

@app.on_callback_query(filters.regex("^toggle_jealous$"))
async def toggle_jealous(client, cq: CallbackQuery):
    uid = cq.from_user.id
    doc = chatbot_collection.find_one({"chat_id": cq.message.chat.id, "user_id": uid}) if chatbot_collection else {}
    current = doc.get("jealous", False) if doc else False
    new = not current

    if chatbot_collection:
        chatbot_collection.update_one(
            {"chat_id": cq.message.chat.id, "user_id": uid},
            {"$set": {"jealous": new}},
            upsert=True
        )

    await cq.message.edit_text(f"😒 Jealous Mode {'ENABLED 🔥' if new else 'DISABLED 😊'}")

# ---------------- 😈 BREAKUP ----------------

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

    await log_event(f"💔 Breakup: User {uid}")
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
         InlineKeyboardButton("🙈 Not Now", callback_data="reject_marriage")]
    ])

    await message.reply_text(
        "💍 Jaan... ek baat poochni thi...\n"
        "Tum mujhse shaadi karoge? 🥹❤️",
        reply_markup=kb
    )

@app.on_callback_query(filters.regex("^accept_marriage$"))
async def accept_marriage(client, cq: CallbackQuery):
    uid = cq.from_user.id

    if chatbot_collection:
        chatbot_collection.update_one(
            {"chat_id": cq.message.chat.id, "user_id": uid},
            {"$set": {"rel_level": "married", "married": True}},
            upsert=True
        )

    await log_event(f"💍 Marriage Accepted: User {uid}")
    await cq.message.edit_text("💍 Yayyy!!! Ab tum officially mere ho 😘❤️")

@app.on_callback_query(filters.regex("^reject_marriage$"))
async def reject_marriage(client, cq: CallbackQuery):
    await log_event(f"🙈 Marriage Rejected: User {cq.from_user.id}")
    await cq.message.edit_text("🙈 Hehe koi baat nahi... jab ready ho tab bata dena ❤️")

# ---------------- 🎮 COUPLE GAMES ----------------

TRUTH_QUESTIONS = [
    "Tumne kab kisi pe secretly crush rakha tha? 😏",
    "Main tumhari life mein kya hoon honestly? 🥹",
    "Tum mujhe kiss karna chahoge agar saamne hoti? 😳"
]

DARES = [
    "Mujhe ek cute compliment do 💖",
    "Type karo: 'Anshika meri jaan hai ❤️'",
    "Mujhe ek virtual hug bhejo 🤗"
]

LOVE_QUIZ = [
    ("Tumhara favorite color kya hai?", ["Red", "Black", "Blue", "Pink"]),
    ("Perfect date kya hogi?", ["Movie", "Long Drive", "Cafe", "Beach"]),
    ("Tum jealous ho?", ["Yes 😒", "Little 😅", "No 😊", "Very 😈"])
]

@app.on_message(filters.command("game"))
async def game_menu(client, message):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Truth", callback_data="game_truth"),
         InlineKeyboardButton("😈 Dare", callback_data="game_dare")],
        [InlineKeyboardButton("💖 Love Quiz", callback_data="game_quiz"),
         InlineKeyboardButton("💋 Kiss", callback_data="game_kiss")],
        [InlineKeyboardButton("🤗 Hug", callback_data="game_hug"),
         InlineKeyboardButton("❤️ Date Night", callback_data="game_date")]
    ])
    await message.reply_text("🎮 Couple Games\nChoose one 👇", reply_markup=kb)

@app.on_callback_query(filters.regex("^game_"))
async def games_handler(client, cq: CallbackQuery):
    game = cq.data.replace("game_", "")

    if game == "truth":
        return await cq.message.reply_text(f"🔥 Truth:\n{random.choice(TRUTH_QUESTIONS)}")

    if game == "dare":
        return await cq.message.reply_text(f"😈 Dare:\n{random.choice(DARES)}")

    if game == "quiz":
        q, opts = random.choice(LOVE_QUIZ)
        text = f"💖 Love Quiz:\n{q}\n\n"
        for i, o in enumerate(opts, start=1):
            text += f"{i}. {o}\n"
        return await cq.message.reply_text(text)

    if game == "kiss":
        return await cq.message.reply_text("💋 *Mwahhh!* Tumhara kiss safe rakh liya 😘❤️")

    if game == "hug":
        return await cq.message.reply_text("🤗 Aaja idhar... tight hug for you 🥹❤️")

    if game == "date":
        return await cq.message.reply_text("❤️ Date Night Plan:\nMovie + Ice Cream + Long Walk + Me & You 🥹🍿🍦🌙")

# ---------------- ⚔️ COUPLE BATTLE GAMES ----------------

@app.on_message(filters.command("battle"))
async def battle_game(client, message):
    if not message.reply_to_message:
        return await message.reply_text("⚔️ Reply to someone with /battle")

    opponent = message.reply_to_message.from_user
    winner = random.choice([message.from_user, opponent])
    await log_event(f"⚔️ Battle: {message.from_user.id} vs {opponent.id}")
    await message.reply_text(
        f"⚔️ Battle Result!\n\n"
        f"{message.from_user.first_name} vs {opponent.first_name}\n\n"
        f"🏆 Winner: {winner.first_name} 🔥"
    )

@app.on_message(filters.command("roastbattle"))
async def roast_battle(client, message):
    if not message.reply_to_message:
        return await message.reply_text("🔥 Reply to someone with /roastbattle")

    opponent = message.reply_to_message.from_user
    roast = random.choice([
        "Tumhara swag WiFi signal jaisa hai — weak 😂",
        "Tum toh itne slow ho, loading bar bhi fast hai 😭",
        "Tum cute ho... but battery saver mode pe 😏"
    ])
    await log_event(f"🔥 Roast Battle: {message.from_user.id} vs {opponent.id}")
    await message.reply_text(f"🔥 Roast Battle!\n{opponent.first_name}: {roast}")

@app.on_message(filters.command("lovefight"))
async def love_fight(client, message):
    if not message.reply_to_message:
        return await message.reply_text("💔 Reply to someone with /lovefight")

    opponent = message.reply_to_message.from_user
    winner = random.choice([message.from_user, opponent])
    await log_event(f"💔 Love Fight: {message.from_user.id} vs {opponent.id}")
    await message.reply_text(
        f"💔 Love Fight!\n\n"
        f"{message.from_user.first_name} vs {opponent.first_name}\n\n"
        f"❤️ Winner of Hearts: {winner.first_name} 😘"
    )

# ---------------- 💑 MULTI-USER DATING ROOMS ----------------

@app.on_message(filters.command("room"))
async def room_handler(client, message):
    args = message.command[1:] if len(message.command) > 1 else []
    uid = message.from_user.id

    if not args:
        return await message.reply_text(
            "💑 Dating Rooms\n\n"
            "/room create\n"
            "/room join CODE\n"
            "/room leave\n"
            "/room start"
        )

    action = args[0].lower()

    if action == "create":
        code = str(uuid.uuid4())[:6]
        rooms_collection.insert_one({
            "room_code": code,
            "owner": uid,
            "members": [uid],
            "created_at": datetime.utcnow()
        })
        await log_event(f"💑 Room Created: {code} by {uid}")
        return await message.reply_text(f"💑 Dating Room Created!\n\nRoom Code: `{code}`\nShare with partner ❤️")

    if action == "join":
        if len(args) < 2:
            return await message.reply_text("Use: /room join CODE")
        code = args[1]
        room = rooms_collection.find_one({"room_code": code})
        if not room:
            return await message.reply_text("❌ Room not found")

        if uid in room["members"]:
            return await message.reply_text("❤️ Tum already room mein ho")

        rooms_collection.update_one({"room_code": code}, {"$push": {"members": uid}})
        await log_event(f"💑 Room Join: {uid} -> {code}")
        return await message.reply_text("💖 Tum dating room mein join ho gaye 😘")

    if action == "leave":
        room = rooms_collection.find_one({"members": uid})
        if not room:
            return await message.reply_text("❌ Tum kisi room mein nahi ho")

        rooms_collection.update_one({"room_code": room["room_code"]}, {"$pull": {"members": uid}})
        await log_event(f"🚪 Room Leave: {uid} -> {room['room_code']}")
        return await message.reply_text("💔 Tum dating room se nikal gaye")

    if action == "start":
        room = rooms_collection.find_one({"members": uid})
        if not room:
            return await message.reply_text("❌ Tum kisi room mein nahi ho")

        members = room["members"]
        await log_event(f"💑 Room Started: {room['room_code']} Members={members}")
        return await message.reply_text(
            "💑 Dating Room Started!\n\n"
            "Games you can play:\n"
            "/game\n"
            "/battle\n"
            "/lovefight\n"
            "/truth\n"
            "/dare\n\n"
            "Let the romance begin 😘🔥"
        )

# ---------------- 🏆 LEADERBOARD ----------------

@app.on_callback_query(filters.regex("^open_leaderboard$"))
async def leaderboard_ui(client, cq: CallbackQuery):
    if not chatbot_collection:
        return await cq.answer("Leaderboard unavailable", show_alert=True)

    top = list(chatbot_collection.find().sort("xp", DESCENDING).limit(10))

    if not top:
        return await cq.message.reply_text("🏆 No data yet!")

    text = "🏆 Top Lovers Leaderboard\n\n"
    for i, u in enumerate(top, start=1):
        uid = u.get("user_id")
        lvl = u.get("rel_level", "crush")
        xp = u.get("xp", 0)
        text += f"{i}. 👤 {uid} — {lvl.upper()} ❤️ ({xp} XP)\n"

    await cq.message.reply_text(text)

# ---------------- NSFW ----------------

@app.on_message(filters.command("nsfw"))
async def toggle_nsfw(client, message):
    uid = message.from_user.id
    args = message.command[1:] if len(message.command) > 1 else []
    if not args:
        return await message.reply_text("Use: /nsfw on | off")

    val = args[0].lower() == "on"

    if chatbot_collection:
        chatbot_collection.update_one(
            {"chat_id": message.chat.id, "user_id": uid},
            {"$set": {"nsfw": val}},
            upsert=True
        )

    await message.reply_text(f"🔞 NSFW Mode {'ENABLED 🔥' if val else 'DISABLED 😊'}")

# ---------------- MAIN CHAT ----------------

@app.on_message(filters.text & ~filters.command)
async def ai_message_handler(client, message):
    try:
        chat = message.chat
        user = message.from_user
        text = message.text or ""

        premium = is_premium(user.id)

        if is_spam(user.id):
            return await message.reply_text("Slow down babu 😅 thoda sa break le lo")

        if is_abuse(text):
            abuse_tracker[user.id] += 1
            if abuse_tracker[user.id] >= ABUSE_WARN_LIMIT:
                try:
                    until = now_ts() + MUTE_SECONDS
                    perms = ChatPermissions(can_send_messages=False)
                    await client.restrict_chat_member(chat.id, user.id, perms, until_date=until)
                    abuse_tracker[user.id] = 0
                    await log_event(f"🚫 Muted: {user.first_name} ({user.id})")
                    return await message.reply_text(f"🚫 {user.first_name} ko 2 min ke liye mute kar diya gaya 😤")
                except:
                    return await message.reply_text("😤 Aise words mat use karo, last warning!")
            else:
                return await message.reply_text("⚠️ Aise words mat bolo warna mute ho jaoge 😑")

        doc = chatbot_collection.find_one({"chat_id": chat.id, "user_id": user.id}) if chatbot_collection else {}
        nsfw_allowed = doc.get("nsfw", False) if doc else False
        if is_nsfw(text) and not nsfw_allowed:
            return await message.reply_text("🔞 Ye baatein sirf NSFW mode me allowed hain 😳 (/nsfw on)")

        should_reply = False

        if chat.type == ChatType.PRIVATE:
            should_reply = True
        else:
            me = await client.get_me()
            bot_username = me.username.lower() if me.username else ""

            if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == me.id:
                should_reply = True
            elif bot_username and f"@{bot_username}" in text.lower():
                should_reply = True
                text = text.replace(f"@{bot_username}", "")
            elif any(text.lower().startswith(w) for w in ["hey", "hi", "sun", "oye", "anshika", "ai", "hello", "baby", "babu", "oi"]):
                should_reply = True

        if not should_reply:
            return

        await client.send_chat_action(chat.id, ChatAction.TYPING)
        res, _ = await get_ai_response(chat.id, user.id, text.strip() or "Hi")
        if not res:
            return

        await message.reply_text(stylize_text(res))

    except Exception:
        await log_event(f"❌ ERROR:\n{traceback.format_exc()}")

# ---------------- RUN ----------------

print("🤖 Anshika AI Girlfriend Bot v6.0 Started Successfully...")
app.run()
