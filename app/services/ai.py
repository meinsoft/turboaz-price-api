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
        sys_msg = """You are a car search query parser for Azerbaijan market.
User may write in Azerbaijani, Russian, or mixed. Return ONLY valid JSON, no markdown.

Fields (null if not mentioned):
{
    "brand":       "BMW" / "Mercedes" / "Toyota" etc or null,
    "model":       "520" / "X5" / "E220" etc or null,
    "price_min":   number in AZN or null,
    "price_max":   number in AZN or null,
    "year_min":    4-digit number or null,
    "year_max":    4-digit number or null,
    "color":       one of: qara/ağ/gümüşü/qırmızı/boz/mavi/göy/sarı/yaşıl/bej/qəhvəyi/qızılı/narıncı/çəhrayı or null,
    "region":      "Bakı" / "Gəncə" / "Sumqayıt" / "Lənkəran" etc or null,
    "fuel_type":   "Benzin" / "Dizel" / "Elektrik" / "Hibrid" / "Qaz" or null,
    "gear":        "Avtomat" / "Mexanik" / "Yarımavtomat" or null,
    "body_type":   "Sedan" / "Hetçbek" / "Universal" / "Offroader / SUV" / "Kupe" / "Kabriolet" / "Minivan" / "Pikap" or null,
    "market":      "Avropa" / "Amerika" / "Yaponiya" / "Koreya" / "Çin" or null,
    "crashed_ok":  true or false,
    "not_painted":   true or null,
    "km_min":        number or null,
    "km_max":        number or null,
    "seats":         number (5/7/8) or null,
    "owners_max":    number (1/2/3) or null,
    "drive":         "Arxa" / "Ön" / "Tam" or null,
    "loan":          true or null,
    "barter":        true or null,
    "only_dealers":  true or null,
    "only_private":  true or null,
    "extras":        list of: "lyuk"/"abs"/"deri salon"/"kondisioner"/"park radari"/"kamera"/"isitme" or null,
    "priority":      "price" / "mileage" / "year" or null
}

Rules:
- ucuz/büdcəyə uyğun/deshevo/недорого → priority: price
- az yürüşlü/az gedişli/с малым пробегом → priority: mileage
- yeni/təzə/свежий/новый → priority: year
- vurğu ola bilər/vuruq/битый/vurulmuş → crashed_ok: true
- rənglənməyib/boyasız/не крашена → not_painted: true
- avtomat/avto/автомат → gear: Avtomat
- mexanik/mexanika/механика → gear: Mexanik
- dizel/дизель → fuel_type: Dizel
- benzin/бензин → fuel_type: Benzin
- elektrik/elektro/электро → fuel_type: Elektrik
- hibrid/hybrid → fuel_type: Hibrid
- sedan → body_type: Sedan
- suv/krossover/внедорожник → body_type: Offroader / SUV
- hetçbek/hetchback → body_type: Hetçbek
- universal/универсал → body_type: Universal
- avropa/европа → market: Avropa
- yaponiya/япония → market: Yaponiya
- amerika/америка → market: Amerika
- koreya/корея → market: Koreya
- price hints: "min azn"=*1000, "15k"=15000, "on min"=10000, "ucuz" no number → price_max: 25000
- km hints: "100k km-dən az" → km_max: 100000, "50 min km" → km_max: 50000
- "7 yerli" / "7 oturacaqlı" → seats: 7
- "ilk sahibi" / "bir sahibli" → owners_max: 1
- "arxa ötürücü" → drive: Arxa, "tam ötürücü"/"4x4" → drive: Tam, "ön ötürücü" → drive: Ön
- "kreditlə" → loan: true
- "barterle"/"barter" → barter: true
- "dilerden" → only_dealers: true, "şəxsidən"/"özəl" → only_private: true
- "lyuklu" → extras: ["lyuk"], "deri salon" → extras: ["deri salon"]
"""
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": s}],
            temperature=0.1,
        )
        return json.loads(res.choices[0].message.content)

    def explain(self, arr, user_prompt, priority=None, color=None):
        priority_note = ""
        if priority == "mileage":
            priority_note = "User cares most about LOW mileage. Mention km in every why."
        elif priority == "price":
            priority_note = "User cares most about LOW price. Mention price in every why."
        elif priority == "year":
            priority_note = "User cares most about NEW cars. Mention year in every why."
        if color:
            priority_note += f" All cars are already filtered by color ({color}). Never mention color issues."

        ids = [x["turbo_id"] for x in arr]
        sys_msg = (
            "You are a car assistant writing short explanations in Azerbaijani. "
            + priority_note
            + f" Return JSON with key results as array. Each item: turbo_id and why. "
            + f"Cover ALL of these ids: {ids}. "
            + "why: Azerbaijani, max 15 words. Write like a friend recommending a car — casual, honest, natural. "
            + "Use the car data but explain it conversationally, not just list specs. "
            + "Examples: 'Az qalıb, demək olar yenidir' or 'Puluna dəyər, bu qiymətə belə tapılmaz' or 'Kilometri çoxdur amma qiymət bağışladır'. "
            + "Tone: real person talking, not a robot."
        )
        user_msg = f"User request: {user_prompt}\nCars:\n{json.dumps(arr, ensure_ascii=False)}"
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.3,
        )
        parsed = json.loads(res.choices[0].message.content)
        if "results" in parsed:
            return parsed["results"]
        return []

    def _calc_pros_cons(self, listing, similar):
        """Pros/cons-u hesabla, AI hallüsinasiyasız"""
        price = listing.get("price_azn") or 0
        km    = listing.get("mileage_km") or 0
        year  = listing.get("year") or 2000
        condition = (listing.get("condition") or "").lower()

        prices = [s.get("price_azn") for s in similar if s.get("price_azn")]
        kms    = [s.get("mileage_km") for s in similar if s.get("mileage_km")]
        avg_price = sum(prices) / len(prices) if prices else price
        avg_km    = sum(kms) / len(kms) if kms else km

        pros, cons = [], []

        # Qiymət
        if price < avg_price * 0.85:
            pros.append(f"Qiymət bazar ortalamasından {round((1 - price/avg_price)*100)}% ucuzdur")
        elif price > avg_price * 1.15:
            cons.append(f"Qiymət bazar ortalamasından {round((price/avg_price - 1)*100)}% bahadır")
        else:
            pros.append("Qiymət bazar ortalamasına uyğundur")

        # Yürüş
        if km > 0 and kms:
            if km < avg_km * 0.7:
                pros.append(f"Az yürüşlüdür ({km:,} km — ortalama {int(avg_km):,} km)")
            elif km > avg_km * 1.3:
                cons.append(f"Yürüşü yüksəkdir ({km:,} km — ortalama {int(avg_km):,} km)")
            else:
                pros.append(f"Yürüşü normaldır ({km:,} km)")

        # İl
        if year >= 2023:
            pros.append(f"{year}-ci il — yeni avtomobildir")
        elif year >= 2018:
            pros.append(f"{year}-ci il — orta yaşlı avtomobildir")
        else:
            cons.append(f"{year}-ci il — köhnə avtomobildir")

        # Vəziyyət
        if "vuruğu var" in condition or "rənglənib" in condition:
            cons.append("Vuruğu var və ya rənglənib")
        elif "vuruğu yoxdur" in condition:
            pros.append("Vuruğu yoxdur, rənglənməyib")

        return pros[:3], cons[:3]

    def analyze(self, listing, similar):
        sys_msg = """You are an honest, experienced Azerbaijani car dealer giving advice to a friend.
Compare the listing against similar cars and return ONLY valid JSON, no markdown.
All text fields MUST be in Azerbaijani. Be specific, direct, and useful.

Rules:
- verdict: "Ucuzdur" if price is 10%+ below market, "Bahalıdır" if 10%+ above, else "Normaldır"
- score: 0-100 overall buy recommendation (consider price, mileage, year, condition together)
- price_diff_percent: exact % difference from similar cars average (negative = cheaper)
- summary: 2 sentences max. Mention exact numbers (price, km, year). Sound like a friend giving real advice, not a report.
- pros: 3 items max. Each must be SPECIFIC to this car. Mention real numbers. No generic phrases.
- cons: 3 items max. Each must be SPECIFIC to this car. Mention real numbers. No generic phrases.

Good pros example: "203,150 AZN-ə 2023 X7 — bazarda ən az yürüşlülərdən biridir (15,000 km)"
Bad pros example: "Maşın yeni və az kilometrkeçirilidir"

Good cons example: "Eyni X7-lər 175,000-185,000 AZN-ə satılır, bu isə 15% bahadır"
Bad cons example: "Qiymət bir az yüksəkdir"

Format:
{
    "verdict": "Ucuzdur" or "Normaldır" or "Bahalıdır",
    "score": 0-100,
    "price_diff_percent": 12.5,
    "summary": "...",
    "pros": ["...", "...", "..."],
    "cons": ["...", "...", "..."]
}"""
        # Similar datani sadə mətn kimi göndər — hallüsinasiya azalır
        similar_text = "\n".join([
            f"- {s.get('brand','')} {s.get('model','')} {s.get('year','')} | {s.get('price_azn','')} AZN | {s.get('mileage_km','')} km"
            for s in similar[:15]
        ])
        avg_price = sum(s.get('price_azn',0) for s in similar if s.get('price_azn')) / max(len([s for s in similar if s.get('price_azn')]), 1)
        user_msg = f"""Analyze this specific car listing. Use ONLY the data provided below. Do NOT invent any numbers.
Listing car (analyze THIS only):
Brand: {listing.get('brand')} {listing.get('model')}
Year: {listing.get('year')}
Price: {listing.get('price_azn')} AZN
Mileage: {listing.get('mileage_km')} km
City: {listing.get('city')}
Condition: {listing.get('condition', 'unknown')}

Market average price: {round(avg_price)} AZN
Similar cars on market:
{similar_text}

Write pros/cons ONLY about the listing car above.
STRICT: Use ONLY the exact numbers from listing (price={listing.get('price_azn')} AZN, km={listing.get('mileage_km')}, year={listing.get('year')}).
Do NOT invent or approximate any numbers.
For mileage comparison: lower km than market average is GOOD, higher is BAD."""
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        result = json.loads(res.choices[0].message.content)
        pros, cons = self._calc_pros_cons(listing, similar)
        result["pros"] = pros
        result["cons"] = cons
        return result
