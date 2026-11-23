import csv
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean
import subprocess

import matplotlib.pyplot as plt
from .study import ROOT, ROLES, TOTAL, digest, guard, read_json, require

LABEL = {"k2":"Стала група k=2","k3":"Стала група k=3","adaptive":"Адаптивний відбір","replay":"Донорський розклад"}
OUT = ROOT/"report"


def csv_file(name, rows):
    with (OUT/name).open("x",encoding="utf-8-sig",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def fmt(x, places=3):
    return f"{float(x):.{places}f}".replace(".",",")


def report():
    guard()
    receipts = [read_json(p) for p in (ROOT/"collected").rglob("*.receipt.json")]
    cases = {(r["trip"],r["pc"],r["role"]):r for r in receipts}
    require(len(receipts)==len(cases)==60 and set(cases)=={(i,pc,k) for i in range(1,7) for pc in (90,100) for k in ROLES},
            "Incomplete pair inventory")
    OUT.mkdir(parents=True)
    manifests, observed = [], []
    for trip in range(1,7):
        item = read_json(ROOT/"inputs"/f"trip-{trip}.json")
        parcels = {p["id"]:p for p in item["parcels"]}
        manifests.extend(dict(trip=trip,**p) for p in parcels.values())
        paired = [r for r in receipts if r["trip"]==trip]
        require(len({r["bank_sha"] for r in paired})==1 and
                len({r["rng_sha"] for r in paired if r["role"]!="donor"})==1 and
                len({r["rng_sha"] for r in paired})==2 and len({r["rng_sha"] for r in paired if r["role"]=="donor"})==1,
                "Pairing differs")
        for pc in (90,100):
            require(cases[trip,pc,"donor"]["schedule_sha"]==cases[trip,pc,"replay"]["schedule_sha"],"Schedule mismatch")
        for r in paired:
            require(r["commit"]==os.environ["GITHUB_SHA"] and r["verified"] and
                    r["manifest_sha"]==digest(item["parcels"]) and r["optimum"]==item["certificate"]["optimum"],"Wrong origin")
            ids = r["ids"]
            require(len(ids)==len(set(ids)) and sum(parcels[k]["mass_100g"] for k in ids)==r["mass_100g"]<=5000
                    and sum(parcels[k]["points"] for k in ids)==r["points"]<=r["optimum"],"Load sheet mismatch")
            observed.append({"trip":trip,"pc":r["pc"],"role":r["role"],"kg":r["mass_100g"]/10,"parcels":len(ids),
                             "points":r["points"],"optimum":r["optimum"],**{f"q{a}":q for a,q in r["hits"].items()},
                             "selected_ids":" ".join(ids)})
    csv_file("manifests.csv",manifests)
    csv_file("loads.csv",sorted(observed,key=lambda r:(r["trip"],r["pc"],r["role"])))
    results, transfer, feedback = [],[],[]
    def metrics(pc,role):
        part=[cases[t,pc,role] for t in range(1,7)]
        return {"gap":mean(Fraction(100*(r["optimum"]-r["points"]),r["optimum"]) for r in part),
                "t93":mean(Fraction(r["hits"]["93"] if r["hits"]["93"] is not None else TOTAL) for r in part),
                "mean_points":mean(Fraction(r["points"]) for r in part),
                **{f"hits{a}":sum(r["hits"][str(a)] is not None for r in part) for a in (93,95,99)}}
    for pc in (90,100):
        values={k:metrics(pc,k) for k in LABEL}
        results.extend({"pc":pc,"method":k,**{m:float(v) if isinstance(v,Fraction) else v for m,v in row.items()}}
                       for k,row in values.items())
        for m in ("gap","t93"):
            leader=min(v[m] for v in values.values())
            winners=[k for k,v in values.items() if v[m]==leader]
            ref="k2" if (pc,m)==(100,"gap") else "k3"
            transfer.append({"pc":pc,"metric":m,"previous":ref,"winners":",".join(winners),"value":float(leader),
                             "match":"так" if winners==[ref] else "спільний мінімум" if ref in winners else "ні"})
            delta=values["replay"][m]-values["adaptive"][m]
            sign=1 if m=="gap" or pc==100 else -1
            feedback.append({"pc":pc,"metric":m,"donor_minus_adaptive":float(delta),
                             "direction_agrees":"нічия" if delta==0 else "так" if sign*delta>0 else "ні"})
    for name,rows in (("profiles.csv",results),("transfer.csv",transfer),("feedback.csv",feedback)):
        csv_file(name,rows)
    text=["# Відбір посилок для одного рейсу", "", "## Модель і умови", "",
          "Досліджено шість змодельованих рейсів. Для кожного рейсу задано 100 неподільних посилок і вантажопідйомність 500 кг. Цінність доставки виміряно в балах пріоритету. Стандартна посилка отримує 10 балів, пріоритетна 25, термінова 50. Кожна доба очікування додає 2 бали. Дані створено для перевірки алгоритму; тарифів чи записів реального оператора модель не використовує.",
          "", "Для кожного маніфесту обчислено два точних еталони. За кожної ймовірності схрещування чотири способи відбору мають спільну початкову популяцію з 15 особин, мутацію 1% та однаковий ліміт 100 000 оцінювань. Перевірено 48 порівняльних та 12 донорських запусків. Усі шість рейсів мають однакову вагу.",
          "", "## Спостережені результати", "",
          "| Схрещування | Спосіб відбору | Відставання, % | Балів за рейс | Оцінювань до 93% | Досягли 93% із 6 |",
          "|---:|---|---:|---:|---:|---:|"]
    for r in results:
        text.append(f"| {r['pc']}% | {LABEL[r['method']]} | {fmt(r['gap'],4)} | {fmt(r['mean_points'],2)} | {fmt(r['t93'],2)} | {r['hits93']} |")
    for i,(metric,unit) in enumerate((("gap","Кінцеве відставання, %"),("t93","Оцінювань до 93% оптимуму")),1):
        fig,ax=plt.subplots(figsize=(7,3.2),layout="constrained")
        for j,pc in enumerate((90,100)):
            ax.barh([n+(j-.5)*.36 for n in range(4)],[r[metric] for r in results if r["pc"]==pc],
                    height=.34,label=f"Схрещування {pc}%")
        ax.set_yticks(range(4),list(LABEL.values()))
        ax.set_xlabel(unit)
        ax.legend()
        ax.grid(axis="x",alpha=.2)
        fig.savefig(OUT/f"{metric}.png",dpi=180)
        plt.close(fig)
        text.extend(["",f"![]({metric}.png)","",f"Рисунок {i} – {unit}. Середнє за шістьма рейсами."])
    example=cases[1,90,"k3"]
    text.extend(["","## Приклад вантажу","",
                 f"У першому рейсі за схрещування 90% і сталого відбору з трьох особин відібрано {len(example['ids'])} посилок загальною масою {fmt(example['mass_100g']/10,1)} кг. Вантаж набрав {example['points']} балів за точного максимуму {example['optimum']}. Повний склад кожного завантаження наведено в loads.csv.",
                 "", "## Перенесення результатів", "",
                 "| Схрещування | Показник | Лідер на KPLIB | Лідери на моделі рейсу | Збіг |",
                 "|---:|---|---|---|---|"])
    units={"gap":"кінцеве відставання","t93":"оцінювання до 93%"}
    for r in transfer:
        text.append(f"| {r['pc']}% | {units[r['metric']]} | {LABEL[r['previous']]} | {', '.join(LABEL[k] for k in r['winners'].split(','))} | {r['match']} |")
    text+=["","Для порівняння з розкладом додатна різниця означає перевагу адаптивного відбору.",""]
    for f in feedback:
        unit="в. п." if f["metric"]=="gap" else "оцінювань"
        text.append(f"- Схрещування {f['pc']}%, {units[f['metric']]}. Розклад мінус адаптивний відбір: {fmt(f['donor_minus_adaptive'],4)} {unit}. Збіг напряму з KPLIB: {f['direction_agrees']}.")
    text+=["","## Висновок","",f"Одноосібний лідер збігся з попереднім дослідженням у {sum(r['match']=='так' for r in transfer)} із чотирьох наперед визначених порівнянь. Спільний мінімум із попереднім лідером отримано у {sum(r['match']=='спільний мінімум' for r in transfer)} порівняннях. Висновок стосується шести синтетичних маніфестів та одного початку для кожного. Для оцінки роботи перевізника потрібні його пріоритети та фактичний склад замовлень."]
    (OUT/"Звіт.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    subprocess.run(["pandoc","Звіт.md","-o","Звіт.docx","-M","lang=uk-UA"],cwd=OUT,check=True)
    subprocess.run(["libreoffice","--headless","--convert-to","pdf","Звіт.docx","--outdir","."],cwd=OUT,check=True)
    require((OUT/"Звіт.pdf").read_bytes().startswith(b"%PDF"),"Missing PDF")
    (OUT/"checksums.json").write_text(json.dumps({p.name:sha256(p.read_bytes()).hexdigest()
        for p in OUT.iterdir() if p.is_file()},indent=2),encoding="utf-8")

if __name__=="__main__":
    report()
