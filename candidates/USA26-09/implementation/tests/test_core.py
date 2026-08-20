import numpy as np
from usa2609.core import brute_force_split_minmax, make_uniform_instance, nearest_neighbor_order, split_minmax


def test_split_matches_bruteforce_small():
    instance = make_uniform_instance(7, 8, 3)
    order = tuple(range(1, 8))
    assert abs(split_minmax(order, instance) - brute_force_split_minmax(order, instance.distances, 3)) < 1e-12


def test_frozen_instance_and_nearest_neighbor_anchor():
    instance = make_uniform_instance()
    assert instance.n_nodes == 50
    value = split_minmax(nearest_neighbor_order(instance), instance)
    assert abs(value - 1.8288547696784496) < 1e-12
