"""Streamlit frontend: upload a factory workbook, get the leakage report in the
browser. Reuses ingest/metrics/rules/report unchanged.

Local:   streamlit run app.py
Deploy:  push to GitHub, point Streamlit Community Cloud at this file.
"""
import os
import tempfile
import streamlit as st
from ingest import main as ingest
from report import build, ACTION, AREA_LABEL

st.set_page_config(page_title="Garment Leakage Analyzer", layout="wide")
st.title("Garment Leakage Analyzer")
st.caption("Upload a factory workbook. Get a money-ranked list of where the "
           "factory is leaking money, and what to do about each one.")

# let a new user grab the template / sample to see the format
if os.path.exists("abc_data.xlsx"):
    with open("abc_data.xlsx", "rb") as fp:
        st.download_button("Download sample workbook (ABC test data)", fp,
                           file_name="sample_workbook.xlsx")

st.markdown("**Required sheets:** orders, production, material, labour, quality, "
            "utilities, dispatch, accounts.")

up = st.file_uploader("Factory workbook (.xlsx)", type="xlsx")
if not up:
    st.stop()

with tempfile.TemporaryDirectory() as d:
    xp, db = os.path.join(d, "in.xlsx"), os.path.join(d, "client.db")
    with open(xp, "wb") as fp:
        fp.write(up.getbuffer())
    try:
        ingest(xp, db)
        money, roll, total = build(db)
    except SystemExit as e:        # ingest raises SystemExit on bad structure
        st.error(str(e))
        st.stop()

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
