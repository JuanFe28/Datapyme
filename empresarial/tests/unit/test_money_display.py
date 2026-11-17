from app.core.jinja_filters import format_cop_filter


def test_cop_preserves_cents_without_rounding_to_a_different_total():
    assert format_cop_filter("1234.57") == "$ 1.234,57"
    assert format_cop_filter("100.00") == "$ 100"
