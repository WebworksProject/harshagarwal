"""Turn metrics into findings: Good / Watch / Leak, with money impact where it is
real, ranked so the biggest money problem is first.

Two kinds of finding:
  - MONEY leaks (a rupee number we can defend): margin lost vs quote, and the
    extra utility spend when cost-per-unit rises over the period.
  - CAUSE flags (efficiency, fabric, quality below benchmark): the WHY behind the
    money leaks. Status only, no invented rupee figure.

Run standalone to see findings:  python3 rules.py
"""
import pandas as pd
from metrics import compute

BENCH = pd.read_csv("benchmarks.csv").set_index("metric")


def status(metric, value):
    b = BENCH.loc[metric]
    if b["direction"] == "high":
        return "Good" if value >= b["good"] else "Watch" if value >= b["watch"] else "Leak"
    return "Good" if value <= b["good"] else "Watch" if value <= b["watch"] else "Leak"


def findings(db="abc.db"):
    m = compute(db)
    rows = []

    # --- MONEY: margin lost vs quote, per line+style (so one bad style is not
    # hidden by profitable ones on the same line) ---
    g = m.groupby(["line", "style"]).agg(
        margin_gap=("margin_gap_total", "sum"),
        rm_pp=("realized_margin_pp", "mean")).reset_index()
    for _, r in g.iterrows():
        if r["margin_gap"] < 0:
            rows.append(dict(scope=f"{r['line']}/{r['style']}", area="Margin",
                             detail=f"realized margin {r['rm_pp']:.0f}/pc below quote",
                             status="Leak", money_impact=round(-r["margin_gap"])))

    # --- MONEY: utility cost-per-unit rise vs the first month ---
    base_month = sorted(m["month"].unique())[0]
    base = m[m["month"] == base_month]["utility_cost_per_unit"].mean()
    for month, sub in m.groupby("month"):
        cur = sub["utility_cost_per_unit"].mean()
        if cur > base * 1.05:  # >5% rise
            extra = round((cur - base) * sub["actual_qty"].sum())
            rows.append(dict(scope=f"Plant {month}", area="Electricity",
                             detail=f"cost/unit {cur:.1f} vs {base:.1f} baseline",
                             status="Leak", money_impact=extra))

    # --- CAUSE flags: efficiency / fabric / quality below benchmark ---
    cause_metrics = ["line_efficiency", "fabric_util", "output_attainment",
                     "defect_rate", "reject_rate"]
    for _, r in m.iterrows():
        for met in cause_metrics:
            st = status(met, r[met])
            if st != "Good":
                rows.append(dict(scope=f"{r['line']}/{r['style']} {r['month']}",
                                 area=met, detail=f"{r[met]:.2f}",
                                 status=st, money_impact=None))

    f = pd.DataFrame(rows)
    # rank: money leaks first (desc), then cause flags (Leak before Watch)
    f["sort_money"] = f["money_impact"].fillna(-1)
    f["sort_sev"] = f["status"].map({"Leak": 1, "Watch": 0})
    return f.sort_values(["sort_money", "sort_sev"], ascending=False).drop(
        columns=["sort_money", "sort_sev"]).reset_index(drop=True)


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(findings().to_string(index=False))
