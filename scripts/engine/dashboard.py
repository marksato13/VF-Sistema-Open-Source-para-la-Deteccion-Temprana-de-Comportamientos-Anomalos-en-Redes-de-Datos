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
import sys
import time
import tomllib
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]

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
    /* Paleta categorica para las capas del modelo (L2/L3/L4/L7): tonos vivos y
       distintos entre si, elegidos para NO chocar con los colores semanticos
       (verde=ok, ambar=aviso, rojo=alerta). Contraste medido sobre las
       superficies del panel >= 5.9 (AA de texto normal). */
    --capa-a: #2dd4bf; --capa-b: #60a5fa; --capa-c: #c084fc; --capa-d: #f472b6;
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
  /* display:flex pisa al atributo hidden: sin esto, en modo operativo los
     enlaces de desarrollo seguian en el menu apuntando a secciones ocultas. */
  .side nav a[hidden] { display: none; }
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
  /* El diagrama es HORIZONTAL (ancho): se apila -diagrama arriba a todo el
     ancho, detalle debajo- para que no quede estrecho al lado. */
  .topo-wrap {
    display: grid; grid-template-columns: 1fr; gap: 1rem;
    align-items: start;
  }
  /* Panel de detalle plegado: el diagrama ocupa todo el ancho. */
  .topo-wrap.sin-detalle { grid-template-columns: 1fr; }
  .topo-wrap.sin-detalle .topo-detail { display: none; }
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
  .topo-scroll { overflow: auto; flex: 1; min-height: 0; max-height: 82vh; }
  .topo-scroll svg { display: block; }
  /* Zoom por seccion: un boton por fase que encuadra ese grupo. */
  .topo-fases { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
  .topo-fases .lbl { font: 0.72rem var(--mono); color: var(--text-dim); margin-right: 0.15rem; }
  .topo-fases button {
    font: 600 0.76rem var(--sans); line-height: 1; min-width: 22px;
    background: var(--surface-2); color: var(--text-dim); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.25rem 0.5rem; cursor: pointer;
  }
  .topo-fases button:hover { border-color: var(--accent); color: var(--accent); }

  /* Pantalla completa: el diagrama manda y el detalle se queda al lado. */
  .topo-wrap:fullscreen { background: var(--bg); padding: 1rem; gap: 1rem; height: 100%; grid-template-columns: 1fr; grid-template-rows: minmax(0, 1fr) auto; }
  .topo-wrap:fullscreen .topo-canvas { height: 100%; min-height: 0; }
  .topo-wrap:fullscreen .topo-scroll { height: auto; max-height: none; display: grid; place-items: center; }
  .topo-wrap:fullscreen .topo-detail { overflow-y: auto; max-height: 34vh; }

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
  .topo-node .ttl { fill: var(--text); font: 700 13px var(--sans); }
  .topo-node .sub { fill: var(--text-dim); font: 600 11px var(--mono); font-variant-numeric: tabular-nums; }
  .topo-node .ico { color: var(--text); }
  .topo-node.ok .ico { color: var(--ok); }
  .topo-node.warn .ico { color: var(--amber); }
  .topo-node.bad .ico { color: var(--danger); }
  .topo-node .led { stroke: none; }
  /* Artefacto = algo que se escribe en disco, no un proceso. Se distingue con
     trazo discontinuo para que el diagrama no mienta sobre qué es cada caja. */
  .topo-node.artefacto .box { stroke-dasharray: 5 4; fill: #101827; }
  .topo-node.sumidero .box { stroke-dasharray: 2 3; fill: #16111a; }
  .topo-node .tag { fill: var(--text-dim); font: 600 10px var(--mono); letter-spacing: 0.06em; }

  .topo-edge { stroke: var(--border); stroke-width: 1.6; fill: none; }
  .topo-edge.live { stroke: var(--accent); stroke-dasharray: 5 6; animation: flow 1.1s linear infinite; }
  .topo-edge.dim { stroke: color-mix(in srgb, var(--text-dim) 45%, var(--border)); stroke-dasharray: 3 5; }
  .topo-edge.descarte { stroke: var(--danger); opacity: 0.55; stroke-dasharray: 2 4; animation: none; }
  @keyframes flow { to { stroke-dashoffset: -22; } }
  @media (prefers-reduced-motion: reduce) { .topo-edge.live { animation: none; } }
  .topo-edge-label { fill: var(--text); font: 600 10px var(--mono); }
  .topo-grupo { fill: none; stroke: var(--border); stroke-width: 1; stroke-dasharray: 3 4; opacity: 0.6; }
  .topo-grupo-txt { fill: var(--text); font: 600 10.5px var(--mono); letter-spacing: 0.08em; text-transform: uppercase; }
  .topo-fase-n { fill: color-mix(in srgb, var(--accent) 20%, transparent); stroke: var(--accent); stroke-width: 1; }
  .topo-fase-nt { fill: var(--accent); font: 700 11px var(--mono); }
  .topo-host .box { fill: #101a2e; stroke: color-mix(in srgb, var(--accent) 35%, var(--border)); }
  .topo-host:hover .box { stroke: var(--accent); }
  .topo-host .ico { color: var(--accent); }
  .topo-host .hostip { fill: var(--accent); font: 600 11px var(--mono); }
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

  /* Regla de decision del modelo: recta de score con el umbral y los scores
     reales recientes, para ver DONDE y COMO se decide ALERT vs PERMIT. */
  .modelo-dec { margin: 0.8rem 0 0.2rem; }
  .modelo-dec h4 { font: 600 0.72rem var(--sans); letter-spacing: 0.05em;
    text-transform: uppercase; color: var(--text-dim); margin: 0 0 0.35rem; }
  .modelo-dec .cap { font-size: 0.78rem; color: var(--text-dim); margin-top: 0.35rem; }
  .modelo-dec .cap b.a { color: var(--danger); } .modelo-dec .cap b.p { color: var(--ok); }
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
    padding: 1rem 1.1rem;
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
    /* Franja de color de la capa; --cc-color lo fija el JS por capa. */
    box-shadow: inset 3px 0 0 var(--cc-color, var(--border));
  }
  .var-capa:hover { border-color: var(--accent); }
  .var-capa[aria-pressed="true"] { background: var(--surface-2); border-color: var(--accent); }
  .var-capa .cid { font-size: 0.7rem; letter-spacing: .06em; color: var(--cc-color, var(--accent)); font-weight: 700; }
  .var-capa .cn { font-size: 0.95rem; font-weight: 600; margin-top: 0.1rem; }
  .var-capa .cc { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.15rem; }

  .var-tabla { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .var-grupo { font-size: 0.72rem; letter-spacing: .07em; text-transform: uppercase;
    color: var(--text-dim); background: var(--surface-2); padding: 0.4rem 0.8rem;
    border-bottom: 1px solid var(--border); box-shadow: inset 3px 0 0 var(--cc-color, var(--border)); }
  .var-grupo b { color: var(--cc-color, var(--accent)); font-weight: 700; }
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

  /* Asistente guiado (recorrido). Botón flotante siempre disponible; en modo
     demo se abre solo la primera vez. Foco = recuadro con sombra que oscurece
     todo lo demás; tip = globo con el texto del paso. */
  .tour-fab { position: fixed; right: 18px; bottom: 18px; z-index: 40; display: inline-flex;
    align-items: center; gap: 0.4rem; background: var(--accent); color: #06251f; border: none;
    border-radius: 999px; padding: 0.55rem 0.95rem; font: 600 0.82rem var(--sans); cursor: pointer;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4); }
  .tour-fab:hover { filter: brightness(1.08); }
  .tour-foco { position: fixed; z-index: 50; border-radius: 10px; border: 2px solid var(--accent);
    box-shadow: 0 0 0 9999px rgba(4,8,16,0.62); pointer-events: none; transition: all .2s ease; }
  .tour-tip { position: fixed; z-index: 51; max-width: 340px; background: var(--surface-2);
    border: 1px solid var(--border); border-radius: 12px; padding: 0.9rem 1rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
  .tour-tip h4 { margin: 0 0 0.3rem; font-size: 0.95rem; color: var(--text); }
  .tour-tip p { margin: 0 0 0.75rem; font-size: 0.84rem; color: var(--text-dim); line-height: 1.45; }
  .tour-tip .row { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; }
  .tour-tip .prog { font: 0.74rem var(--mono); color: var(--text-dim); }
  .tour-tip .btns { display: flex; gap: 0.4rem; }
  .tour-tip button { font: 0.8rem var(--sans); border-radius: 7px; padding: 0.32rem 0.72rem;
    cursor: pointer; border: 1px solid var(--border); }
  .tour-tip .next { background: var(--accent); color: #06251f; border-color: var(--accent); font-weight: 600; }
  .tour-tip .prev { background: var(--surface); color: var(--text); }
  .tour-tip .skip { background: none; color: var(--text-dim); }

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
  /* Accion de enforcement: PERMIT deja pasar, LIMIT degrada, BLOCK corta. */
  .badge.acc-permit { background: var(--ok-soft); color: var(--ok); }
  .badge.acc-limit { background: var(--amber-soft); color: var(--amber); }
  .badge.acc-block { background: var(--danger-soft); color: var(--danger); }
  .why { color: var(--text-dim); font-size: 0.82rem; }

  /* Tabla de decisiones: cabecera fija al desplazar la lista larga, y la celda
     de score lleva una mini-barra que situa el valor respecto al umbral. */
  .tbl-scroll { max-height: 420px; overflow-y: auto; }
  .tbl-scroll thead th { position: sticky; top: 0; z-index: 1; background: var(--surface);
    box-shadow: inset 0 -1px 0 var(--border); }
  .score-cell { display: inline-flex; align-items: center; gap: 0.5rem; }
  .score-cell .mini { flex: none; }

  /* Datos en vivo: cada registro con las variables a las que aporta. */
  .vivo-bar { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-bottom: 0.5rem; }
  .vivo-chk { font-size: 0.8rem; color: var(--text-dim); display: inline-flex; gap: 0.3rem; align-items: center; }
  .vivo-tabla { max-height: 560px; }
  .vivo-tabla td { vertical-align: top; }
  .vivo-tabla td.m { font-family: var(--mono); font-size: 0.76rem; white-space: nowrap; }
  .vivo-tabla .sub { color: var(--text-dim); font-size: 0.72rem; }
  .vf { display: inline-block; margin: 0 0.25rem 0.25rem 0; padding: 0.1rem 0.4rem; border-radius: 6px;
    background: var(--surface-2); border: 1px solid var(--border); font-family: var(--mono); font-size: 0.72rem; white-space: nowrap; }
  .vf b { color: var(--accent); font-weight: 600; }
  .vf .ap { color: var(--text-dim); }
  .vf.l2 { border-style: dashed; }
  .vf.l2 b { color: var(--capa-c); }
  .vf.cnt b { color: var(--amber); }
  .vf .par { color: var(--amber); }
  .vivo-tabla .heur { color: var(--amber); font-family: var(--mono); font-size: 0.74rem; }
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
    <a href="#s-vivo" data-sec="s-vivo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h3l2-5 3 10 2-6 2 3h6"/></svg>Datos en vivo</a>
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
    <p class="lede-small">Tres vistas del sistema. <strong>Operacional</strong>: cómo funciona en vivo; del espejo salen dos fuentes (PCAP crudo y eve.json de Suricata), cada una con su parser, que juntas arman las variables por IP y ventana. <strong>Construcción y entrenamiento</strong>: de los datos al modelo congelado y su ciclo de vida (partición, candidatos, métricas, selección, congelación, despliegue, reentrenamiento y comparación antes/después). <strong>Fases del método</strong>: las siete fases de la tesis. Pulsa cualquier componente para ver su detalle; desde las fuentes se abre «Datos en vivo».</p>
    <div class="topo-wrap" id="topoWrap">
      <div class="topo-canvas" id="topoCanvas">
        <div class="topo-bar">
          <div class="range-toggle" id="topoVista">
            <button data-vista="completa" class="active">Operacional</button>
            <button data-vista="construccion">Construcción y entrenamiento</button>
            <button data-vista="metodologica">Fases del método</button>
          </div>
          <div class="topo-zoom">
            <button id="topoMenos" title="Reducir" aria-label="Reducir">&minus;</button>
            <span id="topoNivel">100%</span>
            <button id="topoMas" title="Ampliar" aria-label="Ampliar">+</button>
            <button id="topoReset" title="Ver todo el diagrama" aria-label="Ver todo el diagrama">Ajustar</button>
          </div>
          <div class="topo-fases" id="topoFases"></div>
          <button id="topoArchivosBtn" class="export-btn" title="Muestra los ficheros que usa cada componente" aria-pressed="false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h6l2 3h8v13H4Z"/></svg>
            <span>Ver archivos</span>
          </button>
          <button id="topoDetalleBtn" class="export-btn" title="Oculta el panel de la derecha para ver el diagrama a lo ancho" aria-pressed="false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><line x1="15" y1="4" x2="15" y2="20"/></svg>
            <span id="topoDetalleTxt">Ocultar panel</span>
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

  <section id="s-vivo">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h3l2-5 3 10 2-6 2 3h6"/></svg><h2>Datos en vivo: del registro a la variable</h2></div>
    <p class="lede-small">Las dos fuentes salen del mismo puerto espejo (SPAN): el <strong>PCAP</strong> es la captura cruda de tcpdump y <strong>eve.json</strong> los eventos que Suricata escribe tras procesar esas mismas tramas. Aquí se ve un tramo reciente de cada una pasado por <em>la misma cadena del motor</em> (parser, atribución a la entidad que inicia el flujo, ventanas de 10/30/60 s), y solo se listan los registros que <strong>aportan a alguna variable</strong>: cuál actualizan, con qué aporte y cuánto vale la variable en la ventana que los incorpora.</p>
    <div class="vivo-bar">
      <div class="range-toggle" id="vivoTabs">
        <button data-vtab="eve" class="active">Eventos eve.json</button>
        <button data-vtab="pcap">Tramas PCAP</button>
        <button data-vtab="matriz">Matriz de trazabilidad</button>
      </div>
      <input type="text" id="vivoFiltro" class="ip-filter" placeholder="Filtrar por IP o variable...">
      <label class="vivo-chk" id="vivoTodosLbl"><input type="checkbox" id="vivoTodos"> todas las tramas</label>
      <button id="vivoPausa" class="export-btn" type="button">Pausar</button>
    </div>
    <p class="toolbar-hint" id="vivoResumen">Cargando&hellip;</p>
    <div class="tbl-wrap tbl-scroll vivo-tabla" id="vivoTabla"></div>
    <p class="toolbar-hint" id="vivoPie"></p>
  </section>

  <section id="s-modelo">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/><line x1="2" y1="9" x2="6" y2="9"/><line x1="2" y1="15" x2="6" y2="15"/><line x1="18" y1="9" x2="22" y2="9"/><line x1="18" y1="15" x2="22" y2="15"/></svg><h2>Modelo congelado</h2></div>
    <div class="grid" id="model"></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="16.5" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Punto débil conocido:</strong> este modelo detecta peor la fuerza bruta de contraseñas (50&ndash;55%) que el resto de familias de ataque (&gt;80%). Una decisión PERMIT en ese escenario es menos confiable que en otros.</span></div>

    <p class="lede-small" id="pruebasPrevias" style="margin-top:1.4rem"><strong style="color:var(--text)">Pruebas previas &mdash; comparación exploratoria de modelos.</strong> Se compararon <strong>7 candidatos</strong> con las mismas variables y la misma partición (<code>compare_frozen_models_metrics.py</code>, auditable desde <em>Topología &rarr; Ver contenido</em>). El conjunto positivo son 179 ventanas de anomalía; el negativo, 276 ventanas normales de prueba. Se reportan F1, MCC, ROC&#8209;AUC y precisión media, sin reentrenar y verificando cada modelo contra el manifiesto. La selección posterior a ver resultados de prueba limita la estimación de generalización.</p>
    <p class="lede-small">Y la detección no la hace el modelo solo. La <strong>ablación por componentes</strong> mide qué aporta cada pieza sobre 9 episodios (3 familias con 3 repeticiones):</p>
    <div class="grid">
      <div class="card"><div class="label">Modelo solo</div><div class="value">6 / 9</div></div>
      <div class="card"><div class="label">Heurísticos solos</div><div class="value">7 / 9</div></div>
      <div class="card accent"><div class="label">Modelo + heurísticos</div><div class="value">9 / 9</div></div>
    </div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span>La <strong>complementariedad es el resultado medido</strong>: el modelo detectó flood HTTP y escaneo en esta batería, pero <strong>0/3 DNS</strong>; el heurístico DNS cubrió ese hueco. La fuerza bruta en vivo la confirma el heurístico <code>brute_force</code>. La combinación cubrió 9/9 episodios de las tres primeras familias; no significa que el modelo solo los cubra. La comparación con Suricata y sus límites están en la nota 32 del repositorio de orquestación.</span></div>
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
        <thead><tr><th>Hora</th><th>IP</th><th>Decisión</th><th>Acción</th><th>Motivo</th><th>Score <span class="th-sub">(← umbral)</span></th><th>Paquetes</th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>

<style>
.ver-codigo{margin-top:6px;background:#15202c;border:1px solid #2b3a4a;color:#9fd0ff;border-radius:7px;padding:4px 9px;font-size:11px;cursor:pointer}
.ver-codigo:hover{background:#1b2a39;border-color:#3a5169}
.code-modal{position:fixed;inset:0;background:rgba(2,6,12,.72);z-index:300;display:flex;align-items:center;justify-content:center;padding:26px}
.code-modal[hidden]{display:none}
.code-box{background:#0f1720;border:1px solid #27333f;border-radius:12px;width:min(1000px,94vw);max-height:88vh;display:flex;flex-direction:column;box-shadow:0 24px 70px rgba(0,0,0,.6)}
.code-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid #27333f;font-weight:600;color:#e6eef7}
.code-head button{background:none;border:none;color:#8aa0b2;font-size:24px;line-height:1;cursor:pointer}
.code-head button:hover{color:#fff}
.code-sub{padding:7px 16px;font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#7d93a6;border-bottom:1px solid #1b2530}
.code-pre{margin:0;padding:14px 16px;overflow:auto;white-space:pre;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#d6e2ee;background:#0a1118;border-radius:0 0 12px 12px}
</style>
<div class="code-modal" id="codeModal" hidden>
  <div class="code-box">
    <div class="code-head"><span id="codeTitle"></span><button id="codeClose" type="button" aria-label="Cerrar">&times;</button></div>
    <div class="code-sub" id="codeSub"></div>
    <pre class="code-pre"><code id="codeBody"></code></pre>
  </div>
</div>
<button class="tour-fab" id="tourBtn" title="Recorrido guiado">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.4 9.2a2.6 2.6 0 1 1 3.7 2.4c-.8.4-1.1 1-1.1 1.8"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg>
  Guía
</button>
<div class="tour-foco" id="tourFoco" style="display:none"></div>
<div class="tour-tip" id="tourTip" style="display:none"></div>
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
  if_recalibrado_2026_09: 'modelo recalibrado (IsolationForest)',
  if_recalibrado: 'modelo recalibrado (IsolationForest)',
  auth_failure_heuristic: 'fuerza bruta (heurístico)',
  brute_force: 'fuerza bruta (heurístico)',
  port_scan: 'escaneo de puertos (heurístico)',
  http_abuse: 'abuso HTTP (heurístico)',
  dns_entropy: 'DNS de alta entropía (heurístico)',
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

function renderHealthbar(services, counters, captureMetrics, calibracion, modo) {
  const el = document.getElementById('healthbar');
  // Modo demo: datos de ejemplo del repositorio, sin captura en vivo ni
  // servicios reales. Se dice claramente para no aparentar una operación real.
  if (modo === 'demo') {
    el.className = 'healthbar warn';
    el.innerHTML = `<span class="dot"></span><div><div class="msg">MODO DEMO &mdash; datos de ejemplo del repositorio</div>` +
      `<div class="sub">Estás viendo cómo funciona CyberFlow con decisiones de muestra, sin captura en vivo ni sensor. ` +
      `Para usarlo en tu red, sigue la instalación (modo despliegue).</div></div>`;
    return;
  }
  const allUp = Object.values(services).every(Boolean);
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

// --- Asistente guiado: recorre el flujo de CyberFlow paso a paso -----------
// Se abre solo en modo demo la primera vez (se recuerda en localStorage) y queda
// disponible siempre en el botón flotante. Cada paso enfoca una sección; los
// pasos cuyo elemento no existe -por rol o vista- se saltan solos.
const TOUR_PASOS = [
  { sel: '#kpis', t: 'Las cifras clave', d: 'Cuatro números de un vistazo: entidades vigiladas, ventanas analizadas por hora, cuántos scores rozan el umbral y las alertas reales de la última hora.' },
  { sel: '#s-topologia', t: 'El recorrido del paquete', d: 'De la red al veredicto: captura → variables por capa → modelo y heurísticos → decisión → respuesta en el host. Pulsa cualquier componente para ver qué hace.' },
  { sel: '#topoVista', t: 'Tres vistas del sistema', d: 'Operacional: dos fuentes y dos parsers hasta la decisión. Construcción y entrenamiento: de los datos al modelo congelado y su reentrenamiento. Fases del método: las siete fases de la tesis.' },
  { sel: '#topoArchivosBtn', t: 'Código auditable', d: 'En modo desarrollador, pulsa Ver archivos, elige un componente y un archivo; en su ficha pulsa ◎ Ver contenido. El visor es de solo lectura y solo muestra rutas permitidas.' },
  { sel: '#s-modelo', t: 'El detector activo y su umbral', d: 'El detector desplegado aprende la normalidad de esta red; el umbral se fijó con validación. Aquí ves el modelo activo y sus métricas, no una etiqueta fija de OCSVM.' },
  { sel: '#pruebasPrevias', t: 'Pruebas previas', d: 'Siete modelos se compararon en el estudio; la ablación sobre nueve episodios separa modelo solo (6), heurísticos solos (7) y ambos combinados (9). No confundas el 9/9 del sistema con el modelo solo.' },
  { sel: '#s-scores', t: 'Distribución de scores', d: 'No solo si alertó o no, sino cuánto margen hubo respecto al umbral. Rojo = ALERT, verde = PERMIT.' },
  { sel: '#s-decisiones', t: 'Las decisiones', d: 'Cada ventana con su decisión, su score frente al umbral (la mini-barra) y el motivo. Filtrable por IP y exportable.' },
  { sel: '#s-simulacion', t: 'Escenarios guiados', d: 'Comandos listos para provocar tráfico normal o un ataque y ver cómo responde el modelo. El panel no ejecuta: copias el comando y observas.' },
  { sel: null, t: 'Esto es el demo', d: 'Estás viendo datos de ejemplo. Para usarlo en tu propia red, sigue la instalación del README (modo despliegue) y recalibra con tu tráfico.' },
];
let tourI = 0, tourPasos = [], tourAuto = false;

function tourInit() { tourPasos = TOUR_PASOS.filter(p => !p.sel || document.querySelector(p.sel)); }
function tourEnd() {
  const f = document.getElementById('tourFoco'), t = document.getElementById('tourTip');
  if (f) f.style.display = 'none';
  if (t) t.style.display = 'none';
}
function tourStart() {
  tourInit();
  if (!tourPasos.length) return;
  tourI = 0;
  try { localStorage.setItem('cf_tour_visto', '1'); } catch (e) {}
  tourShow();
}
function tourNav(d) { tourI += d; tourShow(); }
function tourShow() {
  const foco = document.getElementById('tourFoco'), tip = document.getElementById('tourTip');
  if (tourI >= tourPasos.length) { tourEnd(); return; }
  if (tourI < 0) tourI = 0;
  const paso = tourPasos[tourI], total = tourPasos.length;
  const el = paso.sel ? document.querySelector(paso.sel) : null;
  tip.innerHTML = `<h4>${paso.t}</h4><p>${paso.d}</p>`
    + `<div class="row"><span class="prog">${tourI + 1} / ${total}</span><div class="btns">`
    + (tourI > 0 ? `<button class="prev" onclick="tourNav(-1)">Atrás</button>` : '')
    + `<button class="skip" onclick="tourEnd()">Cerrar</button>`
    + `<button class="next" onclick="tourNav(1)">${tourI === total - 1 ? 'Listo' : 'Siguiente'}</button>`
    + `</div></div>`;
  tip.style.display = 'block';
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
      const r = el.getBoundingClientRect();
      foco.style.display = 'block';
      foco.style.left = (r.left - 6) + 'px'; foco.style.top = (r.top - 6) + 'px';
      foco.style.width = (r.width + 12) + 'px'; foco.style.height = (r.height + 12) + 'px';
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let top = r.bottom + 12;
      if (top + th > window.innerHeight - 8) top = Math.max(8, r.top - th - 12);
      let left = r.left + r.width / 2 - tw / 2;
      left = Math.max(8, Math.min(window.innerWidth - tw - 8, left));
      tip.style.left = left + 'px'; tip.style.top = top + 'px';
    }, 260);
  } else {
    foco.style.display = 'none';
    tip.style.left = (window.innerWidth / 2 - tip.offsetWidth / 2) + 'px';
    tip.style.top = (window.innerHeight / 2 - tip.offsetHeight / 2) + 'px';
  }
}
function tourQuizasAuto(modo) {
  if (tourAuto || modo !== 'demo') return;
  tourAuto = true;
  let visto = false;
  try { visto = localStorage.getItem('cf_tour_visto') === '1'; } catch (e) {}
  if (!visto) setTimeout(tourStart, 700);
}
on('tourBtn', 'click', tourStart);

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
    renderHealthbar(status.services, status.counters, status.capture_metrics, status.calibracion, status.modo);
    tourQuizasAuto(status.modo);
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
      // Una métrica que el manifiesto no trae llega como null: se muestra «—»,
      // no un 0 % que parecería una medición.
      const pct = (v, d) => (v == null ? '—' : (v * 100).toFixed(d) + '%');
      modelEl.innerHTML = [
        card('Detector', escSimple(DETECTOR_LABEL[m.detector_name] || m.detector_name || 'no disponible')),
        card('Umbral', m.threshold.toFixed(4), 'accent'),
        card('FPR benigno', pct(m.test_fpr, 2)),
        card('Detección global', pct(m.detection_rate, 1), 'accent'),
        card('Detección Kali-real', pct(m.kali_real_detection_rate, 1), 'accent'),
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

// La ACCION que el enforcement aplicaria para esta decision. Misma logica que
// publicar_feed.py: un heuristico confirmado manda (BLOCK o LIMIT); si no, una
// anomalia del modelo (ALERT) degrada a LIMIT; lo demas, PERMIT. Si el motor
// aun no emite el campo `heuristico` (no reiniciado), se cae a modelo/PERMIT.
function accionDeDecision(d) {
  if (d.heuristico && d.heuristico.accion) return d.heuristico.accion;
  return d.decision === 'ALERT' ? 'LIMIT' : 'PERMIT';
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
    const accion = accionDeDecision(d);
    const accBadge = `<span class="badge acc-${accion.toLowerCase()}">${accion}</span>`;
    const scoreCell = d.score != null
      ? `<span class="score-cell"><span>${d.score.toFixed(4)}</span>${miniBarraScore(d.score)}</span>`
      : '&mdash;';
    // Si disparo un heuristico (deteccion SIN firma), se muestra cual y su motivo;
    // si no, la etiqueta del detector/modelo.
    const motivoTxt = (d.heuristico && d.heuristico.heuristico)
      ? `<span class="badge heur" title="heurístico determinista — detección sin firma">${d.heuristico.heuristico}</span> ${d.heuristico.motivo || ''}`
      : (DETECTOR_LABEL[d.detector_name] || d.detector_name);
    return `<tr class="${isAlert ? 'row-alert' : ''}"><td>${fmtTime(d.logged_at)}</td><td class="ip">${d.entity_ip}</td>` +
      `<td>${badge}</td><td>${accBadge}</td><td class="why">${motivoTxt}</td>` +
      `<td class="num">${scoreCell}</td><td class="num">${d.packet_count_10s}</td></tr>`;
  }).join('') : `<tr class="empty-row"><td colspan="7">${query ? 'Ninguna decisión coincide con el filtro.' : 'Sin decisiones recientes.'}</td></tr>`;
}

on('ipFilter', 'input', renderDecisionsTable);

on('exportCsv', 'click', () => {
  const query = document.getElementById('ipFilter').value.trim();
  const rows = query ? lastDecisions.filter(d => d.entity_ip.includes(query)) : lastDecisions;
  const header = ['hora_utc', 'ip', 'decision', 'accion', 'motivo', 'score', 'paquetes_10s'];
  const csvRows = rows.map(d => [
    d.window_end_utc,
    d.entity_ip,
    d.decision,
    accionDeDecision(d),
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
  captura:  '<circle cx="9" cy="9" r="6.6"/><circle cx="9" cy="9" r="2.4" fill="currentColor" stroke="none"/>',
  reglas:   '<path d="M4 2.4h7l3 3v10.2H4Z"/><path d="M6.4 7h5M6.4 9.8h5M6.4 12.6h3"/>',
  ciclo:    '<path d="M15.2 9a6.2 6.2 0 1 1-1.9-4.5"/><path d="M15.4 2.6V6.1h-3.5"/>',
  decision: '<path d="M9 2 16 9 9 16 2 9Z"/><path d="M9 6.2v2.4M6.9 11h4.2"/>',
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
      { id: 'modelo',   x: 210, y: 438, w: 200, h: 58, icono: 'modelo', titulo: 'Modelo recalibrado' },
      { id: 'control',  x: 210, y: 524, w: 200, h: 58, icono: 'escudo', titulo: 'Respuesta: LIMIT/BLOCK' },
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
    w: 1790, h: 500,
    // Flujo HORIZONTAL de izquierda a derecha: cada fase es una columna
    // (Hosts | Adquisicion | Analisis | Decision | Observabilidad) y el paquete
    // avanza de izquierda a derecha. Un punto lo recorre en vivo.
    packet: 'M374,70 L374,275 L540,139 L628,215 L894,139 L894,249 L1148,187 L1424,187 L1680,183',
    grupos: [
      { x: 12,   y: 32, w: 200, h: 456, txt: 'Hosts · VLAN 20/30' },
      { x: 272,  y: 32, w: 460, h: 456, txt: 'Adquisición',          n: 1 },
      { x: 792,  y: 32, w: 470, h: 456, txt: 'Análisis',             n: 2 },
      { x: 1322, y: 32, w: 196, h: 456, txt: 'Decisión y respuesta', n: 3 },
      { x: 1578, y: 32, w: 196, h: 456, txt: 'Observabilidad',       n: 4 },
    ],
    nodos: [
      { id: 'atacante', x: 24, y: 70,  w: 176, h: 48, icono: 'lupa',   titulo: 'Atacante (Kali)',   host: true, ip: '10.10.20.30',     desc: 'lanza los ataques' },
      { id: 'clientes', x: 24, y: 140, w: 176, h: 48, icono: 'red',    titulo: 'Clientes',          host: true, ip: '10.10.20.21-.26', desc: '6 perfiles legítimos' },
      { id: 'servidor', x: 24, y: 210, w: 176, h: 48, icono: 'disco',  titulo: 'Servidor',          host: true, ip: '10.10.30.10',     desc: 'objetivo HTTP/HTTPS' },
      { id: 'gateway',  x: 24, y: 280, w: 176, h: 48, icono: 'escudo', titulo: 'pfSense / gateway', host: true, ip: '10.10.20.1',      desc: 'enruta entre VLAN' },
      { id: 'red',       x: 286, y: 70,  w: 176, h: 58, icono: 'red',    titulo: 'Red de la entidad',  tag: 'VLAN 10-100' },
      { id: 'span',      x: 286, y: 158, w: 176, h: 58, icono: 'espejo', titulo: 'Espejo SPAN',        tag: 'CORE-STACK' },
      { id: 'nic',       x: 286, y: 246, w: 176, h: 58, icono: 'nic',    titulo: 'Interfaz en escucha', tag: 'ens37 · SIN IP' },
      { id: 'captura',   x: 540, y: 110, w: 176, h: 58, icono: 'captura', titulo: 'tcpdump',           tag: 'SERVICIO' },
      { id: 'pcap',      x: 540, y: 192, w: 176, h: 46, icono: 'fichero', titulo: 'anillo live-*.pcap', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'suricata',  x: 540, y: 274, w: 176, h: 58, icono: 'lupa',   titulo: 'Suricata',           tag: 'SERVICIO' },
      { id: 'eve',       x: 540, y: 356, w: 176, h: 46, icono: 'fichero', titulo: 'eve.json',          tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'motor',     x: 806, y: 110, w: 176, h: 58, icono: 'cpu',    titulo: 'Parser de paquetes', tag: 'TRAMA → FLUJO · L2·L3·L4' },
      { id: 'variables', x: 806, y: 220, w: 176, h: 58, icono: 'tabla',  titulo: 'Variables / 10 s',   tag: 'POR IP Y VENTANA' },
      { id: 'parser_eve', x: 806, y: 330, w: 176, h: 58, icono: 'reglas', titulo: 'Parser de eventos', tag: 'JSON → L7 · HTTP·DNS·TLS' },
      { id: 'descartes', x: 806, y: 420, w: 176, h: 48, icono: 'tijera', titulo: 'Fuera del cálculo',  tag: 'SUMIDERO', clase: 'sumidero' },
      { id: 'reentrenamiento', x: 1060, y: 70, w: 176, h: 58, icono: 'ciclo', titulo: 'Reentrenamiento', tag: 'POLÍTICA PROPUESTA' },
      { id: 'modelo',    x: 1060, y: 158, w: 176, h: 58, icono: 'modelo', titulo: 'Modelo recalibrado', tag: 'IF · CALIBRADO' },
      { id: 'heuristicos', x: 1060, y: 276, w: 176, h: 58, icono: 'reglas', titulo: 'Heurísticos',     tag: 'DETERMINISTAS' },
      { id: 'control',   x: 1336, y: 158, w: 176, h: 58, icono: 'decision', titulo: 'Decisión',        tag: 'PERMIT · ALERT → LIMIT/BLOCK' },
      { id: 'feed',      x: 1336, y: 256, w: 176, h: 58, icono: 'fichero', titulo: 'Feed firmado',     tag: 'ed25519' },
      { id: 'agente',    x: 1336, y: 354, w: 176, h: 58, icono: 'escudo', titulo: 'Agente en host',   tag: 'nftables LIMIT/BLOCK' },
      { id: 'registro',  x: 1592, y: 160, w: 176, h: 46, icono: 'fichero', titulo: 'motor_decision.log', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'panel',     x: 1592, y: 256, w: 176, h: 52, icono: 'ojo',    titulo: 'Este panel',        tag: 'SOLO LECTURA' },
      { id: 'wazuh',     x: 1592, y: 352, w: 176, h: 52, icono: 'ojo',    titulo: 'Wazuh (SIEM)',      tag: 'CONCENTRADOR' },
    ],
    aristas: [
      { d: 'M200,94 L286,90',                       desde: 'atacante', hasta: 'red', etiqueta: 'ataca',    ex: 243, ey: 82 },
      { d: 'M200,164 C250,150 262,100 286,96',      desde: 'clientes', hasta: 'red', etiqueta: 'tráfico',  ex: 250, ey: 152 },
      { d: 'M200,234 C252,210 264,106 286,102',     desde: 'servidor', hasta: 'red', etiqueta: 'objetivo', ex: 252, ey: 214 },
      { d: 'M200,304 C254,270 266,112 286,108',     desde: 'gateway',  hasta: 'red', etiqueta: 'enruta',   ex: 252, ey: 292 },
      { d: 'M374,128 L374,158',                     desde: 'red',      hasta: 'span', etiqueta: 'al troncal', ex: 502, ey: 143 },
      { d: 'M374,216 L374,246',                     desde: 'span',     hasta: 'nic',  etiqueta: 'copia', ex: 500, ey: 231 },
      { d: 'M462,275 C500,268 516,146 540,139',     desde: 'nic',      hasta: 'captura', etiqueta: 'paquetes', ex: 500, ey: 188 },
      { d: 'M462,275 C500,282 516,300 540,303',     desde: 'nic',      hasta: 'suricata', etiqueta: 'paquetes', ex: 500, ey: 322 },
      { d: 'M628,168 L628,192',                     desde: 'captura',  hasta: 'pcap' },
      { d: 'M628,332 L628,356',                     desde: 'suricata', hasta: 'eve' },
      { d: 'M716,215 C760,208 772,146 806,139',     desde: 'pcap',     hasta: 'motor', etiqueta: 'tramas', ex: 762, ey: 165 },
      { d: 'M716,379 C760,376 776,362 806,359',     desde: 'eve',      hasta: 'parser_eve', etiqueta: 'eventos', ex: 760, ey: 394 },
      { d: 'M894,168 L894,220',                     desde: 'motor',    hasta: 'variables', etiqueta: 'L2·L3·L4 por IP', ex: 950, ey: 198 },
      { d: 'M894,330 L894,278',                     desde: 'parser_eve', hasta: 'variables', etiqueta: 'L7 por IP', ex: 936, ey: 308 },
      { d: 'M806,150 C752,240 752,420 806,446',     desde: 'motor',    hasta: 'descartes', tipo: 'descarte', etiqueta: 'descarta', ex: 768, ey: 290 },
      { d: 'M982,249 C1020,242 1036,193 1060,187',  desde: 'variables', hasta: 'modelo', etiqueta: '28 al modelo', ex: 1020, ey: 232 },
      { d: 'M982,249 C1020,256 1036,300 1060,305',  desde: 'variables', hasta: 'heuristicos', etiqueta: 'variables + conteos', ex: 1022, ey: 300 },
      { d: 'M1148,128 L1148,158',                   desde: 'reentrenamiento', hasta: 'modelo', etiqueta: 'entrena y congela', ex: 1200, ey: 143 },
      { d: 'M1236,187 L1336,187',                   desde: 'modelo',   hasta: 'control', etiqueta: 'score &lt; umbral', ex: 1286, ey: 178 },
      { d: 'M1236,305 C1290,300 1302,196 1336,192', desde: 'heuristicos', hasta: 'control', etiqueta: 'confirmado', ex: 1290, ey: 250 },
      { d: 'M1424,216 L1424,256',                   desde: 'control',  hasta: 'feed', etiqueta: 'veredicto firmado', ex: 1424, ey: 243 },
      { d: 'M1424,314 L1424,354',                   desde: 'feed',     hasta: 'agente', etiqueta: 'pull + verifica', ex: 1424, ey: 337 },
      { d: 'M1512,187 C1550,185 1562,184 1592,183', desde: 'control',  hasta: 'registro', etiqueta: 'cada decisión', ex: 1552, ey: 175 },
      { d: 'M1680,206 L1680,256',                   desde: 'registro', hasta: 'panel', etiqueta: 'lee', ex: 1698, ey: 234 },
      { d: 'M1660,206 C1585,270 1585,330 1660,352', desde: 'registro', hasta: 'wazuh', etiqueta: 'syslog', ex: 1642, ey: 336 },
    ],
  },
  // --- Vista METODOLOGICA: como se CONSTRUYO (las 7 fases del metodo) -------
  metodologica: {
    w: 1632, h: 300,
    packet: 'M32,149 L1608,149',
    grupos: [
      { x: 20,   y: 20, w: 210, h: 240, txt: 'Datos y línea base',  n: 1 },
      { x: 250,  y: 20, w: 210, h: 240, txt: 'Preproceso y features', n: 2 },
      { x: 480,  y: 20, w: 210, h: 240, txt: 'Modelado híbrido',    n: 3 },
      { x: 710,  y: 20, w: 210, h: 240, txt: 'Experimento y eval.', n: 4 },
      { x: 940,  y: 20, w: 210, h: 240, txt: 'Respuesta',           n: 5 },
      { x: 1170, y: 20, w: 210, h: 240, txt: 'Despliegue',          n: 6 },
      { x: 1400, y: 20, w: 210, h: 240, txt: 'Validación',          n: 7 },
    ],
    nodos: [
      { id: 'm_datos',  x: 32,   y: 118, w: 196, h: 62, icono: 'disco',    titulo: 'Línea base real',       tag: 'SPAN · PCAP · eve' },
      { id: 'm_feat',   x: 262,  y: 118, w: 196, h: 62, icono: 'tabla',    titulo: '28 features L3/L4/L7',  tag: 'extractor congelado' },
      { id: 'm_modelo', x: 492,  y: 118, w: 196, h: 62, icono: 'modelo',   titulo: 'IF + heurísticos',      tag: 'híbrido' },
      { id: 'm_eval',   x: 722,  y: 118, w: 196, h: 62, icono: 'lupa',     titulo: 'Replay vs Suricata',    tag: '9/9 vs 0/9' },
      { id: 'm_resp',   x: 952,  y: 118, w: 196, h: 62, icono: 'escudo',   titulo: 'PERMIT/LIMIT/BLOCK',    tag: 'feed firmado' },
      { id: 'm_desp',   x: 1182, y: 118, w: 196, h: 62, icono: 'nic',      titulo: 'Desplegado en sensor',  tag: 'systemd · replicable' },
      { id: 'm_valid',  x: 1412, y: 118, w: 196, h: 62, icono: 'ojo',      titulo: 'Interna + externa',     tag: 'demo · TAM' },
    ],
    aristas: [
      { d: 'M228,149 L262,149',   desde: 'm_datos',  hasta: 'm_feat' },
      { d: 'M458,149 L492,149',   desde: 'm_feat',   hasta: 'm_modelo' },
      { d: 'M688,149 L722,149',   desde: 'm_modelo', hasta: 'm_eval' },
      { d: 'M918,149 L952,149',   desde: 'm_eval',   hasta: 'm_resp' },
      { d: 'M1148,149 L1182,149', desde: 'm_resp',   hasta: 'm_desp' },
      { d: 'M1378,149 L1412,149', desde: 'm_desp',   hasta: 'm_valid' },
    ],
  },
  // --- Vista CONSTRUCCION Y ENTRENAMIENTO: de los datos al modelo congelado
  // (fila 1, una vez y en seco) y su ciclo de vida (fila 2, de derecha a
  // izquierda). Responde: donde se entrena, como se partio, que se comparo, con
  // que metricas, por que gano, que cambia al reentrenar y cada cuanto.
  construccion: {
    w: 1560, h: 400,
    packet: 'M140,104 L1420,104 L1420,284 L396,284',
    grupos: [
      { x: 20, y: 36,  w: 1520, h: 130, txt: 'Construcción: una vez, en seco, con datos de esta red', n: 1 },
      { x: 20, y: 216, w: 1520, h: 130, txt: 'Operación y ciclo de vida', n: 2 },
    ],
    nodos: [
      { id: 'c_datos',   x: 40,   y: 72,  w: 200, h: 64, icono: 'disco',    titulo: 'Datos de la red',      tag: 'SPAN → PCAP + eve.json', val: '335 202 ventanas normales' },
      { id: 'c_limpia',  x: 296,  y: 72,  w: 200, h: 64, icono: 'tijera',   titulo: 'Limpieza y alcance',   tag: 'espejo · control · excluidas', val: 'sin imputación' },
      { id: 'c_part',    x: 552,  y: 72,  w: 200, h: 64, icono: 'tabla',    titulo: 'Partición',            tag: 'train / validación / test', val: '204 148 / 65 633 / 65 421' },
      { id: 'c_cand',    x: 808,  y: 72,  w: 200, h: 64, icono: 'modelo',   titulo: 'Candidatos',           tag: 'IF · LOF · OCSVM · EE', val: '7 (laboratorio) · IF aquí' },
      { id: 'c_metr',    x: 1064, y: 72,  w: 200, h: 64, icono: 'lupa',     titulo: 'Comparar métricas',    tag: 'FPR · recall · F1 · AUC', val: 'criterio fijado antes' },
      { id: 'c_sel',     x: 1320, y: 72,  w: 200, h: 64, icono: 'decision', titulo: 'Selección',            tag: 'transfiere a esta red', val: 'IF recalibrado' },
      { id: 'c_cong',    x: 1320, y: 252, w: 200, h: 64, icono: 'cpu',      titulo: 'Congelar modelo+umbral', tag: 'α=0,05 · −0,568892', val: 'sha256 d27f6871…' },
      { id: 'c_desp',    x: 1064, y: 252, w: 200, h: 64, icono: 'nic',      titulo: 'Despliegue',           tag: 'promover + verificar', val: 'manifiesto + hash' },
      { id: 'c_acum',    x: 808,  y: 252, w: 200, h: 64, icono: 'fichero',  titulo: 'Acumulación',          tag: 'temporizador · v3', val: 'automática' },
      { id: 'c_reent',   x: 552,  y: 252, w: 200, h: 64, icono: 'ciclo',    titulo: 'Reentrenar / recalibrar', tag: 'POLÍTICA PROPUESTA', val: 'mensual o por deriva' },
      { id: 'c_antes',   x: 296,  y: 252, w: 200, h: 64, icono: 'tabla',    titulo: 'Antes vs después',     tag: 'mismos datos y métricas', val: 'FPR 92,4 % → 4,45 %' },
    ],
    aristas: [
      { d: 'M240,104 L296,104',   desde: 'c_datos',  hasta: 'c_limpia' },
      { d: 'M496,104 L552,104',   desde: 'c_limpia', hasta: 'c_part' },
      { d: 'M752,104 L808,104',   desde: 'c_part',   hasta: 'c_cand' },
      { d: 'M1008,104 L1064,104', desde: 'c_cand',   hasta: 'c_metr' },
      { d: 'M1264,104 L1320,104', desde: 'c_metr',   hasta: 'c_sel' },
      { d: 'M1420,136 L1420,252', desde: 'c_sel',    hasta: 'c_cong', etiqueta: 'umbral desde validación', ex: 1476, ey: 198 },
      { d: 'M1320,284 L1264,284', desde: 'c_cong',   hasta: 'c_desp' },
      { d: 'M1064,284 L1008,284', desde: 'c_desp',   hasta: 'c_acum' },
      { d: 'M808,284 L752,284',   desde: 'c_acum',   hasta: 'c_reent' },
      { d: 'M552,284 L496,284',   desde: 'c_reent',  hasta: 'c_antes' },
      { d: 'M652,252 L652,136',   desde: 'c_reent',  hasta: 'c_part', tipo: 'descarte', etiqueta: 'repite 3→6 con datos nuevos', ex: 760, ey: 198 },
      { d: 'M396,316 C396,384 1420,384 1420,316', desde: 'c_antes', hasta: 'c_cong', tipo: 'descarte', etiqueta: 'si mejora o iguala (FPR ≤, detección ≥) se congela el nuevo; si no, se queda el vigente', ex: 908, ey: 376 },
    ],
  },
};

let topoVista = 'completa';
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
    flujoTit: 'Flujo de reentrenamiento',
    flujo: [
      {paso: 'Dataset limpio', fichero: 'multilayer-v3.csv', garantia: 'solo tráfico benigno verificado'},
      {paso: 'Particionar', fichero: 'particionar_linea_base.py', garantia: 'bandas de guarda: sin fuga temporal'},
      {paso: 'Entrenar', fichero: 'entrenar_preliminar.py', garantia: 'umbral congelado en validación, antes de evaluar'},
      {paso: 'Modelo + manifiesto', fichero: 'if_recalibrado_desplegable.joblib', garantia: 'hashes que fijan la reproducibilidad'},
      {paso: 'Promoción', fichero: 'misma verificación', garantia: 'FPR y partición revisados; nunca a ciegas'},
    ],
    nota: 'Política PROPUESTA, no automatizada: mensual como suelo o por deriva del FPR, y obligatoria al cambiar la red (nueva VLAN, Wazuh, AAA). Lo automatizado hoy es solo la acumulación de la línea base; el entrenamiento y la promoción se hacen a mano, en seco y con la misma verificación, nunca a ciegas.',
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
    que: 'Parser de la fuente cruda. Lee los PCAP cerrados del anillo, decodifica Ethernet/802.1Q/IPv4/TCP/UDP/ICMP, quita lo que no se puntúa y atribuye cada paquete a la IP que INICIÓ su flujo. Lo ejecuta el servicio ppi-motor cada 10 s.',
    flujoTit: 'Procesamiento interno',
    flujo: [
      {paso: 'Decodificar trama', fichero: 'extract_multilayer_v3.py', garantia: 'parse_con_contexto: VLAN, IP, puertos, flags, TTL, id IP'},
      {paso: 'Filtrado de alcance', fichero: 'motor_decision.py', garantia: 'quita plano de control (CARP 112, pfsync 240) y copias del espejo'},
      {paso: 'Atribución por flujo', fichero: 'extract_multilayer_v2.py', garantia: 'attribute_packets: el SYN-ACK y el eco ICMP se apuntan a quien preguntó'},
      {paso: 'Ventaneo + variables', fichero: 'extract_multilayer_v2.py', garantia: 'build_rows: una fila por IP y ventana (10/30/60 s), junto con lo del parser de eventos'},
    ],
    nota: 'El filtrado es ALCANCE, no fórmula: el extractor está congelado (sus fórmulas no se tocan); los filtros actúan sobre su ENTRADA. En «Datos en vivo → Tramas PCAP» se ve cada trama con la variable que actualiza.',
    enlace: { href: '#s-vivo', vtab: 'pcap', txt: 'Ver tramas parseadas en vivo' },
  },
  parser_eve: {
    que: 'Parser de la fuente estructurada. Lee las líneas JSON que Suricata escribe en eve.json y solo se queda con tres tipos: http (método y estado), dns (consulta y respuesta NXDOMAIN) y tls (sesión y versión). flow, ssh, stats y el resto no entran al cálculo.',
    flujoTit: 'Del evento a la observación',
    flujo: [
      {paso: 'Recortar el tramo', fichero: 'motor_decision.py', garantia: 'solo las líneas de la historia que se puntúa (60 s)'},
      {paso: 'Filtrar tipos', fichero: 'extract_multilayer_v2.py', garantia: 'load_app_observations: http · dns · tls'},
      {paso: 'Atribuir', fichero: 'extract_multilayer_v2.py', garantia: 'a src_ip (en tls, dest_ip si src está fuera de la red); NXDOMAIN a quien preguntó'},
      {paso: 'Ventanas de 60 s', fichero: 'extract_multilayer_v2.py', garantia: 'las 11 variables L7 de la misma fila que las de red'},
    ],
    nota: 'Suricata NO decide aquí: sus alertas por firma no se usan como etiqueta ni como variable. Solo se aprovecha su parseo de protocolos.',
    enlace: { href: '#s-vivo', vtab: 'eve', txt: 'Ver eventos parseados en vivo' },
  },
  modelo: {
    que: 'El modelo one-class RECALIBRADO en esta red (IsolationForest). Aprende la normalidad propia; el umbral se congela desde validación (score_samples < -0,568892).',
    nota: 'Ya calibrado en esta red: la recalibración bajó el FPR del 92,4 % (umbral de otra red) al 4,45 %. Score bajo el umbral = anomalía → LIMIT.',
  },
  heuristicos: {
    que: 'Reglas deterministas sobre las mismas variables de la ventana, complemento del modelo: fuerza bruta, escaneo de puertos, abuso HTTP y DNS de alta entropía.',
    nota: 'Cubren huecos donde el modelo mide flojo (p.ej. DNS-entropy). El motor del sensor declara VERSION_UMBRALES 2026-10-06.2; la unidad del publicador todavía etiqueta el feed como 2026-10-06.1. La discrepancia de trazabilidad debe corregirse antes de atribuir una versión única al flujo. Los ratios de unicidad de 0,45 consideran copias del espejo SPAN; la rama de ráfaga de port_scan es posterior al piloto 1/3.',
    flujoTit: 'Las cuatro reglas (umbrales; versión del motor 2026-10-06.2)',
    flujo: [
      {paso: 'Fuerza bruta', fichero: 'heuristicos.py', garantia: '≥5 req HTTP/60s y ≥80% de fallo de auth → BLOCK'},
      {paso: 'Escaneo de puertos', fichero: 'heuristicos.py', garantia: '≥20 intentos/30s, unicidad ≥0,45 y ≤30% completadas; O ráfaga ≥200/30s y ≤10% completadas → BLOCK'},
      {paso: 'Abuso HTTP', fichero: 'heuristicos.py', garantia: '≥100 req/60s con <80% de fallo de auth (no es fuerza bruta) → LIMIT'},
      {paso: 'DNS-entropy', fichero: 'heuristicos.py', garantia: '≥20 consultas/60s con ≥45% de nombres únicos o ≥50% de NXDOMAIN → LIMIT'},
    ],
  },
  control: {
    que: 'Fusiona las dos señales en UNA decisión por entidad y ventana. El motor registra PERMIT o ALERT (score bajo el umbral, o heurístico); la ALERT se traduce en acción: LIMIT (degradar la tasa) para la anomalía del modelo y para abuso HTTP o DNS, BLOCK (cortar) para fuerza bruta o escaneo confirmados.',
    flujoTit: 'Cómo se decide la acción',
    flujo: [
      {paso: 'Dos entradas', fichero: 'motor_decision.py', garantia: 'score del modelo (anomalía→LIMIT) + heurístico (confirmado→BLOCK)'},
      {paso: 'Acción más severa', fichero: 'publicar_feed.py', garantia: 'por IP; BLOCK gana a LIMIT y LIMIT a PERMIT'},
      {paso: 'Escalada por reincidencia', fichero: 'escalada.py', garantia: '300→1800→3600 s; nunca ∞ automático'},
      {paso: 'Lista nunca-bloquear', fichero: 'publicar_feed.py', garantia: 'gateways y DNS quedan siempre fuera'},
    ],
    nota: 'LIMIT existe para el coste de un falso positivo (con 4,45 % de FPR, degradar es mejor que cortar). El sensor DECIDE pero no ejecuta: solo observa por espejo. La acción la aplica el agente en el host, con el feed firmado de por medio.',
  },
  feed: {
    que: 'La lista FIRMADA (ed25519) de acciones que el sensor publica. Cada entrada: IP, acción, caducidad y motivo.',
    nota: 'Modelo pull: el sensor no tiene credenciales de los hosts; publica y firma, y cada host trae la lista y la verifica. Caducidad escalada (300/1800/3600 s); nunca bloqueo permanente automático.',
    flujoTit: 'Cómo se publica',
    flujo: [
      {paso: 'Publicar', fichero: 'publicar_feed.py', garantia: 'desde las decisiones del motor + la escalera de reincidencia'},
      {paso: 'Firmar', fichero: 'feed.py', garantia: 'ed25519 vía openssl; el host verifica antes de aplicar'},
      {paso: 'Caducidad', fichero: 'escalada.py', garantia: '300→1800→3600 s por reincidencia; ∞ solo revisión humana'},
    ],
  },
  agente: {
    que: 'Corre en cada host protegido: trae el feed, verifica la firma y sincroniza nftables (LIMIT con rate-limit, BLOCK con drop y timeout).',
    nota: 'Fail-safe: si la firma no verifica, no toca nada. Tabla aislada (policy accept): solo cae lo que trae el feed. Nunca bloquea gateways ni DNS. Demostrado: un BLOCK real cortó a la Kali (http_200 → http_000).',
    flujoTit: 'Cómo actúa en el host',
    flujo: [
      {paso: 'Pull + verifica', fichero: 'agente_enforce.py', garantia: 'firma ed25519; fail-safe si falla'},
      {paso: 'Aplica', fichero: 'nftables', garantia: 'set con timeout nativo → caduca solo'},
    ],
  },
  wazuh: {
    que: 'El concentrador de alertas (SIEM) en la VLAN de gestión. El sensor le emite por syslog; Wazuh correlaciona y guarda el histórico.',
    nota: 'Regla de diseño: las alertas fluyen HACIA ADENTRO (a Wazuh), no hacia afuera. El sensor NUNCA sale a Internet (nada de bots externos): esa falta de egress es una propiedad de seguridad. CyberFlow complementa a Wazuh, no lo reemplaza.',
  },
  pcap: {
    que: 'Ficheros PCAP rotados cada 15 s. Es toda la historia de capa 3 y 4 de la que dispone el motor.',
    nota: 'Un temporizador poda los más viejos: sin él el anillo crece sin fin, porque el nombre lleva fecha y tcpdump nunca reutiliza un fichero. Medido antes de podarlo: 403 MB en un día.',
    enlace: { href: '#s-vivo', vtab: 'pcap', txt: 'Ver las tramas en vivo y a qué variable aporta cada una' },
  },
  eve: {
    que: 'El registro de eventos de Suricata, una línea JSON por evento. De aquí salen HTTP, DNS y TLS.',
    nota: 'Va por delante del anillo de PCAP: Suricata emite el evento antes de que tcpdump vuelque los paquetes a disco. Por eso hay ventanas con eventos de aplicación y cero paquetes. No es «eve.json por la NIC»: es una segunda fuente, derivada de las mismas tramas por Suricata.',
    enlace: { href: '#s-vivo', vtab: 'eve', txt: 'Ver los eventos en vivo y a qué variable aporta cada uno' },
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
  // ---- Vista METODOLOGICA (como se construyo) ----
  m_datos: {
    que: 'F1. La línea base se genera y captura en la propia red por espejo SPAN: no es un dataset público. La recalibración sobre tráfico propio bajó el FPR del 92,4 % al 4,45 %.',
    nota: 'Datos reales, no simulados: cierra el salto simulación→realidad que casi ningún trabajo del estado del arte aborda.',
  },
  m_feat: {
    que: 'F2. El extractor congelado convierte los paquetes y las señales de Suricata en 28 variables multicapa (L3/L4/L7) por IP iniciadora, en ventanas de 10/30/60 s. Sin imputación: las ausencias son ceros estructurales.',
    nota: 'Limpieza = deduplicación del espejo + validación fail-closed. 27 de 28 variables con variación observable.',
  },
  m_modelo: {
    que: 'F3. Detector híbrido: Isolation Forest recalibrado (umbral −0,568892) + heurísticos deterministas. La ablación lo justifica: modelo solo 6/9, heurísticos 7/9, combinado 9/9.',
    nota: 'El modelo se elige comparando 7 candidatos (no a ciegas); el umbral se calibra en validación y se congela antes del test.',
  },
  m_eval: {
    que: 'F4. Evaluación justa por replay del MISMO PCAP a CyberFlow y a Suricata, anclando al reloj del paquete. Resultado sin firma: 9/9 vs 0/9.',
    nota: 'Complementario a Suricata: él bloquea lo que tiene firma; CyberFlow detecta lo que no la tiene.',
  },
  m_resp: {
    que: 'F5 (aporte). La decisión se convierte en acción: PERMIT/LIMIT/BLOCK con feed firmado (ed25519), caducidad escalada, aplicada por agentes en los hosts (nftables).',
    nota: 'Actuar, no solo detectar: es lo que casi ningún artículo del estado del arte alcanza.',
  },
  m_desp: {
    que: 'F6 (aporte). Desplegado sobre el sensor con systemd, instalación turnkey offline, verificado en un segundo sensor. 58 corridas sin caídas.',
    nota: 'Nadie de los 15 artículos despliega su sistema en operación real.',
  },
  m_valid: {
    que: 'F7 (aporte). Validación interna (demo técnica en vivo) + externa (TAM + juicio de expertos, Cronbach/Aiken).',
    nota: 'Se demuestra y se acredita; no son solo palabras.',
  },
  // ---- Vista CONSTRUCCION Y ENTRENAMIENTO ----
  // Cifras del informe de calibracion (ensayo-if-v2.json, sha ec3ed063...) y de
  // la comparacion historica de laboratorio (07-metricas-...-7-modelos.md).
  c_datos: {
    que: 'Dónde empieza: la línea base de ESTA red, capturada por el espejo SPAN del troncal. Dos fuentes de la misma copia: PCAP crudo (tcpdump) y eve.json (Suricata). El acumulador las pasa por el mismo extractor que el motor y escribe una fila por IP y ventana.',
    flujoTit: 'Qué entra',
    flujo: [
      {paso: 'Captura', fichero: 'ppi-motor-capture + suricata', garantia: 'misma interfaz ens37, sin IP'},
      {paso: 'Acumulación', fichero: 'acumular_v3.py', garantia: 'filas multilayer-v3 (28 del modelo + 3 de capa 2)'},
      {paso: 'Solo normal', fichero: 'Kali apagada', garantia: 'un detector de una clase aprende lo normal; un ataque en la base lo volvería normal'},
    ],
    nota: 'Total usado para el IF vigente: 335 202 ventanas normales (204 148 + 65 633 + 65 421). Sin ataques: los de la Kali se reservaron para medir detección después.',
  },
  c_limpia: {
    que: 'Limpieza = acotar la ENTRADA, no tocar fórmulas. Se quitan el plano de control del cortafuegos (CARP 112, pfsync 240), la segunda copia de cada trama que el espejo enseña dos veces y las entidades declaradas fuera de alcance.',
    flujoTit: 'Qué se quita y dónde',
    flujo: [
      {paso: 'Plano de control', fichero: 'motor_decision.py', garantia: '--excluir-protocolos 112,240'},
      {paso: 'Copias del espejo', fichero: 'extract_multilayer_v3.py', garantia: 'deduplicar_espejo: TTL −1 entre VLAN, idénticas en difusión'},
      {paso: 'Entidades fuera', fichero: 'cyberflow.local.toml', garantia: '[red] excluir: sensor y bastión'},
    ],
    nota: 'Sin imputación: una ausencia es un cero estructural (no hubo DNS en esa ventana), no un dato perdido. Las filas no elegibles (sin historia suficiente) no entran.',
  },
  c_part: {
    que: 'Cómo se partió: 204 148 ventanas para entrenar, 65 633 para validar y 65 421 para probar (≈ 61/20/20). Tres grupos porque, además de entrenar, hay que fijar el umbral: la validación lo fija y la prueba queda ciega.',
    flujoTit: 'Partición sin fuga temporal',
    flujo: [
      {paso: 'Bloques horarios', fichero: 'particionar_linea_base.py', garantia: 'reparto cíclico que cubre todo el ciclo diario'},
      {paso: 'Banda de guarda 60 s', fichero: 'particionar_linea_base.py', garantia: 'ninguna ventana comparte paquetes entre grupos'},
    ],
    nota: 'No se baraja al azar: ventanas vecinas comparten tráfico (las de 60 s se solapan) y una partición aleatoria filtraría la prueba en el entrenamiento.',
  },
  c_cand: {
    que: 'Qué modelos se compararon. En el laboratorio, 7 detectores de una clase con las mismas 28 variables y la misma partición: cuatro variantes de Isolation Forest, LOF, One-Class SVM y Elliptic Envelope. En esta red se reentrenó un solo candidato, el Isolation Forest (500 árboles).',
    flujoTit: 'Los siete del laboratorio (F1 · FPR de prueba)',
    flujo: [
      {paso: 'ocsvm_scaled', fichero: 'One-Class SVM RBF', garantia: 'F1 0,903 · recall 88,3 % · FPR 4,71 %'},
      {paso: 'if_uniform / if_exact_collapsed', fichero: 'Isolation Forest', garantia: 'F1 0,696 · recall 57,5 % · FPR 5,07 %'},
      {paso: 'if_primary / if_scaled_weighted', fichero: 'Isolation Forest', garantia: 'F1 0,674 · recall 54,2 % · FPR 4,35 %'},
      {paso: 'lof_scaled', fichero: 'Local Outlier Factor', garantia: 'F1 0,579 · recall 43,0 % · FPR 3,62 %'},
      {paso: 'elliptic_envelope_scaled', fichero: 'Elliptic Envelope', garantia: 'F1 0,405 · recall 27,4 % · FPR 5,07 %'},
    ],
    nota: 'Por qué el IF y no el ganador: el OCSVM ganó en el laboratorio, pero se eligió después de ver la prueba (sesgo declarado) y no transfirió a esta red. El IF se reentrenó porque es el que la configuración inicial designaba como principal, y se midió con un objetivo de FPR fijado de antemano.',
  },
  c_metr: {
    que: 'Con qué métricas. Sobre tráfico normal: FPR en validación (para fijar el umbral) y en prueba (una sola vez). Sobre ataques: tasa de detección con la Kali. En el laboratorio, además: precisión, recall, F1, MCC, ROC-AUC y PR-AUC, con McNemar + Holm entre pares.',
    flujoTit: 'Métricas del IF vigente',
    flujo: [
      {paso: 'FPR validación', fichero: 'ensayo-if-v2.json', garantia: '5,00 % (por construcción: α = 0,05)'},
      {paso: 'FPR prueba', fichero: 'ensayo-if-v2.json', garantia: '4,45 % sobre 65 421 ventanas normales'},
      {paso: 'Detección Kali', fichero: 'nota M', garantia: '54/78 = 69 % global; HTTP 27/27'},
    ],
    nota: 'El criterio se fija ANTES de mirar la prueba: umbral desde validación con objetivo de FPR 5 %. El 4,45 % es del modelo sobre tráfico normal, no del sistema completo con heurísticos.',
  },
  c_sel: {
    que: 'Por qué ganó: el OCSVM del laboratorio, llevado a esta red con su umbral, marcaba como anómalo el 92,4 % del tráfico normal. El IF recalibrado aquí cumple el objetivo (4,45 % de FPR en prueba) y detecta 54/78 ventanas de ataque. Se elige el que funciona en la red donde opera.',
    nota: 'La detección no la hace el modelo solo: la ablación da modelo 6/9, heurísticos 7/9 y combinado 9/9. El modelo es una de dos señales.',
    enlace: { href: '#s-modelo', txt: 'Ver «Pruebas previas» y la ablación' },
  },
  c_cong: {
    que: 'Congelar modelo y umbral: el escalador y el IF se empaquetan en un Pipeline y el umbral se fija como el percentil α = 0,05 de validación: score_samples < −0,568892 (decision_function < −0,068892). Desde aquí nada se reajusta: la prueba y la Kali se puntúan con este mismo modelo.',
    flujoTit: 'Qué queda fijo',
    flujo: [
      {paso: 'Pipeline', fichero: 'if_recalibrado_desplegable.joblib', garantia: 'sha256 d27f6871…125a'},
      {paso: 'Umbral + orden de variables', fichero: 'manifest-if-recalibrado.json', garantia: 'el motor rechaza un orden distinto al del extractor'},
      {paso: 'Equivalencia', fichero: 'verificar_equivalencia_umbral.py', garantia: '0 decisiones distintas sobre filas reales'},
    ],
    nota: 'La promoción es reproducible: promover_preliminar.py regenera el modelo desde su paquete con scores idénticos (no byte a byte).',
  },
  c_desp: {
    que: 'Despliegue: el motor carga el Pipeline y el umbral del manifiesto, comprueba hash y orden de variables, y puntúa cada IP cada 10 s. El generador de configuración escribe las unidades systemd desde cyberflow.local.toml.',
    flujoTit: 'Cadena de promoción',
    flujo: [
      {paso: 'Promover', fichero: 'promover_preliminar.py', garantia: 'paquete → Pipeline + manifiesto, se niega a sobrescribir'},
      {paso: 'Verificar', fichero: 'verificar_equivalencia_umbral.py', garantia: 'hash + orden + umbral equivalente'},
      {paso: 'Configurar', fichero: 'cyberflow_config.py', garantia: 'motor y panel con el mismo detector'},
    ],
    nota: 'Rollback: apuntar [motor] modelo, manifiesto y detector al artefacto anterior, regenerar la configuración y reiniciar ppi-motor. Nada se sobrescribe: promover se niega a pisar un artefacto existente.',
  },
  c_acum: {
    que: 'Acumulación: mientras el motor opera, un temporizador sigue escribiendo filas de línea base (v3) con la misma cadena. Es lo único automático del ciclo de vida.',
    nota: 'Las filas acumuladas solo sirven para reentrenar si se verifica que son tráfico normal: una campaña de ataque en ese tramo hay que retirarla antes.',
  },
  c_reent: {
    que: 'Reentrenar o recalibrar: repetir los pasos 3 a 6 (partición, candidatos, métricas, selección) sobre los datos acumulados, en seco, sin tocar el modelo en producción. Recalibrar es solo mover el umbral con validación nueva; reentrenar es rehacer el modelo.',
    flujoTit: 'Cada cuánto (política propuesta)',
    flujo: [
      {paso: 'Suelo', fichero: 'mensual', garantia: 'aunque nada cambie'},
      {paso: 'Por deriva', fichero: 'FPR operativo', garantia: 'si sube claramente sobre el 5 % de diseño'},
      {paso: 'Obligatorio', fichero: 'cambio de red', garantia: 'nueva VLAN, Wazuh, AAA, servicios nuevos'},
    ],
    nota: 'Política PROPUESTA, no automatizada. Hoy el entrenamiento y la promoción se hacen a mano y con la misma verificación, nunca a ciegas.',
  },
  c_antes: {
    que: 'Antes vs después: el modelo nuevo se compara con el vigente sobre los MISMOS datos reservados y con las mismas métricas (FPR en normal, detección en ataques no vistos). La referencia publicada es el cambio de modelo en esta red: OCSVM con umbral de otra red, 92,4 % de FPR → IF recalibrado, 4,45 %.',
    flujoTit: 'Comparación antes / después',
    flujo: [
      {paso: 'Tabla de cambios', fichero: 'comparar_reentrenamiento.py', garantia: 'métricas previas vs posteriores + Δ'},
      {paso: 'Evidencia', fichero: 'comparacion-reentrenamiento.md', garantia: 'queda escrita antes de decidir'},
      {paso: 'Decisión', fichero: 'regla fija', garantia: 'se promueve solo si FPR ≤ y detección ≥; si no, se queda el vigente'},
    ],
    nota: 'El 92,4 → 4,45 no es un reentrenamiento del mismo modelo sino un cambio de modelo y de umbral. La comparación de un reentrenamiento con datos nuevos reservados está pendiente (bloque B3).',
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
      return { estado: '', valor: 'política propuesta', datos: {
        'Cadencia propuesta': 'mensual o por deriva del FPR',
        'Obligatorio': 'al cambiar la red',
        'Automatizado': 'solo la acumulación de la línea base' } };
    case 'heuristicos':
      return { estado: '', valor: '4 reglas deterministas', datos: {
        'Cubren': 'brute-force · port-scan · http-abuse · dns-entropy',
        'Papel': 'complementan al modelo (0,08 % de falsos positivos)' } };
    case 'feed':
      return { estado: '', valor: 'firmado (ed25519)', datos: {
        'Publica': 'el sensor; el host lo trae (pull) y verifica',
        'Caducidad': '300/1800/3600 s, nunca permanente' } };
    case 'agente':
      return { estado: '', valor: 'en el host protegido', datos: {
        'Aplica': 'nftables: LIMIT (rate) / BLOCK (drop), con timeout',
        'Alcance': 'solo lo que trae el feed; nunca gateways/DNS' } };
    case 'wazuh':
      return { estado: '', valor: 'concentrador de alertas', datos: {
        'Recibe': 'del sensor (syslog), intra-VLAN',
        'Regla': 'las alertas van HACIA ADENTRO; el sensor no sale a Internet' } };
  }
  return { estado: '', valor: '—', datos: {} };
}

function renderTopologia(status) {
  topoUltimo = status;
  const v = TOPO_VISTAS[topoVista];
  const svg = document.getElementById('topo');
  const est = {};
  for (const n of v.nodos) {
    est[n.id] = topoEstado(n.id, status);
    // Nodos de las vistas de construccion: sin estado vivo, llevan su cifra fija.
    if (est[n.id].valor === '—' && n.val) est[n.id] = Object.assign({}, est[n.id], { valor: n.val });
  }

  const grupos = v.grupos.map(g => {
    const badge = g.n
      ? `<circle class="topo-fase-n" cx="${g.x + 21}" cy="${g.y + 15}" r="9.5"/>` +
        `<text class="topo-fase-nt" x="${g.x + 21}" y="${g.y + 18}" text-anchor="middle">${g.n}</text>`
      : '';
    const tx = g.n ? g.x + 38 : g.x + 12;
    return `<rect class="topo-grupo" x="${g.x}" y="${g.y}" width="${g.w}" height="${g.h}" rx="12"/>` +
      badge +
      `<text class="topo-grupo-txt" x="${tx}" y="${g.y + 19}">${g.txt}</text>`;
  }).join('');

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
      <g class="ico" transform="translate(${n.x + 12}, ${cy - 11})"><svg width="22" height="22" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[n.icono]}</svg></g>
      <text class="ttl" x="${n.x + 44}" y="${cy - 3}">${n.titulo}</text>
      <text class="hostip" x="${n.x + 44}" y="${cy + 11}">${n.ip}</text>
      <text class="tag" x="${n.x + n.w - 10}" y="${n.y + n.h - 6}" text-anchor="end">${n.desc}</text>
    </g>`;
  }).join('');

  const nodos = v.nodos.filter(n => !n.host).map(n => {
    const e = est[n.id];
    const cy = n.y + n.h / 2;
    const color = e.estado === 'ok' ? 'var(--ok)' : e.estado === 'warn' ? 'var(--amber)'
                : e.estado === 'bad' ? 'var(--danger)' : 'var(--border)';
    const etiqueta = n.tag
      ? `<text class="tag" x="${n.x + 46}" y="${n.y + n.h - 5}">${n.tag}</text>` : '';
    const desplazar = n.tag ? -8 : 0;
    // Con "Ver archivos" activo, cada nodo con ficheros muestra un contador; el
    // detalle de cada uno se abre pulsando el nodo (aparecen como cuadraditos).
    const nfiles = (topoArchivos && artefactos && artefactos[n.id]) ? artefactos[n.id].length : 0;
    const badge = nfiles
      ? `<text class="fbadge" x="${n.x + n.w - 24}" y="${n.y + n.h - 6}" text-anchor="end">▤ ${nfiles}</text>` : '';
    return `<g class="topo-node ${e.estado} ${n.clase || ''} ${nfiles ? 'tiene-archivos' : ''} ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      <g class="ico" transform="translate(${n.x + 13}, ${cy - 11 + desplazar})"><svg width="22" height="22" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[n.icono]}</svg></g>
      <text class="ttl" x="${n.x + 46}" y="${cy - 3 + desplazar}">${n.titulo}</text>
      <text class="sub" x="${n.x + 46}" y="${cy + 12 + desplazar}">${e.valor}</text>
      ${etiqueta}${badge}
      <circle class="led" cx="${n.x + n.w - 13}" cy="${n.y + 13}" r="4" fill="${color}"/>
    </g>`;
  }).join('');

  svg.innerHTML = grupos + aristas + packet + hosts + nodos;
  if (topoFasesVista !== topoVista) { renderFases(); topoFasesVista = topoVista; }
  aplicarZoom();
  renderTopoDetalle();
}

// --- Controles del diagrama: vista, escala y pantalla completa --------------
let topoZoom = null;   // null = ajustar al ancho disponible

// Ajuste por defecto: encuadra TODO el diagrama (ancho Y alto) dentro del
// lienzo, para que se vea entero de un vistazo. El lienzo tiene una altura
// acotada por CSS (min(76vh,760px)); en pantalla completa la hereda del padre.
function escalaAjuste() {
  const v = TOPO_VISTAS[topoVista];
  const caja = document.getElementById('topoScroll');
  const fw = (caja.clientWidth - 8) / v.w;
  // En modo normal ajustamos al ANCHO (el lienzo se encoge a la altura del
  // diagrama, sin hueco). En pantalla completa encuadramos ancho Y alto para
  // que el diagrama llene la pantalla, centrado.
  if (!document.fullscreenElement) return Math.max(0.25, Math.min(1.4, fw));
  const fh = (caja.clientHeight - 8) / v.h;
  return Math.max(0.25, Math.min(2, Math.min(fw, fh)));
}

function aplicarZoom() {
  const v = TOPO_VISTAS[topoVista];
  const svg = document.getElementById('topo');
  svg.setAttribute('viewBox', `0 0 ${v.w} ${v.h}`);
  let escala = topoZoom;
  if (escala == null) escala = escalaAjuste();
  svg.setAttribute('width', Math.round(v.w * escala));
  svg.setAttribute('height', Math.round(v.h * escala));
  document.getElementById('topoNivel').textContent = Math.round(escala * 100) + '%';
}

function escalaActual() {
  return topoZoom != null ? topoZoom : escalaAjuste();
}

// Zoom por seccion: encuadra un grupo (fase) y lo centra en el lienzo.
function zoomAGrupo(g) {
  const caja = document.getElementById('topoScroll');
  const m = 28;
  const esc = Math.max(0.3, Math.min(3, Math.min(
    (caja.clientWidth - m) / g.w, (caja.clientHeight - m) / g.h)));
  topoZoom = esc;
  aplicarZoom();
  caja.scrollLeft = Math.max(0, (g.x + g.w / 2) * esc - caja.clientWidth / 2);
  caja.scrollTop = Math.max(0, (g.y + g.h / 2) * esc - caja.clientHeight / 2);
}

// Un boton por fase (solo en vistas con grupos numerados) + "Todo".
let topoFasesVista = null;
function renderFases() {
  const cont = document.getElementById('topoFases');
  if (!cont) return;
  const grupos = (TOPO_VISTAS[topoVista].grupos || []).filter(g => g.n);
  if (!grupos.length) { cont.innerHTML = ''; cont.style.display = 'none'; return; }
  cont.style.display = 'flex';
  cont.innerHTML = '<span class="lbl">Fase</span>'
    + grupos.map(g => `<button type="button" data-fase="${g.n}" title="Encuadrar: ${g.txt}">${g.n}</button>`).join('')
    + '<button type="button" data-fase="all" title="Ver todo el diagrama">Todo</button>';
}

on('topoFases', 'click', (ev) => {
  const b = ev.target.closest('button[data-fase]');
  if (!b) return;
  const caja = document.getElementById('topoScroll');
  if (b.dataset.fase === 'all') { topoZoom = null; aplicarZoom(); caja.scrollTop = 0; caja.scrollLeft = 0; return; }
  const g = (TOPO_VISTAS[topoVista].grupos || []).find(x => String(x.n) === b.dataset.fase);
  if (g) zoomAGrupo(g);
});

on('topoVista', 'click', (ev) => {
  const b = ev.target.closest('button[data-vista]');
  if (!b) return;
  topoVista = b.dataset.vista;
  document.querySelectorAll('#topoVista button').forEach(x => x.classList.toggle('active', x === b));
  topoZoom = null;   // cada vista tiene otro tamano: se reajusta
  // Si el nodo seleccionado no existe en la vista nueva, se cae al primero.
  if (!TOPO_VISTAS[topoVista].nodos.some(n => n.id === topoSel)) {
    const prim = TOPO_VISTAS[topoVista].nodos.find(n => !n.host) || TOPO_VISTAS[topoVista].nodos[0];
    topoSel = prim ? prim.id : null;
  }
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

// Plegar/desplegar el panel de detalle: al ocultarlo el diagrama toma todo el
// ancho (util para verlo a lo ancho). La preferencia es por-visor.
on('topoDetalleBtn', 'click', () => {
  const wrap = document.getElementById('topoWrap');
  const oculto = wrap.classList.toggle('sin-detalle');
  document.getElementById('topoDetalleBtn').setAttribute('aria-pressed', oculto ? 'true' : 'false');
  document.getElementById('topoDetalleTxt').textContent = oculto ? 'Ver panel' : 'Ocultar panel';
  try { localStorage.setItem('cf_topo_detalle', oculto ? 'oculto' : 'visible'); } catch (e) {}
  topoZoom = null;               // reajusta al nuevo ancho disponible
  setTimeout(aplicarZoom, 60);   // tras el reflujo del grid
});
(function () {
  let pref = null;
  try { pref = localStorage.getItem('cf_topo_detalle'); } catch (e) {}
  if (pref !== 'oculto') return;
  const wrap = document.getElementById('topoWrap');
  if (!wrap) return;
  wrap.classList.add('sin-detalle');
  const btn = document.getElementById('topoDetalleBtn');
  if (btn) btn.setAttribute('aria-pressed', 'true');
  const txt = document.getElementById('topoDetalleTxt');
  if (txt) txt.textContent = 'Ver panel';
})();

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
  let e = topoEstado(n.id, topoUltimo);
  if (e.valor === '—' && n.val) e = Object.assign({}, e, { valor: n.val });
  const t = TOPO_TEXTO[n.id] || {};
  const filas = Object.entries(e.datos || {})
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  const cabIp = n.host && n.ip ? `<span class="state">${n.ip}</span>` : `<span class="state ${e.estado}">${e.valor}</span>`;
  document.getElementById('topoDetail').innerHTML =
    `<h3>${n.titulo}${cabIp}</h3>` +
    (t.que ? `<p>${t.que}</p>` : '') +
    (n.id === 'modelo' ? decisionModeloHTML() : '') +
    (filas ? `<dl>${filas}</dl>` : '') +
    (t.cmd ? `<pre class="topo-cmd">${t.cmd.replace(/</g, '&lt;')}</pre>` : '') +
    (t.flujo ? flujoHTML(t.flujo, t.flujoTit) : '') +
    filesHTML(n.id) +
    (t.nota ? `<p class="dim">${t.nota}</p>` : '') +
    (t.enlace ? `<p><a href="${t.enlace.href}"${t.enlace.vtab ? ` data-vtab="${t.enlace.vtab}"` : ''}>${t.enlace.txt} &rarr;</a></p>` : '');
}

// La regla de decision del modelo, hecha visible en el nodo "Modelo": una recta
// de score con el umbral marcado y los scores reales recientes como puntos. A la
// izquierda del umbral la ventana es anomala (ALERT); a la derecha, normal
// (PERMIT). Reusa la escala del histograma y las decisiones ya cargadas; si aun
// no hay scores, lo dice en vez de dibujar una recta vacia que afirme algo.
function decisionModeloHTML() {
  const e = window._escalaScore;
  if (!e || e.max === e.min) {
    return '<div class="modelo-dec"><h4>Cómo decide</h4>'
      + '<p class="cap">Sin scores recientes que ilustrar. La regla es: '
      + 'score < umbral &rarr; <b class="a">ALERT</b>; score &ge; umbral &rarr; <b class="p">PERMIT</b>.</p></div>';
  }
  const w = 300, h = 52, y = 30, x0 = 10, x1 = w - 10;
  const px = v => x0 + (Math.max(e.min, Math.min(e.max, v)) - e.min) / (e.max - e.min) * (x1 - x0);
  const ux = px(e.umbral);
  let s = `<svg width="100%" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Recta de score con el umbral y scores recientes">`;
  // Zonas: ALERT a la izquierda del umbral, PERMIT a la derecha.
  s += `<rect x="${x0}" y="${y - 7}" width="${(ux - x0).toFixed(1)}" height="14" fill="var(--danger-soft)"/>`;
  s += `<rect x="${ux.toFixed(1)}" y="${y - 7}" width="${(x1 - ux).toFixed(1)}" height="14" fill="var(--ok-soft)"/>`;
  s += `<line x1="${x0}" y1="${y}" x2="${x1}" y2="${y}" stroke="var(--border)" stroke-width="1"/>`;
  // Scores reales recientes como puntos semitransparentes (densidad visible).
  const scores = (lastDecisions || []).filter(d => d.score != null).slice(0, 60);
  scores.forEach(d => {
    const col = d.score < e.umbral ? 'var(--danger)' : 'var(--ok)';
    s += `<circle cx="${px(d.score).toFixed(1)}" cy="${y}" r="3" fill="${col}" fill-opacity="0.55"/>`;
  });
  // Umbral: linea discontinua con etiqueta.
  s += `<line x1="${ux.toFixed(1)}" y1="${y - 11}" x2="${ux.toFixed(1)}" y2="${y + 11}" stroke="var(--text)" stroke-width="1.3" stroke-dasharray="3 2"/>`;
  s += `<text x="${ux.toFixed(1)}" y="12" font-size="9" fill="var(--text)" text-anchor="middle" font-family="ui-monospace, monospace">umbral ${e.umbral.toFixed(2)}</text>`;
  s += `<text x="${x0}" y="${h - 3}" font-size="8.5" fill="var(--danger)" font-family="ui-monospace, monospace">${e.min.toFixed(2)} · anómalo</text>`;
  s += `<text x="${x1}" y="${h - 3}" font-size="8.5" fill="var(--ok)" text-anchor="end" font-family="ui-monospace, monospace">normal · ${e.max.toFixed(2)}</text>`;
  s += '</svg>';
  return `<div class="modelo-dec"><h4>Cómo decide</h4>${s}`
    + `<p class="cap">${scores.length} score(s) reciente(s). A la izquierda del umbral, `
    + `<b class="a">ALERT</b>; a la derecha, <b class="p">PERMIT</b>.</p></div>`;
}

// Mini-flujo del reentrenamiento: pasos encadenados, cada uno con su fichero y
// la garantia que aporta. Hace visible POR QUE el reentrenamiento es fiable
// (sin fuga, umbral congelado, promocion verificada), no solo que existe.
function flujoHTML(pasos, titulo) {
  let html = '<div class="topo-flujo"><h4>' + (titulo || 'Flujo interno') + '</h4>';
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
  const p = String(ruta).split(/[\\\\/]/);
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
      const verbtn = f.existe
        ? `<button class="ver-codigo" data-ruta="${String(f.ruta).replace(/"/g, '&quot;')}">◎ Ver contenido</button>`
        : '';
      html += `<div class="topo-file-det"><div class="ruta">${f.ruta}</div>`
        + `<div>${f.que}</div><div>${estado}</div>${verbtn}</div>`;
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

on('topoDetail', 'click', async (ev) => {
  const vc = ev.target.closest('.ver-codigo');
  if (vc) { await verCodigo(vc.dataset.ruta); return; }
  const f = ev.target.closest('.topo-file');
  if (!f) return;
  const clave = f.dataset.file;
  if (filesAbiertos.has(clave)) filesAbiertos.delete(clave); else filesAbiertos.add(clave);
  renderTopoDetalle();
});

// Modo desarrollador: abre un modal con el CONTENIDO del script (solo lectura).
async function verCodigo(ruta) {
  const modal = document.getElementById('codeModal');
  document.getElementById('codeTitle').textContent = nombreFichero(ruta);
  document.getElementById('codeSub').textContent = ruta;
  document.getElementById('codeBody').textContent = 'cargando…';
  modal.hidden = false;
  try {
    const r = await fetch('/api/archivo?ruta=' + encodeURIComponent(ruta));
    const d = await r.json();
    if (!d || d.contenido == null) {
      document.getElementById('codeBody').textContent = (d && d.nota) || 'no disponible';
    } else {
      document.getElementById('codeBody').textContent =
        d.contenido + (d.truncado ? '\\n\\n…(archivo truncado: se muestran los primeros 512 KB)…' : '');
      document.getElementById('codeSub').textContent =
        ruta + '  ·  ' + (d.bytes || 0) + ' bytes';
    }
  } catch (e) {
    document.getElementById('codeBody').textContent = 'error al cargar el archivo';
  }
}
on('codeClose', 'click', () => { document.getElementById('codeModal').hidden = true; });
on('codeModal', 'click', (ev) => { if (ev.target.id === 'codeModal') ev.currentTarget.hidden = true; });
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') { const m = document.getElementById('codeModal'); if (m) m.hidden = true; }
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

// Paleta categorica de las capas: se asigna por ORDEN de aparicion, no por el id
// literal, asi que funciona sea cual sea el nombre de la capa y con cuantas haya.
const CAPA_PALETA = ['var(--capa-a)', 'var(--capa-b)', 'var(--capa-c)', 'var(--capa-d)'];
function capaColor(id) {
  if (!varDatos || !varDatos.capas) return 'var(--accent)';
  const i = varDatos.capas.findIndex(c => c.id === id);
  return CAPA_PALETA[(i < 0 ? 0 : i) % CAPA_PALETA.length];
}

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
    return `<button class="var-capa" data-capa="${c.id}" aria-pressed="${sel}" title="${varEsc(c.que)}" style="--cc-color:${capaColor(c.id)}">`
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
      html += `<div class="var-grupo" style="--cc-color:${capaColor(capaActual)}"><b>${capaActual}</b> · ${varEsc(c.nombre || '')} — ${varEsc(c.que || '')}</div>`;
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

// ---- Datos en vivo -------------------------------------------------------
// Tres pestañas sobre /api/vivo y /api/trazabilidad (solo admin). Se refresca
// cada 10 s mientras la seccion esta visible y no esta en pausa; la matriz se
// pide una vez porque sale del esquema y del codigo, no del trafico.
let vivoTab = 'eve', vivoDatos = null, vivoMatriz = null, vivoPausa = false;

function vfChip(f) {
  const cls = f.uso === 'modelo' ? '' : (f.uso === 'conteo' ? ' cnt' : ' l2');
  const val = f.valor === null ? '—' : String(f.valor);
  const tip = f.feature + ' · ventana ' + f.ventana_s + ' s · uso: ' + f.uso +
    (f.parcial ? ' · valor PARCIAL: la ventana empieza antes del tramo leído' : '');
  return '<span class="vf' + cls + '" title="' + varEsc(tip) + '"><b>' + varEsc(f.feature) +
    '</b> <span class="ap">' + varEsc(f.aporte) + '</span> → ' + varEsc(val) +
    (f.parcial ? '<span class="par">*</span>' : '') + '</span>';
}

function vivoPasa(r, q) {
  if (!q) return true;
  const txt = [r.entidad, r.ip_src, r.ip_dst, r.origen, r.destino, r.evento]
    .concat((r.features || []).map(f => f.feature)).join(' ').toLowerCase();
  return txt.includes(q);
}

function renderVivo() {
  const caja = document.getElementById('vivoTabla');
  const res = document.getElementById('vivoResumen');
  const pie = document.getElementById('vivoPie');
  if (!caja) return;
  document.getElementById('vivoTodosLbl').style.display = vivoTab === 'pcap' ? '' : 'none';
  const q = (document.getElementById('vivoFiltro').value || '').trim().toLowerCase();
  const hora = (s) => s ? s.slice(11, 19) : '—';

  if (vivoTab === 'matriz') {
    if (!vivoMatriz) { caja.innerHTML = '<p class="var-vacio">Cargando matriz…</p>'; return; }
    const filas = vivoMatriz.filter(m => !q || (m.feature + ' ' + m.registro + ' ' + m.fuente).toLowerCase().includes(q));
    res.textContent = 'Fuente → registro → parser → variable → ventana → uso. Construida del esquema ' +
      '(multilayer-v2/v3), de build_rows y del código de heuristicos.py: si cambia el código, cambia la matriz.';
    caja.innerHTML = '<table><thead><tr><th>Fuente</th><th>Registro que la alimenta</th><th>Parser</th>' +
      '<th>Variable</th><th>Capa</th><th>Ventana</th><th>Uso</th><th>Heurísticos</th></tr></thead><tbody>' +
      filas.map(m => '<tr><td>' + varEsc(m.fuente) + '</td><td>' + varEsc(m.registro) + '</td><td class="m">' +
        varEsc(m.parser) + '</td><td class="m"><b>' + varEsc(m.feature) + '</b></td><td>' + varEsc(m.capa) +
        '</td><td>' + m.ventana_s + ' s</td><td>' + varEsc(m.uso) + '</td><td class="heur">' +
        varEsc((m.heuristicos || []).join(', ') || '—') + '</td></tr>').join('') + '</tbody></table>';
    pie.textContent = filas.length + ' columnas: 28 entran al modelo (v2), 3 de capa 2 se acumulan sin puntuarse (v3) ' +
      'y 3 son conteos que solo leen los heurísticos.';
    return;
  }

  if (!vivoDatos) { caja.innerHTML = '<p class="var-vacio">Cargando…</p>'; return; }
  if (vivoDatos.error) {
    caja.innerHTML = '<p class="var-vacio">' + varEsc(vivoDatos.error) + '</p>';
    res.textContent = ''; pie.textContent = ''; return;
  }
  const d = vivoDatos;
  const cfg = 'Red ' + d.config.red_entidades + ' · excluidas ' + (d.config.excluir.join(', ') || 'ninguna') +
    ' · protocolos fuera ' + (d.config.excluir_protocolos.join(', ') || 'ninguno') + ' (de ' + d.config.fuente + ')';

  if (vivoTab === 'eve') {
    const e = d.eve;
    const ign = Object.entries(e.ignorados || {}).map(([k, v]) => k + ' ' + v).join(', ');
    res.textContent = 'Tramo ' + (e.tramo ? hora(e.tramo.desde) + '–' + hora(e.tramo.hasta) + ' UTC' : 'vacío') +
      ' · ' + e.eventos + ' eventos leídos, ' + e.aportan + ' aportan a variables · ignorados: ' + (ign || 'ninguno') +
      '. El motor solo usa http, dns (consulta y NXDOMAIN) y tls.';
    const filas = d.eventos.filter(r => vivoPasa(r, q));
    caja.innerHTML = '<table><thead><tr><th>Hora UTC</th><th>Entidad</th><th>Evento</th><th>Origen → destino</th>' +
      '<th>Variable · aporte → valor en la ventana</th><th>Ventana</th><th>Fuente</th></tr></thead><tbody>' +
      filas.map(r => '<tr><td class="m">' + varEsc(r.hora) + '</td><td class="m">' + varEsc(r.entidad) +
        '</td><td>' + varEsc(r.evento) + '<div class="sub">' + varEsc(r.tipo) + (r.vlan ? ' · VLAN ' + r.vlan : '') +
        '</div></td><td class="m">' + varEsc(r.origen) + '<div class="sub">→ ' + varEsc(r.destino) + '</div></td><td>' +
        r.features.map(vfChip).join('') + '</td><td class="m">hasta ' + hora(r.ventana_fin) + '</td><td class="m">' +
        varEsc(r.fuente.fichero) + '<div class="sub">byte ' + r.fuente.byte + '</div></td></tr>').join('') +
      '</tbody></table>';
    pie.textContent = cfg + ' · * valor parcial (la ventana de 60 s empieza antes del tramo leído).';
  } else {
    const p = d.pcap;
    res.textContent = 'Tramo ' + (p.tramo ? hora(p.tramo.desde) + '–' + hora(p.tramo.hasta) + ' UTC' : 'vacío') +
      ' · ' + p.ficheros.length + ' ficheros cerrados del anillo, ' + p.tramas + ' tramas: ' + p.no_ipv4 +
      ' sin IPv4, ' + p.plano_control + ' de plano de control, ' + p.duplicados_espejo + ' copias del espejo, ' +
      p.fuera_de_alcance + ' de entidades fuera de la red, ' + p.atribuidas + ' atribuidas (' + p.entidad_excluida +
      ' de entidades excluidas). Mostrando: ' + p.filtro + '.' +
      (p.ilegibles.length ? ' No legibles: ' + p.ilegibles.map(x => x.fichero).join(', ') + '.' : '');
    const filas = d.tramas.filter(r => vivoPasa(r, q));
    caja.innerHTML = '<table><thead><tr><th>Hora UTC</th><th>VLAN</th><th>MAC origen → destino</th>' +
      '<th>IP origen → destino</th><th>Proto · flags</th><th>Long.</th><th>Variable · aporte → valor en la ventana</th>' +
      '<th>Ventana</th><th>Fichero</th></tr></thead><tbody>' +
      filas.map(r => '<tr><td class="m">' + varEsc(r.hora) + '</td><td class="m">' + (r.vlan || '—') +
        '</td><td class="m">' + varEsc(r.mac_src || '') + '<div class="sub">→ ' + varEsc(r.mac_dst || '') +
        '</div></td><td class="m">' + varEsc(r.ip_src) + (r.puerto_src ? ':' + r.puerto_src : '') +
        '<div class="sub">→ ' + varEsc(r.ip_dst) + (r.puerto_dst ? ':' + r.puerto_dst : '') +
        ' · entidad ' + varEsc(r.entidad) + ' (' + r.sentido + ')</div></td><td>' + varEsc(r.proto) +
        '<div class="sub">' + varEsc(r.evento) + '</div></td><td class="m">' + (r.longitud === null ? '—' : r.longitud + ' B') +
        '</td><td>' + r.features.map(vfChip).join('') + '</td><td class="m">hasta ' + hora(r.ventana_fin) +
        '</td><td class="m">' + varEsc(r.fuente.fichero || '') + '<div class="sub">trama ' + r.fuente.trama +
        '</div></td></tr>').join('') + '</tbody></table>';
    pie.textContent = cfg + ' · * valor parcial · borde discontinuo: capa 2, se acumula pero no se puntúa · ' +
      'ámbar: conteo que solo leen los heurísticos.';
  }
  if (!caja.querySelector('tbody tr')) caja.innerHTML = '<p class="var-vacio">Sin registros que aporten en este tramo' +
    (q ? ' con ese filtro' : '') + '.</p>';
}

async function cargarVivo(forzar) {
  const sec = document.getElementById('s-vivo');
  if (!sec || (!forzar && (vivoPausa || sec.hidden))) return;
  try {
    if (vivoTab === 'matriz') {
      if (!vivoMatriz) vivoMatriz = (await (await fetch('/api/trazabilidad')).json()).filas || [];
    } else {
      const todos = document.getElementById('vivoTodos').checked ? '1' : '0';
      vivoDatos = await (await fetch('/api/vivo?todos=' + todos)).json();
    }
  } catch (e) {
    vivoDatos = {error: 'No se pudo leer /api/vivo: ' + e};
  }
  renderVivo();
}

if (document.getElementById('vivoTabla')) {
  on('vivoTabs', 'click', (ev) => {
    const b = ev.target.closest('button[data-vtab]');
    if (!b) return;
    vivoTab = b.dataset.vtab;
    document.querySelectorAll('#vivoTabs button').forEach(x => x.classList.toggle('active', x === b));
    renderVivo();
    cargarVivo(true);
  });
  on('vivoFiltro', 'input', renderVivo);
  on('vivoTodos', 'change', () => cargarVivo(true));
  on('vivoPausa', 'click', () => {
    vivoPausa = !vivoPausa;
    document.getElementById('vivoPausa').textContent = vivoPausa ? 'Reanudar' : 'Pausar';
    if (!vivoPausa) cargarVivo(true);
  });
  // Enlaces "Ver en vivo" del diagrama: abren la pestaña de su fuente.
  document.addEventListener('click', (ev) => {
    const a = ev.target.closest('a[data-vtab]');
    if (!a) return;
    const b = document.querySelector('#vivoTabs button[data-vtab="' + a.dataset.vtab + '"]');
    if (b) b.click();
  });
  cargarVivo(true);
  setInterval(() => cargarVivo(false), 10000);
}

// ---- Sesion: quien eres y en que modo miras ------------------------------
// El modo es del ADMIN y solo del admin: alterna entre la vista operativa y la
// de desarrollo. No es un permiso -esta autorizado a las dos- sino una forma de
// quitarse de encima lo que no necesita mientras opera. Por eso vive en
// localStorage y no en la sesion: es preferencia, no autorizacion.
const SESION = JSON.parse(document.getElementById('datosSesion').textContent);
const DEV_SECS = ['s-topologia', 's-variables', 's-vivo', 's-modelo', 's-alcance', 's-simulacion'];

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


def compute_counters(decisions: list[dict], window_seconds: int = 3600,
                     detector_modelo: str = "ocsvm_scaled") -> dict:
    now = time.time()
    recent = [d for d in decisions if now - d.get("logged_at", 0) <= window_seconds]
    # Los dos detectores reales que pueden producir ALERT se cuentan por
    # separado -- mezclarlos en un solo numero oculta cual esta disparando,
    # justo cuando el motor ya tiene dos caminos distintos hacia ALERT
    # (el modelo desplegado y el heuristico de fuerza bruta). `detector_modelo`
    # es el nombre del detector del modelo EN ESTA red (viene de --detector-name):
    # tras recalibrar puede ser `if_recalibrado_2026_09`, no `ocsvm_scaled`; si se
    # dejara fijo, los contadores del modelo saldrian en 0 tras congelar.
    alert_ocsvm = sum(1 for d in recent if d["decision"] == "ALERT" and d.get("detector_name") == detector_modelo)
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
        if d["decision"] == "PERMIT" and d.get("detector_name") == detector_modelo
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
    if not names:
        return {}
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
    """Resumen del detector para el panel.

    El umbral se lee de donde lo lee el motor (`detectors.<nombre>.calibration`,
    ver `motor_decision.load_threshold`); solo si el manifiesto es de laboratorio y no
    lo trae ahí se usa `evaluation.<nombre>.threshold_used`. Las métricas que el
    manifiesto no tenga quedan en None y el panel muestra «—»: mostrar un 0 % o las
    cifras de otro detector sería peor que no mostrar nada.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    det = (manifest.get("detectors") or {}).get(detector_name) or {}
    cal = det.get("calibration") or {}
    ev = (manifest.get("evaluation") or {}).get(detector_name) or {}
    if "threshold" in cal:
        threshold = float(cal["threshold"])
    elif "threshold_used" in ev:
        threshold = float(ev["threshold_used"])
    else:
        raise KeyError(f"el manifiesto no tiene umbral para el detector {detector_name!r}")

    def num(v):
        return None if v is None else float(v)

    an = ev.get("anomalies") or {}
    return {
        "detector_name": detector_name,
        "threshold": threshold,
        "test_fpr": num((ev.get("test") or {}).get("fpr")),
        "detection_rate": num(an.get("detection_rate")),
        "kali_real_detection_rate": num(an.get("kali_real_detection_rate")),
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
RUTAS_ADMIN = frozenset({"/api/variables", "/api/artefactos", "/api/escenarios", "/api/archivo",
                         "/api/vivo", "/api/trazabilidad"})

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


def ruta_modelo_activo(manifest_path: Path, detector_name: str, raiz: Path) -> Path:
    """Ubica el artefacto declarado para el detector activo sin cargar el joblib."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declarado = manifest.get("detectors", {}).get(detector_name, {}).get("model_path")
        if isinstance(declarado, str) and declarado.strip():
            ruta = Path(declarado)
            return ruta if ruta.is_absolute() else raiz / ruta
    except (OSError, ValueError, TypeError):
        pass
    # Manifiestos históricos: el artefacto vivía junto al manifiesto.
    return manifest_path.parent / (detector_name + ".joblib")


def estado_artefactos(eve_path: Path, dataset: Path | None, manifest_path: Path,
                      log_path: Path, schema_extra: Path | None,
                      descripciones: Path, raiz: Path | None = None,
                      capture_dir: Path = Path("/var/lib/ppi-motor-capture"),
                      detector_name: str = "ocsvm_scaled") -> dict:
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

    modelo_activo = ruta_modelo_activo(manifest_path, detector_name, r)
    config_local = r / "configs/cyberflow.local.toml"
    config_usada = config_local if config_local.is_file() else r / "configs/cyberflow.toml"
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
                  rel("scripts/features/extract_multilayer_v3.py", "py",
                      "trama con contexto (VLAN, MAC) y deduplicacion del espejo"),
                   _stat_fichero(config_usada, "toml", "configuracion de este despliegue")],
        "parser_eve": [_stat_fichero(eve_path, "json", "fuente: eventos de Suricata"),
                       rel("scripts/features/extract_multilayer_v2.py", "py",
                           "load_app_observations: http, dns y tls")],
        "pcap": [anillo, rel("scripts/engine/vista_vivo.py", "py",
                             "«Datos en vivo»: la misma cadena del motor sobre el tramo reciente")],
        "eve": [_stat_fichero(eve_path, "json", "una linea JSON por evento"),
                rel("scripts/engine/vista_vivo.py", "py",
                    "«Datos en vivo»: la misma cadena del motor sobre el tramo reciente")],
        "c_part": [rel("scripts/dataset/particionar_linea_base.py", "py",
                       "bloques horarios y banda de guarda")],
        "c_cand": [rel("scripts/analysis/compare_frozen_models_metrics.py", "py",
                       "comparacion historica de 7 candidatos"),
                   rel("scripts/modeling/experiments/significancia_modelos.py", "py",
                       "McNemar + Holm entre pares")],
        "c_metr": [rel("scripts/modeling/entrenar_preliminar.py", "py",
                       "FPR de validacion y prueba con el umbral congelado")],
        "c_cong": [rel("scripts/modeling/entrenar_preliminar.py", "py",
                       "entrena y fija el umbral desde validacion"),
                   _stat_fichero(manifest_path, "json", "umbral, orden y hash")],
        "c_desp": [rel("scripts/modeling/promover_preliminar.py", "py",
                       "paquete -> Pipeline + manifiesto"),
                   rel("scripts/modeling/verificar_equivalencia_umbral.py", "py",
                       "hash, orden y umbral equivalente"),
                   rel("scripts/setup/cyberflow_config.py", "py", "unidades systemd")],
        "c_acum": [rel("scripts/features/acumular_v3.py", "py",
                       "acumula filas del anillo al dataset")],
        "c_antes": [rel("scripts/modeling/comparar_reentrenamiento.py", "py",
                        "metricas previas vs posteriores")],
        "variables": [_stat_fichero(schema_extra, "json", "contrato de las 31 variables")
                      if schema_extra else rel("configs/features/multilayer-v3.json",
                                               "json", "contrato de las 31 variables"),
                      _stat_fichero(descripciones, "json", "texto por variable"),
                      rel("scripts/features/acumular_v3.py", "py",
                          "acumula filas del anillo al dataset"),
                      (_stat_fichero(dataset, "csv", "dataset acumulado")
                       if dataset else rel("artifacts/linea-base/multilayer-v3.csv",
                                           "csv", "dataset acumulado"))],
        "modelo": [_stat_fichero(modelo_activo, "joblib",
                                  "artefacto del detector activo; umbral en el manifiesto"),
                   _stat_fichero(manifest_path, "json", "hashes y evaluacion")],
        "reentrenamiento": [rel("scripts/dataset/particionar_linea_base.py", "py",
                                "parte sin fuga temporal"),
                            rel("scripts/modeling/entrenar_preliminar.py", "py",
                                "entrena y congela el umbral")],
        "heuristicos": [rel("scripts/engine/heuristicos.py", "py",
                            "las cuatro reglas y sus umbrales")],
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


def resolver_detector(explicito: str | None, raiz: Path = RAIZ_REPO) -> tuple[str, str]:
    """Detector cuyas métricas muestra el panel, y de dónde se tomó.

    Tiene que ser el MISMO que ejecuta el motor. La unidad lo pasa con --detector-name
    (el generador lo escribe desde la configuración). Si una unidad no lo pasa, se lee
    de la misma configuración de la que lo toma el generador —el perfil local y, si no,
    el genérico— en lugar de caer a un nombre fijo: con un nombre fijo, Sensor1 mostraba
    las cifras del OCSVM mientras el motor ejecutaba el Isolation Forest recalibrado.
    """
    if explicito:
        return explicito, "--detector-name"
    for nombre in ("cyberflow.local.toml", "cyberflow.toml"):
        try:
            datos = tomllib.loads((raiz / "configs" / nombre).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        detector = (datos.get("motor") or {}).get("detector")
        if detector:
            return str(detector), f"configs/{nombre} [motor] detector"
    return "ocsvm_scaled", "valor por omisión (ninguna configuración declara detector)"


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
    parser.add_argument(
        "--detector-name", default=None,
        help="detector del motor cuyas métricas se muestran; si se omite, se lee de "
             "configs/cyberflow.local.toml (o cyberflow.toml), [motor] detector",
    )
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
    # «Datos en vivo»: por omisión, los mismos valores que el generador pasa al
    # motor, leídos de configs/cyberflow.local.toml (o cyberflow.toml).
    parser.add_argument("--capture-dir", default=None,
                        help="anillo PCAP del motor; por omisión [captura] directorio")
    parser.add_argument("--capture-glob", default=None)
    parser.add_argument("--entity-network", default=None,
                        help="red de entidades; por omisión [red] red_entidades")
    parser.add_argument("--excluir", default=None,
                        help="redes excluidas separadas por comas; por omisión [red] excluir")
    parser.add_argument("--excluir-protocolos", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="modo demostración: sin login, sin comprobar servicios reales, con "
             "un banner que avisa de que son datos de ejemplo. Para ver el "
             "sistema funcionando desde un clon recién hecho, sin red ni sensor.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.detector_name, fuente_detector = resolver_detector(args.detector_name)
    print(f"panel: detector {args.detector_name} (fuente: {fuente_detector})",
          file=sys.stderr, flush=True)
    service_names = [name.strip() for name in args.services.split(",") if name.strip()]
    model_summary = load_model_summary(args.manifest_path, args.detector_name)

    # Sin autenticacion solo si se pide EXPRESAMENTE. Si faltan los ficheros y
    # nadie lo pidio, el panel no arranca: servir sin login porque un fichero no
    # estaba es el modo de fallo que hay que evitar.
    auth = not (args.sin_autenticacion or args.demo)
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
                        "modo": "demo" if args.demo else "live",
                        "services": service_status([] if args.demo else service_names),
                        "model": model_summary,
                        "blocked": enforcement_list(args.enforce_command),
                        "counters": compute_counters(decisions, detector_modelo=args.detector_name),
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
                    args.schema_extra, args.descripciones, detector_name=args.detector_name))
                return
            if path == "/api/escenarios":
                self._send_json(cargar_escenarios(args.escenarios))
                return
            if path in ("/api/vivo", "/api/trazabilidad"):
                # Se importa aquí: el panel arranca igual aunque falte el
                # extractor, y solo esta sección lo necesita.
                try:
                    if str(Path(__file__).resolve().parent) not in sys.path:
                        sys.path.insert(0, str(Path(__file__).resolve().parent))
                    import vista_vivo
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": "vista_vivo no disponible: %s" % exc})
                    return
                if path == "/api/trazabilidad":
                    self._send_json({"filas": vista_vivo.matriz_trazabilidad()})
                    return
                params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                if args.demo:
                    self._send_json({"error": "en modo demostración no hay captura en vivo"})
                    return
                cfg = vista_vivo.config(
                    red_entidades=args.entity_network, directorio=args.capture_dir,
                    anillo_glob=args.capture_glob,
                    excluir=None if args.excluir is None else
                    [t.strip() for t in args.excluir.split(",") if t.strip()],
                    excluir_protocolos=None if args.excluir_protocolos is None else
                    [int(t) for t in args.excluir_protocolos.split(",") if t.strip()])
                if not cfg.get("red_entidades"):
                    self._send_json({"error": "falta la red de entidades (--entity-network "
                                              "o [red] red_entidades)"})
                    return
                try:
                    self._send_json(vista_vivo.calcular_con_cache(
                        args.eve_path, cfg, todos=params.get("todos") == "1"))
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": "%s: %s" % (type(exc).__name__, exc)})
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
            if path == "/api/archivo":
                # Modo desarrollador: muestra el CONTENIDO de un script del
                # pipeline. Whitelist estricta -solo rutas que estado_artefactos
                # declara- y solo tipos de TEXTO: ni path traversal, ni binarios.
                import urllib.parse as _u
                params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                ruta = _u.unquote(params.get("ruta", ""))
                mapa = estado_artefactos(
                    args.eve_path, args.dataset, args.manifest_path, args.log_path,
                    args.schema_extra, args.descripciones, detector_name=args.detector_name)
                permitidas = {}
                for lst in mapa.values():
                    for art in lst:
                        if art.get("ruta"):
                            permitidas[art["ruta"]] = art.get("tipo", "")
                if ruta not in permitidas:
                    self.send_error(403)
                    return
                tipo = permitidas[ruta]
                TEXTO = {"py", "sh", "toml", "md", "json", "log", "yml", "yaml", "cfg", "txt"}
                fp = Path(ruta)
                if tipo not in TEXTO or not fp.is_file():
                    self._send_json({"ruta": ruta, "tipo": tipo, "contenido": None,
                                     "nota": "no es texto legible, o no existe en este despliegue"})
                    return
                try:
                    crudo = fp.read_bytes()
                    contenido = crudo[:524288].decode("utf-8", errors="replace")
                    self._send_json({"ruta": ruta, "tipo": tipo, "contenido": contenido,
                                     "truncado": len(crudo) > 524288, "bytes": len(crudo)})
                except OSError:
                    self._send_json({"ruta": ruta, "tipo": tipo, "contenido": None,
                                     "nota": "no se pudo leer"})
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
