"""One place that decides where data lives.

- If DATABASE_URL is set (env var, or Streamlit secret) -> that Postgres (Neon).
- Else -> a local SQLite file, so your Mac works offline with no setup.

Also small helpers to list/pick saved uploads (batches).
"""
import os
from sqlalchemy import create_engine, text

SHEETS = ("orders", "production", "material", "labour", "quality",
          "utilities", "dispatch", "accounts")


def _url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets["DATABASE_URL"]
        except Exception:
            url = None
    return url


def get_engine():
    url = _url()
    if url:
        url = url.replace("postgres://", "postgresql://", 1)  # Neon sometimes gives postgres://
        return create_engine(url, pool_pre_ping=True)
    return create_engine("sqlite:///abc.db")


def is_cloud():
    return bool(_url())


def list_batches(engine):
    """[(client_name, batch_id, rows)] newest first, or [] if nothing saved yet."""
    try:
        import pandas as pd
        q = text("select client_name, batch_id, count(*) as rows from production "
                 "group by client_name, batch_id order by batch_id desc")
        return list(pd.read_sql(q, engine).itertuples(index=False, name=None))
    except Exception:
        return []


def latest_batch(engine, client):
    try:
        import pandas as pd
        q = text("select max(batch_id) as b from production where client_name=:c")
        b = pd.read_sql(q, engine, params={"c": client}).iloc[0]["b"]
        return b
    except Exception:
        return None
