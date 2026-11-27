import unittest

from .confirmatory import compare
from .design import BASES, METRICS, CONTROLS, TOTAL


class ConfirmatoryTests(unittest.TestCase):
    def setUp(self):
        self.roles = {(p,m,k):"common" for p in BASES for m in METRICS
                      for k in ("candidate", *CONTROLS)}
        self.clusters = {i:[3*i+j for j in range(3)] for i in range(10)}
        self.rows = [dict(task=t,seed=s,configuration="common",verified=True,total=TOTAL,
                          optimum=100,best=93,hits={"93":TOTAL,"95":None,"99":None})
                     for t in range(30) for s in range(10)]

    def run_analysis(self):
        return compare(self.rows,self.roles,self.clusters,range(10))

    def test_identity_and_inapplicable(self):
        self.roles[90,"gap","same_mechanism_H145"] = None
        results = self.run_analysis()
        self.assertEqual(len(results),20)
        self.assertEqual(sum(r["status"]=="IDENTICAL" for r in results),19)
        self.assertEqual(sum(r["status"]=="NOT_APPLICABLE" for r in results),1)

    def test_last_attainment_and_nonattainment(self):
        self.roles[100,"t93","same_mechanism_H145"] = "historical"
        self.rows += [dict(r,configuration="historical",best=90,
                           hits={"93":None,"95":None,"99":None}) for r in self.rows]
        result = self.run_analysis()[-1]
        self.assertEqual(result["candidate_misses93"],0)
        self.assertEqual(result["control_misses93"],300)
        self.assertEqual(result["effect"],0)
        self.assertFalse(result["supported"])

    def test_missing_and_duplicate(self):
        self.rows.pop()
        with self.assertRaises(ValueError):
            self.run_analysis()
        self.rows.append(self.rows[0])
        with self.assertRaises(ValueError):
            self.run_analysis()
