from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import numpy as np
from .core import EffortLedger, conditional_mutation, hypervolume_contribution, oneminmax_objective, random_bits

@dataclass(frozen=True)
class OldRunResult:
    seed: int; n: int; offspring: int; complete: bool; evaluations: int; generations: int; archive_size: int
    first_hits: tuple[int | None, ...]; final_rate: float; lower_winners: int; higher_winners: int
    archive_digest: str; trace_digest: str; effort: EffortLedger
    def canonical(self) -> dict:
        return {"seed":self.seed,"n":self.n,"offspring":self.offspring,"complete":self.complete,"evaluations":self.evaluations,"generations":self.generations,"archive_size":self.archive_size,"first_hits":list(self.first_hits),"final_rate":format(self.final_rate,".17g"),"lower_winners":self.lower_winners,"higher_winners":self.higher_winners,"archive_digest":self.archive_digest,"trace_digest":self.trace_digest,"effort":self.effort.__dict__}

def update_two_rate(rate: float, winner_group: str, draw: float, n: int) -> float:
    if winner_group not in {"lower","higher"}: raise ValueError("winner_group must be lower or higher")
    if not 0.0 <= draw < 1.0: raise ValueError("draw must be in [0,1)")
    p=0.75 if winner_group=="lower" else 0.25
    return max(rate/2,0.5) if draw<p else min(rate*2,n/4)

def run_two_rate_old(seed:int,*,n:int=100,offspring:int=10,max_evaluations:int=2_000_000,record_trace:bool=False)->OldRunResult:
    if n<2 or offspring<2 or offspring%2 or max_evaluations<1+offspring: raise ValueError("invalid OLD configuration")
    rng=np.random.Generator(np.random.PCG64DXSM(int(seed))); initial=random_bits(rng,n); w=oneminmax_objective(initial,n)[0]; archive={w:initial}; first=[None]*(n+1); first[w]=1; evaluations=1; generations=0; rate=1.; low=high=draws=flipped=0; insertions=1; trace=sha256(f"seed={seed};initial={initial};weight={w}".encode())
    while len(archive)<n+1 and evaluations+offspring<=max_evaluations:
        weights=tuple(sorted(archive)); bits=tuple(archive[x] for x in weights); candidates=[]
        for i in range(offspring):
            parent=bits[int(rng.integers(0,len(bits)))]; group="lower" if i<offspring//2 else "higher"; p=rate/(2*n) if group=="lower" else 2*rate/n; child,l=conditional_mutation(parent,n,p,rng); draws+=1; flipped+=l; weight=oneminmax_objective(child,n)[0]; candidates.append((hypervolume_contribution(weights,weight,n),weight,group,child)); evaluations+=1; first[weight]=evaluations if first[weight] is None else first[weight]
        best=max(x[0] for x in candidates); winner=[x for x in candidates if x[0]==best][int(rng.integers(0,len([x for x in candidates if x[0]==best])))][2]; low+=winner=="lower"; high+=winner=="higher"; rate=update_two_rate(rate,winner,float(rng.random()),n)
        for _,weight,_,child in candidates:
            if weight not in archive: archive[weight]=child; insertions+=1
        generations+=1
        if record_trace: trace.update(f";g={generations};size={len(archive)};winner={winner};rate={rate:.17g}".encode())
    effort=EffortLedger(evaluations,generations*offspring,draws,flipped,insertions,generations); effort.validate(offspring); digest=sha256(",".join(map(str,sorted(archive))).encode()).hexdigest()
    return OldRunResult(int(seed),n,offspring,len(archive)==n+1,evaluations,generations,len(archive),tuple(first),rate,low,high,digest,trace.hexdigest(),effort)
