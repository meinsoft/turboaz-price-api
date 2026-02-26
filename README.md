<div align="center">

# TurboAZ Price Analyzer

**AI-powered car search and price analysis for Azerbaijan market**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)

*Type what you want in plain text. Get smart car recommendations. Know if a price is fair.*

</div>

---

## What is this?

Searching for a car on Turbo.az is hard — filters are complex, comparing prices to the market takes time, and knowing whether a listing is actually a good deal requires experience.

This API removes all of that friction. You write what you want in plain Azerbaijani or Russian, and the system figures out the rest.

```
"bmw 520 istiyirem ucuz, biraz vurgu ola biler"
                    |
                    v
        AI understands the request
        (brand, price, priority, crashed_ok...)
                    |
                    v
        Turbo.az scraped live
        (always fresh — cars sell fast)
                    |
                    v
        Each listing ranked by semantic similarity
        + market-normalized price/mileage/year score
                    |
                    v
        AI explains each result in natural Azerbaijani
                    |
                    v
        Top results returned with score + why
```

---

## API Endpoints

### `POST /api/recommend`

Send a plain text request. Get the best matching cars.

Understands 20+ parameters from natural language — brand, model, price range, mileage, year, color, region, fuel type, gearbox, body type, drive type, number of owners, extras (leather, sunroof, parking sensors...), loan, barter, dealer/private, and more.

**Request:**
```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bmw 520 istiyirem ucuz vurugu ola biler"}'
```

**Response:**
```json
{
  "prompt_parsed": {
    "brand": "BMW",
    "model": "520",
    "crashed_ok": true,
    "priority": "price"
  },
  "total_found": 36,
  "recommendations": [
    {
      "brand": "BMW",
      "model": "520",
      "year": 2014,
      "price_azn": 29500.0,
      "mileage_km": 127000,
      "city": "Bakı",
      "similarity": 0.81,
      "rank": 1,
      "score": 90,
      "why": "Puluna dəyər, bu qiymətə belə tapılmaz"
    }
  ]
}
```

**Example prompts:**
```
bmw 520 ucuz vurugu ola biler
mercedes e class 2015-2018 arasi avtomat
toyota 15000 azne qeder az gedish
honda civic dilerden deri salon lyuklu
7 yerli suv tam ötürücü 2020 uzeri
```

---

### `POST /api/analyze`

Send a Turbo.az listing URL. Get a full market price analysis.

Scrapes the listing, finds similar cars on the market, calculates the average price, and returns an honest verdict — cheap, fair, or overpriced — with specific reasons.

**Request:**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://turbo.az/autos/10030006-bmw-ix"}'
```

**Response:**
```json
{
  "listing": {
    "brand": "BMW",
    "model": "iX",
    "year": 2025,
    "price_azn": 167600.0,
    "mileage_km": 0,
    "city": "Bakı"
  },
  "similar_count": 12,
  "ai": {
    "verdict": "Normaldır",
    "score": 60,
    "price_diff_percent": 1.2,
    "summary": "2025-ci il BMW iX, 0 km. Oxşar elanlarla müqayisədə qiymət normaldır.",
    "pros": ["Qiymət bazar ortalamasına uyğundur", "0 km — yenidir"],
    "cons": ["2025 modeli üçün bazar çox məhduddur"]
  }
}
```

---

## How It Works

```
+-------------------------------------------------------+
|                        User                           |
|          "bmw 520 ucuz vurgu ola biler"               |
+------------------------+------------------------------+
                         |
                         | HTTP POST
                         v
+-------------------------------------------------------+
|                  FastAPI  :8000                       |
|                                                       |
|    /api/recommend              /api/analyze           |
|          |                           |                |
|    parse prompt              scrape listing page      |
|    (Groq LLaMA)                      |                |
|          |                     save to DB             |
|    scrape live listings              |                |
|          |                     find similar cars      |
|    batch embed + rank                |                |
|    (similarity + market score) AI verdict             |
|          |                           |                |
|    AI explain in Azerbaijani         |                |
|          +-----------------+--------+                 |
|                            v                         |
|                      JSON response                    |
+------------------------+------------------------------+
                         |
              +----------+----------+
              |                     |
              v                     v
        +----------+         +----------+
        |PostgreSQL|         |   Groq   |
        |  :5433   |         | LLaMA 70B|
        +----------+         +----------+
```

---

## Ranking Logic

Results are not sorted by price or date. Each car gets a score based on:

- **Semantic similarity** — how well the listing matches the request (via multilingual embeddings)
- **Market-normalized score** — price, mileage, and year compared to all other results in the same pool
- **Intent score** — if the user cares about price, mileage, or year specifically, that factor is weighted higher

This means a 2012 car with 200,000 km won't outrank a 2018 car just because it's cheaper — unless the user explicitly asks for the cheapest option.

---

## Tech Stack

| Tool | What it does |
|---|---|
| **FastAPI** | REST API framework |
| **PostgreSQL + pgvector** | Stores listings and price history |
| **Groq + LLaMA 3.3 70B** | Parses prompts, explains results in Azerbaijani, analyzes prices |
| **sentence-transformers** | Multilingual embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) |
| **BeautifulSoup4** | Scrapes Turbo.az listing pages live |
| **Docker Compose** | Runs everything with one command |

---

## Project Structure

```
turboaz-price-api/
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- routers/
|   |   |-- analyze.py       # POST /api/analyze
|   |   +-- recommend.py     # POST /api/recommend
|   |-- services/
|   |   |-- scraper.py       # live Turbo.az scraper
|   |   |-- embedder.py      # sentence-transformers wrapper
|   |   |-- db.py            # PostgreSQL queries
|   |   +-- ai.py            # PromptParser + explain + analyze
|   +-- bot/
|       +-- main.py          # Telegram bot (optional)
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
+-- .env
```

---

## Database

```
listings        ->  car data saved on each scrape for price tracking
price_history   ->  price changes over time
tasks           ->  async job tracking
```

> Search results are always live-scraped — never served from DB cache. DB is used only for price trend analysis in `/api/analyze`.

---

## Setup

### You need
- Docker + Docker Compose
- Groq API key → https://console.groq.com (free)

### Steps

**1. Clone**
```bash
git clone https://github.com/meinsoft/turboaz-price-api.git
cd turboaz-price-api
```

**2. Create `.env`**
```bash
cat > .env << 'EOF'
DATABASE_URL=postgresql://admin:secret@postgres:5432/cardb
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
EOF
```

**3. Start**
```bash
docker-compose up -d --build
```

**4. Open Swagger UI**
```
http://localhost:8000/docs
```

---

## Performance

| Step | Time |
|---|---|
| AI prompt parse (Groq) | ~4 sec |
| Live scrape (2–5 pages) | ~5 sec |
| Batch embedding + similarity | ~2 sec |
| AI explain (Groq) | ~3 sec |
| **Total** | **~11–14 sec** |

The embedding model is preloaded inside the Docker image at build time — no download on startup or per-request.

---

## Roadmap

- [ ] Telegram bot integration
- [ ] Redis cache for repeated queries
- [ ] Async parallel scraping
- [ ] Price trend charts
- [ ] Monthly market reports

---

<div align="center">

Built for Azerbaijan &nbsp;|&nbsp; Powered by LLaMA 3.3 &nbsp;|&nbsp; Data from Turbo.az

</div>
