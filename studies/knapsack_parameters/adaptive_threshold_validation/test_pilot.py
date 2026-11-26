"""CI acceptance tests for the original cycle, control events and independent replay."""
import unittest
from copy import deepcopy
from fractions import Fraction

from ..parameter_dynamics import engine as original
from . import analysis, design, engine, verification
from .study import input_case, thresholds


class PilotTests(unittest.TestCase):
    def test_design(self):
        self.assertEqual(len(set(design.cases())),3780)
        self.assertEqual(len(set(design.contrasts())),20)
        self.assertEqual(design.threshold_control("A2","absolute",145),"NOT_APPLICABLE")
        self.assertEqual(design.threshold_control("A7","absolute",145),"IDENTICAL")
        for pc in design.BASES:
            self.assertEqual(len(set(design.static_grid(pc,"A7"))),24)
            self.assertEqual(len(set(design.static_grid(pc,"A6"))),20)
        with self.assertRaises(ValueError):
            analysis.select_screen([])
        self.assertEqual(analysis.bca([0]*10)["status"],"DEGENERATE")
        self.assertEqual(analysis.bca(list(range(10)))["confidence"],.9975)

    def test_threshold_boundaries(self):
        for mu,h,q in ((30,145,145),(15,70,70),(15,140,140),(15,145,154),(15,280,280)):
            p=dict(engine.default_parameters(),target_mu=mu)
            count=elapsed=0
            while elapsed<q:
                elapsed+=mu-1
                r=engine.update_parameters(p,count,False,mu-1,Fraction(0),8,p,h)
                count=r["failed_queries_after"]
                self.assertEqual(r["event"],"STAGNATION" if elapsed==q else "NO_CHANGE")
            self.assertEqual(count,0)
        r=engine.update_parameters(p,140,True,14,Fraction(0),8,p,145)
        self.assertEqual((r["event"],r["failed_queries_after"]),("SUCCESS",0))

    def test_legacy_exact(self):
        problem,bank,_=input_case("n00100-UC-s000",196999)
        def streams():
            return engine.make_rngs(196999,bank["task_index"],0)
        for profile in (0,31):
            args=problem,bank["masks"],bank["scores"],profile
            historical=original.run_search(*args,streams(),budget=301)
            log=engine.run_search(*args,streams(),301,initial=engine.default_parameters())
            verification.verify_log(log,initial=engine.default_parameters(),threshold=145)
            for key in ("initial_masks","rng_initial","candidates","generations","rng_final","summary"):
                self.assertEqual(log[key],historical[key],key)

    def test_donor_and_partial(self):
        problem,bank,_=input_case("n00100-SC-s005",196999)
        p=dict(engine.default_parameters(),p_c=1.,target_mu=15)
        def run(seed,schedule=None):
            return engine.run_search(problem,bank["masks"][:15],bank["scores"][:15],31,
                   engine.make_rngs(seed,bank["task_index"],0),302,initial=p,threshold=70,
                   dynamic_h=5,schedule=schedule)
        donor=run(197000)
        schedule=[g["parameters_before"] for g in donor["generations"]]
        log=run(196999,schedule)
        self.assertEqual([g["parameters_before"] for g in log["generations"]],schedule)
        verification.verify_log(log,initial=p,threshold=70,dynamic_h=5,schedule=schedule)
        corrupted=deepcopy(log)
        corrupted["candidates"][-1]["profit"]+=1
        with self.assertRaises(ValueError):
            verification.verify_log(corrupted,initial=p,threshold=70,dynamic_h=5,schedule=schedule)
        self.assertEqual(log["generations"][0]["parameters_before"]["p_c"],1.)
        self.assertLessEqual(log["generations"][1]["parameters_before"]["p_c"],.9)

    def test_targets(self):
        log={"initial_scores":[dict(feasible=True,profit=93)],
             "candidates":[dict(call=1,record_profit=93),dict(call=2,record_profit=95)]}
        self.assertEqual(thresholds(log,100),{93:1,95:3,99:None})
