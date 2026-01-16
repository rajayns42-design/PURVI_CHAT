def trigger_breakup(user):
    user["status"] = "broken"
    user["locked_romance"] = True
    return user

def breakup_reply():
    return "💔 Tum badal gaye ho… ab main pehle jaisi nahi reh sakti 😔"
