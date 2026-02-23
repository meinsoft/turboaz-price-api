from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ai import PromptParser
from app.services.scraper import scrape_listings, BRAND_IDS
from app.services.db import search_listings

router = APIRouter()
parser = PromptParser()


class Req(BaseModel):
    prompt: str
    force_scrape: bool = False


def sort_by_priority(arr, priority):
    if priority == "mileage":
        arr.sort(key=lambda x: x.get("mileage_km") or 999999)
    elif priority == "price":
        arr.sort(key=lambda x: x.get("price_azn") or 999999)
    elif priority == "year":
        arr.sort(key=lambda x: x.get("year") or 0, reverse=True)
    return arr


def calc_score(item, priority, rank):
    km = item.get("mileage_km") or 0
    price = item.get("price_azn") or 0
    year = item.get("year") or 2000
    base = 95 - (rank - 1) * 5

    if priority == "mileage":
        if km < 50000:    bonus = 0
        elif km < 100000: bonus = -5
        elif km < 200000: bonus = -15
        else:             bonus = -25
    elif priority == "price":
        if price < 10000:  bonus = 0
        elif price < 20000: bonus = -5
        elif price < 40000: bonus = -15
        else:               bonus = -25
    elif priority == "year":
        if year >= 2022:   bonus = 0
        elif year >= 2018: bonus = -5
        elif year >= 2014: bonus = -15
        else:              bonus = -25
    else:
        bonus = 0

    return min(max(base + bonus, 0), 100)


def slim(item):
    return {
        "turbo_id": item.get("turbo_id"),
        "brand": item.get("brand"),
        "model": item.get("model"),
        "year": item.get("year"),
        "price_azn": item.get("price_azn"),
        "mileage_km": item.get("mileage_km"),
        "city": item.get("city"),
    }


@router.post("/recommend")
def recommend(req: Req):
    parsed = parser.parse(req.prompt)

    brand = parsed.get("brand")
    model = parsed.get("model")
    price_max = parsed.get("price_max")
    year_min = parsed.get("year_min")
    crashed_ok = parsed.get("crashed_ok")
    priority = parsed.get("priority")

    arr = search_listings(brand, None, price_max, year_min, crashed_ok)

    if len(arr) < 5 or req.force_scrape:
        params = {}
        if brand:
            bid = BRAND_IDS.get(brand)
            if bid:
                params["brand_id"] = bid
        if price_max:
            params["price_max"] = price_max
        if crashed_ok:
            params["crashed"] = True
        arr = scrape_listings(params, max_pages=1)

    if model:
        filtered = []
        for x in arr:
            if x.get("model") and model.lower() in x["model"].lower():
                filtered.append(x)
        if filtered:
            arr = filtered

    seen = set()
    unique = []
    for x in arr:
        if x["turbo_id"] not in seen:
            seen.add(x["turbo_id"])
            unique.append(x)
    arr = unique

    if not arr:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")

    arr = sort_by_priority(arr, priority)
    top5 = arr[:5]

    for i, item in enumerate(top5):
        item["rank"] = i + 1
        item["score"] = calc_score(item, priority, i + 1)

    slim_list = [slim(x) for x in top5]
    whys = parser.explain(slim_list, req.prompt, priority)
    why_map = {w["turbo_id"]: w["why"] for w in whys}

    for item in top5:
        item["why"] = why_map.get(item["turbo_id"], "")

    return {"prompt_parsed": parsed, "total_found": len(arr), "recommendations": top5}
