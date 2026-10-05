"""Compute KPIs from the loaded DB. One tidy table at (month, line, style) grain.

Each row carries the metrics that drive the report:
  fabric_util, line_efficiency, output_attainment, defect_rate, reject_rate,
  realized_cost_pp, quoted_margin_pp, realized_margin_pp, margin_gap_total,
  utility_cost_per_unit.

Used by rules.py and report.py. Run standalone to eyeball the numbers:
  python3 metrics.py
"""
import pandas as pd
from sqlalchemy import text
from db import get_engine, latest_batch

MACHINE_PER_HR = 50   # machine running cost
OVERHEAD_PP = 40      # fixed factory overhead per garment


def compute(engine=None, client="ABC Apparels", batch=None):
    engine = engine or get_engine()
    batch = batch or latest_batch(engine, client)
    if batch is None:
        raise SystemExit(f"no saved data for client '{client}'")

    def read(name):
        q = text(f"select * from {name} where client_name=:c and batch_id=:b")
        df = pd.read_sql(q, engine, params={"c": client, "b": batch})
        return df.drop(columns=["client_name", "batch_id"])  # constant within a batch

    t = {n: read(n) for n in
         ("orders", "production", "material", "labour", "quality", "utilities")}

    # base grain = production (month, line, style)
    df = t["production"].merge(
        t["material"], on=["month", "line", "style"]).merge(
        t["labour"], on=["month", "line", "style"]).merge(
        t["quality"], on=["month", "line", "style"])

    # order economics (quoted price/cost per piece) by line+style
    o = t["orders"][["line", "style", "quoted_price", "quoted_cost"]].drop_duplicates()
    df = df.merge(o, on=["line", "style"])

    # allocate monthly line utilities to styles by output share
    u = t["utilities"].rename(columns={"utility_cost": "u_cost", "output_qty": "u_out"})
    df = df.merge(u[["month", "line", "u_cost", "u_out"]], on=["month", "line"])
    df["util_alloc"] = df["u_cost"] * df["actual_qty"] / df["u_out"]
    df["utility_cost_per_unit"] = df["u_cost"] / df["u_out"]

    # --- efficiency & flow ---
    df["fabric_util"] = df["fabric_consumed"] / df["fabric_issued"]
    df["line_efficiency"] = (df["sam_per_piece"] * df["actual_qty"]) / (df["hours_paid"] * 60)
    df["output_attainment"] = df["actual_qty"] / df["planned_qty"]
    df["defect_rate"] = df["defect_qty"] / df["inspected_qty"]
    df["reject_rate"] = df["reject_qty"] / df["inspected_qty"]

    # --- realized cost & margin (the money question) ---
    df["realized_cost_total"] = (df["rm_cost"] + df["labour_cost"]
                                 + df["machine_hours"] * MACHINE_PER_HR
                                 + df["util_alloc"] + OVERHEAD_PP * df["actual_qty"])
    df["realized_cost_pp"] = df["realized_cost_total"] / df["actual_qty"]
    df["quoted_margin_pp"] = df["quoted_price"] - df["quoted_cost"]
    df["realized_margin_pp"] = df["quoted_price"] - df["realized_cost_pp"]
    # money lost vs what was quoted, over the actual quantity made
    df["margin_gap_total"] = (df["realized_margin_pp"] - df["quoted_margin_pp"]) * df["actual_qty"]

    keep = ["month", "line", "style", "planned_qty", "actual_qty",
            "fabric_util", "line_efficiency", "output_attainment",
            "defect_rate", "reject_rate", "utility_cost_per_unit",
            "quoted_margin_pp", "realized_margin_pp", "realized_cost_pp",
            "margin_gap_total"]
    return df[keep].round(3)


if __name__ == "__main__":
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(compute().to_string(index=False))
