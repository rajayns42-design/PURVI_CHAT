import random

QUIZ_QUESTIONS = [
    ("Your partner's fav color?", ["Red", "Blue", "Black", "Pink"], "Pink"),
    ("Perfect date idea?", ["Movie", "Beach", "Cafe", "Road trip"], "Road trip"),
    ("Love language?", ["Gifts", "Time", "Touch", "Words"], "Touch"),
]

KISS_DUEL_LINES = [
    "💋 Tumne pehla kiss jeet liya!",
    "😘 Oops! Tum haar gaye!",
    "🔥 It's a tie... intense chemistry!",
]

LOVE_BATTLES = [
    "Who loves more? ❤️",
    "Who texts first? 📱",
    "Who gets jealous faster? 😏",
]

def quiz_question():
    return random.choice(QUIZ_QUESTIONS)

def kiss_duel():
    return random.choice(KISS_DUEL_LINES)

def love_battle():
    return random.choice(LOVE_BATTLES)
