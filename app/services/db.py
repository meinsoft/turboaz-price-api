import psycopg2


def conn():
    return psycopg2.connect(
        dbname="cardb", user="admin",
        password="secret", host="postgres", port="5432"
    )


def save_listing(d):
    c = conn()
    cur = c.cursor()
    cur.execute("""
        INSERT INTO listings (
            turbo_id, brand, model, year, price_azn, mileage_km,
            city, url, color, body_type, is_new, condition, description
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (turbo_id) DO UPDATE SET
            price_azn = EXCLUDED.price_azn,
            is_active = true,
            last_seen_at = NOW()
        RETURNING id
    """, (
        d.get("turbo_id"), d.get("brand"), d.get("model"),
        d.get("year"), d.get("price_azn"), d.get("mileage_km"),
        d.get("city"), d.get("url"), d.get("color"),
        d.get("body_type"), d.get("is_new") == "Bəli",
        d.get("condition"), d.get("description"),
    ))
    lid = cur.fetchone()[0]
    if d.get("price_azn"):
        cur.execute(
            "INSERT INTO price_history (listing_id, price_azn) VALUES (%s,%s)",
            (lid, d.get("price_azn"))
        )
    c.commit()
    cur.close()
    c.close()
    return lid


def save_listing_card(d):
    c = conn()
    cur = c.cursor()
    cur.execute("""
        INSERT INTO listings (turbo_id, brand, model, year, price_azn, mileage_km, city, url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (turbo_id) DO UPDATE SET
            price_azn = EXCLUDED.price_azn,
            is_active = true,
            last_seen_at = NOW()
        RETURNING id
    """, (
        d.get("turbo_id"), d.get("brand"), d.get("model"),
        d.get("year"), d.get("price_azn"), d.get("mileage_km"),
        d.get("city"), d.get("url"),
    ))
    lid = cur.fetchone()[0]
    if d.get("price_azn"):
        cur.execute(
            "INSERT INTO price_history (listing_id, price_azn) VALUES (%s,%s)",
            (lid, d.get("price_azn"))
        )
    c.commit()
    cur.close()
    c.close()
    return lid


def get_similar(brand, model, year, limit=50):
    c = conn()
    cur = c.cursor()
    cur.execute("""
        SELECT turbo_id, brand, model, year, price_azn, mileage_km, city, url
        FROM listings
        WHERE brand = %s AND is_active = true
        AND year BETWEEN %s AND %s
        ORDER BY price_azn ASC
        LIMIT %s
    """, (brand, year - 2, year + 2, limit))
    rows = cur.fetchall()
    cur.close()
    c.close()
    arr = []
    for r in rows:
        arr.append({
            "turbo_id": r[0], "brand": r[1], "model": r[2],
            "year": r[3], "price_azn": float(r[4]) if r[4] else None,
            "mileage_km": r[5], "city": r[6], "url": r[7],
        })
    return arr
