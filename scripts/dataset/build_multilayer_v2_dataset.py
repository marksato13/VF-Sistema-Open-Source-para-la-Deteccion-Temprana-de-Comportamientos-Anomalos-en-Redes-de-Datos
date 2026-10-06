#!/usr/bin/env python3
"""Ensambla CSV v2 elegibles sin repartir un episodio entre particiones."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

FEATURES=tuple(x["name"] for x in sorted(json.loads((Path(__file__).resolve().parents[2]/"configs/features/multilayer-v2.json").read_text())["features"],key=lambda x:x["order"]))
META=("campaign_id","entity_ip","window_end_utc","history_coverage_s","eligible_training","packet_count_10s","flow_attempt_count_30s","syn_count_10s","http_request_count_60s","dns_query_count_60s","tcp_data_segment_count_10s","tls_observation_count_60s")
def main():
 p=argparse.ArgumentParser(); p.add_argument("--features-root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--partition-map",type=Path,required=True); p.add_argument("--label",default="normal",choices=("normal","anomaly")); a=p.parse_args()
 mapping=json.loads(a.partition_map.read_text()); rows=[]; episode_parts={}
 for cid,part in mapping.items():
  path=a.features_root/cid/"multilayer-v2.csv"
  if not path.is_file(): raise SystemExit(f"falta CSV v2: {cid}")
  for row in csv.DictReader(path.open()):
   if row.get("eligible_training") != "True": continue
   row["episode_id"]=cid; row["partition"]=part; row["label"]=a.label; rows.append(row); episode_parts.setdefault(cid,set()).add(part)
 if not rows: raise SystemExit("no hay filas elegibles")
 if any(len(parts)!=1 for parts in episode_parts.values()): raise SystemExit("episodio repartido entre particiones")
 a.output.parent.mkdir(parents=True,exist_ok=True); fields=("episode_id","partition","label",*META,*FEATURES)
 with a.output.open("w",newline="",encoding="utf-8") as h:
  w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
 digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
 report={"schema_version":"multilayer-v2-dataset","rows":len(rows),"episodes":len(episode_parts),"partitions":{p:sum(r["partition"]==p for r in rows) for p in ("train","validation","test")},"sha256":digest,"output":str(a.output)}
 print(json.dumps(report,sort_keys=True))
if __name__=="__main__": main()
