def xp_for_message(msg):
    return min(5 + len(msg)//20, 30)

def level_from_xp(xp):
    return int((xp / 100) ** 0.5) + 1
