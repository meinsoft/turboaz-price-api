from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def embed(text):
    m = get_model()
    vec = m.encode(text, normalize_embeddings=True)
    return vec.tolist()


def build_text(d):
    parts = []
    if d.get("brand") and d.get("model"):
        parts.append(f"{d['brand']} {d['model']}")
    if d.get("year"):
        parts.append(f"{d['year']} il")
    if d.get("body_type"):
        parts.append(d["body_type"])
    if d.get("fuel_type"):
        parts.append(d["fuel_type"])
    if d.get("transmission"):
        parts.append(d["transmission"])
    if d.get("description"):
        parts.append(d["description"])
    if d.get("extras") and isinstance(d["extras"], list):
        parts.append(" ".join(d["extras"]))

    body = (d.get("body_type") or "").lower()
    seats = d.get("seats") or 0
    if "sedan" in body or "universal" in body or seats >= 5:
        parts.append("ailə avtomobili rahat geniş")
    if "suv" in body or "crossover" in body or seats >= 7:
        parts.append("ailə SUV 7 yerli geniş")
    if (d.get("price_azn") or 0) < 15000:
        parts.append("ucuz əlverişli")
    elif (d.get("price_azn") or 0) < 30000:
        parts.append("orta qiymət")

    return " ".join(parts)


def embed_listing(d):
    return embed(build_text(d))
