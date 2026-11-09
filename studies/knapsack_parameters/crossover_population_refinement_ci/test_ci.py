"""Small deterministic CI checks; no registered tuning run is started."""
import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from .common import choose,scientific_digest,sha,unpack,validate_compact
from .ci_driver import DATA,aggregate,read,task_data


class PortableChecks(unittest.TestCase):
    def sample(self):
        events=[[1,0],[7,93],[8,95],[9,99],[10,100]]
        targets={str(a):{'first_total_evaluation':q,'attained':True,'restricted_evaluations':q}
                 for a,q in ((93,7),(95,8),(99,9))}
        return {'task':'example','seed':1,'mu':20,'pc_percent':90,'optimum':100,'best':100,
                'events':events,'checkpoints':[{'q':q,'record_profit':100} for q in (5000,10000,20000,50000,100000)],
                'targets':targets,'duplicates':0,
                'operator_bins':[{'distance':0,'total':99980,'crossed':100,'novel_crossed':0,
                                  'feasible_crossed':100,'better_both_crossed':0}]}

    def test_exact_target_inclusive_and_final_history(self):
        row=self.sample();self.assertEqual(validate_compact(row)['best'],100)
        row['targets']['95']['first_total_evaluation']=9
        with self.assertRaises(ValueError):validate_compact(row)

    def test_invalid_operator_counts_and_checkpoint_rejected(self):
        row=self.sample();row['operator_bins'][0]['better_both_crossed']=101
        with self.assertRaises(ValueError):validate_compact(row)
        row=self.sample();row['checkpoints'][0]['record_profit']=99
        with self.assertRaises(ValueError):validate_compact(row)

    def test_selection_ties_and_strict_inventory(self):
        tasks=('a','b','c')
        rows=[{'task':t,'mu':mu,'pc_percent':pc,'optimum':1000,'best':990}
              for t in tasks for mu in (20,25,30,35) for pc in (70,80,90,100) for _ in range(3)]
        self.assertEqual(choose(rows,tasks)[0][3:],(20,90))
        with self.assertRaises(ValueError):choose(rows[:-1],tasks)

    def test_digest_ignores_only_schema_contract_and_timing(self):
        a={'schema':'old','timing_ns':{'total':1},'candidates':[{'mask':'10'}]}
        b={'schema':'new','configuration_contract':'new','timing_ns':{'total':2},'candidates':[{'mask':'10'}]}
        self.assertEqual(scientific_digest(a),scientific_digest(b))
        b['candidates'][0]['mask']='01'
        self.assertNotEqual(scientific_digest(a),scientific_digest(b))

    def test_compressed_input_checksum(self):
        raw=b'{"x":3}'
        encoded={'encoding':'zlib-base64-json','raw_sha256':hashlib.sha256(raw).hexdigest(),
                 'data':base64.b64encode(zlib.compress(raw)).decode('ascii')}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.json';path.write_text(json.dumps(encoded),encoding='utf-8')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(unpack(path,digest),{'x':3})
            with self.assertRaises(ValueError):unpack(path,'0'*64)

    def test_handoff_is_disjoint_and_complete(self):
        plan=read(DATA/'plan.json')
        from .common import unpack
        completed=unpack(DATA/plan['completed']['file'],plan['completed']['sha256'])
        keys=lambda rows:{(r['task'],r['seed'],r['mu'],r['pc_percent']) for r in rows}
        self.assertEqual((len(completed),len(plan['remaining'])),(37,107))
        self.assertFalse(keys(completed)&keys(plan['remaining']))
        self.assertEqual(len(keys(completed)|keys(plan['remaining'])),144)
        for row in completed:validate_compact(row)
        for dataset in plan['datasets']:
            task=task_data(plan,dataset['task'])
            self.assertEqual(task['problem']['n'],500)
            self.assertEqual({len(v['masks']) for v in task['banks'].values()},{35})

    def test_complete_aggregation_with_independent_evidence(self):
        import gzip
        from itertools import product
        tasks=('n00500-UC-s000','n00500-WC-s001','n00500-SC-s005')
        identities=[dict(task=t,seed=seed,mu=mu,pc_percent=pc)
                    for t,seed,mu,pc in product(tasks,(133001,133002,133003),(20,25,30,35),(70,80,90,100))]
        def row(job,origin):
            result=self.sample();result.update(job);result.update(origin=origin,optimum=1000,best=970,
                events=[[1,970]],targets={'93':{'first_total_evaluation':1,'attained':True,'restricted_evaluations':1},
                '95':{'first_total_evaluation':1,'attained':True,'restricted_evaluations':1},
                '99':{'first_total_evaluation':None,'attained':False,'restricted_evaluations':100000}})
            result['checkpoints']=[{'q':q,'record_profit':970,'population_metrics':{},'completed_generations':0}
                                   for q in (5000,10000,20000,50000,100000)]
            result['operator_bins'][0]['total']=100000-job['mu']
            result['source_sha256']={}
            return result
        local=[row(job,'retained' if i<27 else 'new') for i,job in enumerate(identities[:37])]
        plan={'completed':{'file':'not-used','sha256':'not-used'},'remaining':identities[37:],
              'datasets':[{'task':t} for t in tasks],'local_freeze_sha256':'freeze','handoff_snapshot_sha256':'snapshot'}
        files={'log':'journal.json.gz','verification':'verification.json','observations':'observations.json.gz',
               'operator_diagnostics':'operator_bins.json'}
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);shards=base/'shards';out=base/'analysis';shards.mkdir()
            for index in range(4):
                root=shards/f'shard-{index}';root.mkdir();labels=[]
                for pos,job in enumerate(plan['remaining'][index::4]):
                    label=f'case-{index}-{pos}';labels.append(label);folder=root/label;folder.mkdir()
                    item=row(job,'ci_new')
                    (folder/files['log']).write_bytes(b'test-log')
                    checked={'verification_status':'VERIFIED','new_calls':100000-job['mu'],'record_profit':970}
                    (folder/files['verification']).write_text(json.dumps(checked),encoding='utf-8')
                    observed={'record_events':[{'q':1,'profit':970}],'targets':item['targets'],
                              'optimum':1000,'total_evaluations':100000,'final_best_profit':970}
                    with gzip.open(folder/files['observations'],'wt',encoding='utf-8') as stream:json.dump(observed,stream)
                    (folder/files['operator_diagnostics']).write_text(json.dumps({'operator_bins':item['operator_bins']}),encoding='utf-8')
                    hashes={k:sha(folder/name) for k,name in files.items()};item['source_sha256']=hashes
                    (folder/'compact.json').write_text(json.dumps(item),encoding='utf-8')
                    meta={'job':job,'status':'VERIFIED','files':files,'sha256':hashes,
                          'compact_sha256':sha(folder/'compact.json'),'search_seconds':1,'verification_seconds':1,
                          'observations_seconds':1,'log_write_seconds':1}
                    (folder/'record.json').write_text(json.dumps(meta),encoding='utf-8')
                (root/'shard.json').write_text(json.dumps({'status':'COMPLETE','shard':index,
                                      'jobs':labels,'commit':'synthetic'}),encoding='utf-8')
            with patch('studies.knapsack_parameters.crossover_population_refinement_ci.ci_driver.setup',return_value=plan),\
                 patch('studies.knapsack_parameters.crossover_population_refinement_ci.ci_driver.unpack',return_value=local),\
                 patch.dict('os.environ',{'GITHUB_SHA':'synthetic','GITHUB_RUN_ID':'0'}):
                aggregate(shards,out)
            selected=read(out/'selection.json')
            self.assertEqual((selected['mu'],selected['pc_percent'],selected['runs']),(20,90,144))
            self.assertTrue((out/'figures/heatmap-100000.png').is_file())
            self.assertTrue((out/'figures/attainment-99.png').is_file())


if __name__=='__main__':unittest.main()
