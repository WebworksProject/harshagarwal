"""Smallest guard that fails if the pipeline logic breaks. Assumes abc.db is
loaded (run make_test_data.py + ingest.py first).

Run:  python3 test_pipeline.py
"""
from metrics import compute
from rules import findings


def test():
    m = compute()
    # the baked leaks must still be visible
    l2 = m[(m.line == "L2")]
    assert l2["line_efficiency"].max() < 0.65, "L2 efficiency leak vanished"
    assert m[(m.line == "L2") & (m.style == "S300")]["fabric_util"].max() < 0.80, \
        "L2/S300 fabric leak vanished"

    f = findings()
    money = f[f.money_impact.notna()]
    assert not money.empty, "no money leak found"
    top = money.iloc[0]
    assert top["scope"] == "L2/S100" and top["area"] == "Margin", \
        f"top leak changed: {top['scope']} {top['area']}"
    assert any((money.area == "Electricity") & (money.scope.str.contains("2025-09"))), \
        "Sep electricity leak not caught"
    print("OK: pipeline catches the baked leaks. top leak =",
          top["scope"], f"Rs {int(top['money_impact']):,}")


if __name__ == "__main__":
    test()
