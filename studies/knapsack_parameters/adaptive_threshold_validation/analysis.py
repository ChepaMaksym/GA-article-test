"""Paired family/manifest inference under the registered 20-slot multiplicity correction."""
from collections import defaultdict
from fractions import Fraction
from math import floor, ceil
from statistics import NormalDist, mean
import numpy as np

from .design import BITS, METRICS, TOTAL, screening, tasks


def endpoint(record, metric):
    if metric=="gap":
        return Fraction(100*(record["optimum"]-record["best"]),record["optimum"])
    q=record["hits"]["93"]
    return Fraction(TOTAL if q is None else q)


def select_screen(records):
    expected={(t,s,p,r,h) for t in tasks() for s in range(150001,150004) for p,r,h in screening()}
    groups=defaultdict(lambda:defaultdict(list))
    for row in records:
        key=(row["task"],row["seed"],row["pc"],row["role"],row["threshold"])
        if key not in expected or row["verified"] is not True or row["total"]!=TOTAL:
            raise ValueError(f"Unexpected case: {key}")
        expected.remove(key)
        groups[key[2:]][(key[0][-4:],key[0])].append(row)
    if expected:
        raise ValueError(f"Missing {len(expected)} cases")
    estimates={}
    for config,per_task in groups.items():
        estimates[config]={}
        for metric in METRICS:
            families=defaultdict(list)
            for (family,_),rows in per_task.items():
                families[family].append(mean(endpoint(x,metric) for x in rows))
            estimates[config][metric]=mean(mean(v) for v in families.values())
    winners=[]
    for pc in (90,100):
        for metric,secondary in (METRICS,METRICS[::-1]):
            eligible=[c for c in estimates if c[0]==pc and c[1].startswith("A")]
            key=min(eligible,key=lambda c:(estimates[c][metric],estimates[c][secondary],
                    BITS[c[1]].bit_count(),c[1],c[2] or 0))
            winners.append(dict(pc=pc,metric=metric,role=key[1],threshold=key[2],
                                value=float(estimates[key][metric])))
    return winners


def bca(differences, seed=196031):
    """Resample paired cluster effects (ten families or thirty manifests)."""
    d=np.asarray(differences,dtype=float)
    if d.shape not in ((10,),(30,)) or not np.isfinite(d).all():
        raise ValueError("Incomplete paired cluster effects")
    effect=float(d.mean())
    loo=(d.sum()-d)/(len(d)-1)
    result=dict(effect=effect,leave_one_out=loo.tolist(),confidence=.9975)
    if np.all(d==d[0]):
        return dict(result,status="DEGENERATE",interval=None)
    rng=np.random.default_rng(seed)
    samples=np.sort(d[rng.integers(len(d),size=(50000,len(d)))].mean(axis=1))
    prob=(sum(samples<effect)+.5*sum(samples==effect))/len(samples)
    if not 0<prob<1:
        return dict(result,status="DEGENERATE",interval=None)
    normal=NormalDist()
    z0=normal.inv_cdf(prob)
    centered=loo.mean()-loo
    acceleration=np.sum(centered**3)/(6*np.sum(centered**2)**1.5)
    limits=[]
    for q in (.00125,.99875):
        z=z0+normal.inv_cdf(q)
        denominator=1-acceleration*z
        if denominator<=0:
            return dict(result,status="DEGENERATE",interval=None)
        index=(len(samples)-1)*normal.cdf(z0+z/denominator)
        low,high=floor(index),ceil(index)
        limits.append(float(samples[low]+(index-low)*(samples[high]-samples[low])))
    return dict(result,status="ESTIMATED" if limits[0]<limits[1] else "DEGENERATE",interval=limits)
