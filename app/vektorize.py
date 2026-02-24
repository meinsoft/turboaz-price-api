import sys
sys.path.append("/app")

from app.services.scraper import scrape_listings, BRAND_IDS
from app.services.db import save_listing_card, save_embedding
from app.services.embedder import embed_listing

brands = ["BMW", "Mercedes", "Toyota", "Kia", "Hyundai"]

for brand in brands:
    bid = BRAND_IDS.get(brand)
    if not bid:
        continue
    print(f"{brand} scrape edilir...")
    arr = scrape_listings({"brand_id": bid}, max_pages=2)
    for d in arr:
        lid = save_listing_card(d)
        vec = embed_listing(d)
        save_embedding(d["turbo_id"], vec)
        print(f"  {d['turbo_id']} — {d['brand']} {d['model']} ✓")

print("Bitti!")
