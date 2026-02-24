import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

BASE = "https://turbo.az/autos"

BRAND_IDS = {
    "BMW": 3, "Mercedes": 4, "Toyota": 23, "Hyundai": 1,
    "Kia": 8, "Honda": 12, "Nissan": 7, "Volkswagen": 24,
    "Audi": 9, "Chevrolet": 41, "Opel": 29, "Ford": 2,
}


def build_url(params, page):
    q = f"?page={page}&q%5Bcurrency%5D=azn&q%5Bcategory%5D=1"
    if params.get("brand_id"):
        q += f"&q%5Bmake%5D%5B%5D={params['brand_id']}"
    if params.get("price_max"):
        q += f"&q%5Bprice_to%5D={params['price_max']}"
    if params.get("price_min"):
        q += f"&q%5Bprice_from%5D={params['price_min']}"
    if params.get("year_min"):
        q += f"&q%5Byear_from%5D={params['year_min']}"
    if params.get("crashed"):
        q += "&q%5Bcrashed%5D=1"
    return BASE + q


def parse_card(card):
    a = card.select_one("a.products-i__link")
    url = "https://turbo.az" + a["href"] if a else None
    tid = url.rstrip("/").split("/")[-1].split("-")[0] if url else None

    price_tag = card.select_one(".products-i__price")
    price = None
    if price_tag:
        price = float(
            price_tag.text.strip()
            .replace("\xa0", "").replace("₼", "").replace(" ", "")
        )

    name = card.select_one(".products-i__name")
    attrs = card.select_one(".products-i__attributes")
    city_tag = card.select_one(".products-i__datetime")
    img = card.select_one("img")

    brand = model = None
    if name:
        parts = name.text.strip().split(" ", 1)
        brand = parts[0]
        model = parts[1] if len(parts) > 1 else None

    year = mileage = engine = None
    is_moto = False
    if attrs:
        arr = attrs.text.strip().split(",")
        try:
            year = int(arr[0].strip())
        except:
            pass
        if len(arr) >= 2:
            engine = arr[1].strip()
            if "sm3" in engine.lower():
                return None
        if len(arr) >= 3:
            try:
                mileage = int(arr[2].strip().replace(" ", "").replace("km", ""))
            except:
                pass

    city = city_tag.text.strip().split(",")[0] if city_tag else None

    return {
        "turbo_id": tid,
        "url": url,
        "brand": brand,
        "model": model,
        "year": year,
        "price_azn": price,
        "mileage_km": mileage,
        "engine": engine,
        "city": city,
        "image": img["src"] if img and img.get("src") else None,
    }


def scrape_listings(params, max_pages=1):
    arr = []
    for p in range(1, max_pages + 1):
        url = build_url(params, p)
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        cards = soup.select(".products-i")
        if not cards:
            break
        for card in cards:
            x = parse_card(card)
            if x and x["turbo_id"]:
                arr.append(x)
        print(f"Səhifə {p}: {len(cards)} elan tapıldı")
    return arr


def scrape(url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    props = {}
    for tag in soup.select(".product-properties__i"):
        n = tag.select_one(".product-properties__i-name")
        v = tag.select_one(".product-properties__i-value")
        if n and v:
            props[n.text.strip()] = v.text.strip()

    images = []
    for img in soup.select(".product-photos__slider-top-i img"):
        if img.get("src"):
            images.append(img["src"])

    extras = []
    for li in soup.select(".product-extras__i"):
        extras.append(li.text.strip())

    title = soup.select_one(".product-title")
    price = soup.select_one(".product-price__i--bold")
    views = soup.select_one(".product-statistics__i-text")
    desc = soup.select_one(".product-description__content p")
    tid = url.rstrip("/").split("/")[-1].split("-")[0]

    price_clean = None
    if price:
        price_clean = float(
            price.text.strip()
            .replace("\xa0", "").replace("₼", "").replace(" ", "")
        )

    mileage_clean = None
    mileage_raw = props.get("Yürüş")
    if mileage_raw:
        try:
            mileage_clean = int(mileage_raw.replace(" ", "").replace("km", ""))
        except:
            pass

    year_clean = None
    year_raw = props.get("Buraxılış ili")
    if year_raw:
        try:
            year_clean = int(year_raw.strip())
        except:
            pass

    return {
        "turbo_id": tid,
        "url": url,
        "title": title.text.strip() if title else None,
        "price_azn": price_clean,
        "city": props.get("Şəhər"),
        "brand": props.get("Marka"),
        "model": props.get("Model"),
        "year": year_clean,
        "body_type": props.get("Ban növü"),
        "color": props.get("Rəng"),
        "engine": props.get("Mühərrik"),
        "mileage_km": mileage_clean,
        "transmission": props.get("Sürətlər qutusu"),
        "drive": props.get("Ötürücü"),
        "is_new": props.get("Yeni"),
        "condition": props.get("Vəziyyəti"),
        "description": desc.text.strip() if desc else None,
        "extras": extras,
        "images": images,
        "views": views.text.strip() if views else None,
    }
