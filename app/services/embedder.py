from sentence_transformers import SentenceTransformer
import json
import math
import re
from pathlib import Path
from collections import Counter

_model = None
_filters = None

MODEL_NAME = "intfloat/multilingual-e5-small"

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def get_filters():
    global _filters
    if _filters is None:
        path = Path(__file__).parent / "turboaz_filters.json"
        with open(path, encoding="utf-8") as f:
            _filters = json.load(f)
    return _filters

def resolve(filter_key, id_or_name):
    if not id_or_name:
        return None
    f = get_filters()
    data = f.get(filter_key, {})
    val = str(id_or_name)
    if val in data:
        return data[val]
    for fid, name in data.items():
        if name.lower() == val.lower():
            return name
    return str(id_or_name)

def build_text(d):
    parts = []

    brand = d.get("brand") or resolve("q[make][]", d.get("make_id"))
    model = d.get("model") or resolve("q[model][]", d.get("model_id"))
    if brand and model:
        parts.append(f"{brand} {model}")
    elif brand:
        parts.append(brand)

    year = d.get("year")
    if year:
        parts.append(f"{year} il")

    body = d.get("body_type") or resolve("q[category][]", d.get("category_id"))
    if body:
        parts.append(body)

    fuel = d.get("fuel_type") or resolve("q[fuel_type][]", d.get("fuel_id"))
    if fuel:
        parts.append(fuel)

    trans = d.get("transmission") or resolve("q[transmission][]", d.get("trans_id"))
    if trans:
        parts.append(trans)

    gear = d.get("drive") or resolve("q[gear][]", d.get("gear_id"))
    if gear:
        parts.append(gear)

    color = d.get("color") or resolve("q[color][]", d.get("color_id"))
    if color:
        parts.append(f"{color} rəng")

    market = d.get("market") or resolve("q[market][]", d.get("market_id"))
    if market:
        parts.append(f"{market} bazarı")

    city = d.get("city") or resolve("q[region][]", d.get("region_id"))
    if city:
        parts.append(city)

    price = d.get("price_azn") or 0
    if price < 10000:   parts.append("çox ucuz büdcəyə uyğun")
    elif price < 20000: parts.append("ucuz əlverişli")
    elif price < 40000: parts.append("orta qiymət")
    elif price < 80000: parts.append("yuxarı qiymət")
    else:               parts.append("bahalı premium")

    km = d.get("mileage_km") or 0
    if km == 0:          parts.append("yeni sıfır km")
    elif km < 50000:     parts.append("az yürüşlü")
    elif km < 150000:    parts.append("orta yürüş")
    else:                parts.append("çox yürüşlü")

    seats = d.get("seats") or 0
    try:
        seats = int(seats)
        if seats >= 7:
            parts.append(f"{seats} yerli geniş ailə")
    except:
        pass

    cond = (d.get("condition") or "").lower()
    if "vuruğu yoxdur" in cond:
        parts.append("təmiz vuruğu yoxdur")
    elif "vuruğu var" in cond:
        parts.append("vuruğu var zədəli")
    if "rənglənməyib" in cond:
        parts.append("rənglənməyib orijinal")
    elif "rənglənib" in cond:
        parts.append("rənglənib")

    extras = d.get("extras")
    if extras and isinstance(extras, list):
        parts.extend(extras[:5])

    desc = d.get("description")
    if desc:
        parts.append(desc[:200])

    return " ".join(filter(None, parts))


def tokenize(text):
    return re.findall(r"[a-zA-Z0-9\u0400-\u04FF\u0080-\u024F]+", text.lower())


class BM25:
    """
    Robertson BM25 — keyword axtarışı üçün.
    k1 və b standart dəyərlərdir, araşdırmalarda ən yaxşı nəticəni verir.
    """
    k1 = 1.5
    b  = 0.75

    def __init__(self, docs):
        self.n = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.n, 1)
        self.doc_freqs = []
        self.idf = {}

        df = Counter()
        for d in docs:
            freq = Counter(d)
            self.doc_freqs.append(freq)
            for term in freq:
                df[term] += 1

        for term, count in df.items():
            self.idf[term] = math.log((self.n - count + 0.5) / (count + 0.5) + 1)

    def score(self, query_tokens, doc_idx):
        freq = self.doc_freqs[doc_idx]
        dl = sum(freq.values())
        result = 0.0
        for term in query_tokens:
            if term not in freq:
                continue
            tf = freq[term]
            idf = self.idf.get(term, 0)
            denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            result += idf * (tf * (self.k1 + 1)) / denom
        return result

    def scores(self, query_tokens):
        return [self.score(query_tokens, i) for i in range(self.n)]


def rrf(bm25_ranks, vec_ranks, k=60):
    """
    Reciprocal Rank Fusion — iki fərqli sıralamadan vahid skor yaradır.
    k=60 ədəbiyyatda standart dəyərdir.
    """
    combined = {}
    for rank, idx in enumerate(bm25_ranks):
        combined[idx] = combined.get(idx, 0) + 1 / (k + rank + 1)
    for rank, idx in enumerate(vec_ranks):
        combined[idx] = combined.get(idx, 0) + 1 / (k + rank + 1)
    return combined


def hybrid_rank(query, cars, vec_similarities):
    """
    BM25 + vector similarity-ni birləşdirir.

    Qaytarır: hər car üçün hybrid skor dict {idx: score}
    """
    query_tokens = tokenize(query)

    texts = [build_text(c) for c in cars]
    tokenized = [tokenize(t) for t in texts]

    bm25 = BM25(tokenized)
    bm25_raw = bm25.scores(query_tokens)

    bm25_ranks = sorted(range(len(cars)), key=lambda i: bm25_raw[i], reverse=True)
    vec_ranks  = sorted(range(len(cars)), key=lambda i: vec_similarities[i], reverse=True)

    return rrf(bm25_ranks, vec_ranks)


def embed_query(text):
    m = get_model()
    vec = m.encode(f"query: {text}", normalize_embeddings=True)
    return vec.tolist()

def embed_passage(text):
    m = get_model()
    vec = m.encode(f"passage: {text}", normalize_embeddings=True)
    return vec.tolist()

def embed(text):
    return embed_query(text)

def embed_listing(d):
    return embed_passage(build_text(d))