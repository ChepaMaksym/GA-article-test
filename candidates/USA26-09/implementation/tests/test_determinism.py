from usa2609.core import make_uniform_instance
from usa2609.optimizer import generate_initial_population, run_hybrid, run_old


def test_paired_initial_population_and_determinism():
    instance = make_uniform_instance()
    pop1 = generate_initial_population(instance, 1001)
    pop2 = generate_initial_population(instance, 1001)
    assert pop1 == pop2
    a = run_old(instance, 1001, 180, 1.83)
    b = run_old(instance, 1001, 180, 1.83)
    assert a.canonical() == b.canonical()
    h = run_hybrid(instance, 1001, 180, 1.83)
    assert a.initial_population_digest == h.initial_population_digest
