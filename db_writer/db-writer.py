import os
import json
import logging
import time

from kafka import KafkaConsumer
import psycopg2

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("db-writer")

# --- Config, all from environment (your manifest supplies these) ---
KAFKA_BROKER = os.environ["KAFKA_BROKER"]      # e.g. kafka-svc:9092
TOPIC = os.environ.get("TOPIC", "fund.updated")
GROUP_ID = os.environ.get("GROUP_ID", "db-writer")

DB_HOST = os.environ["DB_HOST"]            # e.g. postgres-0.postgres-svc
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ["DB_PASSWORD"]


def connect_db():
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASSWORD,
            )
            conn.autocommit = False
            log.info("Connected to Postgres at %s:%s", DB_HOST, DB_PORT)
            return conn
        except psycopg2.OperationalError as e:
            log.warning("Postgres not ready (%s). Retrying in 3s...", e)
            time.sleep(3)


def write_fund(conn, event):
    fund_id = event["fund_id"]
    fund_name = event["fund_name"]
    holdings = event.get("holdings", [])

    with conn.cursor() as cur:
        # Upsert the fund (reprocessing the same event is safe)
        cur.execute(
            """
            INSERT INTO funds (fund_id, fund_name)
            VALUES (%s, %s)
            ON CONFLICT (fund_id) DO UPDATE SET fund_name = EXCLUDED.fund_name
            """,
            (fund_id, fund_name),
        )
        # Replace this fund's holdings with the new set
        cur.execute("DELETE FROM holdings WHERE fund_id = %s", (fund_id,))
        for h in holdings:
            cur.execute(
                "INSERT INTO holdings (fund_id, stock_symbol, weight) VALUES (%s, %s, %s)",
                (fund_id, h["stock_symbol"], h["weight"]),
            )


def main():
    conn = connect_db()
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=GROUP_ID,
        enable_auto_commit=False,       # we commit the offset ourselves
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    log.info("Listening on '%s' as group '%s'", TOPIC, GROUP_ID)

    for message in consumer:
        event = message.value
        try:
            write_fund(conn, event)
            conn.commit()               # 1. make the DB write durable first
            consumer.commit()           # 2. only then mark the message as done
            log.info("Wrote fund '%s' (%d holdings)",
                     event.get("fund_id"), len(event.get("holdings", [])))
        except Exception as e:
            conn.rollback()             # undo the half-written fund
            log.error("Write failed, offset left uncommitted: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
