#!/usr/bin/env python3
"""Auditoría reproducible de calidad/procedencia del dataset multilayer-v2."""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/'configs/features/multilayer-v2.json').read_text())
FEATURES=[x['name'] for x in sorted(SCHEMA['features'],key=lambda x:x['order'])]
LAYERS=Counter(x['layer'] for x in SCHEMA['features'])
VALID_PARTITIONS={'train','validation','test','evaluation_only','excluded_calibration'}
def rows(path):
 with path.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--normal',type=Path,required=True);ap.add_argument('--anomalies',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 n=rows(a.normal); z=rows(a.anomalies); allrows=n+z; cols=set(allrows[0]); missing_schema=sorted(set(FEATURES)-cols)
 missing={k:sum(not r.get(k) for r in allrows) for k in FEATURES}; constants={k:len({r[k] for r in allrows}) for k in FEATURES if len({r[k] for r in allrows})<=1}
 vector_keys=[tuple(r[k] for k in FEATURES) for r in allrows]; dup_vectors=len(vector_keys)-len(set(vector_keys))
 by_episode=defaultdict(set)
 for r in allrows: by_episode[r['episode_id']].add(r['partition'])
 split_violations={e:sorted(v) for e,v in by_episode.items() if len(v)>1}
 normal_labels=Counter(r.get('label','normal') for r in n); anomaly_labels=Counter(r.get('label') for r in z)
 invalid_partition_values=sorted({r.get('partition') for r in allrows}-VALID_PARTITIONS)
 report={'schema_version':'multilayer-v2-audit','normal_rows':len(n),'anomaly_rows':len(z),'normal_episodes':len({r['episode_id'] for r in n}),'anomaly_episodes':len({r['episode_id'] for r in z}),'feature_count':len(FEATURES),'layer_feature_counts':dict(LAYERS),'missing_by_feature':missing,'constant_features':constants,'duplicate_feature_vectors_total':dup_vectors,'episode_split_violations':split_violations,'normal_labels':dict(normal_labels),'anomaly_labels':dict(anomaly_labels),'invalid_partition_values':invalid_partition_values,'normal_sha256':hashlib.sha256(a.normal.read_bytes()).hexdigest(),'anomaly_sha256':hashlib.sha256(a.anomalies.read_bytes()).hexdigest(),'gates':{'schema_complete':not missing_schema,'no_missing_values':not any(missing.values()),'no_episode_split':not split_violations,'normal_labels_clean':set(normal_labels)<=({'normal'}),'anomaly_labels_clean':set(anomaly_labels)<=({'anomaly'}),'partition_values_valid':not invalid_partition_values}}
 report['gates']['pass']=all(report['gates'].values());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
