#!/usr/bin/env python3
"""Dashboard operativo de solo lectura para el motor de tiempo real en VM02.

Complementario, no reemplaza otras herramientas de monitoreo (journalctl,
SSH directo al helper de enforcement). No ejecuta ninguna accion: solo lee
el log del motor, el estado del set nftables de enforcement (via el mismo
helper root ya autorizado, subcomando "list" de solo lectura) y el estado de
los servicios systemd relevantes. Ver diseno completo, justificacion de
arquitectura y manual de instalacion/usuario en
docs/fase06-dashboard/01-diseno-dashboard-motor.md.

Sin dependencias externas a proposito: corre con /usr/bin/python3 del
sistema, no con el venv del motor (que tiene scikit-learn/numpy, innecesario
aqui). VM02 esta aislada de internet; agregar una dependencia nueva (p.ej.
Flask) repetiria el esfuerzo de aprovisionamiento offline ya hecho para el
venv del motor, para una ganancia marginal frente a polling simple.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import ssl
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberFlow &middot; motor en vivo</title>
<link id="favicon" rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='13' fill='%235eead4'/%3E%3C/svg%3E">
<style>
  :root {
    --bg: #0a0f1a;
    --surface: #121a2b;
    --surface-2: #1a2338;
    --border: #253150;
    --text: #dbe4f2;
    --text-dim: #7c8bad;
    --accent: #5eead4;
    --ok: #4ade80; --ok-soft: #12271c;
    --amber: #f0b429; --amber-soft: #332508;
    --danger: #f87171; --danger-soft: #351515;
    --mono: ui-monospace, "Cascadia Code", "Roboto Mono", "SF Mono", Menlo, Consolas, monospace;
    --sans: ui-sans-serif, system-ui, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--sans); font-size: 15px; line-height: 1.5;
  }

  /* --- Distribucion: barra lateral fija + contenido --- */
  .shell { display: grid; grid-template-columns: 224px minmax(0, 1fr); }
  .side {
    position: sticky; top: 0; align-self: start; height: 100vh;
    border-right: 1px solid var(--border); background: var(--surface);
    padding: 1.3rem 0.9rem; display: flex; flex-direction: column; gap: 1rem;
    overflow-y: auto;
  }
  .side .brand { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.01em; padding: 0 0.45rem; }
  .side .brand small {
    display: block; font-family: var(--mono); font-size: 0.64rem; color: var(--text-dim);
    font-weight: 400; letter-spacing: 0.05em; text-transform: uppercase; margin-top: 0.15rem;
  }
  .side-state {
    display: flex; align-items: center; gap: 0.5rem; margin: 0 0.45rem;
    font-size: 0.78rem; color: var(--text-dim);
  }
  .side-state .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--text-dim); }
  .side-state.ok .dot { background: var(--ok); box-shadow: 0 0 7px var(--ok); }
  .side-state.warn .dot { background: var(--amber); box-shadow: 0 0 7px var(--amber); }
  .side-state.bad .dot { background: var(--danger); box-shadow: 0 0 7px var(--danger); }
  .side nav { display: flex; flex-direction: column; gap: 0.15rem; }
  .side nav a {
    display: flex; align-items: center; gap: 0.6rem; text-decoration: none;
    color: var(--text-dim); font-size: 0.86rem; padding: 0.46rem 0.55rem; border-radius: 8px;
    border-left: 2px solid transparent;
  }
  .side nav a svg { flex: none; }
  .side nav a:hover { background: var(--surface-2); color: var(--text); }
  .side nav a.active { background: var(--surface-2); color: var(--accent); border-left-color: var(--accent); font-weight: 600; }
  .side nav a .pill {
    margin-left: auto; font-family: var(--mono); font-size: 0.68rem;
    background: var(--danger-soft); color: var(--danger); padding: 0.05rem 0.4rem; border-radius: 999px;
  }
  .side .foot { margin-top: auto; padding: 0 0.45rem; font-size: 0.7rem; color: var(--text-dim); font-family: var(--mono); }

  .wrap { max-width: 1080px; margin: 0 auto; padding: 1.6rem 1.4rem 4rem; }
  section { scroll-margin-top: 1rem; }

  @media (max-width: 900px) {
    .shell { grid-template-columns: 1fr; }
    .side {
      position: static; height: auto; border-right: none; border-bottom: 1px solid var(--border);
      flex-direction: row; align-items: center; gap: 0.8rem; padding: 0.7rem 0.9rem; overflow-x: auto;
    }
    .side .brand small, .side .foot, .side-state span { display: none; }
    .side nav { flex-direction: row; gap: 0.2rem; }
    .side nav a { border-left: none; border-bottom: 2px solid transparent; white-space: nowrap; }
    .side nav a.active { border-left-color: transparent; border-bottom-color: var(--accent); }
  }

  /* --- Topologia --- */
  .topo-wrap {
    display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 1rem;
    align-items: start;
  }
  @media (max-width: 820px) { .topo-wrap { grid-template-columns: 1fr; } }
  .topo-canvas {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.6rem 0.7rem 0.8rem; display: flex; flex-direction: column; min-height: 0;
  }
  .topo-bar {
    display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    padding-bottom: 0.6rem; margin-bottom: 0.6rem; border-bottom: 1px solid var(--border);
  }
  .topo-bar .export-btn { margin-left: auto; padding: 0.3rem 0.6rem; }
  .topo-zoom { display: flex; align-items: center; gap: 0.25rem; font-family: var(--mono); font-size: 0.74rem; color: var(--text-dim); }
  .topo-zoom button {
    font-family: var(--sans); font-size: 0.82rem; line-height: 1; min-width: 24px;
    background: var(--surface-2); color: var(--text-dim); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.25rem 0.45rem; cursor: pointer;
  }
  .topo-zoom button:hover { border-color: var(--accent); color: var(--accent); }
  .topo-zoom #topoNivel { min-width: 38px; text-align: center; }
  .topo-scroll { overflow: auto; flex: 1; min-height: 0; }
  .topo-scroll svg { display: block; }

  /* Pantalla completa: el diagrama manda y el detalle se queda al lado. */
  .topo-wrap:fullscreen { background: var(--bg); padding: 1rem; gap: 1rem; height: 100%; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); }
  .topo-wrap:fullscreen .topo-canvas { height: 100%; }
  .topo-wrap:fullscreen .topo-detail { overflow-y: auto; max-height: 100%; }

  .topo-node { cursor: pointer; }
  .topo-node .box {
    fill: var(--surface-2); stroke: var(--border); stroke-width: 1.2;
    transition: stroke 0.15s, fill 0.15s;
  }
  .topo-node:hover .box { stroke: var(--accent); }
  .topo-node.sel .box { stroke: var(--accent); stroke-width: 2; fill: #16233a; }
  .topo-node.ok .box { stroke: color-mix(in srgb, var(--ok) 55%, var(--border)); }
  .topo-node.warn .box { stroke: color-mix(in srgb, var(--amber) 55%, var(--border)); }
  .topo-node.bad .box { stroke: color-mix(in srgb, var(--danger) 60%, var(--border)); }
  .topo-node .ttl { fill: var(--text); font: 600 12.5px var(--sans); }
  .topo-node .sub { fill: var(--text-dim); font: 11px var(--mono); }
  .topo-node .ico { color: var(--text-dim); }
  .topo-node.ok .ico { color: var(--ok); }
  .topo-node.warn .ico { color: var(--amber); }
  .topo-node.bad .ico { color: var(--danger); }
  .topo-node .led { stroke: none; }
  /* Artefacto = algo que se escribe en disco, no un proceso. Se distingue con
     trazo discontinuo para que el diagrama no mienta sobre qué es cada caja. */
  .topo-node.artefacto .box { stroke-dasharray: 5 4; fill: #101827; }
  .topo-node.sumidero .box { stroke-dasharray: 2 3; fill: #16111a; }
  .topo-node .tag { fill: var(--text-dim); font: 9.5px var(--mono); letter-spacing: 0.06em; }

  .topo-edge { stroke: var(--border); stroke-width: 1.6; fill: none; }
  .topo-edge.live { stroke: var(--accent); stroke-dasharray: 5 6; animation: flow 1.1s linear infinite; }
  .topo-edge.dim { stroke: var(--border); stroke-dasharray: 3 5; }
  .topo-edge.descarte { stroke: var(--danger); opacity: 0.55; stroke-dasharray: 2 4; animation: none; }
  @keyframes flow { to { stroke-dashoffset: -22; } }
  @media (prefers-reduced-motion: reduce) { .topo-edge.live { animation: none; } }
  .topo-edge-label { fill: var(--text-dim); font: 9.5px var(--mono); }
  .topo-grupo { fill: none; stroke: var(--border); stroke-width: 1; stroke-dasharray: 3 4; opacity: 0.6; }
  .topo-grupo-txt { fill: var(--text-dim); font: 9.5px var(--mono); letter-spacing: 0.08em; text-transform: uppercase; }
  .topo-host .box { fill: #101a2e; stroke: color-mix(in srgb, var(--accent) 35%, var(--border)); }
  .topo-host:hover .box { stroke: var(--accent); }
  .topo-host .ico { color: var(--accent); }
  .topo-host .hostip { fill: var(--accent); font: 10.5px var(--mono); }
  .topo-pkt { fill: var(--accent); filter: drop-shadow(0 0 4px var(--accent)); }
  @media (prefers-reduced-motion: reduce) { .topo-pkt { display: none; } }
  .topo-cmd { background: #0b1220; border: 1px solid var(--border); border-radius: 7px;
    padding: 0.5rem 0.6rem; margin: 0.5rem 0; font: 11px var(--mono); color: var(--text-dim);
    white-space: pre-wrap; overflow-x: auto; }
  /* Mapa de artefactos: los "cuadraditos" de ficheros por componente. */
  .export-btn.active { border-color: var(--accent); color: var(--accent); }
  .topo-node .fbadge { fill: var(--accent); font: 9px var(--mono); }
  .topo-node.tiene-archivos .box { stroke-dasharray: none; }
  .topo-files { margin: 0.5rem 0 0.2rem; }
  .topo-files h4 { font: 600 0.72rem var(--sans); letter-spacing: 0.05em;
    text-transform: uppercase; color: var(--text-dim); margin: 0 0 0.4rem; }
  .topo-file { display: inline-flex; align-items: center; gap: 0.35rem; cursor: pointer;
    font: 11px var(--mono); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.22rem 0.45rem; margin: 0 0.3rem 0.3rem 0; background: var(--surface);
    color: var(--text); transition: border-color .12s; }
  .topo-file:hover { border-color: var(--accent); }
  .topo-file[aria-expanded="true"] { border-color: var(--accent); background: var(--surface-2); }
  .topo-file .cuadro { width: 9px; height: 9px; border-radius: 2px; flex: none; }
  /* Color por tipo de fichero (paleta validada: py teal, json azul, csv ambar,
     pcap violeta; el resto en tinta tenue). El color va en el cuadradito, el
     texto queda en tinta normal -identidad por la marca, no por el texto-. */
  .tipo-py .cuadro   { background: #14b8a6; }
  .tipo-json .cuadro, .tipo-toml .cuadro { background: #3b82f6; }
  .tipo-csv .cuadro  { background: #d97706; }
  .tipo-pcap .cuadro { background: #a855f7; }
  .tipo-joblib .cuadro { background: #4ade80; }
  .tipo-log .cuadro, .tipo-sh .cuadro { background: var(--text-dim); }
  .topo-file-det { font: 11px var(--mono); color: var(--text-dim);
    border-left: 2px solid var(--border); padding: 0.3rem 0 0.3rem 0.6rem; margin: 0 0 0.5rem; }
  .topo-file-det .ruta { color: var(--text); word-break: break-all; }
  .topo-file-det .aus { color: var(--amber); }
  /* Mini-flujo de reentrenamiento en el detalle. */
  .topo-flujo { margin: 0.6rem 0 0.3rem; }
  .topo-flujo h4 { font: 600 0.72rem var(--sans); letter-spacing: 0.05em;
    text-transform: uppercase; color: var(--text-dim); margin: 0 0 0.5rem; }
  .topo-flujo .paso { display: flex; gap: 0.55rem; align-items: flex-start; }
  .topo-flujo .n { flex: none; width: 20px; height: 20px; border-radius: 50%;
    background: var(--surface-2); border: 1px solid var(--accent); color: var(--accent);
    font: 600 11px var(--mono); display: grid; place-items: center; }
  .topo-flujo .tit { font: 600 0.82rem var(--sans); color: var(--text); display: flex;
    gap: 0.5rem; align-items: baseline; flex-wrap: wrap; }
  .topo-flujo .tit code { font: 10.5px var(--mono); color: var(--accent);
    background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
    padding: 0.05rem 0.3rem; }
  .topo-flujo .gar { font-size: 0.76rem; color: var(--text-dim); margin-top: 0.1rem; }
  .topo-flujo .flecha { color: var(--text-dim); margin: 0.1rem 0 0.1rem 0.5rem; font-size: 0.9rem; }
  /* Escenarios de simulacion. */
  .sim-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 0.9rem; margin-top: 0.9rem; }
  .sim-card { border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; background: var(--surface); }
  .sim-card h3 { margin: 0 0 0.1rem; font-size: 0.98rem; }
  .sim-card .donde { font: 11px var(--mono); color: var(--accent); margin-bottom: 0.5rem; }
  .sim-card .explica { font-size: 0.84rem; color: var(--text-dim); margin: 0 0 0.6rem; }
  .sim-cmd { position: relative; background: #0b1220; border: 1px solid var(--border);
    border-radius: 7px; padding: 0.5rem 2.4rem 0.5rem 0.6rem; margin: 0 0 0.6rem;
    font: 11px var(--mono); color: var(--text); white-space: pre-wrap; word-break: break-all; }
  .sim-copiar { position: absolute; top: 0.35rem; right: 0.35rem; font: 10px var(--sans);
    cursor: pointer; border: 1px solid var(--border); border-radius: 5px; padding: 0.15rem 0.4rem;
    background: var(--surface-2); color: var(--text-dim); }
  .sim-copiar:hover { border-color: var(--accent); color: var(--accent); }
  .sim-vars { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
  .sim-var { font: 10.5px var(--mono); background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 5px; padding: 0.1rem 0.4rem; color: var(--text-dim); }
  .sim-resp { font-size: 0.82rem; border-left: 2px solid var(--accent); padding-left: 0.6rem; color: var(--text); }
  .sim-card.peligro .sim-resp { border-left-color: var(--amber); }

  .topo-detail {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 1rem 1.1rem; min-height: 100%;
  }
  .topo-detail h3 { margin: 0 0 0.15rem; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem; }
  .topo-detail .state {
    font-family: var(--mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
    padding: 0.1rem 0.5rem; border-radius: 999px; background: var(--surface-2); color: var(--text-dim);
  }
  .topo-detail .state.ok { background: var(--ok-soft); color: var(--ok); }
  .topo-detail .state.warn { background: var(--amber-soft); color: var(--amber); }
  .topo-detail .state.bad { background: var(--danger-soft); color: var(--danger); }
  .topo-detail p { font-size: 0.87rem; color: var(--text); margin: 0.7rem 0 0; }
  .topo-detail p.dim { color: var(--text-dim); font-size: 0.82rem; }
  .topo-detail dl { display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 0.8rem; margin: 0.9rem 0 0; font-size: 0.83rem; }
  .topo-detail dt { color: var(--text-dim); }
  .topo-detail dd { margin: 0; font-family: var(--mono); font-variant-numeric: tabular-nums; }
  header { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1.4rem; }
  h1 { font-size: 1.35rem; margin: 0; letter-spacing: -0.01em; }
  h1 small { display: block; font-family: var(--mono); font-size: 0.72rem; color: var(--text-dim); font-weight: 400; margin-top: 0.15rem; letter-spacing: 0.04em; text-transform: uppercase; }
  .stamp { font-family: var(--mono); font-size: 0.78rem; color: var(--text-dim); }

  .healthbar {
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.85rem 1.1rem; border-radius: 12px; margin-bottom: 1.6rem;
    border: 1px solid var(--border); background: var(--surface);
  }
  .healthbar.ok { border-color: color-mix(in srgb, var(--ok) 45%, var(--border)); }
  .healthbar.warn { border-color: color-mix(in srgb, var(--amber) 45%, var(--border)); }
  .healthbar.bad { border-color: color-mix(in srgb, var(--danger) 45%, var(--border)); }
  .healthbar .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .healthbar.ok .dot { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
  .healthbar.warn .dot { background: var(--amber); box-shadow: 0 0 8px var(--amber); }
  .healthbar.bad .dot { background: var(--danger); box-shadow: 0 0 8px var(--danger); }
  .healthbar .msg { font-weight: 600; }
  .healthbar .sub { color: var(--text-dim); font-size: 0.86rem; }

  section { margin-bottom: 2.2rem; }
  .sec-head { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.8rem; color: var(--text-dim); }
  .sec-head svg { color: var(--accent); flex: none; }
  .sec-head h2 { font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin: 0; color: var(--text-dim); }
  .sec-head-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.6rem; }
  .sec-head-row .sec-head { margin-bottom: 0; }
  .range-toggle { display: flex; gap: 0.3rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.2rem; }
  .range-toggle button {
    font-family: var(--sans); font-size: 0.78rem; border: none; background: transparent; color: var(--text-dim);
    padding: 0.3rem 0.7rem; border-radius: 6px; cursor: pointer;
  }
  .range-toggle button.active { background: var(--accent); color: var(--bg); font-weight: 600; }

  .toolbar { display: flex; gap: 0.5rem; align-items: center; }
  .ip-filter {
    font-family: var(--mono); font-size: 0.85rem; background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px; padding: 0.4rem 0.7rem; width: 160px;
  }
  .ip-filter:focus { outline: 1.5px solid var(--accent); border-color: var(--accent); }
  .export-btn {
    display: inline-flex; align-items: center; gap: 0.4rem; font-family: var(--sans); font-size: 0.82rem;
    background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
    padding: 0.4rem 0.8rem; cursor: pointer;
  }
  .export-btn:hover { border-color: var(--accent); color: var(--accent); }
  .toolbar-hint { font-size: 0.78rem; color: var(--text-dim); margin: 0.4rem 0 0; min-height: 1em; }
  .lede-small { font-size: 0.86rem; color: var(--text-dim); margin: -0.3rem 0 0.8rem; }

  /* Cabecera de sesion: quien eres, en que modo y como salir. */
  .sesion { display: flex; align-items: center; gap: 0.6rem; margin-left: auto; }
  .sesion form { margin: 0; }
  .quien { font-size: 0.78rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .btn-modo, .btn-salir {
    font: inherit; font-size: 0.78rem; cursor: pointer; padding: 0.3rem 0.7rem;
    border-radius: 7px; border: 1px solid var(--border);
    background: var(--surface); color: var(--text-dim); transition: border-color .15s, color .15s;
  }
  .btn-modo:hover, .btn-salir:hover { border-color: var(--accent); color: var(--text); }
  .btn-modo[data-modo="desarrollo"] { border-color: var(--accent); color: var(--accent); }
  /* El lector no recibe las secciones de desarrollo, asi que su barra lateral
     es mas corta; nada que ocultar aqui, el marcado ya no las trae. */

  /* Fila de KPIs: las cuatro cifras que importan de un vistazo. */
  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.8rem; margin-bottom: 1.1rem; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 0.8rem 1rem; position: relative; }
  .kpi .k-lab { font: 0.72rem var(--sans); letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--text-dim); }
  .kpi .k-val { font: 700 1.9rem var(--sans); color: var(--text); font-variant-numeric: tabular-nums;
    line-height: 1.15; margin-top: 0.15rem; }
  .kpi .k-val small { font-size: 0.9rem; font-weight: 600; color: var(--text-dim); }
  .kpi .k-sub { font: 0.74rem var(--sans); color: var(--text-dim); margin-top: 0.1rem; }
  .kpi .k-dot { position: absolute; top: 0.9rem; right: 0.9rem; width: 9px; height: 9px; border-radius: 50%; }
  .kpi.ok .k-dot { background: var(--ok); }
  .kpi.warn .k-dot { background: var(--amber); }
  .kpi.bad .k-dot { background: var(--danger); }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.8rem; }

  /* Variables por capa. La cabecera de capa es un boton: filtra la tabla. */
  .var-capas { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.6rem; margin-bottom: 0.9rem; }
  .var-capa {
    text-align: left; cursor: pointer; font: inherit; color: inherit;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.6rem 0.7rem; transition: border-color .15s, background .15s;
  }
  .var-capa:hover { border-color: var(--accent); }
  .var-capa[aria-pressed="true"] { background: var(--surface-2); border-color: var(--accent); }
  .var-capa .cid { font-size: 0.7rem; letter-spacing: .06em; color: var(--accent); font-weight: 700; }
  .var-capa .cn { font-size: 0.95rem; font-weight: 600; margin-top: 0.1rem; }
  .var-capa .cc { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.15rem; }

  .var-tabla { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .var-grupo { font-size: 0.72rem; letter-spacing: .07em; text-transform: uppercase;
    color: var(--text-dim); background: var(--surface-2); padding: 0.4rem 0.8rem;
    border-bottom: 1px solid var(--border); }
  .var-fila {
    display: grid; grid-template-columns: 1fr auto auto; gap: 0.6rem; align-items: center;
    width: 100%; text-align: left; font: inherit; color: inherit; cursor: pointer;
    background: none; border: none; border-bottom: 1px solid var(--border);
    padding: 0.55rem 0.8rem; transition: background .12s;
  }
  .var-fila:hover { background: var(--surface-2); }
  .var-fila[aria-expanded="true"] { background: var(--surface-2); }
  .var-fila .vn { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; }
  .var-fila .vq { display: block; font-size: 0.76rem; color: var(--text-dim); margin-top: 0.12rem;
    font-family: inherit; }
  .var-fila .vw { font-size: 0.72rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .var-chev { width: 14px; height: 14px; transition: transform .15s; color: var(--text-dim); }
  .var-fila[aria-expanded="true"] .var-chev { transform: rotate(90deg); color: var(--accent); }
  .var-badge { font-size: 0.64rem; letter-spacing: .05em; padding: 0.1rem 0.35rem;
    border-radius: 4px; background: var(--amber-soft); color: var(--amber); margin-left: 0.4rem; }
  .var-det { padding: 0.1rem 0.8rem 0.8rem; border-bottom: 1px solid var(--border);
    background: var(--surface-2); font-size: 0.82rem; }
  .var-det p { margin: 0.3rem 0 0.6rem; color: var(--text-dim); }
  .var-det .stats { display: flex; flex-wrap: wrap; gap: 0.4rem 1.2rem; margin-bottom: 0.5rem;
    font-variant-numeric: tabular-nums; }
  .var-det .stats b { color: var(--text); font-weight: 600; }
  .var-ej { width: 100%; border-collapse: collapse; font-size: 0.76rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .var-ej th { text-align: left; color: var(--text-dim); font-weight: 500; padding: 0.2rem 0.5rem 0.2rem 0;
    font-family: inherit; }
  .var-ej td { padding: 0.2rem 0.5rem 0.2rem 0; color: var(--text); }
  .var-vacio { padding: 0.9rem 0.8rem; color: var(--text-dim); font-size: 0.82rem; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--border);
    border-radius: 10px; padding: 0.8rem 1rem;
  }
  .card.ok { border-left-color: var(--ok); }
  .card.bad { border-left-color: var(--danger); }
  .card .label { font-size: 0.74rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; }
  .card .value { font-family: var(--mono); font-size: 1.25rem; font-weight: 700; margin-top: 0.15rem; font-variant-numeric: tabular-nums; }
  .card.ok .value { color: var(--ok); }
  .card.bad .value { color: var(--danger); }
  .card.accent .value { color: var(--accent); }
  .card.amber .value { color: var(--amber); }

  .note {
    display: flex; gap: 0.6rem; align-items: flex-start;
    border-left: 3px solid var(--amber); background: var(--amber-soft);
    border-radius: 0 10px 10px 0; padding: 0.7rem 1rem; font-size: 0.86rem; color: var(--text);
  }
  .note svg { color: var(--amber); flex: none; margin-top: 0.1rem; }

  .spark-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; overflow-x: auto; position: relative; }
  .spark-legend { display: flex; gap: 1.1rem; font-size: 0.76rem; color: var(--text-dim); margin-top: 0.5rem; }
  .spark-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
  .swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

  /* Tooltip de la grafica de actividad: sigue al raton con una cruz de
     referencia y muestra las dos series -PERMIT y ALERT- del intervalo. */
  .chart-tip { position: absolute; top: 6px; transform: translateX(-50%); pointer-events: none;
    z-index: 3; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px;
    padding: 0.35rem 0.55rem; font-size: 0.72rem; line-height: 1.35; color: var(--text);
    box-shadow: 0 4px 14px rgba(0,0,0,0.35); white-space: nowrap; visibility: hidden; }
  .chart-tip .t-when { color: var(--text-dim); margin-bottom: 0.15rem; }
  .chart-tip b { font-variant-numeric: tabular-nums; }
  .chart-tip .t-p { color: var(--ok); } .chart-tip .t-a { color: var(--danger); }

  table { border-collapse: collapse; width: 100%; font-size: 0.86rem; }
  .tbl-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; overflow-x: auto; }
  th { text-align: left; padding: 0.6rem 0.9rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); border-bottom: 1px solid var(--border); }
  th .th-sub { text-transform: none; letter-spacing: 0; font-weight: 400; opacity: 0.75; }
  td { padding: 0.5rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr.row-alert td:first-child { box-shadow: inset 3px 0 0 var(--danger); }
  .ip, .num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .empty-row td { color: var(--text-dim); text-align: center; padding: 1.1rem; }

  .badge { display: inline-flex; align-items: center; gap: 0.35rem; font-family: var(--mono); font-size: 0.76rem; padding: 0.18rem 0.55rem; border-radius: 999px; font-weight: 600; }
  .badge.alert { background: var(--danger-soft); color: var(--danger); }
  .badge.permit { background: var(--ok-soft); color: var(--ok); }
  .badge.heur { background: var(--surface-2); color: var(--text-dim); }
  .why { color: var(--text-dim); font-size: 0.82rem; }

  /* Tabla de decisiones: cabecera fija al desplazar la lista larga, y la celda
     de score lleva una mini-barra que situa el valor respecto al umbral. */
  .tbl-scroll { max-height: 420px; overflow-y: auto; }
  .tbl-scroll thead th { position: sticky; top: 0; z-index: 1; background: var(--surface);
    box-shadow: inset 0 -1px 0 var(--border); }
  .score-cell { display: inline-flex; align-items: center; gap: 0.5rem; }
  .score-cell .mini { flex: none; }
</style>

<div class="shell">
<aside class="side">
  <div class="brand">CyberFlow<small>Motor en vivo</small></div>
  <div class="side-state" id="sideState"><span class="dot"></span><span id="sideStateText">conectando&hellip;</span></div>
  <nav id="nav">
    <a href="#s-salud" data-sec="s-salud"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/></svg>Salud</a>
    <!--ADMIN-->
    <a href="#s-topologia" data-sec="s-topologia"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg>Topología</a>
    <a href="#s-variables" data-sec="s-variables"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><line x1="3" y1="9.5" x2="21" y2="9.5"/><line x1="9" y1="9.5" x2="9" y2="20"/></svg>Variables</a>
    <a href="#s-modelo" data-sec="s-modelo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>Modelo</a>
    <a href="#s-alcance" data-sec="s-alcance"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><line x1="5" y1="19" x2="19" y2="5"/></svg>Alcance</a>
    <a href="#s-simulacion" data-sec="s-simulacion"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="6,4 20,12 6,20"/></svg>Simulación</a>
    <!--/ADMIN-->
    <a href="#s-scores" data-sec="s-scores"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg>Scores</a>
    <a href="#s-actividad" data-sec="s-actividad"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,12 7,12 9,6 13,18 15,12 22,12"/></svg>Actividad<span class="pill" id="navAlertPill" hidden></span></a>
    <a href="#s-bloqueos" data-sec="s-bloqueos"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>Bloqueos</a>
    <a href="#s-decisiones" data-sec="s-decisiones"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>Decisiones</a>
  </nav>
  <div class="foot">SOLO LECTURA</div>
</aside>

<div class="wrap">
  <header>
    <h1>CyberFlow<small>Motor en vivo &middot; solo lectura</small></h1>
    <span class="stamp" id="stamp"></span>
    <div class="sesion">
      <!--ADMIN--><button id="modoBtn" class="btn-modo" type="button"
        title="Cambia entre la vista operativa y la de desarrollo. Las dos son de solo lectura."></button><!--/ADMIN-->
      <span class="quien" id="quien"></span>
      <form method="post" action="/logout"><button class="btn-salir" type="submit">Salir</button></form>
    </div>
  </header>

  <div class="kpi-row" id="kpis"></div>
  <div class="healthbar" id="healthbar"></div>

  <section id="s-salud">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.9" fill="currentColor" stroke="none"/></svg><h2>Salud del sistema</h2></div>
    <div class="grid" id="health"></div>
  </section>

  <!--ADMIN-->
  <section id="s-topologia">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg><h2>Topología y flujo</h2></div>
    <p class="lede-small">El camino que recorre un paquete desde el troncal hasta la decisión. Pulsa un componente para ver qué hace, qué mide y de dónde sale ese número.</p>
    <div class="topo-wrap" id="topoWrap">
      <div class="topo-canvas" id="topoCanvas">
        <div class="topo-bar">
          <div class="range-toggle" id="topoVista">
            <button data-vista="esencial" class="active">Esencial</button>
            <button data-vista="completa">Completa</button>
          </div>
          <div class="topo-zoom">
            <button id="topoMenos" title="Reducir" aria-label="Reducir">&minus;</button>
            <span id="topoNivel">100%</span>
            <button id="topoMas" title="Ampliar" aria-label="Ampliar">+</button>
            <button id="topoReset" title="Ajustar al ancho" aria-label="Ajustar al ancho">Ajustar</button>
          </div>
          <button id="topoArchivosBtn" class="export-btn" title="Muestra los ficheros que usa cada componente" aria-pressed="false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h6l2 3h8v13H4Z"/></svg>
            <span>Ver archivos</span>
          </button>
          <button id="topoExpandir" class="export-btn" title="Pantalla completa">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6"/></svg>
            <span id="topoExpandirTxt">Expandir</span>
          </button>
        </div>
        <div class="topo-scroll" id="topoScroll">
          <svg id="topo" role="img" aria-label="Diagrama de arquitectura y flujo de CyberFlow"></svg>
        </div>
      </div>
      <div class="topo-detail" id="topoDetail"></div>
    </div>
  </section>

  <section id="s-variables">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><line x1="3" y1="9.5" x2="21" y2="9.5"/><line x1="9" y1="9.5" x2="9" y2="20"/></svg><h2>Variables por capa</h2></div>
    <p class="lede-small">Qué mide el sistema en cada capa del modelo OSI. Pulsa una fila para ver su explicación y valores reales tomados del dataset que se está acumulando.</p>
    <div class="var-capas" id="varCapas"></div>
    <div class="var-tabla" id="varTabla"></div>
    <p class="toolbar-hint" id="varPie"></p>
  </section>

  <section id="s-modelo">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/><line x1="2" y1="9" x2="6" y2="9"/><line x1="2" y1="15" x2="6" y2="15"/><line x1="18" y1="9" x2="22" y2="9"/><line x1="18" y1="15" x2="22" y2="15"/></svg><h2>Modelo congelado</h2></div>
    <div class="grid" id="model"></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="16.5" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Punto débil conocido:</strong> este modelo detecta peor la fuerza bruta de contraseñas (50&ndash;55%) que el resto de familias de ataque (&gt;80%). Una decisión PERMIT en ese escenario es menos confiable que en otros.</span></div>
  </section>

  <section id="s-alcance">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="5" y1="19" x2="19" y2="5"/></svg><h2>Alcance del análisis</h2></div>
    <p class="lede-small">Lo que se captura pero NO se puntúa, y por qué. Declararlo con su cifra es parte del método: sin número, «se excluyó» no es una medición.</p>
    <div class="grid" id="alcance"></div>
    <p class="toolbar-hint" id="alcanceDetalle"></p>
  </section>

  <section id="s-simulacion">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="6,4 20,12 6,20"/></svg><h2>Simulación de escenarios</h2></div>
    <p class="lede-small">Cada escenario trae su explicación y el comando exacto para copiar y pegar en TU terminal SSH. El panel no ejecuta nada: solo guía y luego verás la respuesta del modelo en Actividad y Decisiones.</p>
    <div class="range-toggle" id="simTabs">
      <button data-sim="normal" class="active">Tráfico normal</button>
      <button data-sim="anomalo">Tráfico anómalo</button>
    </div>
    <div class="sim-grid" id="simGrid"></div>
  </section>
  <!--/ADMIN-->

  <section id="s-scores">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg><h2>Distribución de scores recientes</h2></div>
    <p class="lede-small">Qué tan cerca del umbral está pasando el tráfico reciente &mdash; no solo si alertó o no, sino cuánto margen hubo. La línea marca el umbral operativo.</p>
    <div class="spark-wrap">
      <svg id="histogram" width="100%" height="90" viewBox="0 0 610 90" preserveAspectRatio="none"></svg>
      <p class="toolbar-hint" id="histogramHint"></p>
    </div>
  </section>

  <section id="s-actividad">
    <div class="sec-head-row">
      <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,12 7,12 9,6 13,18 15,12 22,12"/></svg><h2>Actividad</h2></div>
      <div class="range-toggle" id="rangeToggle">
        <button data-range="1h" class="active">Última hora</button>
        <button data-range="24h">Últimas 24h</button>
      </div>
    </div>
    <div class="grid" id="counters"></div>
    <div class="spark-wrap">
      <svg id="spark" width="100%" height="46" viewBox="0 0 610 46" preserveAspectRatio="none"></svg>
      <div class="chart-tip" id="sparkTip"></div>
      <div class="spark-legend">
        <span><i class="swatch" style="background:var(--danger)"></i>intervalo con ALERT</span>
        <span><i class="swatch" style="background:var(--accent)"></i>solo PERMIT</span>
        <span><i class="swatch" style="background:var(--border)"></i>sin tráfico</span>
        <span id="sparkRangeLabel">&larr; hace 60 min&nbsp;&nbsp;&nbsp;ahora &rarr;</span>
      </div>
    </div>
  </section>

  <section id="s-bloqueos">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg><h2>IPs bloqueadas ahora</h2></div>
    <div class="tbl-wrap">
      <table><thead><tr><th>IP</th><th>Expira en</th></tr></thead><tbody id="blocked"></tbody></table>
    </div>
  </section>

  <section id="s-decisiones">
    <div class="sec-head-row">
      <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg><h2>Decisiones recientes</h2></div>
      <div class="toolbar">
        <input type="text" id="ipFilter" placeholder="Filtrar por IP..." class="ip-filter">
        <button id="exportCsv" class="export-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><polyline points="7,10 12,15 17,10"/><path d="M4 18v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          Exportar CSV
        </button>
      </div>
    </div>
    <p class="toolbar-hint" id="filterHint"></p>
    <div class="tbl-wrap tbl-scroll">
      <table>
        <thead><tr><th>Hora</th><th>IP</th><th>Decisión</th><th>Motivo</th><th>Score <span class="th-sub">(← umbral)</span></th><th>Paquetes</th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>
</div>

<!-- Quien ha iniciado sesion, puesto por el servidor al servir la pagina. Es
     informativo: el rol de verdad se comprueba en cada peticion, y cambiar
     esto en el navegador no da acceso a nada. -->
<script type="application/json" id="datosSesion">__SESION__</script>

<script>
// Solo los iconos usados dinamicamente en refresh(); los estaticos (encabezados
// de seccion, nota de contexto) ya estan inline en el HTML de arriba.
const ICON = {
  ok: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,12 9,17 20,6"/></svg>',
  bad: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>',
};

const DETECTOR_LABEL = {
  empty_window_heuristic: 'sin tráfico (heurístico)',
  no_live_packets_heuristic: 'sin paquetes aún (heurístico)',
  ocsvm_scaled: 'modelo (OCSVM)',
  auth_failure_heuristic: 'fuerza bruta (heurístico)',
};
const SERVICE_LABEL = { 'ppi-motor.service': 'Motor', 'ppi-motor-capture.service': 'Captura', 'suricata.service': 'Suricata' };
let currentRange = '1h';

// Alerta visual en vivo (Seccion B): el dashboard hace polling cada 5s, no
// push -- sin esto, un ALERT real puede pasar desapercibido si el analista
// no esta mirando la tabla justo en ese momento. Solo cambia titulo/favicon
// del propio navegador, no notificaciones del sistema operativo (mas
// invasivo e innecesario para un panel de solo lectura).
const PROTO = { 112: 'VRRP/CARP (latido del cortafuegos)', 240: 'pfsync (sincronización entre cortafuegos)' };
const BASE_TITLE = document.title;
const BASE_FAVICON = document.getElementById('favicon').href;
const ALERT_FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='13' fill='%235eead4'/%3E%3Ccircle cx='24' cy='9' r='7' fill='%23f87171' stroke='%230a0f1a' stroke-width='1.5'/%3E%3C/svg%3E";
const seenDecisionKeys = new Set();
let unseenAlertCount = 0;
let sessionStart = true; // evita contar todo el historial como "nuevo" en la primera carga

function markSeenAndCountNewAlerts(decisions) {
  let newAlerts = 0;
  for (const d of decisions) {
    const key = d.entity_ip + '|' + d.window_end_utc;
    if (seenDecisionKeys.has(key)) continue;
    seenDecisionKeys.add(key);
    if (!sessionStart && d.decision === 'ALERT') newAlerts++;
  }
  sessionStart = false;
  if (seenDecisionKeys.size > 5000) {
    // evita crecimiento sin limite en una sesion de navegador larga
    const it = seenDecisionKeys.values();
    for (let i = 0; i < 1000; i++) seenDecisionKeys.delete(it.next().value);
  }
  if (newAlerts > 0 && document.visibilityState !== 'visible') {
    unseenAlertCount += newAlerts;
    document.title = `(${unseenAlertCount}) ` + BASE_TITLE;
    document.getElementById('favicon').href = ALERT_FAVICON;
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && unseenAlertCount > 0) {
    unseenAlertCount = 0;
    document.title = BASE_TITLE;
    document.getElementById('favicon').href = BASE_FAVICON;
  }
});

function card(label, value, cls) {
  return `<div class="card ${cls||''}"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
function fmtTime(t) {
  return new Date(t * 1000).toLocaleTimeString();
}

// Fila de KPIs: las cuatro cifras que un operador mira primero. Todo sale de
// datos ya cargados (contadores + el resumen del histograma); nada inventado.
function renderKpis(status) {
  const el = document.getElementById('kpis');
  if (!el) return;
  const c = status.counters || {};
  const cal = status.calibracion && status.calibracion.calibrado_en_esta_red;
  const alertas = c.alert_model || 0;
  const hr = window._histResumen;
  const tile = (lab, val, sub, estado) =>
    `<div class="kpi ${estado || ''}"><div class="k-dot"></div>`
    + `<div class="k-lab">${lab}</div><div class="k-val">${val}</div>`
    + `<div class="k-sub">${sub}</div></div>`;
  el.innerHTML =
    tile('Entidades vigiladas', c.entidades != null ? c.entidades : '—', 'última hora', '') +
    tile('Ventanas/h', (c.total != null ? c.total : 0).toLocaleString('es'), 'analizadas', '') +
    tile('Cerca del umbral', hr ? hr.pct + '<small>%</small>' : '—',
         hr ? hr.bajoUmbral + ' de ' + hr.n + ' scores' : 'sin scores', hr && hr.pct > 20 ? 'warn' : '') +
    tile('Alertas reales (1h)', alertas,
         cal ? 'modelo calibrado' : 'modelo sin calibrar: ruido',
         !cal ? 'warn' : (alertas > 0 ? 'bad' : 'ok'));
}

function renderHealthbar(services, counters, captureMetrics, calibracion) {
  const allUp = Object.values(services).every(Boolean);
  const el = document.getElementById('healthbar');
  const hasDrops = captureMetrics && (captureMetrics.kernel_drops > 0 || captureMetrics.kernel_ifdrops > 0);
  const nAlertas = counters.alert_model + counters.alert_auth_heuristic;
  // Un modelo calibrado en otra red no mide nada aqui: anunciar sus alertas
  // como "reales" es dar una alarma falsa en la primera linea del panel.
  // Medido en este despliegue: 87 % de ALERT sin ningun ataque en curso.
  if (allUp && calibracion && !calibracion.calibrado_en_esta_red) {
    el.className = 'healthbar warn';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Modelo sin calibrar para esta red &mdash; las alertas aun no son fiables</div>` +
      `<div class="sub">El umbral viene de otra red. ${nAlertas} alerta(s) en la última hora: trátalas como ruido hasta recalibrar con tráfico propio.` +
      (hasDrops ? ' Además, Suricata está descartando paquetes.' : '') + `</div></div>`;
    return;
  }
  if (!allUp) {
    el.className = 'healthbar bad';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Atención: un servicio no está activo</div><div class="sub">Revisar con journalctl -- el motor puede no estar observando tráfico real ahora mismo.</div></div>`;
  } else if (counters.alert_model + counters.alert_auth_heuristic > 0) {
    const n = counters.alert_model + counters.alert_auth_heuristic;
    el.className = 'healthbar warn';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Servicios activos &middot; ${n} alerta(s) real(es) en la última hora</div><div class="sub">El sistema está funcionando y respondiendo -- revisar la tabla de decisiones abajo.</div></div>`;
  } else if (hasDrops) {
    el.className = 'healthbar warn';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Atención: Suricata está descartando paquetes</div><div class="sub">Las features del motor pueden estar incompletas mientras esto ocurra -- ver "Paquetes capturados" abajo.</div></div>`;
  } else {
    el.className = 'healthbar ok';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">Todo operando con normalidad</div><div class="sub">Servicios activos, sin alertas reales en la última hora, sin drops de captura.</div></div>`;
  }
}

// La grafica de actividad guarda sus datos para el tooltip; la unidad de tiempo
// depende del rango elegido (minutos en 1h, horas en 24h).
let _sparkData = { activity: [], unidad: 'min' };

function _sparkCuando(b) {
  return b.offset === 0 ? 'ahora' : ('hace ' + b.offset + ' ' + _sparkData.unidad);
}

function renderSparkline(activity) {
  const svg = document.getElementById('spark');
  const n = activity.length;
  const w = 610, h = 46, bw = w / n;
  _sparkData = { activity: activity, unidad: currentRange === '24h' ? 'h' : 'min' };
  let bars = '';
  activity.forEach((b, i) => {
    const total = b.alert + b.permit;
    const x = i * bw;
    let color = 'var(--border)';
    let barH = 3;
    if (total > 0) {
      barH = Math.max(4, Math.min(h - 2, 4 + Math.log2(total + 1) * 9));
      color = b.alert > 0 ? 'var(--danger)' : 'var(--accent)';
    }
    // <title> nativo por barra: el tooltip basico funciona aunque el JS de la
    // cruz falle. La cruz y el recuadro de abajo lo enriquecen, no lo sustituyen.
    bars += `<rect x="${x.toFixed(1)}" y="${(h - barH).toFixed(1)}" width="${Math.max(1, bw - 1.2).toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="${color}">`
      + `<title>${_sparkCuando(b)} · ${b.permit} PERMIT · ${b.alert} ALERT</title></rect>`;
  });
  bars += `<line id="sparkCross" x1="0" y1="0" x2="0" y2="${h}" stroke="var(--text-dim)" stroke-width="1" stroke-dasharray="3 2" visibility="hidden"/>`;
  svg.innerHTML = bars;
}

function _sparkMove(ev) {
  const svg = document.getElementById('spark');
  const tip = document.getElementById('sparkTip');
  const cross = document.getElementById('sparkCross');
  const a = _sparkData.activity;
  if (!svg || !tip || !cross || !a.length) return;
  const rect = svg.getBoundingClientRect();
  let i = Math.floor((ev.clientX - rect.left) / rect.width * a.length);
  i = Math.max(0, Math.min(a.length - 1, i));
  const b = a[i];
  const cx = (i + 0.5) * (610 / a.length);
  cross.setAttribute('x1', cx.toFixed(1));
  cross.setAttribute('x2', cx.toFixed(1));
  cross.setAttribute('visibility', 'visible');
  tip.innerHTML = `<div class="t-when">${_sparkCuando(b)}</div>`
    + `<div><span class="t-p">PERMIT</span> <b>${b.permit}</b></div>`
    + `<div><span class="t-a">ALERT</span> <b>${b.alert}</b></div>`;
  // Situa el recuadro sobre la barra sin salirse del contenedor. Un <svg> no
  // tiene offsetLeft (es API de HTMLElement), asi que se calcula con los rects
  // de cliente respecto al contenedor posicionado.
  const wrapRect = tip.offsetParent.getBoundingClientRect();
  const centroX = rect.left + (i + 0.5) / a.length * rect.width - wrapRect.left;
  const media = tip.offsetWidth / 2;
  tip.style.left = Math.max(media + 2, Math.min(wrapRect.width - media - 2, centroX)).toFixed(0) + 'px';
  tip.style.visibility = 'visible';
}

function _sparkLeave() {
  const tip = document.getElementById('sparkTip');
  const cross = document.getElementById('sparkCross');
  if (tip) tip.style.visibility = 'hidden';
  if (cross) cross.setAttribute('visibility', 'hidden');
}

(function initSpark() {
  const svg = document.getElementById('spark');
  if (svg) {
    svg.addEventListener('mousemove', _sparkMove);
    svg.addEventListener('mouseleave', _sparkLeave);
  }
})();

function renderHistogram(data) {
  const svg = document.getElementById('histogram');
  const hint = document.getElementById('histogramHint');
  if (!data.buckets.length) {
    svg.innerHTML = '';
    hint.textContent = 'Sin scores recientes para graficar (solo hay decisiones del heurístico de ventana vacía).';
    return;
  }
  const w = 610, h = 90, padBottom = 16;
  const maxCount = Math.max(...data.buckets.map(b => b.count), 1);
  const bw = w / data.buckets.length;
  const base = h - padBottom;
  let bars = '';
  let bajoUmbral = 0;
  data.buckets.forEach((b, i) => {
    const barH = b.count > 0 ? Math.max(3, (b.count / maxCount) * (base - 4)) : 0;
    const x = i * bw;
    // Rojo: cubo enteramente en zona ALERT (por debajo del umbral). Verde:
    // enteramente en zona PERMIT. Ambar: el cubo cruza el umbral -- scores
    // ahi mezclan ambas decisiones, la zona mas interesante para mirar.
    let color = 'var(--accent)', zona = 'PERMIT';
    if (b.hi <= data.threshold) { color = 'var(--danger)'; zona = 'ALERT'; bajoUmbral += b.count; }
    else if (b.lo < data.threshold) { color = 'var(--amber)'; zona = 'cruza el umbral'; }
    // Barra con tope redondeado (spec de marcas) y, encima, un area invisible de
    // toda la altura como diana de hover: el <title> da el tooltip nativo sin
    // depender de JS -robusto, y el raton no tiene que acertar la barra fina-.
    if (barH > 0)
      bars += `<rect x="${x.toFixed(1)}" y="${(base - barH).toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${barH.toFixed(1)}" rx="2" fill="${color}"/>`;
    bars += `<rect x="${x.toFixed(1)}" y="0" width="${bw.toFixed(1)}" height="${base}" fill="transparent">`
      + `<title>score ${b.lo.toFixed(3)} a ${b.hi.toFixed(3)} · ${b.count} ventana(s) · ${zona}</title></rect>`;
  });
  const thresholdX = ((data.threshold - data.min) / (data.max - data.min)) * w;
  bars += `<line x1="${thresholdX.toFixed(1)}" y1="0" x2="${thresholdX.toFixed(1)}" y2="${base}" stroke="var(--text)" stroke-width="1.3" stroke-dasharray="3 2"/>`;
  bars += `<text x="${Math.min(w - 40, thresholdX + 4).toFixed(1)}" y="10" font-size="9" fill="var(--text)" font-family="ui-monospace, monospace">umbral ${data.threshold.toFixed(2)}</text>`;
  // Eje X: score minimo y maximo, para que las barras tengan escala.
  bars += `<text x="2" y="${h - 3}" font-size="9" fill="var(--text-dim)" font-family="ui-monospace, monospace">${data.min.toFixed(2)}</text>`;
  bars += `<text x="${w - 2}" y="${h - 3}" font-size="9" fill="var(--text-dim)" text-anchor="end" font-family="ui-monospace, monospace">${data.max.toFixed(2)}</text>`;
  svg.innerHTML = bars;
  const pct = data.n ? Math.round(100 * bajoUmbral / data.n) : 0;
  window._histResumen = { pct: pct, n: data.n, bajoUmbral: bajoUmbral };
  // La misma escala del histograma la reusa la mini-barra de la tabla.
  window._escalaScore = { min: data.min, max: data.max, umbral: data.threshold };
  hint.textContent = `${data.n} score(s) real(es) · ${bajoUmbral} (${pct}%) por debajo del umbral. `
    + `Pasa el ratón por una barra para ver su rango. Rojo = ALERT, ámbar = cruza el umbral, verde = PERMIT.`;
}

async function loadActivity(range) {
  const data = await (await fetch('/api/activity?range=' + range)).json();
  renderSparkline(data.activity);
  document.getElementById('sparkRangeLabel').textContent = range === '24h'
    ? '← hace 24h    ahora →'
    : '← hace 60 min    ahora →';
}

on('rangeToggle', 'click', (e) => {
  const btn = e.target.closest('button[data-range]');
  if (!btn) return;
  currentRange = btn.dataset.range;
  document.querySelectorAll('#rangeToggle button').forEach(b => b.classList.toggle('active', b === btn));
  loadActivity(currentRange);
});

// El lector no recibe las secciones de desarrollo, asi que sus elementos NO
// existen en su documento. Un addEventListener sobre null lanza TypeError y
// aborta el script entero -se quedaria sin panel, no sin una seccion-. Este
// ayudante hace que la ausencia sea silenciosa y esperada.
function on(id, evento, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(evento, fn);
}

async function refresh() {
  try {
    // El histograma se pide junto al estado para que la tarjeta "Cerca del
    // umbral" tenga su cifra ya en la primera pintada, no un ciclo despues.
    const [statusRes, histRes] = await Promise.all([
      fetch('/api/status'), fetch('/api/score-histogram')]);
    const status = await statusRes.json();
    const histogramData = await histRes.json();
    stamp.textContent = 'Actualizado ' + new Date().toLocaleTimeString();

    renderHistogram(histogramData);
    renderKpis(status);
    renderHealthbar(status.services, status.counters, status.capture_metrics, status.calibracion);
    renderSidebar(status);
    // Las tres secciones de desarrollo -topologia, modelo y alcance- no estan
    // en el documento del lector. Se comprueba la existencia del elemento en
    // vez del rol: el servidor ya decidio que enviarle, y el navegador no tiene
    // por que repetir esa decision ni poder contradecirla.
    if (document.getElementById('topo')) renderTopologia(status);

    const healthCards = Object.entries(status.services).map(([name, active]) =>
      card(SERVICE_LABEL[name] || name, active ? ICON.ok + ' activo' : ICON.bad + ' inactivo', active ? 'ok' : 'bad')
    );
    const cm = status.capture_metrics;
    if (cm) {
      const hasDrops = cm.kernel_drops > 0 || cm.kernel_ifdrops > 0;
      healthCards.push(card(
        'Paquetes capturados',
        cm.kernel_packets.toLocaleString('es'),
        'accent'
      ));
      healthCards.push(card(
        'Drops de captura',
        (cm.kernel_drops + cm.kernel_ifdrops).toLocaleString('es'),
        hasDrops ? 'bad' : 'ok'
      ));
    }
    health.innerHTML = healthCards.join('');

    const modelEl = document.getElementById('model');
    if (modelEl) {
      const m = status.model;
      modelEl.innerHTML = [
        card('Detector', 'OCSVM'),
        card('Umbral', m.threshold.toFixed(4), 'accent'),
        card('FPR benigno', (m.test_fpr * 100).toFixed(2) + '%'),
        card('Detección global', (m.detection_rate * 100).toFixed(1) + '%', 'accent'),
        card('Detección Kali-real', (m.kali_real_detection_rate * 100).toFixed(1) + '%', 'accent'),
      ].join('');
    }

    blocked.innerHTML = status.blocked.length
      ? status.blocked.map(b => `<tr><td class="ip">${b.ip}</td><td class="num">${b.expires_seconds != null ? b.expires_seconds + 's' : '?'}</td></tr>`).join('')
      : '<tr class="empty-row"><td colspan="2">Ninguna IP bloqueada ahora mismo.</td></tr>';

    const c = status.counters;
    counters.innerHTML = [
      card('Total', c.total),
      card('ALERT (modelo)', c.alert_model, c.alert_model > 0 ? 'bad' : ''),
      card('ALERT (fuerza bruta)', c.alert_auth_heuristic, c.alert_auth_heuristic > 0 ? 'bad' : ''),
      card('PERMIT (modelo)', c.permit_model, 'ok'),
      card('PERMIT (sin tráfico)', c.permit_heuristic),
    ].join('');

    const alcanceEl = document.getElementById('alcance');
    if (alcanceEl) {
      const ex = status.alcance || {};
      alcanceEl.innerHTML = [
        card('Paquetes de plano de control descartados', (ex.plano_control_descartado ?? 0).toLocaleString('es')),
        card('Ventanas de entidades excluidas', (ex.ventanas_excluidas ?? 0).toLocaleString('es')),
        card('Red analizada', ex.red_entidades || '&mdash;'),
      ].join('');
      const protos = (ex.protocolos_excluidos || []).map(p => PROTO[p] || ('proto ' + p));
      document.getElementById('alcanceDetalle').textContent =
        (protos.length ? 'Protocolos fuera del cálculo: ' + protos.join(', ') + '. ' : '') +
        ((ex.excluidas || []).length ? 'Entidades fuera del cálculo: ' + ex.excluidas.join(', ') + '.' : '');
    }

    if (currentRange === '1h') renderSparkline(status.activity);
    else loadActivity(currentRange);

    lastDecisions = await (await fetch('/api/decisions?limit=100')).json();
    markSeenAndCountNewAlerts(lastDecisions);
    renderDecisionsTable();
  } catch (e) {
    stamp.textContent = 'Error al actualizar: ' + e;
  }
}

// Seccion C: el filtro y la exportacion trabajan sobre lastDecisions (lo
// que ya esta cargado en el navegador), sin pedir nada nuevo al backend.
let lastDecisions = [];

// Mini-barra del score: situa el valor en la misma escala del histograma, con
// el umbral marcado. A la izquierda del umbral es zona ALERT (rojo); a la
// derecha, PERMIT (verde). Sin escala aun (histograma no cargado) o sin score,
// no se pinta nada -- no se inventa una posicion.
function miniBarraScore(score) {
  const e = window._escalaScore;
  if (score == null || !e || e.max === e.min) return '';
  const w = 66, h = 14, cy = h / 2;
  const x = v => ((Math.max(e.min, Math.min(e.max, v)) - e.min) / (e.max - e.min)) * (w - 6) + 3;
  const ux = x(e.umbral), sx = x(score);
  const col = score < e.umbral ? 'var(--danger)' : 'var(--ok)';
  const zona = score < e.umbral ? 'ALERT' : 'PERMIT';
  return `<svg class="mini" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img"`
    + ` aria-label="score ${score.toFixed(3)}, umbral ${e.umbral.toFixed(3)}, ${zona}">`
    + `<title>score ${score.toFixed(3)} · umbral ${e.umbral.toFixed(3)} · ${zona}</title>`
    + `<line x1="3" y1="${cy}" x2="${w - 3}" y2="${cy}" stroke="var(--border)" stroke-width="2" stroke-linecap="round"/>`
    + `<line x1="${ux.toFixed(1)}" y1="1.5" x2="${ux.toFixed(1)}" y2="${h - 1.5}" stroke="var(--text-dim)" stroke-width="1" stroke-dasharray="2 1.5"/>`
    + `<circle cx="${sx.toFixed(1)}" cy="${cy}" r="3.4" fill="${col}"/></svg>`;
}

function renderDecisionsTable() {
  const query = document.getElementById('ipFilter').value.trim();
  const rows = query ? lastDecisions.filter(d => d.entity_ip.includes(query)) : lastDecisions;
  document.getElementById('filterHint').textContent = query
    ? `${rows.length} de ${lastDecisions.length} decisiones coinciden con "${query}"`
    : '';
  document.getElementById('decisions').innerHTML = rows.length ? rows.map(d => {
    const isAlert = d.decision === 'ALERT';
    const badge = isAlert ? `<span class="badge alert">${ICON.bad} ALERT</span>` : `<span class="badge permit">${ICON.ok} PERMIT</span>`;
    const scoreCell = d.score != null
      ? `<span class="score-cell"><span>${d.score.toFixed(4)}</span>${miniBarraScore(d.score)}</span>`
      : '&mdash;';
    return `<tr class="${isAlert ? 'row-alert' : ''}"><td>${fmtTime(d.logged_at)}</td><td class="ip">${d.entity_ip}</td>` +
      `<td>${badge}</td><td class="why">${DETECTOR_LABEL[d.detector_name] || d.detector_name}</td>` +
      `<td class="num">${scoreCell}</td><td class="num">${d.packet_count_10s}</td></tr>`;
  }).join('') : `<tr class="empty-row"><td colspan="6">${query ? 'Ninguna decisión coincide con el filtro.' : 'Sin decisiones recientes.'}</td></tr>`;
}

on('ipFilter', 'input', renderDecisionsTable);

on('exportCsv', 'click', () => {
  const query = document.getElementById('ipFilter').value.trim();
  const rows = query ? lastDecisions.filter(d => d.entity_ip.includes(query)) : lastDecisions;
  const header = ['hora_utc', 'ip', 'decision', 'motivo', 'score', 'paquetes_10s'];
  const csvRows = rows.map(d => [
    d.window_end_utc,
    d.entity_ip,
    d.decision,
    DETECTOR_LABEL[d.detector_name] || d.detector_name,
    d.score != null ? d.score : '',
    d.packet_count_10s,
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));
  const csv = [header.join(','), ...csvRows].join('\\r\\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `cyberflow-decisiones-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// ---------------------------------------------------------------------------
// Topologia: el camino real de un paquete, no un dibujo decorativo. Cada nodo
// muestra un numero que sale del backend; si el backend no lo trae, se dice
// "sin medir" y no se pinta un cero -- un cero afirmaria que se midio.
// ---------------------------------------------------------------------------
const TOPO_ICON = {
  red:      '<circle cx="9" cy="9" r="7.4"/><path d="M1.6 9h14.8M9 1.6c3.6 3.8 3.6 11.2 0 14.8M9 1.6C5.4 5.4 5.4 12.8 9 16.4"/>',
  espejo:   '<path d="M9 2v14"/><path d="M14.5 5.5 9 2 3.5 5.5"/><path d="M3.5 12.5 9 16l5.5-3.5"/>',
  nic:      '<rect x="1.8" y="5.5" width="14.4" height="9" rx="1.6"/><path d="M5 5.5V3M9 5.5V3M13 5.5V3"/>',
  disco:    '<circle cx="9" cy="9" r="7"/><circle cx="9" cy="9" r="2.4"/><path d="M9 2v2.2"/>',
  lupa:     '<circle cx="7.8" cy="7.8" r="5.4"/><path d="M11.7 11.7 16.4 16.4"/>',
  cpu:      '<rect x="4.5" y="4.5" width="9" height="9" rx="1.2"/><path d="M7 1.6v2.9M11 1.6v2.9M7 13.5v2.9M11 13.5v2.9M1.6 7h2.9M1.6 11h2.9M13.5 7h2.9M13.5 11h2.9"/>',
  modelo:   '<path d="M9 1.8 15.6 5.6v7.6L9 17 2.4 13.2V5.6Z"/><circle cx="9" cy="9.4" r="2.4"/>',
  escudo:   '<path d="M9 1.8 15 4.2v5c0 3.6-2.5 6.3-6 7.2-3.5-.9-6-3.6-6-7.2v-5Z"/><path d="M6.4 9.2 8.3 11l3.4-3.4"/>',
  fichero:  '<path d="M4 1.8h6l4 4v10.4H4Z"/><path d="M10 1.8v4h4"/>',
  tijera:   '<circle cx="4.4" cy="13.4" r="2.2"/><circle cx="13.6" cy="13.4" r="2.2"/><path d="M5.9 11.9 14.4 2.6M12.1 11.9 3.6 2.6"/>',
  tabla:    '<rect x="2" y="3" width="14" height="12" rx="1.4"/><path d="M2 7h14M7 7v8M11.5 7v8"/>',
  ojo:      '<path d="M1.6 9S4.4 3.8 9 3.8 16.4 9 16.4 9 13.6 14.2 9 14.2 1.6 9 1.6 9Z"/><circle cx="9" cy="9" r="2.3"/>',
};

// Dos vistas del mismo sistema. "esencial" es el camino del paquete en siete
// pasos; "completa" anade los artefactos que se escriben en disco, la rama de
// lo que se descarta y quien consume el registro. Los artefactos se dibujan
// con trazo discontinuo para que el diagrama no confunda un fichero con un
// proceso.
const TOPO_VISTAS = {
  esencial: {
    w: 620, h: 592,
    packet: 'M310,37 L310,553',
    grupos: [],
    nodos: [
      { id: 'red',      x: 210, y: 8,   w: 200, h: 58, icono: 'red',    titulo: 'Red de la entidad' },
      { id: 'span',     x: 210, y: 94,  w: 200, h: 58, icono: 'espejo', titulo: 'Espejo SPAN' },
      { id: 'nic',      x: 210, y: 180, w: 200, h: 58, icono: 'nic',    titulo: 'Interfaz en escucha' },
      { id: 'captura',  x: 12,  y: 266, w: 194, h: 58, icono: 'disco',  titulo: 'Anillo de PCAP' },
      { id: 'suricata', x: 414, y: 266, w: 194, h: 58, icono: 'lupa',   titulo: 'Suricata' },
      { id: 'motor',    x: 210, y: 352, w: 200, h: 58, icono: 'cpu',    titulo: 'Motor de decisión' },
      { id: 'modelo',   x: 210, y: 438, w: 200, h: 58, icono: 'modelo', titulo: 'OCSVM congelado' },
      { id: 'control',  x: 210, y: 524, w: 200, h: 58, icono: 'escudo', titulo: 'Control nftables' },
    ],
    aristas: [
      { d: 'M310,66 L310,94',                   desde: 'red',      hasta: 'span' },
      { d: 'M310,152 L310,180',                 desde: 'span',     hasta: 'nic' },
      { d: 'M310,238 C310,256 109,248 109,266', desde: 'nic',      hasta: 'captura' },
      { d: 'M310,238 C310,256 511,248 511,266', desde: 'nic',      hasta: 'suricata' },
      { d: 'M109,324 C109,342 310,334 310,352', desde: 'captura',  hasta: 'motor' },
      { d: 'M511,324 C511,342 310,334 310,352', desde: 'suricata', hasta: 'motor' },
      { d: 'M310,410 L310,438',                 desde: 'motor',    hasta: 'modelo' },
      { d: 'M310,496 L310,524',                 desde: 'modelo',   hasta: 'control' },
    ],
  },
  completa: {
    w: 900, h: 840,
    // Camino ilustrativo de un paquete por la tuberia: baja al espejo, al
    // anillo de PCAP y de ahi al motor y al modelo. Un punto lo recorre en vivo.
    packet: 'M450,64 L450,232 L175,290 L175,392 L450,452 L450,732',
    grupos: [
      { x: 12,  y: 0,   w: 300, h: 236, txt: 'Hosts · VLAN 20/30' },
      { x: 18,  y: 242, w: 834, h: 152, txt: 'Adquisición' },
      { x: 18,  y: 406, w: 834, h: 242, txt: 'Análisis' },
      { x: 300, y: 660, w: 300, h: 84,  txt: 'Respuesta' },
      { x: 300, y: 750, w: 552, h: 76,  txt: 'Observabilidad' },
    ],
    nodos: [
      { id: 'atacante', x: 18, y: 22,  w: 200, h: 48, icono: 'lupa',   titulo: 'Atacante (Kali)',   host: true, ip: '10.10.20.30',    desc: 'lanza los ataques' },
      { id: 'clientes', x: 18, y: 78,  w: 200, h: 48, icono: 'red',    titulo: 'Clientes',          host: true, ip: '10.10.20.21-.26', desc: '6 perfiles legítimos' },
      { id: 'servidor', x: 18, y: 134, w: 200, h: 48, icono: 'disco',  titulo: 'Servidor',          host: true, ip: '10.10.30.10',    desc: 'objetivo HTTP/HTTPS' },
      { id: 'gateway',  x: 18, y: 190, w: 200, h: 48, icono: 'escudo', titulo: 'pfSense / gateway', host: true, ip: '10.10.20.1',     desc: 'enruta entre VLAN' },
      { id: 'red',       x: 330, y: 8,   w: 240, h: 56, icono: 'red',    titulo: 'Red de la entidad',  tag: 'VLAN 10-100' },
      { id: 'span',      x: 330, y: 92,  w: 240, h: 56, icono: 'espejo', titulo: 'Espejo SPAN',        tag: 'CORE-STACK' },
      { id: 'nic',       x: 330, y: 176, w: 240, h: 56, icono: 'nic',    titulo: 'Interfaz en escucha', tag: 'ens37 · SIN IP' },
      { id: 'captura',   x: 60,  y: 260, w: 230, h: 56, icono: 'disco',  titulo: 'tcpdump',            tag: 'SERVICIO' },
      { id: 'suricata',  x: 610, y: 260, w: 230, h: 56, icono: 'lupa',   titulo: 'Suricata',           tag: 'SERVICIO' },
      { id: 'pcap',      x: 60,  y: 344, w: 230, h: 48, icono: 'fichero', titulo: 'anillo live-*.pcap', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'eve',       x: 610, y: 344, w: 230, h: 48, icono: 'fichero', titulo: 'eve.json',          tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'descartes', x: 30,  y: 424, w: 250, h: 56, icono: 'tijera', titulo: 'Fuera del cálculo',  tag: 'SUMIDERO',  clase: 'sumidero' },
      { id: 'motor',     x: 330, y: 424, w: 240, h: 56, icono: 'cpu',    titulo: 'Atribución de flujo', tag: 'SERVICIO' },
      { id: 'variables', x: 330, y: 508, w: 240, h: 56, icono: 'tabla',  titulo: 'Variables / 10 s', tag: 'L2·L3·L4·L7' },
      { id: 'modelo',    x: 330, y: 592, w: 240, h: 56, icono: 'modelo', titulo: 'OCSVM congelado',    tag: 'UMBRAL FIJO' },
      { id: 'reentrenamiento', x: 610, y: 592, w: 250, h: 56, icono: 'modelo', titulo: 'Reentrenamiento', tag: 'MENSUAL / POR DERIVA' },
      { id: 'control',   x: 330, y: 676, w: 240, h: 56, icono: 'escudo', titulo: 'Control nftables',   tag: 'EXPIRA A 120 s' },
      { id: 'registro',  x: 330, y: 760, w: 240, h: 48, icono: 'fichero', titulo: 'motor_decision.log', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'panel',     x: 620, y: 760, w: 230, h: 48, icono: 'ojo',    titulo: 'Este panel',         tag: 'SOLO LECTURA' },
    ],
    aristas: [
      { d: 'M218,46 L330,34',  desde: 'atacante', hasta: 'red', etiqueta: 'ataca',    ex: 258, ey: 30 },
      { d: 'M218,102 L330,38', desde: 'clientes', hasta: 'red', etiqueta: 'tráfico',  ex: 268, ey: 74 },
      { d: 'M218,158 L330,44', desde: 'servidor', hasta: 'red', etiqueta: 'objetivo', ex: 300, ey: 128 },
      { d: 'M218,214 L330,50', desde: 'gateway',  hasta: 'red', etiqueta: 'enruta',   ex: 300, ey: 190 },
      { d: 'M450,64 L450,92',                    desde: 'red',       hasta: 'span', etiqueta: 'todo cruza el troncal', ex: 575, ey: 82 },
      { d: 'M450,148 L450,176',                  desde: 'span',      hasta: 'nic', etiqueta: 'copia de tramas', ex: 560, ey: 166 },
      { d: 'M450,232 C450,250 175,242 175,260',  desde: 'nic',       hasta: 'captura', etiqueta: 'paquetes', ex: 250, ey: 245 },
      { d: 'M450,232 C450,250 725,242 725,260',  desde: 'nic',       hasta: 'suricata', etiqueta: 'paquetes', ex: 648, ey: 245 },
      { d: 'M175,316 L175,344',                  desde: 'captura',   hasta: 'pcap' },
      { d: 'M725,316 L725,344',                  desde: 'suricata',  hasta: 'eve' },
      { d: 'M175,392 C175,412 450,404 450,424',  desde: 'pcap',      hasta: 'motor', etiqueta: 'L3·L4', ex: 250, ey: 408 },
      { d: 'M725,392 C725,412 450,404 450,424',  desde: 'eve',       hasta: 'motor', etiqueta: 'HTTP·DNS·TLS', ex: 662, ey: 408 },
      { d: 'M330,452 L280,452',                  desde: 'motor',     hasta: 'descartes', tipo: 'descarte', etiqueta: 'descarta', ex: 305, ey: 444 },
      { d: 'M450,480 L450,508',                  desde: 'motor',     hasta: 'variables', etiqueta: 'atribuye por IP', ex: 575, ey: 498 },
      { d: 'M450,564 L450,592',                  desde: 'variables', hasta: 'modelo', etiqueta: '31 variables', ex: 548, ey: 582 },
      { d: 'M610,620 L570,620',                  desde: 'reentrenamiento', hasta: 'modelo', etiqueta: 'entrena y congela', ex: 590, ey: 610 },
      { d: 'M450,648 L450,676',                  desde: 'modelo',    hasta: 'control', etiqueta: 'score < umbral', ex: 560, ey: 666 },
      { d: 'M450,732 L450,760',                  desde: 'control',   hasta: 'registro' },
      { d: 'M570,784 L620,784',                  desde: 'registro',  hasta: 'panel' },
    ],
  },
};

let topoVista = 'esencial';
// Mapa de artefactos: los ficheros de cada componente. Se pide solo cuando se
// activa "Ver archivos" -es de admin- y se guarda; los chips abiertos se
// recuerdan entre repintados.
let topoArchivos = false;
let artefactos = null;
const filesAbiertos = new Set();

const TOPO_TEXTO = {
  red: {
    que: 'El tráfico entre VLAN de la entidad. No se toca: CyberFlow solo observa una copia.',
    nota: 'La red enruta a través del cortafuegos, así que todo el tráfico entre VLAN pasa por el troncal espejado.',
  },
  span: {
    que: 'La sesión de espejo del conmutador copia el troncal del cortafuegos hacia el puerto del sensor.',
    nota: 'Desde el sensor no se puede leer el estado de la sesión: se infiere de que lleguen paquetes. Si deja de llegar tráfico, el problema puede estar aquí y el panel no lo distingue de una red en silencio.',
    cmd: 'monitor session 1 source interface Gi1/0/20 , Gi2/0/20 both\\nmonitor session 1 destination interface Gi1/0/48 encapsulation replicate\\n! Gi1/0/20 y Gi2/0/20: troncales al hipervisor A (172.17.25.3)\\n! encapsulation replicate: conserva la etiqueta 802.1Q -> el sensor ve la VLAN',
  },
  atacante: {
    que: 'La VM Kali (10.10.20.30). Genera los ataques del ensayo: escaneo, nikto, flood HTTP y ARP spoofing.',
    nota: 'Fuera de la fase de ataque debe estar apagada: si emite durante la línea base, el modelo aprendería el ataque como normal.',
  },
  clientes: {
    que: 'Una VM con seis alias .21-.26, cada uno un perfil de tráfico legítimo (ofimática, navegación, descargas, aplicación, ligero, errático) contra el servidor.',
    nota: 'Seis IP sobre una sola MAC, a propósito: el motor puntúa por IP, así que son seis entidades distintas para el modelo.',
  },
  servidor: {
    que: 'El objetivo del laboratorio (10.10.30.10), servidor HTTP/HTTPS. Recibe el tráfico legítimo y los ataques.',
    nota: 'Aparece con pocos paquetes propios porque el motor atribuye cada flujo a quien lo inicia -el cliente-, no al destino.',
  },
  gateway: {
    que: 'La puerta de enlace de la VLAN 20 (10.10.20.1, VIP CARP de pfSense). Enruta entre VLAN.',
    nota: 'En el ARP spoofing su IP pasó a verse con dos MAC: esa es la anomalía de capa 2 que dispara unique_src_mac_30s.',
  },
  reentrenamiento: {
    que: 'El modelo envejece: la normalidad cambia con el tiempo. Se reentrena con datos verificados limpios, congelando el umbral en validación antes de evaluar.',
    flujo: [
      {paso: 'Dataset limpio', fichero: 'multilayer-v3.csv', garantia: 'solo tráfico benigno verificado'},
      {paso: 'Particionar', fichero: 'particionar_linea_base.py', garantia: 'bandas de guarda: sin fuga temporal'},
      {paso: 'Entrenar', fichero: 'entrenar_preliminar.py', garantia: 'umbral congelado en validación, antes de evaluar'},
      {paso: 'Modelo + manifiesto', fichero: 'ocsvm_scaled.joblib', garantia: 'hashes que fijan la reproducibilidad'},
      {paso: 'Promoción', fichero: 'misma verificación', garantia: 'FPR y partición revisados; nunca a ciegas'},
    ],
    nota: 'Cadencia: mensual como suelo, pero el disparador real es la deriva del FPR, y es OBLIGATORIO al cambiar la red (nueva VLAN, Wazuh, AAA). La automatización prepara el candidato; promocionarlo pasa por la misma verificación, nunca a ciegas.',
  },
  nic: {
    que: 'La interfaz que recibe el espejo, sin dirección IP y en modo promiscuo.',
    nota: 'Sin dirección a propósito: con una, el sensor sería alcanzable desde el troncal espejado y su propio tráfico entraría en su propia captura.',
  },
  captura: {
    que: 'tcpdump escribe un anillo de ficheros PCAP rotados por tiempo. De ahí salen las variables de red y transporte.',
    nota: 'Un fichero que el motor no pueda leer se descarta en silencio, así que se cuenta. Si este número no es cero, hay historia que no se está analizando.',
  },
  suricata: {
    que: 'Suricata analiza el mismo espejo y emite eventos HTTP, DNS y TLS a eve.json. De ahí salen las variables de aplicación.',
    nota: 'Los descartes del núcleo miden si la captura llega completa. Con descartes, las ventanas afectadas están incompletas y el modelo las puntúa igual.',
  },
  motor: {
    que: 'Atribuye cada paquete a la IP que inició el flujo, extrae las variables en ventanas fijas y puntúa cada ventana.',
    nota: 'Antes de puntuar descarta el plano de control y las copias que el espejo enseña dos veces. Ese filtrado es alcance, no fórmula: el extractor congelado no se toca.',
  },
  modelo: {
    que: 'Un One-Class SVM entrenado solo con tráfico benigno. El umbral se calibró con datos de validación y se congeló antes de evaluar.',
    nota: 'Mientras el umbral venga de otra red, las alertas son ruido: la distribución de esta red no es la que vio el modelo.',
  },
  control: {
    que: 'Una regla nftables con expiración nativa, en una tabla separada y aditiva.',
    nota: 'Solo corta de verdad si el sensor está en el camino del tráfico. Con un espejo SPAN no lo está: la regla se escribe, pero el paquete ya pasó por otro sitio.',
  },
  pcap: {
    que: 'Ficheros PCAP rotados cada 15 s. Es toda la historia de capa 3 y 4 de la que dispone el motor.',
    nota: 'Un temporizador poda los más viejos: sin él el anillo crece sin fin, porque el nombre lleva fecha y tcpdump nunca reutiliza un fichero. Medido antes de podarlo: 403 MB en un día.',
  },
  eve: {
    que: 'El registro de eventos de Suricata, una línea JSON por evento. De aquí salen HTTP, DNS y TLS.',
    nota: 'Va por delante del anillo de PCAP: Suricata emite el evento antes de que tcpdump vuelque los paquetes a disco. Por eso hay ventanas con eventos de aplicación y cero paquetes.',
  },
  descartes: {
    que: 'Lo que se captura pero NO se puntúa: plano de control, copias del espejo y entidades declaradas fuera de alcance.',
    nota: 'Declararlo con su cifra es parte del método. Sin número, «se excluyó» no es una medición sino una afirmación.',
  },
  variables: {
    // El desglose por capas ya NO se escribe aqui: vive en la seccion
    // "Variables", generado del esquema. Escrito a mano decia "seis de red,
    // cinco de transporte y diecisiete de aplicacion" -el esquema dice nueve,
    // ocho y once- y la suma daba 28, asi que el error sobrevivio meses.
    que: 'Una fila por entidad y ventana, con las variables que el modelo puntúa.',
    nota: 'El extractor está congelado: los filtros actúan sobre su entrada, nunca sobre sus fórmulas.',
    enlace: { href: '#s-variables', txt: 'Ver las variables por capa' },
  },
  registro: {
    que: 'Una línea JSON por decisión: entidad, ventana, detector, score y los contadores de alcance.',
    nota: 'Es la única fuente del panel. Por eso el panel no puede afirmar un alcance distinto del que el motor aplica de verdad.',
  },
  panel: {
    que: 'Lee el registro del motor, el estado de los servicios y la tabla nftables. No ejecuta ninguna acción.',
    nota: 'Solo lectura a propósito. Un panel que pudiera desbloquear una IP sería otro camino hacia el cortafuegos, y con su propia superficie de ataque.',
  },
};

let topoSel = 'motor';
let topoUltimo = null;

// Declarada AQUI, no junto al resto del codigo de la seccion "Variables": la
// lee topoEstado(), y refresh() corre antes que aquel bloque. Un `let` leido
// antes de su declaracion lanza ReferenceError -zona muerta temporal- y se
// llevaba por delante el primer pintado entero del panel.
let varDatos = null;

function topoEstado(id, s) {
  const sv = s.services || {};
  const cm = s.capture_metrics;
  const al = s.alcance || {};
  const c = s.counters || {};
  const llegaTrafico = !!(cm && cm.kernel_packets > 0);
  const num = (v) => Number(v).toLocaleString('es');

  switch (id) {
    case 'red':
      // La red no tiene "estado" propio que el sensor pueda leer: lo unico
      // observable es que llegue trafico por el espejo. Se dice eso y no mas.
      return { estado: llegaTrafico ? 'ok' : '', valor: al.red_entidades || 'sin declarar', datos: {} };
    case 'span':
      return {
        estado: llegaTrafico ? 'ok' : 'warn',
        valor: llegaTrafico ? 'entregando tráfico' : 'sin tráfico visible',
        datos: { 'Estado en el conmutador': 'no legible desde aquí' },
      };
    case 'nic':
      return {
        estado: llegaTrafico ? 'ok' : 'warn',
        valor: llegaTrafico ? num(cm.kernel_packets) + ' paquetes' : 'sin paquetes',
        datos: cm ? { 'Paquetes vistos': num(cm.kernel_packets) } : {},
      };
    case 'captura': {
      const on = !!sv['ppi-motor-capture.service'];
      const ile = al.pcaps_ilegibles;
      const mal = on && ile != null && ile > 0;
      return {
        estado: !on ? 'bad' : (mal ? 'bad' : 'ok'),
        valor: !on ? 'inactivo' : (ile == null ? 'activo' : (mal ? num(ile) + ' ficheros ilegibles' : 'anillo íntegro')),
        datos: { 'Servicio': on ? 'activo' : 'inactivo',
                 'Ficheros ilegibles': ile == null ? 'sin medir' : num(ile) },
      };
    }
    case 'suricata': {
      const on = !!sv['suricata.service'];
      const drops = cm ? (cm.kernel_drops + cm.kernel_ifdrops) : null;
      return {
        estado: !on ? 'bad' : (drops ? 'warn' : 'ok'),
        valor: !on ? 'inactivo' : (drops == null ? 'activo' : (drops ? num(drops) + ' descartes' : 'sin descartes')),
        datos: { 'Servicio': on ? 'activo' : 'inactivo',
                 'Descartes del núcleo': drops == null ? 'sin medir' : num(drops) },
      };
    }
    case 'motor': {
      const on = !!sv['ppi-motor.service'];
      const dup = al.duplicados_espejo;
      return {
        estado: on ? 'ok' : 'bad',
        valor: on ? num(c.total || 0) + ' decisiones/h' : 'inactivo',
        datos: { 'Servicio': on ? 'activo' : 'inactivo',
                 'Copias del espejo quitadas': dup == null ? 'sin medir' : num(dup),
                 'Plano de control descartado': al.plano_control_descartado == null ? 'sin medir' : num(al.plano_control_descartado) },
      };
    }
    case 'modelo': {
      const cal = s.calibracion && s.calibracion.calibrado_en_esta_red;
      const m = s.model || {};
      return {
        estado: cal ? 'ok' : 'warn',
        valor: cal ? 'calibrado aquí' : 'umbral de otra red',
        datos: { 'Umbral': m.threshold != null ? m.threshold.toFixed(4) : '—',
                 'Calibrado en esta red': cal ? 'sí' : 'no' },
      };
    }
    case 'control': {
      const n = (s.blocked || []).length;
      return {
        estado: n ? 'warn' : '',
        valor: n ? n + ' IP bloqueadas' : 'sin bloqueos activos',
        datos: { 'Bloqueos vigentes': String(n) },
      };
    }
    case 'pcap': {
      const ile = al.pcaps_ilegibles;
      return {
        estado: ile == null ? '' : (ile > 0 ? 'bad' : 'ok'),
        valor: ile == null ? 'sin medir' : (ile > 0 ? num(ile) + ' ilegibles' : 'íntegro'),
        datos: { 'Ficheros que el motor no pudo leer': ile == null ? 'sin medir' : num(ile) },
      };
    }
    case 'eve': {
      const drops = cm ? (cm.kernel_drops + cm.kernel_ifdrops) : null;
      const datos = { 'Paquetes vistos': cm ? num(cm.kernel_packets) : 'sin medir',
                      'Descartes del núcleo': drops == null ? 'sin medir' : num(drops) };
      if (cm && cm.errors != null) datos['Errores de captura'] = num(cm.errors);
      // La marca del propio evento stats, no la hora de esta pantalla: si
      // Suricata dejo de emitir, la cifra se queda quieta y aqui se ve.
      if (cm && cm.medido_en) datos['Medido en'] = String(cm.medido_en).slice(11, 19);
      return {
        estado: drops == null ? '' : (drops ? 'warn' : 'ok'),
        valor: drops == null ? 'sin medir' : (drops ? num(drops) + ' descartes' : 'sin descartes'),
        datos,
      };
    }
    case 'descartes': {
      const partes = {
        'Plano de control (CARP, pfsync)': al.plano_control_descartado,
        'Copias del espejo': al.duplicados_espejo,
        'Ventanas de entidades excluidas': al.ventanas_excluidas,
      };
      const total = Object.values(partes).reduce((a, v) => a + (v || 0), 0);
      const datos = {};
      for (const [k, v] of Object.entries(partes)) datos[k] = v == null ? 'sin medir' : num(v);
      if ((al.excluidas || []).length) datos['Entidades declaradas fuera'] = al.excluidas.join(', ');
      return { estado: '', valor: total ? num(total) + ' descartados' : 'sin descartes', datos };
    }
    case 'variables': {
      const on = !!sv['ppi-motor.service'];
      // Los numeros salen del esquema, no de literales: un "28" escrito aqui
      // se queda atras en cuanto el esquema cambie y nadie lo notara.
      const d = varDatos;
      const datos = d
        ? {
            'Puntuadas por ventana': String(d.n_motor),
            'En acumulación': String(d.n_total - d.n_motor),
            'Paso': d.paso_segundos + ' s',
            'Historia máxima': d.historia_maxima_s + ' s',
          }
        : { 'Paso': '10 s' };
      return { estado: on ? 'ok' : 'bad', valor: num(c.total || 0) + ' ventanas/h', datos };
    }
    case 'registro':
      return { estado: '', valor: 'una línea por decisión', datos: {} };
    case 'panel':
      return { estado: 'ok', valor: 'solo lectura', datos: { 'Refresco': '5 s' } };
    case 'reentrenamiento':
      return { estado: '', valor: 'periódico', datos: {
        'Cadencia base': 'mensual',
        'Disparador real': 'deriva del FPR',
        'Obligatorio': 'al cambiar la red' } };
  }
  return { estado: '', valor: '—', datos: {} };
}

function renderTopologia(status) {
  topoUltimo = status;
  const v = TOPO_VISTAS[topoVista];
  const svg = document.getElementById('topo');
  const est = {};
  for (const n of v.nodos) est[n.id] = topoEstado(n.id, status);

  const grupos = v.grupos.map(g =>
    `<rect class="topo-grupo" x="${g.x}" y="${g.y}" width="${g.w}" height="${g.h}" rx="12"/>` +
    `<text class="topo-grupo-txt" x="${g.x + 12}" y="${g.y + 15}">${g.txt}</text>`
  ).join('');

  // Una arista se anima cuando el tramo esta operativo: ningun extremo caido.
  // Un aviso -por ejemplo, umbral sin calibrar- no interrumpe el flujo, asi
  // que no apaga la arista; solo un servicio caido lo hace. La rama de
  // descarte nunca se anima: no es el camino del dato, es donde se queda.
  const aristas = v.aristas.map(e => {
    if (e.tipo === 'descarte') {
      return `<path class="topo-edge descarte" d="${e.d}"/>` +
             (e.etiqueta ? `<text class="topo-edge-label" x="${e.ex}" y="${e.ey}" text-anchor="middle">${e.etiqueta}</text>` : '');
    }
    const vivo = est[e.desde].estado !== 'bad' && est[e.hasta].estado !== 'bad'
                 && est[e.desde].estado !== '';
    const label = e.etiqueta
      ? `<text class="topo-edge-label" x="${e.ex}" y="${e.ey}" text-anchor="middle">${e.etiqueta}</text>` : '';
    return `<path class="topo-edge ${vivo ? 'live' : 'dim'}" d="${e.d}"/>` + label;
  }).join('');

  // Un punto recorre la tuberia en bucle: hace visible que el dato fluye.
  const packet = v.packet
    ? `<circle class="topo-pkt" r="5"><animateMotion dur="6s" repeatCount="indefinite" calcMode="linear" path="${v.packet}"/></circle>`
    : '';

  // Los hosts no pasan por topoEstado: se dibujan con su IP y su rol.
  const hosts = v.nodos.filter(n => n.host).map(n => {
    const cy = n.y + n.h / 2;
    return `<g class="topo-node topo-host ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      <g class="ico" transform="translate(${n.x + 12}, ${cy - 9})"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[n.icono]}</svg></g>
      <text class="ttl" x="${n.x + 40}" y="${cy - 3}">${n.titulo}</text>
      <text class="hostip" x="${n.x + 40}" y="${cy + 11}">${n.ip}</text>
      <text class="tag" x="${n.x + n.w - 10}" y="${n.y + n.h - 6}" text-anchor="end">${n.desc}</text>
    </g>`;
  }).join('');

  const nodos = v.nodos.filter(n => !n.host).map(n => {
    const e = est[n.id];
    const cy = n.y + n.h / 2;
    const color = e.estado === 'ok' ? 'var(--ok)' : e.estado === 'warn' ? 'var(--amber)'
                : e.estado === 'bad' ? 'var(--danger)' : 'var(--border)';
    const etiqueta = n.tag
      ? `<text class="tag" x="${n.x + 42}" y="${n.y + n.h - 5}">${n.tag}</text>` : '';
    const desplazar = n.tag ? -8 : 0;
    // Con "Ver archivos" activo, cada nodo con ficheros muestra un contador; el
    // detalle de cada uno se abre pulsando el nodo (aparecen como cuadraditos).
    const nfiles = (topoArchivos && artefactos && artefactos[n.id]) ? artefactos[n.id].length : 0;
    const badge = nfiles
      ? `<text class="fbadge" x="${n.x + n.w - 24}" y="${n.y + n.h - 6}" text-anchor="end">▤ ${nfiles}</text>` : '';
    return `<g class="topo-node ${e.estado} ${n.clase || ''} ${nfiles ? 'tiene-archivos' : ''} ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      <g class="ico" transform="translate(${n.x + 13}, ${cy - 9 + desplazar})"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[n.icono]}</svg></g>
      <text class="ttl" x="${n.x + 42}" y="${cy - 3 + desplazar}">${n.titulo}</text>
      <text class="sub" x="${n.x + 42}" y="${cy + 12 + desplazar}">${e.valor}</text>
      ${etiqueta}${badge}
      <circle class="led" cx="${n.x + n.w - 13}" cy="${n.y + 13}" r="4" fill="${color}"/>
    </g>`;
  }).join('');

  svg.innerHTML = grupos + aristas + packet + hosts + nodos;
  aplicarZoom();
  renderTopoDetalle();
}

// --- Controles del diagrama: vista, escala y pantalla completa --------------
let topoZoom = null;   // null = ajustar al ancho disponible

function aplicarZoom() {
  const v = TOPO_VISTAS[topoVista];
  const svg = document.getElementById('topo');
  const caja = document.getElementById('topoScroll');
  svg.setAttribute('viewBox', `0 0 ${v.w} ${v.h}`);
  let escala = topoZoom;
  if (escala == null) escala = Math.max(0.25, (caja.clientWidth - 6) / v.w);
  svg.setAttribute('width', Math.round(v.w * escala));
  svg.setAttribute('height', Math.round(v.h * escala));
  document.getElementById('topoNivel').textContent = Math.round(escala * 100) + '%';
}

function escalaActual() {
  if (topoZoom != null) return topoZoom;
  const v = TOPO_VISTAS[topoVista];
  return Math.max(0.25, (document.getElementById('topoScroll').clientWidth - 6) / v.w);
}

on('topoVista', 'click', (ev) => {
  const b = ev.target.closest('button[data-vista]');
  if (!b) return;
  topoVista = b.dataset.vista;
  document.querySelectorAll('#topoVista button').forEach(x => x.classList.toggle('active', x === b));
  topoZoom = null;   // cada vista tiene otro tamano: se reajusta
  // Si el nodo seleccionado no existe en la vista nueva, se cae al motor.
  if (!TOPO_VISTAS[topoVista].nodos.some(n => n.id === topoSel)) topoSel = 'motor';
  if (topoUltimo) renderTopologia(topoUltimo);
});

on('topoMas', 'click', () => {
  topoZoom = Math.min(3, escalaActual() * 1.25); aplicarZoom();
});
on('topoMenos', 'click', () => {
  topoZoom = Math.max(0.25, escalaActual() / 1.25); aplicarZoom();
});
on('topoReset', 'click', () => {
  topoZoom = null; aplicarZoom();
});

on('topoExpandir', 'click', () => {
  const caja = document.getElementById('topoWrap');
  if (document.fullscreenElement) { document.exitFullscreen(); return; }
  if (!caja.requestFullscreen) { topoZoom = 1.4; aplicarZoom(); return; }
  // El navegador puede denegarlo (politica de permisos, o una pulsacion que no
  // considera gesto del usuario). Devuelve una promesa rechazada: sin este
  // catch queda una excepcion suelta en la consola y el boton no hace nada.
  caja.requestFullscreen().catch(() => {
    topoZoom = 1.4;
    aplicarZoom();
    document.getElementById('topoExpandirTxt').textContent = 'Ampliado';
  });
});
document.addEventListener('fullscreenchange', () => {
  const dentro = !!document.fullscreenElement;
  document.getElementById('topoExpandirTxt').textContent = dentro ? 'Salir' : 'Expandir';
  // En pantalla completa cabe la vista detallada: se cambia sola la primera vez.
  if (dentro && topoVista === 'esencial') {
    topoVista = 'completa';
    document.querySelectorAll('#topoVista button').forEach(
      x => x.classList.toggle('active', x.dataset.vista === 'completa'));
    if (topoUltimo) renderTopologia(topoUltimo);
  }
  topoZoom = null;
  setTimeout(aplicarZoom, 60);   // tras el reflujo del navegador
});
window.addEventListener('resize', () => { if (topoZoom == null) aplicarZoom(); });

function renderTopoDetalle() {
  if (!topoUltimo) return;
  const lista = TOPO_VISTAS[topoVista].nodos;
  const n = lista.find(x => x.id === topoSel) || lista[0];
  const e = topoEstado(n.id, topoUltimo);
  const t = TOPO_TEXTO[n.id] || {};
  const filas = Object.entries(e.datos || {})
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  const cabIp = n.host && n.ip ? `<span class="state">${n.ip}</span>` : `<span class="state ${e.estado}">${e.valor}</span>`;
  document.getElementById('topoDetail').innerHTML =
    `<h3>${n.titulo}${cabIp}</h3>` +
    (t.que ? `<p>${t.que}</p>` : '') +
    (filas ? `<dl>${filas}</dl>` : '') +
    (t.cmd ? `<pre class="topo-cmd">${t.cmd.replace(/</g, '&lt;')}</pre>` : '') +
    (t.flujo ? flujoHTML(t.flujo) : '') +
    filesHTML(n.id) +
    (t.nota ? `<p class="dim">${t.nota}</p>` : '') +
    (t.enlace ? `<p><a href="${t.enlace.href}">${t.enlace.txt} &rarr;</a></p>` : '');
}

// Mini-flujo del reentrenamiento: pasos encadenados, cada uno con su fichero y
// la garantia que aporta. Hace visible POR QUE el reentrenamiento es fiable
// (sin fuga, umbral congelado, promocion verificada), no solo que existe.
function flujoHTML(pasos) {
  let html = '<div class="topo-flujo"><h4>Flujo de reentrenamiento</h4>';
  pasos.forEach((p, i) => {
    html += `<div class="paso"><span class="n">${i + 1}</span>`
      + `<div><div class="tit">${p.paso}<code>${p.fichero}</code></div>`
      + `<div class="gar">${p.garantia}</div></div></div>`;
    if (i < pasos.length - 1) html += '<div class="flecha">↓</div>';
  });
  return html + '</div>';
}

function fmtBytes(b) {
  if (b == null) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(0) + ' KB';
  if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
  return (b / 1073741824).toFixed(1) + ' GB';
}

function nombreFichero(ruta) {
  const p = ruta.split('/');
  return p[p.length - 1] || ruta;
}

// Los "cuadraditos" de ficheros del componente seleccionado, cada uno con su
// ventana de info que se abre al pulsar. Solo con "Ver archivos" activo.
function filesHTML(nodeId) {
  if (!topoArchivos) return '';
  if (!artefactos) return '<div class="topo-files"><h4>Archivos</h4><p class="dim" style="font-size:11px">cargando…</p></div>';
  const lista = artefactos[nodeId];
  if (!lista || !lista.length) return '';
  let html = '<div class="topo-files"><h4>Archivos que usa</h4>';
  for (const f of lista) {
    const clave = nodeId + '|' + f.ruta;
    const abierto = filesAbiertos.has(clave);
    html += `<button class="topo-file tipo-${f.tipo}" data-file="${clave.replace(/"/g, '&quot;')}" aria-expanded="${abierto}">`
      + `<span class="cuadro"></span>${nombreFichero(f.ruta)}</button>`;
    if (abierto) {
      const estado = f.existe
        ? [f.n != null ? f.n + ' ficheros' : null, fmtBytes(f.bytes),
           f.mtime ? 'modif. ' + new Date(f.mtime * 1000).toLocaleString() : null]
            .filter(Boolean).join(' · ')
        : '<span class="aus">no existe todavía</span>';
      html += `<div class="topo-file-det"><div class="ruta">${f.ruta}</div>`
        + `<div>${f.que}</div><div>${estado}</div></div>`;
    }
  }
  return html + '</div>';
}

async function cargarArtefactos() {
  try {
    artefactos = await (await fetch('/api/artefactos')).json();
  } catch (e) {
    artefactos = {};
  }
}

// ---- Simulacion de escenarios --------------------------------------------
// El panel GUIA, no ejecuta: muestra el comando para copiar. Es la opcion que
// eligio Mark; el panel de solo lectura no gana capacidad de ejecutar nada.
let escenarios = null;
let simTab = 'normal';

function escSimple(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderSimulacion() {
  const cont = document.getElementById('simGrid');
  if (!cont) return;
  if (!escenarios) { cont.innerHTML = '<p class="dim" style="font-size:12px">cargando…</p>'; return; }
  const lista = escenarios[simTab] || [];
  if (!lista.length) { cont.innerHTML = '<p class="dim" style="font-size:12px">sin escenarios en esta pestaña.</p>'; return; }
  cont.innerHTML = lista.map(e => {
    const peligro = /sudo|arpspoof/.test(e.comando || '') ? ' peligro' : '';
    const vars = (e.variables || []).map(v => `<span class="sim-var">${escSimple(v)}</span>`).join('');
    return `<div class="sim-card${peligro}">`
      + `<h3>${escSimple(e.nombre)}</h3>`
      + `<div class="donde">${escSimple(e.donde || '')}</div>`
      + `<p class="explica">${escSimple(e.explica || '')}</p>`
      + `<div class="sim-cmd"><button class="sim-copiar" data-cmd="${escSimple(e.comando)}">copiar</button>${escSimple(e.comando)}</div>`
      + `<div class="sim-vars">${vars}</div>`
      + `<div class="sim-resp">${escSimple(e.responde || '')}</div>`
      + `</div>`;
  }).join('');
}

async function cargarEscenarios() {
  try {
    escenarios = await (await fetch('/api/escenarios')).json();
  } catch (e) {
    escenarios = { normal: [], anomalo: [] };
  }
  renderSimulacion();
}

on('simTabs', 'click', (ev) => {
  const b = ev.target.closest('button[data-sim]');
  if (!b) return;
  simTab = b.dataset.sim;
  document.querySelectorAll('#simTabs button').forEach(x => x.classList.toggle('active', x === b));
  renderSimulacion();
});

on('simGrid', 'click', async (ev) => {
  const b = ev.target.closest('.sim-copiar');
  if (!b) return;
  try {
    await navigator.clipboard.writeText(b.dataset.cmd);
    const antes = b.textContent; b.textContent = 'copiado ✓';
    setTimeout(() => { b.textContent = antes; }, 1500);
  } catch (e) {
    b.textContent = 'copia manual';
  }
});

on('topoArchivosBtn', 'click', async () => {
  topoArchivos = !topoArchivos;
  const b = document.getElementById('topoArchivosBtn');
  b.setAttribute('aria-pressed', String(topoArchivos));
  b.classList.toggle('active', topoArchivos);
  if (topoArchivos && !artefactos) await cargarArtefactos();
  if (topoUltimo) renderTopologia(topoUltimo);
});

on('topoDetail', 'click', (ev) => {
  const f = ev.target.closest('.topo-file');
  if (!f) return;
  const clave = f.dataset.file;
  if (filesAbiertos.has(clave)) filesAbiertos.delete(clave); else filesAbiertos.add(clave);
  renderTopoDetalle();
});

on('topo', 'click', (ev) => {
  const g = ev.target.closest('.topo-node');
  if (!g) return;
  topoSel = g.dataset.node;
  document.querySelectorAll('#topo .topo-node').forEach(x => x.classList.toggle('sel', x === g));
  renderTopoDetalle();
});
on('topo', 'keydown', (ev) => {
  if (ev.key !== 'Enter' && ev.key !== ' ') return;
  const g = ev.target.closest('.topo-node');
  if (!g) return;
  ev.preventDefault();
  topoSel = g.dataset.node;
  document.querySelectorAll('#topo .topo-node').forEach(x => x.classList.toggle('sel', x === g));
  renderTopoDetalle();
});

// --- Barra lateral: estado global y seccion visible -------------------------
function renderSidebar(status) {
  const sv = status.services || {};
  const nombres = Object.keys(sv);
  const caidos = nombres.filter(k => !sv[k]);
  const cal = status.calibracion && status.calibracion.calibrado_en_esta_red;
  const el = document.getElementById('sideState');
  let clase = 'ok', texto = 'todo en marcha';
  if (caidos.length) { clase = 'bad'; texto = caidos.length + ' servicio(s) caído(s)'; }
  else if (!cal) { clase = 'warn'; texto = 'sin calibrar'; }
  el.className = 'side-state ' + clase;
  document.getElementById('sideStateText').textContent = texto;

  const c = status.counters || {};
  const alertas = (c.alert_model || 0) + (c.alert_auth_heuristic || 0);
  const pill = document.getElementById('navAlertPill');
  pill.hidden = alertas === 0;
  pill.textContent = alertas;
}

const secciones = [...document.querySelectorAll('section[id]')];
const enlaces = new Map([...document.querySelectorAll('#nav a[data-sec]')].map(a => [a.dataset.sec, a]));
const spy = new IntersectionObserver((entradas) => {
  // Se marca la seccion mas alta que este visible, no la ultima que cruzo el
  // umbral: al desplazarse rapido, varias entran a la vez.
  const visibles = entradas.filter(e => e.isIntersecting)
    .map(e => e.target.id)
    .sort((a, b) => secciones.findIndex(s => s.id === a) - secciones.findIndex(s => s.id === b));
  if (!visibles.length) return;
  enlaces.forEach(a => a.classList.remove('active'));
  const activo = enlaces.get(visibles[0]);
  if (activo) activo.classList.add('active');
}, { rootMargin: '-10% 0px -70% 0px', threshold: 0 });
secciones.forEach(s => spy.observe(s));

refresh();
// ---- Variables por capa ---------------------------------------------------
// La tabla se GENERA desde el esquema. El texto que habia antes decia "seis de
// red, cinco de transporte y diecisiete de aplicacion" cuando el esquema dice
// nueve, ocho y once: como la suma seguia dando 28, nadie lo noto en meses.
// Generarla hace imposible esa clase de error.
// varDatos se declara arriba, junto a topoSel: topoEstado() la necesita antes
// de que este bloque se ejecute.
let varCapaSel = null;              // null = todas las capas
const varAbiertas = new Set();      // se conserva entre refrescos

function varEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function varFmt(v) {
  if (v == null) return '—';
  if (v === 0) return '0';
  const a = Math.abs(v);
  // Sin expresion regular a proposito: HTML es una cadena normal de Python, y
  // una barra invertida aqui dentro seria una secuencia de escape invalida
  // -Python ya avisa, y en una version futura sera error-. parseFloat quita
  // los ceros sobrantes igual de bien y no necesita escapar nada.
  if (a >= 1000) return v.toFixed(0);
  if (a >= 1) return String(parseFloat(v.toFixed(2)));
  return v.toPrecision(2);
}

function varDetalleHTML(v) {
  const m = v.muestra;
  let html = '<div class="var-det">';
  if (v.senal) html += `<p>${varEsc(v.senal)}</p>`;

  if (!m) {
    html += '<p class="var-vacio" style="padding:0">Sin muestra: el dataset todavía no existe o no contiene esta variable. No se inventa ningún ejemplo.</p>';
    return html + '</div>';
  }

  html += '<div class="stats">'
    + `<span>ventanas <b>${m.n}</b></span>`
    + `<span>mín <b>${varFmt(m.min)}</b></span>`
    + `<span>mediana <b>${varFmt(m.p50)}</b></span>`
    + `<span>máx <b>${varFmt(m.max)}</b></span>`
    + `<span>en cero <b>${m.ceros}</b> (${Math.round(100 * m.ceros / m.n)}%)</span>`
    + '</div>';

  if (m.ceros === m.n) {
    html += '<p>Esta variable está a cero en toda la muestra: esta red no ejercita todavía el comportamiento que mide. Es información, no un fallo.</p>';
  }

  if (m.ejemplos && m.ejemplos.length) {
    html += '<table class="var-ej"><thead><tr><th>entidad</th><th>ventana</th><th>valor</th></tr></thead><tbody>';
    for (const e of m.ejemplos) {
      html += `<tr><td>${varEsc(e.entidad)}</td><td>${varEsc(e.ventana)}</td><td><b>${varFmt(e.valor)}</b></td></tr>`;
    }
    html += '</tbody></table>';
  }
  return html + '</div>';
}

function renderVariables() {
  const cCapas = document.getElementById('varCapas');
  const cTabla = document.getElementById('varTabla');
  const pie = document.getElementById('varPie');
  if (!varDatos) { cTabla.innerHTML = '<p class="var-vacio">Cargando…</p>'; return; }

  cCapas.innerHTML = varDatos.capas.map(c => {
    const sel = varCapaSel === c.id;
    const fuera = c.n - c.n_motor;
    const nota = fuera ? `${c.n_motor} en el motor · ${fuera} en acumulación` : `${c.n} en el motor`;
    return `<button class="var-capa" data-capa="${c.id}" aria-pressed="${sel}" title="${varEsc(c.que)}">`
      + `<span class="cid">${c.id} · ${varEsc(c.nombre)}</span>`
      + `<div class="cn">${c.n} variable${c.n === 1 ? '' : 's'}</div>`
      + `<div class="cc">${nota}</div></button>`;
  }).join('');

  const visibles = varDatos.variables.filter(v => !varCapaSel || v.layer === varCapaSel);
  let html = '';
  let capaActual = null;
  for (const v of visibles) {
    if (v.layer !== capaActual) {
      capaActual = v.layer;
      const c = varDatos.capas.find(x => x.id === capaActual) || {};
      html += `<div class="var-grupo">${capaActual} · ${varEsc(c.nombre || '')} — ${varEsc(c.que || '')}</div>`;
    }
    const abierta = varAbiertas.has(v.name);
    const badge = v.en_motor ? '' : '<span class="var-badge">EN ACUMULACIÓN</span>';
    html += `<button class="var-fila" data-var="${varEsc(v.name)}" aria-expanded="${abierta}">`
      + `<span><span class="vn">${varEsc(v.name)}</span>${badge}<span class="vq">${varEsc(v.que)}</span></span>`
      + `<span class="vw">${v.window_seconds}s · ${varEsc(v.unit)}</span>`
      + '<svg class="var-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9,5 16,12 9,19"/></svg>'
      + '</button>';
    if (abierta) html += varDetalleHTML(v);
  }
  cTabla.innerHTML = html || '<p class="var-vacio">Ninguna variable en esta capa.</p>';

  const d = varDatos.dataset;
  const fuera = varDatos.n_total - varDatos.n_motor;
  let txt = `${varDatos.n_motor} variables puntuadas cada ${varDatos.paso_segundos} s`
    + (fuera ? `, ${fuera} más acumulándose para la próxima versión` : '')
    + ` · historia máxima ${varDatos.historia_maxima_s} s`;
  txt += d
    ? ` · muestra: ${d.filas} filas de ${d.entidades} entidades, ${d.desde} → ${d.hasta}`
    : ' · sin dataset: la tabla se pinta sin valores de ejemplo';
  pie.textContent = txt;
}

on('varCapas', 'click', (ev) => {
  const b = ev.target.closest('.var-capa');
  if (!b) return;
  varCapaSel = varCapaSel === b.dataset.capa ? null : b.dataset.capa;
  renderVariables();
});

on('varTabla', 'click', (ev) => {
  const b = ev.target.closest('.var-fila');
  if (!b) return;
  const n = b.dataset.var;
  if (varAbiertas.has(n)) varAbiertas.delete(n); else varAbiertas.add(n);
  renderVariables();
});

async function cargarVariables() {
  try {
    varDatos = await (await fetch('/api/variables')).json();
    renderVariables();
  } catch (e) {
    document.getElementById('varTabla').innerHTML =
      '<p class="var-vacio">No se pudo cargar el esquema de variables: ' + varEsc(e) + '</p>';
  }
}

if (document.getElementById('varTabla')) {
  cargarVariables();
  // El esquema no cambia y la muestra se mueve despacio: cada minuto sobra. A
  // 5 s no aportaria nada y solo daria ocasiones de perder la fila desplegada.
  setInterval(cargarVariables, 60000);
}

// Escenarios: catalogo estatico, se pide una vez (solo el admin tiene la seccion).
if (document.getElementById('simGrid')) cargarEscenarios();

// ---- Sesion: quien eres y en que modo miras ------------------------------
// El modo es del ADMIN y solo del admin: alterna entre la vista operativa y la
// de desarrollo. No es un permiso -esta autorizado a las dos- sino una forma de
// quitarse de encima lo que no necesita mientras opera. Por eso vive en
// localStorage y no en la sesion: es preferencia, no autorizacion.
const SESION = JSON.parse(document.getElementById('datosSesion').textContent);
const DEV_SECS = ['s-topologia', 's-variables', 's-modelo', 's-alcance', 's-simulacion'];

function aplicarModo(modo) {
  const dev = modo === 'desarrollo';
  for (const id of DEV_SECS) {
    const sec = document.getElementById(id);
    if (sec) sec.hidden = !dev;
    const enlace = document.querySelector('#nav a[data-sec="' + id + '"]');
    if (enlace) enlace.hidden = !dev;
  }
  const b = document.getElementById('modoBtn');
  if (b) {
    b.dataset.modo = modo;
    b.textContent = dev ? 'Modo desarrollo' : 'Modo operativo';
  }
  try { localStorage.setItem('cyberflow_modo', modo); } catch (e) { /* sin persistir */ }
}

document.getElementById('quien').textContent = SESION.usuario + ' · ' + SESION.rol;

if (SESION.rol === 'admin') {
  let modo = 'operativo';
  try { modo = localStorage.getItem('cyberflow_modo') || 'operativo'; } catch (e) { /* por omision */ }
  aplicarModo(modo);
  on('modoBtn', 'click', () => {
    const b = document.getElementById('modoBtn');
    aplicarModo(b.dataset.modo === 'desarrollo' ? 'operativo' : 'desarrollo');
  });
}

setInterval(refresh, 5000);
</script>
"""


