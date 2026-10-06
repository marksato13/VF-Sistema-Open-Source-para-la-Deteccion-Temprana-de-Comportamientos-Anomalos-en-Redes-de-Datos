from __future__ import annotations
import csv,json,tempfile,unittest
from pathlib import Path
import subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
class DatasetV2Tests(unittest.TestCase):
 def test_rejects_episode_split(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); (root/'E1').mkdir()
   fields=['campaign_id','entity_ip','window_end_utc','history_coverage_s','eligible_training','packet_count_10s','flow_attempt_count_30s','syn_count_10s','http_request_count_60s','dns_query_count_60s','tcp_data_segment_count_10s','tls_observation_count_60s']+[x['name'] for x in json.loads((ROOT/'configs/features/multilayer-v2.json').read_text())['features']]
   with (root/'E1/multilayer-v2.csv').open('w',newline='') as h:
    w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerow({**{k:'0' for k in fields},'campaign_id':'E1','eligible_training':'True'})
   pm=root/'map.json'; pm.write_text(json.dumps({'E1':'train'})); out=root/'out.csv'
   r=subprocess.run([sys.executable,str(ROOT/'scripts/dataset/build_multilayer_v2_dataset.py'),'--features-root',str(root),'--output',str(out),'--partition-map',str(pm)],capture_output=True,text=True)
   self.assertEqual(r.returncode,0); self.assertTrue(out.exists())
if __name__=='__main__': unittest.main()
