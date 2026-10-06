#!/usr/bin/env python3
"""Dashboard local, sin dependencias externas, para el dataset multilayer-v2."""
from __future__ import annotations
import argparse, csv, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = '''<!doctype html><meta charset="utf-8"><title>PPI multilayer-v2</title>
<style>body{font:16px system-ui;margin:2rem;background:#10151c;color:#e8eef5}h1{color:#7dd3fc}.grid{display:flex;gap:1rem;flex-wrap:wrap}.card{background:#1b2633;padding:1rem;border-radius:10px;min-width:180px}table{border-collapse:collapse;width:100%;margin-top:1rem}td,th{padding:.45rem;border-bottom:1px solid #334155;text-align:left}code{color:#bae6fd}</style>
<h1>Sistema PPI — dataset multilayer-v2</h1><p id="stamp"></p><div id="cards" class="grid"></div><h2>Particiones</h2><table><thead><tr><th>Partición</th><th>Filas</th><th>Campañas</th></tr></thead><tbody id="parts"></tbody></table><h2>Features</h2><table><thead><tr><th>Feature</th><th>Min</th><th>Max</th><th>Promedio</th></tr></thead><tbody id="features"></tbody></table>
<script>fetch('/api/summary').then(r=>r.json()).then(x=>{stamp.textContent='Actualizado: '+x.generated_at+' | esquema: '+x.schema_version;cards.innerHTML=[['Filas',x.rows],['Episodios',x.episodes],['Train',x.partitions.train||0],['Validation',x.partitions.validation||0],['Test',x.partitions.test||0]].map(a=>`<div class="card"><b>${a[0]}</b><br><strong>${a[1]}</strong></div>`).join('');parts.innerHTML=Object.entries(x.partition_campaigns).map(([p,v])=>`<tr><td>${p}</td><td>${x.partitions[p]||0}</td><td>${v}</td></tr>`).join('');features.innerHTML=Object.entries(x.features).map(([n,v])=>`<tr><td><code>${n}</code></td><td>${v.min}</td><td>${v.max}</td><td>${v.mean}</td></tr>`).join('')}).catch(e=>document.body.insertAdjacentHTML('beforeend','<p>'+e+'</p>'))</script>'''

def summary(path: Path) -> dict:
    with path.open(newline='', encoding='utf-8') as f: rows=list(csv.DictReader(f))
    numeric=[k for k in rows[0] if k not in {'episode_id','partition','campaign_id','entity_ip','window_end_utc','eligible_training'}] if rows else []
    feats={}
    for k in numeric:
        vals=[]
        for r in rows:
            try: vals.append(float(r[k]))
            except (ValueError,TypeError): pass
        if vals: feats[k]={'min':round(min(vals),6),'max':round(max(vals),6),'mean':round(sum(vals)/len(vals),6)}
    parts={p:sum(r.get('partition')==p for r in rows) for p in ('train','validation','test')}
    campaigns={p:len({r.get('episode_id') for r in rows if r.get('partition')==p}) for p in ('train','validation','test')}
    return {'schema_version':'multilayer-v2-dataset','rows':len(rows),'episodes':len({r.get('episode_id') for r in rows}),'partitions':parts,'partition_campaigns':campaigns,'features':feats}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dataset',type=Path,default=Path('/srv/ppi-evidence/dataset/multilayer-v2.csv')); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8787); a=ap.parse_args()
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/': body=HTML.encode()
            elif self.path=='/api/summary': body=json.dumps({**summary(a.dataset),'generated_at':__import__('datetime').datetime.now().isoformat()}).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(body); return
            else: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    print(f'Dashboard: http://{a.host}:{a.port}/'); ThreadingHTTPServer((a.host,a.port),H).serve_forever()
if __name__=='__main__': main()
