"""Certify candidate KPLIB inputs outside the search; historical GA use is audited separately."""
import hashlib
import json
from pathlib import Path
from time import monotonic
from urllib.request import urlopen

from ..population_size_study.exact import certify_problem
from ..population_size_study.inputs import parse_kp_bytes, problem_sha256, unordered_problem_sha256
from ..population_validation_100.preparation import score
from .study import require

CLASSES = {"00Uncorrelated":"UC","01WeaklyCorrelated":"WC","02StronglyCorrelated":"SC"}
REVISION = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"


def main():
    registry = json.loads(Path(__file__).with_name("holdout-sources.json").read_bytes())
    entries = registry["blobs"]
    paths = {f"{kind}/n00100/R01000/s{i:03}.kp" for kind in CLASSES for i in range(90)}
    require(registry["commit"] == REVISION and len(entries)==270 and {e["path"] for e in entries}==paths,
            "Unexpected source inventory")
    previous = set()
    candidates = set()
    manifest = []
    root = Path("holdout-inputs")
    root.mkdir()
    for entry in sorted(entries,key=lambda e:(Path(e["path"]).stem,e["path"])):
        path = entry["path"]
        url = f"https://raw.githubusercontent.com/likr/kplib/{REVISION}/{path}"
        with urlopen(url, timeout=45) as response:
            require(response.geturl()==url,"Unexpected source redirect")
            raw = response.read(entry["size"]+1)
        blob = hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        require(len(raw)==entry["size"] and blob==entry["sha"],"Source identity differs")
        problem = parse_kp_bytes(raw,100)
        key = unordered_problem_sha256(problem)
        family = int(Path(path).stem[1:])
        if family < 80:
            previous.add(key)
            continue
        require(key not in previous and key not in candidates,"Exact or permuted holdout duplicate")
        candidates.add(key)
        task = f"n00100-{CLASSES[path.split('/')[0]]}-s{family:03}"
        cert = certify_problem(problem,memory_limit_bytes=512*1024**2,deadline=monotonic()+60)
        for kind in ("capacity_certificate","profit_certificate"):
            measured = score(problem,cert[kind]["witness_mask"])
            require(measured["feasible"] and measured["profit"]==cert["optimum"],"Inconsistent witness")
        dest = root/task
        dest.mkdir()
        (dest/"source.kp").write_bytes(raw)
        for name,value in (("problem",problem),("certificate",cert)):
            (dest/(name+".json")).write_text(json.dumps(value,sort_keys=True),encoding="utf8")
        manifest.append(dict(task=task,source=path,git_blob=blob,source_sha256=hashlib.sha256(raw).hexdigest(),
                             problem_sha256=problem_sha256(problem),unordered_sha256=key,optimum=cert["optimum"]))
    require(len(manifest)==30,"Incomplete certification")
    (root/"manifest.json").write_text(json.dumps(dict(tasks=manifest,source_revision=REVISION,
        source="https://github.com/likr/kplib",license="CC-BY-4.0",comparison_inputs=240,
        previous_search_audit="PENDING",search_runs=0),indent=2),encoding="utf8")


if __name__=="__main__":
    main()
