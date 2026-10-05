"""Assemble the client report: money-ranked leaks, the causes behind them, the
healthy areas, and a concrete action per leak. Prints to console and writes
report.html (no PDF dependency yet).

Run:  python3 report.py
"""
import pandas as pd
from rules import findings

# one concrete action per area
ACTION = {
    "Margin": "Style loses money at current cost. Re-quote it, or fix the cost drivers below (efficiency / fabric / quality on that line).",
    "Electricity": "Utility cost per unit rising while output is flat. Audit the tariff slab, idle machines left running, and peak-hour load.",
    "line_efficiency": "Low operator efficiency. Run a time study, check machine layout and WIP feeding on the line.",
    "fabric_util": "Fabric wasted in cutting. Re-check marker efficiency and fabric spreading for this style.",
    "output_attainment": "Line missing planned output. Investigate downtime, absenteeism, and line balancing.",
    "defect_rate": "High defect rate. Add inline QC and root-cause the top defect.",
    "reject_rate": "High reject rate. Same root-cause work; rejects are pure lost material + labour.",
}
AREA_LABEL = {"line_efficiency": "Line efficiency", "fabric_util": "Fabric use",
              "output_attainment": "Output vs plan", "defect_rate": "Defects",
              "reject_rate": "Rejects"}


def build(db="abc.db"):
    f = findings(db)
    money = f[f["money_impact"].notna()].copy()
    causes = f[f["money_impact"].isna()].copy()

    # roll causes up: (scope-line, area) -> worst value, how many times flagged
    causes["line"] = causes["scope"].str.split("/").str[0]
    roll = (causes.groupby(["line", "area"])
            .agg(flags=("status", "size"), worst=("detail", lambda s: s.astype(float).min()
                 if causes.loc[s.index, "area"].iloc[0] in ("defect_rate", "reject_rate")
                 else s.astype(float).min()))
            .reset_index().sort_values("flags", ascending=False))

    total = int(money["money_impact"].sum())
    return money, roll, total


def to_text(money, roll, total):
    L = ["ABC APPARELS: LEAKAGE REPORT", "=" * 40, ""]
    L.append(f"Quantifiable money leak this period: approx Rs {total:,}")
    L.append("")
    L.append("TOP MONEY LEAKS (ranked by impact)")
    L.append("-" * 40)
    for _, r in money.iterrows():
        L.append(f"  Rs {int(r['money_impact']):>8,}  |  {r['scope']:<14}  {r['area']}")
        L.append(f"             {r['detail']}")
        L.append(f"             ACTION: {ACTION.get(r['area'], '')}")
        L.append("")
    L.append("CAUSES BEHIND THE LEAKS (below benchmark)")
    L.append("-" * 40)
    for _, r in roll.iterrows():
        label = AREA_LABEL.get(r["area"], r["area"])
        L.append(f"  Line {r['line']}  {label}: worst {r['worst']:.2f}, flagged {int(r['flags'])}x")
        L.append(f"             ACTION: {ACTION.get(r['area'], '')}")
    return "\n".join(L)


def to_html(money, roll, total, path="report.html"):
    rows_m = "".join(
        f"<tr><td class=m>Rs {int(r.money_impact):,}</td><td>{r.scope}</td>"
        f"<td>{r.area}</td><td>{r.detail}</td><td>{ACTION.get(r.area,'')}</td></tr>"
        for r in money.itertuples())
    rows_c = "".join(
        f"<tr><td>Line {r.line}</td><td>{AREA_LABEL.get(r.area, r.area)}</td>"
        f"<td>worst {r.worst:.2f}, {int(r.flags)}x</td><td>{ACTION.get(r.area,'')}</td></tr>"
        for r in roll.itertuples())
    html = f"""<!doctype html><meta charset=utf-8>
<title>ABC Apparels - Leakage Report</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px;color:#1a1a1a}}
 h1{{margin:0}} .sub{{color:#666}}
 .big{{font-size:22px;font-weight:700;margin:18px 0;color:#b00}}
 table{{border-collapse:collapse;width:100%;margin:12px 0 28px}}
 th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
 th{{background:#f4f4f4}} td.m{{font-weight:700;white-space:nowrap}}
</style>
<h1>ABC Apparels</h1><div class=sub>Leakage report</div>
<div class=big>Quantifiable money leak this period: approx Rs {total:,}</div>
<h3>Top money leaks (ranked)</h3>
<table><tr><th>Impact</th><th>Where</th><th>Area</th><th>Detail</th><th>Action</th></tr>{rows_m}</table>
<h3>Causes behind the leaks</h3>
<table><tr><th>Line</th><th>Area</th><th>Severity</th><th>Action</th></tr>{rows_c}</table>
"""
    with open(path, "w") as fp:
        fp.write(html)
    return path


if __name__ == "__main__":
    money, roll, total = build()
    print(to_text(money, roll, total))
    print("\nwrote", to_html(money, roll, total))
