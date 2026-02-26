from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ai import PromptParser
from app.services.scraper import scrape_listings, BRAND_IDS, COLOR_IDS
from app.services.db import save_listing_card
from app.services.embedder import get_model, build_text, hybrid_rank, embed_query

import numpy as np

router = APIRouter()
parser = PromptParser()


class Req(BaseModel):
    prompt: str


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def pct(value, pool):
    if not pool or value is None:
        return 0.5
    return len([x for x in pool if x <= value]) / len(pool)


def value_score(car, pool):
    price = car.get("price_azn")  or 99999
    km    = car.get("mileage_km")
    year  = car.get("year")       or 2000
    crash = car.get("crashed")    or False

    prices = [c["price_azn"]  for c in pool if c.get("price_azn")]
    kms    = [c["mileage_km"] for c in pool if c.get("mileage_km") and c["mileage_km"] > 0]
    years  = [c["year"]       for c in pool if c.get("year")]

    p_rank  = pct(price, prices)
    km_rank = pct(km, kms) if km and km > 0 else 0.5
    yr_rank = pct(year, years)

    vfm = (1 - p_rank) * 0.5 + (1 - km_rank) * 0.5

    if year >= 2018:   yr_bonus = 1.0
    elif year >= 2013: yr_bonus = 0.75
    elif year >= 2010: yr_bonus = 0.45
    else:              yr_bonus = 0.15

    crash_mul = 0.75 if crash else 1.0

    return round(vfm * 0.65 + yr_rank * 0.25 * yr_bonus + (0 if crash else 0.10), 4) * crash_mul


def intent_score(car, pool, priority):
    price = car.get("price_azn")  or 99999
    km    = car.get("mileage_km") or 0
    year  = car.get("year")       or 2000

    prices = [c["price_azn"]  for c in pool if c.get("price_azn")]
    kms    = [c["mileage_km"] for c in pool if c.get("mileage_km") and c["mileage_km"] > 0]
    years  = [c["year"]       for c in pool if c.get("year")]

    if priority == "price":
        return round(1 - pct(price, prices), 4)
    if priority == "mileage":
        return round(1 - pct(km, kms), 4) if km > 0 else 0.5
    if priority == "year":
        return round(pct(year, years), 4)
    return None


def score_car(car, pool, priority, similarity):
    sim = max(0.0, min(1.0, (similarity - 0.15) / 0.6))

    if priority:
        base = intent_score(car, pool, priority)
        return round(base * 0.75 + sim * 0.25, 4)

    base = value_score(car, pool)
    return round(base * 0.80 + sim * 0.20, 4)


def slim(car):
    return {
        "turbo_id":   car.get("turbo_id"),
        "brand":      car.get("brand"),
        "model":      car.get("model"),
        "year":       car.get("year"),
        "price_azn":  car.get("price_azn"),
        "mileage_km": car.get("mileage_km"),
        "city":       car.get("city"),
        "engine":     car.get("engine"),
        "fuel_type":  car.get("fuel_type"),
        "crashed":    car.get("crashed"),
        "color":      car.get("color"),
    }


