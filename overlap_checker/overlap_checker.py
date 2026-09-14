import os
import json
import logging

from flask import Flask, request, jsonify
import psycopg2
import redis

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("overlap-engine")

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ["DB_PASSWORD"]

VALKEY_HOST = os.environ["VALKEY_HOST"]        # e.g. valkey-svc
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))

app = Flask(__name__)
cache = redis.Redis(host=VALKEY_HOST, port=VALKEY_PORT, decode_responses=True)


def get_holdings(fund_id):
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                            user=DB_USER, password=DB_PASSWORD)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stock_symbol FROM holdings WHERE fund_id = %s", (fund_id,))
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.get("/overlap")
def overlap():
    fund_a = request.args.get("fund_a")
    fund_b = request.args.get("fund_b")
    if not fund_a or not fund_b:
        return jsonify(error="fund_a and fund_b are required"), 400

    cache_key = f"overlap:{fund_a}:{fund_b}"

    cached = cache.get(cache_key)
    if cached:
        log.info("cache hit for %s", cache_key)
        return jsonify(json.loads(cached))

    log.info("cache miss for %s, computing", cache_key)
    a = get_holdings(fund_a)
    b = get_holdings(fund_b)
    common = sorted(a & b)

    result = {
        "fund_a": fund_a,
        "fund_b": fund_b,
        "overlap_count": len(common),
        "overlap_tickers": common,
    }
    cache.set(cache_key, json.dumps(result), ex=CACHE_TTL)
    return jsonify(result)
