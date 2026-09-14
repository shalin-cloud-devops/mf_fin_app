import json
import logging
import os

from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ingestion-worker")

# Config comes from the environment so the same image runs anywhere.
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka-svc:9092")
TOPIC = "fund.updated"

# In production this data is fetched from an upstream holdings feed.
# In the sandbox there is no upstream, so we seed two funds that share
# some stocks (AAPL, MSFT) so the overlap math later has something to find.
SAMPLE_FUNDS = [
    {
        "fund_id": 1,
        "fund_name": "Bluechip Growth Fund",
        "holdings": [
            {"stock_symbol": "AAPL", "weight": 12.5},
            {"stock_symbol": "MSFT", "weight": 10.0},
            {"stock_symbol": "AMZN", "weight": 8.0},
        ],
    },
    {
        "fund_id": 2,
        "fund_name": "Tech Leaders Fund",
        "holdings": [
            {"stock_symbol": "MSFT", "weight": 15.0},
            {"stock_symbol": "GOOGL", "weight": 11.0},
            {"stock_symbol": "AAPL", "weight": 9.0},
        ],
    },
]


def build_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        key_serializer=lambda k: str(k).encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )


def publish_funds(producer, funds):
    for fund in funds:
        producer.send(TOPIC, key=fund["fund_id"], value=fund)
        log.info("Published fund.updated for fund_id=%s", fund["fund_id"])
    producer.flush()


def main():
    log.info("Connecting to Kafka at %s", KAFKA_BROKER)
    producer = build_producer()
    publish_funds(producer, SAMPLE_FUNDS)
    log.info("All events flushed. Ingestion worker done.")
    producer.close()


if __name__ == "__main__":
    main()
