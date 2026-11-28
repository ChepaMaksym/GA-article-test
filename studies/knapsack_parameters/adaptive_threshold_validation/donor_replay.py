"""Construct an independent donor schedule and replay its full parameter vectors."""
from hashlib import sha256
import json

from . import design, engine, verification
from .study import require


def evaluate(problem, bank, config, *, stream_group=0, schedule=None, total=design.TOTAL, on_solution=None):
    pc, role, mu, k, elites, threshold, dynamic = config
    require(role in ("A4","A5","fixed"), "Unexpected finalist mechanism")
    initial = dict(target_mu=mu,p_c=pc/100,p_m=.01,tournament_size=k,elite_count=elites)
    streams = engine.make_rngs(bank["search_seed"],bank["task_index"],stream_group)
    initial_states = {name:r.bit_generator.state for name,r in streams.items()}
    if stream_group == 0:
        require(initial_states == bank["rng_states"],"Receiver RNGs differ from paired bank")
    else:
        require(all(initial_states[n]!=bank["rng_states"][n] for n in streams),
                "Donor must use six distinct streams from the receiver")
    args = dict(initial=initial,threshold=threshold,dynamic_h=dynamic,schedule=schedule)
    log = engine.run_search(problem,bank["masks"][:mu],bank["scores"][:mu],
                            design.BITS.get(role,0),streams,total-mu,**args)
    if on_solution is not None:
        on_solution(log["summary"]["best_mask"])
    checked = verification.verify_log(log,**args)
    require(checked["verification_status"]=="VERIFIED" and checked["new_calls"]+mu==total,
            "Incomplete replay")
    if schedule is not None:
        require([g["parameters_before"] for g in log["generations"]]==schedule,
                "Receiver did not apply the complete donor schedule")
    return log,checked


def paired_donor(problem, bank, config, retain, *, total=design.TOTAL):
    """retain(kind, log, replay, schedule_hash) must persist evidence before returning."""
    donor,checked = evaluate(problem,bank,config,stream_group=1,total=total)
    schedule = [dict(g["parameters_before"]) for g in donor["generations"]]
    digest = sha256(json.dumps(schedule,separators=(",",":"),sort_keys=True).encode()).hexdigest()
    retain("donor",donor,checked,digest)
    del donor
    receiver,checked = evaluate(problem,bank,config,schedule=schedule,total=total)
    retain("receiver",receiver,checked,digest)
    return digest
