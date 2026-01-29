from app.time_format import format_fraction


def test_format_fraction_under_hour() -> None:
    assert format_fraction(72, 768) == "01:12/12:48"


def test_format_fraction_over_hour() -> None:
    assert format_fraction(3723, 6940) == "1:02:03/1:55:40"
