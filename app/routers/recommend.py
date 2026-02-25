from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ai import PromptParser
from app.services.scraper import scrape_listings, BRAND_IDS
from app.services.db import save_listing_card
from app.services.embedder import embed, embed_listing

import numpy as np

router = APIRouter()
parser = PromptParser()


class Req(BaseModel):
    prompt: str


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def combined_score(car, priority, similarity):
    km    = car.get("mileage_km") or 0
    price = car.get("price_azn") or 99999
    year  = car.get("year") or 2000

    if priority == "price":
        if price < 10000:   p = 1.0
        elif price < 15000: p = 0.8
        elif price < 20000: p = 0.6
        else:               p = 0.3
    elif priority == "mileage":
        if km < 50000:    p = 1.0
        elif km < 100000: p = 0.8
        elif km < 200000: p = 0.5
        else:             p = 0.2
    elif priority == "year":
        if year >= 2022:   p = 1.0
        elif year >= 2018: p = 0.8
        elif year >= 2014: p = 0.6
        else:              p = 0.3
    else:
        p = 0.5

    return round(similarity * 0.6 + p * 0.4, 4)


def slim(car):
    return {
        "turbo_id":   car.get("turbo_id"),
        "brand":      car.get("brand"),
        "model":      car.get("model"),
        "year":       car.get("year"),
        "price_azn":  car.get("price_azn"),
        "mileage_km": car.get("mileage_km"),
        "city":       car.get("city"),
    }


@router.post("/recommend")
def recommend(req: Req):
    parsed    = parser.parse(req.prompt)
    brand     = parsed.get("brand")
    price_max = parsed.get("price_max")
    year_min  = parsed.get("year_min")
    crashed   = parsed.get("crashed_ok")
    priority  = parsed.get("priority")

    params = {}
    if brand and BRAND_IDS.get(brand):
        params["brand_id"] = BRAND_IDS[brand]
    if price_max:
        params["price_max"] = price_max
    if year_min:
        params["year_min"] = year_min
    if crashed:
        params["crashed"] = True

    cars = scrape_listings(params, max_pages=2)
    if not cars:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")

    for car in cars:
        save_listing_card(car)

    from app.services.embedder import get_model, build_text
    m         = get_model()
    query_vec = m.encode(req.prompt, normalize_embeddings=True).tolist()
    texts     = [build_text(car) for car in cars]
    vecs      = m.encode(texts, normalize_embeddings=True, batch_size=32)

    for i, car in enumerate(cars):
        sim              = cosine(query_vec, vecs[i].tolist())
        car["similarity"]   = round(sim, 3)
        car["_rank_score"]  = combined_score(car, priority, sim)

    if year_min:
        by_year = [x for x in cars if (x.get("year") or 0) >= year_min]
        if by_year:
            cars = by_year

    by_km = [x for x in cars if (x.get("mileage_km") or 0) <= 250000]
    if by_km:
        cars = by_km

    if price_max:
        by_price = [x for x in cars if (x.get("price_azn") or 0) <= price_max]
        if by_price:
            cars = by_price

    if not brand:
        cars = [x for x in cars if x["similarity"] >= 0.55]

    if not brand:
        cars = [x for x in cars if x["similarity"] >= 0.55]

    seen, unique = set(), []
    for car in cars:
        if car["turbo_id"] not in seen:
            seen.add(car["turbo_id"])
            unique.append(car)
    cars = unique

    if not cars:
        raise HTTPException(status_code=404, detail="Filtrlərə uyğun elan tapılmadı")

    cars.sort(key=lambda x: x["_rank_score"], reverse=True)
    top5 = cars[:5]

    for i, car in enumerate(top5):
        car["rank"]  = i + 1
        car["score"] = min(round(car["_rank_score"] * 100), 100)
        del car["_rank_score"]

    whys    = parser.explain([slim(c) for c in top5], req.prompt, priority)
    why_map = {w["turbo_id"]: w["why"] for w in whys}
    for car in top5:
        car["why"] = why_map.get(car["turbo_id"], "")

    return {
        "prompt_parsed":   parsed,
        "total_found":     len(cars),
        "recommendations": top5
    }
