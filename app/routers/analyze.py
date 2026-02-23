from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.scraper import scrape
from app.services.db import save_listing, get_similar
from app.services.ai import PromptParser

router = APIRouter()
parser = PromptParser()


class Req(BaseModel):
    url: str


@router.post("/analyze")
def analyze(req: Req):
    if "turbo.az" not in req.url:
        raise HTTPException(status_code=400, detail="Yalnız turbo.az linkləri qəbul edilir")

    d = scrape(req.url)
    save_listing(d)
    similar = get_similar(d.get("brand"), d.get("model"), d.get("year"))
    ai = parser.analyze(d, similar)

    return {
        "listing": {
            "turbo_id": d.get("turbo_id"),
            "brand": d.get("brand"),
            "model": d.get("model"),
            "year": d.get("year"),
            "price_azn": d.get("price_azn"),
            "mileage_km": d.get("mileage_km"),
            "city": d.get("city"),
            "url": d.get("url"),
        },
        "similar_count": len(similar),
        "ai": ai
    }
