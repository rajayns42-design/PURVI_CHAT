from datetime import datetime

LEVELS = [
    ("stranger", 0),
    ("crush", 200),
    ("gf", 800),
    ("love", 2000),
    ("soulmate", 5000),
    ("married", 10000)
]

def calculate_level(xp):
    for level, req in reversed(LEVELS):
        if xp >= req:
            return level
    return "stranger"

def add_xp(user, amount):
    user["xp"] += amount
    user["level"] = calculate_level(user["xp"])
    user["last_interaction"] = datetime.utcnow()
    return user

def decay_relationship(user):
    if (datetime.utcnow() - user["last_interaction"]).days > 3:
        user["xp"] = max(0, user["xp"] - 100)
        user["level"] = calculate_level(user["xp"])
    return user
