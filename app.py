"""Streamlit frontend. Upload a factory workbook, it is saved to the database and
a money-ranked leakage report is shown. Past uploads can be reloaded without
re-uploading. Reuses ingest/metrics/rules/report unchanged in logic.

Local:   streamlit run app.py        (uses local SQLite)
Cloud:   set DATABASE_URL in Streamlit secrets (Neon Postgres) to persist data.
"""
import os
import tempfile
import streamlit as st
from db import get_engine, is_cloud, list_batches
from ingest import save
from report import build, ACTION, AREA_LABEL

st.set_page_config(page_title="Garment Leakage Analyzer", layout="wide")
st.title("Garment Leakage Analyzer")
st.caption("Upload a factory workbook. Get a money-ranked list of where the "
           "factory is leaking money, and what to do about each one.")

engine = get_engine()
st.sidebar.write("**Storage:** " + ("Postgres (saved)" if is_cloud()
                                     else "local SQLite (this machine only)"))

if os.path.exists("abc_data.xlsx"):
    with open("abc_data.xlsx", "rb") as fp:
        st.sidebar.download_button("Download sample workbook", fp,
                                   file_name="sample_workbook.xlsx")

client = st.text_input("Client / factory name", value="ABC Apparels")

# --- upload a new workbook (saved) ---
st.markdown("**Required sheets:** orders, production, material, labour, quality, "
            "utilities, dispatch, accounts.")
up = st.file_uploader("Factory workbook (.xlsx)", type="xlsx")

chosen = None  # (client, batch) to report on
if up is not None:
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fp:
        fp.write(up.getbuffer())
        xp = fp.name
    try:
        batch_id, rej, counts = save(xp, client, engine)
    except SystemExit as e:
        st.error(str(e))
        st.stop()
    finally:
        os.unlink(xp)
    st.success(f"Saved {sum(counts.values())} rows for {client}.")
    if not rej.empty:
        st.warning("Some rows were rejected (fix in the source file):")
        st.dataframe(rej[["_sheet", "_reason"]], hide_index=True)
    chosen = (client, batch_id)

# --- or reload a past upload ---
batches = list_batches(engine)
if batches:
    labels = {f"{c}  |  {b[:8]} ({n} rows)": (c, b) for c, b, n in batches}
    pick = st.selectbox("Or reload a saved upload", ["(current)"] + list(labels))
    if pick != "(current)":
        chosen = labels[pick]

if chosen is None:
    st.info("Upload a workbook, or pick a saved one above, to see the report.")
    st.stop()

# --- report ---
client_sel, batch_sel = chosen
money, roll, total = build(engine, client_sel, batch_sel)

st.header(f"{client_sel}: leakage report")
st.metric("Quantifiable money leak this period", f"Rs {total:,.0f}")

st.subheader("Top money leaks (ranked by impact)")
if money.empty:
    st.success("No quantifiable money leak found in this data.")
else:
    m = money.copy()
    m["action"] = m["area"].map(ACTION)
    m["money_impact"] = m["money_impact"].map(lambda v: f"Rs {v:,.0f}")
    st.dataframe(m[["money_impact", "scope", "area", "detail", "action"]],
                 hide_index=True, use_container_width=True)

st.subheader("Causes behind the leaks (below benchmark)")
if roll.empty:
    st.info("No benchmark breaches flagged.")
else:
    r = roll.copy()
    r["area"] = r["area"].map(lambda a: AREA_LABEL.get(a, a))
    r["action"] = roll["area"].map(ACTION)
    r["worst"] = r["worst"].map(lambda v: f"{v:.2f}")
    r = r.rename(columns={"line": "Line", "area": "Area", "worst": "Worst value",
                          "flags": "Times flagged", "action": "Action"})
    st.dataframe(r[["Line", "Area", "Worst value", "Times flagged", "Action"]],
                 hide_index=True, use_container_width=True)
