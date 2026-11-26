"""Registered designs. Parameters in static tuples use percentages (including mutation)."""
from itertools import product
from math import lcm

BITS = {"k2": 0, "k3": 0, "A1": 4, "A2": 2, "A3": 1, "A4": 8, "A5": 16, "A6": 24, "A7": 31}
BASES = (90, 100)
LEVELS = ((10,15,20,25,30,50,75,100), tuple(range(10,101,10)), (1,2,4,8), (2,3,4,5), (1,2,3,4,5))
COORDS = {"A1": (0,), "A2": (1,), "A3": (2,), "A4": (3,), "A5": (4,), "A6": (3,4)}
METRICS = ("gap","t93")
CONTROLS = ("k2","k3","tuned_static","donor_schedule","same_mechanism_H145")
TOTAL = 100000


def screening():
    for pc in BASES:
        for role in BITS:
            for threshold in ((None,) if role in ("k2","k3","A2") else (70,145,280)):
                yield pc,role,threshold


def tasks():
    return [f"n00100-{kind}-s{family:03}" for family in range(50,60) for kind in ("UC","WC","SC")]


def cases():
    return product(tasks(),range(150001,150004),screening())


def static_grid(pc, role):
    base = (15,pc,1,2,1)
    if role != "A7":
        indices = COORDS[role]
        result = []
        for values in product(*(LEVELS[i] for i in indices)):
            v = list(base)
            for i,x in zip(indices,values,strict=True):
                v[i] = x
            result.append(tuple(v))
        return result
    selected = [base,(15,pc,1,3,1)]
    scale = lcm(*(len(axis)-1 for axis in LEVELS))
    coords = {v:tuple(axis.index(x)*scale//(len(axis)-1) for axis,x in zip(LEVELS,v))
              for v in product(*LEVELS)}
    remaining = {v:float("inf") for v in coords}
    def update(point):
        remaining.pop(point)
        for v in remaining:
            d = sum((a-b)**2 for a,b in zip(coords[v],coords[point]))
            remaining[v] = min(remaining[v],d)
    for v in selected:
        update(v)
    while len(selected)<24:
        point = min(remaining,key=lambda v:(-remaining[v],v))
        selected.append(point)
        update(point)
    return selected


def contrasts():
    return list(product(BASES,METRICS,CONTROLS))


def threshold_control(role, mode, value):
    if role in ("A2","k2","k3"):
        return "NOT_APPLICABLE"
    if mode=="absolute" and value==145 or mode=="initial" and value*14==145:
        return "IDENTICAL"
    return "PAIRED"
