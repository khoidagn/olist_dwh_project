import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

APP_DIR = Path(__file__).resolve().parents[1]
CACHE_TTL = "12h"
_misses = {"count": 0}


def _config():
    return st.secrets["bigquery"]


@st.cache_resource
def get_client() -> bigquery.Client:
    cfg = _config()
    key_file = (APP_DIR / cfg["key_path"]).resolve()
    creds = service_account.Credentials.from_service_account_file(str(key_file))
    return bigquery.Client(credentials=creds, project=cfg["project"], location=cfg["location"])


def dataset_ref() -> str:
    cfg = _config()
    return f"{cfg['project']}.{cfg['dataset']}"


def table(name: str) -> str:
    return f"`{dataset_ref()}.{name}`"


def _param(name, type_, value):
    if isinstance(value, (list, tuple)):
        return bigquery.ArrayQueryParameter(name, type_, list(value))
    return bigquery.ScalarQueryParameter(name, type_, value)


def _job_config(params: tuple, use_bq_cache: bool) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(
        query_parameters=[_param(*p) for p in params],
        maximum_bytes_billed=2 * 1024**3,
        use_query_cache=use_bq_cache,
    )


def _run_one(client: bigquery.Client, sql: str, params: tuple, use_bq_cache: bool):
    rows = client.query_and_wait(sql, job_config=_job_config(params, use_bq_cache))
    frame = rows.to_dataframe(create_bqstorage_client=False)
    server_ms = None
    if rows.started and rows.ended:
        server_ms = (rows.ended - rows.started).total_seconds() * 1000
    scanned = rows.total_bytes_processed
    stats = {
        "bytes": scanned or 0,
        "bq_cache": use_bq_cache and scanned == 0,
        "server_ms": server_ms,
    }
    return frame, stats


@st.cache_data(ttl=CACHE_TTL, max_entries=300, show_spinner=False)
def run_query(sql: str, params: tuple = (), use_bq_cache: bool = True):
    _misses["count"] += 1
    return _run_one(get_client(), sql, params, use_bq_cache)


@st.cache_data(ttl=CACHE_TTL, max_entries=100, show_spinner=False)
def run_queries(batch: tuple, use_bq_cache: bool = True, parallel: bool = True):
    _misses["count"] += 1
    client = get_client()
    if not parallel:
        return {name: _run_one(client, sql, params, use_bq_cache) for name, sql, params in batch}
    with ThreadPoolExecutor(max_workers=len(batch)) as pool:
        futures = {
            name: pool.submit(_run_one, client, sql, params, use_bq_cache)
            for name, sql, params in batch
        }
        return {name: future.result() for name, future in futures.items()}


def perf_settings() -> dict:
    return {
        "use_bq_cache": st.session_state.get("perf_bq_cache", True),
        "parallel": st.session_state.get("perf_parallel", True),
    }


def _record(label: str, started: float, misses_before: int, stats: list) -> None:
    hit_streamlit = _misses["count"] == misses_before
    st.session_state.setdefault("perf_log", []).append(
        {
            "label": label,
            "queries": len(stats),
            "ms": (time.perf_counter() - started) * 1000,
            "source": "Streamlit cache"
            if hit_streamlit
            else ("BigQuery cache" if all(s["bq_cache"] for s in stats) else "BigQuery chạy mới"),
            "mb": 0.0 if hit_streamlit else sum(s["bytes"] for s in stats) / 1024**2,
        }
    )


def _fail(exc: Exception):
    st.error("Không truy vấn được BigQuery.")
    with st.expander("Chi tiết lỗi"):
        st.code(str(exc))
    st.stop()


def load(sql: str, params: tuple = (), label: str = "1 truy vấn") -> pd.DataFrame:
    settings = perf_settings()
    started, before = time.perf_counter(), _misses["count"]
    try:
        with st.spinner("Đang tải dữ liệu..."):
            frame, stats = run_query(sql, params, settings["use_bq_cache"])
    except Exception as exc:
        _fail(exc)
    _record(label, started, before, [stats])
    return frame


def load_many(batch: dict, label: str) -> dict:
    settings = perf_settings()
    items = tuple((name, sql, params) for name, (sql, params) in batch.items())
    started, before = time.perf_counter(), _misses["count"]
    try:
        with st.spinner("Đang tải dữ liệu..."):
            results = run_queries(items, settings["use_bq_cache"], settings["parallel"])
    except Exception as exc:
        _fail(exc)
    _record(label, started, before, [stats for _, stats in results.values()])
    return {name: frame for name, (frame, _) in results.items()}
