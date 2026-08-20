from usa2609.experiment import run_campaign, scientific_digest


def test_worker_invariance_1_2():
    seeds = range(1001, 1004)
    one = run_campaign(seeds, budget=180, workers=1)
    two = run_campaign(seeds, budget=180, workers=2)
    assert scientific_digest(one) == scientific_digest(two)
