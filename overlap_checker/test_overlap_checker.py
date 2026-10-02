import os
import json
from unittest.mock import patch, MagicMock

# overlap_checker reads these env vars at import time (os.environ["DB_HOST"] etc.),
# so they must exist before the module is imported or the import itself crashes.
# Dummy values are safe: no test ever opens a real DB or cache connection.
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("VALKEY_HOST", "localhost")

import overlap_checker  # noqa: E402  (must come after the env setup above)
from overlap_checker import app  # noqa: E402


def test_healthz_returns_200():
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_overlap_missing_param_returns_400():
    client = app.test_client()
    resp = client.get("/overlap?fund_a=1")  # fund_b missing on purpose
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("overlap_checker.get_holdings")
@patch("overlap_checker.cache")
def test_overlap_cache_hit_skips_db(mock_cache, mock_get_holdings):
    cached = {
        "fund_a": "1",
        "fund_b": "2",
        "overlap_count": 2,
        "overlap_tickers": ["AAPL", "MSFT"],
    }
    mock_cache.get.return_value = json.dumps(cached)  # a hit

    client = app.test_client()
    resp = client.get("/overlap?fund_a=1&fund_b=2")

    assert resp.status_code == 200
    assert resp.get_json() == cached
    mock_get_holdings.assert_not_called()  # DB is never touched on a cache hit


@patch("overlap_checker.get_holdings")
@patch("overlap_checker.cache")
def test_overlap_cache_miss_computes(mock_cache, mock_get_holdings):
    mock_cache.get.return_value = None  # a miss
    # The two funds share AAPL and MSFT.
    mock_get_holdings.side_effect = [
        {"AAPL", "MSFT", "GOOG"},
        {"AAPL", "MSFT", "TSLA"},
    ]

    client = app.test_client()
    resp = client.get("/overlap?fund_a=1&fund_b=2")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["overlap_count"] == 2
    assert body["overlap_tickers"] == ["AAPL", "MSFT"]  # sorted intersection
    mock_cache.set.assert_called_once()  # computed result is written back to cache


@patch("overlap_checker.psycopg2.connect")
def test_get_holdings_reads_symbols(mock_connect):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("AAPL",), ("MSFT",)]
    # get_holdings uses: with conn.cursor() as cur
    mock_connect.return_value.cursor.return_value.__enter__.return_value = mock_cursor

    result = overlap_checker.get_holdings("1")

    assert result == {"AAPL", "MSFT"}
