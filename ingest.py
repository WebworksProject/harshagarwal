"""Load a client workbook into a local SQLite DB, validating as we go.

Bad rows are not silently dropped: they are written to a `_rejected` table and
printed, because bad data is itself a finding the factory should see.

Run:  python3 ingest.py abc_data.xlsx   ->  writes abc.db
"""
import sqlite3
import sys
import pandas as pd

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


def validate(name, df):
    """Return (clean_df, rejected_df). A row is rejected if a required field is
    missing/blank or a numeric field is not a number."""
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


def main(path, db="abc.db"):
    book = pd.read_excel(path, sheet_name=None)  # all sheets
    con = sqlite3.connect(db)
    all_rejects = []
    for name in REQUIRED:
        if name not in book:
            raise SystemExit(f"workbook missing sheet: {name}")
        clean, rejected = validate(name, book[name])
        clean.to_sql(name, con, if_exists="replace", index=False)
        if not rejected.empty:
            all_rejects.append(rejected)
        print(f"[{name}] loaded {len(clean)}, rejected {len(rejected)}")

    rej = pd.concat(all_rejects) if all_rejects else pd.DataFrame(columns=["_sheet", "_reason"])
    rej.to_sql("_rejected", con, if_exists="replace", index=False)
    con.close()
    if not rej.empty:
        print("\nREJECTED ROWS (fix these in the source data):")
        print(rej[["_sheet", "_reason"]].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "abc_data.xlsx")
