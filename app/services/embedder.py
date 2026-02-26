from sentence_transformers import SentenceTransformer
import json
from pathlib import Path

_model = None
_filters = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model

def get_filters():
    global _filters
    if _filters is None:
        path = Path(__file__).parent / "turboaz_filters.json"
        with open(path, encoding="utf-8") as f:
            _filters = json.load(f)
    return _filters

def resolve(filter_key, id_or_name):
    """ID-dən ad-a çevir, ad varsa olduğu kimi qaytar"""
    if not id_or_name:
        return None
    f = get_filters()
    data = f.get(filter_key, {})
    val = str(id_or_name)
    # ID ilə axtar
    if val in data:
        return data[val]
    # Ad ilə axtar (artıq ad-dırsa)
    for fid, name in data.items():
        if name.lower() == val.lower():
            return name
    return str(id_or_name)

def build_text(d):
    parts = []

    # Brand + Model
    brand = d.get("brand") or resolve("q[make][]", d.get("make_id"))
    model = d.get("model") or resolve("q[model][]", d.get("model_id"))
    if brand and model:
        parts.append(f"{brand} {model}")
    elif brand:
        parts.append(brand)

    # İl
    year = d.get("year")
    if year:
        parts.append(f"{year} il")

    # Kuzov növü
    body = d.get("body_type") or resolve("q[category][]", d.get("category_id"))
    if body:
        parts.append(body)

    # Yanacaq
    fuel = d.get("fuel_type") or resolve("q[fuel_type][]", d.get("fuel_id"))
    if fuel:
        parts.append(fuel)

    # Sürətlər qutusu
    trans = d.get("transmission") or resolve("q[transmission][]", d.get("trans_id"))
    if trans:
        parts.append(trans)

    # Ötürücü
    gear = d.get("drive") or resolve("q[gear][]", d.get("gear_id"))
    if gear:
        parts.append(gear)

    # Rəng
    color = d.get("color") or resolve("q[color][]", d.get("color_id"))
    if color:
        parts.append(f"{color} rəng")

    # Bazar
    market = d.get("market") or resolve("q[market][]", d.get("market_id"))
    if market:
        parts.append(f"{market} bazarı")

    # Şəhər/Region
    city = d.get("city") or resolve("q[region][]", d.get("region_id"))
    if city:
        parts.append(city)

    # Qiymət — sözlü ifadə
    price = d.get("price_azn") or 0
    if price < 10000:   parts.append("çox ucuz büdcəyə uyğun")
    elif price < 20000: parts.append("ucuz əlverişli")
    elif price < 40000: parts.append("orta qiymət")
    elif price < 80000: parts.append("yuxarı qiymət")
    else:               parts.append("bahalı premium")

    # Km — sözlü ifadə
    km = d.get("mileage_km") or 0
    if km == 0:          parts.append("yeni sıfır km")
    elif km < 50000:     parts.append("az yürüşlü")
    elif km < 150000:    parts.append("orta yürüş")
    else:                parts.append("çox yürüşlü")

    # Oturacaq sayı
    seats = d.get("seats") or 0
    try:
        seats = int(seats)
        if seats >= 7:
            parts.append(f"{seats} yerli geniş ailə")
    except:
        pass

    # Vəziyyət
    cond = (d.get("condition") or "").lower()
    if "vuruğu yoxdur" in cond:
        parts.append("təmiz vuruğu yoxdur")
    elif "vuruğu var" in cond:
        parts.append("vuruğu var zədəli")
    if "rənglənməyib" in cond:
        parts.append("rənglənməyib orijinal")
    elif "rənglənib" in cond:
        parts.append("rənglənib")

    # Extras
    extras = d.get("extras")
    if extras and isinstance(extras, list):
        parts.extend(extras[:5])

    # Açıqlama
    desc = d.get("description")
    if desc:
        parts.append(desc[:200])

    return " ".join(filter(None, parts))

def embed(text):
    m = get_model()
    vec = m.encode(text, normalize_embeddings=True)
    return vec.tolist()

def embed_listing(d):
    return embed(build_text(d))
