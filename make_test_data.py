"""Generate ABC Apparels test workbook: 3 months, 3 lines, 3 styles.

Deliberate leaks are baked in so the report has real things to catch:
  - Line L2 is the problem line: low efficiency, poor fabric use, behind schedule,
    high rework, ships late.
  - Style S300 (hoodie) is quoted as profitable but actually loses margin on L2.
  - September utility cost jumps ~28% plant-wide while output stays flat.

Run:  python3 make_test_data.py   ->  writes abc_data.xlsx
"""
import random
from datetime import date
import pandas as pd

random.seed(7)  # deterministic: same workbook every run

MONTHS = ["2025-07", "2025-08", "2025-09"]
LINES = ["L1", "L2", "L3"]

# style -> economics
STYLES = {
    "S100": dict(name="Tshirt", price=250, qcost=190, sam=8,  fab_std=1.6, rm_rate=60),
    "S200": dict(name="Polo",   price=450, qcost=350, sam=14, fab_std=2.0, rm_rate=90),
    "S300": dict(name="Hoodie", price=900, qcost=680, sam=22, fab_std=2.8, rm_rate=130),
}
CUSTOMER = {"S100": "Metro Retail", "S200": "Urban Co", "S300": "NorthWear"}

# line efficiency (standard minutes produced / minutes paid). L2 is bad.
LINE_EFF = {"L1": 0.80, "L3": 0.78, "L2": 0.55}
# planned-vs-actual output ratio. L2 falls behind.
LINE_OUTPUT = {"L1": 1.00, "L3": 0.99, "L2": 0.80}
# fabric utilization (consumed / issued). L2 wastes, worst on the heavy hoodie.
def fabric_util(line, style):
    if line == "L2":
        return 0.74 if style == "S300" else 0.84
    return 0.91
# defect & reject rates. L2 worse.
def quality_rate(line):
    return (0.09, 0.03) if line == "L2" else (0.035, 0.01)  # defect, reject

WAGE_PER_HR = 120
MACHINE_PER_HR = 50
PLANNED_QTY = 1000

orders, production, material, labour, quality, utilities, dispatch, accounts = (
    [], [], [], [], [], [], [], [])

for m in MONTHS:
    y, mo = int(m[:4]), int(m[5:7])
    util_mult = 1.28 if m == "2025-09" else 1.0  # Sep electricity leak
    for line in LINES:
        line_output_qty = 0
        for style, s in STYLES.items():
            oid = f"O-{m}-{line}-{style}"
            planned = PLANNED_QTY
            actual = round(planned * LINE_OUTPUT[line] * random.uniform(0.98, 1.02))
            line_output_qty += actual

            # labour: paid minutes = standard minutes / efficiency
            std_min = actual * s["sam"]
            paid_min = std_min / LINE_EFF[line]
            labour_hours = round(paid_min / 60, 1)
            ot_hours = round(labour_hours * (0.18 if line == "L2" else 0.06), 1)
            labour_cost = round(labour_hours * WAGE_PER_HR + ot_hours * WAGE_PER_HR * 0.5)
            machine_hours = round(labour_hours * 0.9, 1)

            # material
            consumed = round(actual * s["fab_std"] * random.uniform(1.0, 1.03), 1)
            issued = round(consumed / fabric_util(line, style), 1)
            rm_cost = round(issued * s["rm_rate"])
            rm_standard_cost = round(actual * s["fab_std"] * s["rm_rate"])

            # quality
            d_rate, r_rate = quality_rate(line)
            defect = round(actual * d_rate)
            reject = round(actual * r_rate)
            rework_hours = round(defect * 0.15, 1)

            # dispatch: L2 ships late
            due = date(y, mo, 25)
            disp_day = 28 if line == "L2" else 23
            dispatched = actual - reject

            # accounts: NorthWear (S300) pays slow / partial
            invoiced = dispatched * s["price"]
            if style == "S300":
                received = round(invoiced * 0.6)
                recv_date = ""  # still outstanding
            else:
                received = invoiced
                recv_date = date(y, mo, 28).isoformat()

            orders.append(dict(order_id=oid, customer=CUSTOMER[style], style=style,
                               line=line, qty=planned, order_date=date(y, mo, 1).isoformat(),
                               due_date=due.isoformat(), quoted_price=s["price"],
                               quoted_cost=s["qcost"]))
            production.append(dict(month=m, line=line, style=style, planned_qty=planned,
                                   actual_qty=actual, machine_hours=machine_hours,
                                   labour_hours=labour_hours))
            material.append(dict(month=m, line=line, style=style, fabric_issued=issued,
                                 fabric_consumed=consumed, rm_cost=rm_cost,
                                 rm_standard_cost=rm_standard_cost))
            labour.append(dict(month=m, line=line, style=style, workers=25,
                               hours_paid=labour_hours, overtime_hours=ot_hours,
                               labour_cost=labour_cost, sam_per_piece=s["sam"]))
            quality.append(dict(month=m, line=line, style=style, inspected_qty=actual,
                                defect_qty=defect, rework_hours=rework_hours,
                                reject_qty=reject))
            dispatch.append(dict(order_id=oid, dispatch_date=date(y, mo, disp_day).isoformat(),
                                 dispatched_qty=dispatched))
            accounts.append(dict(order_id=oid, invoiced_amount=invoiced,
                                 received_amount=received, received_date=recv_date))

        # utilities per line/month, allocated-ready; cost rises in Sep
        base_kwh = round(line_output_qty * 0.9)
        utilities.append(dict(month=m, line=line, kwh=round(base_kwh * util_mult),
                              utility_cost=round(base_kwh * util_mult * 9),
                              output_qty=line_output_qty))

sheets = dict(orders=orders, production=production, material=material, labour=labour,
              quality=quality, utilities=utilities, dispatch=dispatch, accounts=accounts)

with pd.ExcelWriter("abc_data.xlsx", engine="openpyxl") as xl:
    for name, rows in sheets.items():
        pd.DataFrame(rows).to_excel(xl, sheet_name=name, index=False)

print("wrote abc_data.xlsx:", {k: len(v) for k, v in sheets.items()})
