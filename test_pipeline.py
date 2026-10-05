"""Smallest guard that fails if the pipeline logic breaks. Builds a fresh local DB
from the test workbook, then checks the baked leaks still surface.

Run:  python3 test_pipeline.py
"""
import os
from sqlalchemy import create_engine
from ingest import save
from metrics import compute
from rules import findings

CLIENT = "ABC Apparels"


def test():
    if os.path.exists("test.db"):
        os.remove("test.db")
    engine = create_engine("sqlite:///test.db")
    batch, rej, _ = save("abc_data.xlsx", CLIENT, engine)
    assert rej.empty, "clean test data should have no rejects"

    m = compute(engine, CLIENT, batch)
    assert m[m["line"] == "L2"]["line_efficiency"].max() < 0.65, "L2 efficiency leak gone"
    assert m[(m["line"] == "L2") & (m["style"] == "S300")]["fabric_util"].max() < 0.80, \
        "L2/S300 fabric leak gone"

    f = findings(engine, CLIENT, batch)
    money = f[f.money_impact.notna()]
    assert not money.empty, "no money leak found"
    top = money.iloc[0]
    assert top["scope"] == "L2/S100" and top["area"] == "Margin", \
        f"top leak changed: {top['scope']} {top['area']}"
    assert any((money.area == "Electricity") & money.scope.str.contains("2025-09")), \
        "Sep electricity leak not caught"
    os.remove("test.db")
    print("OK: pipeline catches the baked leaks. top leak =",
          top["scope"], f"Rs {int(top['money_impact']):,}")


if __name__ == "__main__":
    test()
