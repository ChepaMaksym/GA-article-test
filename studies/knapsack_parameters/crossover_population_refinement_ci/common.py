"""Portable, deterministic checks for the CI continuation."""
import base64
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import zlib


def require(condition,message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):
            digest.update(part)
    return digest.hexdigest()


def scientific_digest(log):
    scientific={k:v for k,v in log.items() if k not in ('schema','configuration_contract','timing_ns')}
    digest=hashlib.sha256()
    for part in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).iterencode(scientific):
        digest.update(part.encode('utf-8'))
    return digest.hexdigest()


def unpack(path,expected_sha256):
    require(sha(path)==expected_sha256,'Input file checksum differs')
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    require(value['encoding']=='zlib-base64-json','Invalid input encoding')
    raw=zlib.decompress(base64.b64decode(value['data'],validate=True))
    require(hashlib.sha256(raw).hexdigest()==value['raw_sha256'],'Unpacked input checksum differs')
    return json.loads(raw)


def gap(optimum,best):
    require(type(optimum) is int and type(best) is int and 0<=best<=optimum and optimum>0,'Invalid score/reference')
    return Fraction(100*(optimum-best),optimum)


def validate_compact(row,total=100000):
    optimum=row['optimum'];events=row['events']
    require(type(events) is list and bool(events),'Record history missing')
    require(all(1<=q<=total and type(p) is int and 0<=p<=optimum for q,p in events),'Invalid record event')
    require(all(a[0]<b[0] and a[1]<b[1] for a,b in zip(events,events[1:])), 'Record events are not strictly ordered')
    require(events[-1][1]==row['best'],'Final record differs')
    gap(optimum,row['best'])
    expected_points={5000,10000,20000,50000,total}
    require({p['q'] for p in row['checkpoints']}==expected_points and len(row['checkpoints'])==5,'Checkpoints incomplete')
    for point in row['checkpoints']:
        best=next(p for q,p in reversed(events) if q<=point['q'])
        require(best==point['record_profit'],'Checkpoint record differs')
    for target in (93,95,99):
        first=next((q for q,p in events if 100*p>=target*optimum),None)
        hit=row['targets'][str(target)]
        require(hit['first_total_evaluation']==first and hit['attained']==(first is not None)
                and hit['restricted_evaluations']==(total if first is None else first),'Target accounting differs')
    require(type(row['duplicates']) is int and row['duplicates']>=0,'Duplicate count differs')
    bins=row['operator_bins']
    require(type(bins) is list and sum(b['total'] for b in bins)==total-row['mu'],'Operator count differs')
    for b in bins:
        require(all(type(b[k]) is int and b[k]>=0 for k in ('total','crossed','novel_crossed','feasible_crossed','better_both_crossed')),
                'Invalid operator count')
        require(b['crossed']<=b['total'] and b['novel_crossed']<=b['crossed']
                and b['feasible_crossed']<=b['crossed'] and b['better_both_crossed']<=b['feasible_crossed'],
                'Impossible operator counts')
    return row


def choose(rows,tasks):
    ranking=[]
    for mu in (20,25,30,35):
        for pc in (70,80,90,100):
            means=[]
            for task in tasks:
                own=[gap(r['optimum'],r['best']) for r in rows if (r['mu'],r['pc_percent'],r['task'])==(mu,pc,task)]
                require(len(own)==3,'Three repeats are required')
                means.append(sum(own,Fraction())/3)
            ranking.append((sum(means,Fraction())/3,max(means),abs(pc-90),mu,pc))
    ranking.sort()
    return ranking
