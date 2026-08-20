from __future__ import annotations
import argparse, json, platform, os
from pathlib import Path
from usa2609.experiment import run_campaign, scientific_digest

p=argparse.ArgumentParser()
p.add_argument('--workers',type=int,required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
rows=run_campaign(range(1001,1007),budget=300,target=1.830,workers=a.workers)
report={
 'status':'PASS_WORKER_PROFILE',
 'workers':a.workers,
 'scientific_digest':scientific_digest(rows),
 'python':platform.python_version(),
 'platform':platform.platform(),
 'cpu_count':os.cpu_count(),
}
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,sort_keys=True))
print(json.dumps(report,sort_keys=True))
