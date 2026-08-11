import random
import unittest
import numpy as np

from candidates.EU26_20.old.agawer_core import (
    AdaptiveState, average_minimum_distance, offspring_counts,
    replacement_mutation, repository_radius, roulette_probabilities,
    should_stop, update_adaptation, variable_single_point_crossover,
)


class TestOldCore(unittest.TestCase):
    def test_initial_offspring_counts(self):
        self.assertEqual(offspring_counts(10, 0.9, 0.4), (10, 4))

    def test_adaptation_sequence(self):
        s = AdaptiveState()
        observed = [(s.pc, s.pm)]
        for i in range(1, 21):
            s = update_adaptation(s, False)
            if i % 5 == 0:
                observed.append((s.pc, s.pm))
        self.assertEqual(observed, [(0.9,0.4),(0.6,0.6),(0.3,0.8),(0.0,1.0),(0.0,1.0)])
        self.assertTrue(should_stop(s, 20, 0.95))

    def test_improvement_resets_controller(self):
        s = AdaptiveState()
        for _ in range(8):
            s = update_adaptation(s, False)
        self.assertEqual((s.pc, s.pm), (0.6, 0.6))
        s = update_adaptation(s, True)
        self.assertEqual(s, AdaptiveState())

    def test_variable_crossover_preserves_uniqueness(self):
        y1, y2 = variable_single_point_crossover([1,2,3,4], [3,4,5,6], random.Random(7))
        self.assertEqual(len(y1), len(set(y1)))
        self.assertEqual(len(y2), len(set(y2)))
        self.assertTrue(set(y1) <= {1,2,3,4,5,6})
        self.assertTrue(set(y2) <= {1,2,3,4,5,6})

    def test_mutation_replaces_with_unseen_feature(self):
        x = [1,2,3]
        y = replacement_mutation(x, range(1,8), random.Random(1))
        self.assertEqual(len(y), 3)
        self.assertEqual(len(set(y)), 3)
        self.assertEqual(len(set(x) ^ set(y)), 2)

    def test_roulette(self):
        p = roulette_probabilities([1,2,7])
        np.testing.assert_allclose(p, [0.1,0.2,0.7])

    def test_paper_distance_example(self):
        # Paper example S1={(1,2),(3,4)}, S2={(2,1),(5,6),(7,8)} gives ~2.71.
        s1 = np.array([[1,2],[3,4]])
        s2 = np.array([[2,1],[5,6],[7,8]])
        self.assertAlmostEqual(average_minimum_distance(s1, s2), 2.7106, places=3)

    def test_radius_beta_two(self):
        pop = [np.array([[0.0]]), np.array([[10.0]]), np.array([[4.0]])]
        self.assertAlmostEqual(repository_radius(pop, 2), 5.0)


if __name__ == '__main__':
    unittest.main()
