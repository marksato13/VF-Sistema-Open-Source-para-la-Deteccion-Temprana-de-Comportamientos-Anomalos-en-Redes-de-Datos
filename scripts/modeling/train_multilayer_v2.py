#!/usr/bin/env python3
"""Entrenamiento/evaluación reproducible de Isolation Forest multilayer-v2."""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.preprocessing import StandardScaler

META={'episode_id','partition','label','campaign_id','entity_ip','window_end_utc','eligible_training'}
SCHEMA=Path(__file__).resolve().parents[2]/'configs/features/multilayer-v2.json'
def read(path):
    with path.open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
def features(rows):
    contract=json.loads(SCHEMA.read_text(encoding='utf-8'))
    names=[x['name'] for x in sorted(contract['features'],key=lambda x:x['order'])]
    missing=[n for n in names if n not in rows[0]]
    if missing: raise ValueError(f'faltan features del contrato: {missing}')
    return names,np.asarray([[float(r[k]) for k in names] for r in rows],dtype=float)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--normal',type=Path,required=True); ap.add_argument('--anomalies',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    normal=read(a.normal); anomalies=read(a.anomalies)
    train=[r for r in normal if r['partition']=='train']; val=[r for r in normal if r['partition']=='validation']; test=[r for r in normal if r['partition']=='test']
    names,xtrain=features(train); _,xval=features(val); _,xtest=features(test); _,xanom=features(anomalies)
    scaler=StandardScaler().fit(xtrain); ztrain=scaler.transform(xtrain); zval=scaler.transform(xval); ztest=scaler.transform(xtest); zanom=scaler.transform(xanom)
    model=IsolationForest(n_estimators=500,random_state=20260813,contamination='auto',n_jobs=1,max_features=1.0).fit(ztrain)
    # decision_function: higher means more normal; threshold is validation lower tail.
    val_scores=model.decision_function(zval); threshold=float(np.quantile(val_scores,0.05))
    test_scores=model.decision_function(ztest); anomaly_scores=model.decision_function(zanom)
    y=np.r_[np.zeros(len(test_scores)),np.ones(len(anomaly_scores))]; s=np.r_[-test_scores,-anomaly_scores]
    pred=(s >= -threshold).astype(int)
    sensitivity=[]
    for q in (0.05,0.10,0.20,0.30,0.40):
        t=float(np.quantile(val_scores,q)); pp=(s >= -t).astype(int)
        sensitivity.append({'validation_quantile':q,'threshold':t,'validation_false_positive_count':int(np.sum(val_scores<t)),'test_normal_flagged':int(np.sum(test_scores<t)),'anomaly_detected':int(np.sum(anomaly_scores<t)),'confusion_matrix':confusion_matrix(y,pp,labels=[0,1]).tolist()})
    report={'schema_version':'multilayer-v2-model-evaluation','generated_at':datetime.now(timezone.utc).isoformat(),'protocol':'train-only IF; threshold from validation 5th percentile','features':names,'train_rows':len(train),'validation_rows':len(val),'test_rows':len(test),'anomaly_rows':len(anomalies),'threshold_decision_function':threshold,'validation_false_positive_count':int(np.sum(val_scores < threshold)),'test_normal_flagged':int(np.sum(test_scores < threshold)),'anomaly_detected':int(np.sum(anomaly_scores < threshold)),'roc_auc_test_plus_anomaly':float(roc_auc_score(y,s)) if len(set(y))>1 else None,'average_precision_test_plus_anomaly':float(average_precision_score(y,s)),'confusion_matrix_labels_normal_anomaly':confusion_matrix(y,pred,labels=[0,1]).tolist(),'threshold_sensitivity_from_validation':sensitivity,'model_parameters':{'n_estimators':500,'random_state':20260813,'max_features':1.0},'normal_csv_sha256':hashlib.sha256(a.normal.read_bytes()).hexdigest(),'anomaly_csv_sha256':hashlib.sha256(a.anomalies.read_bytes()).hexdigest()}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report,sort_keys=True))
if __name__=='__main__': main()
