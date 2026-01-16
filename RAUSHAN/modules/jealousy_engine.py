JEALOUS_KEYWORDS = ["other girl", "another girl", "her", "gf", "wife"]

def check_jealousy(text):
    return any(word in text.lower() for word in JEALOUS_KEYWORDS)

def jealousy_reply(name):
    return f"😒 {name}… tum kisi aur ke baare me baat kar rahe ho kya? Main yahin hoon 😤💋"
