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
import json
import subprocess
import time
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

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.8rem; }
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

  .spark-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; overflow-x: auto; }
  .spark-legend { display: flex; gap: 1.1rem; font-size: 0.76rem; color: var(--text-dim); margin-top: 0.5rem; }
  .spark-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
  .swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

  table { border-collapse: collapse; width: 100%; font-size: 0.86rem; }
  .tbl-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; overflow-x: auto; }
  th { text-align: left; padding: 0.6rem 0.9rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); border-bottom: 1px solid var(--border); }
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
</style>

<div class="shell">
<aside class="side">
  <div class="brand">CyberFlow<small>Motor en vivo</small></div>
  <div class="side-state" id="sideState"><span class="dot"></span><span id="sideStateText">conectando&hellip;</span></div>
  <nav id="nav">
    <a href="#s-salud" data-sec="s-salud"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/></svg>Salud</a>
    <a href="#s-topologia" data-sec="s-topologia"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg>Topología</a>
    <a href="#s-modelo" data-sec="s-modelo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>Modelo</a>
    <a href="#s-alcance" data-sec="s-alcance"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><line x1="5" y1="19" x2="19" y2="5"/></svg>Alcance</a>
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
  </header>

  <div class="healthbar" id="healthbar"></div>

  <section id="s-salud">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.9" fill="currentColor" stroke="none"/></svg><h2>Salud del sistema</h2></div>
    <div class="grid" id="health"></div>
  </section>

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
    <div class="tbl-wrap">
      <table>
        <thead><tr><th>Hora</th><th>IP</th><th>Decisión</th><th>Motivo</th><th>Score</th><th>Paquetes</th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>
</div>

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

function renderSparkline(activity) {
  const svg = document.getElementById('spark');
  const n = activity.length;
  const w = 610, h = 46, bw = w / n;
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
    bars += `<rect x="${x.toFixed(1)}" y="${(h - barH).toFixed(1)}" width="${Math.max(1, bw - 1.2).toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="${color}"/>`;
  });
  svg.innerHTML = bars;
}

function renderHistogram(data) {
  const svg = document.getElementById('histogram');
  const hint = document.getElementById('histogramHint');
  if (!data.buckets.length) {
    svg.innerHTML = '';
    hint.textContent = 'Sin scores recientes para graficar (solo hay decisiones del heurístico de ventana vacía).';
    return;
  }
  const w = 610, h = 90, padBottom = 14;
  const maxCount = Math.max(...data.buckets.map(b => b.count), 1);
  const bw = w / data.buckets.length;
  let bars = '';
  data.buckets.forEach((b, i) => {
    const barH = b.count > 0 ? Math.max(3, (b.count / maxCount) * (h - padBottom - 4)) : 0;
    const x = i * bw;
    // Rojo: cubo enteramente en zona ALERT (por debajo del umbral). Verde:
    // enteramente en zona PERMIT. Ambar: el cubo cruza el umbral -- scores
    // ahi mezclan ambas decisiones, la zona mas interesante para mirar.
    let color = 'var(--accent)';
    if (b.hi <= data.threshold) color = 'var(--danger)';
    else if (b.lo < data.threshold) color = 'var(--amber)';
    bars += `<rect x="${x.toFixed(1)}" y="${(h - padBottom - barH).toFixed(1)}" width="${Math.max(1, bw - 1.2).toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="${color}"/>`;
  });
  const thresholdX = ((data.threshold - data.min) / (data.max - data.min)) * w;
  bars += `<line x1="${thresholdX.toFixed(1)}" y1="0" x2="${thresholdX.toFixed(1)}" y2="${h - padBottom}" stroke="var(--text)" stroke-width="1.3" stroke-dasharray="3 2"/>`;
  bars += `<text x="${thresholdX.toFixed(1)}" y="${h - 3}" font-size="9" fill="var(--text-dim)" text-anchor="middle" font-family="ui-monospace, monospace">umbral</text>`;
  svg.innerHTML = bars;
  hint.textContent = `${data.n} score(s) real(es) de las últimas 500 decisiones, entre ${data.min.toFixed(2)} y ${data.max.toFixed(2)}. Rojo = zona ALERT, ámbar = cruza el umbral, verde = zona PERMIT.`;
}

async function loadActivity(range) {
  const data = await (await fetch('/api/activity?range=' + range)).json();
  renderSparkline(data.activity);
  document.getElementById('sparkRangeLabel').textContent = range === '24h'
    ? '← hace 24h    ahora →'
    : '← hace 60 min    ahora →';
}