def tail_lines(path: Path, max_bytes: int = 1_048_576) -> list[str]:
    if not path.exists():
        return []
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - max_bytes))
        chunk = handle.read()
    text = chunk.decode("utf-8", errors="replace")
    lines = text.split("\n")
    return [line for line in lines[1:] if line.strip()] if size > max_bytes else [
        line for line in lines if line.strip()
    ]


def read_decisions(log_path: Path, limit: int, max_bytes: int = 1_048_576) -> list[dict]:
    records = []
    for line in tail_lines(log_path, max_bytes=max_bytes):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "decision":
            records.append(event)
    records.sort(key=lambda item: item.get("logged_at", 0))
    return records[-limit:][::-1]


def leer_alcance(log_path: Path) -> dict:
    """Lo que el motor declara sobre su alcance y su captura, leido de su
    propio registro.

    No se configura aqui a proposito: el panel no debe afirmar un alcance
    distinto del que el motor aplica de verdad. Los contadores viajan en cada
    decision y la configuracion en el evento de arranque.

    Las claves de integridad de captura -``duplicados_espejo`` y
    ``pcaps_ilegibles``- solo existen si el motor desplegado es lo bastante
    reciente para emitirlas. Se devuelven ausentes y no en cero cuando no
    aparecen: un cero afirmaria que se midio y salio limpio, que es justo lo
    contrario de no haberlo medido.
    """
    alcance: dict = {}
    for line in tail_lines(log_path, max_bytes=1_048_576):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "motor_startup":
            alcance["red_entidades"] = event.get("entity_network")
            alcance["excluidas"] = event.get("excluidas", [])
            alcance["protocolos_excluidos"] = event.get("protocolos_excluidos", [])
        elif event.get("event") == "decision":
            for clave in ("plano_control_descartado", "duplicados_espejo",
                          "pcaps_ilegibles"):
                if clave in event:
                    alcance[clave] = event[clave]
            if "excluidas_acumulado" in event:
                alcance["ventanas_excluidas"] = event["excluidas_acumulado"]
            if event.get("pcaps_ilegibles_motivo"):
                alcance["pcaps_ilegibles_motivo"] = event["pcaps_ilegibles_motivo"]
    return alcance


