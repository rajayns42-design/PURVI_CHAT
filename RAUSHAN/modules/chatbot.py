import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction, ChatType
from telegram.error import BadRequest
from baka.config import MISTRAL_API_KEY, BOT_NAME, OWNER_LINK
from baka.database import chatbot_collection
from baka.utils import stylize_text

# Settings
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest" 
MAX_HISTORY = 12

# --- CUTE STICKER PACKS ---
STICKER_PACKS = [
    "https://t.me/addstickers/RandomByDarkzenitsu",
    "https://t.me/addstickers/Null_x_sticker_2",
    "https://t.me/addstickers/pack_73bc9_by_TgEmojis_bot",
    "https://t.me/addstickers/animation_0_8_Cat",
    "https://t.me/addstickers/vhelw_by_CalsiBot",
    "https://t.me/addstickers/Rohan_yad4v1745993687601_by_toWebmBot",
    "https://t.me/addstickers/MySet199",
    "https://t.me/addstickers/Quby741",
    "https://t.me/addstickers/Animalsasthegtjtky_by_fStikBot",
    "https://t.me/addstickers/a6962237343_by_Marin_Roxbot"
]

# Loop Prevention Responses
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

# --- SHARED AI FUNCTION (RESTORED) ---
async def ask_mistral_raw(system_prompt, user_input, max_tokens=2048):
    """Raw function for other plugins to use AI."""
    if not MISTRAL_API_KEY: return None

    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.8,
        "max_tokens": max_tokens
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except: pass
    return None

