"""CI-only continuation of the frozen 500-item crossover tuning grid."""
from collections import defaultdict
from fractions import Fraction
from bisect import bisect_right
import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import sys
import time
import traceback

from .common import choose,gap,require,scientific_digest,sha,unpack,validate_compact

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
DATA=HERE/'data'
TOTAL=100000
POINTS=(5000,10000,20000,50000,TOTAL)
TARGETS=(93,95,99)
POPS=(20,25,30,35)
CROSS=(70,80,90,100)


def read(path):
    path=Path(path)
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),'Existing evidence must not be overwritten: '+str(path))
    pending=path.with_name(path.name+'.pending')
    opener=gzip.open if path.suffix=='.gz' else open
    options={'compresslevel':3} if path.suffix=='.gz' else {}
    with opener(pending,'wt',encoding='utf-8',**options) as stream:
        json.dump(obj,stream,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    pending.replace(path)


def setup():
    require(os.environ.get('GITHUB_ACTIONS')=='true','The continuation is CI-only')
    require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','Automatic rerun could repeat completed identities; create a new handoff')
    import numpy as np
    require(np.__version__=='2.2.6','NumPy version differs from the local experiment')
    require(sys.version_info[:3]==(3,12,14),'Python version differs from the local experiment')
    manifest=read(DATA/'source_hashes.json')
    for row in manifest['files']:
        path=(REPO/row['path']).resolve()
        require(path.is_relative_to(REPO.resolve()) and path.is_file() and sha(path)==row['sha256'],
                'Frozen source or input differs: '+row['path'])
    plan=read(DATA/'plan.json')
    require(plan['protocol']=='population-crossover-ci-continuation-v1' and len(plan['remaining'])==107
            and plan['completed']['count']==37 and plan['ci_limits']['parallel_jobs']==4,'Plan differs')
    return plan


def task_data(plan,name):
    entry=next(x for x in plan['datasets'] if x['task']==name)
    value=unpack(DATA/entry['file'],entry['sha256'])
    require(value['problem']['n']==500 and value['optimum']>0,'Problem or optimum differs')
    return value


def make_log(job,task):
    from studies.knapsack_parameters.crossover_population.program.ga_core import create_random_generators,parameter_controller,run_ga
    seed,mu,pc=job['seed'],job['mu'],job['pc_percent']
    require(seed in (133001,133002,133003) and mu in POPS and pc in CROSS,'Configuration outside registered grid')
    bank=task['banks'][str(seed)]
    require(len(bank['masks'])==len(bank['scores'])==35 and bank['masks'][0]=='0'*500,'Bank differs')
    initial={'masks':bank['masks'][:mu],'scores':bank['scores'][:mu]}
    rngs=create_random_generators(seed,task['task_index'],0)
    states={name:generator.bit_generator.state for name,generator in rngs.items()}
    require(states==task['rng_states'][str(seed)],'Initial random states differ')
    params={'p_m':1/500,'p_c':pc/100,'target_mu':mu,'tournament_size':2,'elite_count':1}
    started=time.perf_counter()
    log=run_ga(task['problem'],initial,parameter_controller(0),rngs,budget=TOTAL-mu,
               initial_parameters=params,configuration_contract='population-crossover-v1')
    return log,time.perf_counter()-started


def compact(job,checked,observed,bins,origin,source_sha):
    row={'task':job['task'],'seed':job['seed'],'mu':job['mu'],'pc_percent':job['pc_percent'],
         'origin':origin,'best':observed['final_best_profit'],'optimum':observed['optimum'],
         'events':[[x['q'],x['profit']] for x in observed['record_events']],
         'checkpoints':[{'q':p['q'],'record_profit':p['record_profit'],'population_metrics':p['population_metrics'],
                         'completed_generations':p['completed_generations']} for p in observed['checkpoints']],
         'targets':observed['targets'],'duplicates':checked['duplicate_candidates'],
         'operator_bins':[x for x in bins if x['total']],'source_sha256':source_sha}
    return validate_compact(row)


def pilot(out):
    plan=setup()
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    job=plan['pilot'];task=task_data(plan,job['task'])
    log,elapsed=make_log(job,task)
    started=time.perf_counter();verified=verify_log(log);verify_seconds=time.perf_counter()-started
    require(verified['verification_status']=='VERIFIED','Independent replay failed')
    digest=scientific_digest(log)
    require(digest==job['expected_scientific_sha256'],'CI scientific trajectory differs from the retained local reference')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    write(out/'pilot.json',{'status':'IDENTICAL_SCIENTIFIC_TRACE','scientific_sha256':digest,
          'reference_log_sha256':job['source_log_sha256'],'search_seconds':elapsed,
          'verification_seconds':verify_seconds,'new_search_evaluations':TOTAL,'numpy':'2.2.6',
          'python':sys.version.split()[0],'commit':os.environ.get('GITHUB_SHA')})
    print('Cross-platform pilot: independent verification and complete scientific trajectory match',flush=True)


def run_one(job,task,folder):
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    folder.mkdir(parents=True,exist_ok=False)
    begin=time.perf_counter();log,search_seconds=make_log(job,task)
    write(folder/'journal.json.gz',log);log_write_seconds=time.perf_counter()-begin-search_seconds
    begin=time.perf_counter();checked=verify_log(log);verification_seconds=time.perf_counter()-begin
    require(checked['verification_status']=='VERIFIED' and checked['new_calls']==TOTAL-job['mu'],'Independent replay failed')
    derived=checked.pop('derived_metrics');bins=derived['operator_bins'];del derived
    write(folder/'verification.json',checked)
    write(folder/'operator_bins.json',{'operator_bins':bins,'premutation_score_checks':checked['premutation_score_checks']})
    begin=time.perf_counter();observed=extract(log,TOTAL,task['optimum'],checkpoints=POINTS)
    observations_seconds=time.perf_counter()-begin
    write(folder/'observations.json.gz',observed)
    require(checked['record_profit']==observed['final_best_profit'],'Verification and observations disagree')
    files={'log':'journal.json.gz','verification':'verification.json','observations':'observations.json.gz',
           'operator_diagnostics':'operator_bins.json'}
    source_sha={key:sha(folder/name) for key,name in files.items()}
    result=compact(job,checked,observed,bins,'ci_new',source_sha)
    write(folder/'compact.json',result)
    write(folder/'record.json',{'job':job,'status':'VERIFIED','files':files,'sha256':source_sha,
          'compact_sha256':sha(folder/'compact.json'),'search_seconds':search_seconds,
          'verification_seconds':verification_seconds,'observations_seconds':observations_seconds,
          'log_write_seconds':log_write_seconds,'search_evaluations_including_initial':TOTAL,
          'independent_score_checks':checked['independent_score_checks'],
          'premutation_score_checks':checked['premutation_score_checks'],
          'commit':os.environ.get('GITHUB_SHA')})


def shard(index,pilot_file,out):
    plan=setup();pilot_record=read(pilot_file)
    require(pilot_record['status']=='IDENTICAL_SCIENTIFIC_TRACE'
            and pilot_record['scientific_sha256']==plan['pilot']['expected_scientific_sha256']
            and pilot_record['commit']==os.environ.get('GITHUB_SHA'),'CI pilot is not valid for this commit')
    require(index in range(4),'Invalid shard')
    selected=plan['remaining'][index::4]
    require(len(selected) in (26,27),'Unexpected shard size')
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    tasks={entry['task']:task_data(plan,entry['task']) for entry in plan['datasets']}
    begin=time.monotonic();finished=[]
    for job in selected:
        used=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
        require(time.monotonic()-begin<52*60-300,'Shard is near its time ceiling; retain and resume the missing cases')
        require(used+28*1024**2<plan['ci_limits']['per_shard_bytes'],'Shard is near its storage ceiling')
        label=f"{job['task']}-seed{job['seed']}-mu{job['mu']}-pc{job['pc_percent']}"
        folder=root/label
        try:
            run_one(job,tasks[job['task']],folder)
            finished.append(label)
            print(f'Shard {index}: verified {len(finished)}/{len(selected)} {label}',flush=True)
        except BaseException:
            write(root/'failure.json',{'status':'FAILED','job':job,'error':traceback.format_exc(),'finished':finished})
            raise
    used=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    require(used<=plan['ci_limits']['per_shard_bytes'],'Shard storage exceeded')
    write(root/'shard.json',{'status':'COMPLETE','shard':index,'jobs':finished,'elapsed_seconds':time.monotonic()-begin,
                            'bytes':used,'commit':os.environ.get('GITHUB_SHA')})


def num(value,digits=3):return f'{float(value):.{digits}f}'.replace('.',',')


def aggregate(shards,out):
    plan=setup()
    local=unpack(DATA/plan['completed']['file'],plan['completed']['sha256'])
    require(len(local)==37 and sum(r['origin']=='retained' for r in local)==27,'Local inventory differs')
    rows=[validate_compact(r) for r in local]
    remaining={(j['task'],j['seed'],j['mu'],j['pc_percent']) for j in plan['remaining']}
    ci=[];timings=[]
    for index in range(4):
        root=Path(shards)/f'shard-{index}';manifest=read(root/'shard.json')
        require(manifest['status']=='COMPLETE' and manifest['shard']==index
                and manifest['commit']==os.environ.get('GITHUB_SHA'),'A shard is incomplete or from another commit')
        for label in manifest['jobs']:
            require(type(label) is str and Path(label).name==label and label not in ('.','..'), 'Unsafe case label')
            folder=root/label;meta=read(folder/'record.json');job=meta['job']
            key=(job['task'],job['seed'],job['mu'],job['pc_percent'])
            require(key in remaining and meta['status']=='VERIFIED','Unexpected CI result')
            require(meta['files']=={'log':'journal.json.gz','verification':'verification.json',
                    'observations':'observations.json.gz','operator_diagnostics':'operator_bins.json'},
                    'Evidence file inventory differs')
            for kind,name in meta['files'].items():
                require(sha(folder/name)==meta['sha256'][kind], 'Saved evidence checksum differs')
            require(sha(folder/'compact.json')==meta['compact_sha256'],'Compact data checksum differs')
            item=validate_compact(read(folder/'compact.json'))
            require((item['task'],item['seed'],item['mu'],item['pc_percent'])==key
                    and item['source_sha256']==meta['sha256'],'Compact identity or source differs')
            verified=read(folder/'verification.json');observed=read(folder/'observations.json.gz')
            bin_data=read(folder/'operator_bins.json')
            require(verified['verification_status']=='VERIFIED' and verified['new_calls']==TOTAL-job['mu']
                    and verified['record_profit']==item['best']==observed['final_best_profit']
                    and observed['optimum']==item['optimum'] and observed['total_evaluations']==TOTAL,
                    'Independent replay or observation differs')
            require(item['events']==[[e['q'],e['profit']] for e in observed['record_events']]
                    and item['targets']==observed['targets']
                    and item['operator_bins']==[b for b in bin_data['operator_bins'] if b['total']],
                    'Compact results differ from saved evidence')
            ci.append(item);timings.append({'task':job['task'],'seed':job['seed'],'mu':job['mu'],
                 'pc_percent':job['pc_percent'],**{k:meta[k] for k in ('search_seconds','verification_seconds','observations_seconds','log_write_seconds')}})
    require(len(ci)==107 and {(r['task'],r['seed'],r['mu'],r['pc_percent']) for r in ci}==remaining,
            'CI result inventory is incomplete or duplicated')
    rows+=ci
    tasks=tuple(x['task'] for x in plan['datasets'])
    expected={(task,seed,mu,pc) for task in tasks for seed in (133001,133002,133003) for mu in POPS for pc in CROSS}
    require(len(rows)==144 and {(r['task'],r['seed'],r['mu'],r['pc_percent']) for r in rows}==expected,'Full grid differs')
    for task in tasks:require(len({r['optimum'] for r in rows if r['task']==task})==1,'Optimum differs by configuration')
    ranking=choose(rows,tasks);winner=ranking[0]
    destination=Path(out);destination.mkdir(parents=True,exist_ok=False)
    (destination/'figures').mkdir()
    summary=[];operator=[]
    for mu in POPS:
        for pc in CROSS:
            own=[r for r in rows if (r['mu'],r['pc_percent'])==(mu,pc)]
            fields=('total','crossed','novel_crossed','feasible_crossed','better_both_crossed')
            counts={k:sum(b[k] for r in own for b in r['operator_bins']) for k in fields}
            operator.append({'mu':mu,'pc_percent':pc,'runs':len(own),**counts})
            for q in POINTS:
                mean=sum((gap(r['optimum'],next(p['record_profit'] for p in r['checkpoints'] if p['q']==q)) for r in own),Fraction())/9
                summary.append({'mu':mu,'pc_percent':pc,'q':q,'runs':9,'mean_gap_percent':float(mean),
                    **{f'attained_{target}':sum(r['targets'][str(target)]['attained'] for r in own) for target in TARGETS},
                    **{f'restricted_mean_{target}':sum(r['targets'][str(target)]['restricted_evaluations'] for r in own)/9 for target in TARGETS},
                    'target_horizon_evaluations':TOTAL})
    def save_csv(name,records):
        with (destination/name).open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]),delimiter=';');writer.writeheader();writer.writerows(records)
    save_csv('summary.csv',summary);save_csv('operator_summary.csv',operator);save_csv('ci_timings.csv',timings)
    selection={'status':'SELECTED_FROM_COMPLETE_TUNING','mu':winner[3],'pc_percent':winner[4],
               'mean_gap_percent':float(winner[0]),'mean_gap_exact':[winner[0].numerator,winner[0].denominator],
               'worst_task_gap_percent':float(winner[1]),'runs':144,
               'tie_order':['mean_gap','worst_task_gap','distance_to_90','smaller_population','smaller_crossover'],
               'plan_sha256':sha(DATA/'plan.json'),'local_completed_sha256':plan['completed']['sha256'],
               'local_freeze_sha256':plan['local_freeze_sha256'],'ci_commit':os.environ.get('GITHUB_SHA'),
               'interpretation':'descriptive tuning; independent holdout not performed'}
    write(destination/'selection.json',selection)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'savefig.bbox':'tight'})
    maximum=max(r['mean_gap_percent'] for r in summary if r['q'] in (50000,TOTAL))
    for q in (50000,TOTAL):
        matrix=np.array([[next(r['mean_gap_percent'] for r in summary if (r['mu'],r['pc_percent'],r['q'])==(mu,pc,q))
                          for pc in CROSS] for mu in POPS])
        fig,ax=plt.subplots(figsize=(9,4.8));image=ax.imshow(matrix,cmap='YlGnBu',vmin=0,vmax=maximum*1.05,aspect='auto')
        for y in range(4):
            for x in range(4):ax.text(x,y,num(matrix[y,x])+'%',ha='center',va='center',
                color='white' if matrix[y,x]>maximum*.62 else '#14222b',fontsize=12)
        ax.set(xticks=range(4),xticklabels=CROSS,yticks=range(4),yticklabels=POPS,
               xlabel='Імовірність застосування схрещування, %',ylabel='Кількість особин у популяції')
        fig.colorbar(image,ax=ax,label='Середнє відставання від OPT, %; менше краще')
        fig.savefig(destination/'figures'/f'heatmap-{q}.png',dpi=180)
        fig.savefig(destination/'figures'/f'heatmap-{q}.svg');plt.close(fig)
    colors={70:'#2166ac',80:'#d66032',90:'#238b45',100:'#984ea3'}
    for target in TARGETS:
        fig,axes=plt.subplots(2,2,figsize=(10,7),sharex=True,sharey=True)
        for ax,mu in zip(axes.flat,POPS):
            for pc in CROSS:
                own=[r for r in rows if (r['mu'],r['pc_percent'])==(mu,pc)]
                hits=sorted(r['targets'][str(target)]['first_total_evaluation'] for r in own if r['targets'][str(target)]['attained'])
                xs=sorted({0,TOTAL,*hits});ys=[100*bisect_right(hits,q)/9 for q in xs]
                ax.step(xs,ys,where='post',label=f'{pc}% схрещування',color=colors[pc])
            ax.set(xlim=(0,TOTAL),ylim=(0,100),xlabel='Загальна кількість оцінювань',
                   ylabel=f'Популяція {mu}; досягли {target}% OPT, %')
            ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(destination/'figures'/f'attainment-{target}.png',dpi=180)
        fig.savefig(destination/'figures'/f'attainment-{target}.svg');plt.close(fig)
    lines=['# Схрещування 70–100% і розмір популяції','',
      'Порівняно 16 комбінацій на трьох задачах із 500 предметами. Кожна комбінація має дев’ять результатів: три задачі та три повторення. У 100 000 загальних оцінювань входить початкова популяція. Мутація дорівнює 1/500, відбір виконується з двох особин, зберігається одна еліта.','',
      f'За найменшим середнім відставанням обрано популяцію {winner[3]} і схрещування {winner[4]}%: {num(winner[0])}%. Це описовий вибір на трьох відомих задачах, який потребує незалежної перевірки.','',
      'Таблиця 1 - Середнє відставання після 100 000 оцінювань','',
      '| Популяція | 70% | 80% | 90% | 100% |','| --- | --- | --- | --- | --- |']
    for mu in POPS:
        values=[next(r['mean_gap_percent'] for r in summary if (r['mu'],r['pc_percent'],r['q'])==(mu,pc,TOTAL)) for pc in CROSS]
        lines.append('| '+str(mu)+' | '+' | '.join(num(x)+'%' for x in values)+' |')
    lines += ['', 'Підсумок складається з 37 перевірених локальних результатів і 107 результатів GitHub Actions. Середнє обчислено спочатку за повтореннями, потім за задачами з однаковими вагами. Один локальний контрольний запуск окремо повторено в CI для перевірки точного збігу всієї наукової траєкторії; до 144 результатів цей контроль не додано.', '']
    captions={f'heatmap-50000':'Середнє відставання після 50 000 оцінювань',f'heatmap-100000':'Середнє відставання після 100 000 оцінювань',
              **{f'attainment-{t}':f'Досягнення {t}% OPT' for t in TARGETS}}
    for index,(name,title) in enumerate(captions.items(),1):
        lines += [f'![Рисунок {index} - {title}](figures/{name}.png)','']
    lines += ['Кожна крива містить дев’ять запусків; недосягнення залишено у знаменнику. 93%, 95% та 99% OPT відповідають відставанню до 7%, 5% та 1%. Практичну прийнятність цих втрат для окремого застосування не встановлено. Кольорові шкали двох теплових карт однакові.','',
      'Вибір є результатом підбору в межах перевіреної сітки. Він не є доказом універсальної оптимальності та ще не перевірений на незалежних задачах. Схрещування, популяція та інші параметри були сталими в кожному запуску.','']
    (destination/'Звіт.md').write_text('\n'.join(lines),encoding='utf-8')
    write(destination/'provenance.json',{'status':'COMPLETE','local_runs':37,'ci_runs':107,'pilot_excluded':True,
          'selection':selection,'ci_run_id':os.environ.get('GITHUB_RUN_ID'),'ci_commit':os.environ.get('GITHUB_SHA'),
          'plan_sha256':sha(DATA/'plan.json'),'handoff_snapshot_sha256':plan['handoff_snapshot_sha256']})
    print('Complete verified grid:',len(rows),'selected:',winner[3],winner[4],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('pilot');p.add_argument('--out',required=True)
    p=sub.add_parser('shard');p.add_argument('--index',type=int,required=True);p.add_argument('--pilot',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('aggregate');p.add_argument('--shards',required=True);p.add_argument('--out',required=True)
    args=parser.parse_args()
    if args.action=='pilot':pilot(args.out)
    elif args.action=='shard':shard(args.index,args.pilot,args.out)
    else:aggregate(args.shards,args.out)


if __name__=='__main__':main()
