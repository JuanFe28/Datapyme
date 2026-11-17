from app.core.jinja_filters import format_cop_filter, format_qty_filter


def test_cop_preserves_cents_without_rounding_to_a_different_total():
    assert format_cop_filter("1234.57") == "$ 1.234,57"
    assert format_cop_filter("100.00") == "$ 100"


def test_weighted_stock_does_not_lose_quantity_when_displayed():
    assert format_qty_filter("1.250", "kg") == "1,25 kg"
    assert format_qty_filter("0.125", "kg") == "0,125 kg"
