<div align="center">

# TurboAZ Price Analyzer

**AI-powered car price analysis for Azerbaijan market**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)

*Type what you want in plain text. Get smart car recommendations. Know if a price is fair.*

</div>

---

## What is this?

A REST API that understands natural language car requests in Azerbaijani or Russian, scrapes **live** listings from Turbo.az, ranks them using semantic embeddings, and uses AI to explain each result.

```
User types:  "bmw 520 istiyirem ucuz, biraz vurgu ola biler"
                              |
                              v
                   AI parses the request
                              |
                              v
                   Turbo.az scraped live
                              |
                              v
              Each listing embedded + similarity scored
                              |
                              v
                   AI explains top 5 results
                              |
                              v
                    Top 5 cars + why
```

> Data is always fresh — listings are scraped in real time on every request because Turbo.az cars sell fast.

---

## API Endpoints

### `POST /api/recommend`

Send a plain text request. Get the best matching cars.

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
      "city": "Baki",
      "similarity": 0.81,
      "rank": 1,
      "score": 90,
      "why": "29500 AZN ucuzdur, vurğu var"
    }
  ]
}
```

---

### `POST /api/analyze`

Send a Turbo.az link. Get a full price analysis.

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
    "city": "Baki"
  },
  "similar_count": 12,
  "ai": {
    "verdict": "Normaldır",
    "score": 50,
    "price_diff_percent": 0.0,
    "summary": "This car is priced fairly compared to the market.",
    "pros": ["Brand new", "0 km", "Electric engine"],
    "cons": ["High price range"]
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
|    parse prompt              scrape detail page       |
|    (Groq LLaMA)                      |                |
|          |                     save to DB             |
|    scrape live listings              |                |
|          |                     find similar cars      |
|    embed + similarity rank           |                |
|    (parallel, 8 threads)       AI verdict             |
|          |                           |                |
|    AI explain top 5                  |                |
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

## Tech Stack

| Tool | What it does |
|---|---|
| **FastAPI** | REST API framework |
| **PostgreSQL + pgvector** | Stores listings and price history |
| **Groq + LLaMA 3.3 70B** | Parses prompts, explains results, analyzes prices |
| **sentence-transformers** | Multilingual embeddings for semantic ranking |
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
|   |   +-- ai.py            # PromptParser + explain
|   +-- models/
|       |-- listing.py
|       +-- task.py
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

> Search results are always live-scraped. DB is used only for price trend analysis in `/api/analyze`.

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
| AI prompt parse (Groq) | ~3 sec |
| Live scrape (2 pages) | ~3 sec |
| Embedding + similarity (parallel) | ~2 sec |
| AI explain top 5 (Groq) | ~20 sec |
| **Total** | **~30 sec** |

Bottleneck is Groq API inference. Scraping and embedding are fast.

---

## Roadmap

- [ ] Celery background tasks
- [ ] Redis cache for repeated prompts
- [ ] Price trend charts
- [ ] Telegram bot interface
- [ ] Monthly market reports

---

<div align="center">

Built for Azerbaijan &nbsp;|&nbsp; Powered by LLaMA 3.3 &nbsp;|&nbsp; Data from Turbo.az

</div>
