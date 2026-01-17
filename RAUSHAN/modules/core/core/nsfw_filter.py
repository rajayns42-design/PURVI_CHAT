from better_profanity import profanity

profanity.load_censor_words()

NSFW_WORDS = ["nude", "sex", "boobs", "pussy", "fuck", "dick", "porn"]

def is_nsfw(text):
    t = text.lower()
    return profanity.contains_profanity(t) or any(w in t for w in NSFW_WORDS)