def compute_counters(decisions: list[dict], window_seconds: int = 3600) -> dict:
    now = time.time()
    recent = [d for d in decisions if now - d.get("logged_at", 0) <= window_seconds]
    # Los dos detectores reales que pueden producir ALERT se cuentan por
    # separado -- mezclarlos en un solo numero oculta cual esta disparando,
    # justo cuando el motor ya tiene dos caminos distintos hacia ALERT
    # (ocsvm_scaled y el heuristico de fuerza bruta agregado despues).
    alert_ocsvm = sum(1 for d in recent if d["decision"] == "ALERT" and d.get("detector_name") == "ocsvm_scaled")
    alert_auth_heuristic = sum(
        1 for d in recent if d["decision"] == "ALERT" and d.get("detector_name") == "auth_failure_heuristic"
    )
    # PERMIT por heuristico = ventana vacia O sin paquetes (el modelo NO puntuo
    # ninguna de las dos). permit_model = solo los PERMIT que el modelo SI
    # puntuo (ocsvm_scaled). Sin esta distincion, los PERMIT de
    # no_live_packets_heuristic se contarian erroneamente como decisiones del
    # modelo, aunque el modelo nunca los vio.
    heuristic_permit_detectors = {"empty_window_heuristic", "no_live_packets_heuristic"}
    permit_heuristic = sum(
        1 for d in recent
        if d["decision"] == "PERMIT" and d.get("detector_name") in heuristic_permit_detectors
    )
    permit_model = sum(
        1 for d in recent
        if d["decision"] == "PERMIT" and d.get("detector_name") == "ocsvm_scaled"
    )
    return {
        "total": len(recent),
        "alert_model": alert_ocsvm,
        "alert_auth_heuristic": alert_auth_heuristic,
        "permit_model": permit_model,
        "permit_heuristic": permit_heuristic,
        "entidades": len({d.get("entity_ip") for d in recent if d.get("entity_ip")}),
    }


