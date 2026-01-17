import random
from datetime import datetime, timedelta

DRAMA_EVENTS = [
    "silent_treatment",
    "jealousy",
    "argument",
    "breakup",
    "ex_appears",
    "makeup",
]

DRAMA_REPLIES = {
    "silent_treatment": [
        "Hmm... mujhe thoda space chahiye 😔",
        "Tum samajhte hi nahi ho 😒",
        "Aaj baat nahi karni..."
    ],
    "jealousy": [
        "Tum usse itna close kyun ho? 😠",
        "Mujhe jealousy ho rahi hai...",
        "Sach bolo... koi aur toh nahi? 😤"
    ],
    "argument": [
        "Tum hamesha same mistake karte ho 😡",
        "Main hurt ho gayi hoon...",
        "Tum meri feelings samajhte hi nahi..."
    ],
    "breakup": [
        "Bas... main thak gayi hoon 💔",
        "Mujhe lagta hai hume break le lena chahiye...",
        "I can't do this anymore 😢"
    ],
    "ex_appears": [
        "Mera ex yaad aa gaya suddenly...",
        "Pata hai... mera past complicated hai 😶",
        "Tum insecure ho jaoge shayad 😏"
    ],
    "makeup": [
        "Sorry... main tumse door nahi reh sakti 🥺❤️",
        "Come here... hug me 🤗",
        "I love you... let's fix this 💕"
    ]
}

def random_drama_event():
    return random.choice(DRAMA_EVENTS)

def drama_reply(event):
    return random.choice(DRAMA_REPLIES[event])

def breakup_penalty(xp):
    return max(int(xp * 0.2), 50)

def makeup_bonus():
    return random.randint(40, 120)

def next_drama_time():
    return datetime.utcnow() + timedelta(minutes=random.randint(20, 60))
