import pytest
from app.services.split_service import calculate_splits


@pytest.mark.parametrize(
    "amount,ids,expected",
    [
        (10000, [1, 2], [5000, 5000]),
        (10000, [1, 2, 3], [3334, 3333, 3333]),
        (1, [3, 1, 2], [1, 0, 0]),
        (999, [1], [999]),
    ],
)
def test_equal(amount, ids, expected):
    assert (
        list(calculate_splits(amount, "equal", [{"user_id": i} for i in ids]).values()) == expected
    )


def test_exact():
    assert calculate_splits(
        100, "exact", [{"user_id": 1, "amount_cents": 30}, {"user_id": 2, "amount_cents": 70}]
    ) == {1: 30, 2: 70}


@pytest.mark.parametrize(
    "mode,parts",
    [
        ("exact", [{"user_id": 1, "amount_cents": 99}]),
        ("percent", [{"user_id": 1, "percentage": "99"}]),
        ("equal", [{"user_id": 1}, {"user_id": 1}]),
        ("equal", []),
    ],
)
def test_invalid(mode, parts):
    with pytest.raises(ValueError):
        calculate_splits(100, mode, parts)


def test_percent_rounding():
    assert calculate_splits(
        101,
        "percent",
        [
            {"user_id": 1, "percentage": "50"},
            {"user_id": 2, "percentage": "25"},
            {"user_id": 3, "percentage": "25"},
        ],
    ) == {1: 51, 2: 25, 3: 25}


def test_single_payer_independent():
    assert calculate_splits(9000, "single", [{"user_id": 2}]) == {2: 9000}
