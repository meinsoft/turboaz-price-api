import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)


def clean(txt):
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[-1]
    if txt.endswith("```"):
        txt = txt.rsplit("```", 1)[0]
    return txt.strip()


class PromptParser:

    def parse(self, s):
        sys_msg = """
        You are a car search assistant. Convert the user prompt into structured JSON.
        User may write in Azerbaijani or Russian.
        Return ONLY valid JSON, no markdown, no code blocks.
        Format:
        {
            "brand": "BMW" or null,
            "model": "520" or null,
            "price_max": 30000 or null,
            "price_min": null,
            "year_min": null,
            "year_max": null,
            "crashed_ok": true or false,
            "priority": "price" or "mileage" or "year"
        }
        Rules:
        - ucuz, büdcəyə uyğun, дешево, недорого → priority: price
        - vurğu ola bilər, vurulmuş, битый → crashed_ok: true
        - az yürüşlü, с небольшим пробегом → priority: mileage
        - yeni, свежий, новый → priority: year
        - If user says недорого or ucuz but no number, set price_max to 20000
        """
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": s}],
            temperature=0.1,
        )
        return json.loads(clean(res.choices[0].message.content))

    def rank(self, arr, s, priority=None):
        priority_instruction = ""
        if priority == "mileage":
            priority_instruction = "CRITICAL: Sort by mileage_km ascending. Cars with LOWEST mileage must be ranked first. Never rank a high mileage car above a low mileage car."
        elif priority == "price":
            priority_instruction = "CRITICAL: Sort by price_azn ascending. Cars with LOWEST price must be ranked first."
        elif priority == "year":
            priority_instruction = "CRITICAL: Sort by year descending. Newest cars must be ranked first."

        sys_msg = f"""
        You are a car expert. Rank listings based on user request.
        Return ONLY valid JSON array, no markdown, no code blocks.
        Each item format: {{"turbo_id": "...", "rank": 1, "score": 85, "why": "...azerbaijani..."}}
        The why field MUST be in Azerbaijani only.
        {priority_instruction}
        """
        user_msg = f"User request: {s}\nListings:\n{json.dumps(arr, ensure_ascii=False)}\nPick best 5. Write why in Azerbaijani only."
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        return json.loads(clean(res.choices[0].message.content))

    def analyze(self, listing, similar):
        sys_msg = """
        You are a car price expert. Compare listing with similar ones.
        Return ONLY valid JSON, no markdown, no code blocks.
        All text fields must be in Azerbaijani language only.
        Format:
        {
            "verdict": "Ucuzdur" or "Normaldır" or "Bahalıdır",
            "score": 0-100,
            "price_diff_percent": 12.5,
            "summary": "...",
            "pros": ["..."],
            "cons": ["..."]
        }
        """
        user_msg = f"Listing:\n{json.dumps(listing, ensure_ascii=False)}\nSimilar:\n{json.dumps(similar, ensure_ascii=False)}"
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        return json.loads(clean(res.choices[0].message.content))
