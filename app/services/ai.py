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
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": s}],
            temperature=0.1,
        )
        return json.loads(res.choices[0].message.content)

    def explain(self, arr, user_prompt, priority=None):
        priority_note = ""
        if priority == "mileage":
            priority_note = "User cares most about LOW mileage. Mention km in every why."
        elif priority == "price":
            priority_note = "User cares most about LOW price. Mention price in every why."
        elif priority == "year":
            priority_note = "User cares most about NEW cars. Mention year in every why."

        ids = [x["turbo_id"] for x in arr]
        sys_msg = f"""
        You are a car assistant writing short explanations in Azerbaijani.
        {priority_note}
        
        CRITICAL RULES:
        - You MUST return a why for EVERY turbo_id listed below: {ids}
        - Return JSON object with key "results" as array
        - Each item: {{"turbo_id": "...", "why": "..."}}
        - why must be in Azerbaijani, max 10 words, mention a specific number (km, price or year)
        - Do NOT skip any turbo_id
        """
        user_msg = f"User request: {user_prompt}\nCars:\n{json.dumps(arr, ensure_ascii=False)}"
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.1,
        )
        parsed = json.loads(res.choices[0].message.content)
        if "results" in parsed:
            return parsed["results"]
        for v in parsed.values():
            if isinstance(v, list):
                return v
        return []

    def analyze(self, listing, similar):
        sys_msg = """
        You are a car price expert. Compare listing with similar ones.
        Return ONLY valid JSON, no markdown.
        All text fields must be in Azerbaijani.
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
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        return json.loads(res.choices[0].message.content)