@router.post("/recommend")
def recommend(req: Req):
    parsed    = parser.parse(req.prompt)
    brand     = parsed.get("brand")
    model     = parsed.get("model")
    price_max = parsed.get("price_max")
    price_min = parsed.get("price_min")
    year_min  = parsed.get("year_min")
    year_max  = parsed.get("year_max")
    crashed      = parsed.get("crashed_ok")
    priority     = parsed.get("priority")
    color        = parsed.get("color")
    region       = parsed.get("region")
    fuel_type    = parsed.get("fuel_type")
    gear         = parsed.get("gear")
    body_type    = parsed.get("body_type")
    market       = parsed.get("market")
    not_painted  = parsed.get("not_painted")
    km_min       = parsed.get("km_min")
    km_max       = parsed.get("km_max")
    seats        = parsed.get("seats")
    owners_max   = parsed.get("owners_max")
    drive        = parsed.get("drive")
    loan         = parsed.get("loan")
    barter       = parsed.get("barter")
    only_dealers = parsed.get("only_dealers")
    only_private = parsed.get("only_private")
    extras_list  = parsed.get("extras") or []

    from app.services.scraper import brand_id as _bid, color_id as _cid
    from app.services.scraper import region_id, fuel_id, trans_id, drive_id, body_id, market_id

    params = {}
    if brand:
        bid = _bid(brand)
        if bid: params["brand_id"] = bid
    if price_max:   params["price_max"]  = price_max
    if price_min:   params["price_min"]  = price_min
    if year_min:    params["year_min"]   = year_min
    if year_max:    params["year_max"]   = year_max
    if crashed:     params["crashed"]    = True
    if not_painted: params["not_painted"]= True
    if color:
        cid = _cid(color.lower())
        if cid: params["color_id"] = cid
    if region:
        rid = region_id(region)
        if rid: params["region_id"] = rid
    if fuel_type:
        fid = fuel_id(fuel_type)
        if fid: params["fuel_id"] = fid
    if gear:
        tid = trans_id(gear)
        if tid: params["trans_id"] = tid
    if body_type:
        bids = body_id(body_type)
        if bids: params["category_ids"] = bids if isinstance(bids, list) else [bids]
    if market:
        mid = market_id(market)
        if mid: params["market_id"] = mid
    if km_min:        params["km_min"]       = km_min
    if km_max:        params["km_max"]       = km_max
    if seats:         params["seats_id"]     = str(seats)
    if owners_max:    params["owners_count"] = str(owners_max)
    if loan:          params["loan"]         = True
    if barter:        params["barter"]       = True
    if only_dealers:  params["only_dealers"] = True
    if only_private:  params["only_private"] = True
    if drive:
        drive_map = {"Arxa": "1", "Ön": "2", "Tam": "3"}
        did = drive_map.get(drive)
        if did: params["drive_id"] = did
    extras_id_map = {
        "lyuk": "7", "abs": "5", "deri salon": "13",
        "kondisioner": "11", "park radari": "10",
        "kamera": "15", "isitme": "12"
    }
    if extras_list:
        params["extras"] = [extras_id_map[e] for e in extras_list if e in extras_id_map]

    max_pages = 5 if model else 4 if brand else 3
    cars = scrape_listings(params, max_pages=max_pages)
    if not cars:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")

    for car in cars:
        save_listing_card(car)

    if model:
        ml = model.lower().strip()
        first_word    = ml.split()[0] if ml.split() else ml
        full_no_space = ml.replace(" ", "")

        def model_match(car_model):
            if not car_model:
                return False
            cm = car_model.lower().strip()
            cm_no_space = cm.replace(" ", "")
            if full_no_space in cm_no_space:
                return True
            if "class" in ml and cm.startswith(first_word):
                return True
            if cm.startswith(first_word + " ") or cm == first_word:
                return True
            return False

        filtered = [c for c in cars if model_match(c.get("model"))]
        if filtered:
            cars = filtered

    if year_max:
        filtered = [c for c in cars if (c.get("year") or 9999) <= year_max]
        if filtered:
            cars = filtered

    if year_min:
        filtered = [c for c in cars if (c.get("year") or 0) >= year_min]
        if filtered:
            cars = filtered

    if price_max:
        filtered = [c for c in cars if (c.get("price_azn") or 0) <= price_max]
        if filtered:
            cars = filtered

    if price_min:
        filtered = [c for c in cars if (c.get("price_azn") or 0) >= price_min]
        if filtered:
            cars = filtered

    if not crashed:
        filtered = [c for c in cars if (c.get("year") or 0) >= 2010]
        if filtered:
            cars = filtered

    filtered = [c for c in cars if (c.get("mileage_km") or 0) <= 250000]
    if filtered:
        cars = filtered

    m         = get_model()
    query_vec = embed_query(req.prompt)
    texts     = [f"passage: {build_text(c)}" for c in cars]
    vecs      = m.encode(texts, normalize_embeddings=True, batch_size=32)

    vec_sims = [cosine(query_vec, vecs[i].tolist()) for i in range(len(cars))]
    hybrid   = hybrid_rank(req.prompt, cars, vec_sims)

    for i, car in enumerate(cars):
        car["similarity"] = round(vec_sims[i], 3)
        car["_hybrid"]    = hybrid.get(i, 0)

    if not brand and not color and not body_type and not fuel_type and not gear:
        cars = [c for c in cars if c["similarity"] >= 0.45]

    seen, unique = set(), []
    for car in cars:
        tid = car["turbo_id"]
        if tid not in seen:
            seen.add(tid)
            unique.append(car)
    cars = unique

    if not cars:
        raise HTTPException(status_code=404, detail="Filtrlərə uyğun elan tapılmadı")

    for car in cars:
        base          = score_car(car, cars, priority, car["similarity"])
        h             = car.pop("_hybrid", 0)
        car["_score"] = round(base * 0.85 + h * 0.15, 4)

    cars.sort(key=lambda x: x["_score"], reverse=True)
    top = cars[:10]

    for i, car in enumerate(top):
        car["rank"]  = i + 1
        car["score"] = min(round(car["_score"] * 100), 100)
        del car["_score"]

    whys    = parser.explain([slim(c) for c in top], req.prompt, priority, color)
    why_map = {w["turbo_id"]: w["why"] for w in whys}
    for car in top:
        car["why"] = why_map.get(car["turbo_id"], "")

    return {
        "prompt_parsed":   parsed,
        "total_found":     len(cars),
        "recommendations": top,
    }