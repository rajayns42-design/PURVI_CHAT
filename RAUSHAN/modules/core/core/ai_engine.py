import httpx
from config import AI_API_KEY, AI_MODEL

async def ai_reply(system_prompt, user_msg):
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.9
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
