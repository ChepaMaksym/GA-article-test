"""CI-only scientific figures from fully validated prespecified report data."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def create_plots(report: dict, directory: Path) -> list[dict]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("scientific plotting is permitted only in GitHub Actions")
    if report.get("status") != "COMPLETE_VERIFIED_MAIN" or report.get("runs") != 35640:
        raise ValueError("figures require the complete main series, never a partial/pilot result")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                                "axes.grid":False,"savefig.facecolor":"white"})
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    figures=[]
    def save(figure,name,caption):
        figure.savefig(directory/name,dpi=180,bbox_inches="tight")
        plt.close(figure)
        figures.append({"path":f"figures/{name}","caption":caption})
    for profile,metric,limit,title,name in (
        ("local","escape_rate_equal_family",(0,1),"Частота виходу з локального центра","local_escape_grid.png"),
        ("random","mean_final_relative_gap_equal_family",None,"Кінцевий відносний розрив до оптимуму","random_gap_grid.png"),
    ):
        rows=[row for row in report["configuration_summaries"] if row["start_profile"]==profile]
        values={(r["mutation_numerator"],r["crossover_probability"],r["population_size"]):r[metric] for r in rows}
        high=max(values.values()) if limit is None else limit[1]
        high=max(high,1e-12)
        fig,axes=plt.subplots(1,3,figsize=(11.3,3.6),constrained_layout=True)
        for ax,population in zip(axes,(10,30,50),strict=True):
            grid=np.asarray([[values[(m,c,population)] for c in (0.,.5,.9)] for m in (.5,1.,3.)])
            ax.imshow(grid,cmap="Greys",vmin=0,vmax=high,aspect="equal")
            for m in range(3):
                for c in range(3):
                    ax.text(c,m,f"{100*grid[m,c]:.2f}%",ha="center",va="center",
                            color="white" if grid[m,c]>high*.55 else "black")
            ax.set_xticks(range(3),["0","0,5","0,9"])
            ax.set_yticks(range(3),["0,5/n","1/n","3/n"])
            ax.set_xlabel("Імовірність схрещування")
            ax.set_ylabel("Імовірність мутації біта")
            ax.set_title(f"Популяція {population}")
        fig.suptitle(title+"; рівна вага сімейств")
        save(fig,name,title+" для всіх 27 конфігурацій. Описові середні з однаковою вагою сімейств.")

    intervals=report["primary_statistics"]["intervals"]
    labels=["Мутація 3/n − 1/n","Схрещування 0,9 − 0","Популяція 50 − 10","Взаємодія мутації та схрещування"]
    fig,ax=plt.subplots(figsize=(9.6,3.7),constrained_layout=True)
    for index,row in enumerate(intervals):
        value=100*row["estimate"]
        if row["status"]=="INFERENTIAL_BCA":
            low,high=100*row["lower"],100*row["upper"]
            ax.hlines(index,low,high,color="black",linewidth=1.5)
            ax.plot([low,high],[index,index],"|",color="black",markersize=9)
            ax.plot(value,index,"o",color="black",markersize=5)
        else:
            ax.plot(value,index,"o",markerfacecolor="white",markeredgecolor="black",markersize=7)
            ax.annotate("лише описово",(value,index),xytext=(8,6),textcoords="offset points",fontsize=8)
    ax.axvline(0,color="gray",linestyle="--",linewidth=1)
    ax.set_yticks(range(4),labels)
    ax.invert_yaxis()
    ax.set_xlabel("Різниця частот виходу, відсоткові пункти")
    ax.set_title("Чотири зареєстровані контрасти: BCa-інтервали 98,75%")
    save(fig,"primary_contrasts.png","Чотири первинні контрасти з поправкою на множинність. "
         "Порожня точка означає описову оцінку без придатного інтервалу.")

    styles={.5:("black",":"),1.:("black","-"),3.:("black","--")}
    for profile in ("random","local"):
        trajectories=[row for row in report["example_trajectories"] if row["start_profile"]==profile]
        if len(trajectories)!=3:
            raise ValueError("the predefined three-configuration trajectory set is incomplete")
        fig,axes=plt.subplots(3,1,figsize=(10,8.2),sharex=True,constrained_layout=True)
        for row in trajectories:
            color,linestyle=styles[row["mutation_numerator"]]
            label=f"pₘ = {str(row['mutation_numerator']).replace('.',',')}/n"
            axes[0].step(row["requests"],row["best_feasible_profit"],where="post",
                         color=color,linestyle=linestyle,label=label,linewidth=1.3)
            checkpoints=row["population_metrics"]
            x=[point["request"] for point in checkpoints]
            # No extension to 5000, interpolation or partial-population invention.
            y=[np.nan if point["mean_feasible_profit"] is None else point["mean_feasible_profit"] for point in checkpoints]
            axes[1].plot(x,y,color=color,linestyle=linestyle,linewidth=1.2)
            axes[2].plot(x,[point["diversity"] for point in checkpoints],
                         color=color,linestyle=linestyle,linewidth=1.2)
        axes[0].legend(loc="best",ncols=3)
        axes[0].set_ylabel("Рекорд цінності")
        axes[1].set_ylabel("Середня цінність\nдопустимих особин")
        axes[2].set_ylabel("Унікальні маски / N")
        axes[2].set_ylim(-.025,1.025)
        axes[2].set_xlabel("Логічне оцінювання, включно з початковою популяцією")
        for ax in axes:
            ax.grid(axis="y",color="0.88",linewidth=.6)
        kind="випадковий" if profile=="random" else "локальний"
        fig.suptitle(f"UC-s000, seed 51001: {kind} початок; pс = 0,9; N = 30")
        save(fig,f"example_UC_s000_51001_{profile}.png",
             f"Наперед визначений приклад: {kind} початок. Рекорд охоплює всі оцінені кандидати; "
             "популяційні показники лише початок і завершені покоління. Без штучного продовження до ліміту.")
    return figures