def bucket_activity(decisions: list[dict], bucket_seconds: int, count: int) -> list[dict]:
    """Agrega decisiones en cubos de tamano fijo para graficar actividad.

    Generaliza el sparkline de 60 minutos (bucket_seconds=60, count=60) y el
    de 24 horas (bucket_seconds=3600, count=24) con la misma logica. Cubos
    vacios se incluyen con ceros -- el frontend los necesita para dibujar
    una linea de tiempo continua, no solo los intervalos con actividad.
    """
    now = time.time()
    buckets = [{"offset": i, "alert": 0, "permit": 0} for i in range(count, -1, -1)]
    index_by_offset = {b["offset"]: b for b in buckets}
    for item in decisions:
        age_seconds = now - item.get("logged_at", 0)
        if age_seconds < 0 or age_seconds > count * bucket_seconds:
            continue
        offset = int(age_seconds // bucket_seconds)
        bucket = index_by_offset.get(offset)
        if bucket is None:
            continue
        if item["decision"] == "ALERT":
            bucket["alert"] += 1
        else:
            bucket["permit"] += 1
    return buckets


def bucket_by_minute(decisions: list[dict], minutes: int = 60) -> list[dict]:
    return bucket_activity(decisions, bucket_seconds=60, count=minutes)


def histogram_scores(decisions: list[dict], threshold: float, num_buckets: int = 16) -> dict:
    """Distribucion de los scores reales del modelo, no solo ALERT/PERMIT binario.

    Responde "que tan cerca del umbral esta pasando el trafico reciente" --
    encontrado como pregunta real en esta misma sesion (rafagas de ping
    puntuaron de forma inconsistente cerca del umbral, 1.24 vs 1.87, algo
    invisible en un simple conteo de ALERT/PERMIT). El rango incluye
    siempre el umbral, aunque todos los scores recientes caigan de un solo
    lado, para que la linea de referencia del umbral siempre sea visible.
    """
    scores = [d["score"] for d in decisions if d.get("score") is not None]
    if not scores:
        return {"buckets": [], "threshold": threshold, "min": None, "max": None}
    lo = min(min(scores), threshold)
    hi = max(max(scores), threshold)
    if lo == hi:
        lo -= 0.5
        hi += 0.5
    width = (hi - lo) / num_buckets
    buckets = [{"lo": lo + i * width, "hi": lo + (i + 1) * width, "count": 0} for i in range(num_buckets)]
    for score in scores:
        index = min(num_buckets - 1, max(0, int((score - lo) / width)))
        buckets[index]["count"] += 1
    return {"buckets": buckets, "threshold": threshold, "min": lo, "max": hi, "n": len(scores)}


def service_status(names: list[str]) -> dict[str, bool]:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", *names],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {name: False for name in names}
    outputs = result.stdout.strip().split("\n")
    return {name: (outputs[i].strip() == "active" if i < len(outputs) else False) for i, name in enumerate(names)}


def enforcement_list(enforce_command: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["sudo", "-n", enforce_command, "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def suricata_stats_desde_eve(eve_path: Path) -> dict | None:
    """Contadores de captura leidos del ultimo evento 'stats' de eve.json.

    Se prefiere esta via a invocar un ayudante con sudo, por tres razones
    medidas en el sensor de referencia:

    - El ayudante ``/usr/local/sbin/ppi-suricata-metrics`` que el panel
      esperaba por omision **no existe** en el despliegue, y tampoco estaba en
      la lista NOPASSWD. El resultado era ``capture_metrics: null`` y tres
      nodos del diagrama sin cifra, sin que nada lo dijera.
    - ``eve.json`` ya lo escribe Suricata con permisos 644, asi que no hace
      falta ningun privilegio nuevo ni un binario que instalar.
    - Suricata emite un evento ``stats`` cada pocos segundos con el mismo
      bloque ``capture`` que devolvia el ayudante.

    Devuelve None -y no ceros- si no hay ningun evento: un cero afirmaria que
    la captura no pierde paquetes, que no es lo mismo que no haberlo medido.
    """
    for line in reversed(tail_lines(eve_path, max_bytes=2_097_152)):
        if '"stats"' not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "stats":
            continue
        captura = (event.get("stats") or {}).get("capture") or {}
        if "kernel_packets" not in captura:
            continue
        return {
            "kernel_packets": captura.get("kernel_packets", 0),
            "kernel_drops": captura.get("kernel_drops", 0),
            # af-packet no siempre publica ifdrops; ausente cuenta como 0
            # porque el contador que importa, kernel_drops, si vino.
            "kernel_ifdrops": captura.get("kernel_ifdrops", 0),
            "errors": captura.get("errors", 0),
            "medido_en": event.get("timestamp"),
        }
    return None


def suricata_metrics(command: str) -> dict | None:
    """Metricas reales de captura via el helper ya autorizado en sudoers.

    Solo se usa como respaldo si ``eve.json`` no trae eventos ``stats``.

    "activo/inactivo" del servicio no dice si esta PERDIENDO paquetes --
    un analista necesita saber eso, no solo si el proceso vive. Sin
    argumentos: la regla sudoers exige exactamente cero argumentos
    (el "" en el sudoers es la sintaxis de sudo para "sin argumentos",
    no un argumento vacio literal -- confirmado contra el uso real ya
    existente en scripts/campaign/start.sh y stop.sh).
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    capture = data.get("suricata", {}).get("capture", {})
    return {
        "service_state": data.get("suricata", {}).get("service_state"),
        "kernel_packets": capture.get("kernel_packets", 0),
        "kernel_drops": capture.get("kernel_drops", 0),
        "kernel_ifdrops": capture.get("kernel_ifdrops", 0),
    }


def load_model_summary(manifest_path: Path, detector_name: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    detector_eval = manifest["evaluation"][detector_name]
    return {
        "detector_name": detector_name,
        "threshold": float(detector_eval["threshold_used"]),
        "test_fpr": float(detector_eval["test"]["fpr"]),
        "detection_rate": float(detector_eval["anomalies"]["detection_rate"]),
        "kali_real_detection_rate": float(detector_eval["anomalies"]["kali_real_detection_rate"]),
    }


# --------------------------------------------------------------- autenticacion
#
# Dos cuentas y nada mas: "admin" ve todo, "lector" solo la vista operativa. El
# admin puede conmutar entre modo operativo y modo desarrollador con un boton,
# pero eso es comodidad, no permiso: esta autorizado a los dos.
#
# La frontera de verdad es el ROL y se aplica en el servidor. Ocultar secciones
# con CSS no sirve de nada -el lector leeria el marcado igual, o llamaria al
# endpoint directamente-, asi que el HTML se recorta por rol y cada ruta
# comprueba quien pregunta.
#
# El login NO sustituye la regla nftables que limita quien alcanza el puerto.
# Son dos capas y se quedan las dos.

ROLES = ("admin", "lector")

# Rutas que solo sirve el administrador. La lista es explicita y una prueba
# recorre las que el servidor despacha de verdad: si se anade un endpoint y
# nadie lo clasifica, la prueba falla en vez de dejarlo abierto.
RUTAS_ADMIN = frozenset({"/api/variables", "/api/artefactos", "/api/escenarios"})

# Rutas que se sirven sin sesion. Solo el login y lo que necesita para pintarse.
RUTAS_PUBLICAS = frozenset({"/login"})

MARCA_INI = "<!--ADMIN-->"
MARCA_FIN = "<!--/ADMIN-->"

COOKIE = "cyberflow_sesion"

# Parametros de scrypt. n=2**14 tarda ~50 ms en el sensor: bastante para que un
# ataque por diccionario no sea gratis, poco para que un login legitimo se note.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


def hash_contrasena(contrasena: str, sal: bytes | None = None) -> str:
    """Devuelve la cadena que se guarda en el fichero de usuarios.

    Lleva dentro los parametros y la sal, asi que se pueden subir en el futuro
    sin invalidar los hashes viejos.
    """
    sal = secrets.token_bytes(16) if sal is None else sal
    dk = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal,
                        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
                                      sal.hex(), dk.hex())


def verificar_contrasena(almacenado: str, contrasena: str) -> bool:
    try:
        algo, n, r, p, sal, esperado = almacenado.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(contrasena.encode("utf-8"), salt=bytes.fromhex(sal),
                            n=int(n), r=int(r), p=int(p), dklen=len(esperado) // 2)
    except (ValueError, TypeError):
        return False
    # compare_digest y no "==": la comparacion normal sale antes en cuanto
    # encuentra un byte distinto, y ese tiempo es informacion.
    return hmac.compare_digest(dk.hex(), esperado)


def firmar_sesion(usuario: str, rol: str, caduca: int, clave: bytes) -> str:
    """Cookie con la sesion DENTRO de la firma: el servidor no guarda estado.

    Sin estado no hay tabla de sesiones que crezca ni que se pierda al
    reiniciar el panel, y la caducidad va firmada, asi que el navegador no
    puede estirarla.
    """
    cuerpo = base64.urlsafe_b64encode(
        ("%s|%s|%d" % (usuario, rol, caduca)).encode("utf-8")).decode().rstrip("=")
    firma = hmac.new(clave, cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    return cuerpo + "." + firma


def leer_sesion(cookie: str, clave: bytes, ahora: float | None = None) -> dict | None:
    """Valida la cookie. Devuelve None ante cualquier duda, sin explicar cual."""
    if not cookie or "." not in cookie:
        return None
    cuerpo, _, firma = cookie.rpartition(".")
    esperada = hmac.new(clave, cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, esperada):
        return None
    try:
        relleno = "=" * (-len(cuerpo) % 4)
        usuario, rol, caduca = base64.urlsafe_b64decode(cuerpo + relleno).decode(
            "utf-8").split("|")
        caduca_i = int(caduca)
    except (ValueError, UnicodeDecodeError):
        return None
    if rol not in ROLES:
        return None
    if (time.time() if ahora is None else ahora) >= caduca_i:
        return None
    return {"usuario": usuario, "rol": rol, "caduca": caduca_i}


class Cerrojo:
    """Bloquea una cuenta tras varios intentos fallidos seguidos.

    En memoria a proposito: el panel es un solo proceso y un reinicio que
    borre los contadores no es un agujero -reiniciarlo requiere root en el
    sensor, que es mas de lo que da adivinar una contrasena-.
    """

    def __init__(self, maximo: int = 5, minutos: int = 15) -> None:
        self.maximo = maximo
        self.segundos = minutos * 60
        self._fallos: dict[str, tuple[int, float]] = {}

    def bloqueado(self, usuario: str, ahora: float | None = None) -> bool:
        t = time.time() if ahora is None else ahora
        _, hasta = self._fallos.get(usuario, (0, 0.0))
        if hasta and t < hasta:
            return True
        if hasta and t >= hasta:
            self._fallos.pop(usuario, None)
        return False

    def fallo(self, usuario: str, ahora: float | None = None) -> None:
        t = time.time() if ahora is None else ahora
        n, _ = self._fallos.get(usuario, (0, 0.0))
        n += 1
        self._fallos[usuario] = (n, t + self.segundos if n >= self.maximo else 0.0)

    def acierto(self, usuario: str) -> None:
        self._fallos.pop(usuario, None)


def cargar_usuarios(ruta: Path) -> dict[str, dict]:
    """Lee el fichero de usuarios. Vive FUERA del repositorio, en modo 0600.

    Nunca en cyberflow.toml, que esta en git: ahi no van credenciales, ni
    siquiera en forma de hash.
    """
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {u: d for u, d in datos.items()
            if isinstance(d, dict) and d.get("rol") in ROLES and d.get("hash")}


_AVISO_AUDITORIA: list[bool] = []


def auditar(ruta: Path | None, evento: str, usuario: str, origen: str,
            rol: str = "", detalle: str = "") -> None:
    """Una linea JSON por evento de sesion, en el formato del registro del motor.

    Un panel con login sin registro de accesos no sirve para nada en una
    auditoria: "quien vio que y cuando" es media pregunta del tribunal.
    """
    if ruta is None:
        return
    linea = json.dumps({
        "event": "panel",
        "tipo": evento,
        "usuario": usuario,
        "rol": rol,
        "origen": origen,
        "detalle": detalle,
        "logged_at": time.time(),
    }, sort_keys=True)
    try:
        with ruta.open("a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError as e:
        # No se deja caer el panel por no poder escribir el registro, pero
        # tampoco se calla: un panel con login cuya auditoria no se escribe es
        # peor que uno sin login, porque aparenta un rastro que no existe. Se
        # avisa UNA vez -si no, cada peticion llenaria el journal-.
        if not _AVISO_AUDITORIA:
            _AVISO_AUDITORIA.append(True)
            print("AVISO: no se puede escribir la auditoria en %s (%s). "
                  "Revisa ReadWritePaths en la unidad." % (ruta, e))


def html_por_rol(plantilla: str, rol: str) -> str:
    """Recorta del HTML lo que el rol no debe ni recibir.

    Para el admin solo se quitan las marcas. Para el lector se elimina el
    contenido que hay entre ellas: no basta con esconderlo, porque el marcado
    viaja igual al navegador y se lee con Ctrl+U.
    """
    if rol == "admin":
        return plantilla.replace(MARCA_INI, "").replace(MARCA_FIN, "")
    trozos = []
    resto = plantilla
    while MARCA_INI in resto:
        antes, _, resto = resto.partition(MARCA_INI)
        trozos.append(antes)
        _, _, resto = resto.partition(MARCA_FIN)
    trozos.append(resto)
    return "".join(trozos)


LOGIN = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberFlow &middot; acceso</title>
<style>
  :root { color-scheme: dark; --bg:#0b1020; --surface:#111a2e; --border:#253150;
          --text:#dbe4f2; --dim:#8da2c0; --accent:#5eead4; --bad:#f87171; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:var(--bg); color:var(--text);
         font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
  form { width: min(92vw, 340px); background:var(--surface);
         border:1px solid var(--border); border-radius:14px; padding:1.6rem; }
  h1 { margin:0 0 0.2rem; font-size:1.15rem; letter-spacing:-0.01em; }
  p.sub { margin:0 0 1.3rem; font-size:0.8rem; color:var(--dim); }
  label { display:block; font-size:0.76rem; color:var(--dim); margin-bottom:0.25rem; }
  input { width:100%; font:inherit; font-size:0.9rem; padding:0.5rem 0.65rem;
          margin-bottom:0.9rem; border-radius:8px; border:1px solid var(--border);
          background:var(--bg); color:var(--text); }
  input:focus { outline:none; border-color:var(--accent); }
  button { width:100%; font:inherit; font-size:0.9rem; font-weight:600;
           padding:0.55rem; border:none; border-radius:8px; cursor:pointer;
           background:var(--accent); color:#06231e; }
  .err { font-size:0.78rem; color:var(--bad); margin:0 0 0.9rem; }
</style>
<form method="post" action="/login">
  <h1>CyberFlow</h1>
  <p class="sub">Panel de solo lectura del motor</p>
  __ERROR__
  <label for="u">Usuario</label>
  <input id="u" name="usuario" autocomplete="username" autofocus required>
  <label for="p">Contraseña</label>
  <input id="p" name="contrasena" type="password" autocomplete="current-password" required>
  <button type="submit">Entrar</button>
</form>
"""


_CACHE_VARIABLES: dict[str, object] = {}


def _cola_de_fichero(path: Path, max_bytes: int) -> list[str]:
    """Ultimas lineas de datos de un CSV, sin leerlo entero.

    El dataset de la linea base llega a ~155.000 filas. Leerlo entero en cada
    peticion del panel costaria mas que todo lo demas junto, y no hace falta:
    para una muestra representativa basta la cola.

    La primera linea SIEMPRE se descarta, y por dos motivos distintos que se
    dan segun el tamano: si el fichero es mayor que la ventana, esa linea viene
    cortada por la mitad; si cabe entero, esa linea es la cabecera. Tratarla
    como dato metia "entity_ip" entre las entidades y "window_end_utc" entre
    las ventanas -visto con datos reales: 18 entidades donde habia 17, y un
    rango temporal que terminaba en "utc"-.
    """
    with path.open("rb") as f:
        f.seek(0, 2)
        tamano = f.tell()
        f.seek(max(0, tamano - max_bytes))
        crudo = f.read().decode("utf-8", errors="replace")
    return crudo.splitlines()[1:]


def muestra_del_dataset(dataset: Path, nombres: list[str],
                        max_bytes: int = 262_144) -> dict:
    """Valores reales por variable, tomados del CSV que se esta acumulando.

    Es lo que convierte la tabla del panel en una medicion y no en un folleto:
    cada variable se explica con numeros que salieron de esta red, no con un
    ejemplo inventado. Si el dataset aun no existe se devuelve vacio y el panel
    lo dice; no se rellena con nada.
    """
    if not dataset.exists():
        return {}
    try:
        with dataset.open("r", encoding="utf-8", errors="replace") as f:
            cabecera = f.readline().rstrip("\n").split(",")
        if not cabecera:
            return {}
        filas = [l.split(",") for l in _cola_de_fichero(dataset, max_bytes) if l.strip()]
        filas = [c for c in filas if len(c) == len(cabecera)]
        if not filas:
            return {}
        idx = {n: i for i, n in enumerate(cabecera)}
        i_ent = idx.get("entity_ip")
        i_ven = idx.get("window_end_utc")

        salida: dict[str, object] = {}
        for nombre in nombres:
            i = idx.get(nombre)
            if i is None:
                continue
            valores = []
            for c in filas:
                try:
                    valores.append(float(c[i]))
                except ValueError:
                    pass
            if not valores:
                continue
            ordenados = sorted(valores)

            # Ejemplos: las ultimas filas con valor distinto de cero, que son
            # las que ensenan algo. Si la variable esta a cero en toda la cola
            # -pasa, y es informacion- se ensenan las ultimas tal cual.
            def fila_ejemplo(c: list[str], v: float) -> dict:
                return {
                    "entidad": c[i_ent] if i_ent is not None else "",
                    "ventana": c[i_ven] if i_ven is not None else "",
                    "valor": v,
                }

            recientes = []
            for c in reversed(filas):
                try:
                    recientes.append((c, float(c[i])))
                except ValueError:
                    continue
                if len(recientes) >= 400:
                    break
            no_cero = [(c, v) for c, v in recientes if v != 0.0]
            elegidos = (no_cero or recientes)[:3]
            ejemplos = [fila_ejemplo(c, v) for c, v in elegidos]
            salida[nombre] = {
                "n": len(ordenados),
                "min": ordenados[0],
                "p50": ordenados[len(ordenados) // 2],
                "max": ordenados[-1],
                "ceros": sum(1 for v in valores if v == 0.0),
                "ejemplos": ejemplos,
            }

        ventanas = {c[i_ven] for c in filas} if i_ven is not None else set()
        entidades = {c[i_ent] for c in filas} if i_ent is not None else set()
        return {
            "_meta": {
                "filas": len(filas),
                "ventanas": len(ventanas),
                "entidades": len(entidades),
                "desde": min(ventanas) if ventanas else "",
                "hasta": max(ventanas) if ventanas else "",
            },
            "por_variable": salida,
        }
    except OSError:
        return {}


def resumen_variables(schema_path: Path, extra_path: Path | None,
                      descripciones_path: Path, dataset: Path | None) -> dict:
    """Esquema + texto editorial + muestra real, listo para pintar la tabla.

    La tabla se GENERA desde el esquema; no se escribe a mano. El texto que
    habia antes decia "seis de red, cinco de transporte y diecisiete de
    aplicacion" cuando el esquema dice nueve, ocho y once: una descripcion
    escrita a mano se desincroniza y nadie lo nota porque la suma cuadra.
    """
    esquema = json.loads(schema_path.read_text(encoding="utf-8"))
    del_motor = {f["name"] for f in esquema["features"]}
    features = list(esquema["features"])

    if extra_path is not None and extra_path.exists():
        extra = json.loads(extra_path.read_text(encoding="utf-8"))
        conocidas = {f["name"] for f in features}
        for f in extra["features"]:
            if f["name"] not in conocidas:
                features.append(f)

    try:
        textos = json.loads(descripciones_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        textos = {"capas": {}, "features": {}}

    dat = muestra_del_dataset(dataset, [f["name"] for f in features]) if dataset else {}
    por_variable = dat.get("por_variable", {}) if dat else {}

    variables = []
    for f in sorted(features, key=lambda x: (x["layer"], x.get("order", 0))):
        t = textos.get("features", {}).get(f["name"], {})
        variables.append({
            "name": f["name"],
            "layer": f["layer"],
            "unit": f.get("unit", ""),
            "window_seconds": f.get("window_seconds"),
            "source": f.get("source", ""),
            "order": f.get("order"),
            "en_motor": f["name"] in del_motor,
            "que": t.get("que", ""),
            "senal": t.get("senal", ""),
            "muestra": por_variable.get(f["name"]),
        })

    capas = []
    for cid in ("L2", "L3", "L4", "L7"):
        de_esta = [v for v in variables if v["layer"] == cid]
        if not de_esta:
            continue
        ct = textos.get("capas", {}).get(cid, {})
        capas.append({
            "id": cid,
            "nombre": ct.get("nombre", cid),
            "que": ct.get("que", ""),
            "senal": ct.get("senal", ""),
            "n": len(de_esta),
            "n_motor": sum(1 for v in de_esta if v["en_motor"]),
        })

    return {
        "paso_segundos": esquema.get("emission_step_seconds"),
        "historia_maxima_s": esquema.get("maximum_history_seconds"),
        "version": esquema.get("schema_version"),
        "n_motor": len(del_motor),
        "n_total": len(variables),
        "capas": capas,
        "variables": variables,
        "dataset": dat.get("_meta") if dat else None,
    }


def _stat_fichero(ruta: Path, tipo: str, que: str) -> dict:
    """Metadatos de UN fichero real. Nunca su contenido: el panel solo mira.

    Si no existe, se dice -no se inventa-. El estado en vivo (tamano, mtime)
    es lo que hace util el mapa: un CSV que no crece o un log parado se ven.
    """
    info = {"ruta": str(ruta), "tipo": tipo, "que": que, "existe": ruta.exists()}
    try:
        if ruta.exists():
            st = ruta.stat()
            info["bytes"] = st.st_size
            info["mtime"] = st.st_mtime
    except OSError:
        pass
    return info


def estado_artefactos(eve_path: Path, dataset: Path | None, manifest_path: Path,
                      log_path: Path, schema_extra: Path | None,
                      descripciones: Path, raiz: Path | None = None,
                      capture_dir: Path = Path("/var/lib/ppi-motor-capture")) -> dict:
    """Los ficheros que cada componente USA de verdad, con su estado en vivo.

    Da nombre y forma al mapa de artefactos del panel: por cada nodo de la
    topologia, los .py/.sh/.pcap/.json/.csv/.joblib que participan. Solo se
    listan los que existen o deberian existir en ESTE despliegue; nada teorico.
    """
    r = raiz or Path.cwd()

    def rel(p: str, tipo: str, que: str) -> dict:
        return _stat_fichero(r / p, tipo, que)

    # El anillo de PCAP es un directorio que rota: se resume, no se lista entero.
    anillo = {"ruta": str(capture_dir / "live-*.pcap"), "tipo": "pcap",
              "que": "anillo de captura crudo (capa 3/4)", "existe": capture_dir.exists()}
    try:
        pcaps = sorted(capture_dir.glob("live-*.pcap"))
        anillo["n"] = len(pcaps)
        if pcaps:
            anillo["bytes"] = sum(f.stat().st_size for f in pcaps)
            anillo["mtime"] = pcaps[-1].stat().st_mtime
    except OSError:
        pass

    modelo_dir = manifest_path.parent
    return {
        "captura": [anillo,
                    rel("scripts/setup/cyberflow_config.py", "py",
                        "genera la unidad de tcpdump y del resto")],
        "suricata": [_stat_fichero(eve_path, "json",
                                   "eventos HTTP/DNS/TLS, una linea por evento")],
        "motor": [rel("scripts/engine/motor_decision.py", "py",
                      "atribuye, extrae y puntua cada ventana"),
                  rel("scripts/features/extract_multilayer_v2.py", "py",
                      "extractor congelado de las 28 variables"),
                  rel("configs/cyberflow.toml", "toml", "alcance, umbral, rutas")],
        "variables": [_stat_fichero(schema_extra, "json", "contrato de las 31 variables")
                      if schema_extra else rel("configs/features/multilayer-v3.json",
                                               "json", "contrato de las 31 variables"),
                      _stat_fichero(descripciones, "json", "texto por variable"),
                      rel("scripts/features/acumular_v3.py", "py",
                          "acumula filas del anillo al dataset"),
                      (_stat_fichero(dataset, "csv", "dataset acumulado")
                       if dataset else rel("artifacts/linea-base/multilayer-v3.csv",
                                           "csv", "dataset acumulado"))],
        "modelo": [_stat_fichero(modelo_dir / "ocsvm_scaled.joblib", "joblib",
                                 "modelo entrenado, umbral congelado"),
                   _stat_fichero(manifest_path, "json", "hashes y evaluacion")],
        "reentrenamiento": [rel("scripts/dataset/particionar_linea_base.py", "py",
                                "parte sin fuga temporal"),
                            rel("scripts/modeling/entrenar_preliminar.py", "py",
                                "entrena y congela el umbral")],
        "control": [rel("scripts/engine/responder_iptables.py", "py",
                        "bloqueo con interlock de calibracion")],
        "registro": [_stat_fichero(log_path, "log", "una linea JSON por decision")],
        "panel": [rel("scripts/engine/dashboard.py", "py", "este panel, solo lectura")],
    }


def cargar_escenarios(ruta: Path) -> dict:
    """Catalogo de escenarios normal/anomalo. Es contenido, no accion.

    El panel lo muestra para copiar y pegar en la propia terminal SSH; el panel
    NUNCA ejecuta estos comandos. Si el fichero falta o es invalido, se devuelve
    vacio en vez de romper el panel.
    """
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"normal": [], "anomalo": []}
    return {"normal": datos.get("normal", []), "anomalo": datos.get("anomalo", [])}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("/home/useransible/ppi-motor-logs/motor_decision.log"),
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=Path("/home/useransible/ppi-motor-model/manifest.json"),
    )
    parser.add_argument("--detector-name", default="ocsvm_scaled")
    parser.add_argument("--enforce-command", default="/usr/local/sbin/ppi-enforce")
    parser.add_argument(
        "--eve-path",
        type=Path,
        default=Path("/var/log/suricata/eve.json"),
        help="registro de Suricata del que se leen los contadores de captura",
    )
    parser.add_argument("--suricata-metrics-command", default="/usr/local/sbin/ppi-suricata-metrics")
    parser.add_argument(
        "--services",
        default="ppi-motor.service,ppi-motor-capture.service,suricata.service",
    )
    parser.add_argument(
        "--calibrado-en-esta-red",
        action="store_true",
        help="declara que el umbral se calibro con trafico de ESTA red. Sin "
             "esta bandera el panel avisa de que las alertas no son fiables, "
             "que es lo correcto mientras se use un umbral de otro sitio",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("configs/features/multilayer-v2.json"),
        help="esquema que usa el motor: define las variables que SE PUNTUAN",
    )
    parser.add_argument(
        "--schema-extra",
        type=Path,
        default=None,
        help="esquema mas amplio -v3- cuyas variables adicionales se acumulan "
             "pero todavia no se puntuan. El panel las marca como tales",
    )
    parser.add_argument(
        "--descripciones",
        type=Path,
        default=Path("configs/features/descripciones.json"),
        help="texto editorial por variable y por capa, separado del esquema",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="CSV acumulado del que se toman los valores de ejemplo. Sin el, "
             "la tabla se pinta igual pero sin muestra: no se inventa ninguna",
    )
    parser.add_argument(
        "--escenarios",
        type=Path,
        default=Path("configs/escenarios.json"),
        help="catalogo de escenarios (normal/anomalo) para el panel guiado",
    )
    parser.add_argument(
        "--usuarios",
        type=Path,
        default=None,
        help="JSON con los usuarios y sus hashes, FUERA del repositorio y en "
             "modo 0600. Sin el, el panel no arranca: prefiere no servir a "
             "servir sin autenticacion",
    )
    parser.add_argument(
        "--clave-sesion",
        type=Path,
        default=None,
        help="fichero con la clave que firma las cookies, 0600. Se genera en "
             "la instalacion con cyberflow_usuarios.py --clave-sesion",
    )
    parser.add_argument("--tls-cert", type=Path, default=None)
    parser.add_argument(
        "--tls-key",
        type=Path,
        default=None,
        help="sin TLS la contrasena viaja en claro por el troncal ESPEJADO y "
             "acaba en el propio anillo de PCAP de CyberFlow",
    )
    parser.add_argument("--auditoria", type=Path, default=None,
                        help="registro de accesos, una linea JSON por evento")
    parser.add_argument("--sesion-minutos", type=int, default=480)
    parser.add_argument("--intentos-max", type=int, default=5)
    parser.add_argument("--bloqueo-minutos", type=int, default=15)
    parser.add_argument(
        "--sin-autenticacion",
        action="store_true",
        help="arranca sin login, como antes. Solo para desarrollo local: "
             "el panel queda accesible a cualquiera que alcance el puerto",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service_names = [name.strip() for name in args.services.split(",") if name.strip()]
    model_summary = load_model_summary(args.manifest_path, args.detector_name)

    # Sin autenticacion solo si se pide EXPRESAMENTE. Si faltan los ficheros y
    # nadie lo pidio, el panel no arranca: servir sin login porque un fichero no
    # estaba es el modo de fallo que hay que evitar.
    auth = not args.sin_autenticacion
    usuarios: dict[str, dict] = {}
    clave = b""
    if auth:
        if args.usuarios is None or args.clave_sesion is None:
            print("faltan --usuarios o --clave-sesion. Generalos con "
                  "scripts/setup/cyberflow_usuarios.py, o arranca con "
                  "--sin-autenticacion si de verdad quieres el panel abierto.")
            return 2
        usuarios = cargar_usuarios(args.usuarios)
        if not usuarios:
            print("el fichero de usuarios esta vacio o no se pudo leer: %s"
                  % args.usuarios)
            return 2
        clave = args.clave_sesion.read_bytes().strip()
        if len(clave) < 32:
            print("la clave de sesion es demasiado corta; regenerala.")
            return 2
        if args.tls_cert is None or args.tls_key is None:
            print("faltan --tls-cert y --tls-key. Sin TLS la contrasena viaja "
                  "en claro por el troncal espejado y acaba en el anillo de "
                  "PCAP de este mismo sistema.")
            return 2

    cerrojo = Cerrojo(args.intentos_max, args.bloqueo_minutos)
    HTML_POR_ROL = {rol: html_por_rol(HTML, rol) for rol in ROLES}

    class Handler(BaseHTTPRequestHandler):
        # ---------------------------------------------------------- sesion
        def _sesion(self) -> dict | None:
            """Quien pregunta, o None. Con --sin-autenticacion, siempre admin."""
            if not auth:
                return {"usuario": "anonimo", "rol": "admin", "caduca": 0}
            crudo = self.headers.get("Cookie", "")
            for parte in crudo.split(";"):
                nombre, _, valor = parte.strip().partition("=")
                if nombre == COOKIE:
                    return leer_sesion(valor, clave)
            return None

        def _origen(self) -> str:
            return self.client_address[0] if self.client_address else "?"

        def _send_html(self, cuerpo: str, codigo: int = 200,
                       cookie: str | None = None) -> None:
            datos = cuerpo.encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            if cookie is not None:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(datos)

        def _login_html(self, error: str = "") -> str:
            marca = '<p class="err">%s</p>' % error if error else ""
            return LOGIN.replace("__ERROR__", marca)

        def _pedir_login(self, json_esperado: bool) -> None:
            if json_esperado:
                body = json.dumps({"error": "sesion requerida"}).encode("utf-8")
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send_html(self._login_html(), 401)

        def _prohibido(self) -> None:
            body = json.dumps({"error": "rol insuficiente"}).encode("utf-8")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ------------------------------------------------------------ POST
        def do_POST(self) -> None:  # noqa: N802
            path, _, _ = self.path.partition("?")
            if path == "/logout":
                s = self._sesion()
                if s:
                    auditar(args.auditoria, "salida", s["usuario"],
                            self._origen(), s["rol"])
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie",
                                 "%s=; Max-Age=0; Path=/; HttpOnly; Secure; "
                                 "SameSite=Strict" % COOKIE)
                self.end_headers()
                return

            if path != "/login":
                self.send_error(404)
                return

            largo = int(self.headers.get("Content-Length", "0") or 0)
            campos = urllib.parse.parse_qs(
                self.rfile.read(min(largo, 4096)).decode("utf-8", "replace"))
            usuario = (campos.get("usuario") or [""])[0][:64]
            contrasena = (campos.get("contrasena") or [""])[0][:256]
            origen = self._origen()

            if cerrojo.bloqueado(usuario):
                auditar(args.auditoria, "bloqueado", usuario, origen)
                self._send_html(self._login_html(
                    "Cuenta bloqueada temporalmente por intentos fallidos."), 429)
                return

            ficha = usuarios.get(usuario)
            # Se comprueba el hash aunque el usuario no exista, contra uno
            # ficticio: si no, un usuario inexistente responderia al instante y
            # eso dice cuales existen.
            almacenado = ficha["hash"] if ficha else hash_contrasena("x" * 24)
            valido = verificar_contrasena(almacenado, contrasena) and ficha is not None

            if not valido:
                cerrojo.fallo(usuario)
                auditar(args.auditoria, "fallo", usuario, origen)
                self._send_html(self._login_html("Usuario o contraseña incorrectos."), 401)
                return

            cerrojo.acierto(usuario)
            caduca = int(time.time() + args.sesion_minutos * 60)
            galleta = firmar_sesion(usuario, ficha["rol"], caduca, clave)
            auditar(args.auditoria, "entrada", usuario, origen, ficha["rol"])
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie",
                "%s=%s; Max-Age=%d; Path=/; HttpOnly; Secure; SameSite=Strict"
                % (COOKIE, galleta, args.sesion_minutos * 60))
            self.end_headers()

        def _send_json(self, payload: dict | list) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path, _, query = self.path.partition("?")

            if path == "/login":
                self._send_html(self._login_html())
                return

            sesion = self._sesion()
            if sesion is None:
                # Las llamadas de la API responden JSON; la pagina, el login.
                self._pedir_login(path.startswith("/api/"))
                return
            if path in RUTAS_ADMIN and sesion["rol"] != "admin":
                auditar(args.auditoria, "denegado", sesion["usuario"],
                        self._origen(), sesion["rol"], path)
                self._prohibido()
                return

            if path == "/":
                # El HTML se recorta por rol ANTES de enviarlo: al lector no le
                # llegan las secciones de desarrollo, no se le ocultan.
                datos = json.dumps({"usuario": sesion["usuario"],
                                    "rol": sesion["rol"]}).replace("<", "\\u003c")
                pagina = HTML_POR_ROL[sesion["rol"]].replace("__SESION__", datos)
                self._send_html(pagina)
                return
            if path == "/api/status":
                decisions = read_decisions(args.log_path, limit=2000)
                self._send_json(
                    {
                        "services": service_status(service_names),
                        "model": model_summary,
                        "blocked": enforcement_list(args.enforce_command),
                        "counters": compute_counters(decisions),
                        "activity": bucket_by_minute(decisions),
                        # eve.json primero: no necesita privilegios. El ayudante
                        # queda como respaldo para despliegues que lo tengan.
                        "capture_metrics": (
                            suricata_stats_desde_eve(args.eve_path)
                            or suricata_metrics(args.suricata_metrics_command)
                        ),
                        "alcance": leer_alcance(args.log_path),
                        "calibracion": {
                            "calibrado_en_esta_red": args.calibrado_en_esta_red,
                        },
                    }
                )
                return
            if path == "/api/variables":
                # El dataset crece durante toda la linea base: se relee solo
                # cuando cambia, no en cada refresco de 5 s del panel.
                sello = None
                if args.dataset and args.dataset.exists():
                    st = args.dataset.stat()
                    sello = (st.st_mtime_ns, st.st_size)
                if _CACHE_VARIABLES.get("sello") != sello or "datos" not in _CACHE_VARIABLES:
                    _CACHE_VARIABLES["sello"] = sello
                    _CACHE_VARIABLES["datos"] = resumen_variables(
                        args.schema, args.schema_extra, args.descripciones,
                        args.dataset)
                self._send_json(_CACHE_VARIABLES["datos"])
                return
            if path == "/api/artefactos":
                self._send_json(estado_artefactos(
                    args.eve_path, args.dataset, args.manifest_path, args.log_path,
                    args.schema_extra, args.descripciones))
                return
            if path == "/api/escenarios":
                self._send_json(cargar_escenarios(args.escenarios))
                return
            if path == "/api/decisions":
                params = dict(pair.split("=") for pair in query.split("&") if "=" in pair)
                limit = int(params.get("limit", "100"))
                self._send_json(read_decisions(args.log_path, limit=limit))
                return
            if path == "/api/activity":
                params = dict(pair.split("=") for pair in query.split("&") if "=" in pair)
                range_param = params.get("range", "1h")
                if range_param == "24h":
                    # Lee mas atras en el archivo (16 MiB en vez de 1 MiB) para
                    # tener una chance real de cubrir 24h de historia. Si el
                    # log no llega tan atras (rotacion, reinicio reciente), los
                    # cubos mas viejos simplemente quedan en cero -- no se
                    # rellena con datos inventados.
                    decisions = read_decisions(args.log_path, limit=200_000, max_bytes=16_777_216)
                    activity = bucket_activity(decisions, bucket_seconds=3600, count=24)
                else:
                    decisions = read_decisions(args.log_path, limit=2000)
                    activity = bucket_activity(decisions, bucket_seconds=60, count=60)
                self._send_json({"range": range_param, "activity": activity})
                return
            if path == "/api/score-histogram":
                decisions = read_decisions(args.log_path, limit=500)
                self._send_json(histogram_scores(decisions, model_summary["threshold"]))
                return
            self.send_error(404)

        def log_message(self, *args_: object) -> None:  # silencioso, evita ruido en journal
            pass

    esquema = "http"
    if args.tls_cert and args.tls_key:
        # TLS_SERVER exige TLS 1.2 como minimo y desactiva la renegociacion
        # insegura por omision. El certificado es autofirmado: no hay CA que
        # valide un sensor interno, asi que se comprueba por huella.
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(args.tls_cert), keyfile=str(args.tls_key))

        class ServidorTLS(ThreadingHTTPServer):
            # El handshake TLS se hace en el hilo de CADA conexion, no en el
            # bucle de aceptar. Envolver el socket de ESCUCHA -lo obvio- serializa
            # el handshake en el hilo principal: un cliente lento o a medias -una
            # pestana colgada, un tunel con conexiones zombis- bloquea a todos los
            # demas y el panel deja de responder (visto: cola de accept sin vaciar
            # y 000 para cualquiera). do_handshake_on_connect=False lo aplaza a la
            # primera lectura, que ya ocurre en el hilo del handler; el timeout
            # evita que un handshake que nunca termina retenga un hilo para siempre.
            daemon_threads = True

            def get_request(self):
                sock, addr = self.socket.accept()
                sock.settimeout(30)
                return ctx.wrap_socket(sock, server_side=True,
                                       do_handshake_on_connect=False), addr

            def handle_error(self, request, client_address):
                pass   # un handshake fallido no es error del servidor

        servidor = ServidorTLS((args.host, args.port), Handler)
        esquema = "https"
    else:
        servidor = ThreadingHTTPServer((args.host, args.port), Handler)
        if auth:
            print("AVISO: hay login pero NO hay TLS. La contrasena viaja en claro.")

    print(f"Dashboard: {esquema}://{args.host}:{args.port}/"
          + ("" if auth else "   [SIN AUTENTICACION]"))
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
