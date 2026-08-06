from pact.negotiation.concession import (
    ConcessionParams,
    generate_offer_sequence,
    offer_at_round,
    reservation_price_for_buyer,
)


def test_round_one_is_opening_offer():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=5)
    assert offer_at_round(params, 1) == 12000


def test_final_round_reaches_reservation():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=5)
    assert offer_at_round(params, 5) == 9000


def test_offer_never_crosses_reservation_past_final_round():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=5)
    assert offer_at_round(params, 10) == 9000


def test_offers_monotonically_concede_toward_reservation():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=6)
    sequence = generate_offer_sequence(params)
    for a, b in zip(sequence, sequence[1:], strict=False):
        assert b <= a


def test_reproducibility_identical_inputs_identical_sequence():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=6, beta=2.0)
    first = generate_offer_sequence(params)
    second = generate_offer_sequence(params)
    assert first == second


def test_reservation_price_is_lower_of_budget_and_market_floor():
    assert reservation_price_for_buyer(budget_ceiling=10000, market_floor=8500) == 8500
    assert reservation_price_for_buyer(budget_ceiling=7000, market_floor=8500) == 7000


def test_single_round_negotiation_starts_at_reservation():
    params = ConcessionParams(opening=12000, reservation=9000, total_rounds=1)
    assert generate_offer_sequence(params) == [9000]


def test_invalid_total_rounds_rejected():
    import pytest

    with pytest.raises(ValueError):
        ConcessionParams(opening=100, reservation=50, total_rounds=0)


def test_invalid_beta_rejected():
    import pytest

    with pytest.raises(ValueError):
        ConcessionParams(opening=100, reservation=50, total_rounds=5, beta=0)
