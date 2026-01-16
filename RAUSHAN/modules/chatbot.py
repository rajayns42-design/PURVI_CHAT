   # =========================
# 💖 ANSHIKA AI GIRLFRIEND BOT v5.0 (ULTIMATE)
# =========================

import os
import random
import time
import re
import httpx
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
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
UPI_ID = os.getenv("UPI_ID")

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
        print("❌ MongoDB connection failed:", e)
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

JEALOUSY_TRIGGERS = ["she", "her", "another girl", "other girl", "ex", "crush", "gf", "wife"]

# ---------------- MEMORY ----------------
spam_tracker = defaultdict(lambda: deque(maxlen=SPAM_LIMIT))
abuse_tracker = defaultdict(int)
pending_nsfw = set()
pending_marriage = set()
pending_breakup = set()
pending_proposal = set()

# ---------------- HELPERS ----------------

def stylize_text(text):
    return text

def is_nsfw(text: str):
    return bool(NSFW_PATTERN.search(text or ""))

def is_abuse(text: str):
    return bool(ABUSE_PATTERN.search(text or ""))

def is_spam(user_id: int, premium=False):
    if premium:
        return False
    now = time.time()
    q = spam_tracker[user_id]
    q.append(now)
    return len(q) >= SPAM_LIMIT and (now - q[0]) < SPAM_WINDOW

def detect_emotion(text: str):
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

def detect_jealousy(text: str):
    t = (text or "").lower()
    return any(w in t for w in JEALOUSY_TRIGGERS)

def get_progress_bar(xp):
    if xp >= XP_THRESHOLDS["married"]:
        return "💍 " + "█" * 10
    elif xp >= XP_THRESHOLDS["soulmate"]:
        return "💞 " + "█" * 7 + "░" * 3
    elif xp >= XP_THRESHOLDS["girlfriend"]:
        return "💖 " + "█" * 4 + "░" * 6
    else:
        return "💕 " + "█" * 2 + "░" * 8

def now_ts():
    return int(time.time())

# ---------------- AUTO FLIRT MODE ----------------

def auto_flirt_mode(emotion, xp, nsfw, breakup=False, jealous=False):
    if breakup:
        return "cold"
    if jealous:
        return "jealous"
    if nsfw and xp >= 200:
        return "hot"
    if emotion == "sad":
        return "soft"
    if emotion == "romantic":
        return "romantic"
    if xp >= XP_THRESHOLDS["married"]:
        return "husband_wife"
    if xp >= XP_THRESHOLDS["soulmate"]:
        return "possessive"
    if emotion == "flirty":
        return "teasing"
    return "sweet"

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

# ---------------- SUBSCRIPTION ENGINE ----------------

SUB_PLANS = {
    "basic": {"price": 99, "xp_bonus": 0, "features": ["Romantic Mode"]},
    "pro": {"price": 199, "xp_bonus": 2, "features": ["NSFW", "Jealousy", "Voice Soon"]},
    "elite": {"price": 399, "xp_bonus": 4, "features": ["Marriage", "Selfies", "Possessive Mode"]},
    "lifetime": {"price": 999, "xp_bonus": 10, "features": ["All Features Forever"]}
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

def has_feature(uid, feature):
    sub = get_subscription(uid)
    if not sub:
        return False
    return feature in SUB_PLANS.get(sub.get("plan"), {}).get("features", [])

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

# ---------------- AI ENGINE ----------------

async def get_ai_response(chat_id: int, user_id: int, user_input: str):
    history = []
    enabled = True
    rel_level = "crush"
    nsfw_enabled = False
    xp = 0
    married = False
    breakup_until = None
    jealousy_enabled = False

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
        jealousy_enabled = doc.get("jealousy", False)

    if not enabled:
        return None, None

    now = time.time()
    in_breakup = breakup_until and breakup_until > now

    emotion = detect_emotion(user_input)
    jealous = detect_jealousy(user_input) and jealousy_enabled and has_feature(user_id, "Jealousy")
    flirt_mode = auto_flirt_mode(emotion, xp, nsfw_enabled, breakup=in_breakup, jealous=jealous)
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
    )

    if jealous:
        persona += "Jealous Mode: Possessive, emotional, teasing, slightly insecure but loving.\n"

    if in_breakup:
        persona += "Mode: EX — cold replies, short answers, emotional distance.\n"

    persona += (
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
        "Jealous Mode Example:\n"
        "User: I was talking to another girl\n"
        "You: Oh really? 😒 Accha hai, phir main kyun hoon tumhari life me? 😤❤️\n\n"
        "Breakup Mode Example:\n"
        "User: Hi\n"
        "You: Hmm... bolo kya hai 😐"
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
            if rl == pm or rl in pm or pm in rl:
                should_fallback = True
                break

    if user_input.lower().strip() in ["nothing", "nahi", "nhi", "nope", "na", "kuch nahi", "kuch ni"]:
        should_fallback = True

    if should_fallback:
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

    # -------- AUTO MARRIAGE PROPOSAL 💍 --------
    if new_xp >= PROPOSAL_XP and new_level == "soulmate" and not married and user_id not in pending_proposal:
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
                "married": (new_level == "married")
            }},
            upsert=True
        )

    return reply, None