document.getElementById('rangeToggle').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-range]');
  if (!btn) return;
  currentRange = btn.dataset.range;
  document.querySelectorAll('#rangeToggle button').forEach(b => b.classList.toggle('active', b === btn));
  loadActivity(currentRange);
});

async function refresh() {
  try {
    const status = await (await fetch('/api/status')).json();
    stamp.textContent = 'Actualizado ' + new Date().toLocaleTimeString();

    renderHealthbar(status.services, status.counters, status.capture_metrics, status.calibracion);
    renderSidebar(status);
    renderTopologia(status);

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

    const m = status.model;
    model.innerHTML = [
      card('Detector', 'OCSVM'),
      card('Umbral', m.threshold.toFixed(4), 'accent'),
      card('FPR benigno', (m.test_fpr * 100).toFixed(2) + '%'),
      card('Detección global', (m.detection_rate * 100).toFixed(1) + '%', 'accent'),
      card('Detección Kali-real', (m.kali_real_detection_rate * 100).toFixed(1) + '%', 'accent'),
    ].join('');

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

    const ex = status.alcance || {};
    document.getElementById('alcance').innerHTML = [
      card('Paquetes de plano de control descartados', (ex.plano_control_descartado ?? 0).toLocaleString('es')),
      card('Ventanas de entidades excluidas', (ex.ventanas_excluidas ?? 0).toLocaleString('es')),
      card('Red analizada', ex.red_entidades || '&mdash;'),
    ].join('');
    const protos = (ex.protocolos_excluidos || []).map(p => PROTO[p] || ('proto ' + p));
    document.getElementById('alcanceDetalle').textContent =
      (protos.length ? 'Protocolos fuera del cálculo: ' + protos.join(', ') + '. ' : '') +
      ((ex.excluidas || []).length ? 'Entidades fuera del cálculo: ' + ex.excluidas.join(', ') + '.' : '');

    if (currentRange === '1h') renderSparkline(status.activity);
    else loadActivity(currentRange);

    const histogramData = await (await fetch('/api/score-histogram')).json();
    renderHistogram(histogramData);

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

function renderDecisionsTable() {
  const query = document.getElementById('ipFilter').value.trim();
  const rows = query ? lastDecisions.filter(d => d.entity_ip.includes(query)) : lastDecisions;
  document.getElementById('filterHint').textContent = query
    ? `${rows.length} de ${lastDecisions.length} decisiones coinciden con "${query}"`
    : '';
  document.getElementById('decisions').innerHTML = rows.length ? rows.map(d => {
    const isAlert = d.decision === 'ALERT';
    const badge = isAlert ? `<span class="badge alert">${ICON.bad} ALERT</span>` : `<span class="badge permit">${ICON.ok} PERMIT</span>`;
    return `<tr class="${isAlert ? 'row-alert' : ''}"><td>${fmtTime(d.logged_at)}</td><td class="ip">${d.entity_ip}</td>` +
      `<td>${badge}</td><td class="why">${DETECTOR_LABEL[d.detector_name] || d.detector_name}</td>` +
      `<td class="num">${d.score != null ? d.score.toFixed(4) : '&mdash;'}</td><td class="num">${d.packet_count_10s}</td></tr>`;
  }).join('') : `<tr class="empty-row"><td colspan="6">${query ? 'Ninguna decisión coincide con el filtro.' : 'Sin decisiones recientes.'}</td></tr>`;
}

document.getElementById('ipFilter').addEventListener('input', renderDecisionsTable);

document.getElementById('exportCsv').addEventListener('click', () => {
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
    grupos: [
      { x: 18,  y: 242, w: 834, h: 152, txt: 'Adquisición' },
      { x: 18,  y: 406, w: 834, h: 242, txt: 'Análisis' },
      { x: 300, y: 660, w: 300, h: 84,  txt: 'Respuesta' },
      { x: 300, y: 750, w: 552, h: 76,  txt: 'Observabilidad' },
    ],
    nodos: [
      { id: 'red',       x: 330, y: 8,   w: 240, h: 56, icono: 'red',    titulo: 'Red de la entidad',  tag: 'ENTORNO' },
      { id: 'span',      x: 330, y: 92,  w: 240, h: 56, icono: 'espejo', titulo: 'Espejo SPAN',        tag: 'CORE-STACK' },
      { id: 'nic',       x: 330, y: 176, w: 240, h: 56, icono: 'nic',    titulo: 'Interfaz en escucha', tag: 'PROMISCUA · SIN IP' },
      { id: 'captura',   x: 60,  y: 260, w: 230, h: 56, icono: 'disco',  titulo: 'tcpdump',            tag: 'SERVICIO' },
      { id: 'suricata',  x: 610, y: 260, w: 230, h: 56, icono: 'lupa',   titulo: 'Suricata',           tag: 'SERVICIO' },
      { id: 'pcap',      x: 60,  y: 344, w: 230, h: 48, icono: 'fichero', titulo: 'anillo live-*.pcap', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'eve',       x: 610, y: 344, w: 230, h: 48, icono: 'fichero', titulo: 'eve.json',          tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'descartes', x: 30,  y: 424, w: 250, h: 56, icono: 'tijera', titulo: 'Fuera del cálculo',  tag: 'SUMIDERO',  clase: 'sumidero' },
      { id: 'motor',     x: 330, y: 424, w: 240, h: 56, icono: 'cpu',    titulo: 'Atribución de flujo', tag: 'SERVICIO' },
      { id: 'variables', x: 330, y: 508, w: 240, h: 56, icono: 'tabla',  titulo: '28 variables / 10 s', tag: 'L3 · L4 · L7' },
      { id: 'modelo',    x: 330, y: 592, w: 240, h: 56, icono: 'modelo', titulo: 'OCSVM congelado',    tag: 'UMBRAL FIJO' },
      { id: 'control',   x: 330, y: 676, w: 240, h: 56, icono: 'escudo', titulo: 'Control nftables',   tag: 'EXPIRA A 120 s' },
      { id: 'registro',  x: 330, y: 760, w: 240, h: 48, icono: 'fichero', titulo: 'motor_decision.log', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'panel',     x: 620, y: 760, w: 230, h: 48, icono: 'ojo',    titulo: 'Este panel',         tag: 'SOLO LECTURA' },
    ],
    aristas: [
      { d: 'M450,64 L450,92',                    desde: 'red',       hasta: 'span' },
      { d: 'M450,148 L450,176',                  desde: 'span',      hasta: 'nic' },
      { d: 'M450,232 C450,250 175,242 175,260',  desde: 'nic',       hasta: 'captura' },
      { d: 'M450,232 C450,250 725,242 725,260',  desde: 'nic',       hasta: 'suricata' },
      { d: 'M175,316 L175,344',                  desde: 'captura',   hasta: 'pcap' },
      { d: 'M725,316 L725,344',                  desde: 'suricata',  hasta: 'eve' },
      { d: 'M175,392 C175,412 450,404 450,424',  desde: 'pcap',      hasta: 'motor' },
      { d: 'M725,392 C725,412 450,404 450,424',  desde: 'eve',       hasta: 'motor' },
      { d: 'M330,452 L280,452',                  desde: 'motor',     hasta: 'descartes', tipo: 'descarte', etiqueta: 'descarta', ex: 305, ey: 444 },
      { d: 'M450,480 L450,508',                  desde: 'motor',     hasta: 'variables' },
      { d: 'M450,564 L450,592',                  desde: 'variables', hasta: 'modelo' },
      { d: 'M450,648 L450,676',                  desde: 'modelo',    hasta: 'control' },
      { d: 'M450,732 L450,760',                  desde: 'control',   hasta: 'registro' },
      { d: 'M570,784 L620,784',                  desde: 'registro',  hasta: 'panel' },
    ],
  },
};

let topoVista = 'esencial';

const TOPO_TEXTO = {
  red: {
    que: 'El tráfico entre VLAN de la entidad. No se toca: CyberFlow solo observa una copia.',
    nota: 'La red enruta a través del cortafuegos, así que todo el tráfico entre VLAN pasa por el troncal espejado.',
  },
  span: {
    que: 'La sesión de espejo del conmutador copia el troncal del cortafuegos hacia el puerto del sensor.',
    nota: 'Desde el sensor no se puede leer el estado de la sesión: se infiere de que lleguen paquetes. Si deja de llegar tráfico, el problema puede estar aquí y el panel no lo distingue de una red en silencio.',
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
    que: 'Veintiocho variables por entidad y ventana: seis de red, cinco de transporte y diecisiete de aplicación.',
    nota: 'El extractor está congelado y su salida se compara contra los SHA-256 del manifiesto. Los filtros actúan sobre su entrada, nunca sobre sus fórmulas.',
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
      return {
        estado: drops == null ? '' : (drops ? 'warn' : 'ok'),
        valor: drops == null ? 'sin medir' : (drops ? num(drops) + ' descartes' : 'sin descartes'),
        datos: { 'Paquetes vistos': cm ? num(cm.kernel_packets) : 'sin medir',
                 'Descartes del núcleo': drops == null ? 'sin medir' : num(drops) },
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
      return {
        estado: on ? 'ok' : 'bad',
        valor: num(c.total || 0) + ' ventanas/h',
        datos: { 'Variables por ventana': '28', 'Paso': '10 s', 'Historia máxima': '60 s' },
      };
    }
    case 'registro':
      return { estado: '', valor: 'una línea por decisión', datos: {} };
    case 'panel':
      return { estado: 'ok', valor: 'solo lectura', datos: { 'Refresco': '5 s' } };
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
    return `<path class="topo-edge ${vivo ? 'live' : 'dim'}" d="${e.d}"/>`;
  }).join('');

  const nodos = v.nodos.map(n => {
    const e = est[n.id];
    const cy = n.y + n.h / 2;
    const color = e.estado === 'ok' ? 'var(--ok)' : e.estado === 'warn' ? 'var(--amber)'
                : e.estado === 'bad' ? 'var(--danger)' : 'var(--border)';
    const etiqueta = n.tag
      ? `<text class="tag" x="${n.x + 42}" y="${n.y + n.h - 5}">${n.tag}</text>` : '';
    const desplazar = n.tag ? -8 : 0;
    return `<g class="topo-node ${e.estado} ${n.clase || ''} ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      <g class="ico" transform="translate(${n.x + 13}, ${cy - 9 + desplazar})"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[n.icono]}</svg></g>
      <text class="ttl" x="${n.x + 42}" y="${cy - 3 + desplazar}">${n.titulo}</text>
      <text class="sub" x="${n.x + 42}" y="${cy + 12 + desplazar}">${e.valor}</text>
      ${etiqueta}
      <circle class="led" cx="${n.x + n.w - 13}" cy="${n.y + 13}" r="4" fill="${color}"/>
    </g>`;
  }).join('');

  svg.innerHTML = grupos + aristas + nodos;
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

document.getElementById('topoVista').addEventListener('click', (ev) => {
  const b = ev.target.closest('button[data-vista]');
  if (!b) return;
  topoVista = b.dataset.vista;
  document.querySelectorAll('#topoVista button').forEach(x => x.classList.toggle('active', x === b));
  topoZoom = null;   // cada vista tiene otro tamano: se reajusta
  // Si el nodo seleccionado no existe en la vista nueva, se cae al motor.
  if (!TOPO_VISTAS[topoVista].nodos.some(n => n.id === topoSel)) topoSel = 'motor';
  if (topoUltimo) renderTopologia(topoUltimo);
});

document.getElementById('topoMas').addEventListener('click', () => {
  topoZoom = Math.min(3, escalaActual() * 1.25); aplicarZoom();
});
document.getElementById('topoMenos').addEventListener('click', () => {
  topoZoom = Math.max(0.25, escalaActual() / 1.25); aplicarZoom();
});
document.getElementById('topoReset').addEventListener('click', () => {
  topoZoom = null; aplicarZoom();
});

document.getElementById('topoExpandir').addEventListener('click', () => {
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
  document.getElementById('topoDetail').innerHTML =
    `<h3>${n.titulo}<span class="state ${e.estado}">${e.valor}</span></h3>` +
    (t.que ? `<p>${t.que}</p>` : '') +
    (filas ? `<dl>${filas}</dl>` : '') +
    (t.nota ? `<p class="dim">${t.nota}</p>` : '');
}

document.getElementById('topo').addEventListener('click', (ev) => {
  const g = ev.target.closest('.topo-node');
  if (!g) return;
  topoSel = g.dataset.node;
  document.querySelectorAll('#topo .topo-node').forEach(x => x.classList.toggle('sel', x === g));
  renderTopoDetalle();
});
document.getElementById('topo').addEventListener('keydown', (ev) => {
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


def suricata_metrics(command: str) -> dict | None:
    """Metricas reales de captura via el helper ya autorizado en sudoers.

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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service_names = [name.strip() for name in args.services.split(",") if name.strip()]
    model_summary = load_model_summary(args.manifest_path, args.detector_name)

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict | list) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path, _, query = self.path.partition("?")
            if path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
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
                        "capture_metrics": suricata_metrics(args.suricata_metrics_command),
                        "alcance": leer_alcance(args.log_path),
                        "calibracion": {
                            "calibrado_en_esta_red": args.calibrado_en_esta_red,
                        },
                    }
                )
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

    print(f"Dashboard: http://{args.host}:{args.port}/")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
