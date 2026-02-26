import json
import requests
import re
from pathlib import Path
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
BASE = "https://turbo.az/autos"

_filters_path = Path(__file__).parent / "turboaz_filters.json"
with open(_filters_path, encoding="utf-8") as f:
    _F = json.load(f)

def _lookup(filter_key, label):
    data = _F.get(filter_key, {})
    label = label.lower().strip()
    for fid, name in data.items():
        if (name.lower() == label) or (label in name.lower()):
            return fid
    return None

def brand_id(name): return _lookup("q[make][]", name)
def color_id(name): return _lookup("q[color][]", name)
def region_id(name): return _lookup("q[region][]", name)
def fuel_id(name): return _lookup("q[fuel_type][]", name)

def trans_id(name):
    data = _F.get("q[transmission][]", {})
    name = name.lower().strip()
    if ("avtomat" in name) or ("auto" in name):
        for fid, label in data.items():
            if ("avtomat" in label.lower()) and ("at)" in label.lower()): return fid
        for fid, label in data.items():
            if ("avtomat" in label.lower()): return fid
    if ("mexanik" in name) or ("manual" in name):
        for fid, label in data.items():
            if ("mexaniki" in label.lower()): return fid
    return _lookup("q[transmission][]", name)

def drive_id(name): return _lookup("q[gear][]", name)

def body_id(name):
    name = name.lower().strip()
    data = _F.get("q[category][]", {})
    if ("suv" in name) or ("offroader" in name) or ("krossover" in name):
        return [fid for fid, label in data.items() if ("offroader" in label.lower()) or ("suv" in label.lower())]
    for fid, label in data.items():
        if (label.lower() == name) or (name in label.lower()): return [fid]
    return None

def market_id(name): return _lookup("q[market][]", name)

BRAND_IDS = {name: int(fid) for fid, name in _F.get("q[make][]", {}).items()}
COLOR_IDS = {name.lower(): int(fid) for fid, name in _F.get("q[color][]", {}).items()}

def build_url(params, page):
    parts = [f"page={page}", "q%5Bcurrency%5D=azn"]
    cat_ids = params.get("category_ids")
    if (cat_ids):
        for cid in cat_ids: parts.append(f"q%5Bcategory%5D%5B%5D={cid}")
    elif (params.get("category_id", "1") != "1"):
        parts.append(f"q%5Bcategory%5D%5B%5D={params['category_id']}")
    else:
        auto_cats = [1,2,3,4,5,6,8,11,14,21,28,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75]
        for cid in auto_cats: parts.append(f"q%5Bcategory%5D%5B%5D={cid}")

    def add(key, val): parts.append(f"q%5B{key}%5D%5B%5D={val}")
    def add_range(key, val): parts.append(f"q%5B{key}%5D={val}")

    if (params.get("brand_id")): add("make", params["brand_id"])
    if (params.get("color_id")): add("color", params["color_id"])
    if (params.get("region_id")): add("region", params["region_id"])
    if (params.get("fuel_id")): add("fuel_type", params["fuel_id"])
    if (params.get("trans_id")): add("transmission", params["trans_id"])
    if (params.get("drive_id")): add("gear", params["drive_id"])
    if (params.get("market_id")): add("market", params["market_id"])
    if (params.get("seats_id")): add("seats_count", params["seats_id"])
    if (params.get("price_min")): add_range("price_from", params["price_min"])
    if (params.get("price_max")): add_range("price_to", params["price_max"])
    if (params.get("year_min")): add_range("year_from", params["year_min"])
    if (params.get("year_max")): add_range("year_to", params["year_max"])
    if (params.get("km_min")): add_range("mileage_from", params["km_min"])
    if (params.get("km_max")): add_range("mileage_to", params["km_max"])
    if (params.get("power_min")): add_range("power_from", params["power_min"])
    if (params.get("power_max")): add_range("power_to", params["power_max"])
    if (params.get("engine_max")): add_range("engine_volume_to", params["engine_max"])
    if (params.get("owners_count")): add("prior_owners_count", params["owners_count"])
    if (params.get("crashed")): parts.append("q%5Bcrashed%5D=1")
    if (params.get("not_painted")): parts.append("q%5Bpainted%5D=0")
    if (params.get("not_crashed")): parts.append("q%5Bcrashed%5D=0")
    if (params.get("loan")): parts.append("q%5Bloan%5D=1")
    if (params.get("barter")): parts.append("q%5Bbarter%5D=1")
    if (params.get("only_dealers")): parts.append("q%5Bonly_shops%5D=1")
    if (params.get("only_private")): parts.append("q%5Bonly_shops%5D=0")
    if (params.get("availability")): add_range("availability_status", params["availability"])
    for extra_id in params.get("extras", []): add("extras", extra_id)

    return f"{BASE}?{'&'.join(parts)}"

