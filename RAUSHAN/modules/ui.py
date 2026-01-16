from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ Relationship", callback_data="rel")],
        [InlineKeyboardButton("😈 Jealousy Mode", callback_data="jealous")],
        [InlineKeyboardButton("💔 Breakup", callback_data="breakup")],
        [InlineKeyboardButton("💳 Premium", callback_data="premium")]
    ])