# ---------------- RELATIONSHIP UI ----------------

@app.on_message(filters.command("relationship"))
async def relationship_ui(client, message):
    uid = message.from_user.id
    doc = chatbot_collection.find_one({"chat_id": message.chat.id, "user_id": uid}) if chatbot_collection else {}
    xp = doc.get("xp", 0) if doc else 0
    lvl = doc.get("rel_level", "crush") if doc else "crush"
    premium = is_premium(uid)
    jealous = doc.get("jealousy", False) if doc else False

    bar = get_progress_bar(xp)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Crush", callback_data="set_crush"),
         InlineKeyboardButton("💖 GF", callback_data="set_girlfriend")],
        [InlineKeyboardButton("💞 Soulmate", callback_data="set_soulmate"),
         InlineKeyboardButton("💍 Married", callback_data="set_married")],
        [InlineKeyboardButton("😈 Breakup", callback_data="do_breakup"),
         InlineKeyboardButton(f"{'🔥 Jealous ON' if jealous else '😈 Jealous OFF'}", callback_data="toggle_jealousy")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="open_leaderboard"),
         InlineKeyboardButton("💎 Subscription", callback_data="open_subscription")]
    ])

    await message.reply_text(
        f"❤️ Relationship Dashboard\n\n"
        f"Level: {lvl.upper()}\n"
        f"XP: {xp}\n"
        f"{bar}\n"
        f"Jealousy Mode: {'ON 😈' if jealous else 'OFF 🙂'}\n"
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

# ---------------- 😈 JEALOUSY TOGGLE ----------------

@app.on_callback_query(filters.regex("^toggle_jealousy$"))
async def toggle_jealousy(client, cq: CallbackQuery):
    uid = cq.from_user.id
    if not has_feature(uid, "Jealousy"):
        return await cq.answer("💎 Jealousy Mode sirf Pro users ke liye hai 😏", show_alert=True)

    doc = chatbot_collection.find_one({"chat_id": cq.message.chat.id, "user_id": uid}) or {}
    state = not doc.get("jealousy", False)

    chatbot_collection.update_one(
        {"chat_id": cq.message.chat.id, "user_id": uid},
        {"$set": {"jealousy": state}},
        upsert=True
    )

    await cq.answer(f"{'🔥 Jealousy ON 😈' if state else '🙂 Jealousy OFF'}", show_alert=True)
    await cq.message.delete()

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
                "breakup_until": until,
                "jealousy": False
            }},
            upsert=True
        )

    await message.reply_text("💔 Fine... jao. Ab thoda distance hi better hai 😐")

# ---------------- 💍 AUTO MARRIAGE PROPOSAL ----------------

@app.on_message(filters.text & ~filters.command)
async def auto_proposal_checker(client, message):
    uid = message.from_user.id
    if uid not in pending_proposal:
        return

    pending_proposal.remove(uid)

    if not has_feature(uid, "Marriage"):
        return

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

    await cq.message.edit_text("💍 Yayyy!!! Ab tum officially mere ho 😘❤️")

@app.on_callback_query(filters.regex("^reject_marriage$"))
async def reject_marriage(client, cq: CallbackQuery):
    await cq.message.edit_text("🙈 Hehe koi baat nahi... jab ready ho tab bata dena ❤️")

# ---------------- 🏆 LEADERBOARD SYSTEM ----------------

@app.on_callback_query(filters.regex("^open_leaderboard$"))
async def leaderboard_ui(client, cq: CallbackQuery):
    if not chatbot_collection:
        return await cq.answer("Leaderboard unavailable", show_alert=True)

    top = list(chatbot_collection.find().sort("xp", DESCENDING).limit(10))
    if not top:
        return await cq.message.reply_text("🏆 No lovers yet!")

    text = "🏆 Top Lovers 💖\n\n"
    for i, u in enumerate(top, start=1):
        uid = u.get("user_id")
        lvl = u.get("rel_level", "crush")
        xp = u.get("xp", 0)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💘"
        text += f"{medal} {i}. {uid} — {lvl.upper()} ({xp} XP)\n"

    await cq.message.reply_text(text)

