from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ai import PromptParser
from app.services.scraper import scrape_listings, BRAND_IDS

router = APIRouter()
parser = PromptParser()


class Req(BaseModel):
    prompt: str


@router.post("/recommend")
def recommend(req: Req):
    parsed = parser.parse(req.prompt)

    params = {}
    if parsed.get("brand"):
        bid = BRAND_IDS.get(parsed["brand"])
        if bid:
            params["brand_id"] = bid
    if parsed.get("price_max"):
        params["price_max"] = parsed["price_max"]
    if parsed.get("price_min"):
        params["price_min"] = parsed["price_min"]
    if parsed.get("year_min"):
        params["year_min"] = parsed["year_min"]
    if parsed.get("crashed_ok"):
        params["crashed"] = True

    arr = scrape_listings(params, max_pages=1)
    if not arr:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")

    ranked = parser.rank(arr[:10], req.prompt)

    m = {x["turbo_id"]: x for x in arr}
    result = []
    for r in ranked:
        tid = r.get("turbo_id")
        if tid in m:
            item = m[tid]
            item["rank"] = r.get("rank")
            item["score"] = r.get("score")
            item["why"] = r.get("why")
            result.append(item)

    return {"prompt_parsed": parsed, "total_found": len(arr), "recommendations": result}
