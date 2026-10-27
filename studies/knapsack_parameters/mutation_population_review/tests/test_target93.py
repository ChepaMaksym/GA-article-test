import unittest
from ..review import target_query
from ..targets93 import target_stats, validate_target_order


class Target93Tests(unittest.TestCase):
    def test_exact_integer_boundary_initial_and_last_query(self):
        self.assertEqual(target_query([{"q": 0, "profit": 93}], 100, 93), 0)
        events = [{"q": 0, "profit": 929}, {"q": 5000, "profit": 930}]
        self.assertEqual(target_query(events, 1000, 93), 5000)
        self.assertIsNone(target_query(events, 1000, 95))
        self.assertIsNone(target_query([{"q": 0, "profit": 93}], 101, 93))
        self.assertEqual(target_query([{"q": 0, "profit": 94}], 101, 93), 0)

    def test_targets_are_nested_and_nondetection_stays_none(self):
        self.assertEqual(validate_target_order([{"q": 0, "profit": 92}, {"q": 10, "profit": 95}], 100), [10,10,None])

    def test_family_weights_and_restricted_mean_preserve_failures(self):
        rows = [{"family":"a", "task":"a1", "optimum":100, "record_events":[{"q":0,"profit":93}]},
                {"family":"a", "task":"a2", "optimum":100, "record_events":[{"q":0,"profit":90},{"q":100,"profit":93}]},
                {"family":"b", "task":"b1", "optimum":100, "record_events":[{"q":0,"profit":90}]}]
        result = target_stats(rows, 93)
        self.assertEqual(result["attained"], 2)
        self.assertEqual(result["not_attained"], 1)
        self.assertEqual(result["restricted_mean_queries"], 2525)
        self.assertEqual(result["curve"][-1]["fraction"], .5)

    def test_success_at5000_and_failure_are_distinct(self):
        rows = [{"family":"a","task":"a1","optimum":100,"record_events":[{"q":0,"profit":90},{"q":5000,"profit":93}]},
                {"family":"a","task":"a1","optimum":100,"record_events":[{"q":0,"profit":90}]}]
        result = target_stats(rows,93)
        self.assertEqual(result["restricted_mean_queries"],5000)
        self.assertEqual(result["attained"],1)
        self.assertEqual(result["not_attained"],1)
