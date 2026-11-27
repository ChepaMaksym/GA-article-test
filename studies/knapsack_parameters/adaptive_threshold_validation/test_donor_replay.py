import unittest

from .donor_replay import paired_donor
from .study import input_case


class DonorChecks(unittest.TestCase):
    def test_registered_mechanisms(self):
        problem,bank,_=input_case("n00100-UC-s000",196999)
        for cfg in ((90,"A4",15,2,1,145,None),(100,"A5",15,2,1,70,None),
                    (100,"A5",15,2,1,70,5)):
            saved={}
            def retain(kind,log,check,digest):
                saved[kind]=(log["initial_masks"],log["rng_initial"],digest,check["new_calls"],
                             [g["parameters_before"] for g in log["generations"]])
            paired_donor(problem,bank,cfg,retain,total=402)
            d,r=saved["donor"],saved["receiver"]
            self.assertEqual(d[0],r[0])
            self.assertEqual(d[2:],r[2:])
            self.assertEqual(r[3],387)
            self.assertTrue(all(d[1][k]!=r[1][k] for k in r[1]))
