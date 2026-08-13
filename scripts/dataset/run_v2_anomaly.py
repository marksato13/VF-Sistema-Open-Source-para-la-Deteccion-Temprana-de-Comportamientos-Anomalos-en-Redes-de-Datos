#!/usr/bin/env python3
"""Ejecuta perfiles v2 de anomalía aislados de las particiones normales."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PROFILES={
 "ANOM-SYN-RATE-10":("tcp-refused",["10"],"syn_rate_10s,rst_ratio_10s"),
 "ANOM-DNS-NX-200":("dns-nxdomain",["200"],"dns_nxdomain_ratio_60s,dns_query_rate_60s"),
 "ANOM-AUTH-FAIL-50":("api-auth-fail",["50"],"http_auth_failure_ratio_60s,http_request_rate_60s"),
}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--profile',required=True,choices=PROFILES); p.add_argument('--attempt-suffix',default='B'); a=p.parse_args()
 scenario,args,signals=PROFILES[a.profile]; cid=f"F2A-{a.profile}-E01-{a.attempt_suffix}"
 root=Path(os.environ.get('PPI_ARTIFACTS_ROOT','/srv/ppi-evidence/artifacts')).resolve(); cdir=root/'campaigns'/cid; fdir=root/'features-v2'/cid
 if cdir.exists() or fdir.exists(): raise SystemExit(f'ya existe evidencia: {cid}')
 env=os.environ.copy(); env.update(PPI_CAMPAIGN_PURPOSE='evaluation',PPI_CAMPAIGN_PHASE='F2',PPI_CAMPAIGN_WARMUP_SECONDS='60',PPI_CAMPAIGN_SETTLE_SECONDS='9',PPI_CAMPAIGN_PARTITION='evaluation_only',PPI_ARTIFACTS_ROOT=str(root))
 cmd=[str(ROOT/'scripts/campaign/run-f1.sh'),cid,scenario,*args]
 print(json.dumps({'campaign_id':cid,'label':'anomaly','partition':'evaluation_only','expected_signals':signals,'command':cmd},sort_keys=True),flush=True)
 subprocess.run(cmd,cwd=ROOT,env=env,check=True)
 extractor=ROOT/'scripts/features/extract_campaign_v2.sh'; subprocess.run([str(extractor),cid],cwd=ROOT,env=env,check=True)
 manifest=cdir/'manifest.json'; data=json.loads(manifest.read_text()); data.update({'label':'anomaly','evaluation_only':True,'expected_signals':signals,'anomaly_matrix':'multilayer-v2-anomalies'})
 manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'campaign_id':cid,'status':data.get('status'),'rows':json.loads((fdir/'extraction-report.json').read_text()).get('rows')},sort_keys=True))
if __name__=='__main__': main()
