import numpy as np
import pytest
from usa2609.optimizer import Roulette, apply_move, lambda_controls, round_half_up, update_lambda


def test_old_roulette_formula_and_reward():
    r = Roulette()
    assert np.allclose(r.probabilities(), [0.25] * 4)
    r.reward(2, True)
    assert tuple(r.weights) == (100, 100, 101, 100)
    r.reward(2, False)
    assert tuple(r.weights) == (100, 100, 101, 100)


def test_lambda_controls_and_updates():
    assert round_half_up(2.5) == 3
    p, c, offspring = lambda_controls(4.0, 20)
    assert (p, c, offspring) == (0.2, 0.25, 4)
    assert update_lambda(4.0, True, 20) == pytest.approx(4 / 1.5)
    assert update_lambda(20.0, False, 20, reset=True) == 1.0
    assert update_lambda(20.0, False, 20, reset=False) == 20.0


def test_moves_preserve_permutation():
    order = tuple(range(1, 20))
    for move in range(4):
        out = apply_move(order, move, np.random.default_rng(10 + move))
        assert sorted(out) == list(order)