def parse_card(card):
    a = card.select_one("a.products-i__link")
    if (not a): return {}
    url = f"https://turbo.az{a['href']}"
    tid = url.rstrip("/").split("/")[-1].split("-")[0]

    name_tag = card.select_one(".products-i__name")
    price_tag = card.select_one(".products-i__price")
    city_tag = card.select_one(".products-i__datetime")
    img_tag = card.select_one("img")
    attrs_tag = card.select_one(".products-i__attributes")

    name = name_tag.text.strip() if (name_tag) else ""
    parts = name.split()
    brand = parts[0] if (parts) else None
    model = " ".join(parts[1:]) if (len(parts) > 1) else None

    price_azn = None
    if (price_tag):
        raw = price_tag.text.strip().replace("≈","").replace("₼","").replace("AZN","").replace("\xa0","").replace(" ","").replace(",","")
        try: price_azn = float(raw)
        except: pass

    city = city_tag.text.strip().split("\n")[0].split(",")[0].strip() if (city_tag) else None
    img = (img_tag.get("src") or img_tag.get("data-src")) if (img_tag) else None
    if (img and img.startswith("//")): img = f"https:{img}"

    year = mileage_km = engine = None
    if (attrs_tag):
        for part in attrs_tag.text.strip().split(","):
            p = part.strip().replace("\xa0", "")
            if (p.isdigit() and len(p) == 4): year = int(p)
            elif ("km" in p.lower()):
                try: mileage_km = int(p.lower().replace("km","").replace(" ","").replace("\xa0",""))
                except: pass
            elif ("L" in p): engine = p.strip()

    return {"turbo_id": tid, "url": url, "brand": brand, "model": model, "year": year, "price_azn": price_azn, "mileage_km": mileage_km, "city": city, "engine": engine, "image": img}

def scrape_listings(params, max_pages=3):
    all_cars = []
    for p in range(1, max_pages + 1):
        try:
            res = requests.get(build_url(params, p), headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.select(".products-i")
            if (not cards): break
            cars = [parse_card(c) for c in cards]
            cars = [c for c in cars if c.get("turbo_id")]
            m_k = ["moto", "motor", "bike", "ktm", "yamaha moto", "honda cb", "kawasaki"]
            cars = [c for c in cars if not any(k in (c.get("model") or "").lower() or k in (c.get("brand") or "").lower() for k in m_k)]
            all_cars.extend(cars)
        except: break
    return all_cars

def scrape(url):
    res = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")

    def get_prop(label):
        for row in soup.select(".product-properties__i"):
            l = row.select_one(".product-properties__i-name")
            v = row.select_one(".product-properties__i-value")
            if (l and v and label.lower() in l.text.lower()): return v.text.strip()
        return None

    p_el = soup.select_one(".product-price__i--bold")
    price = float(re.sub(r"[^\d.]", "", p_el.text.strip().replace(",", "."))) if (p_el) else None

    title = soup.select_one("h1.product-title")
    t_text = title.text.strip() if (title) else ""
    t_parts = t_text.split()
    brand = t_parts[0] if (t_parts) else None
    model = " ".join(t_parts[1:-1]) if (len(t_parts) > 2) else (t_parts[1] if (len(t_parts) == 2) else None)
    year = next((int(x) for x in reversed(t_parts) if x.isdigit() and len(x) == 4), None)

    km_raw = get_prop("Yürüş")
    km = int(km_raw.replace(" ", "").replace("km", "").replace(",", "")) if (km_raw) else None

    city_el = soup.select_one(".product-map__address")
    city = city_el.text.strip().split(",")[0] if (city_el) else get_prop("Şəhər")
    extras = [e.text.strip() for e in soup.select(".product-extras__i")]
    desc = " ".join([v.text.strip() for v in soup.select(".product-properties__i-value")])

    return {
        "turbo_id": url.rstrip("/").split("/")[-1].split("-")[0],
        "url": url, "brand": brand, "model": model, "year": year,
        "price_azn": price, "mileage_km": km, "city": city,
        "engine": get_prop("Mühərrik"), "fuel_type": get_prop("Yanacaq növü"),
        "transmission": get_prop("Sürətlər qutusu"), "body_type": get_prop("Ban növü"),
        "color": get_prop("Rəng"), "drive": get_prop("Ötürücü"),
        "condition": get_prop("Vəziyyəti"), "market": get_prop("Hansı bazar üçün yığılıb"),
        "seats": get_prop("Yerlərin sayı"), "extras": extras, "description": desc,
        "crashed": "vuruğu yoxdur" not in (get_prop("Vəziyyəti") or "").lower()
    }