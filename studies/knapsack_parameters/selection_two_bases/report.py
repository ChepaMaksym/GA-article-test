"""Aggregate the pre-registered task pairs and render the Ukrainian study report."""
from collections import Counter
import csv
from fractions import Fraction
import json
import os
from pathlib import Path
from statistics import mean
import subprocess

from .study import ROLES, TASKS, TOTAL, check_ci, require

NAMES = {"k2":"Сталий відбір, k=2", "k3":"Сталий відбір, k=3", "adaptive":"Адаптивний відбір",
         "replay":"Донорський розклад"}
OUT = Path("stage/report")


def table(name, rows):
    with (OUT/name).open("x",newline="",encoding="utf-8-sig") as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=";")
        w.writeheader()
        w.writerows(rows)


def val(row, metric):
    if metric == "gap":
        return Fraction(100*(row["optimum"]-row["best"]),row["optimum"])
    q = row["hits"]["93"]
    return TOTAL if q is None else q


def main():
    check_ci()
    rows = [json.loads(p.read_bytes()) for p in Path("stage/collected").rglob("*.receipt.json")]
    cases = {(r["task"],r["pc"],r["role"]):r for r in rows}
    require(len(rows)==len(cases)==300 and set(cases)=={(t,pc,r) for t in TASKS for pc in (90,100) for r in ROLES},
            "Missing or duplicated study identity")
    require(all(r["verified"] is True and r["commit"]==os.environ["GITHUB_SHA"] and r["evaluations"]==TOTAL for r in rows),
            "Replay or commit differs")
    for task in TASKS:
        subset=[r for r in rows if r["task"]==task]
        for field in ("optimum","source_sha256","bank_sha256"):
            require(len({r[field] for r in subset})==1, "Unpaired source, bank or optimum")
        recipients={r["rng_initial"] for r in subset if r["role"]!="donor"}
        donors={r["rng_initial"] for r in subset if r["role"]=="donor"}
        require(len(recipients)==len(donors)==1 and recipients.isdisjoint(donors), "Unexpected seed pairing")
        for pc in (90,100):
            require(cases[task,pc,"donor"]["schedule_sha256"]==cases[task,pc,"replay"]["schedule_sha256"],
                    "Donor and recipient schedules differ")
    OUT.mkdir(parents=True)
    family, profiles, effects = [],[],[]
    for pc in (90,100):
        for role in NAMES:
            part=[cases[t,pc,role] for t in TASKS]
            label=NAMES[role]
            fr=[]
            for number in range(70,80):
                group=[r for r in part if r["task"].endswith(f"s{number:03}")]
                require(len(group)==3,"Family size differs")
                fr.append({m:mean(val(r,m) for r in group) for m in ("gap","t93")})
                family.append({"pc":pc,"role":role,"family":number, **{k:float(v) for k,v in fr[-1].items()}})
            profiles.append({"pc":pc,"role":role,"method":label,"runs":len(part),
                             **{m:float(mean(x[m] for x in fr)) for m in ("gap","t93")},
                             **{f"missed_{a}":sum(r["hits"][str(a)] is None for r in part) for a in (93,95,99)}})
        for control in ("k2","k3","replay"):
            for metric in ("gap","t93"):
                delta=[val(cases[t,pc,control],metric)-val(cases[t,pc,"adaptive"],metric) for t in TASKS]
                effects.append({"pc":pc,"control":control,"metric":metric,"effect":float(mean(delta)),
                                "adaptive_better":sum(x>0 for x in delta),"tie":sum(x==0 for x in delta),
                                "control_better":sum(x<0 for x in delta)})
    table("profiles.csv",profiles)
    table("families.csv",family)
    table("effects.csv",effects)
    (OUT/"receipts.json").write_text(json.dumps(rows,indent=1),encoding="utf-8")
    import matplotlib.pyplot as plt
    def fmt(x): return f"{x:.4f}".replace(".",",")
    text=["# Керування турнірним відбором за двох імовірностей схрещування", "",
          "## Методика", "",
          "На 30 задачах рюкзака зі 100 предметами порівняно чотири способи відбору. Популяція складалася з 15 особин, імовірність мутації біта становила 1%. Кожний запуск охоплював 100 000 оцінювань разом із початковою популяцією. Незалежно відтворено 240 порівняльних і 60 донорських запусків. Один донор передавав послідовність розмірів групи одному одержувачеві за тієї самої задачі та ймовірності схрещування.",
          "", "Кожен варіант оцінено за одним спільним повторенням на кожній задачі. Спочатку усереднено три задачі кожного сімейства, потім десять сімейств. Недосягнення цілі враховано як 100 000 оцінювань.",
          "", "| Схрещування | Спосіб відбору | Кінцеве відставання, % | Оцінювань до 93% | Недосягнення 93% із 30 |",
          "|---:|---|---:|---:|---:|"]
    for r in profiles:
        text.append(f"| {r['pc']}% | {r['method']} | {fmt(r['gap'])} | {fmt(r['t93'])} | {r['missed_93']} |")
    for i,(metric,title,unit) in enumerate((("gap","Кінцева якість","Відставання від оптимуму, %"),
                                             ("t93","Швидкість досягнення 93% оптимуму","Кількість оцінювань до 93%")),1):
        fig,ax=plt.subplots(figsize=(7,3.6),layout="constrained")
        for j,pc in enumerate((90,100)):
            ax.barh([v+(j-.5)*.34 for v in range(4)],[r[metric] for r in profiles if r["pc"]==pc],
                    height=.32,label=f"Схрещування {pc}%")
        ax.set_yticks(range(4), list(NAMES.values()))
        ax.set_xlabel(unit)
        ax.legend()
        ax.grid(axis="x", alpha=.2)
        for ext in ("png","svg"):
            fig.savefig(OUT/f"{metric}.{ext}",dpi=170)
        plt.close(fig)
        text.extend(["",f"![]({metric}.png)","",f"Рисунок {i} – {title} за чотирьох способів відбору."])
    text.extend(["","## Висновки",""])
    for pc in (90,100):
        subset=[r for r in profiles if r["pc"]==pc]
        for metric,description in (("gap","найменше середнє кінцеве відставання"),("t93","найменше середнє число оцінювань до 93%")):
            best=min(r[metric] for r in subset)
            leaders=", ".join(r["method"] for r in subset if r[metric]==best)
            text.extend([f"За схрещування {pc}% {description} отримано для варіанта «{leaders}» ({fmt(best)}).",""])
    for control in ("k2","k3","replay"):
        for metric,units in (("gap","в. п. кінцевого відставання"),("t93","оцінювань до 93%")):
            pair=[e for e in effects if e["control"]==control and e["metric"]==metric]
            text.extend([f"Різниця між контролем «{NAMES[control]}» та адаптивним відбором становила {fmt(pair[0]['effect'])} і {fmt(pair[1]['effect'])} {units} за схрещування 90% і 100% відповідно. Додатне значення відповідає перевазі адаптивного відбору.",""])
    text.append("Оцінки характеризують десять сімейств і вибраний початок кожної задачі. Одне повторення залишає невиміряною мінливість результату за інших початкових чисел генератора.")
    (OUT/"Звіт.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    subprocess.run(["pandoc","Звіт.md","-o","Звіт.docx","-M","lang=uk-UA"],cwd=OUT,check=True)
    subprocess.run(["libreoffice","--headless","--convert-to","pdf","Звіт.docx","--outdir","."],cwd=OUT,check=True)
    require((OUT/"Звіт.pdf").read_bytes().startswith(b"%PDF-"),"Missing rendered report")

if __name__=="__main__":
    main()