# ---------------- 💳 SaaS SUBSCRIPTION SYSTEM ----------------

@app.on_callback_query(filters.regex("^open_subscription$"))
async def open_subscription(client, cq: CallbackQuery):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥉 Basic ₹99/mo", callback_data="buy_basic"),
         InlineKeyboardButton("🥈 Pro ₹199/mo", callback_data="buy_pro")],
        [InlineKeyboardButton("🥇 Elite ₹399/mo", callback_data="buy_elite"),
         InlineKeyboardButton("👑 Lifetime ₹999", callback_data="buy_lifetime")]
    ])

    await cq.message.reply_text(
        "💎 Subscription Plans\n\n"
        "🥉 Basic — Romantic Mode\n"
        "🥈 Pro — NSFW + Jealousy\n"
        "🥇 Elite — Marriage + Selfies\n"
        "👑 Lifetime — All Forever\n\n"
        "Choose your plan 👇",
        reply_markup=kb
    )

@app.on_callback_query(filters.regex("^buy_"))
async def buy_plan(client, cq: CallbackQuery):
    plan = cq.data.replace("buy_", "")
    if plan not in SUB_PLANS:
        return await cq.answer("Invalid plan", show_alert=True)

    uid = cq.from_user.id
    order_id = str(uuid.uuid4())[:8]
    price = SUB_PLANS[plan]["price"]

    if subscriptions_collection:
        subscriptions_collection.insert_one({
            "order_id": order_id,
            "user_id": uid,
            "plan": plan,
            "status": "pending",
            "created_at": datetime.utcnow()
        })

    text = (
        f"💎 {plan.upper()} Subscription\n\n"
        f"Price: ₹{price}\n\n"
        f"📱 Pay using UPI:\n`{UPI_ID}`\n\n"
        f"💳 Or Stripe Checkout (Auto verify soon)\n\n"
        f"After UPI payment send screenshot + Order ID:\n`{order_id}`"
    )

    await cq.message.reply_text(text)

@app.on_message(filters.command("confirm_payment"))
async def confirm_payment(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Sirf owner payment verify kar sakta hai.")

    args = message.command[1:] if len(message.command) > 1 else []
    if not args:
        return await message.reply_text("Use: /confirm_payment ORDER_ID")

    order_id = args[0]
    order = subscriptions_collection.find_one({"order_id": order_id}) if subscriptions_collection else None
    if not order:
        return await message.reply_text("❌ Order not found")

    uid = order["user_id"]
    plan = order["plan"]

    expires = 9999999999 if plan == "lifetime" else now_ts() + 30 * 24 * 3600

    subscriptions_collection.update_one(
        {"order_id": order_id},
        {"$set": {"status": "active", "expires_at": expires}}
    )

    await message.reply_text("✅ Subscription activated 💎")

# ---------------- MAIN CHAT HANDLER ----------------

@app.on_message(filters.text & ~filters.command)
async def ai_message_handler(client, message):
    chat = message.chat
    user = message.from_user
    text = message.text or ""

    premium = is_premium(user.id)

    # -------- SPAM CONTROL --------
    if is_spam(user.id, premium=premium):
        return await message.reply_text("Slow down babu 😅 thoda sa break le lo")

    # -------- ABUSE DETECTOR --------
    if is_abuse(text):
        abuse_tracker[user.id] += 1
        if abuse_tracker[user.id] >= ABUSE_WARN_LIMIT:
            try:
                until = now_ts() + MUTE_SECONDS
                perms = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat.id, user.id, perms, until_date=until)
                abuse_tracker[user.id] = 0
                return await message.reply_text(f"🚫 {user.first_name} ko 2 min ke liye mute kar diya gaya 😤")
            except:
                return await message.reply_text("😤 Aise words mat use karo, last warning!")
        else:
            return await message.reply_text("⚠️ Aise words mat bolo warna mute ho jaoge 😑")

    # -------- NSFW FILTER --------
    doc = chatbot_collection.find_one({"chat_id": chat.id, "user_id": user.id}) if chatbot_collection else {}
    nsfw_allowed = doc.get("nsfw", False) if doc else False
    if is_nsfw(text) and not nsfw_allowed:
        return await message.reply_text("🔞 Ye baatein sirf NSFW mode me allowed hain 😳 (/nsfw on)")

    should_reply = False

    if chat.type == ChatType.PRIVATE:
        should_reply = True
    else:
        is_enabled = doc.get("enabled", True) if doc else True
        if not is_enabled:
            return

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

    if random.random() < 0.30:
        await send_ai_sticker(client, message)

# ---------------- RUN ----------------
print("🤖 Anshika AI Girlfriend Bot v5.0 Started Successfully...")
app.run()
