"""Tiny FastAPI service that proves Postgres + Redis connectivity from a container."""

import os

import psycopg
import redis
from fastapi import FastAPI

app = FastAPI(title="docker-on-web demo")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db")
def db():
    with psycopg.connect(DATABASE_URL) as conn:
        version = conn.execute("select version()").fetchone()[0]
    return {"postgres": version}


@app.get("/cache")
def cache():
    r = redis.Redis.from_url(REDIS_URL)
    hits = r.incr("hits")
    return {"redis_hits": hits}
