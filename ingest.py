"""Validate a client workbook and SAVE it to the database, tagged by client and
upload time so nothing is overwritten and past uploads can be reloaded.

Bad rows are not silently dropped: they go to `_rejected` and are returned/printed.

CLI:  python3 ingest.py abc_data.xlsx "ABC Apparels"
"""
import sys
from datetime import datetime
import pandas as pd
from db import get_engine, SHEETS

# required columns per sheet, and which of them must be numeric
REQUIRED = {
    "orders":     (["order_id", "style", "line", "qty", "quoted_price", "quoted_cost"],
                   ["qty", "quoted_price", "quoted_cost"]),
    "production": (["month", "line", "style", "planned_qty", "actual_qty",
                    "machine_hours", "labour_hours"],
                   ["planned_qty", "actual_qty", "machine_hours", "labour_hours"]),
    "material":   (["month", "line", "style", "fabric_issued", "fabric_consumed",
                    "rm_cost", "rm_standard_cost"],
                   ["fabric_issued", "fabric_consumed", "rm_cost", "rm_standard_cost"]),
    "labour":     (["month", "line", "style", "hours_paid", "labour_cost", "sam_per_piece"],
                   ["hours_paid", "overtime_hours", "labour_cost", "sam_per_piece"]),
    "quality":    (["month", "line", "style", "inspected_qty", "defect_qty", "reject_qty"],
                   ["inspected_qty", "defect_qty", "rework_hours", "reject_qty"]),
    "utilities":  (["month", "line", "kwh", "utility_cost", "output_qty"],
                   ["kwh", "utility_cost", "output_qty"]),
    "dispatch":   (["order_id", "dispatch_date", "dispatched_qty"], ["dispatched_qty"]),
    "accounts":   (["order_id", "invoiced_amount", "received_amount"],
                   ["invoiced_amount", "received_amount"]),
}
assert set(REQUIRED) == set(SHEETS)


def validate(name, df):
    cols, numeric = REQUIRED[name]
    missing_cols = [c for c in cols if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"[{name}] missing columns: {missing_cols}")
    reason = pd.Series("", index=df.index)
    for c in cols:
        blank = df[c].isna() | (df[c].astype(str).str.strip() == "")
        reason[blank & (reason == "")] = f"missing {c}"
    for c in numeric:
        bad = pd.to_numeric(df[c], errors="coerce").isna() & (reason == "")
        reason[bad] = f"non-numeric {c}"
    rejected = df[reason != ""].copy()
    if not rejected.empty:
        rejected.insert(0, "_reason", reason[reason != ""])
        rejected.insert(0, "_sheet", name)
    return df[reason == ""].copy(), rejected


def save(path, client, engine=None):
    """Load workbook -> validate -> append to DB tagged (client, batch_id).
    Returns (batch_id, rejected_df, loaded_counts)."""
    engine = engine or get_engine()
    book = pd.read_excel(path, sheet_name=None)
    batch_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    rejects, counts = [], {}
    for name in REQUIRED:
        if name not in book:
            raise SystemExit(f"workbook missing sheet: {name}")
        clean, rejected = validate(name, book[name])
        clean.insert(0, "client_name", client)
        clean.insert(1, "batch_id", batch_id)
        clean.to_sql(name, engine, if_exists="append", index=False)
        counts[name] = len(clean)
        if not rejected.empty:
            rejected.insert(0, "client_name", client)
            rejected.insert(0, "batch_id", batch_id)
            rejects.append(rejected)
    rej = pd.concat(rejects) if rejects else pd.DataFrame()
    if not rej.empty:
        rej.to_sql("_rejected", engine, if_exists="append", index=False)
    return batch_id, rej, counts


def main(path, client="ABC Apparels"):
    batch_id, rej, counts = save(path, client)
    print(f"saved batch {batch_id} for {client}: {counts}")
    if not rej.empty:
        print("\nREJECTED ROWS (fix in source):")
        print(rej[["_sheet", "_reason"]].to_string(index=False))
    return batch_id


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "abc_data.xlsx",
         sys.argv[2] if len(sys.argv) > 2 else "ABC Apparels")
