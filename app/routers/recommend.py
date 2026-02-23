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


@router.post("/recommend")
def recommend(req: Req):
    parsed = parser.parse(req.prompt)

    brand = parsed.get("brand")
    model = parsed.get("model")
    price_max = parsed.get("price_max")
    year_min = parsed.get("year_min")
    crashed_ok = parsed.get("crashed_ok")

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

    ranked = parser.rank(arr[:10], req.prompt, parsed.get("priority"))

    m = {x["turbo_id"]: x for x in arr}
    result = []
    added = set()
    for r in ranked:
        tid = r.get("turbo_id")
        if tid in m and tid not in added:
            item = m[tid]
            item["rank"] = r.get("rank")
            item["score"] = r.get("score")
            item["why"] = r.get("why")
            result.append(item)
            added.add(tid)

    return {"prompt_parsed": parsed, "total_found": len(arr), "recommendations": result}
