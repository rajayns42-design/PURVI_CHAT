from pyrogram import filters
from pyrogram.enums import ChatType
from bot import app

from database.users import get_user, create_user, update_user
from core.ai_engine import ai_reply
from core.flirting_engine import girlfriend_prompt
from core.emotion_engine import detect_emotion
from core.nsfw_filter import is_nsfw
from core.abuse_engine import is_abuse
from core.xp_engine import xp_for_message, level_from_xp
from core.relationship_engine import get_level_name
from core.selfie_engine import get_selfie
from core.analytics_engine import log

@app.on_message(filters.private & filters.text)
async def private_handler(client, message):
    uid = message.from_user.id
    name = message.from_user.first_name
    text = message.text.strip()

    user = get_user(uid)
    if not user:
        create_user(uid, name)
        user = get_user(uid)

    if user.get("blocked"):
        return

    # Abuse control
    if is_abuse(text):
        warns = user.get("nsfw_warns", 0) + 1
        update_user(uid, {"nsfw_warns": warns})
        if warns >= 3:
            update_user(uid, {"blocked": True})
            await message.reply("🚫 Tum bahut badtameezi kar rahe ho... main tumse baat nahi kar sakti 😔")
            return
        await message.reply("😠 Aise baat mat karo... warna main gussa ho jaungi!")
        return

    # NSFW filter
    if is_nsfw(text):
        await message.reply("🙈 Aise baatein nahi... thoda classy raho na baby 😏")
        return

    # XP system
    gained = xp_for_message(text)
    new_xp = user["xp"] + gained
    new_level = level_from_xp(new_xp)
    update_user(uid, {"xp": new_xp, "level": new_level})

    # Emotion detection
    emotion = detect_emotion(text)
    update_user(uid, {"emotion": emotion})

    # Commands
    if text.lower() == "/selfie":
        await message.reply_photo(get_selfie(), caption="📸 Sirf tumhare liye 😘")
        return

    if text.lower() == "/status":
        await message.reply(
            f"""
💖 Relationship Status
👩 Girlfriend: {user['girlfriend']}
❤️ Mode: {user['mode']}
🔥 Level: {get_level_name(new_level)}
⭐ XP: {new_xp}
💎 Premium: {user.get('premium')}
"""
        )
        return

    # AI girlfriend reply
    system_prompt = girlfriend_prompt(
        user["girlfriend"],
        user["mode"],
        emotion,
        get_level_name(new_level)
    )

    reply = await ai_reply(system_prompt, text)
    await message.reply(reply)

    log("message", {"uid": uid, "text": text})
