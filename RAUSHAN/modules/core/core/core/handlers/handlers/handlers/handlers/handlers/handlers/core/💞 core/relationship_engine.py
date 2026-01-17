LEVELS = {
    1: "Crush 💕",
    5: "Flirting 😘",
    10: "Girlfriend ❤️",
    20: "Soulmate 💍",
    40: "Married 💎"
}

def get_level_name(level):
    for l in sorted(LEVELS.keys(), reverse=True):
        if level >= l:
            return LEVELS[l]

