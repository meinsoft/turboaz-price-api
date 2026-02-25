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
        - ailə, семейный, rahat → set year_min to 2005
        - If no mileage mentioned, leave null
        """
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": s}],
            temperature=0.1,
        )
        return json.loads(res.choices[0].message.content)

    def explain(self, arr, user_prompt, priority=None):
        results = []
        for car in arr:
            tid   = car.get("turbo_id")
            price = car.get("price_azn") or 0
            km    = car.get("mileage_km")
            year  = car.get("year") or 0
            sim   = car.get("similarity") or 0

            if priority == "price":
                if price < 8000:    why = f"{int(price)} AZN — çox ucuzdur"
                elif price < 15000: why = f"{int(price)} AZN — əlverişli qiymətdir"
                elif price < 25000: why = f"{int(price)} AZN — orta qiymət"
                else:               why = f"{int(price)} AZN — yuxarı qiymət"
            elif priority == "mileage":
                if km is None:      why = f"{year} il — yürüşü bilinmir"
                elif km < 50000:    why = f"{km:,} km — çox az yürüşlüdür"
                elif km < 100000:   why = f"{km:,} km — az yürüşlüdür"
                elif km < 200000:   why = f"{km:,} km — orta yürüş"
                else:               why = f"{km:,} km — yürüşü çoxdur"
            elif priority == "year":
                if year >= 2022:    why = f"{year} il — çox təzədir"
                elif year >= 2018:  why = f"{year} il — təzədir"
                elif year >= 2014:  why = f"{year} il — orta yaş"
                else:               why = f"{year} il — köhnədir"
            else:
                if sim >= 0.75:     why = f"sorğuya çox uyğundur, {year} il"
                elif sim >= 0.6:    why = f"sorğuya uyğundur, {year} il"
                else:               why = f"{year} il, {int(price)} AZN"

            results.append({"turbo_id": tid, "why": why})
        return results
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