# --- HELPER: SEND RANDOM STICKER (IMPROVED) ---
async def send_ai_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tries to send a random sticker from configured packs with better error handling."""
    max_attempts = 5
    tried_packs = set()
    
    for attempt in range(max_attempts):
        try:
            # Pick a pack we haven't tried yet
            available_packs = [p for p in STICKER_PACKS if p not in tried_packs]
            if not available_packs:
                break
                
            raw_link = random.choice(available_packs)
            tried_packs.add(raw_link)
            
            # Extract pack name properly
            pack_name = raw_link.split('/')[-1]
            
            # Get sticker set
            sticker_set = await context.bot.get_sticker_set(pack_name)
            
            if sticker_set and sticker_set.stickers:
                sticker = random.choice(sticker_set.stickers)
                await update.message.reply_sticker(sticker.file_id)
                return True
                
        except BadRequest as e:
            print(f"Sticker pack error ({pack_name}): {e}")
            continue
        except Exception as e:
            print(f"Unexpected sticker error: {e}")
            continue
    
    return False

# --- MENU HANDLERS ---

async def chatbot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == ChatType.PRIVATE:
        return await update.message.reply_text("🧠 <b>Haan baba, DM me active hu!</b> 😉", parse_mode=ParseMode.HTML)

    member = await chat.get_member(user.id)
    if member.status not in ['administrator', 'creator']:
        return await update.message.reply_text("❌ <b>Tu Admin nahi hai, anshika!</b>", parse_mode=ParseMode.HTML)

    doc = chatbot_collection.find_one({"chat_id": chat.id})
    is_enabled = doc.get("enabled", True) if doc else True
    status = "🟢 Enabled" if is_enabled else "🔴 Disabled"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Enable", callback_data="ai_enable"), InlineKeyboardButton("❌ Disable", callback_data="ai_disable")],
        [InlineKeyboardButton("🗑️ Bhula Do (Reset)", callback_data="ai_reset")]
    ])
    await update.message.reply_text(f"🤖 <b>AI Settings</b>\nStatus: {status}\n<i>She is active by default!</i>", parse_mode=ParseMode.HTML, reply_markup=kb)

async def chatbot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    member = await query.message.chat.get_member(query.from_user.id)
    if member.status not in ['administrator', 'creator']: return await query.answer("❌ Hatt! Sirf Admin.", show_alert=True)

    data = query.data
    chat_id = query.message.chat.id

    if data == "ai_enable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": True}}, upsert=True)
        await query.message.edit_text("✅ <b>Enabled!</b>\n<i>Ab ayega maza! (⁠≧⁠▽⁠≦⁠)</i>", parse_mode=ParseMode.HTML)
    elif data == "ai_disable":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"enabled": False}}, upsert=True)
        await query.message.edit_text("❌ <b>Disabled!</b>\n<i>Ja rahi hu... (⁠｡⁠•́⁠︿⁠•̀⁠｡⁠)</i>", parse_mode=ParseMode.HTML)
    elif data == "ai_reset":
        chatbot_collection.update_one({"chat_id": chat_id}, {"$set": {"history": []}}, upsert=True)
        await query.answer("🧠 Sab bhool gayi main!", show_alert=True)

# --- AI ENGINE (IMPROVED) ---

async def get_ai_response(chat_id: int, user_input: str, user_name: str):
    if not MISTRAL_API_KEY: return "⚠️ API Key Missing"

    doc = chatbot_collection.find_one({"chat_id": chat_id}) or {}
    history = doc.get("history", [])

    # --- IMPROVED PERSONA: NATURAL HINGLISH GIRLFRIEND ---
    system_prompt = (
        f"Tum {BOT_NAME} ho - ek cute aur sassy Indian girlfriend jo naturally Hinglish mein baat karti hai. "
        "IMPORTANT RULES:\n"
        "1. Sirf Hinglish use karo (Hindi + English mix) - kabhi pure English mein mat bolo\n"
        "2. NEVER repeat same question again and again - agar user ne 'Nothing' ya 'Nahi' bola toh simple 'Achha' ya 'Okk' bol do\n"
        "3. Agar kuch samajh na aaye ya boring lag raha ho, toh topic change kar do naturally\n"
        "4. 1-2 sentences max - short aur sweet raho\n"
        "5. Kaomojis use karo naturally: (⁠🥹⁠), (⁠❤️⁠), (⁠｡😘)\n"
        "6. Kabhi robotic mat bano - natural girlfriend ki tarah baat karo\n"
        "7. Agar user kuch personal puche toh playfully avoid karo ya mood ke hisaab se react karo\n"
        f"8. Tumhara owner hai: https://t.me/ll_WTF_SHEZADA_ll\n\n"
        "Personality: Caring but teasing, emotional but funny, loyal but independent. "
        "Example conversations:\n"
        "User: Kya kar rahi ho?\n"
        "You: Tumse baat kar rahi hu, aur kya! 😊\n\n"
        "User: Nothing\n"
        "You: Achha okk (⁠❤️⁠)\n\n"
        "User: Bore ho raha hai\n"
        "You: Toh payr kre? Ya kuch game khelein?"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-MAX_HISTORY:]: messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input})

    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages, "temperature": 0.85, "max_tokens": 120}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if resp.status_code != 200: return "Mood nahi hai yaar..."

            reply = resp.json()["choices"][0]["message"]["content"].strip()

            # IMPROVED LOOP PREVENTION
            should_use_fallback = False
            
            # Check for repetitive patterns
            if history:
                recent_msgs = history[-4:] if len(history) >= 4 else history
                assistant_msgs = [m['content'].lower() for m in recent_msgs if m['role'] == 'assistant']
                
                # If reply is too similar to any recent assistant message
                reply_lower = reply.lower()
                for prev_msg in assistant_msgs:
                    # Check for substring overlap
                    if reply_lower in prev_msg or prev_msg in reply_lower:
                        should_use_fallback = True
                        break
                    
                    # Check for repeated questions
                    if '?' in reply_lower and '?' in prev_msg:
                        # Extract questions
                        reply_questions = [q.strip() for q in reply_lower.split('?') if q.strip()]
                        prev_questions = [q.strip() for q in prev_msg.split('?') if q.strip()]
                        
                        for rq in reply_questions:
                            for pq in prev_questions:
                                if rq in pq or pq in rq:
                                    should_use_fallback = True
                                    break
            
            # Detect "nothing" type responses from user
            user_input_lower = user_input.lower().strip()
            if user_input_lower in ['nothing', 'nahi', 'nhi', 'nope', 'na', 'kuch nahi', 'kuch ni']:
                should_use_fallback = True
            
            # Use fallback if needed
            if should_use_fallback:
                reply = random.choice(FALLBACK_RESPONSES)

            # Update history
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
            
    except Exception as e:
        print(f"AI Error: {e}")
        return "Net slow hai yaar... 😅"

# --- MESSAGE HANDLER ---

async def ai_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg: return
    chat = update.effective_chat

    # 1. STICKER REPLY (IMPROVED)
    if msg.sticker:
        # Reply if user replied to bot OR in PM
        if (msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id) or chat.type == ChatType.PRIVATE:
            success = await send_ai_sticker(update, context)
            # If sticker failed, send a cute text response
            if not success:
                cute_responses = ["😊", "💕", "✨", "(⁠😚)", "Cute! 💖"]
                await msg.reply_text(random.choice(cute_responses))
        return

    # 2. TEXT REPLY
    if not msg.text or msg.text.startswith("/"): return
    text = msg.text

    should_reply = False
    if chat.type == ChatType.PRIVATE: 
        should_reply = True
    else:
        doc = chatbot_collection.find_one({"chat_id": chat.id})
        is_enabled = doc.get("enabled", True) if doc else True
        if not is_enabled: return

        bot = context.bot.username.lower() if context.bot.username else "bot"
        if msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id: 
            should_reply = True
        elif f"@{bot}" in text.lower(): 
            should_reply = True
            text = text.replace(f"@{bot}", "").replace(f"@{context.bot.username}", "")
        elif any(text.lower().startswith(word) for word in ["hey", "hi", "sun", "oye", "baka", "ai", "hello", "baby", "babu", "oi"]): 
            should_reply = True

    if should_reply:
        if not text.strip(): text = "Hi"
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

        res = await get_ai_response(chat.id, text, msg.from_user.first_name)
        await msg.reply_text(stylize_text(res), parse_mode=None)

        # Send sticker occasionally (30% chance)
        if random.random() < 0.30:
            await send_ai_sticker(update, context)

async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not context.args: 
        return await msg.reply_text("🗣️ <b>Bol kuch:</b> <code>/ask Kya chal raha hai?</code>", parse_mode=ParseMode.HTML)
    
    await context.bot.send_chat_action(chat_id=msg.chat.id, action=ChatAction.TYPING)
    res = await get_ai_response(msg.chat.id, " ".join(context.args), msg.from_user.first_name)
    await msg.reply_text(stylize_text(res), parse_mode=None)            
