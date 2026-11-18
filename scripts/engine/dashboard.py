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
import bisect
import hashlib
import hmac
import ipaddress
import json
import secrets
import ssl
import subprocess
import sys
import threading
import time
import tomllib
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:      # cargado por ruta (tests)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import cadena_v2  # noqa: E402  (mismo directorio; solo lectura de las trazas v2)

# Cadena de respuesta v2 (4A). None = panel con la politica v1 de siempre (demo).
_CADENA_V2: "cadena_v2.IndiceV2 | None" = None

RAIZ_REPO = Path(__file__).resolve().parents[2]

HTML = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberFlow &middot; motor en vivo</title>
<script id="temaInicial">/* 17-nov: tema claro por omision; el boton «Tema» lo alterna y se recuerda. */
try { document.documentElement.dataset.tema = localStorage.getItem('cf_tema') || 'claro'; }
catch (e) { document.documentElement.dataset.tema = 'claro'; }</script>
<link id="favicon" rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='13' fill='%235eead4'/%3E%3C/svg%3E">
<style>
  :root {
    /* 3-nov: fondo mas profundo y superficies con mas escalon entre si, para
       que tarjetas, tablas y la barra del recorrido se separen al proyectar. */
    --bg: #070b15;
    --surface: #0f1729;
    --surface-2: #17213a;
    --border: #233152;
    --text: #e3eaf6;
    /* 13-oct: subido de #7c8bad a #8d9cbd. El anterior daba 4,59:1 sobre las
       tarjetas (AA justo, sin margen) y se perdia proyectado; este da 5,68:1
       y sigue 2,3x mas tenue que --text, asi que la jerarquia se mantiene. */
    --text-dim: #94a3c4;
    --accent: #45dfc9;
    --ok: #4ade80; --ok-soft: #12271c;
    --amber: #f0b429; --amber-soft: #332508;
    --danger: #f87171; --danger-soft: #351515;
    /* Paleta categorica para las capas del modelo (L2/L3/L4/L7): tonos vivos y
       distintos entre si, elegidos para NO chocar con los colores semanticos
       (verde=ok, ambar=aviso, rojo=alerta). Contraste medido sobre las
       superficies del panel >= 5.9 (AA de texto normal). */
    /* Revisada el 12-oct con el validador de la skill de visualizacion: el
       azul y el violeta anteriores eran indistinguibles con deuteranopia
       (dE 1,3). Estos cuatro pasan separacion para daltonismo y contraste. */
    --capa-a: #199e70; --capa-b: #3987e5; --capa-c: #d55181; --capa-d: #9085e9;
    --mono: ui-monospace, "Cascadia Code", "Roboto Mono", "SF Mono", Menlo, Consolas, monospace;
    --sans: ui-sans-serif, system-ui, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  /* Barras de desplazamiento al tono del tema: la blanca del navegador cantaba
     sobre el fondo oscuro, sobre todo en el menu lateral. */
  * { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
  ::-webkit-scrollbar { width: 9px; height: 9px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 5px;
    border: 2px solid transparent; background-clip: content-box; }
  ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); background-clip: content-box; }
  ::-webkit-scrollbar-corner { background: transparent; }
  body {
    margin: 0; color: var(--text);
    background: radial-gradient(1200px 600px at 85% -10%, rgba(69,223,201,.07), transparent 60%),
                radial-gradient(900px 500px at -10% 110%, rgba(57,135,229,.06), transparent 60%), var(--bg);
    background-attachment: fixed;
    font-family: var(--sans); font-size: 15px; line-height: 1.5;
  }

  /* --- Distribucion: barra lateral fija + contenido --- */
  .shell { display: grid; grid-template-columns: 224px minmax(0, 1fr); }
  /* Sin esto, el ancho de contenido minimo de la barra (su nav) estira la
     columna mas que la pantalla y el documento desborda en movil: el min-width:0
     deja que la pista encoja por debajo del contenido y la barra scrollee dentro. */
  .shell > * { min-width: 0; }
  /* 18-nov: la barra es FIJA (no sticky): con sticky, al llegar al final de la página se quedaba
     donde terminaba .shell y debajo asomaba el fondo. */
  .shell { display: block; padding-left: 224px; }
  .side {
    position: fixed; left: 0; top: 0; bottom: 0; width: 224px; box-sizing: border-box; z-index: 30;
    border-right: 1px solid var(--border); background: var(--surface);
    padding: 1.3rem 0.9rem; display: flex; flex-direction: column; gap: 1rem;
    overflow-y: auto;
  }
  .side .brand { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.01em; padding: 0 0.45rem; }
  .side .brand { padding: 0.7rem 0.45rem 0.2rem; }
  .side .brand-logo { display: block; width: 100%; max-width: 180px; height: auto; margin: 0 auto; }
  .side .side-state { justify-content: center; align-self: center; margin: 0 0 0.6rem; padding: 0.22rem 0.8rem;
    border-radius: 999px; border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.05);
    font: 700 0.7rem var(--mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .side .side-state.ok { color: #6ee7b7; border-color: rgba(110,231,183,0.35); }
  .side .side-state.warn { color: #fcd34d; border-color: rgba(252,211,77,0.4); }
  .side .side-state.bad { color: #fca5a5; border-color: rgba(252,165,165,0.45); }
  .side .side-state.ok .dot { animation: latido 2s ease-in-out infinite; }
  @keyframes latido { 50% { opacity: 0.35; } }
  @media (prefers-reduced-motion: reduce) { .side .side-state.ok .dot { animation: none; } }
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
  .side nav { display: flex; flex-direction: column; gap: 0.1rem; }
  .nav-grupo { font: 600 0.66rem var(--mono); letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--text-dim); opacity: 0.65; padding: 0.7rem 0.6rem 0.25rem; }
  .nav-grupo:first-child { padding-top: 0.1rem; }
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
  .side .foot { margin-top: auto; padding: 0 0.45rem; font-size: 0.74rem; color: var(--text-dim); font-family: var(--mono); }

  .wrap { max-width: 1080px; margin: 0 auto; padding: 1.6rem 1.4rem 4rem; }
  section { scroll-margin-top: 1rem; }
  /* Navegacion por paginas: una seccion a la vez, asi el menu de la izquierda y
     el contenido de la derecha SIEMPRE coinciden. La activa lleva .pag-activa.
     El atributo hidden (modo operativo) gana: misma especificidad, declarado
     despues, para que una seccion de desarrollo oculta no reaparezca. */
  .wrap > section[id] { display: none; }
  .wrap > section[id].pag-activa { display: block; }
  @media (prefers-reduced-motion: no-preference) {
    .wrap > section[id].pag-activa { animation: cf-entra .18s ease-out; }
    @keyframes cf-entra { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    .btn-sec, .btn-prep, .esc-card, .nav a, .rg-pasos button { transition: background-color .15s, border-color .15s, color .15s, transform .15s; }
    .esc-card:hover { transform: translateY(-1px); }
  }
  .tbl-wrap, .esc-filas, .cmp-card { contain: content; }
  .wrap > section[id][hidden] { display: none; }
  /* Pie de "Vistas relacionadas": enlaces a las vistas que siguen el hilo. */
  .rel-vistas { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem;
    margin-top: 1.6rem; padding-top: 0.9rem; border-top: 1px solid var(--border); }
  .rel-lbl { font: 600 0.66rem var(--mono); letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--text-dim); margin-right: 0.2rem; }
  .rel-link { display: inline-flex; align-items: center; gap: 0.3rem; text-decoration: none;
    font-size: 0.82rem; color: var(--accent); background: var(--surface-2);
    border: 1px solid var(--border); border-radius: 999px; padding: 0.3rem 0.75rem; }
  .rel-link:hover { border-color: var(--accent); background: var(--surface); }

  @media (max-width: 900px) {
    /* En movil se apila: bloque, no grid. Con una sola columna de grid y dos
       hijos, .wrap caia en una columna implicita 'auto' dimensionada al
       contenido (~827 px) y desbordaba a la derecha. Como bloques, cada hijo
       toma el ancho de la pantalla y la barra scrollea dentro de si. */
    .shell { display: block; padding-left: 0; }
    .side {
      position: static; height: auto; width: auto; border-right: none; border-bottom: 1px solid var(--border);
      flex-direction: row; align-items: center; gap: 0.8rem; padding: 0.7rem 0.9rem; overflow-x: auto;
    }
    .side .brand small, .side .foot, .side-state span { display: none; }
    .side nav { flex-direction: row; gap: 0.2rem; }
    .side nav a { border-left: none; border-bottom: 2px solid transparent; white-space: nowrap; }
    .side nav a.active { border-left-color: transparent; border-bottom-color: var(--accent); }
    /* Las tablas (Decisiones, Bloqueos) tienen mas columnas de las que caben:
       scrollean dentro de si, no ensanchan el documento. display:block hace de
       la tabla un bloque con scroll; sus filas conservan el layout de tabla. */
    .wrap table { display: block; overflow-x: auto; }
    /* Los filtros se envuelven en varias lineas en vez de salirse. */
    .toolbar { flex-wrap: wrap; }
  }

  /* --- Topologia --- */
  /* El diagrama es HORIZONTAL (ancho): se apila -diagrama arriba a todo el
     ancho, detalle debajo- para que no quede estrecho al lado. */
  /* minmax(0,1fr), no 1fr: con 1fr el track crece hasta el ancho del diagrama y empuja
     toda la tarjeta (y la barra) fuera de la pantalla; con min 0 la tarjeta se queda del
     ancho disponible y el mapa se desplaza DENTRO de .topo-scroll. */
  .topo-wrap {
    display: grid; grid-template-columns: minmax(0, 1fr); gap: 1rem;
    align-items: start;
  }
  /* Panel de detalle plegado: el diagrama ocupa todo el ancho. */
  .topo-wrap.sin-detalle { grid-template-columns: minmax(0, 1fr); }
  .topo-wrap.sin-detalle .topo-detail { display: none; }
  .topo-canvas {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.6rem 0.7rem 0.8rem; display: flex; flex-direction: column; min-height: 0; min-width: 0;
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
  .topo-scroll { overflow: auto; flex: 1; min-height: 0; min-width: 0; max-width: 100%; max-height: 82vh; overscroll-behavior: contain; cursor: grab; }
  .topo-scroll.arrastrando { cursor: grabbing; }
  .topo-scroll svg { display: block; }
  .card .value small { display: block; font: 400 0.72rem var(--sans); color: var(--text-dim); margin-top: 0.15rem; letter-spacing: 0; }
  .card.txt .value { font-size: 1rem; line-height: 1.3; overflow-wrap: anywhere; }
  .fam-wrap { margin: 0.9rem 0 0.4rem; }
  .fam { display: grid; grid-template-columns: 190px 1fr 120px; gap: 0.8rem; align-items: center; padding: 0.28rem 0; }
  .fam-n { font-size: 0.86rem; color: var(--text); }
  .fam-b { height: 10px; background: var(--surface-2); border-radius: 4px; overflow: hidden; }
  .fam-b i { display: block; height: 100%; border-radius: 0 4px 4px 0; }
  .fam-v { font: 600 0.86rem var(--mono); color: var(--text); font-variant-numeric: tabular-nums; }
  .fam-v small { font-weight: 400; color: var(--text-dim); margin-left: 0.5rem; }
  /* Despliegue: la cadena sensor -> relay -> host, cada eslabon una tarjeta. */
  .desp { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; gap: 0.9rem; align-items: stretch; }
  @media (max-width: 900px) { .desp { grid-template-columns: 1fr; } }
  .desp-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0.9rem 1rem; position: relative; }
  .desp-card.sensor { border-left: 3px solid var(--accent); }
  .desp-card.relay { border-left: 3px solid var(--capa-b); }
  .desp-card.agente { border-left: 3px solid var(--amber); }
  .desp-rol { font: 600 0.66rem var(--mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim); }
  .desp-h { font-size: 1.02rem; font-weight: 700; color: var(--text); margin: 0.1rem 0 0.15rem; }
  .desp-host { font: 600 0.8rem var(--mono); color: var(--accent); }
  .desp-meta { font-size: 0.82rem; color: var(--text-dim); margin: 0.1rem 0 0.6rem; }
  .desp-comp { display: flex; align-items: center; gap: 0.5rem; padding: 0.28rem 0; border-top: 1px solid var(--border); font-size: 0.82rem; }
  .desp-comp .c-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); flex: none; }
  .desp-comp.ok .c-dot { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .desp-comp.bad .c-dot { background: var(--danger); }
  .desp-comp .c-n { color: var(--text); }
  .desp-comp .c-u { margin-left: auto; font: 0.7rem var(--mono); color: var(--text-dim); }
  .desp-nota { font-size: 0.8rem; color: var(--text-dim); margin-top: 0.6rem; font-style: italic; }
  .desp-flecha { display: flex; align-items: center; justify-content: center; color: var(--text-dim); font-size: 1.4rem; }
  @media (max-width: 860px) { .desp-flecha { transform: rotate(90deg); } }
  .apr-graf { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 0.8rem; margin-bottom: 1.1rem; }
  .apr-chart { display: block; width: 100%; height: 170px; }
  #histogram { display: block; width: 100%; height: 240px; }
  .hist-chart { display: block; width: 100%; }
  .apr-chart text, #histogram text, .hist-chart text { font: 600 10px var(--mono); fill: var(--text-dim); }
  .var-fila .vw { min-width: 190px; text-align: right; }
  /* Graficos con eje: las marcas van en HTML junto al SVG. */
  .act-chart { display: grid; grid-template-columns: 40px 1fr; }
  .act-y { position: relative; font: 600 10px var(--mono); color: var(--text-dim); }
  .act-y span { position: absolute; right: 7px; transform: translateY(-50%); white-space: nowrap; }
  .act-x { display: flex; justify-content: space-between; margin-left: 40px; padding-top: 4px;
    font: 600 10px var(--mono); color: var(--text-dim); }
  .act-h .th-sub { text-transform: none; letter-spacing: 0; font-weight: 400; margin-left: 0.4rem; }
  .dec-chart { margin: 0 0 0.8rem; }
  .dec-chart svg { display: block; width: 100%; height: 170px; cursor: crosshair; }
  .dec-chart text { font: 600 10px var(--mono); fill: var(--text-dim); }
  tr.dec-fila { cursor: pointer; }
  tr.dec-det td { background: var(--surface-2); padding: 0.6rem 1rem 0.8rem; }
  .dec-det dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0.45rem 1.2rem; margin: 0; }
  .dec-det dt { font: 600 0.66rem var(--mono); letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-dim); }
  .dec-det dd { margin: 0.1rem 0 0; font: 600 0.82rem var(--mono); color: var(--text); overflow-wrap: anywhere; }
  /* Alertas: el feed de lo que el sistema detecto (modelo o regla). */
  .alertas-resumen { display: flex; align-items: center; gap: 0.7rem; margin: 0.4rem 0 0.2rem; }
  .al-num { font: 800 2.1rem var(--sans); color: var(--text-dim); line-height: 1; }
  .al-num.hay { color: var(--amber); }
  .al-num-t { font-size: 0.86rem; color: var(--text); line-height: 1.3; }
  .al-num-t small { display: block; color: var(--text-dim); font-size: 0.8rem; font-family: var(--mono); }
  .alertas-lista { display: grid; gap: 0.5rem; margin-top: 0.9rem; }
  .al-card { display: grid; grid-template-columns: 70px 1fr auto; align-items: center; gap: 0.8rem;
    background: var(--surface); border: 1px solid var(--border); border-left-width: 3px; border-radius: 10px;
    padding: 0.55rem 0.85rem; }
  /* 17-nov: toda la tarjeta lleva el color de su criticidad, con icono. */
  :root { --sev-block: #e5383b; --sev-limit: #f2c200; }
  html[data-tema="claro"] { --sev-block: #d62828; --sev-limit: #e8b400; }
  .al-card { border-left-width: 5px; }
  .al-card.al-block { border-left-color: var(--sev-block);
    background: color-mix(in srgb, var(--sev-block) 16%, var(--surface)); border-color: color-mix(in srgb, var(--sev-block) 50%, var(--border)); }
  .al-card.al-limit { border-left-color: var(--sev-limit);
    background: color-mix(in srgb, var(--sev-limit) 20%, var(--surface)); border-color: color-mix(in srgb, var(--sev-limit) 60%, var(--border)); }
  .al-card.al-block .al-sev, .al-card.al-limit .al-sev { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; }
  .al-ico { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; color: #fff; }
  .al-block .al-ico { background: var(--sev-block); box-shadow: 0 0 0 4px color-mix(in srgb, var(--sev-block) 28%, transparent); }
  .al-limit .al-ico { background: var(--sev-limit); color: #3a2c00; box-shadow: 0 0 0 4px color-mix(in srgb, var(--sev-limit) 32%, transparent); }
  .al-sev .al-ico + .badge { font-size: 0.66rem; }
  .al-tag svg { vertical-align: -2px; margin-right: 0.25rem; }
  .al-top { display: flex; align-items: baseline; gap: 0.6rem; }
  .al-ip { font: 700 0.92rem var(--mono); color: var(--text); }
  .al-hace { font-size: 0.8rem; color: var(--text-dim); }
  .al-tags { margin: 0.22rem 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .al-tag { font: 600 0.64rem var(--mono); letter-spacing: 0.03em; text-transform: uppercase;
    padding: 0.08rem 0.45rem; border-radius: 999px; }
  .al-tag.regla { background: var(--danger-soft); color: var(--danger); }
  .al-tag.modelo { background: color-mix(in srgb, var(--accent) 20%, transparent); color: var(--accent); }
  .al-motivo { font-size: 0.82rem; color: var(--text-dim); overflow-wrap: anywhere; }
  .al-mini { flex: none; }
  @media (max-width: 640px) { .al-card { grid-template-columns: 58px 1fr; } .al-mini { display: none; } }
  /* Lista blanca: infraestructura conocida, agrupada aparte de las alertas. */
  .lb-caja { margin-top: 1.1rem; border: 1px dashed var(--border); border-radius: 12px; padding: 0.75rem 0.9rem; background: var(--surface); }
  .lb-caja h3 { margin: 0 0 0.25rem; font-size: 0.95rem; }
  .lb-sub { margin: 0 0 0.6rem; font-size: 0.8rem; color: var(--text-dim); }
  .lb-plegable > summary { cursor: pointer; display: flex; align-items: center; gap: 0.45rem; font-weight: 650;
    color: var(--text-dim); font-size: 0.86rem; list-style: none; user-select: none; }
  .lb-plegable > summary::-webkit-details-marker { display: none; }
  .lb-plegable > summary::after { content: '▸'; margin-left: 0.2rem; transition: transform .15s; }
  .lb-plegable[open] > summary::after { transform: rotate(90deg); }
  .lb-plegable > summary:hover { color: var(--accent); }
  .lb-plegable[open] > summary { margin-bottom: 0.4rem; }
  .lb-n { font: 600 0.72rem var(--mono); background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 0 0.45rem; }
  .lb-fila { display: grid; grid-template-columns: 1fr auto; gap: 0.6rem; align-items: center; padding: 0.5rem 0; border-top: 1px solid var(--border); }
  .lb-ip { font-family: var(--mono); font-weight: 600; }
  .lb-nom { color: var(--text-dim); font-size: 0.82rem; margin-left: 0.4rem; }
  .lb-det { font-size: 0.8rem; color: var(--text-dim); margin-top: 0.15rem; overflow-wrap: anywhere; }
  .lb-aviso { color: var(--warn, #d9a441); }
  .lb-tarjetas { display: grid; gap: 0.4rem; margin-top: 0.5rem; grid-column: 1 / -1; }
  @media (max-width: 640px) { .lb-fila { grid-template-columns: 1fr; } }
  /* Pulso: lo que entra y lo que se acumula, con su edad. */
  .pulso { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.7rem; margin: 0.2rem 0 1.3rem; }
  .pulso-t { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0.65rem 0.8rem 0.45rem; min-width: 0; }
  .pulso-l { font: 600 0.68rem var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; gap: 0.4rem; }
  .pulso-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--border); flex: none; }
  .pulso-t.ok .pulso-dot { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .pulso-t.warn .pulso-dot { background: var(--amber); }
  .pulso-t.warn { border-color: color-mix(in srgb, var(--amber) 55%, var(--border)); }
  .pulso-v { font: 700 1.35rem var(--mono); color: var(--text); margin-top: 0.2rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .pulso-v small { font: 600 0.72rem var(--mono); color: var(--text-dim); margin-left: 0.3rem; }
  .pulso-s { font-size: 0.8rem; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pulso-spark { width: 100%; height: 26px; display: block; margin-top: 0.25rem; }
  /* Vista "Validacion": una tabla, no un diagrama. */
  .topo-tabla { display: none; padding: 0.4rem 0.2rem 0.8rem; }
  .topo-tabla table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
  .topo-tabla th { text-align: left; font: 600 0.72rem var(--mono); letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-dim); padding: 0.5rem 0.7rem; border-bottom: 1px solid var(--border); }
  .topo-tabla td { padding: 0.55rem 0.7rem; border-bottom: 1px solid var(--border); vertical-align: top; }
  .topo-tabla td:first-child { font-weight: 700; color: var(--text); }
  .topo-tabla .falta { display: block; color: var(--text-dim); font-size: 0.82rem; }
  .val-est { display: inline-block; font: 700 0.74rem var(--mono); padding: 0.16rem 0.55rem;
    border-radius: 999px; border: 1px solid var(--border); }
  .val-est.c { color: var(--ok); border-color: var(--ok); }
  .val-est.p { color: var(--amber); border-color: var(--amber); }
  .val-est.n { color: var(--text-dim); }

  /* Pantalla completa: el diagrama manda y el detalle se queda al lado. */
  .topo-wrap:fullscreen { background: var(--bg); padding: 1rem; gap: 1rem; height: 100%; grid-template-columns: 1fr; grid-template-rows: minmax(0, 1fr) auto; }
  .topo-wrap:fullscreen .topo-canvas { height: 100%; min-height: 0; }
  /* safe center: centra el diagrama, pero si es más grande que la pantalla cae a la
     esquina para que el borde izquierdo/superior SÍ se alcance al arrastrar. */
  .topo-wrap:fullscreen .topo-scroll { height: auto; max-height: none; display: grid; justify-content: safe center; align-content: safe center; }
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
  .topo-node .ico.ico-blanco, .topo-node.ok .ico.ico-blanco, .topo-node.warn .ico.ico-blanco, .topo-node.bad .ico.ico-blanco,
  .topo-node.acc-limit .ico.ico-blanco, .topo-node.acc-block .ico.ico-blanco, .topo-host .ico.ico-blanco,
  .topo-node.en-flujo .ico.ico-blanco { color: #fff !important; }
  .topo-node .ico-bg { stroke: rgba(255,255,255,0.6); stroke-width: 1.5; }
  .det-con-herr { display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 1.2rem; align-items: start; }
  @media (max-width: 900px) { .det-con-herr { grid-template-columns: 1fr; } }
  .herr-col { display: grid; gap: 0.5rem; position: sticky; top: 0.5rem; }
  .herr { display: flex; align-items: center; gap: 0.65rem; padding: 0.5rem 0.6rem; border: 1px solid var(--border);
    border-radius: 12px; background: var(--surface-2); }
  .herr-ico { width: 46px; height: 46px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none;
    box-shadow: 0 4px 10px -6px rgba(0,0,0,0.5); }
  .herr-t { display: flex; flex-direction: column; line-height: 1.25; }
  .herr-t b { font-size: 0.9rem; color: var(--text); }
  .herr-t small { font-size: 0.74rem; color: var(--text-dim); }
  .herr-capa { font: 700 0.68rem var(--mono); letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--accent); margin: 0.55rem 0 0.1rem; padding-left: 0.1rem; }
  .herr-demo { font: 700 0.6rem var(--mono); letter-spacing: 0.04em; text-transform: uppercase;
    color: #052e2b; background: var(--accent); border-radius: 5px; padding: 0.05rem 0.3rem; vertical-align: 1px; }
  .herr-leyenda { font-size: 0.68rem; color: var(--text-dim); margin-top: 0.6rem; }
  .topo-node.ok .ico { color: var(--ok); }
  .topo-node.warn .ico { color: var(--amber); }
  .topo-node.bad .ico { color: var(--danger); }
  .topo-node .led { stroke: none; }
  /* Nodo de decision: rombo. Texto centrado; fondo algo mas marcado. */
  .topo-node .box.rombo { fill: #15233a; }
  .topo-node .rombo-ttl { fill: var(--text); font: 700 12.5px var(--sans); }
  .topo-node .rombo-sub { fill: var(--text-dim); font: 600 10px var(--mono); }
  /* Artefacto = algo que se escribe en disco, no un proceso. Se distingue con
     trazo discontinuo para que el diagrama no mienta sobre qué es cada caja. */
  .topo-node.artefacto .box { stroke-dasharray: 5 4; fill: #101827; }
  .topo-node.sumidero .box { stroke-dasharray: 2 3; fill: #16111a; }
  .topo-node .tag { fill: var(--text-dim); font: 600 10px var(--mono); letter-spacing: 0.06em; }

  .topo-edge { stroke: var(--border); stroke-width: 1.6; fill: none; }
  .topo-edge.live { stroke: var(--accent); stroke-dasharray: 5 6; animation: flow 1.1s linear infinite; }
  .topo-edge.dim { stroke: color-mix(in srgb, var(--text-dim) 45%, var(--border)); stroke-dasharray: 3 5; }
  .topo-edge.descarte { stroke: var(--danger); opacity: 0.55; stroke-dasharray: 2 4; animation: none; }
  /* Conectores por naturaleza, para las vistas que no dependen del estado vivo. */
  .topo-edge.fijo { stroke: var(--accent); }
  .topo-edge.copia { stroke: var(--amber); stroke-dasharray: 6 4; }
  .topo-edge.previsto { stroke: var(--text-dim); stroke-dasharray: 3 5; opacity: 0.75; }
  .topo-edge.retorno { stroke: var(--text-dim); stroke-dasharray: 5 4; }
  .topo-edge.persona { stroke: var(--ok); }
  .topo-edge.enlace { stroke: color-mix(in srgb, var(--text-dim) 60%, var(--border)); }
  .topo-node.acc-limit .box { stroke: var(--amber); }
  .topo-node.acc-block .box { stroke: var(--danger); }
  .topo-node.acc-limit .ico { color: var(--amber); }
  .topo-node.acc-block .ico { color: var(--danger); }
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
  .topo-pkt { filter: drop-shadow(0 0 4px var(--accent)); }
  .topo-pkt rect { fill: var(--accent); stroke: #fff; stroke-width: 1; }
  .topo-pkt path { fill: none; stroke: #0b1220; stroke-width: 1.6; stroke-linejoin: round; stroke-linecap: round; }
  .topo-pkt .pkt-ficha { stroke: #0b1220; stroke-width: 1.2; opacity: 0.5; }
  @media (prefers-reduced-motion: reduce) { .topo-pkt { display: none; } }
  .topo-cmd { background: #0b1220; border: 1px solid var(--border); border-radius: 7px;
    padding: 0.5rem 0.6rem; margin: 0.5rem 0; font: 11px var(--mono); color: var(--text-dim);
    white-space: pre-wrap; overflow-x: auto; }
  /* Bloque de codigo del nodo: ruta, pseudocodigo y comando para editar. */
  .cod-bloque { margin: 0.9rem 0 0; }
  .cod-sub { font: 600 0.64rem var(--mono); letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--text-dim); margin-top: 0.7rem; }
  .cod-ruta { display: inline-block; margin-top: 0.25rem; font: 0.8rem var(--mono);
    color: var(--accent); background: #0b1220; border: 1px solid var(--border);
    border-radius: 6px; padding: 0.2rem 0.5rem; overflow-wrap: anywhere; }
  /* Perfiles de trafico legitimo, con icono. */
  .perfiles { display: grid; gap: 0.6rem; margin: 0.5rem 0 0.3rem; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 900px) { .perfiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .perfiles .perfil { display: flex !important; flex-direction: column; align-items: flex-start; gap: 0.35rem; padding: 0.75rem;
    border: 1px solid var(--border); border-top: 3px solid var(--pc); border-radius: 12px; background: var(--surface-2); }
  .perfiles .perfil-ico { width: 48px; height: 48px; border-radius: 14px; background: var(--pc); display: inline-flex !important;
    align-items: center; justify-content: center; box-shadow: 0 4px 12px -6px var(--pc); }
  .perfiles .perfil-n { font-size: 0.95rem; }
  .perfiles .perfil-d { font-size: 0.82rem; }
  .perfiles .perfil-ej { grid-column: auto !important; font-size: 0.7rem; }
  .perfil { display: grid; grid-template-columns: 24px auto 1fr; align-items: center; gap: 0.5rem;
    font-size: 0.82rem; }
  .perfil-ico { color: var(--accent); display: inline-flex; }
  .perfil-n { color: var(--text); font-weight: 600; white-space: nowrap; }
  .perfil-n small { color: var(--text-dim); font-weight: 400; font-family: var(--mono); margin-left: 0.3rem; }
  .perfil-d { color: var(--text-dim); }
  .perfil-ej { grid-column: 3; color: var(--text-dim); font-family: var(--mono); font-size: 0.72rem; opacity: 0.92; margin-top: 0.05rem; overflow-wrap: anywhere; }
  /* Archivos del sistema con el host donde corre cada uno (vista Carpetas). */
  .archivos { display: grid; gap: 0.35rem; margin: 0.4rem 0 0.2rem; }
  .arch { display: grid; grid-template-columns: 22px auto auto 1fr; align-items: center; gap: 0.5rem; font-size: 0.82rem; }
  .arch-ico { color: var(--text-dim); display: inline-flex; }
  .arch-n { color: var(--text); font-family: var(--mono); font-size: 0.78rem; white-space: nowrap; }
  .arch-d { color: var(--text-dim); font-size: 0.78rem; }
  .host-badge { display: inline-flex; align-items: center; gap: 0.25rem;
    font: 600 0.6rem var(--mono); letter-spacing: 0.04em; text-transform: uppercase;
    padding: 0.1rem 0.45rem; border-radius: 999px; white-space: nowrap; }
  .host-sensor { background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); }
  .host-servidor { background: var(--amber-soft); color: var(--amber); }
  .host-bastion { background: color-mix(in srgb, var(--capa-b) 26%, transparent); color: var(--capa-b); }
  .host-leyenda { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.6rem 0 0; }
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
  .topo-flujo .gar { font-size: 0.82rem; color: var(--text-dim); margin-top: 0.1rem; }
  .topo-flujo .flecha { color: var(--text-dim); margin: 0.1rem 0 0.1rem 0.5rem; font-size: 0.9rem; }

  /* Regla de decision del modelo: recta de score con el umbral y los scores
     reales recientes, para ver DONDE y COMO se decide ALERT vs PERMIT. */
  .modelo-dec { margin: 0.8rem 0 0.2rem; }
  .modelo-dec h4 { font: 600 0.72rem var(--sans); letter-spacing: 0.05em;
    text-transform: uppercase; color: var(--text-dim); margin: 0 0 0.35rem; }
  .modelo-dec .cap { font-size: 0.82rem; color: var(--text-dim); margin-top: 0.35rem; }
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
  .stamp { font-family: var(--mono); font-size: 0.82rem; color: var(--text-dim); }

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
  .toolbar-hint { font-size: 0.82rem; color: var(--text-dim); margin: 0.4rem 0 0; min-height: 1em; }
  .lede-small { font-size: 0.86rem; color: var(--text-dim); margin: -0.3rem 0 0.8rem; }

  /* Cabecera de sesion: quien eres, en que modo y como salir. */
  .sesion { display: flex; align-items: center; gap: 0.6rem; margin-left: auto; }
  .sesion form { margin: 0; }
  .quien { font-size: 0.82rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }
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
  .kpi .k-sub { font: 0.8rem var(--sans); color: var(--text-dim); margin-top: 0.1rem; }
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
  .umb-box { margin-top: 1.5rem; }
  .umb-h { font-size: 1rem; margin: 0 0 0.45rem; }
  .umb-tabla { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin: 0.65rem 0; }
  .umb-tabla table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .umb-tabla th { text-align: left; font-family: var(--mono); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); background: var(--surface-2); padding: 0.5rem 0.7rem; }
  .umb-tabla td { padding: 0.55rem 0.7rem; border-top: 1px solid var(--border); vertical-align: top; }
  .umb-tabla td.umb-r { font-family: var(--mono); white-space: nowrap; font-weight: 700; }
  .esc-cmd { font-family: var(--mono); font-size: 0.74rem; background: var(--surface-2); padding: 0.05rem 0.32rem; border-radius: 4px; }
  .esc-refs { margin: 0.5rem 0 0; padding-left: 1.1rem; font-size: 0.84rem; line-height: 1.5; }
  .esc-refs li { margin: 0.22rem 0; }
  .pipe { display: flex; align-items: stretch; gap: 0.25rem; margin: 0.9rem 0; }
  .pipe-box { flex: 1 1 0; min-width: 0; border: 1px solid var(--border); border-radius: 10px; background: var(--surface-2); padding: 0.5rem 0.6rem; }
  .pipe-box.hl { background: var(--ok-soft); border-color: var(--ok); }
  .pipe-box .pl { display: block; font-family: var(--mono); font-size: 0.6rem; letter-spacing: 0.04em; color: var(--text-dim); text-transform: uppercase; }
  .pipe-box b { display: block; font-size: 0.86rem; margin: 0.1rem 0 0.12rem; }
  .pipe-box small { color: var(--text-dim); font-size: 0.7rem; line-height: 1.25; }
  .pipe-ar { align-self: center; color: var(--text-dim); font-size: 1.1rem; flex: 0 0 auto; }
  .esc-code { background: #0B1220; color: #C7D4E5; border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 0.95rem; font-family: var(--mono); font-size: 0.76rem; line-height: 1.55; overflow-x: auto; white-space: pre; margin: 0.5rem 0; }
  .esc-code .c { color: #7C8BAD; }
  .anat { border: 1px solid var(--border); border-radius: 10px; padding: 0.6rem 0.8rem; margin: 0.55rem 0; }
  .anat .ac { font-family: var(--mono); font-size: 0.78rem; display: block; margin-bottom: 0.4rem; word-break: break-all; }
  .anat ul { margin: 0.15rem 0 0.4rem; padding-left: 1.15rem; font-size: 0.8rem; line-height: 1.45; }
  .anat li { margin: 0.12rem 0; }
  .anat .vd { font-size: 0.82rem; line-height: 1.4; }
  .anat .bad { color: var(--danger); font-weight: 700; }
  .anat .good { color: var(--ok); font-weight: 700; }
  .ojo { background: none; border: 1px solid var(--border); border-radius: 6px; color: var(--text-dim); cursor: pointer; padding: 0.08rem 0.28rem; margin-right: 0.4rem; vertical-align: middle; display: inline-flex; align-items: center; }
  .ojo:hover { color: var(--ok); border-color: var(--ok); }
  .pmodal { position: fixed; inset: 0; background: rgba(6,11,22,0.62); display: none; align-items: center; justify-content: center; z-index: 9999; padding: 1rem; }
  .pmodal.open { display: flex; }
  .pmodal-box { background: var(--surface-2); border: 1px solid var(--border); border-radius: 14px; max-width: 640px; width: 100%; max-height: 85vh; overflow: auto; padding: 1.2rem 1.4rem; box-shadow: 0 18px 50px rgba(0,0,0,0.35); }
  .pmodal-h { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
  .pmodal-h h3 { margin: 0; font-size: 1.05rem; }
  .pmodal-x { background: none; border: none; color: var(--text-dim); font-size: 1.4rem; cursor: pointer; line-height: 1; }
  .pmodal dt { font-family: var(--mono); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); margin-top: 0.75rem; }
  .pmodal dd { margin: 0.18rem 0 0; font-size: 0.86rem; }
  .var-grupo { font-size: 0.72rem; letter-spacing: .07em; text-transform: uppercase;
    color: var(--text-dim); background: var(--surface-2); padding: 0.4rem 0.8rem;
    border-bottom: 1px solid var(--border); box-shadow: inset 3px 0 0 var(--cc-color, var(--border)); }
  .var-grupo b { color: var(--cc-color, var(--accent)); font-weight: 700; }
  .var-fila .vs { display: flex; align-items: center; gap: 0.55rem; justify-content: flex-end;
    font: 600 0.8rem var(--mono); font-variant-numeric: tabular-nums; color: var(--text); min-width: 170px; }
  .var-fila .vs svg { width: 96px; height: 22px; flex: none; }
  .var-fila .vs.fuera { color: var(--amber); }
  .var-fila .vs .sin { color: var(--text-dim); font-weight: 400; }
  .var-serie { display: block; width: 100%; height: 76px; margin: 0.2rem 0 0.5rem;
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
  .var-fila {
    display: grid; grid-template-columns: 1fr auto auto auto; gap: 0.6rem; align-items: center;
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
  /* Aprendizaje supervisado: una tarjeta por defensa, y debajo sus tablas. */
  .apr-def { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.7rem; margin: 0.6rem 0 1rem; }
  .apr-def .card .value { font-size: 1.05rem; }
  .apr-def .sub { font-size: 0.76rem; color: var(--text-dim); margin-top: 0.3rem; line-height: 1.4; }
  .apr-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
  .apr-h { font-size: 0.86rem; margin: 1rem 0 0.45rem; color: var(--text); font-weight: 600; }
  .apr-h .th-sub { color: var(--text-dim); font-weight: 400; font-size: 0.76rem; margin-left: 0.4rem; }
  .apr-cand { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem 1rem; position: relative; }
  .apr-cand table { font-size: 0.8rem; margin: 0.5rem 0; }
  .apr-cand td, .apr-cand th { padding: 0.3rem 0.5rem; }
  .apr-cand td.num { overflow-wrap: anywhere; }
  .apr-cols > div { min-width: 0; }
  .apr-cand .topo-cmd { padding-right: 4.2rem; }
  .badge.v-ok { background: var(--ok-soft); color: var(--ok); }
  .badge.v-no { background: var(--danger-soft); color: var(--danger); }
  .badge.v-inc { background: var(--amber-soft); color: var(--amber); }
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
  /* Franja de la cadena v2 (16-nov): fichas compactas en la columna de contenido. */
  .cv2-franja { margin: 0.5rem 0 0.9rem; font-size: 0.78rem; color: var(--text-dim); }
  .cv2-fichas { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .cv2-ficha { border: 1px solid var(--border); border-radius: 999px; padding: 0.15rem 0.6rem; background: var(--surface); white-space: nowrap; }
  .cv2-ficha.aviso { border-color: #b8892f; color: #e3b860; }
  .cv2-ficha.bien { border-color: #2f7d5b; }
  .cv2-ficha.mal { border-color: #a5463e; color: #f08a80; }
  .cv2-inc { margin-top: 0.35rem; }
  @media (max-width: 640px) { .cv2-ficha { white-space: normal; } }
  .rg-abrir.sin-esc { right: 110px; }
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
  td { padding: 0.5rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: middle; font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  tr.row-alert td:first-child { box-shadow: inset 3px 0 0 var(--danger); }
  .ip, .num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
  /* Cifras de recuento puro (Paquetes, Ventanas, Acciones, comparacion) a la
     derecha, con su cabecera, para que los numeros se lean alineados por
     unidades. Las columnas de tiempo (Hora, Inicio, Desde) siguen a la
     izquierda: comparten clase .num solo por la tipografia tabular. */
  td.num.r, th.r { text-align: right; }
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

  /* Filas por accion: el analista ve primero lo que se corto o se degrado. */
  tr.row-block td:first-child { box-shadow: inset 4px 0 0 var(--danger); }
  tr.row-limit td:first-child { box-shadow: inset 4px 0 0 var(--amber); }
  tr.row-nueva td { animation: fila-nueva 6s ease-out; }
  @keyframes fila-nueva { from { background: rgba(94,234,212,0.16); } to { background: transparent; } }
  .badge.acc-block, .badge.acc-limit { font-size: 0.8rem; padding: 0.22rem 0.65rem; letter-spacing: 0.03em; }
  .hace { display: block; font-size: 0.78rem; color: var(--text-dim); }
  .modelo-celda { display: inline-flex; align-items: center; gap: 0.45rem; font-family: var(--mono); font-size: 0.78rem; }
  .modelo-celda .m-alert { color: var(--danger); font-weight: 600; }
  .modelo-celda .m-permit { color: var(--text-dim); }

  /* Acciones vigentes: cuenta atras visible y barra de lo que queda. */
  .vig-barra { height: 5px; border-radius: 3px; background: var(--border); overflow: hidden; margin-top: 0.3rem; min-width: 90px; }
  .vig-barra i { display: block; height: 100%; }
  .vig-fuente { font-size: 0.74rem; color: var(--text-dim); font-family: var(--mono); }
  .sec-sub { color: var(--text-dim); font-size: 0.82rem; margin: -0.3rem 0 0.7rem; }
  .cmp-lede { font-size: 15px; margin: 0 0 1rem; max-width: 72rem; }
  .cmp-como { list-style: none; padding: 0; margin: 0 0 0.6rem; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
  .cmp-como li { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 12px 10px; display: flex; flex-direction: column; gap: 4px; position: relative; }
  .cmp-como li .n { width: 24px; height: 24px; border-radius: 50%; background: #10283a; color: var(--accent); display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 12px; }
  .cmp-como li b { font-size: 14px; }
  .cmp-como li small { color: var(--text-dim); font-size: 12.5px; line-height: 1.4; }
  .cmp-como li code { margin-top: auto; font-family: var(--mono); font-size: 11px; color: #9fd0ff; background: #0b1322; border: 1px solid #1d2a44; border-radius: 6px; padding: 4px 6px; word-break: break-word; }
  .cmp-run { color: var(--text-dim); font-size: 13px; margin: 0 0 1.2rem; }
  .cmp-run code { font-family: var(--mono); color: #ffd58a; }
  .cmp-h { font-size: 15px; margin: 0 0 0.6rem; }
  .cmp-vivo { display: grid; grid-template-columns: repeat(auto-fill, minmax(520px, 1fr)); gap: 12px; margin-bottom: 1rem; }
  .cmp-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
  .cmp-card header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-2); }
  .cmp-card header b { font-size: 14px; }
  .cmp-card header .ip { font-family: var(--mono); color: var(--text-dim); font-size: 12.5px; }
  .cmp-card header .cuando { margin-left: auto; font-family: var(--mono); color: var(--text-dim); font-size: 12px; }
  .cmp-dos { display: grid; grid-template-columns: 1fr 1fr; }
  .cmp-lado { padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
  .cmp-lado + .cmp-lado { border-left: 1px solid var(--border); }
  .cmp-lado .quien { font-size: 11.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--text-dim); font-weight: 600; }
  .cmp-lado .cifra { font-family: var(--mono); font-size: 26px; font-weight: 700; line-height: 1.1; }
  .cmp-lado .cifra small { font-size: 12px; font-weight: 500; color: var(--text-dim); margin-left: 6px; font-family: var(--sans); }
  .cmp-lado ul { margin: 0; padding-left: 1rem; font-size: 12.5px; color: var(--text-dim); }
  .cmp-lado ul li b { color: var(--text); font-family: var(--mono); font-weight: 600; margin-right: 4px; }
  .cmp-lado .ev { margin-top: auto; font-family: var(--mono); font-size: 11px; color: #7f90b3; }
  .cmp-card footer { padding: 8px 14px; border-top: 1px solid var(--border); font-size: 13px; }
  .cmp-card footer.bien { background: rgba(74,222,128,.07); }
  .cmp-card footer.neutro { background: rgba(148,163,196,.06); }
  .cmp-bateria { margin: 0.4rem 0 0.8rem; }
  @media (max-width: 1100px) { .cmp-como { grid-template-columns: 1fr 1fr; } .cmp-vivo { grid-template-columns: 1fr; } }
  .cmp-notas { margin: 0.5rem 0 0; padding-left: 1.1rem; color: var(--text-dim); font-size: 0.8rem; line-height: 1.5; }
  td.cmp-bien { color: var(--ok); } td.cmp-mal { color: var(--danger); } td.cmp-nm { color: var(--text-dim); font-style: italic; }
  tr.cmp-total td { font-weight: 600; border-top: 2px solid var(--border); }

  /* Actividad: cifras por accion y las IPs que mas actuaron. */
  .act-cols { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1rem; margin-top: 0.9rem; }
  @media (max-width: 900px) { .act-cols { grid-template-columns: 1fr; } }
  .act-h { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); margin: 0 0 0.45rem; font-weight: 600; }

  /* --- Escenario en vivo: un ataque por capa seguido de punta a punta --- */
  .esc-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 0.6rem; margin: 0.8rem 0 1rem; }
  .esc-card { text-align: left; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.7rem 0.8rem; color: var(--text); cursor: pointer; display: flex; flex-direction: column; gap: 0.15rem; font: inherit; }
  .esc-card:hover { border-color: var(--accent); }
  .esc-card.sel { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
  .esc-card b { font-size: 14px; }
  .esc-card small { color: var(--text-dim); font-size: 12px; }
  .esc-capa { font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); }
  .esc-card.fp .esc-capa { color: var(--amber); }
  .esc-det { display: grid; grid-template-columns: 1fr; gap: 0.8rem; }
  .prep { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; background: var(--surface);
          border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 12px;
          padding: 12px 14px; margin: 0 0 1rem; }
  .btn-prep { background: var(--accent); color: #04131a; border: 0; border-radius: 9px; padding: 9px 16px;
              font-weight: 700; font-size: 14px; cursor: pointer; }
  .btn-prep:disabled { opacity: .55; cursor: progress; }
  .prep-txt { color: var(--text-dim); font-size: 13px; flex: 1 1 320px; }
  .prep-txt b { color: var(--text); }
  .prep-lista { list-style: none; margin: 0; padding: 0; flex-basis: 100%; display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 6px 14px; }
  .prep-lista:empty { display: none; }
  .prep-lista li { font-size: 13px; display: flex; gap: 8px; align-items: baseline; }
  .prep-lista li .ic { font-family: var(--mono); font-weight: 700; width: 1.1em; }
  .prep-lista li.ok .ic { color: #4ade80; }
  .prep-lista li.esp .ic { color: #fbbf24; }
  .prep-lista li.mal .ic { color: #f87171; }
  .prep-lista li small { color: var(--text-dim); font-family: var(--mono); font-size: 11.5px; }
  .prep.listo { border-left-color: #4ade80; }
  @media (max-width: 900px) { .esc-det { grid-template-columns: 1fr; } }
  .esc-box { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem 1rem; }
  .esc-box h3 { margin: 0 0 0.4rem; font-size: 14px; }
  .esc-box p { margin: 0.3rem 0; font-size: 13.5px; }
  .esc-box .k { color: var(--text-dim); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
  .esc-cmd { display: flex; gap: 0.5rem; align-items: flex-start; margin: 0.4rem 0; }
  .esc-cmd code { flex: 1; white-space: pre-wrap; word-break: break-all; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.45rem 0.6rem; font-family: var(--mono); font-size: 12.5px; }
  .esc-guion ol { margin: 0.2rem 0 0 1.1rem; padding: 0; font-size: 13.5px; }
  .esc-guion li { margin: 0.3rem 0; }
  .esc-ctl { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin: 1rem 0 0.6rem; }
  .esc-ctl label { font-size: 13px; color: var(--text-dim); display: flex; gap: 0.4rem; align-items: center; }
  .esc-reloj { font-family: var(--mono); font-size: 22px; color: var(--accent); margin-left: auto; }
  .esc-estado { font-size: 13px; color: var(--text-dim); }
  .esc-pasos { list-style: none; margin: 0.4rem 0 1rem; padding: 0; display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.5rem; }
  @media (max-width: 1100px) { .esc-pasos { grid-template-columns: 1fr; } }
  .esc-paso { background: var(--surface-2); border: 1px solid var(--border); border-top: 4px solid var(--border);
    border-radius: 10px; padding: 0.6rem 0.7rem; font-size: 13px; min-height: 120px; }
  .esc-paso h4 { margin: 0 0 0.3rem; font-size: 13.5px; display: flex; justify-content: space-between; gap: 0.4rem; }
  .esc-paso .n { font-family: var(--mono); color: var(--text-dim); font-size: 11px; }
  .esc-paso .t { font-family: var(--mono); color: var(--text-dim); font-size: 12px; display: block; margin-top: 0.3rem; }
  .esc-paso .dnd { display: block; margin-top: 0.35rem; font-size: 11.5px; color: var(--text-dim); }
  .esc-paso .esc-hist, .esc-hist { font-size: 11.5px; color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .esc-x { font-family: var(--mono); font-size: 0.78rem; color: var(--text-dim); margin-left: 0.35rem; }
  .esc-paso.ok { border-top-color: var(--ok); }
  .esc-paso.espera { border-top-color: var(--amber); animation: escPulso 1.6s ease-in-out infinite; }
  .esc-paso.ext { border-top-color: var(--accent); border-style: dashed; }
  .esc-paso.inactivo { opacity: 0.6; }
  @keyframes escPulso { 50% { box-shadow: 0 0 0 3px var(--amber-soft); } }
  .esc-filas { display: flex; flex-direction: column; gap: 0.3rem; max-height: 360px; overflow: auto; }
  .esc-fila { display: grid; grid-template-columns: 78px 72px 74px 1fr; gap: 0.5rem; align-items: center; font-size: 12.5px;
    padding: 0.3rem 0.5rem; border-radius: 6px; background: var(--surface-2); }
  .esc-fila .hora { font-family: var(--mono); color: var(--text-dim); }
  .esc-fila.nueva { animation: escNueva 2s ease-out; }
  @keyframes escNueva { from { background: #134e4a; } }
  .tag-marg { font-size: 10.5px; color: var(--text-dim); border: 1px solid var(--border); border-radius: 4px; padding: 0 0.3rem; margin-left: 0.3rem; }
  @media (prefers-reduced-motion: reduce) { .esc-paso.espera, .esc-fila.nueva { animation: none; } }
  /* Alertas flotantes: una por IP y accion, apiladas arriba a la derecha. */
  .toasts { position: fixed; bottom: 76px; right: 16px; z-index: 400; display: flex; flex-direction: column; gap: 10px; width: min(380px, calc(100vw - 32px)); pointer-events: none; }
  .toast { pointer-events: auto; background: var(--surface-2); border: 1px solid var(--border); border-left: 5px solid var(--amber);
    border-radius: 10px; padding: 0.75rem 0.9rem 0.7rem; box-shadow: 0 10px 30px rgba(0,0,0,0.45); cursor: pointer;
    animation: toast-in .25s ease-out; }
  .toast.block { border-left-color: var(--sev-block); border-color: color-mix(in srgb, var(--sev-block) 55%, var(--border));
    background: color-mix(in srgb, var(--sev-block) 16%, var(--surface)); }
  .toast.limit { border-left-color: var(--sev-limit); border-color: color-mix(in srgb, var(--sev-limit) 65%, var(--border));
    background: color-mix(in srgb, var(--sev-limit) 22%, var(--surface)); }
  .toast .t-ico { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; flex: none; }
  .toast.block .t-ico { background: var(--sev-block); color: #fff; box-shadow: 0 0 0 4px color-mix(in srgb, var(--sev-block) 28%, transparent); }
  .toast.limit .t-ico { background: var(--sev-limit); color: #3a2c00; box-shadow: 0 0 0 4px color-mix(in srgb, var(--sev-limit) 32%, transparent); }
  html[data-tema="claro"] .toast { box-shadow: 0 10px 28px rgba(18,49,95,.22); }
  /* 17-nov: aviso como alarma -fondo intenso que palpita y anillo en el icono-. */
  .toast.block { background: var(--sev-block); border-color: var(--sev-block); color: #fff;
    animation: toast-in .25s ease-out, alarmaBlock 1.1s ease-in-out .25s infinite; }
  .toast.limit { background: var(--sev-limit); border-color: var(--sev-limit); color: #2b2100;
    animation: toast-in .25s ease-out, alarmaLimit 1.4s ease-in-out .25s infinite; }
  .toast.block .t-ip, .toast.block .t-mot { color: #fff; }
  .toast.block .t-meta, .toast.block .t-x { color: rgba(255,255,255,.85); }
  .toast.limit .t-ip, .toast.limit .t-mot { color: #2b2100; }
  .toast.limit .t-meta, .toast.limit .t-x { color: rgba(43,33,0,.75); }
  .toast.block .t-ico { background: #fff; color: var(--sev-block); animation: alarmaIco 1.1s ease-out infinite; }
  .toast.limit .t-ico { background: #2b2100; color: var(--sev-limit); animation: alarmaIco 1.4s ease-out infinite; }
  .toast .badge { background: rgba(255,255,255,.22) !important; color: inherit !important; border: 1px solid rgba(255,255,255,.45); }
  .toast.limit .badge { background: rgba(43,33,0,.12) !important; border-color: rgba(43,33,0,.3); }
  .toast .t-alarma { font: 800 0.68rem var(--mono); letter-spacing: 0.14em; text-transform: uppercase; opacity: .9; }
  @keyframes alarmaBlock { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--sev-block) 70%, transparent), 0 10px 28px rgba(0,0,0,.3); filter: brightness(1); }
    50% { box-shadow: 0 0 0 12px color-mix(in srgb, var(--sev-block) 0%, transparent), 0 10px 28px rgba(0,0,0,.3); filter: brightness(1.18); } }
  @keyframes alarmaLimit { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--sev-limit) 70%, transparent), 0 10px 28px rgba(0,0,0,.25); filter: brightness(1); }
    50% { box-shadow: 0 0 0 10px color-mix(in srgb, var(--sev-limit) 0%, transparent), 0 10px 28px rgba(0,0,0,.25); filter: brightness(1.08); } }
  @keyframes alarmaIco { 0% { box-shadow: 0 0 0 0 rgba(255,255,255,.75); } 100% { box-shadow: 0 0 0 10px rgba(255,255,255,0); } }
  @media (prefers-reduced-motion: reduce) { .toast.block, .toast.limit, .toast .t-ico { animation: none; } }
  /* LIMIT en amarillo en todo el panel (gráficos, leyendas, insignias). */
  :root { --amber: #f2c200; }
  :root[data-tema="claro"] { --amber: #d9a800; --amber-soft: #fff3c4; }
  html[data-tema="claro"] .badge.acc-limit { background: #ffe066; color: #4d3900; }
  html[data-tema="claro"] .card.amber .value, html[data-tema="claro"] .wid.amber .w-val { color: #a07c00; }
  /* Mapa: vista oculta (ojo tachado) y conmutador Lab / Operativa. */
  #topoVista .vista-oculta { display: inline-flex; align-items: center; justify-content: center; opacity: 0.55; cursor: not-allowed; }
  #topoVista .vista-oculta:hover { background: none; }
  .topo-modo button { white-space: nowrap; }
  .topo-lede { max-width: 980px; }
  /* Ojo del recorrido: círculo que despliega su texto al pasar el ratón. */
  .rg-abrir { display: inline-flex; align-items: center; gap: 0; padding: 9px !important; border-radius: 999px; transition: gap .2s, padding .2s; }
  .rg-abrir .rg-txt { max-width: 0; overflow: hidden; white-space: nowrap; transition: max-width .25s ease; }
  .rg-abrir:hover, .rg-abrir:focus-visible { gap: 8px; padding: 9px 14px !important; }
  .rg-abrir:hover .rg-txt, .rg-abrir:focus-visible .rg-txt { max-width: 260px; }
  .rg-abrir.sin-esc { right: 150px; }
  /* Escoba de «Dejar limpio». */
  .btn-escoba { display: inline-flex; align-items: center; gap: 0.45rem; }
  .btn-escoba-sec { display: inline-flex; align-items: center; padding: 0.35rem 0.55rem; }
  .btn-escoba-sec:hover { color: var(--accent); border-color: var(--accent); }
  .btn-escoba[hidden], .btn-escoba-sec[hidden] { display: none; }
  .al-epi { font: 600 0.72rem var(--mono); color: var(--text-dim); background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 999px; padding: 0.05rem 0.5rem; }
  .btn-link { background: none; border: 0; color: var(--accent); font: inherit; font-weight: 600; cursor: pointer; padding: 0 0.2rem; text-decoration: underline; }
  /* Widgets con icono (Actividad, Respuestas, Scores). */
  .wids { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.8rem; margin-bottom: 1rem; }
  .wid { position: relative; display: flex; gap: 0.8rem; align-items: center; background: var(--surface);
    border: 1px solid var(--border); border-radius: 14px; padding: 0.9rem 1rem; overflow: hidden;
    box-shadow: 0 1px 2px rgba(18,49,95,.06), 0 6px 18px rgba(18,49,95,.06); }
  .wid::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--w-c, var(--accent)); }
  .wid .w-ico { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; flex: none;
    background: color-mix(in srgb, var(--w-c, var(--accent)) 15%, transparent); color: var(--w-c, var(--accent)); }
  .wid .w-lab { font: 600 0.7rem var(--sans); letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-dim); }
  .wid .w-val { font: 800 1.75rem var(--sans); color: var(--text); font-variant-numeric: tabular-nums; line-height: 1.15; }
  .wid .w-sub { font-size: 0.74rem; color: var(--text-dim); }
  .wid.bad { --w-c: var(--sev-block); } .wid.bad .w-val { color: var(--sev-block); }
  .wid.amber { --w-c: var(--amber); } .wid.amber .w-val { color: var(--amber); }
  .wid.ok { --w-c: var(--ok); }
  .wid.navy { --w-c: #3b6fb6; }
  /* Gráfico de Decisiones ampliado. */
  .dec-chart { position: relative; }
  .dec-max-btn { position: absolute; top: 8px; right: 10px; z-index: 2; }
  .dec-chart.dec-max { position: fixed; inset: 3vh 3vw; z-index: 600; margin: 0; background: var(--surface);
    border: 1px solid var(--border); border-radius: 14px; padding: 2.6rem 1.2rem 1rem; box-shadow: 0 30px 80px rgba(0,0,0,.45); }
  .dec-chart.dec-max svg { height: calc(94vh - 9rem); }
  .dec-chart.dec-max text { font-size: 12px; }
  .dec-fondo { position: fixed; inset: 0; z-index: 590; background: rgba(8,20,40,.55); backdrop-filter: blur(2px); }
  .dec-zoom-info { position: absolute; top: 12px; left: 1.2rem; font-size: 0.78rem; color: var(--text-dim); }
  /* Respuestas: filas teñidas por acción y bloque de ayuda plegable. */
  #blocked tr:has(.acc-block) td, #histTabla tr:has(.acc-block) td { background: color-mix(in srgb, var(--sev-block) 9%, transparent); }
  #blocked tr:has(.acc-limit) td, #histTabla tr:has(.acc-limit) td { background: color-mix(in srgb, var(--sev-limit) 14%, transparent); }
  #blocked tr:has(.acc-block) td:first-child, #histTabla tr:has(.acc-block) td:first-child { box-shadow: inset 4px 0 0 var(--sev-block); }
  #blocked tr:has(.acc-limit) td:first-child, #histTabla tr:has(.acc-limit) td:first-child { box-shadow: inset 4px 0 0 var(--sev-limit); }
  details.ayuda { margin: 0.2rem 0 0.9rem; font-size: 0.82rem; color: var(--text-dim); }
  details.ayuda summary { cursor: pointer; color: var(--accent); font-weight: 600; list-style: none; display: inline-flex; gap: 0.35rem; align-items: center; }
  details.ayuda summary::-webkit-details-marker { display: none; }
  details.ayuda[open] summary { margin-bottom: 0.4rem; }
  .toast .t-cab { display: flex; align-items: center; gap: 0.5rem; }
  .toast .t-ip { font-family: var(--mono); font-weight: 700; color: var(--text); font-size: 0.95rem; }
  .toast .t-x { margin-left: auto; background: none; border: none; color: var(--text-dim); font-size: 1.1rem; cursor: pointer; line-height: 1; }
  .toast .t-mot { margin-top: 0.35rem; font-size: 0.84rem; color: var(--text); line-height: 1.35; }
  .toast .t-meta { margin-top: 0.3rem; font-size: 0.72rem; color: var(--text-dim); font-family: var(--mono); }
  @keyframes toast-in { from { transform: translateX(30px); opacity: 0; } to { transform: none; opacity: 1; } }
  .btn-avisos { background: var(--surface); border: 1px solid var(--border); color: var(--text-dim); border-radius: 7px; padding: 0.3rem 0.6rem; font: 0.78rem var(--sans); cursor: pointer; }
  .btn-avisos[data-on="1"] { color: var(--accent); border-color: var(--accent); }

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
  .vivo-tabla .sub { color: var(--text-dim); font-size: 0.78rem; }
  .vf { display: inline-block; margin: 0 0.25rem 0.25rem 0; padding: 0.1rem 0.4rem; border-radius: 6px;
    background: var(--surface-2); border: 1px solid var(--border); font-family: var(--mono); font-size: 0.72rem; white-space: nowrap; }
  .vf b { color: var(--accent); font-weight: 600; }
  .vf .ap { color: var(--text-dim); }
  .vf.l2 { border-style: dashed; }
  .vf.l2 b { color: var(--capa-c); }
  .vf.cnt b { color: var(--amber); }
  .vf .par { color: var(--amber); }
  .vivo-tabla .matriz td:nth-child(2) { min-width: 14rem; }
  .vivo-tabla .matriz td.m { white-space: normal; }
  .vivo-tabla .heur { color: var(--amber); font-family: var(--mono); font-size: 0.74rem; }

  /* Captura en vivo: medidor de ingesta y lista tipo Wireshark. */
  .vivo-medidor { display: grid; grid-template-columns: minmax(12rem, 1.2fr) repeat(3, minmax(10rem, 1fr));
    gap: 0.6rem; margin: 0.4rem 0 0.8rem; }
  @media (max-width: 900px) { .vivo-medidor { grid-template-columns: 1fr 1fr; } }
  .vivo-medidor > div { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.55rem 0.7rem; min-width: 0; }
  .vm-estado { display: flex; flex-direction: column; justify-content: center; gap: 0.15rem; }
  .vm-estado b { font-size: 0.95rem; }
  .vm-estado span:last-child { color: var(--text-dim); font-size: 0.74rem; }
  .vm-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--text-dim); display: inline-block; }
  .vm-dot.ok { background: var(--ok); box-shadow: 0 0 0 0 var(--ok); animation: vmPulso 1.4s infinite; }
  .vm-dot.lento { background: var(--amber); }
  .vm-dot.parado { background: var(--danger); }
  @keyframes vmPulso { 0% { box-shadow: 0 0 0 0 rgba(74,222,128,.6); } 100% { box-shadow: 0 0 0 9px rgba(74,222,128,0); } }
  .vm-cab { color: var(--text-dim); font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em; }
  .vm-num { font-family: var(--mono); font-size: 0.8rem; color: var(--text-dim); }
  .vm-num b { font-size: 1.25rem; color: var(--text); }
  .vm-spark { width: 100%; height: 28px; display: block; }
  .vm-spark polyline { fill: none; stroke: var(--accent); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
  .vm-spark polygon { fill: rgba(94,234,212,.12); stroke: none; }
  .vm-pie { font-family: var(--mono); font-size: 0.7rem; color: var(--text-dim); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .vm-pie .crece { color: var(--ok); }
  .vivo-tabla.ws { max-height: 460px; }
  .vivo-tabla.ws table { font-size: 0.72rem; }
  .vivo-tabla.ws .fl { max-width: 12.5rem; overflow: hidden; text-overflow: ellipsis; }
  .vivo-tabla.ws td { padding: 0.2rem 0.45rem; font-family: var(--mono); white-space: nowrap; }
  .vivo-tabla.ws th { padding-left: 0.45rem; padding-right: 0.45rem; }
  .vivo-tabla.ws td.txt { font-family: var(--sans); white-space: normal; }
  .vivo-tabla.ws tbody tr { cursor: pointer; border-left: 3px solid transparent; }
  .vivo-tabla.ws tbody tr.sel { outline: 1px solid var(--accent); outline-offset: -1px; }
  .vivo-tabla.ws .fl { display: block; line-height: 1.35; }
  .vivo-tabla.ws .fl b { color: var(--accent); font-weight: 600; }
  .vivo-tabla.ws .fl.l2 b { color: var(--capa-c); }
  .vivo-tabla.ws .fl.cnt b { color: var(--amber); }
  .vivo-tabla.ws td.txt { max-width: 12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .vivo-tabla.ws .mas { margin-left: 0.35rem; padding: 0 0.3rem; border-radius: 5px; background: var(--surface-2);
    border: 1px solid var(--border); color: var(--text-dim); font-size: 0.68rem; }
  .vivo-tabla.ws .pend { color: var(--text-dim); }
  .vivo-tabla.ws .conf { color: var(--ok); }
  .vivo-tabla.ws .prov { color: var(--text-dim); font-style: italic; }
  /* Reglas de color al estilo de Wireshark, en tinte para el tema oscuro. */
  tr.c-tcp  { background: rgba(141,129,255,.10); border-left-color: rgba(141,129,255,.7) !important; }
  tr.c-syn  { background: rgba(160,160,160,.16); border-left-color: #a0a0a0 !important; }
  tr.c-rst  { background: rgba(248,113,113,.18); border-left-color: var(--danger) !important; }
  tr.c-udp  { background: rgba(96,165,250,.10); border-left-color: rgba(96,165,250,.7) !important; }
  tr.c-icmp { background: rgba(244,114,182,.13); border-left-color: var(--capa-d) !important; }
  tr.c-arp  { background: rgba(240,180,41,.12); border-left-color: var(--amber) !important; }
  tr.c-http { background: rgba(74,222,128,.12); border-left-color: var(--ok) !important; }
  tr.c-dns  { background: rgba(96,165,250,.13); border-left-color: var(--capa-b) !important; }
  tr.c-tls  { background: rgba(192,132,252,.12); border-left-color: var(--capa-c) !important; }
  tr.c-alert { background: rgba(248,113,113,.22); border-left-color: var(--danger) !important; }
  tr.c-fuera td { opacity: .55; }
  tr.nueva { animation: wsNueva 1.2s ease-out; }
  @keyframes wsNueva { from { box-shadow: inset 0 0 0 999px rgba(94,234,212,.28); } to { box-shadow: inset 0 0 0 999px rgba(94,234,212,0); } }
  .ws-detalle { margin-top: 0.5rem; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.6rem 0.8rem; font-family: var(--mono); font-size: 0.76rem; max-height: 340px; overflow: auto; }
  .ws-detalle details { margin: 0.1rem 0; }
  .ws-detalle summary { cursor: pointer; color: var(--text); }
  .ws-detalle .kv { padding-left: 1.2rem; color: var(--text-dim); white-space: pre-wrap; word-break: break-all; }
  .ws-detalle .kv b { color: var(--text); font-weight: 500; }
  .ws-detalle pre { margin: 0.3rem 0 0 1.2rem; white-space: pre-wrap; word-break: break-all; color: var(--text-dim); }

  /* Revision GUI 28-oct: tareas primero, menos ambiguedad, evidencia enlazada. */
  /* Con margin:auto un item de grid no se estira: tomaba el ancho de su tabla
     mas ancha y la cabecera se salia de la pantalla. Ancho fijo a la columna. */
  .shell > .wrap { width: 100%; box-sizing: border-box; }
  @media (min-width: 1500px) { .wrap { max-width: 1320px; } }
  /* El titulo de la seccion ya esta en la cabecera: no repetirlo debajo. */
  .wrap > section > .sec-head, .wrap > section > .sec-head-row > .sec-head { display: none; }
  .wrap > section > .sec-head-row { justify-content: flex-end; }
  h1 small { font-family: var(--sans); font-size: 0.86rem; text-transform: none; letter-spacing: 0; }
  .stamp { text-align: right; }
  .stamp-tz { display: block; font-size: 0.74rem; }
  .nav-grupo[hidden], #nav a[hidden] { display: none; }
  .kpi[data-ir] { cursor: pointer; }
  .kpi[data-ir]:hover, .kpi[data-ir]:focus-visible { border-color: var(--accent); outline: none; }
  .kpi .k-ir { font-size: 0.76rem; color: var(--accent); margin-top: 0.35rem; }
  .al-tag.modelo { background: color-mix(in srgb, var(--capa-b) 24%, transparent); color: #9cc3f7; }
  .al-tag.regla { background: var(--surface-2); color: var(--text); }
  .filtros { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 0.8rem; margin: 0.7rem 0 0.5rem; }
  .filtros label { display: flex; align-items: center; gap: 0.35rem; font-size: 0.8rem; color: var(--text-dim); }
  .filtros input[type="datetime-local"] { background: var(--surface); color: var(--text); border: 1px solid var(--border);
    border-radius: 7px; padding: 0.3rem 0.45rem; font: 0.8rem var(--sans); color-scheme: dark; }
  .btn-sec { background: none; border: 1px solid var(--border); color: var(--accent); border-radius: 7px;
    padding: 0.28rem 0.6rem; font: 0.78rem var(--sans); cursor: pointer; white-space: nowrap; }
  .btn-sec:hover, .btn-sec:focus-visible { border-color: var(--accent); }
  .btn-sec.neutro { color: var(--text-dim); }
  .estado-vacio { padding: 0.8rem 0; color: var(--text-dim); }
  .estado-vacio .btn-sec { margin-left: 0.5rem; }
  .al-ver { display: flex; flex-direction: column; align-items: flex-end; gap: 0.4rem; }
  .dec-resumen { display: flex; flex-wrap: wrap; gap: 0.3rem 1.1rem; font-size: 0.84rem; color: var(--text-dim); margin: 0.3rem 0 0.5rem; }
  .dec-resumen b { color: var(--text); font-variant-numeric: tabular-nums; }
  .periodo-info { font-size: 0.8rem; color: var(--text-dim); margin: 0 0 0.4rem; }
  .periodo-info.activo { color: var(--text); border-left: 3px solid var(--accent); padding-left: 0.55rem; }
  td.ip, td.num { white-space: nowrap; }
  .why .clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  tr.dec-fila.abierta > td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
  .det4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.9rem 1.4rem; }
  .det4 h4 { margin: 0 0 0.35rem; font: 600 0.72rem var(--sans); letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-dim); }
  .det4 p { margin: 0; font-size: 0.88rem; line-height: 1.5; color: var(--text); }
  .det4 dl { grid-template-columns: 1fr; }
  .resp-fuente { font-size: 0.82rem; color: var(--text-dim); border-left: 3px solid var(--border); padding: 0.3rem 0.6rem; margin: 0.4rem 0 0.9rem; }
  .est { display: inline-block; font: 600 0.68rem var(--sans); padding: 1px 7px; border-radius: 999px; margin: 1px 4px 1px 0;
    border: 1px solid var(--border); color: var(--text-dim); white-space: nowrap; }
  .est.si { color: var(--text); border-color: color-mix(in srgb, var(--accent) 45%, var(--border)); }
  .est.no { border-style: dashed; }
  .est.lib { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 50%, var(--border)); }
  .alc-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 0.8rem; margin: 0.6rem 0 1rem; }
  .alc-3 > div { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0.8rem 0.95rem; }
  .alc-3 h3 { margin: 0 0 0.4rem; font-size: 0.95rem; }
  .alc-3 ul { margin: 0; padding-left: 1.1rem; font-size: 0.86rem; line-height: 1.55; color: var(--text-dim); }
  .alc-3 b { color: var(--text); font-weight: 600; }
  details.diag, details.plegable { margin-top: 1rem; border: 1px solid var(--border); border-radius: 12px; padding: 0.55rem 0.9rem; background: var(--surface); }
  details.diag > summary, details.plegable > summary { cursor: pointer; font-weight: 600; font-size: 0.9rem; }
  details.diag[open] > summary, details.plegable[open] > summary { margin-bottom: 0.7rem; }
  .vig-hist { font-size: 0.82rem; color: var(--text-dim); margin: 0.2rem 0 0.8rem; }
  .vig-hist b { color: var(--text); }
  .desp-sum { list-style: none; cursor: pointer; margin-bottom: 0.35rem; }
  .desp-sum::-webkit-details-marker { display: none; }
  .desp-comp .c-n .hace { display: block; font-size: 0.72rem; }
  .desp-comp .c-u { text-align: right; }
  .dec-chart[hidden] { display: none; }
  /* G2 · Alertas activas en el Resumen: cada IP limitada o bloqueada, a un clic
     de su respuesta y de su decision. Las nuevas (menos de 60 s) laten. */
  .aa { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0.8rem 1rem 0.6rem; margin: 0 0 1rem; }
  .aa.con-activas { border-color: color-mix(in srgb, var(--danger) 55%, var(--border)); }
  .aa-cab { display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.45rem; }
  .aa-cab h3 { margin: 0; font-size: 0.95rem; }
  .aa-cab .n { font: 700 0.8rem var(--mono); padding: 0.05rem 0.45rem; border-radius: 999px; background: var(--surface-2); color: var(--text-dim); }
  .aa.con-activas .aa-cab .n { background: var(--danger); color: #fff; }
  .aa-cab .th-sub { margin-left: auto; }
  .aa table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
  .aa th { text-align: left; font-weight: 600; color: var(--text-dim); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 0.25rem 0.5rem; border-bottom: 1px solid var(--border); }
  .aa td { padding: 0.38rem 0.5rem; border-bottom: 1px solid color-mix(in srgb, var(--border) 55%, transparent); vertical-align: middle; }
  .aa td.ip { font-family: var(--mono); font-weight: 600; }
  .aa td .hace { display: block; color: var(--text-dim); font-size: 0.74rem; }
  .aa td.ir { text-align: right; white-space: nowrap; }
  .aa td.ir .btn-sec { margin-left: 0.3rem; }
  .aa tr.row-block td { background: color-mix(in srgb, var(--sev-block) 16%, transparent); }
  .aa tr.row-limit td { background: color-mix(in srgb, var(--sev-limit) 22%, transparent); }
  .aa tr.row-block td:first-child { box-shadow: inset 5px 0 0 var(--sev-block); }
  .aa tr.row-limit td:first-child { box-shadow: inset 5px 0 0 var(--sev-limit); }
  .aa .badge svg { vertical-align: -2px; margin-right: 0.25rem; }
  .aa tr.caducada td { opacity: 0.62; }
  .aa tr.aa-nueva td { animation: aaLatido 1.6s ease-in-out infinite; }
  .aa .aa-sep td { color: var(--text-dim); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.04em; padding-top: 0.6rem; border-bottom: none; }
  .aa .aa-vacio { color: var(--text-dim); font-size: 0.86rem; margin: 0.2rem 0 0.3rem; }
  .aa .nueva-tag { font: 700 0.66rem var(--mono); color: #fff; background: var(--danger); border-radius: 4px; padding: 0.05rem 0.3rem; margin-left: 0.35rem; }
  @keyframes aaLatido { 0%, 100% { background: transparent; } 50% { background: color-mix(in srgb, var(--danger) 16%, transparent); } }
  @media (prefers-reduced-motion: reduce) { .aa tr.aa-nueva td { animation: none; background: color-mix(in srgb, var(--danger) 12%, transparent); } }
  @media (max-width: 760px) { .aa .col-ext { display: none; } }
  /* G3 · Flujo de una IP sobre el Mapa: el camino origen -> agente se resalta
     con el color de su accion y el resto del diagrama se atenua. */
  .flujo-bar { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--flujo, var(--accent)); border-radius: 10px; padding: 0.5rem 0.8rem; margin: 0 0 0.8rem; font-size: 0.86rem; }
  .flujo-bar .ip { font-family: var(--mono); font-weight: 700; }
  .flujo-bar select { background: var(--surface-2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 0.2rem 0.4rem; font: inherit; }
  .flujo-bar .pasos { color: var(--text-dim); font-family: var(--mono); font-size: 0.76rem; }
  svg.con-flujo .topo-node:not(.en-flujo), svg.con-flujo .topo-edge:not(.flujo), svg.con-flujo .topo-edge-label { opacity: 0.28; }
  svg.con-flujo .topo-pkt { display: none; }
  .topo-node.en-flujo .box { stroke: var(--flujo, var(--accent)); stroke-width: 2.6; }
  .topo-node.en-flujo .ico { color: var(--flujo, var(--accent)); }
  .topo-edge.flujo { stroke: var(--flujo, var(--accent)); stroke-width: 3; stroke-dasharray: 7 5; animation: flow 0.9s linear infinite; opacity: 1; }
  @media (prefers-reduced-motion: reduce) { .topo-edge.flujo { animation: none; } }

  /* ---- Tema claro (17-nov, por omision) -------------------------------------
     Mismas variables con tonos claros; abajo, los pocos colores fijos que el tema
     oscuro tenia escritos a mano. Navy y oro de la marca UPeU como acentos. */
  html[data-tema="claro"] {
    color-scheme: light;
    --bg: #f3f6fb; --surface: #ffffff; --surface-2: #eef2f8; --border: #d5ddea;
    --text: #12315f; --text-dim: #55657d; --accent: #0b7a6e;
    --ok: #15803d; --ok-soft: #e6f5ec;
    --amber: #b45309; --amber-soft: #fdf1dc;
    --danger: #c0262d; --danger-soft: #fdeaea;
    --capa-a: #11805a; --capa-b: #1f6fcf; --capa-c: #b8366a; --capa-d: #6a5fd6;
  }
  html[data-tema="claro"] body { background: var(--bg); }
  /* Barra lateral oscura (navy UPeU) aun en tema claro: las variables se redefinen
     dentro de .side y todo lo que cuelga de ella las hereda. */
  html[data-tema="claro"] .side {
    --surface-2: #1b3a66; --border: #2a4a78; --text: #eef3fb; --text-dim: #a9bad4; --accent: #f8a900;
    background: linear-gradient(180deg, #0f2747 0%, #0b1f3a 100%); color: var(--text);
    border-right: none; box-shadow: 2px 0 14px rgba(18,49,95,.18);
  }
  html[data-tema="claro"] .side nav a.active { background: rgba(248,169,0,.14); }
  /* Botones de la cabecera rellenos en navy; el activo, en verde azulado. */
  html[data-tema="claro"] .btn-modo, html[data-tema="claro"] .btn-avisos,
  html[data-tema="claro"] .btn-tema { background: #12315f; border-color: #12315f; color: #ffffff; }
  html[data-tema="claro"] .btn-modo:hover, html[data-tema="claro"] .btn-avisos:hover,
  html[data-tema="claro"] .btn-tema:hover { background: #1b4683; border-color: #1b4683; color: #ffffff; }
  html[data-tema="claro"] .btn-modo[data-modo="desarrollo"],
  html[data-tema="claro"] .btn-avisos[data-on="1"] { background: #0b7a6e; border-color: #0b7a6e; color: #ffffff; }
  html[data-tema="claro"] .btn-salir { background: #ffffff; border-color: #c0262d; color: #c0262d; }
  html[data-tema="claro"] .btn-salir:hover { background: #c0262d; color: #ffffff; }
  html[data-tema="claro"] .topo-cmd, html[data-tema="claro"] .sim-cmd,
  html[data-tema="claro"] .esc-code { background: #0f2340; color: #e6eef8; }
  html[data-tema="claro"] .topo-cmd *, html[data-tema="claro"] .sim-cmd * { color: inherit; }
  html[data-tema="claro"] .esc-code .c { color: #9fb3cf; }
  html[data-tema="claro"] .cv2-ficha.aviso { border-color: #d9a441; color: #8a5a00; }
  html[data-tema="claro"] .cv2-ficha.mal { border-color: #d97a72; color: #a3221b; }
  html[data-tema="claro"] .al-tag.modelo { color: #1f5fae; }
  html[data-tema="claro"] .cmp-como li .n { background: #e3f1ef; }
  html[data-tema="claro"] .cmp-como li code { color: #1f5fae; background: #f1f5fb; border-color: var(--border); }
  html[data-tema="claro"] .cmp-run code { color: #8a5a00; }
  html[data-tema="claro"] .cmp-lado .ev { color: var(--text-dim); }
  html[data-tema="claro"] .rg { background: rgba(255,255,255,.97); border-color: var(--border);
    box-shadow: 0 14px 40px rgba(18,49,95,.18); }
  html[data-tema="claro"] .rg-pasos button { background: var(--surface-2); border-color: var(--border); }
  html[data-tema="claro"] .rg-pasos button:hover { border-color: #9fb3cf; }
  html[data-tema="claro"] .rg-pasos .num { background: #dfe6f1; }
  html[data-tema="claro"] .rg-pasos li.actual button { background: #e3f1ef; }
  html[data-tema="claro"] .rg-pasos li:not(:last-child)::after { background: var(--border); }
  html[data-tema="claro"] .rg-cli { color: #7a4d00; background: #fdf1dc; border-color: #e7c27a; }
  html[data-tema="claro"] .rg-cli .h { color: #a06a10; }
  html[data-tema="claro"] .rg-abrir { background: #ffffff; }
  html[data-tema="claro"] .ver-codigo { background: #eef2f8; border-color: var(--border); color: #1f5fae; }
  html[data-tema="claro"] .ver-codigo:hover { background: #e3eaf5; }
  html[data-tema="claro"] .flj-n { background: #f6f8fc; border-color: var(--border); color: var(--text); }
  html[data-tema="claro"] .pmodal { background: rgba(18,49,95,.35); }
  html[data-tema="claro"] .topo-host .box { fill: #eef6f5; }
  html[data-tema="claro"] .topo-node.sel .box { fill: #e3f1ef; }
  html[data-tema="claro"] .topo-node .box.rombo { fill: #e4ebf6; }
  html[data-tema="claro"] .topo-node.artefacto .box { fill: #f7f9fc; }
  html[data-tema="claro"] .topo-node.sumidero .box { fill: #fbf4f6; }
  @keyframes escNuevaClaro { from { background: #d7f0ec; } }
  .al-fichas { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.35rem; }
  .al-ficha { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; color: var(--text-dim);
    background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 0.18rem 0.6rem; cursor: help; }
  .al-ficha svg { color: var(--accent); flex: none; }
  .al-ficha b { color: var(--text); font-variant-numeric: tabular-nums; }
  .btn-tema { font: inherit; font-size: 0.78rem; padding: 0.3rem 0.65rem; border-radius: 8px; cursor: pointer;
    background: transparent; color: var(--text-dim); border: 1px solid var(--border); }
  .btn-tema:hover { color: var(--text); border-color: var(--accent); }
</style>

<div class="shell">
<aside class="side">
  <div class="brand"><img class="brand-logo" src="data:image/png;base64,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" alt="CyberFlow" title="CyberFlow · motor en vivo"></div>
  <div class="side-state" id="sideState" title="Conectando con el motor"><span class="dot"></span><span id="sideStateText">&hellip;</span></div>
  <nav id="nav">
    <div class="nav-grupo">Operación</div>
    <a href="#s-salud" data-sec="s-salud"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/></svg>Resumen</a>
    <a href="#s-escenario" data-sec="s-escenario"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polygon points="10,8 16,12 10,16"/></svg>Escenario en vivo</a>
    <a href="#s-actividad" data-sec="s-actividad"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,12 7,12 9,6 13,18 15,12 22,12"/></svg>Actividad</a>
    <a href="#s-alertas" data-sec="s-alertas"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.8 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13.5"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg>Alertas<span class="pill" id="navAlertPill" hidden></span></a>
    <a href="#s-decisiones" data-sec="s-decisiones"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>Decisiones</a>
    <a href="#s-bloqueos" data-sec="s-bloqueos"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>Respuestas</a>
    <a href="#s-scores" data-sec="s-scores"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg>Scores</a>
    <!--ADMIN-->
    <div class="nav-grupo">Sistema</div>
    <a href="#s-despliegue" data-sec="s-despliegue"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="3" y="17" width="6" height="5" rx="1"/><rect x="15" y="17" width="6" height="5" rx="1"/><path d="M12 7v4M6 17v-3h12v3"/></svg>Despliegue</a>
    <a href="#s-topologia" data-sec="s-topologia"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg>Mapa del sistema</a>
    <div class="nav-grupo">Datos</div>
    <a href="#s-variables" data-sec="s-variables"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><line x1="3" y1="9.5" x2="21" y2="9.5"/><line x1="9" y1="9.5" x2="9" y2="20"/></svg>Variables</a>
    <a href="#s-vivo" data-sec="s-vivo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h3l2-5 3 10 2-6 2 3h6"/></svg>Datos en vivo</a>
    <div class="nav-grupo">Modelo</div>
    <a href="#s-modelo" data-sec="s-modelo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>Modelo</a>
    <a href="#s-aprendizaje" data-sec="s-aprendizaje"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><polyline points="20,4 20,9 15,9"/></svg>Aprendizaje</a>
    <div class="nav-grupo">Evaluación</div>
    <a href="#s-comparacion" data-sec="s-comparacion"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18V8M10 18V4M16 18v-6M22 18H2"/></svg>Suricata</a>
    <a href="#s-simulacion" data-sec="s-simulacion"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="6,4 20,12 6,20"/></svg>Simulación</a>
    <!--/ADMIN-->
    <div class="nav-grupo">Ayuda</div>
    <a href="#" id="navGuia" role="button"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.4 9.2a2.6 2.6 0 1 1 3.7 2.4c-.8.4-1.1 1-1.1 1.8"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg>Guía operativa</a>
  </nav>
  <div class="foot">SOLO LECTURA</div>
</aside>

<div class="wrap">
  <header>
    <h1><span id="hTitulo">CyberFlow</span><small id="hSub">Motor en vivo</small></h1>
    <span class="stamp"><span id="stamp"></span><span class="stamp-tz" id="stampTz"></span></span>
    <div class="sesion">
      <!--ADMIN--><button id="modoBtn" class="btn-modo" type="button"
        title="Operación: tareas del día a día (resumen, alertas, decisiones, respuestas). Desarrollo: añade mapa, datos, modelo y evaluación. Ninguna de las dos cambia nada en el sistema."></button><!--/ADMIN-->
      <button id="avisosBtn" class="btn-avisos" type="button" data-on="1"
        title="Alertas flotantes cuando una IP recibe LIMIT o BLOCK">Avisos: sí</button>
      <button id="temaBtn" class="btn-tema" type="button" title="Cambiar entre tema claro y oscuro">☾ Tema oscuro</button>
      <span class="quien" id="quien"></span>
      <form method="post" action="/logout"><button class="btn-salir" type="submit">Salir</button></form>
    </div>
  </header>

  <div class="toasts" id="toasts" aria-live="polite"></div>

  <!-- Recorrido guiado de la demo: aparece mientras se sigue un escenario. Cada
       paso lleva a su seccion con la IP filtrada y resaltada; el ultimo dice que
       mirar en la consola (Herdr). El panel no ejecuta nada. -->
  <div class="rg" id="rg" hidden>
    <div class="rg-cab">
      <span class="rg-esc" id="rgEsc"></span>
      <span class="rg-reloj" id="rgReloj"></span>
      <button type="button" class="rg-x" id="rgCerrar" title="Ocultar el recorrido" aria-label="Ocultar el recorrido">&times;</button>
    </div>
    <ol class="rg-pasos" id="rgPasos"></ol>
    <div class="rg-pie">
      <p class="rg-frase" id="rgFrase"></p>
      <span class="rg-cli" id="rgCli"></span>
      <button type="button" class="rg-sig" id="rgSig">Siguiente &rarr;</button>
    </div>
  </div>
  <button type="button" class="rg-abrir" id="rgAbrir" hidden title="Recorrido de la demo" aria-label="Recorrido de la demo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg><span class="rg-txt">Recorrido de la demo</span></button>

  <!-- El resumen (KPIs, barra de salud y pulso) vive en la pagina Salud, no
       como franja repetida en todas: antes se veia identico en cada seccion y
       daba sensacion de que "todo mostraba lo mismo". El estado sigue siempre a
       la vista en la barra lateral (punto + texto + pastilla de alertas). -->
  <section id="s-salud">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.9" fill="currentColor" stroke="none"/></svg><h2>Resumen</h2></div>
    <div class="healthbar" id="healthbar"></div>
    <div class="aa" id="alertasActivas" aria-live="polite"></div>
    <div class="kpi-row" id="kpis"></div>
    <div class="pulso" id="pulso" aria-label="Pulso de la ingesta"></div>
    <details class="diag">
      <summary>Diagnóstico técnico <span class="th-sub">servicios, captura y descartes</span></summary>
      <div class="grid" id="health"></div>
    </details>
  </section>

  <section id="s-escenario">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polygon points="10,8 16,12 10,16"/></svg><h2>Escenario en vivo</h2></div>
    <div class="prep" id="prep">
      <button type="button" class="btn-prep" id="prepBtn">Preparar demo</button>
      <button type="button" class="btn-prep btn-escoba" id="limpiarBtn" hidden title="Dejar limpio: quita las medidas de la Kali y limpia la vista de Alertas" aria-label="Dejar limpio"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 3 11.5 10.5"/><path d="M9.5 9.5l5 5"/><path d="M9.5 9.5 4 15c-1 1-1 3 0 4l1 1c1 1 3 1 4 0l5.5-5.5"/><path d="M6.5 17.5 9 15"/></svg><span>Limpiar</span></button>
      <span class="prep-txt" id="prepTxt">Libera la Kali (10.10.20.30) y el cliente (10.10.20.21) en srv-dmz y comprueba que todo está en marcha. Púlsalo antes de cada demo.</span>
      <ul class="prep-lista" id="prepLista"></ul>
    </div>
    <p class="lede-small">Elige un escenario, lanza su comando y pulsa «Iniciar». El panel sigue a esa IP de la detección a la publicación.</p>
    <div class="esc-cards" id="escCards"></div>
    <div class="esc-det" id="escDet"></div>
    <div class="esc-ctl">
      <label>IP a seguir <input type="text" id="escIp" class="ip-filter" autocomplete="off" spellcheck="false"></label>
      <button type="button" class="btn-sec" id="escIniciar">Iniciar seguimiento</button>
      <button type="button" class="btn-sec neutro" id="escParar" hidden>Terminar</button>
      <span class="esc-estado" id="escEstado"></span>
      <span class="esc-reloj" id="escReloj"></span>
    </div>
    <ol class="esc-pasos" id="escPasos"></ol>
    <p class="act-h">Ventanas de la IP <span class="th-sub" id="escFilasSub">en vivo, cada 3 s</span></p>
    <div class="esc-filas" id="escFilas"></div>
  </section>


  <!--ADMIN-->
  <section id="s-topologia">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg><h2>Mapa del sistema</h2></div>
    <p class="lede-small topo-lede" id="topoLede">Pulsa un componente para ver su detalle.</p>
    <div class="flujo-bar" id="flujoBar" hidden></div>
    <div class="topo-wrap" id="topoWrap">
      <div class="topo-canvas" id="topoCanvas">
        <div class="topo-bar">
          <div class="range-toggle" id="topoVista">
            <button data-vista="red">1 · Red y captura</button>
            <button data-vista="completa" class="active">2 · Operacional</button>
            <button data-vista="construccion" class="vista-oculta" disabled title="Vista oculta" aria-label="Vista oculta"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C3.9 8.4 2 12 2 12s4 7 10 7a9.6 9.6 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg></button>
            <button data-vista="decision">4 · Decisión</button>
            <button data-vista="respuesta">5 · Respuesta</button>
            <button data-vista="carpetas">6 · Carpetas</button>
          </div>
          <div class="range-toggle topo-modo" id="topoModo" title="Lab: lo montado para el ensayo · Operativa: solo el flujo de una red real">
            <button data-modo="lab">Vista lab</button>
            <button data-modo="operativa">Vista operativa</button>
          </div>
          <div class="topo-zoom">
            <button id="topoMenos" title="Reducir" aria-label="Reducir">&minus;</button>
            <span id="topoNivel">100%</span>
            <button id="topoMas" title="Ampliar" aria-label="Ampliar">+</button>
            <button id="topoReset" title="Ver todo el diagrama" aria-label="Ver todo el diagrama">Ajustar</button>
          </div>
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
          <svg id="topo" role="img" aria-label="Mapa del sistema CyberFlow"></svg>
          <div class="topo-tabla" id="topoTabla"></div>
        </div>
      </div>
      <div class="topo-detail" id="topoDetail"></div>
    </div>
  </section>

  <section id="s-despliegue">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2.5" y="17" width="6" height="5" rx="1"/><rect x="15.5" y="17" width="6" height="5" rx="1"/><path d="M12 7v4M5.5 17v-3h13v3"/></svg><h2>Despliegue y agentes</h2></div>
    <p class="lede-small">Dónde está instalado cada componente y cómo viaja el feed firmado del sensor a los hosts protegidos. Cada línea dice de dónde sale su estado: <span class="est si">comprobado desde el sensor</span> (servicio consultado ahora) o <span class="est no">configuración declarada</span> (inventario versionado, verificado el 12-oct-2026; el panel no tiene credenciales de los demás hosts).</p>
    <div class="desp" id="despliegue"></div>
    <p class="toolbar-hint" id="desplieguePie"></p>
    <details class="plegable">
      <summary>Instalación, diagnóstico y mantenimiento</summary>
      <p class="lede-small"><b>Requisitos del sensor</b>: Linux con systemd, interfaz conectada a un puerto espejo (SPAN), Suricata, Python con el entorno del proyecto y espacio para el anillo de PCAP. <b>Por host protegido</b>: nftables, el agente <code>agente_enforce.py</code> con su temporizador y la clave pública del sensor; el agente eleva solo <code>nft</code> con <code>sudo -n</code>.</p>
      <p class="lede-small"><b>Comprobación tras instalar</b>: servicios activos en Resumen · decisiones nuevas en Decisiones · el feed aparece como publicado en Respuestas · en el host, el registro del agente muestra la firma verificada.</p>
      <p class="lede-small"><b>Diagnóstico</b>: <code>journalctl -u ppi-motor -u ppi-motor-capture -n 100</code> en el sensor; <code>journalctl -u ppi-enforce-agent-v2-dmz -n 50</code> en el host. <b>Recuperación</b>: si el agente rechaza la firma no aplica nada; las reglas caducan solas.</p>
      <p class="lede-small"><b>Mantenimiento</b>: a diario, revisar Resumen (servicios y drops) y Respuestas; cada semana, el espacio del anillo, la deriva en Aprendizaje y las entidades con más respuestas. Guía completa: <code>docs/INSTALACION.md</code>.</p>
    </details>
  </section>

  <section id="s-variables">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><line x1="3" y1="9.5" x2="21" y2="9.5"/><line x1="9" y1="9.5" x2="9" y2="20"/></svg><h2>Variables por capa</h2></div>
    <p class="lede-small">Qué mide el sistema en cada capa del modelo OSI. Pulsa una fila para ver su explicación y valores reales tomados del dataset que se está acumulando.</p>
    <div class="var-capas" id="varCapas"></div>
    <div class="var-tabla" id="varTabla"></div>
    <p class="toolbar-hint" id="varPie"></p>

    <div class="umb-box">
      <h3 class="umb-h">Umbrales y régimen de decisión</h3>
      <p class="lede-small">Las 28 variables entran <strong>juntas</strong> a un modelo multivariante (IsolationForest): una ventana es anómala si su <strong>score combinado &lt; &minus;0,622389</strong> (punto operativo adoptado, &alpha;&nbsp;=&nbsp;0,01, <code>if_limpio_2026_10</code>) &mdash; un único umbral, calibrado estadísticamente (percentil &alpha;&nbsp;=&nbsp;0,01 de las puntuaciones de validación). El motor desplegado aún registra con &alpha;&nbsp;=&nbsp;0,05 (&minus;0,569397). <strong>No hay un corte por variable</strong>: el valor de una sola solo cobra sentido combinado con el resto. Solo una parte de las variables lleva, además, un <strong>umbral heurístico explícito</strong> &mdash; criterio razonado y versionado, no calibrado como el del modelo:</p>
      <div class="umb-tabla">
        <table>
          <thead><tr><th>Regla</th><th>Variables y umbral</th><th>Acción</th><th>Por qué ese valor</th></tr></thead>
          <tbody>
            <tr><td class="umb-r">port_scan</td><td>intentos de flujo &ge;20/30s &middot; puertos únicos &ge;0,45 &middot; SYN completados &le;0,30 &mdash; <b>ó</b> ráfaga &ge;200/30s con &le;10&nbsp;%</td><td><span class="badge acc-block">BLOCK</span></td><td>El escaneo prueba muchos puertos y casi ninguno completa. La rama de ráfaga se añadió porque el espejo SPAN topa el ratio de unicidad en ~0,5. FPR validado: +5 en 712&nbsp;450 ventanas (0,012&nbsp;%).</td></tr>
            <tr><td class="umb-r">brute_force</td><td>&ge;5 req HTTP/60s <b>y</b> &ge;80&nbsp;% de fallo de auth (401/403)</td><td><span class="badge acc-block">BLOCK</span></td><td>Ráfaga de logins casi todos fallidos: señal inequívoca. El modelo mide flojo justo en este patrón.</td></tr>
            <tr><td class="umb-r">http_abuse</td><td>&ge;100 req HTTP/60s sin patrón de fuerza bruta</td><td><span class="badge acc-limit">LIMIT</span></td><td>Volumen alto <b>ambiguo</b> (puede ser uso pesado legítimo): se degrada la tasa, no se corta.</td></tr>
            <tr><td class="umb-r">dns_entropy</td><td>&ge;20 consultas DNS/60s <b>y</b> (&ge;50&nbsp;% NXDOMAIN <b>ó</b> &ge;45&nbsp;% nombres únicos)</td><td><span class="badge acc-limit">LIMIT</span></td><td>El hueco donde el modelo sacó 0&nbsp;% (DNS de alta entropía). Los ratios se bajaron a 0,45 porque el SPAN duplica tramas y topa en ~0,5. FPR 0/527 sobre la línea base.</td></tr>
          </tbody>
        </table>
      </div>
      <p class="toolbar-hint">Los umbrales heurísticos son <b>criterio razonado, versionado (2026-10-06.2) y configurable</b> &mdash; no calibrados estadísticamente como el umbral del modelo. Las otras 20 variables no tienen corte fijo: su valor lo pondera el modelo junto con el resto.</p>
    </div>
  </section>

  <section id="s-vivo">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h3l2-5 3 10 2-6 2 3h6"/></svg><h2>Datos en vivo: del registro a la variable</h2></div>
    <p class="lede-small">Las dos fuentes del puerto espejo, en vivo: <strong>tramas PCAP</strong> (tcpdump) y <strong>eventos eve.json</strong> (Suricata). Cada fila aparece al capturarse, <em>provisional</em>, y queda <strong>confirmada</strong> cuando el motor la procesa y calcula el valor real de la variable.</p>
    <div class="vivo-medidor" id="vivoMedidor">
      <div class="vm-estado"><span class="vm-dot" id="vmDot"></span><b id="vmTitulo">Conectando&hellip;</b><span id="vmSub"></span></div>
      <div class="vm-fuente"><div class="vm-cab">PCAP &middot; tcpdump</div><div class="vm-num"><b id="vmPcapTasa">—</b> tramas/s</div><svg id="vmPcapSpark" class="vm-spark" viewBox="0 0 120 28" preserveAspectRatio="none"></svg><div class="vm-pie" id="vmPcapPie">—</div></div>
      <div class="vm-fuente"><div class="vm-cab">eve.json &middot; Suricata</div><div class="vm-num"><b id="vmEveTasa">—</b> eventos/s</div><svg id="vmEveSpark" class="vm-spark" viewBox="0 0 120 28" preserveAspectRatio="none"></svg><div class="vm-pie" id="vmEvePie">—</div></div>
      <div class="vm-fuente"><div class="vm-cab">Desde que abriste la vista</div><div class="vm-num"><b id="vmTotal">0</b></div><div class="vm-pie" id="vmTotalPie">—</div></div>
    </div>
    <div class="vivo-bar">
      <div class="range-toggle" id="vivoTabs">
        <button data-vtab="eve" class="active">Eventos eve.json</button>
        <button data-vtab="pcap">Tramas PCAP</button>
        <button data-vtab="matriz">Matriz de trazabilidad</button>
      </div>
      <input type="text" id="vivoFiltro" class="ip-filter" placeholder="Filtrar: IP, protocolo, variable...">
      <label class="vivo-chk" id="vivoTodosLbl" title="Por omisión solo se listan los registros que aportan a alguna variable"><input type="checkbox" id="vivoTodos"> ver todo</label>
      <label class="vivo-chk" title="Bajar solo con cada registro nuevo, como Wireshark"><input type="checkbox" id="vivoSeguir" checked> seguir</label>
      <button id="vivoPausa" class="export-btn" type="button">Pausar</button>
      <button id="vivoLimpiar" class="export-btn" type="button">Limpiar</button>
    </div>
    <p class="toolbar-hint" id="vivoResumen">Cargando&hellip;</p>
    <div class="tbl-wrap tbl-scroll vivo-tabla ws" id="vivoTabla"></div>
    <div class="ws-detalle" id="vivoDetalle" hidden></div>
    <p class="toolbar-hint" id="vivoPie"></p>
  </section>

  <section id="s-modelo">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="1.5"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/><line x1="2" y1="9" x2="6" y2="9"/><line x1="2" y1="15" x2="6" y2="15"/><line x1="18" y1="9" x2="22" y2="9"/><line x1="18" y1="15" x2="22" y2="15"/></svg><h2>Modelo congelado</h2></div>
    <div class="grid" id="model"></div>
    <p class="vig-hist" id="modeloVigHist"><b>Punto operativo adoptado:</b> &alpha;&nbsp;=&nbsp;0,01, umbral &minus;0,622389 (score_samples; &minus;0,122389 en la escala de decisión), modelo <code>if_limpio_2026_10</code>. <b>Nota:</b> la tarjeta «Umbral vigente» muestra el valor que el <b>motor registra en vivo</b>; el motor desplegado aún opera en &alpha;&nbsp;=&nbsp;0,05 (&minus;0,569397), así que puede mostrar ese número hasta re-apuntarlo. <b>Histórico:</b> <code>if_recalibrado_2026_09</code> (umbral &minus;0,568892, FPR 4,45&#8239;% en el oro) estuvo desplegado hasta el 19-oct-2026; sus cifras aparecen solo como antecedente.</p>
    <div class="fam-wrap" id="modeloFamilias"></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="16.5" r="0.7" fill="currentColor" stroke="none"/></svg><span id="modeloDebil"><strong>Punto débil conocido:</strong> un PERMIT del modelo no descarta un ataque por sí solo; los heurísticos cubren lo que el modelo no ve.</span></div>

    <p class="lede-small" id="pruebasPrevias" style="margin-top:1.4rem"><strong style="color:var(--text)">Pruebas previas &mdash; comparación exploratoria de modelos (laboratorio).</strong> Se compararon <strong>7 candidatos</strong> con las mismas variables y la misma partición (<code>compare_frozen_models_metrics.py</code>, auditable desde <em>Mapa &rarr; Ver archivos</em>). El conjunto positivo son 179 ventanas de anomalía; el negativo, 276 ventanas normales de prueba. Se reportan F1, MCC, ROC&#8209;AUC y precisión media, sin reentrenar y verificando cada modelo contra el manifiesto. Ahí ganó el OCSVM, pero <strong>la selección se hizo tras ver la prueba</strong> (sesgo declarado) y no transfirió a esta red.</p>

    <p class="lede-small" style="margin-top:1rem"><strong style="color:var(--text)">Comparación sobre ESTA red &mdash; la que decide el despliegue.</strong> El ganador de laboratorio (OCSVM), con su umbral, marca el <strong>99,6 %</strong> del tráfico normal de esta red como anomalía: inservible aquí. Por eso se vuelve a comparar sobre datos propios &mdash; <strong>65 421 ventanas normales</strong> del conjunto de oro (para el FPR) y <strong>84 ventanas de ataque</strong> de la Kali (para la detección) &mdash;, cargando cada <code>joblib</code> congelado sin reentrenar.</p>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Modelo</th><th class="r">ROC-AUC</th><th class="r">AP</th><th class="r">FPR</th><th class="r">Recall (umbral propio)</th></tr></thead>
      <tbody>
        <tr><td style="box-shadow:inset 3px 0 0 var(--ok)"><b>IF limpio · <code>if_limpio_2026_10</code> (punto operativo, &alpha;&nbsp;=&nbsp;0,01)</b></td><td class="num r">0,9247</td><td class="num r">0,1858</td><td class="num r">0,87&#8239;%</td><td class="num r"><b>59,52&#8239;%</b></td></tr>
        <tr><td>IF recalibrado · <code>if_recalibrado_2026_09</code> (histórico, hasta 19-oct)</td><td class="num r">0,9228</td><td class="num r">0,2026</td><td class="num r">4,45&#8239;%</td><td class="num r">64,29&#8239;%</td></tr>
        <tr><td>IF scaled (lab)</td><td class="num r">0,8250</td><td class="num r">0,0043</td><td class="num r">30,34&#8239;%</td><td class="num r">91,67&#8239;%</td></tr>
        <tr><td>IF primary (lab)</td><td class="num r">0,8283</td><td class="num r">0,0044</td><td class="num r">29,07&#8239;%</td><td class="num r">82,14&#8239;%</td></tr>
        <tr><td>IF uniform / exact (scores idénticos)</td><td class="num r">0,7960</td><td class="num r">0,0054</td><td class="num r">34,13&#8239;%</td><td class="num r">85,71&#8239;%</td></tr>
        <tr><td>OCSVM (lab)</td><td class="num r">0,4555</td><td class="num r">0,0011</td><td class="num r">99,57&#8239;%</td><td class="num r">100,00&#8239;%</td></tr>
        <tr><td>LOF (lab)</td><td class="num r">0,2991</td><td class="num r">0,0009</td><td class="num r">76,80&#8239;%</td><td class="num r">70,24&#8239;%</td></tr>
        <tr><td>Elliptic Envelope (lab)</td><td class="num r">0,3443</td><td class="num r">0,0014</td><td class="num r">86,90&#8239;%</td><td class="num r">42,86&#8239;%</td></tr>
      </tbody>
    </table></div>
    <p class="toolbar-hint">En el punto operativo adoptado (&alpha;&nbsp;=&nbsp;0,01) el IF limpio detecta 50/84 ventanas etiquetadas y produce 567 falsas alarmas: precisión 8,10&#8239;%, F1 14,27&#8239;%, FPR 0,87&#8239;%. No se afirma superioridad general ni equivalencia estadística frente al antecedente. Figuras y scores completos: repositorio de orquestación, sección 4.1.</p>
    <div class="note"><span><strong>Cómo se comparó.</strong> Mismas 65 505 ventanas, con el umbral propio de cada configuración. La evaluación es reutilizada, no un test ciego independiente. El origen de entrenamiento difiere: se mide transferencia a esta red, no superioridad intrínseca de un algoritmo. Se retiró Det@FPR5% porque fijaba el corte en negativos de prueba. La sensibilidad correcta usa validación; α=0,01 es el punto operativo adoptado, no un óptimo demostrado.</span></div>
    <div class="note"><span><strong>El cálculo.</strong> El IF asigna scores menores a las observaciones más anómalas. El corte congelado del punto operativo adoptado es <code>score_samples(x) &lt; −0,6223889502095352</code> (−0,122389 en la escala de la función de decisión), percentil 1 de validación. ROC-AUC resume ordenamiento; AP es precisión media, no una garantía de precisión en el umbral. La prevalencia es 84/65 505 = 0,128&#8239;%. La validación contiene 80 ventanas Kali, 17 con actividad y normalidad no verificada.</span></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Archivos y código</strong> (auditables desde <em>Mapa &rarr; Ver archivos</em>, con pseudocódigo y diagrama de flujo): <code>entrenar_preliminar.py</code> entrena y congela el umbral; <code>promover_preliminar.py</code> arma el Pipeline + manifiesto; <code>verificar_equivalencia_umbral.py</code> comprueba hash, orden y umbral; <code>compare_frozen_models_metrics.py</code> reproduce las métricas de los 7; <code>significancia_modelos.py</code> hace McNemar + Holm. Los 7 candidatos congelados están en <code>artifacts/model/candidates/*.joblib</code>.</span></div>
    <p class="lede-small"><strong>Ablación histórica del predecesor</strong> sobre 9 episodios (3 familias con 3 repeticiones). No trasladar estas cifras al modelo limpio: su campaña final sigue pendiente.</p>
    <div class="grid">
      <div class="card"><div class="label">Modelo solo</div><div class="value">6 / 9</div></div>
      <div class="card"><div class="label">Heurísticos solos</div><div class="value">7 / 9</div></div>
      <div class="card accent"><div class="label">Modelo + heurísticos</div><div class="value">9 / 9</div></div>
    </div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span>La <strong>complementariedad es el resultado medido</strong>: el modelo detectó flood HTTP y escaneo en esta batería, pero <strong>0/3 DNS</strong>; el heurístico DNS cubrió ese hueco. La fuerza bruta en vivo la confirma el heurístico <code>brute_force</code>. La combinación cubrió 9/9 episodios de las tres primeras familias; no significa que el modelo solo los cubra. La comparación con Suricata y sus límites están en la nota 32 del repositorio de orquestación.</span></div>
  </section>

  <section id="s-comparacion">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18V8M10 18V4M16 18v-6M22 18H2"/></svg><h2>CyberFlow frente a Suricata</h2></div>
    <p class="cmp-lede"><b>Mismo tráfico, dos sistemas.</b> Suricata 7 con ET Open es el IDS de firmas de referencia. Se compara la <b>detección</b>; responder (LIMIT/BLOCK en el host) solo lo hace CyberFlow.</p>
    <ol class="cmp-como">
      <li><span class="n">1</span><b>Recortar el tráfico</b><small>Del anillo PCAP del espejo (Sensor1), solo la IP y el intervalo del ataque.</small><code>tcpdump -r live-*.pcap "host IP" · recortar_pcap.py desde hasta</code></li>
      <li><span class="n">2</span><b>Llevarlo a Suricata</b><small>A una VM aparte (10.10.60.13): Suricata no comparte nada con el sensor.</small><code>ssh suricata · ~/cf-demo/cmp-AAAAMMDD-HHMMSS/pcap</code></li>
      <li><span class="n">3</span><b>Suricata analiza</b><small>Offline, con todas las firmas ET Open activas. Su salida es fast.log.</small><code>suricata -r pcap -S suricata.rules -k none</code></li>
      <li><span class="n">4</span><b>CyberFlow, misma ventana</b><small>Las decisiones del motor para esa IP e intervalo, y el acuse del host.</small><code>motor_decision.log · acuses/srv-dmz.json</code></li>
    </ol>
    <p class="cmp-run">Lo ejecuta el director al final de cada escenario, o a mano en el bastión: <code>~/cf-demo/comparar-suricata.sh IP desde hasta</code></p>
    <h3 class="cmp-h">Comparaciones de la demo <span class="th-sub" id="cmpVivoSub"></span></h3>
    <div class="cmp-vivo" id="cmpVivo"><p class="estado-vacio">Cargando…</p></div>
    <details class="plegable cmp-bateria">
      <summary>Medición previa: replay de la batería N=3 por familia</summary>
      <div class="tbl-wrap"><table><thead><tr><th>Familia</th><th class="r">Suricata</th><th class="r">Solo modelo</th><th class="r">Solo reglas</th><th class="r">CyberFlow</th></tr></thead><tbody id="cmpTabla"></tbody></table></div>
      <p class="toolbar-hint">Celda: episodios detectados / medidos · latencia mediana [mín–máx]. Mismo PCAP a los dos, con el reloj del paquete.</p>
      <ul class="cmp-notas" id="cmpNotas"></ul>
    </details>
    <p class="toolbar-hint">Suricata del sensor corre sin firmas: solo aporta los eventos HTTP/DNS/TLS que CyberFlow usa como variables de capa 7. Las firmas se evalúan aquí, en la VM aparte.</p>
  </section>

  <section id="s-alcance" hidden>
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="5" y1="19" x2="19" y2="5"/></svg><h2>Alcance del análisis</h2></div>
    <div class="alc-3">
      <div><h3>Observa</h3><ul>
        <li><b>IPv4</b>, capas <b>L3, L4 y L7</b></li>
        <li>LAN y tráfico hacia Internet, por <b>puerto espejo (SPAN)</b></li>
        <li>En paralelo, no en línea: no retrasa el tráfico</li></ul></div>
      <div><h3>Responde</h3><ul>
        <li><b>LIMIT</b> (degrada la tasa) o <b>BLOCK</b> (corta), con caducidad</li>
        <li>Solo en hosts que tienen el <b>agente</b> instalado</li>
        <li>El sensor publica un feed firmado; el host lo aplica</li></ul></div>
      <div><h3>Límites</h3><ul>
        <li>IPv6: trabajo futuro</li>
        <li>Sin inspección de capa 2</li>
        <li>La visibilidad depende de lo que llegue al espejo y del cifrado (en TLS solo se ven metadatos)</li></ul></div>
    </div>
    <div class="umb-box">
      <h3 class="umb-h">Cómo leer el panel</h3>
      <p class="lede-small"><b>Anomalía</b>: una ventana cuyo score del modelo queda por debajo del umbral vigente; es una señal, no un ataque confirmado. <b>PERMIT</b>: no se pide acción para esa ventana; no prueba que no haya ataque (el modelo es débil en algunas familias). <b>Dónde se aplica</b>: en el host protegido, por su agente. <b>Qué no confirma el panel</b>: que el host haya aplicado la acción; eso solo lo registra el agente.</p>
    </div>
    <details class="plegable">
      <summary>Alcance declarado en detalle</summary>
      <p class="lede-small">CyberFlow analiza las capas de <strong>red (L3)</strong>, <strong>transporte (L4)</strong> y <strong>aplicación (L7)</strong> sobre <strong>IPv4</strong>. Observa el tráfico de la <strong>LAN</strong> y el que va <strong>hacia Internet</strong> mediante un <strong>puerto espejo (SPAN)</strong>; no inspecciona la capa&nbsp;2 ni IPv6. El sensor observa <strong>en paralelo, no en línea</strong>, y la respuesta (LIMIT/BLOCK) se aplica <strong>en el host protegido</strong>. IPv6 queda declarado como trabajo futuro.</p>
    </details>
    <h3 class="umb-h" style="margin-top:1.2rem">Filtros y cobertura de captura</h3>
    <p class="lede-small">Lo que se captura pero NO se puntúa, y por qué. Declararlo con su cifra es parte del método: sin número, «se excluyó» no es una medición. Las cifras se acumulan desde el último arranque del motor.</p>
    <div class="grid" id="alcance"></div>
    <p class="toolbar-hint" id="alcanceDetalle"></p>
  </section>

  <section id="s-simulacion">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="6,4 20,12 6,20"/></svg><h2>Simulación de escenarios</h2></div>
    <p class="lede-small">Elige un escenario, copia el comando y ejecútalo en la Kali. La respuesta aparece en Actividad y Decisiones.</p>
    <div class="range-toggle" id="simTabs">
      <button data-sim="normal" class="active">Tráfico normal</button>
      <button data-sim="anomalo">Tráfico anómalo</button>
    </div>
    <div class="sim-grid" id="simGrid"></div>

    <div class="pmodal" id="pmodal">
      <div class="pmodal-box">
        <div class="pmodal-h"><h3 id="pmodalTit">Tráfico normal</h3><button class="pmodal-x" aria-label="Cerrar">&times;</button></div>
        <div id="pmodalBody"></div>
      </div>
    </div>
  </section>

  <section id="s-aprendizaje">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><polyline points="20,4 20,9 15,9"/></svg><h2>Reentrenamiento con aprobación humana</h2></div>
    <p class="lede-small">Cada noche el sistema sanea un lote del día, mide la deriva y, cuando toca, entrena y evalúa un modelo candidato. <strong>El modelo en uso solo cambia cuando una persona lo promueve</strong>. Aquí se ve cada defensa con su cifra. La política se cambia en el .toml (sección [reentrenamiento]), no desde aquí.</p>
    <div class="apr-def" id="aprDefensas"></div>
    <div class="apr-cols">
      <div><h3 class="apr-h">Último candidato</h3><div id="aprCandidato"></div></div>
      <div><h3 class="apr-h">Política vigente</h3><div class="tbl-wrap" id="aprPolitica"></div></div>
    </div>
    <h3 class="apr-h">Tendencia <span class="th-sub">cada punto es una noche; la línea discontinua es el límite de la política</span></h3>
    <div class="apr-graf">
      <div class="spark-wrap"><p class="act-h">PSI máximo del lote <span class="th-sub">por encima, el lote se rechaza</span></p><svg id="aprGLote" class="apr-chart"></svg></div>
      <div class="spark-wrap"><p class="act-h">PSI de las puntuaciones <span class="th-sub">por encima, señal de deriva</span></p><svg id="aprGPsi" class="apr-chart"></svg></div>
      <div class="spark-wrap"><p class="act-h">FPR en el oro y anómalo en el lote</p><svg id="aprGTasa" class="apr-chart"></svg></div>
    </div>
    <h3 class="apr-h">Lotes diarios <span class="th-sub">saneamiento y linaje</span></h3>
    <div class="tbl-wrap" id="aprLotes"></div>
    <h3 class="apr-h">Deriva <span class="th-sub">modelo vigente frente al conjunto de oro</span></h3>
    <div class="tbl-wrap" id="aprDeriva"></div>
    <p class="toolbar-hint" id="aprPie"></p>
  </section>
  <!--/ADMIN-->

  <section id="s-scores">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg><h2>Distribución de scores</h2></div>
    <div class="wids" id="scoreWids"></div>
    <details class="ayuda"><summary>ⓘ Cómo leer este gráfico</summary>
    <p class="lede-small">Qué tan cerca del umbral está pasando el tráfico reciente (últimas 500 decisiones) &mdash; no solo si alertó o no, sino cuánto margen hubo. La línea marca el <b>umbral vigente</b>, el mismo que usan Decisiones y el motor. Un score inferior al umbral genera una señal del modelo; la decisión final combina otras reglas.</p></details>
    <div class="spark-wrap">
      <svg id="histogram" role="img" aria-label="Histograma de scores recientes con el umbral"></svg>
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
    <div class="act-cols">
      <div>
        <p class="act-h">Acciones y ventanas analizadas <span class="th-sub" id="sparkRangeLabel">por minuto</span></p>
        <div class="spark-wrap">
          <div class="act-chart">
            <div class="act-y" id="actY"></div>
            <svg id="spark" width="100%" style="height:150px" viewBox="0 0 610 150" preserveAspectRatio="none"></svg>
          </div>
          <div class="act-x" id="actX"></div>
          <div class="chart-tip" id="sparkTip"></div>
          <div class="spark-legend">
            <span><i class="swatch" style="background:var(--danger)"></i>BLOCK</span>
            <span><i class="swatch" style="background:var(--amber)"></i>LIMIT</span>
            <span><i class="swatch" style="background:var(--accent)"></i>ventanas analizadas</span>
            <span>arriba, acciones · abajo, volumen</span>
          </div>
        </div>
      </div>
      <div>
        <p class="act-h">Entidades con señales <span class="th-sub">última hora · pulsa para ver sus decisiones</span></p>
        <div class="tbl-wrap">
          <table><thead><tr><th>Entidad</th><th class="r">Decisiones con acción</th><th>Última</th></tr></thead><tbody id="topIps"></tbody></table>
        </div>
      </div>
    </div>
  </section>

  <section id="s-alertas">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.8 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13.5"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg><h2>Alertas</h2></div>
    <div class="alertas-resumen" id="alertasResumen"></div>
    <div class="filtros">
      <label>Fuente
        <span class="range-toggle" id="alertasFiltro">
          <button data-af="todas" class="active">Todas</button>
          <button data-af="modelo">Modelo</button>
          <button data-af="regla">Reglas</button>
        </span></label>
      <label>Acción
        <span class="range-toggle" id="alertasAccion">
          <button data-aa="todas" class="active">Todas</button>
          <button data-aa="LIMIT">LIMIT</button>
          <button data-aa="BLOCK">BLOCK</button>
        </span></label>
      <input type="text" id="alertasIp" class="ip-filter" placeholder="Filtrar por IP..." aria-label="Filtrar alertas por IP">
      <button type="button" class="btn-sec neutro" id="alertasLimpiar">Limpiar filtros</button>
      <button type="button" class="btn-sec neutro btn-escoba-sec" id="alertasEscoba" title="Dejar limpio: quita las medidas de la Kali y limpia esta vista" aria-label="Dejar limpio"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 3 11.5 10.5"/><path d="M9.5 9.5l5 5"/><path d="M9.5 9.5 4 15c-1 1-1 3 0 4l1 1c1 1 3 1 4 0l5.5-5.5"/><path d="M6.5 17.5 9 15"/></svg></button>
      <button type="button" class="btn-sec neutro" id="alertasMarg" aria-pressed="false" title="Anomalías solo del modelo con el score a menos de 0,05 del umbral">Marginales: ocultas</button>
    </div>
    <div class="alertas-lista" id="alertasLista"></div>
    <div class="lb-caja" id="alertasListaBlanca" hidden></div>
  </section>

  <section id="s-bloqueos">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg><h2>Respuestas</h2></div>
    <p class="sec-sub"><b>LIMIT</b> degrada la tasa de una IP; solo <b>BLOCK</b> la corta.</p>
    <div class="wids" id="respWids"></div>
    <details class="ayuda"><summary>ⓘ Cómo leer esta vista</summary>
    <p class="resp-fuente" id="vigentesSub">Fuente: registro del motor y feed firmado por el sensor. La columna Evidencia añade lo que <b>cada host protegido dice tener</b> en su nftables (acuse que trae el relay cada 10 s): aplicada, liberada por un humano o fuera de alcance. El acuse es un informe del host, no una orden.</p>
    <p class="toolbar-hint">Estados: <span class="est si">registrada</span> el motor la decidió · <span class="est si">publicada</span> está en el feed firmado · <span class="est si">srv-dmz: BLOCK aplicado</span> el host la tiene en nftables · <span class="est lib">liberada</span> un humano la quitó · <span class="est no">fuera de alcance</span> el host no la aplica (infraestructura).</p>
    </details>
    <p class="act-h">Respuestas registradas como vigentes <span class="th-sub" id="vigentesN"></span></p>
    <div class="tbl-wrap">
      <table><thead><tr><th>Entidad</th><th>Acción</th><th>Motivo</th><th>Inicio del episodio · última renovación</th><th>Caduca</th><th>Evidencia</th></tr></thead><tbody id="blocked"></tbody></table>
    </div>
    <p class="act-h" style="margin-top:1.2rem">Historial de las últimas 24 h <span class="th-sub" id="histSub"></span></p>
    <div class="spark-wrap" style="margin-bottom:0.8rem">
      <svg id="histChart" class="hist-chart" role="img" aria-label="Línea de tiempo de acciones por IP en las últimas 24 horas"></svg>
      <div class="spark-legend">
        <span><i class="swatch" style="background:var(--danger)"></i>BLOCK</span>
        <span><i class="swatch" style="background:var(--amber)"></i>LIMIT</span>
        <span>cada barra es una racha de ventanas de la misma IP; la zona rayada es anterior al registro leído</span>
      </div>
    </div>
    <div class="tbl-wrap tbl-scroll" style="max-height:280px">
      <table><thead><tr><th>Inicio</th><th>Entidad</th><th>Acción</th><th>Motivo</th><th>Racha de decisiones</th><th>Caducidad configurada</th><th class="r">Ventanas</th><th>Estado según registro</th><th></th></tr></thead><tbody id="histTabla"></tbody></table>
    </div>
  </section>

  <section id="s-decisiones">
    <div class="sec-head-row">
      <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg><h2>Decisiones</h2></div>
      <div class="toolbar">
        <div class="range-toggle" id="decVista">
          <button data-dv="accion" class="active">Con acción</button>
          <button data-dv="limit">LIMIT</button>
          <button data-dv="block">BLOCK</button>
          <button data-dv="todas">Todas</button>
        </div>
        <input type="text" id="ipFilter" placeholder="Filtrar por IP..." class="ip-filter">
        <button id="exportCsv" class="export-btn" title="Exporta las filas que ves ahora: vista, filtro de IP y periodo actuales">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><polyline points="7,10 12,15 17,10"/><path d="M4 18v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          Exportar CSV
        </button>
      </div>
    </div>
    <div class="filtros" id="decPeriodo">
      <label>Desde <input type="datetime-local" id="decDesde" step="60"></label>
      <label>Hasta <input type="datetime-local" id="decHasta" step="60"></label>
      <button type="button" class="btn-sec" id="decConsultar">Consultar periodo</button>
      <button type="button" class="btn-sec neutro" id="decEnVivo" hidden>Volver a en vivo</button>
      <button type="button" class="btn-sec neutro" id="decLimpiar">Limpiar filtros</button>
      <button type="button" class="btn-sec neutro" id="decGrafBtn" aria-expanded="true">Ocultar gráfico</button>
    </div>
    <p class="periodo-info" id="decPeriodoInfo"></p>
    <div class="dec-resumen" id="decResumen"></div>
    <div class="spark-wrap dec-chart" id="decChartWrap">
      <button type="button" class="btn-sec dec-max-btn" id="decMaxBtn" title="Ver el gráfico a pantalla completa; rueda del ratón = zoom, doble clic = restablecer">⤢ Ampliar</button>
      <span class="dec-zoom-info" id="decZoomInfo"></span>
      <svg id="decChart" role="img" aria-label="Score de cada decisión en el tiempo, con el umbral"></svg>
      <div class="chart-tip" id="decTip"></div>
      <div class="spark-legend">
        <span><i class="swatch" style="background:var(--danger)"></i>BLOCK</span>
        <span><i class="swatch" style="background:var(--amber)"></i>LIMIT</span>
        <span><i class="swatch" style="background:var(--accent)"></i>sin acción</span>
        <span>bajo la línea del umbral, el modelo ve anomalía · pulsa un punto para filtrar su IP · pulsa una fila para ver su detalle</span>
      </div>
    </div>
    <p class="toolbar-hint" id="filterHint"></p>
    <div class="tbl-wrap tbl-scroll">
      <table>
        <thead><tr><th>Hora</th><th>Entidad</th><th>Decisión</th><th>Fuente</th><th>Motivo</th><th>Modelo <span class="th-sub">score frente al umbral</span></th><th class="r">Paquetes</th><th></th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>

<style>
/* ---- Recorrido guiado de la demo ---------------------------------------- */
.rg{position:fixed;left:calc(224px + 24px);right:24px;bottom:16px;z-index:150;background:linear-gradient(180deg,rgba(18,27,46,.97),rgba(12,19,34,.97));border:1px solid #2c3d63;border-radius:14px;box-shadow:0 18px 48px rgba(0,0,0,.55),0 0 0 1px rgba(94,234,212,.06);padding:10px 14px 10px;backdrop-filter:blur(6px)}
.rg[hidden]{display:none}
.rg-cab{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.rg-esc{font-weight:650;font-size:13.5px;color:var(--text)}
.rg-esc .k{color:var(--accent);font-family:var(--mono);font-size:11.5px;letter-spacing:.06em;margin-right:8px}
.rg-esc .ip{font-family:var(--mono);color:var(--text-dim);margin-left:8px;font-weight:500}
.rg-reloj{margin-left:auto;font-family:var(--mono);color:var(--accent);font-size:15px;font-weight:600}
.rg-x{background:none;border:none;color:var(--text-dim);font-size:20px;line-height:1;cursor:pointer;padding:0 2px}
.rg-x:hover{color:var(--text)}
.rg-pasos{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;counter-reset:tp}
.rg-pasos li{position:relative}
.rg-pasos button{width:100%;display:flex;align-items:center;gap:8px;background:#121b2e;border:1px solid #26334f;border-radius:10px;padding:7px 10px;color:var(--text-dim);font:inherit;font-size:13px;cursor:pointer;text-align:left;transition:border-color .15s,background .15s}
.rg-pasos button:hover{border-color:#3a5179;color:var(--text)}
.rg-pasos .num{flex:0 0 22px;height:22px;border-radius:50%;display:grid;place-items:center;font-family:var(--mono);font-size:12px;font-weight:700;background:#1c2742;color:var(--text-dim)}
.rg-pasos .lbl{display:flex;flex-direction:column;line-height:1.2;min-width:0}
.rg-pasos .lbl b{color:var(--text);font-weight:600;font-size:13px}
.rg-pasos .lbl small{font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rg-pasos li.ok .num{background:var(--ok);color:#06210f}
.rg-pasos li.alerta .num{background:var(--danger);color:#2a0606}
.rg-pasos li.limit .num{background:var(--amber);color:#2a1d02}
.rg-pasos li.actual button{border-color:var(--accent);background:#10283a;box-shadow:0 0 0 1px rgba(94,234,212,.25) inset}
.rg-pasos li:not(:last-child)::after{content:"";position:absolute;right:-6px;top:50%;width:6px;height:1px;background:#2c3d63}
.rg-pie{display:flex;align-items:center;gap:12px;margin-top:8px}
.rg-frase{margin:0;flex:1;font-size:14px;color:var(--text)}
.rg-cli{font-family:var(--mono);font-size:12px;color:#ffd58a;background:#2a2109;border:1px solid #5b4511;border-radius:8px;padding:4px 8px;white-space:nowrap;max-width:46%;overflow:hidden;text-overflow:ellipsis}
.rg-cli:empty{display:none}
.rg-cli .h{color:#c9a65a;margin-right:6px}
.rg-sig{background:var(--accent);color:#04201c;border:none;border-radius:9px;padding:7px 14px;font-weight:700;font-size:13px;cursor:pointer}
.rg-sig:hover{filter:brightness(1.08)}
.rg-abrir{position:fixed;right:24px;bottom:16px;z-index:150;background:#10283a;color:var(--accent);border:1px solid var(--accent);border-radius:999px;padding:7px 14px;font-weight:650;font-size:13px;cursor:pointer}
.rg-abrir[hidden]{display:none}
body.con-rg .wrap{padding-bottom:150px}
body.con-rg .toasts{bottom:150px}
.rg-foco{outline:2px solid var(--accent)!important;outline-offset:2px;animation:rgPulso 1.2s ease-in-out 4;border-radius:8px}
tr.rg-foco td{background:rgba(94,234,212,.10)!important}
@keyframes rgPulso{0%,100%{box-shadow:0 0 0 0 rgba(94,234,212,.0)}50%{box-shadow:0 0 0 6px rgba(94,234,212,.28)}}
@media (max-width:1100px){.rg{left:16px;right:16px}.rg-pasos .lbl small{display:none}}
.ver-codigo{margin-top:6px;background:#15202c;border:1px solid #2b3a4a;color:#9fd0ff;border-radius:7px;padding:4px 9px;font-size:11px;cursor:pointer}
.ver-codigo:hover{background:#1b2a39;border-color:#3a5169}
.code-modal{position:fixed;inset:0;background:rgba(2,6,12,.72);z-index:300;display:flex;align-items:center;justify-content:center;padding:22px}
.code-modal[hidden]{display:none}
.code-box{background:#0f1720;border:1px solid #27333f;border-radius:12px;width:min(1240px,96vw);height:90vh;display:flex;flex-direction:column;box-shadow:0 24px 70px rgba(0,0,0,.6)}
.code-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid #27333f;font-weight:600;color:#e6eef7}
.code-head button{background:none;border:none;color:#8aa0b2;font-size:24px;line-height:1;cursor:pointer}
.code-head button:hover{color:#fff}
/* Dos paneles: izquierda el codigo real + su ruta; derecha pseudocodigo y
   explicacion. Al pulsar un paso del pseudocodigo, el codigo salta a su parte. */
.code-panes{display:grid;grid-template-columns:1.7fr 1fr;min-height:0;flex:1}
.code-left{display:flex;flex-direction:column;min-height:0;border-right:1px solid #1b2530}
.code-right{display:flex;flex-direction:column;min-height:0;overflow:auto;padding:12px 14px}
.code-sub{padding:7px 16px;font:11px ui-monospace,Menlo,monospace;color:#7d93a6;border-bottom:1px solid #1b2530;overflow-wrap:anywhere;flex:none}
.code-pre{margin:0;padding:10px 0;overflow:auto;font:12px/1.6 ui-monospace,Menlo,Consolas,monospace;color:#d6e2ee;background:#0a1118;min-height:0;flex:1}
.cl{display:grid;grid-template-columns:46px 1fr;gap:10px;padding:0 14px;white-space:pre}
.cl .ln{color:#3a4a5c;text-align:right;user-select:none}
.cl.hl{background:#14314a}
.cl.hl .ln{color:#9fd0ff}
.code-rtit{font:600 .64rem ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:#7d93a6;margin-bottom:.45rem}
.code-explica{font-size:.84rem;color:#cdd9e5;margin-bottom:.9rem;line-height:1.5}
.code-pseudo{list-style:none;margin:0;padding:0;counter-reset:ps}
.code-pseudo li{counter-increment:ps;display:grid;grid-template-columns:20px 1fr;gap:9px;align-items:start;padding:7px 8px;border:1px solid transparent;border-radius:8px;cursor:pointer;font-size:.82rem;color:#d6e2ee}
.code-pseudo li::before{content:counter(ps);font:600 10px ui-monospace,monospace;color:#06251f;background:#5ee6c3;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;margin-top:1px}
.code-pseudo li.nolink{cursor:default;color:#7d93a6}
.code-pseudo li.nolink::before{background:#2b3a4a;color:#7d93a6}
.code-pseudo li:not(.nolink):hover{border-color:#2b3a4a;background:#13202c}
.code-pseudo li.sel{border-color:#5ee6c3;background:#122a28}
.code-pseudo li small{grid-column:2;display:block;color:#7d93a6;font-family:ui-monospace,monospace;font-size:10px;margin-top:2px;overflow-wrap:anywhere}
@media (max-width:820px){.code-panes{grid-template-columns:1fr;grid-template-rows:1.4fr 1fr}.code-left{border-right:none;border-bottom:1px solid #1b2530}}
/* Resaltado de sintaxis del panel izquierdo: colores que separan funciones de
   palabras clave, cadenas, comentarios y numeros. Pensados sobre el fondo del
   codigo (#0a1118); el nombre de una funcion (definida o llamada) resalta en
   turquesa para seguir el hilo de un fichero a otro. */
.t-kw{color:#c792ea}
.t-def{color:#5eead4;font-weight:600}
.t-call{color:#8fd3ff}
.t-str{color:#e0be87}
.t-com{color:#6f8296;font-style:italic}
.t-num{color:#f0996a}
.t-dec{color:#e0af68}
/* Pestañas del panel derecho: pseudocodigo vs diagrama de flujo. */
.code-tabs{display:flex;gap:5px;margin:2px 0 11px}
.code-tabs button{flex:1;font:600 .74rem var(--sans);padding:6px 8px;border:1px solid #27333f;background:#0f1a24;color:#8aa0b2;border-radius:7px;cursor:pointer}
.code-tabs button.active{background:#13302b;border-color:#2f6d5f;color:#8ff0d8}
/* "Como llegar": la ruta exacta y el comando para abrir/editar el fichero. */
.code-llegar{background:#0d1922;border:1px solid #1f2d3a;border-radius:8px;padding:8px 10px;margin-bottom:11px;font-size:.8rem;color:#aebfce}
.code-llegar b{color:#d6e2ee}
.code-llegar code{font-family:ui-monospace,monospace;color:#9fd0ff;font-size:.76rem;word-break:break-all}
.code-llegar .cmd{display:block;margin-top:6px;background:#07131b;border:1px solid #16222d;border-radius:6px;padding:5px 7px;color:#bfe3c9;font-family:ui-monospace,monospace;font-size:.74rem;overflow-x:auto;white-space:pre}
/* Diagrama de flujo del codigo: procesos, DECISIONES (rombo ambar con sus
   ramas si/no) y saltos a OTRO fichero (chip punteado, pulsable). */
.flj-tit{font-weight:600;color:#cdd9e5;margin:2px 0 9px;font-size:.86rem}
.flj{display:flex;flex-direction:column;gap:0}
.flj-n{border:1px solid #27333f;background:#0f1a24;border-radius:9px;padding:8px 11px;font-size:.81rem;color:#d6e2ee;line-height:1.4}
.flj-n .ln{float:right;color:#7d93a6;font:10px ui-monospace,monospace;margin-left:8px}
.flj-n.dec{border-color:#7f6523;background:#1b1507}
.flj-n.io{border-color:#2f5d6d;background:#0b1c22}
.flj-n.inicio,.flj-n.fin{border-color:#2f6d5f;background:#0e2420;font-weight:600;text-align:center}
.flj-n.archivo{border-style:dashed;border-color:#3a5169;background:#10202c;color:#9fd0ff;cursor:pointer}
.flj-n.archivo:hover{background:#172d3b;border-color:#4a6684}
.flj-n[data-ancla]{cursor:pointer}
.flj-n[data-ancla]:hover{border-color:#5ee6c3}
.flj-n .cond{color:#e3c879;font-family:ui-monospace,monospace;font-size:.72rem;margin-top:3px;white-space:normal}
.flj-n.archivo .cond{color:#9fd0ff}
.flj-ram{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.flj-ram span{font-size:.72rem;padding:1px 8px;border-radius:999px}
.flj-ram .si{background:#12271c;color:#7ee0a0;border:1px solid #1f6d3f}
.flj-ram .no{background:#211014;color:#e58a8a;border:1px solid #6d2f2f}
.flj-arrow{align-self:center;color:#45586b;font-size:15px;line-height:1.15;margin:2px 0}
</style>
<div class="code-modal" id="codeModal" hidden>
  <div class="code-box">
    <div class="code-head"><span id="codeTitle"></span><button id="codeClose" type="button" aria-label="Cerrar">&times;</button></div>
    <div class="code-panes">
      <div class="code-left">
        <div class="code-sub" id="codeSub"></div>
        <div class="code-pre" id="codeBody"></div>
      </div>
      <div class="code-right">
        <div class="code-llegar" id="codeLlegar"></div>
        <div class="code-tabs" id="codeTabs">
          <button type="button" data-ct="pseudo" class="active">Pseudocódigo</button>
          <button type="button" data-ct="flujo">Diagrama de flujo</button>
        </div>
        <div id="ctPseudo">
          <div class="code-rtit">Pseudocódigo y explicación</div>
          <div class="code-explica" id="codeExplica"></div>
          <ol class="code-pseudo" id="codePseudo"></ol>
        </div>
        <div id="ctFlujo" hidden>
          <div class="code-flujo" id="codeFlujo"></div>
        </div>
      </div>
    </div>
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
// Fluidez (3-nov). (a) Con la pestaña oculta no se sondea nada (salvo tareas de >= 1 min);
// al volver se refresca de inmediato. (b) Un innerHTML idéntico al último que se escribió
// en el mismo elemento no se vuelve a escribir: el navegador no reconstruye la tabla,
// no parpadea y no se pierden el hover, la selección ni la posición del scroll.
(() => {
  const nativo = window.setInterval.bind(window);
  window.setInterval = (fn, ms, ...a) => nativo(() => {
    if (document.hidden && (ms || 0) < 60000) return;
    fn(...a);
  }, ms);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && typeof refresh === 'function') refresh();
  });
  const d = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  const ultimo = new WeakMap();
  Object.defineProperty(Element.prototype, 'innerHTML', {
    configurable: true, enumerable: d.enumerable, get: d.get,
    set(v) {
      const s = String(v), u = ultimo.get(this);
      if (u && s !== '' && u.html === s && this.childElementCount === u.n && this.firstElementChild === u.primero) return;
      d.set.call(this, s);
      ultimo.set(this, { html: s, n: this.childElementCount, primero: this.firstElementChild });
    },
  });
})();
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
  if_limpio_2026_10: 'modelo limpio (IsolationForest)',
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
const PROTO = { 112: 'VRRP/CARP (latido del router)', 240: 'pfsync (sincronización entre routers)' };
const BASE_TITLE = document.title;
const BASE_FAVICON = document.getElementById('favicon').href;
const ALERT_FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='13' fill='%235eead4'/%3E%3Ccircle cx='24' cy='9' r='7' fill='%23f87171' stroke='%230a0f1a' stroke-width='1.5'/%3E%3C/svg%3E";
const seenDecisionKeys = new Set();
let unseenAlertCount = 0;
let sessionStart = true; // evita contar todo el historial como "nuevo" en la primera carga

// Decisiones que llegaron en este refresco (para resaltar su fila).
let nuevasClaves = new Set();

function markSeenAndCountNewAlerts(decisions) {
  let newAlerts = 0;
  const nuevas = [];
  nuevasClaves = new Set();
  for (const d of decisions) {
    const key = d.entity_ip + '|' + d.window_end_utc;
    if (seenDecisionKeys.has(key)) continue;
    seenDecisionKeys.add(key);
    if (sessionStart) continue;
    nuevasClaves.add(key);
    // Se avisa por ACCION: un heuristico puede pedir BLOCK con el modelo en PERMIT.
    if (accionDeDecision(d) !== 'PERMIT') { newAlerts++; nuevas.push(d); }
  }
  sessionStart = false;
  if (nuevas.length) avisar(nuevas);
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

// ---- Anomalias marginales ------------------------------------------------
// Una anomalia SOLO del modelo cuyo score queda a menos de MARGEN_MARGINAL por
// debajo del umbral. Es real (esta en el registro y su LIMIT se publica), pero
// es ruido de borde: no se avisa con tarjeta flotante y Alertas la agrupa,
// diciendo siempre cuantas hay. Una regla disparada nunca es marginal.
const MARGEN_MARGINAL = 0.0;   // motor de las campañas (demo: 0.05)
function esMarginal(d) {
  if (!d || d.decision !== 'ALERT' || String(d.detector_name || '').endsWith('_heuristic')) return false;
  if (d.heuristico && (d.heuristico.accion === 'BLOCK' || d.heuristico.accion === 'LIMIT')) return false;
  if (d.score == null || d.threshold == null) return false;
  return d.score >= d.threshold - MARGEN_MARGINAL;
}
let verMarginales = false;

// ---- Escenario en vivo -------------------------------------------------------
// Un escenario por capa (y uno de falso positivo). El panel NO ejecuta nada:
// muestra el comando y sigue a la IP con /api/escenario cada 3 s. La aplicacion
// en el host no se afirma: el panel no lee el nftables del servidor.
const ESC_CATALOGO = [
  { id: 'l4', capa: 'L4 · Transporte', tipo: 'ataque', nombre: 'Escaneo de puertos',
    simula: 'Reconocimiento: prueba miles de puertos TCP para ver cuáles están abiertos.',
    desde: 'Kali · 10.10.20.30', ip: '10.10.20.30',
    comando: 'nmap -sT -T4 --max-retries 1 -p 1-3000 --open 10.10.30.10',
    espera: 'Regla port_scan → BLOCK hacia srv-dmz (en modo sombra se publica, no se aplica).',
    guion: ['Primer paso de casi cualquier intrusión: descubrir puertos abiertos.',
            'La regla port_scan lo ve: muchos puertos distintos, casi ninguna conexión completa. El modelo es solo señal.',
            'BLOCK firmado y con caducidad en el feed v2. En modo sombra el agente de srv-dmz no lo escribe en nftables.'],
    tour: { ataque: 'nmap prueba 3000 puertos TCP del servidor.',
            actividad: 'La Kali sube arriba con BLOCK.',
            decisiones: 'Regla port_scan, ventana a ventana (el score del IF, como señal).',
            respuestas: 'BLOCK firmado en el feed v2, con caducidad.',
            host: 'Modo sombra: el servidor sigue contestando (la medida no se aplica).' } },
  { id: 'l7', capa: 'L7 · Aplicación', tipo: 'ataque', nombre: 'Abuso HTTP (flood)',
    simula: 'Cientos de peticiones web en segundos desde una IP, como un bot.',
    desde: 'Kali · 10.10.20.30', ip: '10.10.20.30',
    comando: 'seq 1 900 | xargs -P20 -I{} curl -s -o /dev/null http://10.10.30.10/',
    espera: 'Regla http_abuse (≥ 600 peticiones en 60 s) → LIMIT hacia srv-dmz (en modo sombra se publica, no se aplica).',
    guion: ['Cada petición es válida; lo anómalo es la tasa.',
            'La regla http_abuse cuenta peticiones por minuto de una sola IP: dispara desde 600.',
            'LIMIT: respuesta proporcional, temporal y reversible.'],
    tour: { ataque: '900 peticiones web en paralelo contra el servidor.',
            actividad: 'La Kali aparece con LIMIT.',
            decisiones: 'http_abuse: ≥ 600 peticiones en 60 s.',
            respuestas: 'LIMIT firmado en el feed v2, con caducidad.',
            host: 'Modo sombra: el servidor sigue atendiendo (la medida no se aplica).' } },
  { id: 'brute', capa: 'L7 · Aplicación', tipo: 'ataque', nombre: 'Fuerza bruta HTTP',
    simula: 'Ráfaga de logins fallidos contra un endpoint que exige autenticación (401).',
    desde: 'Kali · 10.10.20.30', ip: '10.10.20.30',
    comando: 'for i in $(seq 1 120); do curl -s -o /dev/null -u x:x http://10.10.30.10:8081/; done',
    espera: 'Regla brute_force (≥ 5 req HTTP/60 s y ≥ 80 % de fallo de auth 401/403) → BLOCK hacia srv-dmz.',
    guion: ['Muchos intentos de login casi todos fallidos (401): la huella de un ataque de credenciales.',
            'El modelo mide flojo este patrón; quien lo caza es la regla brute_force (ratio de fallos de auth).',
            'BLOCK firmado y con caducidad. Es el valor del híbrido: el heurístico tapa el hueco del modelo.'],
    tour: { ataque: '120 intentos de login fallidos contra el endpoint 8081.',
            actividad: 'La Kali sube con BLOCK.',
            decisiones: 'brute_force: ≥ 80 % de 401 en 60 s.',
            respuestas: 'BLOCK firmado en el feed v2, con caducidad.',
            host: 'Con enforcement: la IP cae en nftables del servidor; en sombra solo se publica.' } },
  { id: 'l3', capa: 'L3 · Red', tipo: 'ataque', nombre: 'Inundación ICMP',
    simula: 'Un equipo satura al servidor con pings: denegación de servicio en capa de red.',
    desde: 'Kali · 10.10.20.30 (sin sudo)', ip: '10.10.20.30',
    comando: 'for k in 1 2 3 4; do ping -q -i 0.002 -s 1200 -w 60 10.10.30.10 >/dev/null & done; wait',
    espera: 'El motor actual no tiene regla ICMP: solo el modelo lo ve (ALERT) y la política if_senal no publica medida. Muestra la señal del IF, no una respuesta.',
    guion: ['Capa de red: ≈ 2000 paquetes ICMP por segundo.',
            'El modelo ve el volumen anómalo (ALERT); ninguna regla lo cubre.',
            'Sin medida: con la política if_senal el modelo solo es señal. Es un límite declarado del alcance.'],
    tour: { ataque: '4 pings en paralelo: ≈ 2000 paquetes/s de ICMP.',
            actividad: 'La Kali aparece con ALERT del modelo, sin acción.',
            decisiones: 'Score del IF bajo el umbral; ninguna regla.',
            respuestas: 'Sin medida en el feed.',
            host: 'El ping sigue pasando.' } },
  { id: 'l7dns', capa: 'L7 · Aplicación', tipo: 'ataque', nombre: 'DNS de alta entropía (DGA)',
    simula: 'Malware que busca su servidor de control con nombres aleatorios.',
    desde: 'Kali · 10.10.20.30', ip: '10.10.20.30',
    comando: 'for i in $(seq 1 80); do r=$(head -c6 /dev/urandom | od -An -tx1 | tr -d " \\n"); dig +short ${r}.francos-sac.com @10.10.10.20 >/dev/null 2>&1; sleep 0.5; done',
    espera: 'Regla dns_entropy (≥ 30 consultas en 60 s, nombres únicos o NXDOMAIN) → LIMIT de DNS hacia DC1. El modelo lo ve casi normal.',
    guion: ['Nombres de dominio aleatorios: la huella de un DGA.',
            'El modelo lo ve casi normal; la regla de entropía DNS, no.',
            'Modelo y reglas se complementan.'],
    tour: { ataque: '80 consultas DNS a nombres aleatorios.',
            actividad: 'La Kali aparece con LIMIT por regla.',
            decisiones: 'dns_entropy: NXDOMAIN y nombres únicos.',
            respuestas: 'LIMIT firmado en el feed v2, destino DC1 (DNS).',
            host: 'Modo sombra: DC1 sigue resolviendo (la medida no se aplica).' } },
  { id: 'fp', capa: 'L7 · Aplicación', tipo: 'tráfico legítimo', nombre: 'Cliente legítimo intenso',
    simula: 'Un usuario real navegando sin parar: una página cada 2 s durante 2 minutos.',
    desde: 'VM clientes · 10.10.20.21', ip: '10.10.20.21',
    comando: 'for i in $(seq 1 60); do curl -s -o /dev/null --interface 10.10.20.21 http://10.10.30.10/; sleep 2; done',
    espera: 'PERMIT de principio a fin: ninguna regla, el modelo no lo sostiene. No se toca al usuario.',
    guion: ['Tráfico legítimo, pero intenso: el caso que más falsos positivos da.',
            'Ninguna regla salta y el modelo no ve una anomalía sostenida.',
            'PERMIT: el usuario sigue trabajando. Antes esto se bloqueaba; se corrigió y se midió.'],
    tour: { ataque: 'Navegación continua: 1 página cada 2 s, 2 minutos.',
            actividad: 'La IP .21 NO aparece con acción.',
            decisiones: 'Todas sus ventanas: PERMIT (marginales sin acción).',
            respuestas: 'Sin respuesta para .21: nada que caducar.',
            host: 'En srv-dmz: «sin regla» para .21; el ping pasa 0 % de pérdida.' } },
];

let esc = null;                  // {id, ip, t0} mientras hay seguimiento
try { esc = JSON.parse(localStorage.getItem('cf_escenario') || 'null'); } catch (e) { esc = null; }
// Un seguimiento de demo dura minutos. Si el guardado tiene mas de 30 min es de
// otra sesion (p.ej. 314:54 en el Resumen): se descarta en vez de mostrarlo.
const ESC_CADUCA_S = 1800;
if (esc && esc.t0 && Date.now() / 1000 - esc.t0 > ESC_CADUCA_S) {
  esc = null;
  try { localStorage.removeItem('cf_escenario'); } catch (e) { /* sin persistir */ }
}
let escSel = (esc && esc.id) || 'l4';
let escDatos = null, escFeedVisto = null, escVistas = new Set(), escError = '';
function escActivo() { return !!(esc && esc.t0 && esc.ip); }
function escGuardar() { try { localStorage.setItem('cf_escenario', JSON.stringify(esc)); } catch (e) { /* sin persistir */ } }
function escMmss(s) { s = Math.max(0, Math.round(s)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }
function escDelta(t) { return escActivo() && t ? ' · +' + escMmss(t - esc.t0) : ''; }

function renderEscCards() {
  const cont = document.getElementById('escCards');
  if (!cont) return;
  cont.innerHTML = ESC_CATALOGO.map(s => '<button type="button" class="esc-card' + (s.id === escSel ? ' sel' : '')
    + (s.tipo === 'tráfico legítimo' ? ' fp' : '') + '" data-esc="' + s.id + '">'
    + '<span class="esc-capa">' + varEsc(s.capa) + '</span><b>' + varEsc(s.nombre) + '</b>'
    + '<small>' + (s.tipo === 'tráfico legítimo' ? 'debe quedar en PERMIT' : 'ataque simulado') + '</small></button>').join('');
}

function renderEscDetalle() {
  const det = document.getElementById('escDet');
  const s = ESC_CATALOGO.find(x => x.id === escSel);
  if (!det || !s) return;
  det.innerHTML = '<div class="esc-box"><span class="k">' + varEsc(s.capa) + ' · ' + varEsc(s.tipo) + '</span>'
    + '<h3>' + varEsc(s.nombre) + '</h3><p>' + varEsc(s.simula) + '</p>'
    + '<p><span class="k">Desde</span> ' + varEsc(s.desde) + '</p>'
    + '<div class="esc-cmd"><code>' + varEsc(s.comando) + '</code>'
    + '<button type="button" class="btn-sec neutro esc-copiar" data-cmd="' + varEsc(s.comando) + '">copiar</button></div>'
    + '<p><span class="k">Qué esperamos</span> ' + varEsc(s.espera) + '</p></div>';
  const ip = document.getElementById('escIp');
  if (ip && !escActivo()) ip.value = s.ip;
}

function escPaso(n, titulo, estado, cuerpo, hora, donde) {
  return '<li class="esc-paso ' + estado + '"><h4><span>' + titulo + '</span><span class="n">' + n + '</span></h4>'
    + cuerpo + (hora ? '<span class="t">' + hora + '</span>' : '') + (donde ? '<span class="dnd">' + donde + '</span>' : '') + '</li>';
}

function renderEscPasos() {
  const ol = document.getElementById('escPasos');
  if (!ol) return;
  const D = escDatos;
  const activo = escActivo();
  const ahora = Date.now() / 1000;
  const filas = (D && D.decisiones) || [];
  const conAccion = filas.filter(f => f.accion !== 'PERMIT');
  const claras = conAccion.filter(f => !f.marginal);
  const legit = activo && (ESC_CATALOGO.find(x => x.id === esc.id) || {}).tipo === 'tráfico legítimo';
  // 1. Llegan datos
  let p1;
  if (!D) p1 = escPaso('1', 'Llegan datos', 'espera', 'Consultando el motor…');
  else {
    const edad = D.ultima_decision ? ahora - D.ultima_decision : null;
    const vivo = edad != null && edad < 30;
    p1 = escPaso('1', 'Llegan datos', vivo ? 'ok' : 'espera',
      vivo ? 'Sí: ' + D.decisiones_60s + ' ventanas analizadas en el último minuto, de ' + D.ips_60s + ' IP.'
           : 'No hay decisiones recientes del motor.',
      edad != null ? 'última ventana hace ' + Math.round(edad) + ' s' : '', 'Resumen · Actividad');
  }
  // 2. Deteccion
  let p2;
  if (!activo) p2 = escPaso('2', 'Detección', 'inactivo', 'Pulsa «Iniciar seguimiento» al lanzar el comando.');
  else if (!filas.length) p2 = escPaso('2', 'Detección', 'espera', 'La IP ' + varEsc(esc.ip) + ' aún no aparece en las ventanas.');
  else if (!conAccion.length) p2 = escPaso('2', 'Detección', 'espera', filas.length + ' ventana(s) de la IP analizadas; todas normales por ahora.', 'primera ventana ' + fmtTime(filas[filas.length - 1].logged_at) + escDelta(filas[filas.length - 1].logged_at), 'Actividad');
  else {
    const pr = (claras.length ? claras : conAccion).reduce((a, b) => (a.logged_at < b.logged_at ? a : b));
    p2 = escPaso('2', 'Detección', 'ok', 'Detectada: ' + conAccion.length + ' de ' + filas.length + ' ventanas con acción'
      + (claras.length ? '' : ' (todas marginales)') + '.', 'primera ' + fmtTime(pr.logged_at) + escDelta(pr.logged_at), 'Actividad · Alertas');
  }
  // 3. Decision: quien y que
  let p3;
  if (!activo || !conAccion.length) p3 = escPaso('3', 'Decisión', activo ? 'espera' : 'inactivo', activo ? 'Esperando una ventana con acción.' : '—');
  else {
    const sev = { BLOCK: 2, LIMIT: 1 };
    const peor = conAccion.reduce((a, b) => ((sev[b.accion] || 0) > (sev[a.accion] || 0) ? b : a));
    const hayModelo = conAccion.some(f => f.decision === 'ALERT');
    const hayRegla = conAccion.some(f => f.heuristico && f.heuristico.heuristico);
    const quien = hayModelo && hayRegla ? 'modelo y regla' : (hayRegla ? 'regla' : 'modelo');
    const conScore = filas.filter(f => f.score != null);
    const minimo = conScore.length ? conScore.reduce((a, b) => (a.score < b.score ? a : b)) : null;
    // el motivo que se enseña es el de la ventana que fijó la acción más severa
    const regla = (peor.heuristico && peor.heuristico.heuristico) ? peor
      : conAccion.find(f => f.heuristico && f.heuristico.heuristico);
    const prim = conAccion.reduce((a, b) => (a.logged_at < b.logged_at ? a : b));
    const escalo = prim.accion !== peor.accion;
    p3 = escPaso('3', 'Decisión', 'ok', '<span class="badge acc-' + peor.accion.toLowerCase() + '">' + peor.accion + '</span> por <b>' + quien + '</b> <span class="esc-hist">(la más severa del seguimiento)</span>'
      + (escalo ? '<br><span class="esc-hist">escaló de ' + prim.accion + ' (' + fmtTime(prim.logged_at) + ') a ' + peor.accion + '</span>' : '')
      + (regla ? '<br>' + varEsc(regla.heuristico.heuristico) + ': ' + varEsc(regla.heuristico.motivo || '') : '')
      + (minimo ? '<br>score mínimo ' + minimo.score.toFixed(3) + ' · umbral ' + Number(minimo.threshold).toFixed(3) : ''),
      fmtTime(peor.logged_at) + escDelta(peor.logged_at), 'Alertas · Decisiones');
  }
  // 4. Publicacion en el feed firmado
  let p4;
  const ent = D && D.feed && D.feed.entrada;
  if (ent && activo && !escFeedVisto) escFeedVisto = ahora;
  if (!activo) p4 = escPaso('4', 'Publicación', 'inactivo', '—');
  else if (ent) p4 = escPaso('4', 'Publicación', 'ok', 'En el feed firmado: <b>' + varEsc(ent.accion) + '</b> · ' + varEsc(ent.motivo || '')
      + '<br>caduca ' + fmtTime(ent.hasta)
      + (ent.nivel > 1 ? '<br><span class="esc-hist">reincidencia nivel ' + ent.nivel + ': la IP ya tuvo episodios en las últimas 24 h, por eso dura más</span>' : ''),
      'feed de las ' + fmtTime(D.feed.generado) + (escFeedVisto ? escDelta(escFeedVisto) : ''), 'Respuestas');
  else if (D && conAccion.length) {
    // La accion de ESTE seguimiento (no la vigente del historial de 24 h, que puede ser otra).
    const accEsc = conAccion.some(f => f.accion === 'BLOCK') ? 'BLOCK' : 'LIMIT';
    const libEsc = ((D.aplicacion) || []).some(a => (a.eventos || []).some(e => e.evento === 'liberada'));
    p4 = libEsc
      ? escPaso('4', 'Publicación', 'ok', 'La orden <b>' + accEsc + '</b> se publicó y ya salió del feed: la IP fue liberada por revisión humana (paso 5).', '', 'Respuestas')
      : escPaso('4', 'Publicación', 'espera', 'Decidida (' + accEsc + '); esperando el próximo feed (cada 10 s).', '', 'Respuestas');
  }
  else p4 = escPaso('4', 'Publicación', activo && conAccion.length ? 'espera' : 'inactivo', 'Aún no está en el feed.', D && D.feed ? 'feed de las ' + fmtTime(D.feed.generado) : '');
  // 5. Aplicacion: lo que el host dice tener en nftables (acuse que trae el relay)
  let p5 = escPaso5(D, activo, ent);
  // Trafico legitimo: el exito es que NO pase nada. Verde cuando hay ventanas
  // de la IP y ninguna pide accion.
  if (legit && filas.length && !conAccion.length) {
    const marg = filas.filter(f => f.politica_modelo === 'marginal' || f.politica_modelo === 'suelta').length;
    p2 = escPaso('2', 'Detección', 'ok', '<b>Sin detección</b>: ' + filas.length + ' ventanas, todas PERMIT.', 'correcto: es un usuario legítimo', 'Actividad');
    p3 = escPaso('3', 'Decisión', 'ok', '<span class="badge acc-permit">PERMIT</span> ninguna regla salta'
      + (marg ? '<br><span class="esc-hist">' + marg + ' anomalía(s) marginal/suelta del modelo: se registran, no actúan</span>' : '<br>el modelo lo ve normal'), '', 'Decisiones');
    p4 = escPaso('4', 'Publicación', 'ok', 'Nada que publicar: la IP no está en el feed.', D && D.feed ? 'feed de las ' + fmtTime(D.feed.generado) : '', 'Respuestas');
    p5 = escPaso('5', 'Aplicación en el host', 'ok', '<b>srv-dmz: sin regla</b> para ' + varEsc(esc.ip) + '. El usuario no se ve afectado.', '', 'según el host · relay cada 10 s');
  }
  ol.innerHTML = p1 + p2 + p3 + p4 + p5;
}

const ESC_EVENTO = { aplicada: 'aplicada', cambiada: 'cambiada a', retirada: 'retirada', liberada: 'liberada por un humano' };

function escPaso5(D, activo, ent) {
  if (!D) return escPaso('5', 'Aplicación en el host', 'espera', 'Consultando el acuse de los hosts…');
  const apl = D.aplicacion;
  if (apl == null) return escPaso('5', 'Aplicación en el host', 'ext',
    'Sin acuse de los hosts: el panel no lee su nftables. Se comprueba en el host.', '', 'srv-dmz: mira-agente.sh');
  if (!apl.length) return escPaso('5', 'Aplicación en el host', 'espera',
    'Ningún host protegido ha enviado su acuse todavía.', '', 'acuse del host · relay cada 10 s');
  let estado = 'espera', hora = '';
  const partes = apl.map(a => {
    const evs = (a.eventos || []);
    const hist = evs.length ? '<br><span class="esc-hist">' + evs.slice(-4).map(e => fmtTime(e.t) + ' ' + (ESC_EVENTO[e.evento] || e.evento)
      + (e.accion ? ' ' + varEsc(e.accion) : '')).join(' · ') + '</span>' : '';
    const quien = '<b>' + varEsc(a.host) + '</b>';
    if (a.error) return quien + ': no pudo leer sus reglas nftables (' + varEsc(a.error) + ').';
    if (a.atrasado) return quien + ': acuse atrasado' + (a.edad != null ? ' (hace ' + Math.round(a.edad) + ' s)' : '') + '.' + hist;
    if (a.agente && a.agente !== 'active') return quien + ': agente EN SOMBRA (' + varEsc(a.agente) + '): recibe la orden, no la aplica.' + hist;
    const liberadaYa = evs.some(e => e.evento === 'liberada') || String(a.fuera_de_alcance || '').startsWith('liberada');
    if (a.fuera_de_alcance && !a.regla && !liberadaYa)
      return quien + ': no se aplica, la IP está fuera de su alcance (' + varEsc(a.fuera_de_alcance) + ').' + hist;
    if (liberadaYa && !a.regla) {
      estado = 'ok';
      const lb = evs.filter(e => e.evento === 'liberada').pop();
      if (lb && activo) hora = 'liberada ' + fmtTime(lb.t) + escDelta(lb.t);
      return quien + ': <b>sin regla</b>, liberada por revisión humana. Las ventanas tardías del mismo episodio no la vuelven a poner.' + hist;
    }
    if (a.regla) {
      estado = 'ok';
      const ap = evs.filter(e => e.evento === 'aplicada' || e.evento === 'cambiada').pop();
      if (ap && activo) hora = 'aplicada ' + fmtTime(ap.t) + escDelta(ap.t);
      return '<span class="badge acc-' + a.regla.accion.toLowerCase() + '">' + varEsc(a.regla.accion) + '</span> en el nftables de ' + quien
        + (a.regla.expira ? ' · se quita sola a las ' + fmtTime(a.regla.expira) : '') + hist;
    }
    const lib = evs.filter(e => e.evento === 'liberada').pop();
    if (lib) {
      estado = 'ok';
      if (activo) hora = 'liberada ' + fmtTime(lib.t) + escDelta(lib.t);
      return quien + ': <b>sin regla</b>, liberada por revisión humana. No se reaplica salvo reincidencia.' + hist;
    }
    if (ent && activo) return quien + ': orden publicada; el agente aún no la aplica (la recoge cada 10 s).' + hist;
    return quien + ': sin regla para esta IP (pasa libre).' + hist;
  });
  const edad = apl.map(a => a.edad).filter(x => x != null);
  return escPaso('5', 'Aplicación en el host', activo ? estado : (estado === 'ok' ? 'ok' : 'inactivo'),
    partes.join('<br>'), hora || (edad.length ? 'acuse de hace ' + Math.round(Math.min.apply(null, edad)) + ' s' : ''),
    'según el host · relay cada 10 s');
}

function renderEscFilas() {
  const cont = document.getElementById('escFilas');
  const sub = document.getElementById('escFilasSub');
  if (!cont) return;
  const filas = (escDatos && escDatos.decisiones) || [];
  if (sub) sub.textContent = escActivo() ? 'de ' + esc.ip + ' desde ' + fmtTime(esc.t0) + ' · en vivo, cada 3 s'
    : 'de ' + ((document.getElementById('escIp') || {}).value || '') + ' en los últimos 2 min';
  if (escError) { cont.innerHTML = '<p class="estado-vacio">No se pudo consultar: ' + varEsc(escError) + '</p>'; return; }
  if (!filas.length) { cont.innerHTML = '<p class="estado-vacio">Sin ventanas de esta IP en el periodo.</p>'; return; }
  // Ventanas iguales del mismo instante (los tres tamaños de ventana, o varias
  // sin score) se agrupan en una fila «×N»: la tabla cuenta lo que cambia.
  const grupos = [];
  for (const f of filas.slice(0, 120)) {
    const mot = f.heuristico && f.heuristico.heuristico ? varEsc(f.heuristico.heuristico) + ': ' + varEsc(f.heuristico.motivo || '')
      : (f.cadena_v2 && f.decision === 'ALERT') ? 'IF del motor: ALERT · ' + varEsc(TXT_MEDIDA_V2[(f.cadena_v2.medida || {}).estado] || 'medida desconocida')
      : (f.decision === 'ALERT' ? (f.politica_modelo === 'marginal' ? 'anomalía marginal del modelo · sin acción' : (f.politica_modelo === 'suelta' ? 'anomalía suelta del modelo · sin acción' : 'anomalía sostenida del modelo · para revisión humana')) : (f.score == null ? 'sin score (poco tráfico)' : 'normal para el modelo'));
    const clave = fmtTime(f.logged_at) + '|' + f.accion + '|' + mot + '|' + (f.marginal ? 1 : 0);
    const ult = grupos[grupos.length - 1];
    if (ult && ult.clave === clave) { ult.n += 1; ult.keys.push(f.logged_at + '|' + f.window_end_utc); continue; }
    grupos.push({ clave: clave, f: f, mot: mot, n: 1, keys: [f.logged_at + '|' + f.window_end_utc] });
  }
  cont.innerHTML = grupos.slice(0, 30).map(g => {
    const f = g.f;
    const nueva = g.keys.some(k => !escVistas.has(k));
    g.keys.forEach(k => escVistas.add(k));
    return '<div class="esc-fila' + (nueva ? ' nueva' : '') + '"><span class="hora">' + fmtTime(f.logged_at) + '</span>'
      + '<span><span class="badge acc-' + String(f.accion).toLowerCase() + '">' + f.accion + '</span></span>'
      + '<span>' + miniBarraScore(f.score) + '</span>'
      + '<span>' + g.mot + (g.n > 1 ? ' <b class="esc-x">×' + g.n + '</b>' : '')
      + (f.marginal ? '<span class="tag-marg">marginal</span>' : '') + '</span></div>';
  }).join('');
}

function renderEscReloj() {
  const r = document.getElementById('escReloj');
  const e = document.getElementById('escEstado');
  if (r) r.textContent = escActivo() ? escMmss(Date.now() / 1000 - esc.t0) : '';
  if (e) e.textContent = escActivo() ? 'Siguiendo ' + esc.ip + ' desde las ' + fmtTime(esc.t0) : '';
  const bI = document.getElementById('escIniciar'), bP = document.getElementById('escParar');
  if (bI) bI.textContent = escActivo() ? 'Reiniciar' : 'Iniciar seguimiento';
  if (bP) bP.hidden = !escActivo();
}

let escEnVuelo = null;
async function escConsultar() {
  const sec = document.getElementById('s-escenario');
  const visible = sec && sec.classList.contains('pag-activa');
  if (!visible && !escActivo()) return;
  const ip = escActivo() ? esc.ip : ((document.getElementById('escIp') || {}).value || '').trim();
  if (!ip) return;
  const desde = escActivo() ? esc.t0 - 5 : Date.now() / 1000 - 120;
  const t0 = escActivo() ? esc.t0 : null;
  // Una respuesta que llega tarde (de la IP o el seguimiento anterior) no se
  // pinta: sin esto, al cambiar de .30 a .21 los pasos mostraban datos de .30.
  const vigente = () => (escActivo() ? (esc.ip === ip && esc.t0 === t0)
    : ((document.getElementById('escIp') || {}).value || '').trim() === ip);
  // Sin solapes: si el panel tarda, no se apilan peticiones cada 3 s.
  const clave = ip + '|' + t0;
  if (escEnVuelo === clave) return;
  escEnVuelo = clave;
  setTimeout(() => { if (escEnVuelo === clave) escEnVuelo = null; }, 20000);
  try {
    const r = await fetch('/api/escenario?ip=' + encodeURIComponent(ip) + '&desde=' + desde.toFixed(0));
    const d = await r.json();
    if (!vigente()) return;
    if (d.error) { escError = d.error; } else { escError = ''; escDatos = d; }
  } catch (e) {
    if (!vigente()) return;
    escError = 'sin conexión con el panel';
    if (escDatos && escDatos.ip !== ip) escDatos = null;
  } finally {
    if (escEnVuelo === clave) escEnVuelo = null;
  }
  if (!vigente()) return;
  renderEscPasos();
  renderEscFilas();
}

function escIniciar() {
  const ip = ((document.getElementById('escIp') || {}).value || '').trim();
  if (!/^\\d{1,3}(\\.\\d{1,3}){3}$/.test(ip)) { const e = document.getElementById('escEstado'); if (e) e.textContent = 'Escribe una IP válida.'; return; }
  esc = { id: escSel, ip: ip, t0: Date.now() / 1000 };
  if (typeof rgPaso !== 'undefined') { rgPaso = 0; rgOculto = false; }
  escFeedVisto = null; escDatos = null; escVistas = new Set();
  escGuardar(); renderEscReloj(); renderEscPasos(); renderEscFilas(); escConsultar();
}

on('escCards', 'click', (ev) => {
  const b = ev.target.closest('.esc-card');
  if (!b) return;
  escSel = b.dataset.esc;
  renderEscCards(); renderEscDetalle();
  if (!escActivo()) { escDatos = null; escVistas = new Set(); escConsultar(); }
});
on('escDet', 'click', async (ev) => {
  const b = ev.target.closest('.esc-copiar');
  if (!b) return;
  try { await navigator.clipboard.writeText(b.dataset.cmd); b.textContent = 'copiado ✓'; }
  catch (e) { b.textContent = 'copia manual'; }
  setTimeout(() => { b.textContent = 'copiar'; }, 1500);
});
on('escIniciar', 'click', escIniciar);

// «Preparar demo»: el panel deja una petición; el publicador la mete en el feed FIRMADO;
// el agente de srv-dmz la verifica, libera las IP de la demo y lo confirma en su acuse.
let prepTimer = null;
function renderPrep(d) {
  const ul = document.getElementById('prepLista'), txt = document.getElementById('prepTxt'), box = document.getElementById('prep');
  if (!ul || !d) return;
  ul.innerHTML = (d.checks || []).map(c => '<li class="' + c.estado + '"><span class="ic">'
    + ({ ok: '✔', esp: '…', mal: '✘' }[c.estado] || '·') + '</span><span>' + varEsc(c.texto)
    + (c.detalle ? ' <small>' + varEsc(c.detalle) + '</small>' : '') + '</span></li>').join('');
  if (box) box.classList.toggle('listo', !!d.listo);
  if (txt && d.peticion) txt.innerHTML = d.listo
    ? '<b>Listo para la demo.</b> Elige un escenario y pulsa «Iniciar».'
    : 'Preparando… (feed firmado → srv-dmz → acuse, unos 30–40 s)';
}
async function prepSondear(fin) {
  clearTimeout(prepTimer);
  let d = null;
  try { d = await (await fetch('/api/demo/estado')).json(); } catch (e) { /* reintenta */ }
  if (d) renderPrep(d);
  const b = document.getElementById('prepBtn');
  if (d && d.listo || Date.now() > fin) { if (b) b.disabled = false; return; }
  prepTimer = setTimeout(() => prepSondear(fin), 3000);
}
async function prepPedir() {
  const b = document.getElementById('prepBtn'), ul = document.getElementById('prepLista');
  if (b) b.disabled = true;
  try {
    const r = await fetch('/api/demo/preparar', { method: 'POST', headers: { 'X-CyberFlow': '1' } });
    if (!r.ok) throw new Error(r.status === 403 ? 'Solo un administrador puede preparar la demo.' : 'HTTP ' + r.status);
    esc = null; escGuardar(); renderEscReloj(); renderEscPasos(); renderEscFilas();
    vistaLimpiaDesde(Date.now() / 1000);
    if (typeof rgOculto !== 'undefined') { rgOculto = false; }
    prepSondear(Date.now() + 120000);
  } catch (e) {
    if (ul) ul.innerHTML = '<li class="mal"><span class="ic">✘</span><span>' + varEsc(e.message) + '</span></li>';
    if (b) b.disabled = false;
  }
}
on('prepBtn', 'click', prepPedir);

// «Dejar limpio» (cadena v2, 16-nov): deja el control D5 (reset_origen de la Kali); el
// publicador lo consume, quita sus medidas vigentes y su escalada, republica el feed y acusa.
// Además se borra el seguimiento de escenario del panel. No toca umbrales ni reglas.
let limpTimer = null;
function pintarLimpieza(items, listo) {
  const ul = document.getElementById('prepLista'), txt = document.getElementById('prepTxt');
  if (ul) ul.innerHTML = items.map(([est, t]) => '<li class="' + est + '"><span class="ic">'
    + ({ ok: '✔', esp: '…', mal: '✘' }[est] || '·') + '</span><span>' + t + '</span></li>').join('');
  if (txt && listo) txt.innerHTML = '<b>Limpio.</b> Elige un escenario y pulsa «Iniciar».';
}
async function limpiezaSondear(id, fin) {
  clearTimeout(limpTimer);
  let d = null;
  try { d = await (await fetch('/api/demo/limpieza?id=' + encodeURIComponent(id))).json(); } catch (e) { /* reintenta */ }
  const b = document.getElementById('limpiarBtn');
  if (d) {
    const ack = d.ack;
    const items = [['ok', 'Petición dejada al publicador'],
      ack ? (ack.ok ? ['ok', 'Publicador: estado de la Kali limpio, feed n.º ' + varEsc(String(ack.secuencia ?? '—'))
                       + ' (' + ((ack.quitado || {}).vigentes || []).length + ' medida(s) retirada(s))']
                    : ['mal', 'Publicador: ' + varEsc(ack.error || 'rechazada')])
          : ['esp', 'Esperando al publicador…'],
      d.kali_en_feed === false ? ['ok', 'Feed sin medidas sobre la Kali ni el cliente'] : ['esp', 'El feed aún tiene una medida sobre la Kali o el cliente']];
    const listo = !!(ack && ack.ok && d.kali_en_feed === false);
    pintarLimpieza(items, listo);
    if (listo || (ack && !ack.ok)) { if (b) b.disabled = false; return; }
  }
  if (Date.now() > fin) { pintarLimpieza([['mal', 'Sin acuse del publicador en 60 s: revisa ppi-publicar-feed-v2']], false); if (b) b.disabled = false; return; }
  limpTimer = setTimeout(() => limpiezaSondear(id, fin), 2000);
}
// Vista limpia: Alertas solo muestra lo posterior a la última limpieza. Es una marca de
// este navegador; los registros del motor no se borran y «Ver historial» la deshace.
let limpioDesde = 0;
try { limpioDesde = Number(localStorage.getItem('cf_limpio_desde')) || 0; } catch (e) { /* sin marca */ }
function vistaLimpiaDesde(t) {
  limpioDesde = t || 0;
  try { if (limpioDesde) localStorage.setItem('cf_limpio_desde', String(limpioDesde)); else localStorage.removeItem('cf_limpio_desde'); } catch (e) { /* sin persistir */ }
  document.querySelectorAll('.toast').forEach(t => t.remove());
  if (typeof toastVisto !== 'undefined') toastVisto.clear();
  if (typeof renderAlertas === 'function') renderAlertas();
  if (typeof pintarPillAlertas === 'function') pintarPillAlertas();
}
on('alertasEscoba', 'click', () => limpiarPedir());
async function limpiarPedir() {
  const b = document.getElementById('limpiarBtn');
  if (b) b.disabled = true;
  try {
    const r = await fetch('/api/demo/limpiar', { method: 'POST', headers: { 'X-CyberFlow': '1' } });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.ok) throw new Error(d.motivo || (r.status === 403 ? 'Solo un administrador puede dejarlo limpio.' : 'HTTP ' + r.status));
    esc = null; escGuardar(); renderEscReloj(); renderEscPasos(); renderEscFilas();
    vistaLimpiaDesde(Date.now() / 1000);
    pintarLimpieza([['ok', 'Petición dejada al publicador'], ['esp', 'Esperando al publicador…']], false);
    limpiezaSondear(d.id, Date.now() + 60000);
  } catch (e) {
    pintarLimpieza([['mal', varEsc(e.message)]], false);
    if (b) b.disabled = false;
  }
}
on('limpiarBtn', 'click', limpiarPedir);
(async () => {
  try {
    const d = await (await fetch('/api/demo/estado')).json();
    if (d && d.peticion && d.peticion_edad < 900) renderPrep(d);
  } catch (e) { /* sin estado previo */ }
})();
on('escParar', 'click', () => { esc = null; escGuardar(); renderEscReloj(); renderEscPasos(); renderEscFilas(); });
renderEscCards(); renderEscDetalle(); renderEscReloj(); renderEscPasos();
if (escActivo()) { const ip = document.getElementById('escIp'); if (ip) ip.value = esc.ip; }
setInterval(renderEscReloj, 1000);
setInterval(escConsultar, 3000);

// ---- Alertas flotantes ---------------------------------------------------
// Una tarjeta por IP y accion, con el motivo. BLOCK se queda hasta cerrarla (o
// 45 s); LIMIT se va sola a los 15 s. Pulsarla filtra Decisiones por esa IP.
// Se pueden silenciar con el boton «Avisos» (se recuerda en este navegador).
let avisosOn = true;
try { avisosOn = localStorage.getItem('cf_avisos') !== '0'; } catch (e) { /* por omision, si */ }

function pintarBotonAvisos() {
  const b = document.getElementById('avisosBtn');
  if (!b) return;
  b.dataset.on = avisosOn ? '1' : '0';
  b.textContent = avisosOn ? 'Avisos: sí' : 'Avisos: no';
}
pintarBotonAvisos();
function pintarBotonTema() {
  const b = document.getElementById('temaBtn');
  if (!b) return;
  const osc = document.documentElement.dataset.tema === 'oscuro';
  // El botón dice a qué tema cambia, con su icono (sol / luna).
  b.textContent = osc ? '☀ Tema claro' : '☾ Tema oscuro';
  b.title = osc ? 'Cambiar al tema claro' : 'Cambiar al tema oscuro';
}
pintarBotonTema();
on('temaBtn', 'click', () => {
  const t = document.documentElement.dataset.tema === 'oscuro' ? 'claro' : 'oscuro';
  document.documentElement.dataset.tema = t;
  try { localStorage.setItem('cf_tema', t); } catch (e) { /* sin persistir */ }
  pintarBotonTema();
});
on('avisosBtn', 'click', () => {
  avisosOn = !avisosOn;
  try { localStorage.setItem('cf_avisos', avisosOn ? '1' : '0'); } catch (e) { /* sin persistir */ }
  pintarBotonAvisos();
});

const REGLA_LEGACY = { auth_failure_heuristic: 'fallos de autenticación repetidos' };

function motivoDeDecision(d) {
  if (d.heuristico && d.heuristico.heuristico) {
    return { regla: d.heuristico.heuristico, texto: d.heuristico.motivo || '' };
  }
  if (d.decision === 'ALERT' && String(d.detector_name || '').endsWith('_heuristic')) {
    return { regla: d.detector_name, texto: REGLA_LEGACY[d.detector_name] || 'regla determinista' };
  }
  if (d.decision === 'ALERT') {
    const s = d.score != null ? 'score ' + d.score.toFixed(3) : '';
    const u = d.threshold != null ? ' bajo el umbral ' + Number(d.threshold).toFixed(3) : '';
    return { regla: 'modelo', texto: 'anomalía: ' + s + u };
  }
  return { regla: '', texto: '' };
}

function avisar(nuevas) {
  if (!avisosOn) return;
  nuevas = (nuevas || []).filter(d => !esMarginal(d) && accionDeDecision(d) !== 'PERMIT');
  // Con un escenario en seguimiento los cinco pasos ya cuentan lo de su IP: el aviso
  // solo taparía la evidencia. Se avisa de las OTRAS IP.
  if (escActivo()) nuevas = nuevas.filter(d => d.entity_ip !== esc.ip);
  if (!nuevas.length) return;
  const cont = document.getElementById('toasts');
  if (!cont) return;
  const grupos = new Map();
  for (const d of nuevas) {
    const acc = accionDeDecision(d);
    const k = d.entity_ip + '|' + acc;
    const g = grupos.get(k) || { ip: d.entity_ip, acc: acc, n: 0, d: d };
    g.n += 1;
    if ((d.logged_at || 0) > (g.d.logged_at || 0)) g.d = d;
    grupos.set(k, g);
  }
  for (const g of grupos.values()) {
    const id = 'toast-' + g.ip.split('.').join('-') + '-' + g.acc;
    if (limpioDesde && (g.d.logged_at || 0) < limpioDesde) continue;
    const visto = toastVisto.get(id), ahoraT = Date.now() / 1000;
    toastVisto.set(id, ahoraT);
    const viejo = document.getElementById(id);
    if (viejo) {
      const mt = viejo.querySelector('.t-mot'); if (mt) mt.textContent = motivoDeDecision(g.d).texto || '';
      // Mientras siga el episodio el aviso queda a la vista; se cierra 20 s después de la última ventana.
      clearTimeout(viejo._cierre); viejo._cierre = setTimeout(() => viejo.remove(), g.acc === 'BLOCK' ? 20000 : 10000);
      continue;
    }
    if (visto && ahoraT - visto < 120) continue;   // mismo episodio: no repetir la alarma
    const m = motivoDeDecision(g.d);
    const el = document.createElement('div');
    el.className = 'toast ' + (g.acc === 'BLOCK' ? 'block' : 'limit');
    el.id = id;
    const tIco = g.acc === 'BLOCK'
      ? '<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>'
      : '<path d="M12 14l3.5-3.5"/><path d="M4.5 18a8.5 8.5 0 1 1 15 0"/>';
    el.innerHTML = '<div class="t-cab"><span class="t-ico"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">' + tIco + '</svg></span>'
      + '<span><span class="t-alarma">' + (g.acc === 'BLOCK' ? 'Alerta crítica' : 'Alerta') + '</span><br>'
      + '<span class="t-ip">' + varEsc(g.ip) + '</span></span>'
      + '<span class="badge acc-' + g.acc.toLowerCase() + '">' + g.acc + '</span>'
      + '<button class="t-x" title="Cerrar" aria-label="Cerrar">×</button></div>'
      + '<div class="t-mot">' + varEsc(m.texto || 'acción del sistema') + '</div>'
      + '<div class="t-meta">' + varEsc(m.regla) + ' · ' + fmtTime(g.d.logged_at)
      + (g.n > 1 ? ' · ' + g.n + ' ventanas' : '') + (g.d.simulado ? ' · simulado' : '') + '</div>';
    el.addEventListener('click', (ev) => {
      if (ev.target.closest('.t-x')) { el.remove(); return; }
      const f = document.getElementById('ipFilter');
      if (f) { f.value = g.ip; decVista = 'todas'; pintarDecVista(); renderDecisionsTable(); }
      if (typeof mostrarSeccion === 'function') mostrarSeccion('s-decisiones');
      el.remove();
    });
    cont.prepend(el);
    el._cierre = setTimeout(() => el.remove(), g.acc === 'BLOCK' ? 20000 : 10000);
  }
  while (cont.children.length > 2) cont.lastElementChild.remove();
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && unseenAlertCount > 0) {
    unseenAlertCount = 0;
    document.title = BASE_TITLE;
    document.getElementById('favicon').href = BASE_FAVICON;
  }
});

const toastVisto = new Map();   // id de aviso -> última vez que llegó una ventana del episodio
function card(label, value, cls) {
  return `<div class="card ${cls||''}"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
// 17-nov: widget con icono para Actividad, Respuestas y Scores.
const W_ICO = {
  ventanas: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v16"/>',
  block: '<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>',
  limit: '<path d="M12 14l3.5-3.5"/><path d="M4.5 18a8.5 8.5 0 1 1 15 0"/>',
  ips: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1-4 4-6 7-6s6 2 7 6"/>',
  modelo: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
  umbral: '<path d="M3 12h18" stroke-dasharray="3 3"/><path d="M6 18l4-9 4 5 4-9"/>',
  reloj: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
  escudo: '<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
};
function widget(label, value, cls, ico, sub) {
  return `<div class="wid ${cls || ''}"><span class="w-ico"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${W_ICO[ico] || ''}</svg></span>`
    + `<div><div class="w-lab">${label}</div><div class="w-val">${value}</div>${sub ? `<div class="w-sub">${sub}</div>` : ''}</div></div>`;
}
function fmtTime(t) {
  return new Date(t * 1000).toLocaleTimeString('es-PE', { hour12: false });
}

// Fila de KPIs: las cuatro cifras que un operador mira primero. Todo sale de
// datos ya cargados (contadores + el resumen del histograma); nada inventado.
function renderKpis(status) {
  const el = document.getElementById('kpis');
  if (!el) return;
  const c = status.counters || {};
  const cal = status.calibracion && status.calibracion.calibrado_en_esta_red;
  const nMod = c.alert_model || 0;
  let nAcc = (c.block || 0) + (c.limit || 0);
  let vig = (status.vigentes || []).length;
  // Cada cifra lleva a la vista donde se ve su detalle. Ambar solo si pide
  // atencion; nunca verde por «hay respuesta»: eso no confirma nada en el host.
  const tile = (lab, val, sub, estado, ir) =>
    `<div class="kpi ${estado || ''}"${ir ? ` data-ir="${ir}" role="link" tabindex="0"` : ''}><div class="k-dot"></div>`
    + `<div class="k-lab">${lab}</div><div class="k-val">${val}</div>`
    + `<div class="k-sub">${sub}</div>${ir ? '<div class="k-ir">Ver ' + escSimple(SEC_TITULO_CORTO[ir] || '') + ' &rarr;</div>' : ''}</div>`;
  // Modo v2 con una fuente ausente: la cifra es desconocida, no cero.
  const cvF = (status.cadena_v2 && status.cadena_v2.activa) ? (status.cadena_v2.fuentes || {}) : null;
  const sinFuente = k => cvF && !(cvF[k] && cvF[k].ok);
  if (sinFuente('traza')) nAcc = '—';
  if (sinFuente('feed')) vig = '—';
  el.innerHTML =
    tile('Entidades observadas', c.entidades != null ? c.entidades : '—', 'IPs con ventanas en la última hora', '', 's-actividad') +
    tile('Ventanas analizadas', (c.total != null ? c.total : 0).toLocaleString('es'), 'en la última hora', '', 's-decisiones') +
    tile((status.cadena_v2 && status.cadena_v2.activa) ? 'Medidas publicadas (v2)' + (sinFuente('traza') ? ' · desconocido (traza ausente)' : '') : 'Alertas detectadas', nAcc,
         (status.cadena_v2 && status.cadena_v2.activa)
           ? nMod + ' señal(es) del IF en la hora · solo actúa lo que publica el publicador v2' + (cal ? '' : ' · modelo sin calibrar')
           : nMod + ' anomalía(s) del modelo · ' + Math.max(0, nAcc - nMod) + ' por reglas' + (cal ? '' : ' · modelo sin calibrar'),
         !cal || nAcc > 0 ? 'warn' : '', 's-alertas') +
    tile('Respuestas registradas', vig, (status.cadena_v2 && status.cadena_v2.activa)
           ? 'medidas en el feed v2 · ' + (status.cadena_v2.modo === 'sombra' ? 'propuestas (sombra), aplicación no ejecutada' : 'aplicación sin evidencia')
           : (status.acuses || []).length
           ? 'vigentes según el motor · ' + aplicadasEnHostsDe(status.acuses) + ' aplicada(s) en el host según su acuse'
           : 'vigentes según el registro del motor; ningún host ha enviado acuse',
         vig > 0 ? 'warn' : '', 's-bloqueos');
}
const SEC_TITULO_CORTO = { 's-actividad': 'Actividad', 's-decisiones': 'Decisiones', 's-alertas': 'Alertas', 's-bloqueos': 'Respuestas' };
on('kpis', 'click', (ev) => {
  const k = ev.target.closest('[data-ir]');
  if (k && typeof mostrarSeccion === 'function') mostrarSeccion(k.dataset.ir);
});
on('kpis', 'keydown', (ev) => {
  const k = ev.target.closest('[data-ir]');
  if (k && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); mostrarSeccion(k.dataset.ir); }
});

// La franja de salud la decide el servidor (status.salud): una sola verdad,
// testeable, que separa salud de servicio de actividad de respuesta. Aqui solo
// se pinta. Una accion LIMIT/BLOCK por heuristico ya NO queda como "todo normal":
// el servidor la cuenta como respuesta activa, no como alerta del modelo.
function renderHealthbar(salud) {
  const el = document.getElementById('healthbar');
  if (!el) return;
  const s = salud || { nivel: 'warn', msg: 'Estado no disponible', sub: '' };
  el.className = 'healthbar ' + (s.nivel || '');
  el.innerHTML = `<span class="dot"></span><div><div class="msg">${escSimple(s.msg || '')}</div>` +
    `<div class="sub">${escSimple(s.sub || '')}</div></div>`;
}

// La grafica de actividad guarda sus datos para el tooltip; la unidad de tiempo
// depende del rango elegido (minutos en 1h, horas en 24h).
let _sparkData = { activity: [], unidad: 'min' };

function _sparkCuando(b) {
  return b.offset === 0 ? 'ahora' : ('hace ' + b.offset + ' ' + _sparkData.unidad);
}

// Tope de eje redondo (1, 2, 5 x 10^n), para que las marcas se lean de un vistazo.
function ejeBonito(v) {
  if (v <= 4) return 4;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const m = v / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}

// Dos bandas con escala propia y lineal: arriba las acciones (LIMIT y BLOCK
// apiladas), abajo el volumen de ventanas. En una sola escala las acciones,
// que son pocas frente al volumen, no se verian.
function renderSparkline(activity) {
  const svg = document.getElementById('spark');
  const n = activity.length;
  const W = 610, H = 150, bw = W / n;
  const A0 = 6, A1 = 52, V0 = 70, V1 = 146;
  _sparkData = { activity: activity, unidad: currentRange === '24h' ? 'h' : 'min' };
  const maxV = ejeBonito(Math.max(1, ...activity.map(b => b.alert + b.permit)));
  const maxA = ejeBonito(Math.max(1, ...activity.map(b => (b.limit || 0) + (b.block || 0))));
  let s = '';
  [A0, A1, V0, (V0 + V1) / 2, V1].forEach(y => {
    const base = y === A1 || y === V1;
    s += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="var(--border)" stroke-width="1" vector-effect="non-scaling-stroke"${base ? '' : ' stroke-dasharray="2 4"'}/>`;
  });
  activity.forEach((b, i) => {
    const x = (i * bw + 0.6).toFixed(1), w = Math.max(1, bw - 1.2).toFixed(1);
    const total = b.alert + b.permit;
    if (total > 0) {
      const h = Math.max(1.5, total / maxV * (V1 - V0));
      s += `<rect x="${x}" y="${(V1 - h).toFixed(1)}" width="${w}" height="${h.toFixed(1)}" fill="var(--accent)" fill-opacity="0.6"/>`;
    }
    const li = b.limit || 0, bl = b.block || 0;
    const hl = li / maxA * (A1 - A0), hb = bl / maxA * (A1 - A0);
    if (li) s += `<rect x="${x}" y="${(A1 - hl).toFixed(1)}" width="${w}" height="${hl.toFixed(1)}" fill="var(--amber)"/>`;
    if (bl) s += `<rect x="${x}" y="${(A1 - hl - hb).toFixed(1)}" width="${w}" height="${hb.toFixed(1)}" fill="var(--danger)"/>`;
  });
  s += `<line id="sparkCross" x1="0" y1="0" x2="0" y2="${H}" stroke="var(--text-dim)" stroke-width="1" stroke-dasharray="3 2" vector-effect="non-scaling-stroke" visibility="hidden"/>`;
  svg.innerHTML = s;
  // Las marcas van en HTML: el SVG se estira a lo ancho y deformaria el texto.
  const pct = y => (y / H * 100).toFixed(1) + '%';
  document.getElementById('actY').innerHTML =
    `<span style="top:${pct(A0)}">${maxA}</span><span style="top:${pct(A1)}">0</span>`
    + `<span style="top:${pct(V0)}">${maxV.toLocaleString('es')}</span><span style="top:${pct((V0 + V1) / 2)}">${(maxV / 2).toLocaleString('es')}</span>`
    + `<span style="top:${pct(V1)}">0</span>`;
  const u = _sparkData.unidad, tot = n - 1;
  document.getElementById('actX').innerHTML = [1, 0.75, 0.5, 0.25].map(f =>
    `<span>−${Math.round(tot * f)} ${u}</span>`).join('') + '<span>ahora</span>';
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
    + `<div><span class="t-p">ventanas</span> <b>${(b.alert + b.permit).toLocaleString('es')}</b></div>`
    + `<div><span style="color:var(--amber)">LIMIT</span> <b>${b.limit || 0}</b></div>`
    + `<div><span class="t-a">BLOCK</span> <b>${b.block || 0}</b></div>`;
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
  // Lienzo en pixeles reales: el texto no se deforma y caben ejes de verdad.
  const w = Math.max(320, svg.clientWidth || 900), h = 240;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  const X0 = 46, X1 = w - 10, Y0 = 22, base = h - 28;
  const maxCount = ejeBonito(Math.max(...data.buckets.map(b => b.count), 1));
  const bw = (X1 - X0) / data.buckets.length;
  const coma = (v, d) => v.toFixed(d).split('.').join(',');
  let bars = '';
  let bajoUmbral = 0;
  const thresholdX = X0 + ((data.threshold - data.min) / (data.max - data.min)) * (X1 - X0);
  // Zona de anomalia (a la izquierda del umbral) y rejilla con el conteo.
  bars += `<rect x="${X0}" y="${Y0}" width="${Math.max(0, thresholdX - X0).toFixed(1)}" height="${base - Y0}" fill="var(--danger)" fill-opacity="0.06"/>`;
  [0, maxCount / 2, maxCount].forEach(c => {
    const y = base - c / maxCount * (base - Y0);
    bars += `<text x="${X0 - 6}" y="${(y + 3).toFixed(1)}" text-anchor="end">${c.toLocaleString('es')}</text>`;
    bars += `<line x1="${X0}" y1="${y.toFixed(1)}" x2="${X1}" y2="${y.toFixed(1)}" stroke="var(--border)"${c ? ' stroke-dasharray="2 4"' : ''}/>`;
  });
  data.buckets.forEach((b, i) => {
    const barH = b.count > 0 ? Math.max(3, (b.count / maxCount) * (base - Y0)) : 0;
    const x = X0 + i * bw;
    // Rojo: cubo enteramente en zona ALERT (por debajo del umbral). Verde:
    // enteramente en zona PERMIT. Ambar: el cubo cruza el umbral -- scores
    // ahi mezclan ambas decisiones, la zona mas interesante para mirar.
    let color = 'var(--accent)', zona = 'PERMIT';
    if (b.hi <= data.threshold) { color = 'var(--danger)'; zona = 'ALERT'; bajoUmbral += b.count; }
    else if (b.lo < data.threshold) { color = 'var(--amber)'; zona = 'cruza el umbral'; }
    // Barra con tope redondeado (spec de marcas) y, encima, un area invisible de
    // toda la altura como diana de hover: el <title> da el tooltip nativo sin
    // depender de JS -robusto, y el raton no tiene que acertar la barra fina-.
    if (barH > 0) {
      bars += `<rect x="${(x + 1).toFixed(1)}" y="${(base - barH).toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${barH.toFixed(1)}" rx="2" fill="${color}"/>`;
      // El conteo encima de la barra, si cabe: se lee sin pasar el raton.
      if (bw >= 22) bars += `<text x="${(x + bw / 2).toFixed(1)}" y="${(base - barH - 4).toFixed(1)}" text-anchor="middle" style="fill:var(--text)">${b.count}</text>`;
    }
    bars += `<rect x="${x.toFixed(1)}" y="${Y0}" width="${bw.toFixed(1)}" height="${base - Y0}" fill="transparent">`
      + `<title>score ${b.lo.toFixed(3)} a ${b.hi.toFixed(3)} · ${b.count} ventana(s) · ${zona}</title></rect>`;
  });
  bars += `<line x1="${thresholdX.toFixed(1)}" y1="${Y0 - 8}" x2="${thresholdX.toFixed(1)}" y2="${base}" stroke="var(--text)" stroke-width="1.3" stroke-dasharray="4 3"/>`;
  const derecha = thresholdX < w - 150;
  bars += `<text x="${(thresholdX + (derecha ? 6 : -6)).toFixed(1)}" y="${Y0 - 9}" text-anchor="${derecha ? 'start' : 'end'}" style="fill:var(--text)">umbral ${coma(data.threshold, 3)}</text>`;
  // El rotulo de la zona solo si cabe: con el umbral pegado al borde se encimaria.
  if (thresholdX - X0 > 110) bars += `<text x="${X0 + 4}" y="${Y0 - 9}" style="fill:var(--danger)">← anomalía</text>`;
  // Eje X: cinco marcas de score entre el minimo y el maximo observados.
  for (let i = 0; i <= 4; i++) {
    const v = data.min + (data.max - data.min) * i / 4, x = X0 + (X1 - X0) * i / 4;
    bars += `<line x1="${x.toFixed(1)}" y1="${base}" x2="${x.toFixed(1)}" y2="${base + 3}" stroke="var(--border)"/>`;
    bars += `<text x="${x.toFixed(1)}" y="${h - 8}" text-anchor="${i === 0 ? 'start' : (i === 4 ? 'end' : 'middle')}">${coma(v, 3)}</text>`;
  }
  svg.innerHTML = bars;
  const pct = data.n ? Math.round(100 * bajoUmbral / data.n) : 0;
  window._histResumen = { pct: pct, n: data.n, bajoUmbral: bajoUmbral };
  const sw = document.getElementById('scoreWids');
  if (sw) {
    const c3 = v => v.toFixed(3).split('.').join(',');
    sw.innerHTML = [
      widget('Decisiones puntuadas', data.n.toLocaleString('es'), 'navy', 'ventanas', 'últimas 500 como máximo'),
      widget('Umbral vigente', c3(data.threshold), 'ok', 'umbral', 'por debajo = anomalía'),
      widget('Bajo el umbral', bajoUmbral.toLocaleString('es'), bajoUmbral ? 'bad' : '', 'modelo', pct + ' % del tráfico reciente'),
      widget('Score mínimo', c3(data.min), '', 'reloj', 'máximo ' + c3(data.max)),
    ].join('');
  }
  // La misma escala del histograma la reusa la mini-barra de la tabla.
  window._escalaScore = { min: data.min, max: data.max, umbral: data.threshold };
  // Referencia: la fraccion que quedo bajo el umbral al calibrar (FPR del
  // manifiesto). Si lo de ahora la dobla, se dice; no es un veredicto, es un aviso.
  const ref = window._fprRef;
  const real = data.n ? 100 * bajoUmbral / data.n : 0;
  let comp = '';
  if (ref != null && data.n) {
    comp = ` En la calibración fue el ${coma(ref * 100, 2)} %`
      + (real > 2 * ref * 100 && bajoUmbral >= 5 ? ': ahora hay más del doble.' : '.');
  }
  hint.textContent = `${data.n} ventanas puntuadas · ${bajoUmbral} (${coma(real, 1)} %) bajo el umbral.${comp} `
    + `Rojo, anomalía; ámbar, la barra cruza el umbral; verde, normal.`;
}

async function loadActivity(range) {
  const data = await (await fetch('/api/activity?range=' + range)).json();
  renderSparkline(data.activity);
  document.getElementById('sparkRangeLabel').textContent = range === '24h' ? 'por hora' : 'por minuto';
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
  // Cuatro tareas operativas primero; la arquitectura y el entrenamiento van
  // despues como recorrido avanzado (solo aparecen en la vista de desarrollo).
  { sel: '#s-salud', t: '1 · Comprobar la salud', d: 'Arriba, el estado general: si los servicios están operativos y si hay algo que atender. Debajo, cuatro cifras de la última hora: entidades observadas, ventanas analizadas, anomalías del modelo y alertas de reglas, y respuestas registradas. Pulsa una cifra para ir a su detalle.' },
  { sel: '#s-alertas', t: '2 · Encontrar el episodio', d: 'Alertas lista cada ventana con señal: anomalía del modelo (azul) o regla disparada. Filtra por fuente, acción o IP. «Ver decisión» abre la decisión exacta.' },
  { sel: '#s-decisiones', t: '3 · Entender la decisión', d: 'Cada fila tiene «Ver detalle»: resultado, por qué se decidió, la evidencia (score frente al umbral, regla) y el contexto técnico. Para mirar atrás, elige un periodo y pulsa «Consultar periodo».' },
  { sel: '#s-bloqueos', t: '4 · Revisar la respuesta', d: 'Respuestas separa lo registrado por el motor, lo publicado en el feed firmado y lo aplicado en el host, que este panel no comprueba. LIMIT degrada la tasa; solo BLOCK corta.' },
  { sel: '#kpis', t: 'Recorrido avanzado', d: 'Lo que sigue explica la arquitectura, el modelo y la evaluación. Puedes cerrar la guía aquí si solo vas a operar.' },
  { sel: '#s-topologia', t: 'El recorrido del paquete', d: 'De la red al veredicto: captura → variables por capa → modelo y heurísticos → decisión → respuesta en el host. Pulsa cualquier componente para ver qué hace.' },
  { sel: '#topoVista', t: 'Vistas', d: 'De la red a las carpetas: cada botón es un diagrama del mismo sistema.' },
  { sel: '#topoModo', t: 'Lab u operativa', d: 'Lab muestra lo que se montó para el ensayo; Operativa, solo el flujo de una red real.' },
  { sel: '#topoArchivosBtn', t: 'Código auditable', d: 'En modo desarrollador, pulsa Ver archivos, elige un componente y un archivo; en su ficha pulsa ◎ Ver contenido. El visor es de solo lectura y solo muestra rutas permitidas.' },
  { sel: '#s-modelo', t: 'El detector activo y su umbral', d: 'El detector desplegado aprende la normalidad de esta red; el umbral se fijó con validación. Aquí ves el modelo activo y sus métricas, no una etiqueta fija de OCSVM.' },
  { sel: '#pruebasPrevias', t: 'Pruebas previas', d: 'Siete modelos se compararon en el estudio; la ablación sobre nueve episodios separa modelo solo (6), heurísticos solos (7) y ambos combinados (9). No confundas el 9/9 del sistema con el modelo solo.' },
  { sel: '#s-scores', t: 'Distribución de scores', d: 'No solo si alertó o no, sino cuánto margen hubo respecto al umbral vigente. A la izquierda de la línea, anómalo para el modelo; a la derecha, normal.' },
  { sel: '#s-simulacion', t: 'Escenarios guiados', d: 'Comandos listos para provocar tráfico normal o un ataque y ver cómo responde el modelo. El panel no ejecuta: copias el comando y observas.' },
  { sel: null, t: 'Esto es el demo', d: 'Estás viendo datos de ejemplo. Para usarlo en tu propia red, sigue la instalación del README (modo despliegue) y recalibra con tu tráfico.' },
];
let tourI = 0, tourPasos = [], tourAuto = false;

// Un paso es valido si su elemento existe Y su seccion no esta oculta por el
// modo operativo: si no, con el paginado el foco saltaba a la esquina (rect 0)
// al intentar mostrar una seccion de desarrollo invisible.
function tourPasoVisible(sel) {
  const el = document.querySelector(sel);
  if (!el) return false;
  const sec = el.closest('.wrap > section[id]');
  return !(sec && sec.hidden);
}
function tourInit() { tourPasos = TOUR_PASOS.filter(p => !p.sel || tourPasoVisible(p.sel)); }
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
    // Con paginado, el paso puede apuntar a otra seccion: se abre antes.
    const secPaso = el.closest('.wrap > section[id]');
    if (secPaso && typeof mostrarSeccion === 'function') mostrarSeccion(secPaso.id, false);
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

// ---- Pulso: lo que entra y lo que se acumula, con su edad -----------------
// Las tasas salen de la diferencia entre dos lecturas del mismo contador. Con
// una sola lectura no hay tasa y se dice «—»: un cero afirmaria que no entra nada.
const pulsoPrev = {};
const pulsoHist = { pk: [], ev: [], dec: [] };
let pulsoFilas0 = null;
function pulsoTasa(clave, valor, t) {
  const a = pulsoPrev[clave];
  if (valor == null || t == null || isNaN(t)) return null;
  if (a && a.t === t) return a.tasa;
  let tasa = null;
  if (a && t > a.t && valor >= a.v) tasa = (valor - a.v) / (t - a.t);
  pulsoPrev[clave] = { v: valor, t: t, tasa: tasa };
  return tasa;
}
function pulsoSpark(h, color) {
  if (h.length < 2) return '<svg class="pulso-spark" viewBox="0 0 120 26"></svg>';
  const max = Math.max.apply(null, h) || 1;
  const pts = h.map((v, i) => (i * 120 / (h.length - 1)).toFixed(1) + ',' + (24 - v / max * 21).toFixed(1)).join(' ');
  return `<svg class="pulso-spark" viewBox="0 0 120 26" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}
function pulsoHace(seg) {
  if (seg == null || isNaN(seg)) return 'sin dato';
  seg = Math.max(0, Math.round(seg));
  if (seg < 90) return 'hace ' + seg + ' s';
  if (seg < 5400) return 'hace ' + Math.round(seg / 60) + ' min';
  return 'hace ' + Math.round(seg / 3600) + ' h';
}
function pulsoNum(v) {
  if (v == null) return '—';
  return v >= 100 ? Math.round(v).toLocaleString('es') : v.toFixed(1).split('.').join(',');
}
function renderPulso(status) {
  const el = document.getElementById('pulso');
  const p = status.pulso;
  if (!el || !p) return;
  const cm = status.capture_metrics;
  // Suricata escribe la zona como +0000; Date.parse la quiere como +00:00.
  let marca = cm && cm.medido_en ? String(cm.medido_en) : null;
  if (marca) {
    const z = marca.charAt(marca.length - 5);
    if (z === '+' || z === '-') marca = marca.slice(0, -2) + ':' + marca.slice(-2);
  }
  const tPk = marca ? Date.parse(marca) / 1000 : null;
  const pk = cm ? pulsoTasa('pk', cm.kernel_packets, tPk) : null;
  const ev = p.eve ? pulsoTasa('ev', p.eve.bytes, p.ahora) : null;
  const guardar = (k, v) => { const h = pulsoHist[k]; h.push(v == null ? 0 : v); if (h.length > 60) h.shift(); };
  guardar('pk', pk); guardar('ev', ev); guardar('dec', p.decisiones_60s);
  const filas = p.dataset ? p.dataset.filas : null;
  if (filas != null && pulsoFilas0 == null) pulsoFilas0 = filas;
  const edad = (t) => t == null ? null : p.ahora - t;
  const ficha = (tit, val, uni, sub, e, limite, spark) => {
    const est = e == null || isNaN(e) ? '' : (e > limite ? 'warn' : 'ok');
    return `<div class="pulso-t ${est}"><div class="pulso-l"><span class="pulso-dot"></span>${tit}</div>`
      + `<div class="pulso-v">${val}<small>${uni}</small></div><div class="pulso-s">${sub}</div>${spark || ''}</div>`;
  };
  el.innerHTML =
    ficha('Paquetes', pulsoNum(pk), '/s', cm ? 'medido ' + pulsoHace(edad(tPk)) : 'sin medir',
          edad(tPk), 30, pulsoSpark(pulsoHist.pk, 'var(--accent)'))
    + ficha('Eventos de Suricata', ev == null ? '—' : pulsoNum(ev / 1024), 'KB/s',
            p.eve ? 'último ' + pulsoHace(edad(p.eve.mtime)) : 'sin dato',
            p.eve ? edad(p.eve.mtime) : null, 30, pulsoSpark(pulsoHist.ev, 'var(--accent)'))
    + ficha('Decisiones', String(p.decisiones_60s), '/min',
            'última ' + pulsoHace(edad(p.ultima_decision)), edad(p.ultima_decision), 60,
            pulsoSpark(pulsoHist.dec, 'var(--ok)'))
    + ficha('Feed publicado', p.feed ? String(p.feed.entradas) : '—', p.feed && p.feed.entradas === 1 ? 'entrada' : 'entradas',
            p.feed ? 'firmado ' + pulsoHace(edad(p.feed.generado)) : 'sin dato',
            p.feed ? edad(p.feed.generado) : null, 150, '');
}

async function refresh() {
  try {
    // El histograma se pide junto al estado para que la tarjeta "Cerca del
    // umbral" tenga su cifra ya en la primera pintada, no un ciclo despues.
    const [statusRes, histRes] = await Promise.all([
      fetch('/api/status'), fetch('/api/score-histogram')]);
    const status = await statusRes.json();
    const histogramData = await histRes.json();
    ultimaActualizacion = Date.now();
    errorActualizacion = '';
    pintarSello();
    cargarListaBlanca();

    window._fprRef = status.model ? status.model.test_fpr : null;
    renderHistogram(histogramData);
    renderKpis(status);
    renderHealthbar(status.salud);
    renderPulso(status);
    if (document.getElementById('despliegue')) renderDespliegue(status);
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
      healthCards.push(card(
        'Paquetes capturados',
        (cm.kernel_packets || 0).toLocaleString('es'),
        'accent'
      ));
      // kernel_drops es ACUMULADO desde el arranque de Suricata. Rojo solo si
      // sube entre dos muestras; un acumulado heredado no es pérdida en curso,
      // y si el stats está viejo se dice "dato atrasado", nunca "sin drops".
      const de = cm.drops_estado || {};
      const total = de.total != null ? de.total : ((cm.kernel_drops || 0) + (cm.kernel_ifdrops || 0));
      let sub, estado;
      if (de.nivel === 'sin_dato') { sub = 'sin medir'; estado = ''; }
      else if (de.subiendo) { sub = 'subiendo +' + de.delta + ' · acumulado desde arranque'; estado = 'bad'; }
      else if (de.atrasado) { sub = 'acumulado desde arranque · dato atrasado'; estado = 'warn'; }
      else { sub = 'acumulado desde arranque · sin aumento reciente'; estado = 'ok'; }
      healthCards.push(card(
        'Drops de captura',
        total.toLocaleString('es') + '<small>' + sub + '</small>',
        estado
      ));
    }
    // El dataset acumulado es diagnostico (aprendizaje), no pulso operativo.
    const pd = status.pulso && status.pulso.dataset;
    if (pd) {
      const filas = pd.filas;
      healthCards.push(card('Dataset acumulado', (filas == null ? '—' : filas.toLocaleString('es'))
        + '<small>filas · escrito ' + pulsoHace(status.pulso.ahora - pd.mtime)
        + (filas != null && pulsoFilas0 != null && filas > pulsoFilas0 ? ' · +' + (filas - pulsoFilas0).toLocaleString('es') + ' en esta sesión' : '')
        + '</small>'));
    }
    health.innerHTML = healthCards.join('');

    const modelEl = document.getElementById('model');
    if (modelEl) {
      const m = status.model;
      // Una métrica que el manifiesto no trae llega como null: se muestra «—»,
      // no un 0 % que parecería una medición.
      const pct = (v, d) => (v == null ? '—' : (v * 100).toFixed(d) + '%');
      const ev = m.evaluacion;
      const coma = (v, d) => v.toFixed(d).split('.').join(',');
      const tarjetas = [
        card('Detector vigente', escSimple(DETECTOR_LABEL[m.detector_name] || m.detector_name || 'no disponible')
          + '<small>' + escSimple(m.detector_name || '') + '</small>', 'txt'),
        card('Umbral vigente', coma(m.threshold, 6) + '<small>score_samples · del manifiesto del motor</small>', 'accent'),
      ];
      if (ev) {
        // Cifras medidas del detector en uso (docs/evaluacion/modelo-vigente.json).
        const dk = ev.deteccion_kali;
        tarjetas.push(card('FPR en el oro (vigente)', coma(ev.fpr_oro.valor * 100, 2) + ' %<small>' + ev.fpr_oro.ventanas.toLocaleString('es') + ' ventanas</small>'));
        tarjetas.push(card('Detección del modelo solo', coma(100 * dk.detectadas / dk.total, 1) + ' %<small>' + dk.detectadas + ' de ' + dk.total + ' ventanas de ataque</small>', 'accent'));
      } else {
        tarjetas.push(card('FPR benigno (vigente)', pct(m.test_fpr, 2) + '<small>del manifiesto; «—» si no lo trae</small>'));
        tarjetas.push(card('Detección global', pct(m.detection_rate, 1), 'accent'));
        tarjetas.push(card('Detección Kali-real', pct(m.kali_real_detection_rate, 1), 'accent'));
      }
      modelEl.innerHTML = tarjetas.join('');
      // Si se hubiera hecho rollback al recalibrado, la nota fija de «histórico»
      // mentiria: se reescribe con lo que dice el manifiesto.
      const vh = document.getElementById('modeloVigHist');
      if (vh && m.detector_name && m.detector_name !== 'if_limpio_2026_10') {
        vh.innerHTML = '<b>Vigente:</b> <code>' + escSimple(m.detector_name) + '</code>, umbral ' + coma(m.threshold, 6)
          + ' (leído del manifiesto del motor). Las cifras de la tabla de abajo marcadas como vigentes corresponden a <code>if_limpio_2026_10</code>: no aplican a este detector.';
      }
      const fam = document.getElementById('modeloFamilias'), debil = document.getElementById('modeloDebil');
      if (ev && fam) {
        // Barras por familia: la mas floja es el punto debil, dicho con su cifra.
        const filas = ev.por_familia.map(f => Object.assign({ p: f.total ? f.detectadas / f.total : 0 }, f));
        fam.innerHTML = '<p class="act-h">Detección del modelo por familia de ataque</p>' + filas.map(f =>
          `<div class="fam"><span class="fam-n">${escSimple(f.familia)}</span>`
          + `<span class="fam-b"><i style="width:${Math.max(1.5, f.p * 100).toFixed(1)}%;background:${f.p < 0.5 ? 'var(--amber)' : 'var(--accent)'}"></i></span>`
          + `<span class="fam-v">${coma(f.p * 100, 0)} %<small>${f.detectadas}/${f.total}</small></span></div>`).join('')
          + `<p class="toolbar-hint">${escSimple(ev.nota || '')} Fuente: ${escSimple(ev.deteccion_kali.fuente)}.</p>`;
        const peor = filas.slice().sort((a, b) => a.p - b.p)[0];
        if (debil && peor) {
          debil.innerHTML = `<strong>Punto débil conocido:</strong> el modelo solo detecta ${peor.detectadas} de ${peor.total} ventanas de `
            + `${escSimple(peor.familia)}. En esa familia, un PERMIT del modelo dice poco: la decisión la sostienen los heurísticos.`;
        }
      } else if (fam) {
        fam.innerHTML = '';
      }
    }

    ACUSES = status.acuses || [];
    ACUSES_V1_HISTORICOS = !!status.acuses_v1_historicos;
    pintarCadenaV2(status.cadena_v2);
    renderVigentes(status.vigentes || [], status.blocked || []);
    AA_VIG = status.vigentes || [];
    try { renderAlertasActivas(); } catch (e) { console.warn('alertas activas', e); }

    const c = status.counters;
    ultimosCounters = c;
    counters.classList.add('wids');
    counters.innerHTML = [
      widget('Ventanas analizadas', (c.total || 0).toLocaleString('es'), 'navy', 'ventanas', 'tráfico puntuado'),
      widget('BLOCK', c.block || 0, c.block > 0 ? 'bad' : '', 'block', 'IP cortada'),
      widget('LIMIT', c.limit || 0, c.limit > 0 ? 'amber' : '', 'limit', 'tasa degradada'),
      widget('IPs con acción', c.ips_con_accion || 0, c.ips_con_accion > 0 ? 'amber' : '', 'ips', 'atacantes distintos'),
      widget('Anomalías del modelo', c.alert_model || 0, c.alert_model > 0 ? 'bad' : '', 'modelo', 'Isolation Forest'),
    ].join('');

    const alcanceEl = document.getElementById('alcance');
    if (alcanceEl) {
      const ex = status.alcance || {};
      // Lo que el motor no midio se muestra «—», no cero: un cero diria que no hubo.
      const cifra = (v) => v == null ? '&mdash;' : Number(v).toLocaleString('es');
      const ile = ex.pcaps_ilegibles;
      alcanceEl.innerHTML = [
        card('Red analizada', ex.red_entidades || '&mdash;', 'txt'),
        card('Plano de control descartado', cifra(ex.plano_control_descartado) + '<small>paquetes</small>'),
        card('Copias del espejo descartadas', cifra(ex.duplicados_espejo) + '<small>paquetes duplicados</small>'),
        card('Ventanas de entidades excluidas', cifra(ex.ventanas_excluidas) + '<small>se cuentan, no se puntúan</small>'),
        card('PCAP que el motor no pudo leer', cifra(ile) + '<small>ficheros del anillo</small>', ile > 0 ? 'amber' : ''),
      ].join('');
      const protos = (ex.protocolos_excluidos || []).map(p => PROTO[p] || ('proto ' + p));
      const motivo = ex.pcaps_ilegibles_motivo ? Object.keys(ex.pcaps_ilegibles_motivo).map(k => k + ': ' + ex.pcaps_ilegibles_motivo[k]).join(' · ') : '';
      document.getElementById('alcanceDetalle').textContent =
        (protos.length ? 'Protocolos fuera del cálculo: ' + protos.join(', ') + '. ' : '') +
        ((ex.excluidas || []).length ? 'Entidades fuera del cálculo: ' + ex.excluidas.join(', ') + '. ' : '') +
        (ile > 0 && motivo ? 'PCAP ilegible: ' + motivo + '. Las cifras son acumuladas desde que arrancó el motor.' : 'Las cifras son acumuladas desde que arrancó el motor.');
    }

    if (currentRange === '1h') renderSparkline(status.activity);
    else loadActivity(currentRange);

    try {
      lastDecisions = await (await fetch('/api/decisions?limit=600')).json();
      decisionesCargadas = true;
      decisionesError = false;
    } catch (e) {
      decisionesError = true;
      throw e;
    }
    markSeenAndCountNewAlerts(lastDecisions);
    renderDecisionsTable();
    renderAlertas();
    renderTopIps();
  } catch (e) {
    errorActualizacion = String(e);
    pintarSello();
    renderAlertas();
  }
}

// Sello de frescura: cuanto hace de la ultima lectura buena, con la hora exacta
// al pasar el raton. Si las lecturas fallan, se dice «datos desactualizados».
let ultimaActualizacion = 0, errorActualizacion = '';
let decisionesCargadas = false, decisionesError = false;
function pintarSello() {
  const el = document.getElementById('stamp');
  if (!el) return;
  if (!ultimaActualizacion) {
    el.textContent = errorActualizacion ? 'Sin conexión con el panel' : 'Conectando…';
    return;
  }
  const s = Math.max(0, Math.round((Date.now() - ultimaActualizacion) / 1000));
  const viejo = s > 20 || errorActualizacion;
  el.textContent = (viejo ? 'Datos desactualizados · ' : '') + 'Actualizado hace ' + (s < 60 ? s + ' s' : Math.floor(s / 60) + ' min');
  el.title = 'Última lectura correcta: ' + new Date(ultimaActualizacion).toLocaleString('es-PE', { hour12: false })
    + (errorActualizacion ? '\\nÚltimo error: ' + errorActualizacion : '');
  el.style.color = viejo ? 'var(--amber)' : '';
}
setInterval(pintarSello, 1000);
(function zonaHoraria() {
  const el = document.getElementById('stampTz');
  if (!el) return;
  let tz = '';
  try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { /* sin Intl */ }
  const off = -new Date().getTimezoneOffset() / 60;
  const utc = 'UTC' + (off === 0 ? '' : (off > 0 ? '+' : '−') + Math.abs(off));
  const nombre = tz === 'America/Lima' ? 'Lima' : (tz.split('/').pop() || '').replace(/_/g, ' ');
  el.textContent = 'Horas: ' + (nombre ? nombre + ' · ' : '') + utc;
  el.title = 'Las horas se muestran en la zona de este navegador. Los registros del motor están en UTC (ventana_end_utc).';
})();

// Seccion C: el filtro y la exportacion trabajan sobre lastDecisions (lo
// que ya esta cargado en el navegador), sin pedir nada nuevo al backend.
let lastDecisions = [];
// Contadores del servidor (ventana real de 60 min). El buffer de 600
// decisiones solo abarca unos minutos, asi que el recuento «de la ultima
// hora» de Alertas se toma de aqui, no del buffer, para cuadrar con Actividad.
let ultimosCounters = null;

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
  const zona = score < e.umbral ? 'anómalo para el modelo' : 'normal para el modelo';
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
// Politica A (3-nov): el modelo SOLO no actua (queda «para revisión humana»);
// actua la regla. Y la infraestructura (gateways, DNS/AD, sensor, bastión) nunca
// recibe accion: = NUNCA_BLOQUEAR de publicar_feed.py.
const MODELO_SOLO_ACTUA = true;   // motor de las campañas (3-nov, noche); política A = false
const NUNCA_BLOQUEAR_JS = new Set(['10.10.10.30', '10.10.60.11', '10.10.30.1', '10.10.40.1',
  '10.10.60.1', '10.10.20.1', '10.10.10.20']);
function esInfraProtegida(d) { return NUNCA_BLOQUEAR_JS.has(String(d.entity_ip || '')); }
function paraRevision(d) {
  return d.decision === 'ALERT' && !String(d.detector_name || '').endsWith('_heuristic')
    && d.politica_modelo === 'sostenida' && !(d.heuristico && d.heuristico.accion);
}
// Cadena v2 (4A): si el servidor adjunta d.cadena_v2, la accion es SOLO la medida que
// publico el publicador v2 (traza). Una anomalia del IF sin medida publicada es PERMIT.
const MEDIDAS_V2 = ['nueva', 'renovada', 'escalada', 'mantenida'];
function medidaV2(d) {
  const m = (d && d.cadena_v2 && d.cadena_v2.medida) || {};
  return (MEDIDAS_V2.includes(m.estado) && (m.accion === 'BLOCK' || m.accion === 'LIMIT')) ? m.accion : 'PERMIT';
}
function accionDeDecision(d) {
  const sev = { BLOCK: 2, LIMIT: 1, PERMIT: 0 };
  let acc = 'PERMIT';
  if (d && d.cadena_v2) return medidaV2(d);
  if (esInfraProtegida(d)) return acc;
  if (d.decision === 'ALERT') {
    if (String(d.detector_name || '').endsWith('_heuristic')) acc = 'BLOCK';
    else if (MODELO_SOLO_ACTUA && (!d.politica_modelo || d.politica_modelo === 'sostenida')) acc = 'LIMIT';
  }
  if (d.heuristico && sev[d.heuristico.accion] > sev[acc]) acc = d.heuristico.accion;
  return acc;
}

// --- Alertas: las ventanas en que el sistema DETECTO algo (modelo o regla) ---
// Una alerta = una decision que provoca una accion (LIMIT/BLOCK): anomalia del
// modelo (score < umbral) o una regla disparada. Es la lista que un operador
// mira primero; el detalle completo esta en Decisiones.
let alertasFiltro = 'todas';
function alertaTipos(d) {
  const det = String(d.detector_name || '');
  const esHeur = det.endsWith('_heuristic');
  const modelo = d.decision === 'ALERT' && !esHeur;
  let regla = (d.heuristico && d.heuristico.heuristico) ? String(d.heuristico.heuristico) : null;
  // Heuristico heredado (motor antiguo): la regla viene en el nombre del detector.
  if (!regla && d.decision === 'ALERT' && esHeur) regla = det.replace(/_heuristic$/, '');
  return { modelo, regla };
}
function pintarBotonMarg() {
  const b = document.getElementById('alertasMarg');
  if (!b) return;
  b.textContent = verMarginales ? 'Marginales: visibles' : 'Marginales: ocultas';
  b.setAttribute('aria-pressed', verMarginales ? 'true' : 'false');
}
document.addEventListener('click', (ev) => {
  if (!ev.target.closest('#alertasMarg, [data-al-marg]')) return;
  verMarginales = !verMarginales;
  pintarBotonMarg();
  renderAlertas();
});
// --- Lista blanca (16-nov): infraestructura conocida (p. ej. Zabbix) agrupada aparte. ---
// Viene de configs/lista-blanca.json por /api/lista-blanca. El panel solo AGRUPA la vista:
// si el feed v2 sigue publicando una medida sobre esa IP, se dice en el bloque.
let LISTA_BLANCA = new Map();
let listaBlancaFeedLeido = false;
let verLB = false;
async function cargarListaBlanca() {
  try {
    const r = await (await fetch('/api/lista-blanca')).json();
    LISTA_BLANCA = new Map((r.entradas || []).map(e => [String(e.ip), e]));
    listaBlancaFeedLeido = !!r.feed_leido;
  } catch (e) { /* sin lista: el panel sigue como siempre */ }
  renderAlertas();
}
function enListaBlanca(ip) { return LISTA_BLANCA.has(String(ip || '')); }
function tarjetaAlerta(d) {
  const coma3 = v => (v == null ? '—' : Number(v).toFixed(3).split('.').join(','));
  const acc = accionDeDecision(d);
  const t = alertaTipos(d);
  const tags = [];
  // Iconos (trazo, 24x24): criticidad y tipo de regla.
  const svg = (p, s) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
  const P_ACC = {
    BLOCK: '<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>',
    LIMIT: '<path d="M12 14l3.5-3.5"/><path d="M4.5 18a8.5 8.5 0 1 1 15 0"/>',
  };
  const P_REGLA = {
    port_scan: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 12l6-6"/>',
    port_scan_temprano: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 12l6-6"/>',
    brute_force: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/>',
    http_abuse: '<path d="M3 7c3-2 6 2 9 0s6-2 9 0M3 12c3-2 6 2 9 0s6-2 9 0M3 17c3-2 6 2 9 0s6-2 9 0"/>',
    dns_entropy: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  };
  const P_MODELO = '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>';
  if (t.modelo || d._modelo) tags.push('<span class="al-tag modelo">' + svg(P_MODELO, 11) + 'Anomalía del modelo</span>');
  if (t.regla) tags.push('<span class="al-tag regla">' + svg(P_REGLA[t.regla] || P_ACC.BLOCK, 11) + 'Regla: ' + varEsc(t.regla) + '</span>');
  if (enListaBlanca(d.entity_ip)) tags.push('<span class="al-tag">Lista blanca</span>');
  const motivo = (d.heuristico && d.heuristico.motivo) ? varEsc(d.heuristico.motivo)
    : (d.score != null ? 'score ' + coma3(d.score) + ' por debajo del umbral ' + coma3(d.threshold) : '');
  const key = d.entity_ip + '|' + d.window_end_utc;
  return `<div class="al-card al-${acc.toLowerCase()}">`
    + `<div class="al-sev">${P_ACC[acc] ? '<span class="al-ico">' + svg(P_ACC[acc], 18) + '</span>' : ''}<span class="badge acc-${acc.toLowerCase()}">${acc}</span></div>`
    + `<div class="al-main"><div class="al-top"><span class="al-ip">${varEsc(d.entity_ip)}</span>`
    + `<span class="al-hace" title="${varEsc(String(d.window_end_utc || ''))} UTC">${fmtTime(d.logged_at)} · ${haceTexto(d.logged_at)}</span>`
    + (d._n > 1 ? `<span class="al-epi" title="Ventanas de 10 s del mismo episodio, agrupadas">${d._n} ventanas · desde ${fmtTime(d._desde)}</span>` : '')
    + `</div>`
    + `<div class="al-tags">${tags.join(' ')}</div>`
    + `<div class="al-motivo">${motivo}</div></div>`
    + `<div class="al-ver">${miniBarraScore(d.score)}<button type="button" class="btn-sec" data-ver-dec="${varEsc(key)}" data-ip="${varEsc(d.entity_ip)}">Ver decisión &rarr;</button></div></div>`;
}
let lbAbierta = false;
function renderListaBlanca(alertasLB) {
  const caja = document.getElementById('alertasListaBlanca');
  if (!caja) return;
  if (!LISTA_BLANCA.size) { caja.hidden = true; caja.innerHTML = ''; return; }
  caja.hidden = false;
  const filas = [...LISTA_BLANCA.values()].map(e => {
    const suyas = alertasLB.filter(d => String(d.entity_ip) === e.ip);
    const ult = suyas.length ? Math.max(...suyas.map(d => d.logged_at || 0)) : null;
    const reglas = [...new Set(suyas.map(d => alertaTipos(d).regla || (alertaTipos(d).modelo ? 'modelo' : '')).filter(Boolean))];
    const m = e.medida_feed;
    const feedTxt = m
      ? `<span class="lb-aviso"><span class="badge acc-${String(m.accion).toLowerCase()}">${varEsc(m.accion)}</span> el publicador aún la emite hacia ${varEsc(m.destino || '—')} (vigente hasta ${fmtTime(m.hasta)}): esta lista solo agrupa la vista.</span>`
      : (listaBlancaFeedLeido ? 'sin medida vigente en el feed' : 'feed no disponible');
    // 17-nov: el motivo largo pasa al title; en pantalla, nombre y fecha de alta.
    return `<div class="lb-fila"><div title="${varEsc(e.motivo)}"><span class="lb-ip">${varEsc(e.ip)}</span><span class="lb-nom">${varEsc(e.nombre)}</span>`
      + (e.alta ? `<div class="lb-det">en la lista desde ${varEsc(e.alta)}</div>` : '')
      + `<div class="lb-det">${suyas.length} alerta(s) en los registros cargados${ult ? ' · última ' + fmtTime(ult) + ' (' + haceTexto(ult) + ')' : ''}${reglas.length ? ' · ' + varEsc(reglas.join(', ')) : ''} · ${feedTxt}</div></div>`
      + (suyas.length ? `<button type="button" class="btn-sec neutro" data-lb-ver="1">${verLB ? 'Ocultar' : 'Ver'} sus alertas</button>` : '<span></span>')
      + (verLB && suyas.length ? `<div class="lb-tarjetas">${suyas.slice(0, 20).map(tarjetaAlerta).join('')}</div>` : '')
      + `</div>`;
  }).join('');
  // 17-nov: plegada por defecto; recuerda si el usuario la abrió (se repinta en cada sondeo).
  caja.innerHTML = `<details class="lb-plegable"${lbAbierta ? ' open' : ''}>`
    + `<summary title="Sus alertas se agrupan aquí y no en la lista de arriba. Se edita en configs/lista-blanca.json del sensor.">`
    + `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>`
    + `Lista blanca <span class="lb-n">${LISTA_BLANCA.size}</span></summary>` + filas + `</details>`;
  const dt = caja.querySelector('details');
  if (dt) dt.addEventListener('toggle', () => { lbAbierta = dt.open; });
}
on('alertasListaBlanca', 'click', (ev) => {
  if (ev.target.closest('[data-lb-ver]')) { verLB = !verLB; renderAlertas(); return; }
  const b = ev.target.closest('[data-ver-dec]');
  if (b) abrirDecision(b.dataset.ip, b.dataset.verDec);
});
// Una sola tarjeta por episodio: ventanas seguidas de la misma IP, acción y regla
// (huecos de hasta 2 min) se funden en la más reciente, con su número de ventanas.
function agruparEpisodios(rows) {
  const ord = rows.slice().sort((a, b) => (b.logged_at || 0) - (a.logged_at || 0));
  const out = [], abiertos = new Map();
  for (const d of ord) {
    const t = alertaTipos(d);
    const k = d.entity_ip + '|' + accionDeDecision(d) + '|' + (t.regla || (t.modelo ? 'modelo' : ''));
    const g = abiertos.get(k);
    if (g && (g._desde - (d.logged_at || 0)) <= 120) { g._n += 1; g._desde = d.logged_at || g._desde; g._modelo = g._modelo || t.modelo; continue; }
    const nuevo = Object.assign({}, d, { _n: 1, _desde: d.logged_at || 0, _modelo: t.modelo });
    abiertos.set(k, nuevo); out.push(nuevo);
  }
  return out;
}
function renderAlertas() {
  const lista = document.getElementById('alertasLista');
  const resumen = document.getElementById('alertasResumen');
  if (!lista || !resumen) return;
  const todasConLB = (lastDecisions || []).filter(d => accionDeDecision(d) !== 'PERMIT');
  const alertasLB = todasConLB.filter(d => enListaBlanca(d.entity_ip));
  renderListaBlanca(alertasLB);
  const todas = todasConLB.filter(d => !enListaBlanca(d.entity_ip) && (!limpioDesde || (d.logged_at || 0) >= limpioDesde));
  const ahora = Date.now() / 1000;
  const h = todas.filter(d => ahora - (d.logged_at || 0) <= 3600);
  // El recuento de la hora viene de los contadores del servidor (ventana real
  // de 60 min); el buffer de 600 decisiones solo abarca unos minutos, asi que
  // tomarlo de ahi daria menos alertas que Actividad y el indicador del menu.
  const c = ultimosCounters || {};
  const hayCont = (c.block != null) || (c.limit != null);
  const totalHora = hayCont ? (c.block || 0) + (c.limit || 0) : h.length;
  const nMod = (c.alert_model != null) ? c.alert_model : h.filter(d => alertaTipos(d).modelo).length;
  const nReg = hayCont ? Math.max(0, totalHora - nMod) : h.filter(d => alertaTipos(d).regla).length;
  const nMargH = (c.alert_model_marginal != null) ? c.alert_model_marginal : h.filter(esMarginal).length;
  // Politica A: alerta = lo que provoca accion (una regla). El modelo solo queda
  // «para revision» y la infraestructura protegida nunca se actua: se cuentan aparte.
  const relev = (c.acciones_relevantes != null) ? c.acciones_relevantes : Math.max(0, totalHora - nMargH);
  const nRegla = (c.acciones_regla != null) ? c.acciones_regla : h.filter(d => alertaTipos(d).regla).length;
  // 17-nov: el desglose va en fichas con icono; la explicación larga queda en el title.
  const ICO = {
    regla: '<path d="M4 6h3M4 12h3M4 18h3M10 6h10M10 12h10M10 18h10"/>',
    modelo: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
    infra: '<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z"/>',
    lb: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    marg: '<path d="M3 12h4l2-4 4 8 2-4h6"/>',
  };
  const ficha = (ico, n, txt, tit) => `<span class="al-ficha" title="${varEsc(tit)}">`
    + `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${ICO[ico]}</svg>`
    + `<b>${n}</b> ${txt}</span>`;
  const epis = agruparEpisodios(todas);
  const nVista = limpioDesde ? epis.length : relev;
  resumen.innerHTML = `<div class="al-num ${nVista ? 'hay' : ''}">${nVista}</div>`
    + `<div class="al-num-t">${limpioDesde ? 'alertas desde la limpieza de las ' + fmtTime(limpioDesde) + ' <button type="button" class="btn-link" data-al-historial="1">Ver historial</button>' : 'alertas con acción · última hora'}<div class="al-fichas">`
    + ficha('regla', nRegla, 'por regla', 'Alertas que dispararon una regla (escaneo, fuerza bruta, abuso HTTP, DNS) y provocan LIMIT o BLOCK.')
    + ficha('modelo', c.revision_modelo || 0, 'solo modelo', 'Anomalías solo del Isolation Forest: quedan para revisión, sin acción.')
    + ficha('infra', c.infra_protegida || 0, 'infraestructura', 'Detecciones sobre infraestructura protegida: nunca se actúa sobre ellas.')
    + (LISTA_BLANCA.size ? ficha('lb', alertasLB.length, 'lista blanca', 'Alertas de IPs en la lista blanca: se muestran abajo, aparte.') : '')
    + ficha('marg', nMargH, 'marginales', 'Score a menos de 0,05 del umbral; ' + (verMarginales ? 'visibles.' : 'agrupadas.'))
    + `</div></div>`;
  // Estados vacios: dependen de por que no hay filas. Una lista filtrada vacia
  // NUNCA permite concluir que el sistema este en PERMIT.
  const vacio = (txt, boton) => {
    lista.innerHTML = `<p class="estado-vacio">${txt}${boton || ''}</p>`;
  };
  if (decisionesError && !decisionesCargadas) {
    vacio('No se pudieron cargar las alertas.', ' <button type="button" class="btn-sec" data-al-reintentar="1">Reintentar</button>');
    return;
  }
  if (!decisionesCargadas) { vacio('Cargando alertas…'); return; }
  if (!(lastDecisions || []).length) { vacio('Todavía no se han recibido registros del motor.'); return; }
  if (limpioDesde && !todas.length) { vacio('Todo limpio: sin alertas desde las ' + fmtTime(limpioDesde) + '.', ' <button type="button" class="btn-sec neutro" data-al-historial="1">Ver historial</button>'); return; }
  const ipQ = ((document.getElementById('alertasIp') || {}).value || '').trim();
  let rows = todas;
  const nMargLista = rows.filter(esMarginal).length;
  if (!verMarginales) rows = rows.filter(d => !esMarginal(d));
  if (alertasFiltro === 'modelo') rows = rows.filter(d => alertaTipos(d).modelo);
  if (alertasFiltro === 'regla') rows = rows.filter(d => alertaTipos(d).regla);
  if (alertasAccion !== 'todas') rows = rows.filter(d => accionDeDecision(d) === alertasAccion);
  if (ipQ) rows = rows.filter(d => String(d.entity_ip).includes(ipQ));
  rows = agruparEpisodios(rows).slice(0, 80);
  if (!rows.length) {
    const limpiar = ' <button type="button" class="btn-sec neutro" data-al-limpiar="1">Limpiar filtros</button>';
    if (!verMarginales && nMargLista) vacio('Ahora solo hay anomalías marginales del modelo (' + nMargLista + '): score a menos de 0,05 del umbral.', ' <button type="button" class="btn-sec neutro" data-al-marg="1">Mostrarlas</button>');
    else if (ipQ) vacio('No encontramos alertas para esta IP en la lista cargada.', limpiar);
    else if (alertasFiltro === 'regla') vacio('No hay alertas de reglas en los registros cargados. Puede haber anomalías del modelo; consulta «Todas».', limpiar);
    else if (alertasFiltro === 'modelo') vacio('No hay anomalías del modelo en los registros cargados. Puede haber alertas de reglas; consulta «Todas».', limpiar);
    else if (alertasAccion !== 'todas') vacio('No hay alertas con ' + alertasAccion + ' en los registros cargados.', limpiar);
    else vacio('No hay alertas en los registros cargados (' + lastDecisions.length + ' decisiones, desde las ' + fmtTime(Math.min(...lastDecisions.map(d => d.logged_at || Infinity))) + '). Para periodos anteriores, consulta Decisiones.');
    return;
  }
  lista.innerHTML = rows.map(tarjetaAlerta).join('');
}
let alertasAccion = 'todas';
on('alertasFiltro', 'click', (ev) => {
  const b = ev.target.closest('button[data-af]');
  if (!b) return;
  alertasFiltro = b.dataset.af;
  document.querySelectorAll('#alertasFiltro button').forEach(x => x.classList.toggle('active', x === b));
  renderAlertas();
});
on('alertasAccion', 'click', (ev) => {
  const b = ev.target.closest('button[data-aa]');
  if (!b) return;
  alertasAccion = b.dataset.aa;
  document.querySelectorAll('#alertasAccion button').forEach(x => x.classList.toggle('active', x === b));
  renderAlertas();
});
on('alertasIp', 'input', () => renderAlertas());
document.addEventListener('click', ev => { if (ev.target.closest('[data-al-historial]')) vistaLimpiaDesde(0); });
function limpiarFiltrosAlertas() {
  alertasFiltro = 'todas'; alertasAccion = 'todas';
  const ip = document.getElementById('alertasIp');
  if (ip) ip.value = '';
  document.querySelectorAll('#alertasFiltro button').forEach(x => x.classList.toggle('active', x.dataset.af === 'todas'));
  document.querySelectorAll('#alertasAccion button').forEach(x => x.classList.toggle('active', x.dataset.aa === 'todas'));
  renderAlertas();
}
on('alertasLimpiar', 'click', limpiarFiltrosAlertas);
on('alertasLista', 'click', (ev) => {
  if (ev.target.closest('[data-al-limpiar]')) { limpiarFiltrosAlertas(); return; }
  if (ev.target.closest('[data-al-reintentar]')) { refresh(); return; }
  const b = ev.target.closest('[data-ver-dec]');
  if (b) abrirDecision(b.dataset.ip, b.dataset.verDec);
});
// Salta de una alerta (o respuesta) a su decision: filtra por IP, abre su
// detalle y la deja a la vista. El detalle sigue abierto en los refrescos.
function abrirDecision(ip, key) {
  const f = document.getElementById('ipFilter');
  if (f) f.value = ip || '';
  decVista = 'todas'; pintarDecVista();
  if (key) decAbiertas.add(key);
  renderDecisionsTable();
  mostrarSeccion('s-decisiones');
  if (key) {
    const tr = [...document.querySelectorAll('#decisions tr.dec-fila')].find(t => t.dataset.key === key);
    if (tr) tr.scrollIntoView({ block: 'center' });
  }
}

function haceTexto(t) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  if (s < 60) return 'hace ' + s + ' s';
  if (s < 3600) return 'hace ' + Math.floor(s / 60) + ' min';
  return 'hace ' + Math.floor(s / 3600) + ' h';
}

function duracionTexto(s) {
  if (s < 60) return s + ' s';
  const m = Math.floor(s / 60), r = s % 60;
  return m + ' min' + (r ? ' ' + r + ' s' : '');
}

// Lo que cada host protegido dice tener para una IP (acuse que trae el relay).
let ACUSES = [];
let ACUSES_V1_HISTORICOS = false;
// Cadena v2 (4A): franja de estado y panel de solo lectura («Preparar demo» oculto).
// Texto de la franja (función pura: se prueba con Node). Las incidencias de las fuentes se
// muestran tal cual; una fuente ausente NUNCA se presenta como cero medidas o normalidad.
function franjaV2HTML(cv) {
  // 16-nov: la misma información, en fichas cortas dentro de la columna de contenido
  // (antes una línea corrida sobre la barra lateral) y con «¿Qué es el modo sombra?».
  const fu = cv.fuentes || {};
  const okF = k => !!(fu[k] && fu[k].ok);
  const est = k => okF(k) ? 'ok' : '<b>ausente o ilegible</b>';
  const inc = cv.incidencias || [];
  const medidas = (fu.feed && fu.feed.ok) ? (cv.feed_entradas || 0) + ' medida(s) en el feed' : 'medidas en el feed: <b>desconocido</b>';
  const ficha = (txt, cls, tit) => '<span class="cv2-ficha' + (cls ? ' ' + cls : '') + '"' + (tit ? ' title="' + varEsc(tit) + '"' : '') + '>' + txt + '</span>';
  const fuentesOk = okF('senales_if') && okF('traza') && okF('feed');
  // 16-nov: con todo sano la franja no se muestra (pedido de Mark); solo aparece si una fuente
  // falta, el feed está atrasado o hay incidencias, para que un problema nunca quede oculto.
  if (fuentesOk && !cv.feed_atrasado && !inc.length) return '';
  // 18-nov (pedido de Mark): la franja NUNCA muestra el estado normal (política, «modo sombra»,
  // «solo lectura», acuse del agente, nº de medidas). Solo asoma el FALLO real —fuente ausente,
  // feed atrasado o incidencia— para que un problema no quede oculto durante la demo.
  const fallos = [];
  if (cv.feed_atrasado) fallos.push(ficha('Feed v2 atrasado', 'mal', 'El publicador v2 no refresca el feed'));
  if (!(fu.feed && fu.feed.ok)) fallos.push(ficha(medidas, 'mal'));
  if (!fuentesOk) fallos.push(ficha('Fuentes: señales IF ' + est('senales_if') + ', traza ' + est('traza') + ', feed ' + est('feed'), 'mal'));
  return (fallos.length ? '<div class="cv2-fichas">' + fallos.join('') + '</div>' : '')
    + (inc.length ? '<div class="cv2-inc"><b class="est no">INCIDENCIA: ' + inc.map(varEsc).join(' · ') + '</b></div>' : '');
}
function pintarCadenaV2(cv) {
  const activa = !!(cv && cv.activa);
  const b = document.getElementById('prepBtn');
  // Solo se oculta, nunca se vuelve a mostrar: en modo v2 el servidor ya lo sirve oculto
  // y una respuesta fallida de /api/status no debe reactivarlo.
  if (b && activa) { b.hidden = true; b.disabled = true; }
  const lb = document.getElementById('limpiarBtn'), pt = document.getElementById('prepTxt');
  if (lb && activa && lb.hidden) {
    lb.hidden = false;
    if (pt) pt.textContent = 'Quita las medidas vigentes de la Kali (10.10.20.30) del feed y reinicia el seguimiento. Púlsalo antes de cada demo.';
  }
  let f = document.getElementById('cadenaV2Franja');
  if (!activa) { if (f) f.remove(); return; }
  if (!f) {
    f = document.createElement('div');
    f.id = 'cadenaV2Franja';
    f.className = 'cv2-franja';
    f.setAttribute('role', 'status');
    // Dentro de la columna de contenido, bajo la cabecera (no sobre la barra lateral).
    const wrap = document.querySelector('.wrap') || document.body;
    const cab = wrap.querySelector(':scope > header');
    wrap.insertBefore(f, cab ? cab.nextSibling : wrap.firstChild);
  }
  f.innerHTML = franjaV2HTML(cv);
  f.hidden = !f.innerHTML;
}
function estadoEnHosts(ip) {
  if (ACUSES_V1_HISTORICOS) {
    // El agente v1 está parado: su acuse es evidencia HISTÓRICA, no el estado actual del host.
    const r = ACUSES.map(a => (a.reglas || {})[ip] ? varEsc(a.host) + ': ' + varEsc(a.reglas[ip].accion) : null).filter(Boolean);
    return r.length ? `<span class="est no" title="Acuse del agente v1 (parado): evidencia histórica">aplicación v1 (histórica): ${r.join(', ')}</span>`
      : '<span class="est no" title="El agente v2 no envía acuse al sensor">host: sin evidencia de aplicación</span>';
  }
  if (!ACUSES.length) return '<span class="est no" title="Ningún host ha enviado su acuse">host: sin acuse</span>';
  return ACUSES.map(a => {
    const h = varEsc(a.host);
    if (a.atrasado) return `<span class="est no" title="El último acuse tiene ${Math.round(a.edad || 0)} s">${h}: acuse atrasado</span>`;
    const r = (a.reglas || {})[ip];
    if (r) return `<span class="est si" title="Según el propio host">${h}: ${varEsc(r.accion)} aplicado</span>`;
    if ((a.liberadas || {})[ip]) return `<span class="est lib" title="Un humano la liberó en el host">${h}: liberada</span>`;
    const motivo = String((a.sombra || {})[ip] || '');
    if (motivo.startsWith('liberada')) return `<span class="est lib" title="Un humano la liberó en el host">${h}: liberada</span>`;
    if (motivo) return `<span class="est no" title="${varEsc(motivo)}">${h}: no se aplica (fuera de alcance)</span>`;
    return `<span class="est no">${h}: sin regla</span>`;
  }).join('');
}
function aplicadasEnHostsDe(acuses) {
  const ips = new Set();
  (acuses || []).forEach(a => { if (!a.atrasado) Object.keys(a.reglas || {}).forEach(ip => ips.add(ip)); });
  return ips.size;
}

// Acciones vigentes: del feed publicado (caducidad exacta) o reconstruidas del
// registro con la misma escalera. Si el host tuviera nftables local, tambien.
function renderVigentes(vigentes, locales) {
  const ahora = Date.now() / 1000;
  const filas = vigentes.map(v => {
    const total = v.accion === 'BLOCK' ? ({ 1: 300, 2: 1800, 3: 3600 }[v.nivel] || 300) + 60 : 360;
    const pct = Math.max(2, Math.min(100, Math.round(100 * v.expira_s / total)));
    const color = v.accion === 'BLOCK' ? 'var(--danger)' : 'var(--amber)';
    const reinc = v.accion === 'BLOCK'
      ? 'reincidencia nivel ' + (v.nivel || 1) + (v.revisar_humano ? ' · revisar' : '')
      : '';
    const caducaEn = ahora + (v.expira_s || 0);
    const registrada = v.registrada !== false;
    const publicada = v.publicada != null ? v.publicada : v.fuente === 'feed';
    const estados = v.fuente === 'feed_v2'
      ? `<span class="est si">publicada en el feed v2</span>`
        + `<span class="est no">${varEsc(v.estado_respuesta || 'propuesta')}</span>`
        + `<span class="est no">aplicación: ${v.aplicacion === 'no_ejecutada' ? 'no ejecutada (sombra)' : 'desconocida'}</span>`
        + `<span class="est no">efecto: sin evidencia</span>`
      : `<span class="est ${registrada ? 'si' : 'no'}">${registrada ? 'registrada' : 'solo en el feed'}</span>`
      + `<span class="est ${publicada ? 'si' : 'no'}">${publicada ? 'publicada' : 'no vista en el feed'}</span>`
      + estadoEnHosts(v.ip);
    return `<tr class="row-${v.accion.toLowerCase()}"><td class="ip">${varEsc(v.ip)}</td>`
      + `<td><span class="badge acc-${v.accion.toLowerCase()}">${v.accion}</span>${reinc ? '<span class="hace">' + reinc + '</span>' : ''}</td>`
      + `<td class="why"><span class="clamp">${varEsc(v.origen || '')}${v.motivo ? ' · ' + varEsc(v.motivo) : ''}</span></td>`
      + `<td class="num">${v.desde ? fmtTime(v.desde) : '—'}${v.ultima ? '<span class="hace">renovada ' + fmtTime(v.ultima) + (v.ofensas ? ' · ' + v.ofensas + ' ventanas' : '') + '</span>' : ''}</td>`
      + `<td class="num">${fmtTime(caducaEn)}<span class="hace">en ${duracionTexto(v.expira_s)}</span><div class="vig-barra"><i style="width:${pct}%;background:${color}"></i></div></td>`
      + `<td>${estados}<div><button type="button" class="btn-sec" data-ver-ip="${varEsc(v.ip)}">Ver decisiones &rarr;</button></div></td></tr>`;
  });
  for (const b of locales) {
    filas.push(`<tr class="row-block"><td class="ip">${varEsc(b.ip)}</td><td><span class="badge acc-block">BLOCK</span></td>`
      + `<td class="why">nftables de este equipo</td><td class="num">—</td>`
      + `<td class="num">${b.expires_seconds != null ? 'en ' + duracionTexto(b.expires_seconds) : '?'}</td>`
      + `<td><span class="est si">aplicada en este equipo</span></td></tr>`);
  }
  const n = document.getElementById('vigentesN');
  if (n) n.textContent = vigentes.length + ' según registro y feed' + (locales.length ? ' · ' + locales.length + ' en el nftables de este equipo' : '');
  document.getElementById('blocked').innerHTML = filas.length ? filas.join('')
    : '<tr class="empty-row"><td colspan="6">Ninguna respuesta registrada como vigente. Esto no comprueba el estado del nftables del host.</td></tr>';
}
on('blocked', 'click', (ev) => {
  const b = ev.target.closest('[data-ver-ip]');
  if (b) abrirDecision(b.dataset.verIp, null);
});

// Historial de acciones: lo que ya paso, no solo lo vigente. Una fila por IP en
// la linea de tiempo; la zona anterior al registro leido se raya, porque ahi no
// se sabe si hubo acciones.
function renderHistorial(d) {
  const svg = document.getElementById('histChart'), tb = document.getElementById('histTabla');
  if (!svg || !tb || !d) return;
  const eps = d.episodios || [];
  const t1 = d.ahora, t0 = d.ahora - d.horas * 3600;
  const corto = d.desde != null && d.desde > t0 + 600;
  document.getElementById('histSub').textContent = eps.length + ' episodio' + (eps.length === 1 ? '' : 's')
    + (corto ? ' · el registro leído empieza a las ' + fmtTime(d.desde) : '');
  const ips = [];
  eps.forEach(e => { if (ips.indexOf(e.ip) < 0) ips.push(e.ip); });
  const rw = document.getElementById('respWids');
  if (rw) {
    const nB = eps.filter(e => e.accion === 'BLOCK').length, nL = eps.filter(e => e.accion === 'LIMIT').length;
    const vig = (typeof AA_VIG !== 'undefined' && AA_VIG) ? AA_VIG.length : 0;
    rw.innerHTML = [
      widget('Vigentes ahora', vig, vig ? 'bad' : 'ok', 'escudo', vig ? 'IP con medida activa' : 'ninguna IP restringida'),
      widget('Episodios BLOCK', nB, nB ? 'bad' : '', 'block', 'últimas ' + d.horas + ' h'),
      widget('Episodios LIMIT', nL, nL ? 'amber' : '', 'limit', 'últimas ' + d.horas + ' h'),
      widget('IPs afectadas', ips.length, ips.length ? 'navy' : '', 'ips', 'distintas en el periodo'),
    ].join('');
  }
  const filas = ips.slice(0, 10);
  const W = Math.max(320, svg.clientWidth || 900), FH = 24, Y0 = 8;
  const H = Y0 + Math.max(1, filas.length) * FH + 26;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.style.height = H + 'px';
  const X0 = 118, X1 = W - 12, YB = Y0 + Math.max(1, filas.length) * FH;
  const px = t => X0 + (Math.max(t0, t) - t0) / (t1 - t0) * (X1 - X0);
  let g = '<defs><pattern id="histRaya" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
    + '<line x1="0" y1="0" x2="0" y2="6" stroke="var(--border)" stroke-width="2"/></pattern></defs>';
  if (corto) g += `<rect x="${X0}" y="${Y0}" width="${(px(d.desde) - X0).toFixed(1)}" height="${YB - Y0}" fill="url(#histRaya)"><title>Anterior al registro leído</title></rect>`;
  for (let i = 0; i <= 4; i++) {
    const x = X0 + (X1 - X0) * i / 4;
    g += `<line x1="${x.toFixed(1)}" y1="${Y0}" x2="${x.toFixed(1)}" y2="${YB + 3}" stroke="var(--border)"${i ? ' stroke-dasharray="2 4"' : ''}/>`;
    g += `<text x="${x.toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 ? 'start' : (i === 4 ? 'end' : 'middle')}">${i === 4 ? 'ahora' : '−' + (d.horas - d.horas * i / 4) + ' h'}</text>`;
  }
  g += `<line x1="${X0}" y1="${YB}" x2="${X1}" y2="${YB}" stroke="var(--border)"/>`;
  if (!filas.length) {
    g += `<text x="${(X0 + X1) / 2}" y="${Y0 + FH / 2 + 4}" text-anchor="middle">Sin acciones en este tramo</text>`;
  }
  filas.forEach((ip, k) => {
    const y = Y0 + k * FH;
    g += `<text x="${X0 - 8}" y="${y + FH / 2 + 3}" text-anchor="end" style="fill:var(--text)">${varEsc(ip)}</text>`;
    if (k) g += `<line x1="${X0}" y1="${y}" x2="${X1}" y2="${y}" stroke="var(--border)" stroke-opacity="0.5"/>`;
    // LIMIT primero: un BLOCK de la misma IP se dibuja encima y no queda tapado.
    ['LIMIT', 'BLOCK'].forEach(tipo => eps.forEach(e => {
      if (e.ip !== ip || e.accion !== tipo) return;
      const xa = px(e.inicio), xb = Math.max(px(e.fin), xa + 4);
      g += `<rect x="${xa.toFixed(1)}" y="${y + 5}" width="${(xb - xa).toFixed(1)}" height="${FH - 10}" rx="3" fill="${tipo === 'BLOCK' ? 'var(--danger)' : 'var(--amber)'}">`
        + `<title>${varEsc(ip)} · ${tipo} · ${fmtTime(e.inicio)} · ${e.ventanas} ventana(s) · ${varEsc(e.motivo || e.origen)}</title></rect>`;
    }));
  });
  svg.innerHTML = g;
  tb.innerHTML = eps.length ? eps.slice(0, 60).map(e => {
    const dur = Math.round(e.fin - e.inicio);
    // Racha = cuanto duraron las decisiones; caducidad = lo que se configuro
    // que dure la accion tras la ultima. Lo aplicado en el host no se ve aqui.
    const cadConf = e.accion === 'BLOCK' ? '300 s (nivel 1; 1800/3600 s si reincide)' : '300 s';
    return `<tr class="row-${e.accion.toLowerCase()}" data-ip="${varEsc(e.ip)}" style="cursor:pointer" title="Pulsa para ver las decisiones de esta IP">`
      + `<td class="num">${fmtTime(e.inicio)}<span class="hace">${haceTexto(e.inicio)}</span></td>`
      + `<td class="ip">${varEsc(e.ip)}</td><td><span class="badge acc-${e.accion.toLowerCase()}">${e.accion}</span></td>`
      + `<td class="why"><span class="clamp">${e.origen && e.origen !== 'modelo' ? '<span class="badge heur">' + varEsc(e.origen) + '</span> ' : ''}${varEsc(e.motivo || '')}</span></td>`
      + `<td class="num">${dur > 0 ? duracionTexto(dur) : 'una ventana'}<span class="hace">${fmtTime(e.inicio)}–${fmtTime(e.fin)}</span></td>`
      + `<td class="num">${cadConf}${e.caduca ? '<span class="hace">hasta ' + fmtTime(e.caduca) + '</span>' : ''}</td>`
      + `<td class="num r">${e.ventanas}</td>`
      + `<td>${e.vigente ? '<span class="badge acc-' + e.accion.toLowerCase() + '">vigente</span>' : '<span class="hace" style="display:inline">caducada</span>'}</td>`
      + `<td><button type="button" class="btn-sec">Ver &rarr;</button></td></tr>`;
  }).join('') : '<tr class="empty-row"><td colspan="9">Ninguna respuesta registrada en este tramo.</td></tr>';
}
async function cargarHistorial() {
  if (!document.getElementById('histChart')) return;
  try {
    const d = await (await fetch('/api/acciones')).json();
    renderHistorial(d);
    AA_EPS = (d && d.episodios) || [];
    renderAlertasActivas();
  } catch (e) { /* se reintenta en el siguiente ciclo */ }
}
cargarHistorial();
setInterval(cargarHistorial, 30000);

// ---- G2 · Alertas activas en el Resumen (validacion externa, R3) -----------
// Cada IP limitada o bloqueada AHORA, con su regla, accion, desde y caducidad,
// a un clic de su respuesta, de su decision y de su flujo en el Mapa. Sale de
// status.vigentes (cada 5 s), asi que un ataque aparece sin cambiar de seccion.
// Debajo, las ultimas respuestas ya caducadas, atenuadas. `var` y no `let`:
// refresh() llama aqui antes de que este bloque se evalue.
// Sin inicializador: un `var x = []` evaluado despues borraria lo ya recibido.
var AA_VIG, AA_EPS, aaVistas, aaListo;   // aaVistas: ip|accion -> cuando la vio este navegador
var AA_NUEVA_S = 60;

function aaEsNueva(v, ahora) {
  const k = v.ip + '|' + v.accion, vista = aaVistas.get(k);
  return (v.desde && ahora - v.desde < 60) || (vista && ahora - vista < 60);
}

function renderAlertasActivas() {
  const caja = document.getElementById('alertasActivas');
  if (!caja) return;
  AA_VIG = AA_VIG || []; AA_EPS = AA_EPS || []; aaVistas = aaVistas || new Map();
  const aaPrimera = !aaListo; aaListo = true;   // en la primera pintada nada cuenta como «nueva»
  const ahora = Date.now() / 1000;
  const vig = AA_VIG.filter(v => !NUNCA_BLOQUEAR_JS.has(String(v.ip)));
  const claves = new Set(vig.map(v => v.ip + '|' + v.accion));
  for (const k of claves) if (!aaVistas.has(k)) aaVistas.set(k, aaPrimera ? 0 : ahora);
  for (const k of [...aaVistas.keys()]) if (!claves.has(k)) aaVistas.delete(k);
  const vigIps = new Set(vig.map(v => v.ip));
  const cad = AA_EPS.filter(e => !e.vigente && !vigIps.has(e.ip) && !NUNCA_BLOQUEAR_JS.has(String(e.ip))).slice(0, 3);
  const regla = (o, m) => (o && o !== 'modelo' ? '<span class="badge heur">' + varEsc(o) + '</span> ' : (o ? 'modelo · ' : '')) + varEsc(m || '');
  const botones = ip => `<button type="button" class="btn-sec" data-aa-resp="${varEsc(ip)}">Respuesta &rarr;</button>`
    + `<button type="button" class="btn-sec" data-aa-dec="${varEsc(ip)}">Decisión &rarr;</button>`
    + (document.getElementById('topo') ? `<button type="button" class="btn-sec" data-aa-mapa="${varEsc(ip)}">Mapa &rarr;</button>` : '');
  const icoAcc = a => a === 'block'
    ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/></svg>'
    : (a === 'limit' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 14l3.5-3.5"/><path d="M4.5 18a8.5 8.5 0 1 1 15 0"/></svg>' : '');
  const filas = vig.map(v => {
    const nueva = aaEsNueva(v, ahora), a = String(v.accion || '').toLowerCase();
    return `<tr class="row-${a}${nueva ? ' aa-nueva' : ''}"><td class="ip">${varEsc(v.ip)}${nueva ? '<span class="nueva-tag">NUEVA</span>' : ''}</td>`
      + `<td><span class="badge acc-${a}">${icoAcc(a)}${varEsc(v.accion)}</span></td>`
      + `<td class="why"><span class="clamp">${regla(v.origen, v.motivo)}</span></td>`
      + `<td class="num col-ext">${v.desde ? fmtTime(v.desde) + '<span class="hace">' + haceTexto(v.desde) + '</span>' : '—'}</td>`
      + `<td class="num col-ext">${fmtTime(ahora + (v.expira_s || 0))}<span class="hace">en ${duracionTexto(Math.round(v.expira_s || 0))}</span></td>`
      + `<td class="ir">${botones(v.ip)}</td></tr>`;
  });
  const filasCad = cad.map(e => {
    const a = String(e.accion || '').toLowerCase();
    return `<tr class="row-${a} caducada"><td class="ip">${varEsc(e.ip)}</td>`
      + `<td><span class="badge acc-${a}">${icoAcc(a)}${varEsc(e.accion)}</span></td>`
      + `<td class="why"><span class="clamp">${regla(e.origen, e.motivo)}</span></td>`
      + `<td class="num col-ext">${fmtTime(e.inicio)}<span class="hace">${haceTexto(e.inicio)}</span></td>`
      + `<td class="num col-ext">${e.caduca ? 'caducó ' + fmtTime(e.caduca) + '<span class="hace">' + haceTexto(e.caduca) + '</span>' : 'caducada'}</td>`
      + `<td class="ir">${botones(e.ip)}</td></tr>`;
  });
  caja.classList.toggle('con-activas', vig.length > 0);
  const cab = `<div class="aa-cab"><h3>Alertas activas</h3><span class="n">${vig.length}</span>`
    + `<span class="th-sub">IPs limitadas o bloqueadas ahora · se actualiza cada 5 s</span></div>`;
  const vacio = vig.length ? '' : '<p class="aa-vacio">Ninguna IP limitada ni bloqueada en este momento.</p>';
  const tabla = (filas.length || filasCad.length)
    ? '<table><thead><tr><th>IP</th><th>Acción</th><th>Regla y motivo</th><th class="col-ext">Desde</th><th class="col-ext">Caduca</th><th></th></tr></thead><tbody>'
      + filas.join('') + (filasCad.length ? '<tr class="aa-sep"><td colspan="6">Últimas respuestas, ya caducadas</td></tr>' + filasCad.join('') : '')
      + '</tbody></table>'
    : '';
  caja.innerHTML = cab + vacio + tabla;
  try { renderFlujoBar(); } catch (e) { /* el Mapa aun no esta listo: el siguiente ciclo */ }
}

function irARespuesta(ip) {
  mostrarSeccion('s-bloqueos');
  setTimeout(() => {
    const tr = [...document.querySelectorAll('#blocked tr, #histTabla tr')].find(t => t.textContent.includes(ip));
    if (tr && typeof rgResaltar === 'function') rgResaltar(tr);
  }, 150);
}
on('alertasActivas', 'click', (ev) => {
  const b = ev.target.closest('button');
  if (!b) return;
  if (b.dataset.aaResp) irARespuesta(b.dataset.aaResp);
  else if (b.dataset.aaDec) abrirDecision(b.dataset.aaDec, null);
  else if (b.dataset.aaMapa) {
    flujoIp = b.dataset.aaMapa;
    if (topoVista !== 'completa') {
      topoVista = 'completa';
      document.querySelectorAll('#topoVista button').forEach(x => x.classList.toggle('active', x.dataset.vista === 'completa'));
      topoZoom = null;
    }
    flujoFirma = '';
    mostrarSeccion('s-topologia');
    if (topoUltimo) renderTopologia(topoUltimo);
  }
});

// ---- G3 · Flujo origen -> servidor sobre el Mapa (validacion externa, R2) ---
// Resalta en la vista «2 · Operacional» el camino que siguio la IP: origen ->
// red -> SPAN -> interfaz -> captura (L3/L4) o Suricata (L7) -> variables ->
// modelo o heuristico -> decision -> feed -> relay -> agente (nftables), con el
// color de su accion. La IP sale de: la elegida, una respuesta vigente, el
// escenario en curso o el ultimo episodio (caducado). No inventa tramos: si no
// hubo LIMIT/BLOCK, el flujo termina en la decision.
var flujoIp;                   // undefined/null = automatico · '' = sin resaltar · ip = elegida
var flujoFirma;
// Reglas que leen eventos L7 de Suricata; el resto sale de los PCAP (L3/L4).
function flujoEsL7(origen) { return ['http_abuse', 'dns_entropy', 'brute_force'].indexOf(origen) >= 0; }

function flujoCandidatas() {
  AA_VIG = AA_VIG || []; AA_EPS = AA_EPS || [];
  const out = [];
  const add = (ip, accion, origen, motivo, fuente) => {
    if (!ip || NUNCA_BLOQUEAR_JS.has(String(ip)) || out.some(o => o.ip === ip)) return;
    out.push({ ip: ip, accion: accion || null, origen: origen || null, motivo: motivo || '', fuente: fuente });
  };
  AA_VIG.forEach(v => add(v.ip, v.accion, v.origen, v.motivo, 'respuesta vigente'));
  if (typeof escActivo === 'function' && escActivo()) {
    const e = AA_EPS.find(x => x.ip === esc.ip && x.inicio >= esc.t0 - 60);
    add(esc.ip, e && e.accion, e && e.origen, e && e.motivo, 'escenario en curso');
  }
  AA_EPS.forEach(e => add(e.ip, e.accion, e.origen, e.motivo, 'último episodio · ' + haceTexto(e.inicio)));
  return out;
}
function flujoActual() {
  if (flujoIp === '') return null;
  const c = flujoCandidatas();
  return (flujoIp && c.find(x => x.ip === flujoIp)) || c[0] || null;
}
function flujoNodos(f) {
  const origen = topoModo === 'operativa' ? 'entrante'
    : f.ip === '10.10.20.30' ? 'atacante' : (/^10\.10\.20\.2[1-6]$/.test(f.ip) ? 'clientes' : null);
  const l7 = flujoEsL7(f.origen);
  const n = [origen, 'red', 'span', 'nic'].concat(l7 ? ['suricata', 'eve', 'parser_eve'] : ['captura', 'pcap', 'motor']);
  n.push('variables', f.origen && f.origen !== 'modelo' ? 'heuristicos' : 'modelo', 'control');
  if (f.accion === 'LIMIT' || f.accion === 'BLOCK') n.push('feed', 'relay', 'agente');
  return n.filter(Boolean);
}
function flujoColor(f) {
  return !f ? 'var(--accent)' : f.accion === 'BLOCK' ? 'var(--danger)' : f.accion === 'LIMIT' ? 'var(--amber)' : 'var(--accent)';
}
function renderFlujoBar() {
  const bar = document.getElementById('flujoBar');
  if (!bar) return;
  const c = flujoCandidatas(), f = flujoActual();
  const firma = JSON.stringify([c, f && f.ip, topoVista]);
  if (firma === flujoFirma) return;     // no repintar el <select> mientras se usa
  flujoFirma = firma;
  bar.hidden = false;
  bar.style.setProperty('--flujo', flujoColor(f));
  if (!c.length) {
    bar.innerHTML = '<span>Sin IP que seguir: el flujo se resalta cuando hay un escenario en curso o una respuesta reciente.</span>';
    return;
  }
  const titulo = id => ((TOPO_VISTAS.completa.nodos.concat([TOPO_OP_ENTRANTE.completa.nodo]).find(n => n.id === id) || {}).titulo || id);
  const opts = c.map(x => `<option value="${varEsc(x.ip)}"${f && f.ip === x.ip ? ' selected' : ''}>${varEsc(x.ip)} · ${varEsc(x.accion || 'sin acción')} · ${varEsc(x.fuente)}</option>`).join('')
    + `<option value=""${f ? '' : ' selected'}>— sin resaltar —</option>`;
  const acc = f && f.accion ? `<span class="badge acc-${f.accion.toLowerCase()}">${varEsc(f.accion)}</span>` : '';
  bar.innerHTML = `<b>Flujo de</b><select id="flujoSel" aria-label="IP cuyo flujo se resalta">${opts}</select>${acc}`
    + (f ? `<span>${f.origen ? varEsc(f.origen) + (f.motivo ? ' · ' : '') : ''}${varEsc(f.motivo || '')}</span>`
      + `<span class="pasos">${flujoNodos(f).map(titulo).join(' → ')}</span>` : '')
    + (f && topoVista !== 'completa' ? '<span class="pasos">(se dibuja en la vista 2 · Operacional)</span>' : '');
}
document.addEventListener('change', (ev) => {
  if (!ev.target || ev.target.id !== 'flujoSel') return;
  flujoIp = ev.target.value;
  flujoFirma = '';
  renderFlujoBar();
  if (topoUltimo) renderTopologia(topoUltimo);
});

// Despliegue: la cadena sensor -> relay -> host protegido. La topologia se
// declara (el panel no tiene credenciales de los otros hosts); la vivacidad del
// sensor sale de los servicios reales de /api/status.
let despliegueDatos = null;
function renderDespliegue(status) {
  const cont = document.getElementById('despliegue');
  if (!cont || !despliegueDatos) return;
  const serv = (status && status.services) || {};
  const ROL = { sensor: 'Sensor', relay: 'Relay', agente: 'Agente' };
  const tarjetas = (despliegueDatos.cadena || []).map(n => {
    const comps = (n.componentes || []).map(c => {
      // Solo el sensor tiene estado real; en relay y agente el servicio es remoto.
      let cls = '', est = '';
      if (n.rol === 'sensor' && c.servicio && (c.servicio in serv)) {
        cls = serv[c.servicio] ? 'ok' : 'bad';
        est = 'comprobado desde el sensor: ' + (serv[c.servicio] ? 'activo' : 'inactivo');
      } else if (n.rol !== 'sensor') {
        est = 'estado no comprobado desde este panel';
      }
      // La periodicidad viene del inventario: se dice que es declarada, no medida.
      const meta = c.cadencia ? c.cadencia + ' · configuración declarada' : (c.detalle || c.fichero || c.unidad || '');
      return `<div class="desp-comp ${cls}"><span class="c-dot"></span><span class="c-n">${varEsc(c.nombre)}`
        + (est ? `<span class="hace">${est}</span>` : '') + `</span>`
        + (meta ? `<span class="c-u" title="${varEsc(c.unidad || '')}">${varEsc(meta)}</span>` : '') + `</div>`;
    }).join('');
    const funciones = n.rol === 'agente'
      ? '<div class="desp-meta"><span class="est si">Verifica firma</span><span class="est si">Aplica nftables con caducidad</span></div>' : '';
    return `<details class="desp-card ${n.rol}" open><summary class="desp-sum"><div class="desp-rol">${ROL[n.rol] || n.rol}</div>`
      + `<div class="desp-h">${varEsc(n.titulo)}</div>`
      + `<div class="desp-host">${varEsc(n.host)} · ${varEsc(n.ip)}</div></summary>`
      + `<div class="desp-meta">VLAN ${varEsc(n.vlan || '—')} · ${varEsc(n.donde || '')}</div>`
      + funciones + comps + (n.nota ? `<div class="desp-nota">${varEsc(n.nota)}</div>` : '') + `</details>`;
  });
  // Flechas entre eslabones (el feed firmado viaja de izquierda a derecha).
  cont.innerHTML = tarjetas.join('<div class="desp-flecha" title="feed firmado">&rarr;</div>');
  const pie = document.getElementById('desplieguePie');
  if (pie) pie.textContent = despliegueDatos.para_anadir_un_host || '';
}
async function cargarDespliegue() {
  if (!document.getElementById('despliegue')) return;
  try {
    despliegueDatos = await (await fetch('/api/despliegue')).json();
    renderDespliegue(topoUltimo);
  } catch (e) { /* se reintenta al proximo refresh */ }
}
cargarDespliegue();
on('histTabla', 'click', (ev) => {
  const tr = ev.target.closest('tr[data-ip]');
  if (!tr) return;
  document.getElementById('ipFilter').value = tr.dataset.ip;
  decVista = 'todas'; pintarDecVista(); renderDecisionsTable();
  mostrarSeccion('s-decisiones');
});

function renderTopIps() {
  const el = document.getElementById('topIps');
  if (!el) return;
  const hora = Date.now() / 1000 - 3600;
  const por = new Map();
  for (const d of lastDecisions) {
    if ((d.logged_at || 0) < hora) continue;
    const acc = accionDeDecision(d);
    if (acc === 'PERMIT') continue;
    const p = por.get(d.entity_ip) || { ip: d.entity_ip, n: 0, block: 0, ult: 0, acc: acc };
    p.n += 1;
    if (acc === 'BLOCK') p.block += 1;
    if ((d.logged_at || 0) > p.ult) { p.ult = d.logged_at; p.acc = acc; }
    por.set(d.entity_ip, p);
  }
  const lista = Array.from(por.values()).sort((a, b) => b.block - a.block || b.n - a.n).slice(0, 6);
  el.innerHTML = lista.length ? lista.map(p =>
    `<tr class="row-${p.acc.toLowerCase()}" data-ip="${varEsc(p.ip)}" style="cursor:pointer"><td class="ip">${varEsc(p.ip)}</td>`
    + `<td class="num r">${p.n}</td><td><span class="badge acc-${p.acc.toLowerCase()}">${p.acc}</span><span class="hace">${haceTexto(p.ult)}</span></td></tr>`).join('')
    : '<tr class="empty-row"><td colspan="3">' + (lastDecisions.length
      ? 'Ninguna entidad con acciones en las decisiones cargadas de la última hora.'
      : 'Todavía no se han recibido decisiones.') + '</td></tr>';
}

on('topIps', 'click', (ev) => {
  const tr = ev.target.closest('tr[data-ip]');
  if (!tr) return;
  document.getElementById('ipFilter').value = tr.dataset.ip;
  decVista = 'todas'; pintarDecVista(); renderDecisionsTable();
  mostrarSeccion('s-decisiones');
});

// Vista de la tabla: por omision solo lo que pidio una accion; «Todas» incluye
// los PERMIT. Un analista empieza por lo que se corto o se degrado.
let decVista = 'accion';
function pintarDecVista() {
  document.querySelectorAll('#decVista button').forEach(b => b.classList.toggle('active', b.dataset.dv === decVista));
}
on('decVista', 'click', (ev) => {
  const b = ev.target.closest('button[data-dv]');
  if (!b) return;
  decVista = b.dataset.dv;
  pintarDecVista();
  renderDecisionsTable();
});

// Las decisiones que se miran: las ultimas 600 en vivo o, si se consulto un
// periodo, las de ese periodo. El refresco de 5 s no pisa una consulta.
let decPeriodo = null;
function decFuente() { return decPeriodo ? decPeriodo.decisiones : lastDecisions; }

function fechaLocalInput(t) {
  const d = new Date(t * 1000), p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes());
}
function fmtFechaHora(t) {
  return new Date(t * 1000).toLocaleString('es-PE', { hour12: false, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}
async function consultarPeriodo() {
  const vd = document.getElementById('decDesde').value, vh = document.getElementById('decHasta').value;
  const desde = vd ? new Date(vd).getTime() / 1000 : null, hasta = vh ? new Date(vh).getTime() / 1000 : null;
  const info = document.getElementById('decPeriodoInfo');
  if (desde == null && hasta == null) { info.textContent = 'Indica al menos «Desde» o «Hasta».'; return; }
  if (desde != null && hasta != null && hasta < desde) { info.textContent = '«Hasta» es anterior a «Desde».'; return; }
  info.className = 'periodo-info';
  info.textContent = 'Consultando el registro…';
  try {
    const q = 'desde=' + (desde != null ? desde : '') + '&hasta=' + (hasta != null ? hasta : '');
    decPeriodo = await (await fetch('/api/decisions?' + q)).json();
  } catch (e) {
    info.textContent = 'No se pudo consultar el periodo: ' + e;
    return;
  }
  document.getElementById('decEnVivo').hidden = false;
  renderDecisionsTable();
}
function pintarPeriodoInfo() {
  const info = document.getElementById('decPeriodoInfo');
  if (!info) return;
  if (!decPeriodo) {
    const ts = lastDecisions.map(d => d.logged_at).filter(Boolean);
    info.className = 'periodo-info';
    info.textContent = ts.length ? 'En vivo: las ' + lastDecisions.length + ' decisiones más recientes, desde '
      + fmtFechaHora(Math.min(...ts)) + '. Para ver antes, elige un periodo.' : 'En vivo: aún no hay decisiones cargadas.';
    return;
  }
  const p = decPeriodo;
  const ini = p.desde != null ? fmtFechaHora(p.desde) : 'el inicio del registro';
  const fin = p.hasta != null ? fmtFechaHora(p.hasta) : 'ahora';
  let txt = 'Periodo consultado: ' + ini + ' – ' + fin + ' · ' + p.total.toLocaleString('es') + ' decisiones';
  if (p.truncado) txt += ' · se muestran las ' + p.limite.toLocaleString('es') + ' más recientes';
  if (p.registro_desde != null && p.desde != null && p.registro_desde > p.desde + 60) {
    txt += ' · el registro leído empieza el ' + fmtFechaHora(p.registro_desde) + ': antes no se puede saber si hubo decisiones';
  }
  info.className = 'periodo-info activo';
  info.textContent = txt;
}
on('decConsultar', 'click', consultarPeriodo);
on('decEnVivo', 'click', () => {
  decPeriodo = null;
  document.getElementById('decEnVivo').hidden = true;
  renderDecisionsTable();
});
on('decLimpiar', 'click', () => {
  decPeriodo = null;
  document.getElementById('decEnVivo').hidden = true;
  document.getElementById('decDesde').value = '';
  document.getElementById('decHasta').value = '';
  document.getElementById('ipFilter').value = '';
  decVista = 'accion'; pintarDecVista();
  decAbiertas.clear();
  renderDecisionsTable();
});
(function () {
  // Periodo por omision en los campos: la ultima hora (no se consulta hasta pulsar).
  const d = document.getElementById('decDesde'), h = document.getElementById('decHasta');
  if (d && h) { const t = Date.now() / 1000; d.value = fechaLocalInput(t - 3600); h.value = fechaLocalInput(t); }
})();
let decGrafVisible = true;
try { decGrafVisible = localStorage.getItem('cf_dec_graf') !== '0'; } catch (e) { /* por omision, visible */ }
function pintarDecGraf() {
  const w = document.getElementById('decChartWrap'), b = document.getElementById('decGrafBtn');
  if (w) w.hidden = !decGrafVisible;
  if (b) { b.textContent = decGrafVisible ? 'Ocultar gráfico' : 'Mostrar gráfico'; b.setAttribute('aria-expanded', String(decGrafVisible)); }
}
pintarDecGraf();
on('decGrafBtn', 'click', () => {
  decGrafVisible = !decGrafVisible;
  try { localStorage.setItem('cf_dec_graf', decGrafVisible ? '1' : '0'); } catch (e) { /* sin persistir */ }
  pintarDecGraf();
  if (decGrafVisible) renderDecChart();
});

function filasFiltradas() {
  const query = document.getElementById('ipFilter').value.trim();
  let rows = decFuente();
  if (decVista === 'accion') rows = rows.filter(d => accionDeDecision(d) !== 'PERMIT');
  if (decVista === 'limit') rows = rows.filter(d => accionDeDecision(d) === 'LIMIT');
  if (decVista === 'block') rows = rows.filter(d => accionDeDecision(d) === 'BLOCK');
  if (query) rows = rows.filter(d => d.entity_ip.includes(query));
  return { rows, query };
}

// Score de cada decision en el tiempo, con el umbral. Las ventanas sin score
// (sin paquetes: el modelo no puntua) van en un carril aparte abajo, no en cero.
// El lienzo usa los pixeles reales del elemento, asi los puntos son redondos.
let decPuntos = [];
// Zoom del gráfico: rango de tiempo visible (null = todo) y modo ampliado.
let decZoom = null, decRango = null, decX0 = 64;
function decAmpliar(si) {
  const w = document.getElementById('decChartWrap'), b = document.getElementById('decMaxBtn');
  if (!w) return;
  let fondo = document.getElementById('decFondo');
  if (si) {
    if (!fondo) {
      fondo = document.createElement('div'); fondo.id = 'decFondo'; fondo.className = 'dec-fondo';
      fondo.addEventListener('click', () => decAmpliar(false)); document.body.appendChild(fondo);
    }
  } else { if (fondo) fondo.remove(); decZoom = null; }
  w.classList.toggle('dec-max', si);
  if (b) b.textContent = si ? '✕ Cerrar' : '⤢ Ampliar';
  renderDecChart();
}
on('decMaxBtn', 'click', () => decAmpliar(!document.getElementById('decChartWrap').classList.contains('dec-max')));
document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && document.getElementById('decFondo')) decAmpliar(false); });
(function () {
  const svg = document.getElementById('decChart');
  if (!svg) return;
  svg.addEventListener('wheel', ev => {
    if (!decRango) return;
    ev.preventDefault();
    const r = svg.getBoundingClientRect(), X0 = decX0, X1 = r.width - 10;
    const [a, b] = decZoom || decRango;
    const fr = Math.min(1, Math.max(0, (ev.clientX - r.left - X0) / (X1 - X0)));
    const tc = a + (b - a) * fr, esc = ev.deltaY < 0 ? 0.75 : 1.33;
    const na = tc - (tc - a) * esc, nb = tc + (b - tc) * esc;
    decZoom = (na <= decRango[0] && nb >= decRango[1]) ? null : [Math.max(decRango[0], na), Math.min(decRango[1], nb)];
    renderDecChart();
  }, { passive: false });
  svg.addEventListener('dblclick', () => { decZoom = null; renderDecChart(); });
})();

function renderDecChart() {
  const svg = document.getElementById('decChart');
  if (!svg || !decGrafVisible) return;
  const query = document.getElementById('ipFilter').value.trim();
  const fuente = decFuente();
  const datos = (query ? fuente.filter(d => d.entity_ip.includes(query)) : fuente)
    .filter(d => d.logged_at);
  const W = Math.max(320, svg.clientWidth || 900), H = Math.max(170, svg.clientHeight || 170);
  const grande = H > 220;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const X0 = grande ? 90 : 64, X1 = W - 10, Y0 = 10, Y1 = H - 46, YS = H - 30;
  decX0 = X0;
  decPuntos = [];
  if (!datos.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">Sin decisiones que graficar.</text>`;
    return;
  }
  const ahora = Date.now() / 1000;
  let t0 = Math.min(...datos.map(d => d.logged_at));
  let t1 = Math.max(decPeriodo ? Math.max(...datos.map(d => d.logged_at)) : ahora, t0 + 60);
  decRango = [t0, t1];
  if (decZoom) { t0 = Math.max(t0, decZoom[0]); t1 = Math.min(t1, decZoom[1]); if (t1 - t0 < 20) t1 = t0 + 20; }
  const zi = document.getElementById('decZoomInfo');
  if (zi) zi.textContent = decZoom ? 'Zoom ' + fmtTime(t0) + ' – ' + fmtTime(t1) + ' · doble clic para restablecer'
    : (grande ? 'Rueda del ratón para acercar · Esc para cerrar' : '');
  const conScore = datos.filter(d => d.score != null);
  const umbral = conScore.length ? conScore[0].threshold : (window._escalaScore ? window._escalaScore.umbral : null);
  let lo = Math.min(...conScore.map(d => d.score)), hi = Math.max(...conScore.map(d => d.score));
  if (umbral != null) { lo = Math.min(lo, umbral); hi = Math.max(hi, umbral); }
  if (!conScore.length) { lo = 0; hi = 1; }
  const margen = (hi - lo) * 0.08 || 0.05;
  lo -= margen; hi += margen;
  const px = t => X0 + (t - t0) / (t1 - t0) * (X1 - X0);
  const py = v => Y1 - (v - lo) / (hi - lo) * (Y1 - Y0);
  const coma = v => v.toFixed(3).split('.').join(',');
  let s = '';
  if (umbral != null && conScore.length) {
    const yu = py(umbral);
    s += `<rect x="${X0}" y="${yu.toFixed(1)}" width="${X1 - X0}" height="${(Y1 - yu).toFixed(1)}" fill="var(--danger)" fill-opacity="0.07"/>`;
    s += `<line x1="${X0}" y1="${yu.toFixed(1)}" x2="${X1}" y2="${yu.toFixed(1)}" stroke="var(--text)" stroke-width="1.2" stroke-dasharray="4 3"/>`;
    s += `<text x="${X1}" y="${(yu - 4).toFixed(1)}" text-anchor="end" style="fill:var(--text)">umbral ${coma(umbral)}</text>`;
    s += `<text x="${X0 - 6}" y="${(yu + 3).toFixed(1)}" text-anchor="end" style="fill:var(--text)">${coma(umbral)}</text>`;
  }
  s += `<line x1="${X0}" y1="${Y0}" x2="${X0}" y2="${Y1}" stroke="var(--border)"/><line x1="${X0}" y1="${Y1}" x2="${X1}" y2="${Y1}" stroke="var(--border)"/>`;
  if (conScore.length) {
    // Las marcas de los extremos se omiten si quedarian encima de la del umbral.
    const yu = umbral != null ? py(umbral) : -99;
    if (Math.abs(yu - (Y0 + 5)) > 13) s += `<text x="${X0 - 6}" y="${Y0 + 8}" text-anchor="end">${coma(hi)}</text>`;
    if (Math.abs(yu - Y1) > 13) s += `<text x="${X0 - 6}" y="${Y1}" text-anchor="end">${coma(lo)}</text>`;
  }
  s += `<text x="${X0 - 6}" y="${YS + 3}" text-anchor="end">sin score</text>`;
  s += `<line x1="${X0}" y1="${YS}" x2="${X1}" y2="${YS}" stroke="var(--border)" stroke-dasharray="2 4"/>`;
  for (let i = 0; i <= 4; i++) {
    const t = t0 + (t1 - t0) * i / 4, x = px(t);
    s += `<line x1="${x.toFixed(1)}" y1="${Y1}" x2="${x.toFixed(1)}" y2="${Y1 + 3}" stroke="var(--border)"/>`;
    s += `<text x="${x.toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 ? 'start' : (i === 4 ? 'end' : 'middle')}">${i === 4 && !decPeriodo && !decZoom ? 'ahora' : fmtTime(t)}</text>`;
  }
  const k = grande ? 1.6 : 1;
  const estilo = { PERMIT: ['var(--accent)', 2 * k, 0.4], LIMIT: ['var(--amber)', 3.8 * k, 0.95], BLOCK: ['var(--sev-block)', 4.4 * k, 1] };
  // Los PERMIT primero: las acciones se dibujan encima y no quedan tapadas.
  ['PERMIT', 'LIMIT', 'BLOCK'].forEach(tipo => {
    datos.forEach(d => {
      if (accionDeDecision(d) !== tipo) return;
      if (d.logged_at < t0 || d.logged_at > t1) return;
      const x = px(d.logged_at), y = d.score != null ? py(d.score) : YS;
      const e = estilo[tipo];
      s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${e[1]}" fill="${e[0]}" fill-opacity="${e[2]}"/>`;
      decPuntos.push({ x: x, y: y, d: d, accion: tipo });
    });
  });
  s += '<circle id="decFoco" r="7" fill="none" stroke="var(--text)" stroke-width="1.4" visibility="hidden"/>';
  svg.innerHTML = s;
}

function decPuntoCercano(ev) {
  const svg = document.getElementById('decChart');
  const r = svg.getBoundingClientRect();
  const x = ev.clientX - r.left, y = ev.clientY - r.top;
  let mejor = null, dist = 18 * 18;
  for (const p of decPuntos) {
    // Una accion gana a un PERMIT que este a la misma distancia.
    const dd = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y) - (p.accion === 'PERMIT' ? 0 : 40);
    if (dd < dist) { dist = dd; mejor = p; }
  }
  return mejor;
}
on('decChart', 'mousemove', (ev) => {
  const tip = document.getElementById('decTip'), foco = document.getElementById('decFoco');
  const p = decPuntoCercano(ev);
  if (!p || !foco) { tip.style.visibility = 'hidden'; if (foco) foco.setAttribute('visibility', 'hidden'); return; }
  foco.setAttribute('cx', p.x.toFixed(1)); foco.setAttribute('cy', p.y.toFixed(1)); foco.setAttribute('visibility', 'visible');
  const m = motivoDeDecision(p.d);
  tip.innerHTML = `<div class="t-when">${fmtTime(p.d.logged_at)} · ${varEsc(p.d.entity_ip)}</div>`
    + `<div><b>${p.accion}</b> ${p.d.score != null ? '· score ' + p.d.score.toFixed(3) : '· sin score'}</div>`
    + (m.texto ? `<div>${varEsc(m.texto)}</div>` : '');
  const ancho = tip.offsetParent.getBoundingClientRect().width, media = tip.offsetWidth / 2;
  tip.style.left = Math.max(media + 2, Math.min(ancho - media - 2, p.x + 16)).toFixed(0) + 'px';
  tip.style.visibility = 'visible';
});
on('decChart', 'mouseleave', () => {
  document.getElementById('decTip').style.visibility = 'hidden';
  const foco = document.getElementById('decFoco');
  if (foco) foco.setAttribute('visibility', 'hidden');
});
on('decChart', 'click', (ev) => {
  const p = decPuntoCercano(ev);
  if (!p) return;
  document.getElementById('ipFilter').value = p.d.entity_ip;
  decVista = 'todas'; pintarDecVista(); renderDecisionsTable();
});

// Filas abiertas: el detalle sobrevive al refresco de 5 s.
const decAbiertas = new Set();
// Quien pidio la accion: el modelo, una regla, los dos o ninguno.
function fuenteDecision(d) {
  const t = alertaTipos(d);
  if (t.modelo && t.regla) return 'Modelo + regla';
  if (t.regla) return 'Regla: ' + t.regla;
  if (t.modelo) return 'Modelo';
  return d.score == null ? 'Sin puntuar' : 'Modelo (normal)';
}
// Explicacion en lenguaje natural de POR QUE salio esta accion.
function porQueDecision(d, accion) {
  const t = alertaTipos(d), h = d.heuristico;
  const reglaTxt = t.regla ? 'la regla «' + t.regla + '»' + (h && h.motivo ? ' (' + h.motivo + ')' : '') : '';
  const modeloTxt = d.score == null ? 'El modelo no puntuó esta ventana (sin paquetes).'
    : (t.modelo ? 'El score del modelo fue inferior al umbral vigente.' : 'El score del modelo quedó por encima del umbral: normal para el modelo.');
  if (accion === 'PERMIT') {
    return 'No se pidió acción: ninguna regla se activó y ' + (d.score == null ? 'el modelo no puntuó la ventana.' : 'el modelo no vio anomalía.')
      + ' PERMIT no prueba que no haya ataque.';
  }
  if (t.regla && t.modelo) return 'Se decidió ' + accion + ' porque se activó ' + reglaTxt + ' y, además, el score del modelo fue inferior al umbral vigente. Manda la acción más severa.';
  if (t.regla) return 'Se decidió ' + accion + ' porque se activó ' + reglaTxt + '. ' + modeloTxt;
  return 'Se decidió ' + accion + ' porque el score del modelo fue inferior al umbral vigente. No se activaron reglas heurísticas en esta ventana. Una anomalía del modelo solo llega a LIMIT.';
}
// Los siete pasos de la cadena v2 de una decision, con su fuente. Lo que no consta en
// una fuente se muestra «desconocido» o «sin evidencia», nunca como «no».
const TXT_MEDIDA_V2 = {
  nueva: 'medida publicada (nueva)', renovada: 'medida publicada (renovada)',
  escalada: 'medida publicada (escalada)', mantenida: 'medida vigente mantenida',
  rechazada: 'regla rechazada por el publicador · sin efecto',
  sin_punto_de_aplicacion: 'sin punto de aplicación · no se restringe',
  no_publicada: 'sin medida publicada', desconocido: 'desconocido · la traza v2 no cubre esta decisión',
  pendiente: 'pendiente · posterior a la última publicación del publicador v2',
  fuente_desactualizada: 'desconocido · la traza v2 está desactualizada',
  fuente_ausente: 'desconocido · traza v2 ausente o ilegible',
};
// Señal α publicada (senales-if.jsonl). «sin señal» solo con cobertura demostrada.
const TXT_SENAL_V2 = {
  sin_senal: 'sin señal α (procesada por el publicador, ningún α superado)',
  sin_puntuar: 'sin puntuar (el motor no puntuó la ventana)',
  pendiente: 'pendiente · posterior a la última publicación del publicador v2',
  fuente_desactualizada: 'desconocido · la traza v2 está desactualizada',
  fuente_ausente: 'desconocido · senales-if.jsonl ausente o ilegible',
  desconocido: 'desconocido · cobertura no demostrada',
};
const TXT_APLICACION_V2 = {
  no_ejecutada: 'no ejecutada (modo sombra)', no_aplica: 'no aplica (ausencia de medida demostrada)',
  desconocido: 'desconocido (sin evidencia)',
};
function cadenaV2HTML(d) {
  const c = d.cadena_v2;
  if (!c) return '';
  const fila = (k, v, src) => `<div><dt>${k}</dt><dd>${v}<small class="hace"> · ${src}</small></dd></div>`;
  const s = c.if || {};
  const ifTxt = s.estado === 'senal'
    ? 'señal IF · score ' + (s.score != null ? Number(s.score).toFixed(4) : '—') + ' · α superados: ' + varEsc((s.alfa_superados || []).join(', ') || 'ninguno')
    : varEsc(TXT_SENAL_V2[s.estado] || TXT_SENAL_V2.desconocido);
  const im = c.if_motor || {};
  const motorTxt = c.if_motor
    ? 'decision_if ' + varEsc(String(im.decision_if ?? 'sin puntuar')) + ' · score ' + (im.score != null ? Number(im.score).toFixed(4) : '—')
      + ' · umbral desplegado ' + (im.umbral != null ? Number(im.umbral).toFixed(4) : '—')
    : 'desconocido';
  const reglas = (c.reglas || []).map(r => varEsc(r.regla) + (r.accion ? ' → ' + varEsc(r.accion) : '')).join('; ') || 'ninguna';
  const m = c.medida || {};
  let medTxt = varEsc(TXT_MEDIDA_V2[m.estado] || String(m.estado || 'desconocido'));
  if (m.accion) medTxt = `<span class="badge acc-${String(m.accion).toLowerCase()}">${varEsc(m.accion)}</span> ` + medTxt
    + (c.propuesta ? ' · <b>propuesta (sombra)</b>' : '') + (m.secuencia != null ? ' · feed n.º ' + m.secuencia : '');
  const apl = TXT_APLICACION_V2[c.aplicacion] || TXT_APLICACION_V2.desconocido;
  return '<div><h4>Cadena v2 (fuentes reales)</h4><dl>'
    + fila('1a · IF del motor', motorTxt, 'registro del motor (decision_if)')
    + fila('1b · Señal α publicada', ifTxt, 'senales-if.jsonl')
    + fila('2 · Regla heurística', reglas, 'registro del motor')
    + fila('3 · Decisión del motor', varEsc(String(c.decision || '—')), 'registro del motor')
    + fila('4 · Medida', medTxt, 'traza del publicador v2')
    + fila('5 · Agente (recepción/evaluación)', 'desconocido', 'sin canal desde el sensor')
    + fila('6 · Aplicación confirmada', apl, 'modo declarado')
    + fila('7 · Efecto observado', 'sin evidencia', 'el sensor no lo mide')
    + '</dl></div>';
}
function decDetalleHTML(d, accion) {
  const h = d.heuristico;
  const margen = d.score != null && d.threshold != null ? d.score - d.threshold : null;
  const caduca = accion === 'LIMIT' ? '300 s tras la última decisión' : (accion === 'BLOCK' ? '300, 1800 o 3600 s según reincidencia' : 'no aplica');
  const fila = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
  return '<div class="det4">'
    + '<div><h4>Resultado</h4><dl>'
    + fila('Decisión', `<span class="badge acc-${accion.toLowerCase()}">${accion}</span>`)
    + fila('Entidad', varEsc(String(d.entity_ip || '—')))
    + fila('Hora', fmtTime(d.logged_at) + ' · ventana ' + varEsc(String(d.window_end_utc || '—')) + ' UTC')
    + fila('Caducidad configurada', caduca)
    + '</dl></div>'
    + '<div><h4>Por qué</h4><p>' + varEsc(porQueDecision(d, accion)) + '</p>'
    + (accion !== 'PERMIT' ? '<p style="margin-top:0.5rem"><button type="button" class="btn-sec" data-ir-resp="1">Ver su respuesta &rarr;</button></p>' : '')
    + '</div>'
    + '<div><h4>Evidencia</h4><dl>'
    + fila('Score y umbral', d.score != null ? d.score.toFixed(4) + ' frente a ' + (d.threshold != null ? d.threshold.toFixed(4) : '—') : 'sin puntuar: ventana sin paquetes')
    + fila('Margen al umbral', margen == null ? '—' : (margen >= 0 ? '+' : '') + margen.toFixed(4) + (margen < 0 ? ' · anómalo' : ' · normal'))
    + fila('Regla', h && h.heuristico ? varEsc(h.heuristico) + ' → ' + varEsc(h.accion || '') : 'ninguna')
    + fila('Qué midió la regla', h && h.motivo ? varEsc(h.motivo) : '—')
    + fila('Paquetes en 10 s', d.packet_count_10s ?? '—')
    + '</dl></div>'
    + '<div><h4>Contexto técnico</h4><dl>'
    + fila('Detector', varEsc(String(d.detector_name || '—')))
    + fila('Decisión del modelo', varEsc(String(d.decision || '—')))
    + fila('Historia cubierta', d.history_coverage_s != null ? d.history_coverage_s + ' s' : '—')
    + fila('Registrada (logged_at)', d.logged_at ? new Date(d.logged_at * 1000).toLocaleString('es-PE', { hour12: false }) : '—')
    + '</dl></div>'
    + cadenaV2HTML(d)
    + '</div>';
}
on('decisions', 'click', (ev) => {
  if (ev.target.closest('[data-ir-resp]')) { mostrarSeccion('s-bloqueos'); return; }
  const tr = ev.target.closest('tr.dec-fila');
  if (!tr) return;
  const k = tr.dataset.key;
  if (decAbiertas.has(k)) decAbiertas.delete(k); else decAbiertas.add(k);
  renderDecisionsTable();
});

function renderDecisionsTable() {
  const { rows, query } = filasFiltradas();
  const fuente = decFuente();
  const cuenta = { PERMIT: 0, LIMIT: 0, BLOCK: 0 };
  fuente.forEach(d => { cuenta[accionDeDecision(d)] += 1; });
  const quees = { accion: 'con acción', limit: 'con LIMIT', block: 'con BLOCK' }[decVista];
  const base = decPeriodo ? 'decisiones del periodo' : 'decisiones recientes';
  document.getElementById('filterHint').textContent =
    (quees ? rows.length + ' ' + quees + ' de ' + fuente.length + ' ' + base : fuente.length + ' ' + base)
    + (query ? ' · filtradas por «' + query + '»' : '');
  const res = document.getElementById('decResumen');
  if (res) res.innerHTML = `<span>Total <b>${fuente.length.toLocaleString('es')}</b></span>`
    + `<span>PERMIT <b>${cuenta.PERMIT.toLocaleString('es')}</b></span>`
    + `<span>LIMIT <b>${cuenta.LIMIT.toLocaleString('es')}</b></span>`
    + `<span>BLOCK <b>${cuenta.BLOCK.toLocaleString('es')}</b></span>`;
  pintarPeriodoInfo();
  renderDecChart();
  document.getElementById('decisions').innerHTML = rows.length ? rows.slice(0, 1500).map(d => {
    const accion = accionDeDecision(d);
    const accBadge = `<span class="badge acc-${accion.toLowerCase()}">${accion}</span>`;
    const isAlert = d.decision === 'ALERT';
    const modelo = d.score != null
      ? `<span class="modelo-celda"><span class="${isAlert ? 'm-alert' : 'm-permit'}">${isAlert ? 'Anómalo' : 'Normal'}</span>`
        + `<span>${d.score.toFixed(3)}</span>${miniBarraScore(d.score)}</span>`
      : '<span class="modelo-celda"><span class="m-permit">sin puntuar</span></span>';
    const m = motivoDeDecision(d);
    const motivoTxt = m.regla && m.regla !== 'modelo'
      ? varEsc(m.texto)
      : (m.regla === 'modelo' ? varEsc(m.texto) : varEsc(DETECTOR_LABEL[d.detector_name] || d.detector_name || ''));
    const fte = fuenteDecision(d);
    const fteHTML = fte.startsWith('Regla: ') ? `<span class="badge heur" title="regla determinista, sin firma">${varEsc(fte.slice(7))}</span>` : varEsc(fte);
    const key = d.entity_ip + '|' + d.window_end_utc;
    const abierta = decAbiertas.has(key);
    const cls = 'dec-fila ' + (accion !== 'PERMIT' ? 'row-' + accion.toLowerCase() : '') + (nuevasClaves.has(key) ? ' row-nueva' : '') + (abierta ? ' abierta' : '');
    return `<tr class="${cls}" data-key="${varEsc(key)}"><td class="num">${fmtTime(d.logged_at)}<span class="hace">${haceTexto(d.logged_at)}</span></td>`
      + `<td class="ip">${varEsc(d.entity_ip)}</td><td>${accBadge}</td><td>${fteHTML}</td><td class="why"><span class="clamp">${motivoTxt}</span></td>`
      + `<td>${modelo}</td><td class="num r">${d.packet_count_10s ?? '—'}</td>`
      + `<td><button type="button" class="btn-sec" aria-expanded="${abierta}">${abierta ? 'Ocultar' : 'Ver detalle'}</button></td></tr>`
      + (abierta ? `<tr class="dec-det"><td colspan="8">${decDetalleHTML(d, accion)}</td></tr>` : '');
  }).join('') : `<tr class="empty-row"><td colspan="8">${query ? 'Ninguna decisión coincide con el filtro en ' + (decPeriodo ? 'el periodo consultado.' : 'las decisiones cargadas.')
      : (decVista === 'accion' ? 'Ninguna decisión con acción en ' + (decPeriodo ? 'el periodo consultado.' : 'las decisiones cargadas.') : 'Sin decisiones en ' + (decPeriodo ? 'el periodo consultado.' : 'las decisiones cargadas.'))}</td></tr>`;
}

on('ipFilter', 'input', renderDecisionsTable);

on('exportCsv', 'click', () => {
  const { rows } = filasFiltradas();
  const header = ['hora_utc', 'ip', 'decision', 'accion', 'motivo', 'score', 'paquetes_10s'];
  const csvRows = rows.map(d => [
    d.window_end_utc,
    d.entity_ip,
    d.decision,
    accionDeDecision(d),
    (motivoDeDecision(d).regla ? motivoDeDecision(d).regla + ': ' + motivoDeDecision(d).texto
      : (DETECTOR_LABEL[d.detector_name] || d.detector_name)),
    d.score != null ? d.score : '',
    d.packet_count_10s,
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));
  const csv = [header.join(','), ...csvRows].join('\\r\\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  // El nombre dice el alcance: en vivo (ultimas cargadas) o el periodo pedido, y la vista.
  const alcance = decPeriodo ? 'periodo-' + fechaLocalInput(decPeriodo.desde || 0).replace(/[:T]/g, '') : 'envivo';
  a.download = `cyberflow-decisiones-${alcance}-${decVista}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
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
  // Cortafuegos: muro de ladrillos. Conmutador: caja con flujo bidireccional.
  firewall: '<rect x="2" y="3.3" width="14" height="11.4" rx="1"/><path d="M2 7.1h14M2 10.9h14M6.6 3.3v3.8M11.4 3.3v3.8M4.3 7.1v3.8M9 7.1v3.8M13.7 7.1v3.8M6.6 10.9v3.8M11.4 10.9v3.8"/>',
  switch:   '<rect x="1.6" y="5.4" width="14.8" height="7.2" rx="1.3"/><path d="M4 9h10"/><path d="M6.4 6.9 4 9l2.4 2.1M11.6 6.9 14 9l-2.4 2.1"/>',
  carpeta:  '<path d="M2 4.6h4.4l1.5 2H16v7.8H2Z"/><path d="M2 8.6h14"/>',
  atacante: '<circle cx="9" cy="9" r="6.3"/><path d="M9 1.3V4.2M9 13.8v2.9M1.3 9H4.2M13.8 9h2.9"/><circle cx="9" cy="9" r="1.5" fill="currentColor" stroke="none"/>',
  usuarios: '<circle cx="6.5" cy="6.5" r="2.6"/><path d="M1.8 15c.6-3 2.4-4.4 4.7-4.4S10.6 12 11.2 15"/><circle cx="12.6" cy="6" r="2.1"/><path d="M12 10.3c2.2 0 3.6 1.4 4.2 4"/>',
  kali:     '<path d="M2.2 13.6c2.6-.4 4.4-1.6 5.4-3.6.8-1.6.6-3.6 2.2-5 1.4-1.2 3.6-1.4 5.8-.6-1.6.2-2.6.8-3 1.8 1.4.2 2.4 1 2.8 2.2-1.2-.6-2.4-.6-3.4 0-1.4 2.6-3.6 4.6-7 5.6"/><path d="M12.4 6.2h.01"/>',
  radar:    '<circle cx="9" cy="9" r="7"/><circle cx="9" cy="9" r="3.6"/><path d="M9 9 14 4"/><circle cx="12.2" cy="11.6" r="0.9" fill="currentColor" stroke="none"/>',
  terminal: '<rect x="1.8" y="3" width="14.4" height="12" rx="1.6"/><path d="M4.8 7.2 7.4 9.4 4.8 11.6M9 12h4"/>',
  bicho:    '<ellipse cx="9" cy="10.4" rx="3.6" ry="4.6"/><path d="M9 5.8V15M5.4 8.6 2.4 7M12.6 8.6l3-1.6M5.4 11.6H2.2M12.6 11.6h3.2M6.6 6.4 5.2 3.4M11.4 6.4l1.4-3"/>',
  flechas:  '<path d="M2.4 6h11.4M11.2 3.4 13.8 6l-2.6 2.6M15.6 12H4.2M6.8 9.4 4.2 12l2.6 2.6"/>',
  python:   '<path d="M9 1.8c-3 0-3.4 1.3-3.4 2.4v1.6H9v.6H4.2C2.8 6.4 1.8 7.4 1.8 9.4s1 3.2 2.4 3.2h1.4v-2c0-1.4 1.2-2.4 2.6-2.4h3.6c1.2 0 2.2-1 2.2-2.2V4.2c0-1.2-1-2.4-5-2.4z"/><path d="M9 16.2c3 0 3.4-1.3 3.4-2.4v-1.6H9v-.6h4.8c1.4 0 2.4-1 2.4-3s-1-3.2-2.4-3.2"/><circle cx="7" cy="3.8" r="0.6" fill="currentColor" stroke="none"/><circle cx="11" cy="14.2" r="0.6" fill="currentColor" stroke="none"/>',
  engranaje:'<circle cx="9" cy="9" r="2.6"/><path d="M9 1.8v2.4M9 13.8v2.4M1.8 9h2.4M13.8 9h2.4M3.9 3.9l1.7 1.7M12.4 12.4l1.7 1.7M3.9 14.1l1.7-1.7M12.4 5.6l1.7-1.7"/>',
  llave:    '<circle cx="5.6" cy="9" r="3.4"/><path d="M9 9h7.2M13.6 9v2.8M15.8 9v2"/>',
  router:   '<circle cx="9" cy="9" r="7.2"/><path d="M9 4.4v3.2M9 10.4v3.2M4.4 9h3.2M10.4 9h3.2"/><path d="M7.9 5.5 9 4.4l1.1 1.1M7.9 12.5 9 13.6l1.1-1.1M5.5 7.9 4.4 9l1.1 1.1M12.5 7.9 13.6 9l-1.1 1.1"/>',
  entrante: '<path d="M1.8 9h8.6"/><path d="M7.2 5.6 10.6 9l-3.4 3.4"/><path d="M11.6 2.6h4.6v12.8h-4.6"/>',
  // Perfiles de trafico legitimo (clientes .21-.26).
  ofimatica:  '<rect x="3.6" y="2" width="10.8" height="14" rx="1.1"/><path d="M6 5.4h6M6 8h6M6 10.6h4"/>',
  navegacion: '<rect x="2" y="3.4" width="14" height="11.2" rx="1.3"/><path d="M2 6.6h14"/><circle cx="4.2" cy="5" r="0.5" fill="currentColor" stroke="none"/><circle cx="6" cy="5" r="0.5" fill="currentColor" stroke="none"/><path d="M9 8.4a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 0 0 0-4.8M6.6 10.8h4.8M9 8.4v4.8"/>',
  descargas:  '<path d="M9 2.4v8.2"/><path d="M5.4 7 9 10.6 12.6 7"/><path d="M2.8 14.2h12.4"/>',
  aplicacion: '<rect x="2.4" y="2.4" width="5.2" height="5.2" rx="1"/><rect x="10.4" y="2.4" width="5.2" height="5.2" rx="1"/><rect x="2.4" y="10.4" width="5.2" height="5.2" rx="1"/><rect x="10.4" y="10.4" width="5.2" height="5.2" rx="1"/>',
  ligero:     '<path d="M2.6 13.4C6 5 11 3.6 15.4 3.6 15 10 10.2 13.8 4.2 13.4"/><path d="M2.6 15.4 7 11"/>',
  erratico:   '<path d="M1.8 10.5 4.3 4.6l2 8L8.8 3l1.9 7.2 1.8-3.8 1.8 3.4 1.9-1.4"/>',
  // Hosts: sensor (antena que escucha), servidor (torre), bastion (fortaleza).
  host_sensor:   '<circle cx="9" cy="9.5" r="1.6"/><path d="M9 11v4"/><path d="M5.8 6.3a4.4 4.4 0 0 0 0 6.4M12.2 6.3a4.4 4.4 0 0 1 0 6.4M3.6 4.1a7.4 7.4 0 0 0 0 10.8M14.4 4.1a7.4 7.4 0 0 1 0 10.8"/>',
  host_servidor: '<rect x="3.4" y="2.2" width="11.2" height="13.6" rx="1.3"/><path d="M3.4 6.6h11.2M3.4 11h11.2"/><circle cx="6" cy="4.4" r="0.55" fill="currentColor" stroke="none"/><circle cx="6" cy="8.8" r="0.55" fill="currentColor" stroke="none"/><circle cx="6" cy="13.2" r="0.55" fill="currentColor" stroke="none"/>',
  host_bastion:  '<path d="M3 15.4V6.6l6-3.8 6 3.8v8.8"/><path d="M2.2 15.4h13.6"/><path d="M7.3 15.4v-3.4h3.4v3.4"/>',
};
const HOST_ICON = { sensor: 'host_sensor', servidor: 'host_servidor', bastion: 'host_bastion' };
// 17-nov: cada tipo de componente con su color (icono blanco sobre círculo de color).
const ICO_COLOR = {
  red: '#0284c7', entrante: '#0d9488', atacante: '#dc2626', usuarios: '#16a34a', host_servidor: '#7c3aed',
  disco: '#7c3aed', router: '#4f46e5', firewall: '#4f46e5', switch: '#2563eb', espejo: '#2563eb', nic: '#475569',
  captura: '#ea580c', lupa: '#f59e0b', fichero: '#64748b', cpu: '#9333ea', tabla: '#0891b2', reglas: '#d97706',
  modelo: '#7c3aed', decision: '#1e3a8a', escudo: '#059669', ojo: '#0369a1', tijera: '#6b7280', ciclo: '#0d9488',
  carpeta: '#ca8a04',
};
function icoCirculo(ico, cx, cy, r, color) {
  const s = Math.round(r * 1.25);
  return `<circle class="ico-bg" cx="${cx}" cy="${cy}" r="${r}" fill="${color || ICO_COLOR[ico] || '#475569'}"/>`
    + `<g class="ico ico-blanco" transform="translate(${cx - s / 2}, ${cy - s / 2})"><svg width="${s}" height="${s}" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[ico] || ''}</svg></g>`;
}
// Herramientas de cada componente (columna de la derecha del detalle). Iconos propios con el color
// de cada herramienta: no son los logotipos oficiales.
const TOPO_HERR = {
  atacante: [
    { n: 'Kali Linux', d: 'VM atacante · 10.10.20.30', ico: 'kali', c: '#367bf0' },
    { n: 'ping (inundación)', d: 'flood ICMP → BLOCK', ico: 'flechas', c: '#0891b2', capa: 'L3 · Red', demo: true },
    { n: 'nmap', d: 'escaneo de puertos → BLOCK', ico: 'radar', c: '#1d4ed8', capa: 'L4 · Transporte', demo: true },
    { n: 'curl · fuerza bruta', d: 'logins fallidos 401 → BLOCK', ico: 'terminal', c: '#0b4f6c', capa: 'L7 · Aplicación', demo: true },
    { n: 'curl · flood HTTP', d: 'muchas peticiones/s → LIMIT', ico: 'terminal', c: '#0e7490', capa: 'L7 · Aplicación', demo: true },
    { n: 'dig · DGA', d: 'DNS de alta entropía → LIMIT', ico: 'red', c: '#b45309', capa: 'L7 · Aplicación', demo: true },
    { n: 'nikto', d: 'vulnerabilidades web', ico: 'bicho', c: '#15803d', capa: 'L7 · Aplicación', demo: false },
    { n: 'arpspoof', d: 'ARP spoofing · trabajo futuro', ico: 'nic', c: '#6b7280', capa: 'L2 · Enlace', demo: false },
  ],
  clientes: [
    { n: 'Python', d: 'clientes_lab.py · servidor_lab.py', ico: 'python', c: '#3776ab' },
    { n: 'systemd', d: 'cyberflow-lab.target · 6 servicios', ico: 'engranaje', c: '#30d475' },
  ],
  servidor: [
    { n: 'Python HTTP/HTTPS', d: 'servidor_lab.py · 80 y 443', ico: 'python', c: '#3776ab' },
    { n: 'nftables', d: 'sets con caducidad: LIMIT y BLOCK', ico: 'escudo', c: '#059669' },
    { n: 'ed25519', d: 'el agente verifica la firma del feed', ico: 'llave', c: '#7c3aed' },
  ],
  gateway: [
    { n: 'pfSense', d: 'router A/B en alta disponibilidad', ico: 'router', c: '#212d6b' },
    { n: 'CARP · pfsync', d: 'VIP compartida entre A y B', ico: 'ciclo', c: '#4f46e5' },
  ],
  suricata: [ { n: 'Suricata', d: 'eventos L7 en eve.json (sin reglas)', ico: 'lupa', c: '#ef6c00' } ],
  captura: [ { n: 'tcpdump', d: 'anillo de PCAP en el sensor', ico: 'captura', c: '#ea580c' } ],
  modelo: [ { n: 'scikit-learn', d: 'Isolation Forest · umbral calibrado', ico: 'modelo', c: '#f7931e' } ],
};
function herramientasHTML(id) {
  const l = TOPO_HERR[id];
  if (!l) return '';
  const tarjeta = h =>
    `<div class="herr"><span class="herr-ico" style="background:${h.c}"><svg width="30" height="30" viewBox="0 0 18 18" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[h.ico] || ''}</svg></span>`
    + `<span class="herr-t"><b>${h.n}${h.demo ? ' <span class="herr-demo">demo</span>' : ''}</b><small>${h.d}</small></span></div>`;
  // Si las herramientas traen capa (p. ej. el atacante), se agrupan por capa del modelo OSI
  // (L2/L3/L4/L7) y se marca con «demo» la que se lanza en la sustentación.
  if (l.some(h => h.capa)) {
    let html = '<aside class="herr-col"><div class="cod-sub">Ataques por capa</div>';
    html += l.filter(h => !h.capa).map(tarjeta).join('');      // la plataforma (Kali), sin capa
    const capas = [];
    l.forEach(h => { if (h.capa && !capas.includes(h.capa)) capas.push(h.capa); });
    for (const capa of capas) {
      html += `<div class="herr-capa">${capa}</div>` + l.filter(h => h.capa === capa).map(tarjeta).join('');
    }
    return html + '<div class="herr-leyenda"><span class="herr-demo">demo</span> = la lanzas en la sustentación</div></aside>';
  }
  return '<aside class="herr-col"><div class="cod-sub">Herramientas</div>' + l.map(tarjeta).join('') + '</aside>';
}

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
    // Dos sobres que salen A LA VEZ desde la Interfaz en escucha, uno por cada rama de
    // adquisición (tcpdump y Suricata), y se JUNTAN en el Modelo recalibrado.
    packets: [
      { d: 'M374,275 L628,139 L628,215 L894,139 L894,249 L1148,187', dur: '6s', begin: '0s' },   // rama tcpdump (L2·L3·L4)
      { d: 'M374,275 L628,303 L628,379 L894,359 L894,249 L1148,187', dur: '6s', begin: '0s' },   // rama Suricata (L7)
    ],
    grupos: [
      { x: 12,   y: 32, w: 200, h: 456, txt: 'Hosts · VLAN 20/30' },
      { x: 272,  y: 32, w: 460, h: 456, txt: 'Adquisición',          n: 1 },
      { x: 792,  y: 32, w: 470, h: 456, txt: 'Análisis',             n: 2 },
      { x: 1322, y: 32, w: 196, h: 456, txt: 'Decisión y respuesta', n: 3 },
      { x: 1578, y: 32, w: 196, h: 456, txt: 'Observabilidad',       n: 4 },
    ],
    nodos: [
      { id: 'atacante', x: 24, y: 70,  w: 176, h: 48, icono: 'atacante',   titulo: 'Atacante (Kali)',   host: true, ip: '10.10.20.30',     desc: 'lanza los ataques' },
      { id: 'clientes', x: 24, y: 140, w: 176, h: 48, icono: 'usuarios',    titulo: 'Clientes',          host: true, ip: '10.10.20.21-.26', desc: '6 perfiles legítimos' },
      { id: 'servidor', x: 24, y: 210, w: 176, h: 48, icono: 'host_servidor',  titulo: 'Servidor',          host: true, ip: '10.10.30.10',     desc: 'objetivo HTTP/HTTPS' },
      { id: 'gateway',  x: 24, y: 280, w: 176, h: 48, icono: 'router', titulo: 'Router', host: true, ip: '10.10.20.1',      desc: 'enruta entre VLAN' },
      { id: 'red',       x: 286, y: 70,  w: 176, h: 58, icono: 'red',    titulo: 'Red de la entidad',  tag: 'VLAN 10-100' },
      { id: 'span',      x: 286, y: 158, w: 176, h: 58, icono: 'switch', titulo: 'Espejo SPAN',        tag: 'SWITCH' },
      { id: 'nic',       x: 286, y: 246, w: 176, h: 58, icono: 'nic',    titulo: 'Interfaz en escucha', tag: 'ens37 · SIN IP' },
      { id: 'captura',   x: 540, y: 110, w: 176, h: 58, icono: 'captura', titulo: 'tcpdump',           tag: 'SERVICIO' },
      { id: 'pcap',      x: 540, y: 192, w: 176, h: 46, icono: 'fichero', titulo: 'anillo live-*.pcap', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'suricata',  x: 540, y: 274, w: 176, h: 58, icono: 'lupa',   titulo: 'Suricata',           tag: 'SERVICIO' },
      { id: 'eve',       x: 540, y: 356, w: 176, h: 46, icono: 'fichero', titulo: 'eve.json',          tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'motor',     x: 806, y: 110, w: 176, h: 58, icono: 'cpu',    titulo: 'Parser de paquetes', tag: 'TRAMA → FLUJO · L2·L3·L4' },
      { id: 'variables', x: 806, y: 220, w: 176, h: 58, icono: 'tabla',  titulo: 'Variables / 10 s',   tag: 'POR IP Y VENTANA' },
      { id: 'parser_eve', x: 806, y: 330, w: 176, h: 58, icono: 'reglas', titulo: 'Parser de eventos', tag: 'JSON → L7 · HTTP·DNS·TLS', val: 'http · dns · tls' },
      { id: 'descartes', x: 806, y: 420, w: 176, h: 48, icono: 'tijera', titulo: 'No se puntúa',       tag: 'CONTROL · DUPLICADOS', clase: 'sumidero' },
      { id: 'reentrenamiento', x: 1060, y: 70, w: 176, h: 58, icono: 'ciclo', titulo: 'Aprendizaje', tag: 'APROBACIÓN HUMANA · CADA NOCHE' },
      { id: 'modelo',    x: 1060, y: 158, w: 176, h: 58, icono: 'modelo', titulo: 'Modelo recalibrado', tag: 'IF · CALIBRADO' },
      { id: 'heuristicos', x: 1060, y: 276, w: 176, h: 58, icono: 'reglas', titulo: 'Heurísticos',     tag: 'DETERMINISTAS' },
      { id: 'control',   x: 1336, y: 158, w: 176, h: 58, icono: 'decision', titulo: 'Decisión', forma: 'rombo', rsub: 'PERMIT / acción' },
      { id: 'feed',      x: 1336, y: 246, w: 176, h: 58, icono: 'fichero', titulo: 'Feed firmado',     tag: 'ed25519 · CICLO 10 s' },
      { id: 'relay',     x: 1336, y: 334, w: 176, h: 52, icono: 'espejo', titulo: 'Relay (bastión)',   val: 'réplica · ciclo 10 s' },
      { id: 'agente',    x: 1336, y: 416, w: 176, h: 58, icono: 'escudo', titulo: 'Agente en host',   tag: 'CICLO 10 s · nftables' },
      { id: 'registro',  x: 1592, y: 160, w: 176, h: 46, icono: 'fichero', titulo: 'motor_decision.log', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'panel',     x: 1592, y: 256, w: 176, h: 52, icono: 'ojo',    titulo: 'Este panel',        tag: 'SOLO LECTURA' },
      { id: 'wazuh',     x: 1592, y: 352, w: 176, h: 52, icono: 'ojo',    titulo: 'Wazuh (SIEM)',      tag: 'PREVISTO', clase: 'artefacto' },
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
      { d: 'M982,249 C1020,256 1036,300 1060,305',  desde: 'variables', hasta: 'heuristicos', etiqueta: '+ conteos', ex: 1012, ey: 318 },
      { d: 'M1148,128 L1148,158',                   desde: 'reentrenamiento', hasta: 'modelo', etiqueta: 'promover', ex: 1186, ey: 143 },
      { d: 'M1236,187 L1336,187',                   desde: 'modelo',   hasta: 'control', etiqueta: 'score &lt; umbral', ex: 1286, ey: 178 },
      { d: 'M1236,305 C1290,300 1302,196 1336,192', desde: 'heuristicos', hasta: 'control', etiqueta: 'confirmado', ex: 1290, ey: 250 },
      { d: 'M1424,216 L1424,246',                   desde: 'control',  hasta: 'feed' },
      { d: 'M1424,304 L1424,334',                   desde: 'feed',     hasta: 'relay' },
      { d: 'M1424,386 L1424,416',                   desde: 'relay',    hasta: 'agente', tipo: 'fijo' },
      { d: 'M1512,187 C1550,185 1562,184 1592,183', desde: 'control',  hasta: 'registro', etiqueta: 'cada decisión', ex: 1552, ey: 175 },
      { d: 'M1680,206 L1680,256',                   desde: 'registro', hasta: 'panel', etiqueta: 'lee', ex: 1698, ey: 234 },
      { d: 'M1660,206 C1585,270 1585,330 1660,352', desde: 'registro', hasta: 'wazuh', tipo: 'previsto', etiqueta: 'syslog', ex: 1642, ey: 336 },
    ],
  },
  // --- Vista METODOLOGICA: como se CONSTRUYO (las 7 fases del metodo) -------
  metodologica: {
    w: 1632, h: 330,
    packet: 'M32,109 L1608,109',
    grupos: [
      { x: 20,   y: 20, w: 210, h: 150, txt: 'Datos y línea base',  n: 1 },
      { x: 250,  y: 20, w: 210, h: 150, txt: 'Preproceso y features', n: 2 },
      { x: 480,  y: 20, w: 210, h: 150, txt: 'Modelado híbrido',    n: 3 },
      { x: 710,  y: 20, w: 210, h: 150, txt: 'Experimento y eval.', n: 4 },
      { x: 940,  y: 20, w: 210, h: 150, txt: 'Respuesta',           n: 5 },
      { x: 1170, y: 20, w: 210, h: 150, txt: 'Despliegue',          n: 6 },
      { x: 1400, y: 20, w: 210, h: 150, txt: 'Validación',          n: 7 },
    ],
    // val = estado de la fase; las tres vueltas atras van anidadas por debajo
    // (la mas corta arriba) para que no se crucen.
    nodos: [
      { id: 'm_datos',  x: 32,   y: 78, w: 196, h: 62, icono: 'disco',    titulo: 'Línea base real',       tag: 'SPAN · PCAP · eve', val: 'hecho' },
      { id: 'm_feat',   x: 262,  y: 78, w: 196, h: 62, icono: 'tabla',    titulo: '28 variables L3/L4/L7', tag: 'extractor congelado', val: 'hecho' },
      { id: 'm_modelo', x: 492,  y: 78, w: 196, h: 62, icono: 'modelo',   titulo: 'IF + heurísticos',      tag: 'θ = −0,622389', val: 'hecho' },
      { id: 'm_eval',   x: 722,  y: 78, w: 196, h: 62, icono: 'lupa',     titulo: 'Replay vs Suricata',    tag: '9/9 vs 0/9 · N=3', val: 'parcial · falta C3' },
      { id: 'm_resp',   x: 952,  y: 78, w: 196, h: 62, icono: 'escudo',   titulo: 'PERMIT/LIMIT/BLOCK',    tag: 'feed firmado', val: 'hecho' },
      { id: 'm_desp',   x: 1182, y: 78, w: 196, h: 62, icono: 'nic',      titulo: 'Desplegado en sensor',  tag: 'systemd · replicable', val: 'hecho' },
      { id: 'm_valid',  x: 1412, y: 78, w: 196, h: 62, icono: 'ojo',      titulo: 'Interna + externa',     tag: 'demo · TAM · expertos', val: 'en curso' },
    ],
    aristas: [
      { d: 'M228,109 L262,109',   desde: 'm_datos',  hasta: 'm_feat',   tipo: 'fijo' },
      { d: 'M458,109 L492,109',   desde: 'm_feat',   hasta: 'm_modelo', tipo: 'fijo' },
      { d: 'M688,109 L722,109',   desde: 'm_modelo', hasta: 'm_eval',   tipo: 'fijo' },
      { d: 'M918,109 L952,109',   desde: 'm_eval',   hasta: 'm_resp',   tipo: 'fijo' },
      { d: 'M1148,109 L1182,109', desde: 'm_resp',   hasta: 'm_desp',   tipo: 'fijo' },
      { d: 'M1378,109 L1412,109', desde: 'm_desp',   hasta: 'm_valid',  tipo: 'fijo' },
      { d: 'M790,140 L790,196 L640,196 L640,140',     desde: 'm_eval',  hasta: 'm_modelo', tipo: 'retorno', etiqueta: 'recalibrar', ex: 715, ey: 190 },
      { d: 'M1280,140 L1280,240 L560,240 L560,140',   desde: 'm_desp',  hasta: 'm_modelo', tipo: 'persona', etiqueta: 'reentrenar con aprobación humana', ex: 920, ey: 234 },
      { d: 'M1510,140 L1510,286 L360,286 L360,140',   desde: 'm_valid', hasta: 'm_feat',   tipo: 'retorno', etiqueta: 'observaciones → mejoras', ex: 935, ey: 280 },
    ],
  },
  // --- Vista CONSTRUCCION Y ENTRENAMIENTO: de los datos al modelo congelado
  // (fila 1, una vez y en seco) y su ciclo de vida (fila 2, de derecha a
  // izquierda). Responde: donde se entrena, como se partio, que se comparo, con
  // que metricas, por que gano, que cambia al reentrenar y cada cuanto.
  // Fila 3: el aprendizaje supervisado de cyberflow_aprendizaje.py, de
  // izquierda a derecha, con sus cuatro defensas y la aprobacion humana que
  // devuelve el modelo nuevo a "Congelar".
  construccion: {
    w: 1560, h: 600,
    packet: 'M140,104 L1420,104 L1420,284 L908,284 L908,316 L344,432 L344,464 L1420,464 L1420,316',
    grupos: [
      { x: 20, y: 36,  w: 1520, h: 130, txt: 'Construcción: una vez, en seco, con datos de esta red', n: 1 },
      { x: 20, y: 216, w: 1520, h: 130, txt: 'Operación', n: 2 },
      { x: 20, y: 396, w: 1520, h: 150, txt: 'Reentrenamiento con aprobación humana: cada noche, lo promueve una persona', n: 3 },
    ],
    nodos: [
      { id: 'c_datos',   x: 40,   y: 72,  w: 200, h: 64, icono: 'disco',    titulo: 'Datos de la red',      tag: 'SPAN → PCAP + eve.json', val: '335 202 ventanas' },
      { id: 'c_limpia',  x: 296,  y: 72,  w: 200, h: 64, icono: 'tijera',   titulo: 'Limpieza y alcance',   tag: 'espejo · control · excluidas', val: 'sin imputación' },
      { id: 'c_part',    x: 552,  y: 72,  w: 200, h: 64, icono: 'tabla',    titulo: 'Partición',            tag: 'train / validación / test', val: '204 148 / 65 633 / 65 421' },
      { id: 'c_cand',    x: 808,  y: 72,  w: 200, h: 64, icono: 'modelo',   titulo: 'Candidatos',           tag: 'IF · LOF · OCSVM · EE', val: '7 (laboratorio) · IF aquí' },
      { id: 'c_metr',    x: 1064, y: 72,  w: 200, h: 64, icono: 'lupa',     titulo: 'Comparar métricas',    tag: 'FPR · recall · F1 · AUC', val: 'criterio fijado antes' },
      { id: 'c_sel',     x: 1320, y: 72,  w: 200, h: 64, icono: 'decision', titulo: 'Selección', forma: 'rombo', rsub: 'IF → esta red' },
      { id: 'c_cong',    x: 1320, y: 252, w: 200, h: 64, icono: 'cpu',      titulo: 'Congelar modelo', tag: 'α=0,01 · −0,622389', val: 'sha256 df547da0…' },
      { id: 'c_desp',    x: 1064, y: 252, w: 200, h: 64, icono: 'nic',      titulo: 'Despliegue',           tag: 'promover + verificar', val: 'manifiesto + hash' },
      { id: 'c_acum',    x: 808,  y: 252, w: 200, h: 64, icono: 'fichero',  titulo: 'Acumulación',          tag: 'temporizador · v3', val: 'cada 10 min' },
      { id: 'c_vivo',    x: 552,  y: 252, w: 200, h: 64, icono: 'escudo',   titulo: 'Motor en vivo',        tag: 'PERMIT · ALERT · BLOCK', val: 'marca IPs sospechosas' },
      { id: 'a_oro',     x: 40,   y: 432, w: 176, h: 64, icono: 'disco',    titulo: 'Conjunto de oro',      tag: 'FIJO · NUNCA ENTRENA', val: 'test de la nota L', clase: 'artefacto' },
      { id: 'a_san',     x: 256,  y: 432, w: 176, h: 64, icono: 'tijera',   titulo: '1 · Saneamiento',        tag: 'LOTE · EXCLUYE VENTANAS', val: 'fuera lo marcado y atípico' },
      { id: 'a_lin',     x: 472,  y: 432, w: 176, h: 64, icono: 'fichero',  titulo: '2 · Linaje',             tag: 'SHA256 ENCADENADO', val: 'registro.jsonl', clase: 'artefacto' },
      { id: 'a_der',     x: 688,  y: 432, w: 176, h: 64, icono: 'lupa',     titulo: '4 · Deriva',             tag: 'CONTRA EL ORO', val: 'PSI · % anómalo' },
      { id: 'a_inf',     x: 904,  y: 432, w: 176, h: 64, icono: 'modelo',   titulo: '3 · Candidato',          tag: 'LÍMITE DE INFLUENCIA', val: 'nuevo ≤ 30 % · IP ≤ 10 %' },
      { id: 'a_ver',     x: 1120, y: 432, w: 176, h: 64, icono: 'decision', titulo: 'Veredicto', forma: 'rombo', rsub: 'FPR≤ · det≥' },
      { id: 'a_hum',     x: 1332, y: 432, w: 176, h: 64, icono: 'ojo',      titulo: 'Aprobación humana',    tag: 'PROMOVER · REVERTIR', val: 'con copia del .toml' },
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
      { d: 'M1064,270 C960,226 760,226 700,252', desde: 'c_desp', hasta: 'c_vivo', etiqueta: 'puntúa cada 10 s', ex: 880, ey: 228 },
      { d: 'M552,120 C380,150 128,300 128,432', desde: 'c_part', hasta: 'a_oro', tipo: 'descarte', etiqueta: 'su test se congela como oro', ex: 250, ey: 300 },
      { d: 'M908,316 C908,384 380,372 360,432', desde: 'c_acum', hasta: 'a_san', etiqueta: 'lote del día', ex: 640, ey: 372 },
      { d: 'M652,316 C652,372 330,380 320,432', desde: 'c_vivo', hasta: 'a_san', tipo: 'descarte', etiqueta: 'IPs marcadas', ex: 560, ey: 350 },
      { d: 'M216,464 L256,464',   desde: 'a_oro',    hasta: 'a_san', tipo: 'descarte' },
      { d: 'M432,464 L472,464',   desde: 'a_san',    hasta: 'a_lin' },
      { d: 'M648,464 L688,464',   desde: 'a_lin',    hasta: 'a_der' },
      { d: 'M864,464 L904,464',   desde: 'a_der',    hasta: 'a_inf' },
      { d: 'M1080,464 L1120,464', desde: 'a_inf',    hasta: 'a_ver' },
      { d: 'M1296,464 L1332,464', desde: 'a_ver',    hasta: 'a_hum' },
      { d: 'M128,496 C128,580 1208,580 1208,496', desde: 'a_oro', hasta: 'a_ver', tipo: 'descarte', etiqueta: 'evalúa vigente y candidato en el oro', ex: 668, ey: 572 },
      { d: 'M1420,432 L1420,316', desde: 'a_hum',    hasta: 'c_cong', etiqueta: 'promover: modelo nuevo', ex: 1476, ey: 374 },
    ],
  },
  // --- Vista RED Y CAPTURA: por donde va el trafico de prueba y por donde
  // llega su copia al sensor. Reusa los nodos vivos (span, nic, captura,
  // suricata) para que el estado sea el real. El recorrido de prueba y la copia
  // SPAN llevan estilos distintos: el sensor no esta en el recorrido.
  red: {
    w: 1480, h: 500,
    packet: 'M200,84 L330,240 L400,216 L400,118 L456,118 L456,216 L330,250 L200,240',
    grupos: [
      { x: 12,  y: 32,  w: 200, h: 146, txt: 'VLAN 20 · usuarios' },
      { x: 12,  y: 190, w: 200, h: 86,  txt: 'VLAN 30 · DMZ' },
      { x: 12,  y: 288, w: 200, h: 146, txt: 'VLAN 10 · gestión' },
      { x: 740, y: 32,  w: 720, h: 452, txt: 'Host ESXi · 172.17.25.2' },
    ],
    nodos: [
      { id: 'atacante',  x: 24,  y: 60,  w: 176, h: 48, icono: 'atacante',   titulo: 'Atacante (Kali)',  host: true, ip: '10.10.20.30',     desc: '' },
      { id: 'clientes',  x: 24,  y: 118, w: 176, h: 48, icono: 'usuarios',    titulo: 'Clientes',         host: true, ip: '10.10.20.21-.26', desc: '' },
      { id: 'servidor',  x: 24,  y: 216, w: 176, h: 48, icono: 'host_servidor',  titulo: 'srv-dmz · objetivo', host: true, ip: '10.10.30.10',   desc: '' },
      { id: 'r_bastion', x: 24,  y: 316, w: 176, h: 48, icono: 'ojo',    titulo: 'VM-GESTION',       host: true, ip: '10.10.10.30',     desc: '' },
      { id: 'r_dns',     x: 24,  y: 374, w: 176, h: 48, icono: 'red',    titulo: 'DNS / AD',         host: true, ip: '10.10.10.20',     desc: '' },
      { id: 'gateway',   x: 330, y: 70,  w: 196, h: 48, icono: 'router', titulo: 'Router A/B',     host: true, ip: 'enruta entre VLAN', desc: '' },
      { id: 'span',      x: 330, y: 216, w: 196, h: 58, icono: 'switch', titulo: 'Switch',           tag: 'NO ENRUTA · ESPEJA' },
      { id: 'r_pg',      x: 760, y: 70,  w: 240, h: 58, icono: 'nic',    titulo: 'PG-CYBERFLOW-SPAN', tag: 'GRUPO DE PUERTOS', val: 'modo promiscuo' },
      { id: 'nic',       x: 760, y: 200, w: 196, h: 58, icono: 'nic',    titulo: 'Sensor1 · ens37',  tag: 'CAPTURA · SIN IP', val: 'modo promiscuo' },
      { id: 'r_sensor2', x: 990, y: 200, w: 196, h: 58, icono: 'nic',    titulo: 'Sensor2 · ens37',  tag: 'RÉPLICA · 10.10.60.12', val: 'recibe la misma copia' },
      { id: 'r_cmp',     x: 1220, y: 200, w: 216, h: 58, icono: 'lupa',  titulo: 'VM-SURICATA',      tag: 'COMPARADOR · 10.10.60.13', val: 'recepción por comprobar', clase: 'artefacto' },
      { id: 'captura',   x: 760, y: 340, w: 176, h: 58, icono: 'captura', titulo: 'tcpdump',         tag: 'ANILLO PCAP' },
      { id: 'suricata',  x: 970, y: 340, w: 176, h: 58, icono: 'lupa',   titulo: 'Suricata',         tag: 'eve.json' },
      { id: 'ens34',     x: 1192, y: 340, w: 208, h: 58, icono: 'nic',   titulo: 'Sensor1 · ens34',  tag: 'GESTIÓN · 10.10.60.11' },
      { id: 'gestion',   x: 1192, y: 418, w: 208, h: 46, icono: 'ojo',   titulo: 'Plano de gestión', tag: 'SSH · PANEL · FEED' },
    ],
    aristas: [
      { d: 'M200,84 C270,84 270,232 330,232',     desde: 'atacante', hasta: 'span',     tipo: 'fijo', etiqueta: '1 · generado', ex: 262, ey: 76 },
      { d: 'M200,142 C262,142 268,240 330,240',   desde: 'clientes', hasta: 'span',     tipo: 'fijo' },
      { d: 'M400,216 L400,118',                   desde: 'span',     hasta: 'gateway',  tipo: 'fijo' },
      { d: 'M456,118 L456,216',                   desde: 'gateway',  hasta: 'span',     tipo: 'fijo', etiqueta: '2 · troncales Gi1/0/23 · Gi2/0/23', ex: 606, ey: 170 },
      { d: 'M330,252 C280,252 260,240 200,240',   desde: 'span',     hasta: 'servidor', tipo: 'fijo', etiqueta: '3 · recibido', ex: 268, ey: 268 },
      { d: 'M200,340 C290,340 340,320 380,274',   desde: 'r_bastion', hasta: 'span',    tipo: 'enlace' },
      { d: 'M526,245 C650,245 640,99 760,99',     desde: 'span',     hasta: 'r_pg',     tipo: 'copia', etiqueta: 'copia SPAN · Gi2/0/19', ex: 640, ey: 150 },
      { d: 'M858,128 L858,200',                   desde: 'r_pg',     hasta: 'nic',      tipo: 'copia' },
      { d: 'M940,128 C940,170 1088,160 1088,200', desde: 'r_pg',     hasta: 'r_sensor2', tipo: 'copia' },
      { d: 'M1000,99 C1328,99 1328,140 1328,200', desde: 'r_pg',     hasta: 'r_cmp',    tipo: 'previsto' },
      { d: 'M848,258 L848,340',                   desde: 'nic',      hasta: 'captura',  etiqueta: '4 · observado', ex: 800, ey: 304 },
      { d: 'M880,258 C880,300 1058,296 1058,340', desde: 'nic',      hasta: 'suricata' },
      { d: 'M1296,398 L1296,418',                 desde: 'ens34',    hasta: 'gestion',  tipo: 'enlace' },
    ],
  },
  // --- Vista DECISION: dos niveles. El motor decide cada ventana; el publicador
  // combina por IP cada 10 s sobre los ultimos 120 s y fija la caducidad.
  // Fuentes: motor_decision.py, heuristicos.py, publicar_feed.py, escalada.py.
  decision: {
    w: 1560, h: 520,
    packet: 'M230,149 L330,99 L630,99 L1060,140 L1160,174 L140,330 L240,359 L820,359 L920,388 L1140,440',
    grupos: [
      { x: 12, y: 32,  w: 1536, h: 236, txt: 'Motor · decide cada ventana', n: 1 },
      { x: 12, y: 296, w: 1536, h: 112, txt: 'Publicador · ciclo 10 s, últimos 120 s, por IP', n: 2 },
    ],
    nodos: [
      { id: 'variables',   x: 40,   y: 120, w: 190, h: 58, icono: 'tabla',  titulo: 'Variables / 10 s', tag: 'POR IP Y VENTANA' },
      { id: 'd_excluida',  x: 40,   y: 204, w: 190, h: 48, icono: 'tijera', titulo: 'IP excluida',      tag: 'SE CUENTA · NO SE PUNTÚA', val: 'fuera de alcance', clase: 'sumidero' },
      { id: 'modelo',      x: 330,  y: 70,  w: 200, h: 58, icono: 'modelo', titulo: 'Isolation Forest', tag: 'SOLO CON PAQUETES' },
      { id: 'heuristicos', x: 330,  y: 170, w: 200, h: 58, icono: 'reglas', titulo: 'Heurísticos',      tag: 'TAMBIÉN SIN PAQUETES (L7)' },
      { id: 'd_alert',     x: 630,  y: 70,  w: 200, h: 58, icono: 'decision', titulo: 'ALERT del modelo', tag: 's(x) < −0,622389', val: 'señal · sin medida' },
      { id: 'd_reglas',    x: 630,  y: 170, w: 300, h: 58, icono: 'reglas', titulo: 'Regla disparada',  tag: 'ABUSO HTTP · DNS → LIMIT', val: 'fuerza bruta · escaneo → BLOCK' },
      { id: 'registro',    x: 1060, y: 124, w: 200, h: 50, icono: 'fichero', titulo: 'motor_decision.log', tag: 'IP · VENTANA · SCORE · REGLA', clase: 'artefacto' },
      { id: 'd_nunca',     x: 40,   y: 330, w: 200, h: 58, icono: 'tijera', titulo: 'Nunca bloquear',   tag: 'FILTRO', val: 'bastión · sensor · DNS' },
      { id: 'd_severa',    x: 300,  y: 330, w: 200, h: 58, icono: 'decision', titulo: 'La más severa', forma: 'rombo', rsub: 'BLOCK > LIMIT · por IP' },
      { id: 'd_escalera',  x: 560,  y: 330, w: 200, h: 58, icono: 'ciclo',  titulo: 'Escalera',         tag: 'REINCIDENCIA EN 24 h', val: '300 → 1800 → 3600 s' },
      { id: 'feed',        x: 820,  y: 330, w: 200, h: 58, icono: 'fichero', titulo: 'Feed firmado',    tag: 'CON VERSIÓN DE UMBRALES' },
      { id: 'd_permit',    x: 560,  y: 440, w: 200, h: 58, icono: 'ojo',    titulo: 'PERMIT',           val: 'sin entrada en el feed' },
      { id: 'd_limit',     x: 820,  y: 440, w: 200, h: 58, icono: 'ciclo',  titulo: 'LIMIT',            val: 'tasa limitada · 300 s', clase: 'acc-limit' },
      { id: 'd_block',     x: 1080, y: 440, w: 240, h: 58, icono: 'escudo', titulo: 'BLOCK',            tag: 'REVISIÓN HUMANA DESDE EL 3.º', val: '300 · 1800 · 3600 s', clase: 'acc-block' },
    ],
    aristas: [
      { d: 'M135,178 L135,204',                      desde: 'variables',   hasta: 'd_excluida', tipo: 'descarte' },
      { d: 'M230,149 C280,149 280,99 330,99',        desde: 'variables',   hasta: 'modelo',     etiqueta: '28 variables', ex: 276, ey: 106 },
      { d: 'M230,149 C280,149 280,199 330,199',      desde: 'variables',   hasta: 'heuristicos', etiqueta: '+ conteos', ex: 280, ey: 204 },
      { d: 'M530,99 L630,99',                        desde: 'modelo',      hasta: 'd_alert',    etiqueta: 'score &lt; umbral', ex: 580, ey: 90 },
      { d: 'M530,199 L630,199',                      desde: 'heuristicos', hasta: 'd_reglas',   tipo: 'fijo' },
      { d: 'M830,99 C960,99 950,140 1060,140',       desde: 'd_alert',     hasta: 'registro',   tipo: 'fijo' },
      { d: 'M930,199 C1000,199 990,158 1060,158',    desde: 'd_reglas',    hasta: 'registro',   tipo: 'fijo' },
      { d: 'M1160,174 C1160,300 140,236 140,330',    desde: 'registro',    hasta: 'd_nunca',    tipo: 'fijo', etiqueta: 'decisiones por ventana', ex: 660, ey: 286 },
      { d: 'M240,359 L300,359',                      desde: 'd_nunca',     hasta: 'd_severa',   tipo: 'fijo' },
      { d: 'M500,359 L560,359',                      desde: 'd_severa',    hasta: 'd_escalera', tipo: 'fijo' },
      { d: 'M760,359 L820,359',                      desde: 'd_escalera',  hasta: 'feed',       tipo: 'fijo' },
      { d: 'M900,388 C900,416 660,412 660,440',      desde: 'feed',        hasta: 'd_permit',   tipo: 'previsto' },
      { d: 'M920,388 L920,440',                      desde: 'feed',        hasta: 'd_limit',    tipo: 'fijo' },
      { d: 'M940,388 C940,416 1200,412 1200,440',    desde: 'feed',        hasta: 'd_block',    tipo: 'fijo' },
    ],
  },
  // --- Vista RESPUESTA: del veredicto a la regla en el host y a su retirada.
  // Los tres tiempos se miden desde el inicio del ataque con el reloj del sensor
  // (docs/evidencias/tiempos-2026-10-06.md).
  respuesta: {
    w: 1560, h: 350,
    packet: 'M40,139 L1286,139 L1198,230',
    grupos: [
      { x: 12,   y: 32, w: 510, h: 290, txt: 'Sensor',         n: 1 },
      { x: 560,  y: 32, w: 240, h: 290, txt: 'Bastión',        n: 2 },
      { x: 830,  y: 32, w: 480, h: 290, txt: 'Host protegido', n: 3 },
      { x: 1340, y: 32, w: 208, h: 290, txt: 'Persona',        n: 4 },
    ],
    nodos: [
      { id: 'control',    x: 40,   y: 110, w: 176, h: 58, icono: 'decision', titulo: 'Decisión', forma: 'rombo', rsub: 'detección ~2–40 s' },
      { id: 'feed',       x: 320,  y: 110, w: 176, h: 58, icono: 'fichero', titulo: 'Feed firmado',  tag: 'CICLO ≤ 10 s' },
      { id: 'relay',      x: 592,  y: 110, w: 176, h: 58, icono: 'espejo',  titulo: 'Relay',         tag: 'RÉPLICA', val: 'ciclo 10 s' },
      { id: 'agente',     x: 860,  y: 110, w: 176, h: 58, icono: 'escudo',  titulo: 'Agente',        tag: 'VERIFICA LA FIRMA' },
      { id: 'p_nft',      x: 1110, y: 110, w: 176, h: 58, icono: 'escudo',  titulo: 'nftables',      tag: 'MEDIDA EN ~1,3 s', val: 'LIMIT · BLOCK', clase: 'acc-block' },
      { id: 'p_noaplica', x: 860,  y: 230, w: 176, h: 58, icono: 'tijera',  titulo: 'Firma inválida', tag: 'LO VIGENTE CADUCA', val: 'no aplica nada', clase: 'sumidero' },
      { id: 'p_caduca',   x: 1110, y: 230, w: 176, h: 58, icono: 'ciclo',   titulo: 'Caduca sola',   tag: 'TIMEOUT DEL SET', val: '300 · 1800 · 3600 s' },
      { id: 'p_manual',   x: 1356, y: 110, w: 176, h: 58, icono: 'ojo',     titulo: 'Retirada manual', tag: 'UNA PERSONA', val: 'nft delete element' },
    ],
    aristas: [
      { d: 'M216,139 L320,139',   desde: 'control', hasta: 'feed',       etiqueta: 'ciclo 10 s', ex: 268, ey: 130 },
      { d: 'M496,139 L592,139',   desde: 'feed',    hasta: 'relay',      tipo: 'fijo', etiqueta: 'copia', ex: 544, ey: 130 },
      { d: 'M768,139 L860,139',   desde: 'relay',   hasta: 'agente',     tipo: 'fijo', etiqueta: 'pull', ex: 814, ey: 130 },
      { d: 'M1036,139 L1110,139', desde: 'agente',  hasta: 'p_nft',      tipo: 'fijo', etiqueta: 'válida', ex: 1073, ey: 130 },
      { d: 'M948,168 L948,230',   desde: 'agente',  hasta: 'p_noaplica', tipo: 'descarte' },
      { d: 'M1198,168 L1198,230', desde: 'p_nft',   hasta: 'p_caduca',   tipo: 'fijo' },
      { d: 'M1356,139 L1286,139', desde: 'p_manual', hasta: 'p_nft',     tipo: 'persona', etiqueta: 'retira', ex: 1322, ey: 130 },
    ],
  },
  // --- Vista CARPETAS: la arquitectura del repositorio como un arbol de tres
  // columnas (raiz -> carpetas de primer nivel -> dentro de scripts/). Es
  // estatico: no tiene estado vivo, cada nodo lleva su descriptor en `val` y el
  // contenido en el panel de detalle.
  carpetas: {
    w: 880, h: 472, packet: '',
    grupos: [
      { x: 290, y: 6, w: 226, h: 460, txt: 'Carpetas de primer nivel' },
      { x: 590, y: 6, w: 260, h: 374, txt: 'Dentro de scripts/' },
    ],
    nodos: [
      { id: 'cf_root',      x: 20,  y: 214, w: 188, h: 60, icono: 'carpeta', titulo: 'CYBERFLOW/',  val: 'repositorio' },
      { id: 'cf_scripts',   x: 300, y: 30,  w: 206, h: 54, icono: 'carpeta', titulo: 'scripts/',    val: 'todo el código' },
      { id: 'cf_configs',   x: 300, y: 104, w: 206, h: 54, icono: 'carpeta', titulo: 'configs/',    val: '.toml · features · suricata' },
      { id: 'cf_artifacts', x: 300, y: 178, w: 206, h: 54, icono: 'carpeta', titulo: 'artifacts/',  val: 'modelo · línea base' },
      { id: 'cf_docs',      x: 300, y: 252, w: 206, h: 54, icono: 'carpeta', titulo: 'docs/',       val: 'evaluación · evidencias' },
      { id: 'cf_tests',     x: 300, y: 326, w: 206, h: 54, icono: 'carpeta', titulo: 'tests/',      val: 'batería unittest' },
      { id: 'cf_deploy',    x: 300, y: 400, w: 206, h: 54, icono: 'carpeta', titulo: 'deploy/ · ansible/', val: 'instalación' },
      { id: 'cf_engine',    x: 600, y: 18,  w: 240, h: 50, icono: 'carpeta', titulo: 'scripts/engine/',   val: 'motor · panel · feed' },
      { id: 'cf_features',  x: 600, y: 78,  w: 240, h: 50, icono: 'carpeta', titulo: 'scripts/features/', val: 'extractores de variables' },
      { id: 'cf_modeling',  x: 600, y: 138, w: 240, h: 50, icono: 'carpeta', titulo: 'scripts/modeling/', val: 'entrenar · aprendizaje' },
      { id: 'cf_enforce',   x: 600, y: 198, w: 240, h: 50, icono: 'carpeta', titulo: 'scripts/enforce/',  val: 'agente del host' },
      { id: 'cf_setup',     x: 600, y: 258, w: 240, h: 50, icono: 'carpeta', titulo: 'scripts/setup/',    val: 'instalación · config' },
      { id: 'cf_mas',       x: 600, y: 318, w: 240, h: 50, icono: 'fichero', titulo: '+ dataset · evaluacion · campaign…', val: 'y más', clase: 'artefacto' },
    ],
    aristas: [
      { d: 'M208,244 C256,244 256,57 300,57',   desde: 'cf_root', hasta: 'cf_scripts',   tipo: 'fijo' },
      { d: 'M208,244 C256,244 256,131 300,131', desde: 'cf_root', hasta: 'cf_configs',   tipo: 'fijo' },
      { d: 'M208,244 C256,232 256,205 300,205', desde: 'cf_root', hasta: 'cf_artifacts', tipo: 'fijo' },
      { d: 'M208,244 C256,258 256,279 300,279', desde: 'cf_root', hasta: 'cf_docs',      tipo: 'fijo' },
      { d: 'M208,244 C256,290 256,353 300,353', desde: 'cf_root', hasta: 'cf_tests',     tipo: 'fijo' },
      { d: 'M208,244 C256,320 256,427 300,427', desde: 'cf_root', hasta: 'cf_deploy',    tipo: 'fijo' },
      { d: 'M506,57 C556,57 556,43 600,43',     desde: 'cf_scripts', hasta: 'cf_engine',   tipo: 'fijo' },
      { d: 'M506,57 C556,70 556,103 600,103',   desde: 'cf_scripts', hasta: 'cf_features', tipo: 'fijo' },
      { d: 'M506,57 C556,90 556,163 600,163',   desde: 'cf_scripts', hasta: 'cf_modeling', tipo: 'fijo' },
      { d: 'M506,57 C556,110 556,223 600,223',  desde: 'cf_scripts', hasta: 'cf_enforce',  tipo: 'fijo' },
      { d: 'M506,57 C556,140 556,283 600,283',  desde: 'cf_scripts', hasta: 'cf_setup',    tipo: 'fijo' },
      { d: 'M506,57 C556,170 556,343 600,343',  desde: 'cf_scripts', hasta: 'cf_mas',      tipo: 'fijo' },
    ],
  },
  // --- Vista VALIDACION: una tabla (requisito, prueba, evidencia, estado), no
  // un diagrama. La pinta validacionHTML().
  validacion: { w: 1200, h: 420, tabla: true, packet: '', grupos: [], nodos: [], aristas: [] },
};

// Matriz de validacion interna. Cada estado cita la nota que lo respalda; un
// parcial dice que falta. Al cambiar un estado, cambiarlo aqui y en la figura
// VI-7 (orquestacion: diagramas-vistas-gui/drawio/gen_vi7.py).
const VALIDACION_FECHA = '12-oct-2026';
const VALIDACION = [
  ['Instalación offline', 'Desde cero en una VM limpia', 'doctor.sh OK a los 30 min · nota R', 'c', ''],
  ['Captura y extracción', 'PCAP + EVE → 28 variables', 'Espejo sin descartes · notas B y D', 'c', ''],
  ['Decisión híbrida', 'Score, regla y motivo por ventana', 'Registro de decisiones · nota 31', 'c', ''],
  ['Respuesta distribuida', 'Feed firmado → nftables', 'Escaneo bloqueado en vivo 12-oct (srv-dmz) · notas O y 26', 'p', 'fuerza bruta en vivo: campaña C3'],
  ['Acceso por roles', 'admin y lector', 'admin por navegador comprobado · 401 sin sesión, sin HTTP en claro · nota R', 'p', 'falta la prueba del rol lector'],
  ['Reentrenamiento', 'Lote → candidato → evaluación', 'Oro, linaje y lote rechazado · nota S', 'p', 'sin candidato real'],
  ['Reversión', 'Caducidad y retirada manual', 'Escalera en pruebas unitarias', 'p', 'falta registro en vivo'],
  ['Comparación con Suricata', 'Mismo PCAP, cuatro condiciones', 'Batería N=3 · notas 26, 28 y 31', 'p', 'C3 propuesta · nota 33'],
  ['Tres tiempos', 'Detección, decisión, respuesta', 'Mediciones del 06-oct (N=3 y N=2)', 'c', 'N pequeño'],
];
const VAL_NOMBRE = { c: 'Cumplido', p: 'Parcial', n: 'Pendiente' };

function validacionHTML() {
  const filas = VALIDACION.map(f =>
    `<tr><td>${f[0]}</td><td>${f[1]}</td><td>${f[2]}</td>` +
    `<td><span class="val-est ${f[3]}">${VAL_NOMBRE[f[3]]}</span>` +
    (f[4] ? `<span class="falta">${f[4]}</span>` : '') + '</td></tr>').join('');
  return '<table><thead><tr><th>Requisito</th><th>Prueba</th><th>Evidencia</th><th>Estado</th></tr></thead>'
    + `<tbody>${filas}</tbody></table>`;
}

function validacionDetalleHTML() {
  const n = k => VALIDACION.filter(f => f[3] === k).length;
  return '<h3>Validación interna</h3>'
    + `<p class="dim">Estado <b>documental</b> al ${VALIDACION_FECHA} — no es una medición en vivo del sensor. Cada estado cita su evidencia; un parcial dice qué falta.</p>`
    + `<dl><dt>Cumplidos</dt><dd>${n('c')}</dd><dt>Parciales</dt><dd>${n('p')}</dd><dt>Pendientes</dt><dd>${n('n')}</dd></dl>`
    + '<p class="dim">Los subtotales resumen la tabla documental; no se deriva de ellos el éxito en producción. TAM y juicio de expertos van en la validación externa.</p>';
}

let topoVista = 'completa';
// 17-nov: Vista lab = lo montado para el ensayo; Vista operativa = solo el flujo de una red real.
// En operativa no se sabe de antemano si el tráfico es un ataque: la Kali y los clientes se
// funden en «Tráfico entrante» y desaparece lo que solo existe en el laboratorio.
let topoModo = 'lab';
try { if (localStorage.getItem('cf_topo_modo') === 'operativa') topoModo = 'operativa'; } catch (e) { /* lab */ }
const TOPO_SIEMPRE_OCULTOS = new Set(['reentrenamiento']);   // el aprendizaje no se muestra (17-nov)
const TOPO_OP_OCULTOS = {
  red: ['atacante', 'clientes', 'r_sensor2', 'r_cmp'],
  completa: ['atacante', 'clientes', 'descartes', 'wazuh'],
};
const TOPO_OP_ENTRANTE = {
  red: { nodo: { id: 'entrante', x: 24, y: 60, w: 176, h: 106, icono: 'entrante', titulo: 'Tráfico entrante', host: true, ip: 'sin clasificar', desc: 'legítimo o ataque: lo decide el sensor' },
         arista: { d: 'M200,113 C268,113 268,236 330,236', desde: 'entrante', hasta: 'span', tipo: 'fijo', etiqueta: '1 · entra', ex: 262, ey: 104 },
         grupo: 'Entrada · sin clasificar',
         packet: 'M200,113 L330,240 L400,216 L400,118 L456,118 L456,216 L330,250 L200,240' },
  completa: { nodo: { id: 'entrante', x: 24, y: 100, w: 176, h: 58, icono: 'entrante', titulo: 'Tráfico entrante', host: true, ip: 'sin clasificar', desc: 'legítimo o ataque: lo decide el sensor' },
              arista: { d: 'M200,129 C250,129 262,99 286,99', desde: 'entrante', hasta: 'red', tipo: 'fijo', etiqueta: 'entra', ex: 240, ey: 112 },
              grupo: 'Red · entrada y servicios' },
};
const TOPO_LEDE = {
  red: 'Por dónde pasa el tráfico y cómo llega su copia al sensor: el switch espeja el troncal del router; el sensor escucha sin IP y no está en el camino.',
  completa: 'El recorrido de un paquete de punta a punta: captura, variables cada 10 s, modelo y reglas, decisión, feed firmado y agente en el host.',
  decision: 'Cómo se decide: el motor juzga cada ventana (modelo + reglas); el publicador agrupa por IP, elige lo más severo y fija la caducidad.',
  respuesta: 'Del veredicto a la regla en el host: feed firmado, réplica en el bastión, agente que verifica la firma y nftables con caducidad.',
  carpetas: 'Dónde vive cada pieza en el repositorio.',
};
const topoCacheOp = {};
function topoV() {
  if (topoVista === 'construccion' || !TOPO_VISTAS[topoVista]) topoVista = 'completa';
  const base = TOPO_VISTAS[topoVista];
  const clave = topoVista + '|' + topoModo;
  if (topoCacheOp[clave]) return topoCacheOp[clave];
  const fuera = new Set(TOPO_SIEMPRE_OCULTOS);
  if (topoModo === 'operativa') (TOPO_OP_OCULTOS[topoVista] || []).forEach(id => fuera.add(id));
  let nodos = base.nodos.filter(n => !fuera.has(n.id));
  let aristas = base.aristas.filter(e => !fuera.has(e.desde) && !fuera.has(e.hasta));
  let grupos = base.grupos, packet = base.packet;
  const ent = topoModo === 'operativa' && TOPO_OP_ENTRANTE[topoVista];
  if (ent) {
    nodos = [ent.nodo].concat(nodos);
    aristas = [ent.arista].concat(aristas);
    grupos = grupos.map((g, i) => i === 0 ? Object.assign({}, g, { txt: ent.grupo }) : g);
    if (ent.packet) packet = ent.packet;
  }
  return (topoCacheOp[clave] = Object.assign({}, base, { nodos, aristas, grupos, packet }));
}
function pintarTopoModo() {
  document.querySelectorAll('#topoModo button').forEach(b => b.classList.toggle('active', b.dataset.modo === topoModo));
  const l = document.getElementById('topoLede');
  if (l) l.textContent = (TOPO_LEDE[topoVista] || '') + (!TOPO_OP_OCULTOS[topoVista] ? ''
    : topoModo === 'operativa' ? ' Vista operativa: solo el flujo que existiría en una red real.'
    : ' Vista lab: incluye lo montado para el ensayo (Kali, clientes, réplica y comparador).') + ' Pulsa un componente para ver su detalle.';
}
// Ultimo estado de /api/aprendizaje (lo llena cargarAprendizaje). Los nodos del
// aprendizaje en la topologia lo leen; con var y aqui arriba para que exista
// desde el primer pintado, aunque llegue despues.
var aprEstado = null;
// Mapa de artefactos: los ficheros de cada componente. Se pide solo cuando se
// activa "Ver archivos" -es de admin- y se guarda; los chips abiertos se
// recuerdan entre repintados.
let topoArchivos = false;
let artefactos = null;
const filesAbiertos = new Set();

const TOPO_TEXTO = {
  red: {
    que: 'El tráfico entre VLAN de la entidad. No se toca: CyberFlow solo observa una copia.',
    nota: 'La red enruta a través del router, así que todo el tráfico entre VLAN pasa por el troncal espejado.',
  },
  span: {
    que: 'La sesión de espejo del switch copia el troncal del router hacia el puerto del sensor. Copia, no desvía: el sensor no está en el camino del tráfico.',
    nota: 'Desde el sensor no se puede leer el estado de la sesión: se infiere de que lleguen paquetes. Si deja de llegar tráfico, el problema puede estar aquí y el panel no lo distingue de una red en silencio.',
    cmd: 'monitor session 1 source interface Gi1/0/23 , Gi2/0/23 both\\nmonitor session 1 destination interface Gi2/0/19 encapsulation replicate\\n! Gi1/0/23 y Gi2/0/23: troncales del router A/B\\n! Gi2/0/19: hacia el hipervisor del sensor (172.17.25.2)\\n! encapsulation replicate: conserva la etiqueta 802.1Q -> el sensor ve la VLAN',
  },
  d_excluida: {
    que: 'Una IP declarada fuera de alcance (por ejemplo, infraestructura propia): sus ventanas se cuentan, pero el motor no las puntúa ni decide sobre ellas.',
    nota: 'No confundir con «No se puntúa» de la vista Operacional, que suma además el latido de los routers y las copias dobles del espejo.',
  },
  entrante: {
    que: 'Todo lo que cruza el troncal espejado: usuarios, servicios y, quizá, un atacante. En una red real nadie lo etiqueta de antemano: el sensor solo ve tráfico y decide, ventana a ventana, si es normal (PERMIT) o anómalo (LIMIT o BLOCK).',
    nota: 'En la vista lab este nodo se separa en la Kali (ataques del ensayo) y los clientes (tráfico legítimo generado): allí sí se sabe cuál es cuál, y eso es lo que permite medir aciertos y falsos positivos.',
  },
  atacante: {
    que: 'La VM Kali (10.10.20.30, VLAN 20). Lanza los ataques del ensayo con herramientas estándar de pentesting; cada familia mueve variables distintas que el sensor ve por el espejo. El panel solo MUESTRA estos comandos (sección Simulación); nunca los ejecuta.',
    flujoTit: 'Herramientas · qué familia lanza cada una',
    flujo: [
      {paso: 'Escaneo de puertos', fichero: 'nmap -sT -sV -T4 -p- --open', garantia: 'barrido TCP a muchos puertos; mueve flow_attempt y unique_dst_port → BLOCK'},
      {paso: 'Fuerza bruta / flood HTTP', fichero: 'curl en 20 hilos a /login (~16 000 POST/2 min)', garantia: 'http_request_rate alto y fallo de auth → BLOCK; sin fallo de auth → LIMIT'},
      {paso: 'Vulnerabilidades web', fichero: 'nikto -h http://10.10.30.10 (tiene firma)', garantia: 'cientos de rutas y 404 en ráfaga; http_request_rate y http_error_ratio'},
      {paso: 'DNS de alta entropía', fichero: 'consultas tipo DGA / NXDOMAIN', garantia: 'nombres únicos y NXDOMAIN altos → LIMIT (hueco donde el modelo saca 0 %)'},
      {paso: 'ARP spoofing (capa 2)', fichero: 'arpspoof -t cliente gateway', garantia: 'unique_src_mac sube; NO lo detecta el modelo global: declarado como trabajo futuro'},
    ],
    nota: 'Fuera de la fase de ataque debe estar APAGADA: si emite durante la línea base, el modelo aprendería el ataque como normal. Por eso sus ventanas se excluyen con excluir_ventanas y el saneamiento del lote.',
  },
  clientes: {
    que: 'Una VM con seis alias .21-.26, cada uno un perfil de tráfico legítimo contra el servidor. Así la línea base tiene variedad realista, no un único patrón. Lo genera un script propio (clientes_lab.py) orquestado por systemd; el servidor de pruebas (servidor_lab.py) responde con los endpoints que alimentan cada variable.',
    perfiles: [
      { icono: 'ofimatica',  n: 'Ofimática',  ip: '.21', d: 'ráfagas cortas de peticiones pequeñas',
        ej: 'cada ~3 s: GET / o /estatico/8k, DNS de intranet.francos-sac.com y algún /api/ok' },
      { icono: 'navegacion', n: 'Navegación', ip: '.22', d: 'muchas conexiones a destinos variados',
        ej: 'cada ~1,5 s: GET /estatico/256k por HTTP y HTTPS, DNS a wiki/erp/correo, a veces abandona una descarga' },
      { icono: 'descargas',  n: 'Descargas',  ip: '.23', d: 'flujos largos, volumen sostenido',
        ej: 'cada ~8 s baja GET /estatico/1M: pocas conexiones, flujos largos' },
      { icono: 'aplicacion', n: 'Aplicación', ip: '.24', d: 'API/HTTP regular, tamaños homogéneos',
        ej: 'cada ~2 s: GET /api/ok y POST /api/enviar; de vez en cuando /api/lento o un 500' },
      { icono: 'ligero',     n: 'Ligero',     ip: '.25', d: 'poco tráfico, intervalos amplios',
        ej: 'cada ~12 s: una consulta DNS, un /api/ok pequeño o un ping' },
      { icono: 'erratico',   n: 'Errático',   ip: '.26', d: 'irregular, sin patrón fijo',
        ej: 'ráfagas y silencios: mezcla peticiones pequeñas y grandes, pings, abandona conexiones y a veces toca un puerto cerrado' },
    ],
    flujoTit: 'Cómo se genera el tráfico',
    flujo: [
      {paso: 'Herramienta', fichero: 'clientes_lab.py + servidor_lab.py', garantia: 'scripts propios en Python (stdlib, sin dependencias): el cliente hace peticiones reales HTTP/HTTPS/DNS/API/ICMP y el servidor responde con endpoints que alimentan variables concretas (p. ej. /api/auth→401, /api/fallo→500, /estatico/<n>k→tamaño de paquete)'},
      {paso: 'Orquestador', fichero: 'systemd · cyberflow-lab.target', garantia: '6 servicios, uno por IP .21-.26, con Restart=always; se arrancan y paran todos con el target. Las unidades las genera clientes_config.py'},
      {paso: 'Decisión por acción', fichero: 'random.choices(acciones, pesos)', garantia: 'elige una acción al azar PONDERADA por su peso (los números de cada perfil) y espera un tiempo aleatorio (distribución exponencial) alrededor del ritmo → parece humano, no periódico'},
      {paso: 'Horario', fichero: 'factor_horario()', garantia: 'curva diaria (las VMs corren en UTC): 08-13 h plena carga (1.0) · comida 0,55 · tarde 0,9 · noche 0,35 · madrugada 0,12 · fin de semana ×0,3'},
    ],
    nota: 'Seis IP sobre una sola MAC, a propósito: el motor puntúa por IP, así que son seis entidades distintas para el modelo. Código: scripts/laboratorio/clientes_lab.py (perfiles, acciones y horarios en factor_horario), servidor_lab.py (el servidor) y clientes_config.py (orquestador systemd).',
  },
  servidor: {
    que: 'El host protegido (srv-dmz, 10.10.30.10, VLAN 30 DMZ): servidor HTTP/HTTPS objetivo del ensayo y donde se APLICA la respuesta. Escucha 80 y 443 (web) y 22 (SSH). Corre el agente que trae el feed firmado y sincroniza nftables en su propio kernel.',
    flujoTit: 'Qué corre en el host y cómo bloquea',
    flujo: [
      {paso: 'Servicio web (servidor_lab.py)', fichero: 'HTTP 80 · HTTPS 443', garantia: 'objetivo del tráfico legítimo y de los ataques. Sirve /estatico/<n>k (tamaños) y /api/* — ok, auth→401, perdido→404, fallo→500, lento: cada endpoint alimenta una variable concreta'},
      {paso: 'Agente de enforcement v2', fichero: 'ppi-enforce-agent-v2-dmz.service (ciclo 10 s)', garantia: 'trae el feed del relay, verifica la firma ed25519 y sincroniza nftables a través de cf-nft-helper (único comando con sudo). Hoy corre en SOMBRA: registra lo que haría'},
      {paso: 'BLOCK = drop', fichero: 'set bloqueados (con timeout)', garantia: 'ip saddr @bloqueados → drop; caduca solo'},
      {paso: 'LIMIT = rate-limit', fichero: 'set limitados (con timeout)', garantia: 'por origen: más de 100 paquetes/s (ráfaga 100) → drop el exceso. En el DNS (DC1), solo puerto 53: 30/min, ráfaga 18'},
    ],
    cmd: 'table inet cyberflow_dmz {\\n  set bloqueados { type ipv4_addr; flags timeout; counter; }\\n  set limitados  { type ipv4_addr; flags timeout; counter; }\\n  chain entrada {\\n    type filter hook input priority -10; policy accept;\\n    ip saddr @bloqueados counter drop\\n    ip saddr @limitados update @tasa_origen { ip saddr limit rate over 100/second burst 100 packets } counter drop\\n  }\\n}',
    nota: 'Tabla AISLADA (policy accept): solo cae lo que trae el feed; nunca gateways ni DNS. El sudoers del agente solo permite el helper cf-nft-helper, que valida cada orden antes de pasarla a nft. Fail-safe: si la firma no verifica, no toca la tabla. Aparece con pocos paquetes PROPIOS porque el motor atribuye cada flujo a quien lo inicia, no al destino.',
  },
  gateway: {
    que: 'El router de la red: enruta entre VLAN y es la puerta de enlace de cada una. En el laboratorio es un pfSense en alta disponibilidad (par A/B con VIP CARP) (VLAN 20 clientes/Kali · 30 DMZ · 60 sensor · 10 gestión). Todo el tráfico entre VLAN cruza el troncal, que es el que se espeja (SPAN) hacia el sensor.',
    flujoTit: 'Reglas implementadas (lo que el ensayo comprobó)',
    flujo: [
      {paso: 'Atacante → DMZ', fichero: 'VLAN 20 → VLAN 30', garantia: 'HTTPS (443) permitido. En la validación del 14-oct el puerto 80 también estaba ABIERTO E2E (ver nota), lo que permitió validar los ataques HTTP; ICMP bloqueado'},
      {paso: 'Clientes → DMZ', fichero: 'VLAN 20 → VLAN 30', garantia: 'tráfico legítimo a 80/443 para la línea base'},
      {paso: 'Sensor sin salida a Internet', fichero: 'VLAN 60 · egress denegado', garantia: 'propiedad de seguridad: nada de bots externos'},
      {paso: 'Troncal espejado', fichero: 'SPAN del trunk → sensor', garantia: 'el sensor ve una COPIA, no está en línea: observa, no corta'},
    ],
    nota: 'El escaneo de puertos se valida de extremo a extremo porque opera a nivel TCP/flujo, que el sensor observa por el espejo SPAN. En la validación del 14-oct el puerto 80 estaba ABIERTO E2E (Kali→DMZ), así que los ataques HTTP en claro —flood (http_abuse→LIMIT) y fuerza bruta sobre el endpoint de laboratorio (brute_force→BLOCK)— también se validaron de extremo a extremo; sobre 443 Suricata solo ve TLS cifrado. El DNS de alta entropía (DGA) se detecta aunque vaya al resolutor de gestión, no a la DMZ. El router es de SOLO LECTURA para CyberFlow: la respuesta la aplica el agente en el host, no aquí. En el ARP spoofing la IP de la puerta de enlace pasa a verse con dos MAC: esa es la anomalía de capa 2 que mueve unique_src_mac_30s.',
  },
  reentrenamiento: {
    que: 'El modelo envejece: la normalidad cambia con el tiempo. Cada noche el sistema sanea un lote, mide la deriva y, cuando toca, entrena y evalúa un candidato. Desplegarlo lo decide una persona: un modelo que se cambia solo podría aprender un ataque lento como normal.',
    flujoTit: 'Reentrenamiento con aprobación humana (cyberflow_aprendizaje.py)',
    flujo: [
      {paso: '1 · Saneamiento', fichero: 'lotes/lote-AAAAMMDD.csv', garantia: 'fuera las IPs marcadas y lo atípico; lote rechazado si su PSI se dispara'},
      {paso: '2 · Linaje', fichero: 'registro.jsonl', garantia: 'sha256 de cada lote en una cadena: retocar uno la rompe'},
      {paso: '3 · Límite de influencia', fichero: 'candidatos/<id>/', garantia: 'lo nuevo ≤ 30 % del entrenamiento; ninguna IP > 10 %'},
      {paso: '4 · Deriva', fichero: 'deriva.jsonl', garantia: 'medida contra el conjunto de oro, que nunca entra a entrenar'},
      {paso: 'Promoción', fichero: 'promover / revertir', garantia: 'solo si FPR ≤ y detección ≥ el vigente; a mano y con copia'},
    ],
    codigo: {
      archivo: 'scripts/modeling/cyberflow_aprendizaje.py',
      pseudo: [
        'cada noche:',
        '  lote ← sanear (fuera IPs marcadas y atípicos); rechazar si PSI alto',
        '  encadenar sha256 del lote (linaje)',
        '  medir deriva contra el conjunto de oro (nunca entrena)',
        '  si toca: entrenar candidato y evaluar (FPR≤ y detección≥ el vigente)',
        '  promover ← SOLO una persona',
      ],
      editar: 'nano ~/cyberflow/scripts/modeling/cyberflow_aprendizaje.py',
    },
    nota: 'Se entrena cada 30 días o antes si la deriva se sostiene 3 días, y es OBLIGATORIO al cambiar la red (nueva VLAN, Wazuh, AAA). La política vive en la sección [reentrenamiento] del .toml; el estado, en la sección Aprendizaje.',
  },
  nic: {
    que: 'ens37, la NIC de CAPTURA: recibe el espejo SPAN, SIN dirección IP y en modo promiscuo. De AQUÍ salen las DOS fuentes de datos — PCAP (tcpdump) y eve.json (Suricata) — no de dos NIC distintas. La gestión va por otra NIC, ens34.',
    nota: 'Sin dirección a propósito: con una, el sensor sería alcanzable desde el troncal espejado y su propio tráfico entraría en su propia captura. Comprobado en Sensor1: ens37 UP sin IP · tcpdump -i ens37 · Suricata af-packet interface: ens37.',
  },
  ens34: {
    que: 'ens34, la NIC de GESTIÓN (10.10.60.11, VLAN 60): por aquí van el SSH del administrador, el acceso al panel y la publicación del feed firmado hacia el relay del bastión. NO recibe el espejo ni alimenta la captura.',
    nota: 'Separar captura (ens37, sin IP) de gestión (ens34, con IP) evita que el tráfico administrativo del propio sensor entre en su línea base. Son dos NIC de la MISMA máquina con trabajos distintos.',
  },
  gestion: {
    que: 'El plano de gestión del sensor, que sale por ens34: la sesión SSH del administrador, el panel HTTPS y el envío del feed al relay del bastión cada 10 s. Separado del plano de captura (ens37).',
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
    codigo: {
      archivo: 'scripts/engine/motor_decision.py  (+ scripts/features/extract_multilayer_v2.py / _v3.py)',
      pseudo: [
        'cada 10 s:',
        '  tramas ← leer PCAP cerrados del anillo',
        '  tramas ← quitar plano de control y copias del espejo',
        '  por cada trama: atribuir a la IP que inició el flujo',
        '  filas ← ventanear por IP (10/30/60 s) → 28 variables',
      ],
      editar: 'nano ~/cyberflow/scripts/engine/motor_decision.py && sudo systemctl restart ppi-motor',
    },
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
    codigo: {
      archivo: 'scripts/features/extract_multilayer_v2.py',
      pseudo: [
        'leer eve.json (líneas del último tramo de 60 s)',
        'quedarse solo con http · dns · tls',
        'atribuir a la IP de origen (NXDOMAIN → quien preguntó)',
        '→ 11 variables L7 en la fila de esa IP y ventana',
      ],
      editar: 'nano ~/cyberflow/scripts/features/extract_multilayer_v2.py && sudo systemctl restart ppi-motor',
    },
    nota: 'Suricata NO decide aquí: sus alertas por firma no se usan como etiqueta ni como variable. Solo se aprovecha su parseo de protocolos.',
    enlace: { href: '#s-vivo', vtab: 'eve', txt: 'Ver eventos parseados en vivo' },
  },
  modelo: {
    que: 'Isolation Forest limpio ajustado en esta red, con umbral congelado en validación (score_samples < -0,622389, punto operativo α = 0,01).',
    codigo: {
      archivo: 'modelo congelado en artifacts/ · entrenamiento en scripts/modeling/',
      pseudo: [
        'score ← modelo.score_samples(features)',
        'si score < umbral (−0,622389): ALERT → LIMIT',
        'si no: PERMIT',
      ],
      editar: 'no se edita a mano: se reentrena y una persona lo promueve (ver Aprendizaje)',
    },
    nota: 'Calibrado en ESTA red. El modelo que venía del laboratorio, con su umbral, marcaba como anómalo casi todo el tráfico normal de aquí —inservible—; recalibrado con datos propios cumple el objetivo de falsos positivos. No fue solo mover el umbral: cambiaron a la vez el modelo (OCSVM→Isolation Forest), los datos (red propia) y el alcance, y el efecto de cada factor no se aisló. Score por debajo del umbral = anomalía → LIMIT.',
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
    codigo: {
      archivo: 'scripts/engine/heuristicos.py',
      pseudo: [
        'por cada ventana (IP):',
        '  si req_http≥5 y fallo_auth≥80%:          BLOCK (fuerza bruta)',
        '  si intentos≥20 y completadas≤30%:        BLOCK (escaneo)',
        '  si req_http≥100:                          LIMIT (abuso HTTP)',
        '  si dns≥20 y (únicos≥45% o NXDOMAIN≥50%):  LIMIT (DNS)',
      ],
      editar: 'nano ~/cyberflow/scripts/engine/heuristicos.py && sudo systemctl restart ppi-motor',
    },
  },
  control: {
    que: 'Fusiona las dos señales en UNA decisión por entidad y ventana. El motor registra PERMIT o ALERT (score bajo el umbral, o heurístico); la acción la pone la regla: LIMIT (degradar la tasa) para abuso HTTP o DNS, BLOCK (cortar) para fuerza bruta o escaneo. La anomalía del modelo, sola, queda como señal para revisión (política if_senal).',
    flujoTit: 'Cómo se decide la acción',
    flujo: [
      {paso: 'Dos entradas', fichero: 'motor_decision.py', garantia: 'score del modelo (anomalía→LIMIT) + heurístico (confirmado→BLOCK)'},
      {paso: 'Acción más severa', fichero: 'publicar_feed.py', garantia: 'por IP; BLOCK gana a LIMIT y LIMIT a PERMIT'},
      {paso: 'Escalada por reincidencia', fichero: 'escalada.py', garantia: '300→1800→3600 s; nunca ∞ automático'},
      {paso: 'Lista nunca-bloquear', fichero: 'publicar_feed.py', garantia: 'gateways y DNS quedan siempre fuera'},
    ],
    codigo: {
      archivo: 'scripts/engine/motor_decision.py + publicar_feed.py + escalada.py',
      pseudo: [
        'acción ← la más severa entre modelo y heurístico  (BLOCK>LIMIT>PERMIT)',
        'si IP en lista nunca_bloquear: acción ← PERMIT',
        'caducidad ← escalera por reincidencia (300→1800→3600 s)',
      ],
      editar: 'nano ~/cyberflow/scripts/engine/publicar_feed.py',
    },
    nota: 'LIMIT existe por el coste de un falso positivo: ante una anomalía del modelo (que puede equivocarse) es más prudente degradar la tasa que cortar; el BLOCK se reserva para los heurísticos de alta confianza. El sensor DECIDE pero no ejecuta: solo observa por espejo. La acción la aplica el agente en el host, con el feed firmado de por medio.',
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
    codigo: {
      archivo: 'scripts/engine/publicar_feed.py + feed.py',
      pseudo: [
        'cada 10 s:',
        '  entradas ← acciones vigentes por IP (con su caducidad)',
        '  feed.json ← {ip, acción, hasta, motivo}',
        '  firmar feed.json con ed25519 (la clave privada vive solo aquí)',
      ],
      editar: 'nano ~/cyberflow/scripts/engine/publicar_feed.py',
    },
  },
  agente: {
    que: 'Corre en cada host protegido: trae el feed, verifica la firma y sincroniza nftables (LIMIT con rate-limit, BLOCK con drop y timeout).',
    nota: 'Fail-safe: si la firma no verifica, no toca nada. Tabla aislada (policy accept): solo cae lo que trae el feed. Nunca bloquea gateways ni DNS. Demostrado: un BLOCK real cortó a la Kali (http_200 → http_000).',
    flujoTit: 'Cómo actúa en el host',
    flujo: [
      {paso: 'Pull + verifica', fichero: 'agente_enforce.py', garantia: 'firma ed25519; fail-safe si falla'},
      {paso: 'Aplica', fichero: 'nftables', garantia: 'set con timeout nativo → caduca solo'},
    ],
    codigo: {
      archivo: '/opt/cyberflow/agente-v2/agente_enforce_v2.py   (corre en el host protegido)',
      pseudo: [
        'cada 10 s:',
        '  feed ← traer del relay (bastión)',
        '  si la firma ed25519 no verifica: no tocar nada (fail-safe)',
        '  sincronizar nftables: LIMIT=rate-limit, BLOCK=drop con timeout',
      ],
      editar: 'sudo nano /opt/cyberflow/agente-v2/agente_enforce_v2.py && sudo systemctl restart ppi-enforce-agent-v2-dmz   (en srv-dmz)',
    },
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
    que: 'Lo que se captura pero NO se puntúa. Casi todo es el latido del par de routers del laboratorio (CARP y pfsync, varios paquetes por segundo, día y noche); el resto son las copias dobles que el espejo enseña de una misma trama y las IP declaradas fuera de alcance. No es tráfico perdido: es ruido que, si se puntuara, el modelo tomaría por normal o por anómalo sin serlo.',
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
    nota: 'Solo lectura a propósito. Un panel que pudiera desbloquear una IP sería otro camino hacia las reglas de los hosts, y con su propia superficie de ataque.',
  },
  relay: {
    que: 'El bastión copia el feed firmado del sensor a la red interna. Los hosts lo traen de aquí: nunca hablan con el sensor.',
    nota: 'Es uno de los tres temporizadores de 10 s, escalonados en :00/:03/:06 para preservar el orden publicador → relay → agente.',
  },
  // ---- Vista RED Y CAPTURA ----
  r_bastion: {
    que: 'La VM de gestión (10.10.10.30, VLAN 10). Es el BASTIÓN del laboratorio: el único punto de entrada por SSH a todas las máquinas (sensor, servidor, Kali, clientes); guarda las claves SSH de cada host, así que toda la administración pasa por aquí. Además, aquí corre el RELAY del feed de enforcement.',
    flujoTit: 'Qué es el «relay del feed»',
    flujo: [
      {paso: 'Qué es el feed', fichero: 'feed.json + feed.sig', garantia: 'la lista FIRMADA (ed25519) de acciones por IP —PERMIT/LIMIT/BLOCK con caducidad— que publica el sensor'},
      {paso: 'Qué hace el relay', fichero: 'ppi-relay-feed.timer · ciclo 10 s', garantia: 'relay-feed.sh TRAE (pull) el feed del sensor y lo EMPUJA (push) al host protegido'},
      {paso: 'Por qué hace falta', fichero: 'red segmentada por VLAN', garantia: 'el host de la DMZ no habla con el sensor directamente; el bastión alcanza a los dos y hace de puente'},
      {paso: 'Por qué es seguro', fichero: 'relay TONTO', garantia: 'solo copia bytes: la firma la pone el sensor y la verifica el host, así que el bastión no puede forjar ni alterar un bloqueo'},
    ],
    nota: 'Modelo «un feed / N agentes (pull)»: el sensor NO tiene credenciales de los hosts; publica una lista firmada y cada host la trae y la verifica. Por eso el bastión, aunque administre, no es un camino hacia las reglas de los hosts. Está en la lista «nunca bloquear» (como los gateways y el DNS) para que un falso positivo no corte la propia vía de gestión. La VM también expone el panel al exterior por Tailscale (vm-gestion.tail83bf9c.ts.net).',
  },
  r_dns: {
    que: 'El DNS y directorio de la red. Las consultas DNS de las pruebas van contra esta máquina.',
    nota: 'Está en la lista «nunca bloquear»: cortarlo dejaría sin resolver a toda la red.',
  },
  r_pg: {
    que: 'El grupo de puertos del hipervisor que recibe la copia del puerto Gi2/0/19. En modo promiscuo la entrega a toda máquina virtual conectada.',
    nota: 'Por eso un solo puerto destino del espejo alimenta a varios sensores.',
  },
  r_sensor2: {
    que: 'El segundo sensor, instalado desde cero para probar que el sistema se replica. Cuelga del mismo grupo de puertos.',
  },
  r_cmp: {
    que: 'La máquina reservada para comparar con Suricata. Está conectada al grupo de puertos, pero su interfaz de captura estaba apagada.',
    nota: 'La comparación publicada se hizo reproduciendo el mismo PCAP, no con esta máquina en vivo.',
  },
  // ---- Vista CARPETAS: arquitectura del repositorio ----
  cf_root: {
    que: 'La raíz del repositorio de CyberFlow. Todo lo versionado cuelga de aquí: el código, la configuración, los artefactos del modelo, la documentación y las pruebas. Pulsa cada carpeta para ver sus archivos del sistema y en qué host corre cada uno.',
    leyenda: ['sensor', 'servidor', 'bastion'],
    nota: 'Casi todo corre en el Sensor (copia del repo en /home/m4rk/cyberflow). Solo dos piezas viven fuera: el relay en el Bastión y el agente en el Servidor protegido.',
  },
  cf_scripts: {
    que: 'Todo el código, organizado por función: el motor en vivo (engine), los extractores de variables (features), el modelado y el aprendizaje (modeling), el agente del host (enforce) y la instalación (setup).',
  },
  cf_engine: {
    que: 'El motor en vivo y este panel. Todo corre en el Sensor.',
    archivos: [
      { n: 'dashboard.py',      host: 'sensor', d: 'este panel' },
      { n: 'motor_decision.py', host: 'sensor', d: 'decide cada ventana' },
      { n: 'heuristicos.py',    host: 'sensor', d: 'las 4 reglas' },
      { n: 'publicar_feed.py',  host: 'sensor', d: 'publica el feed' },
      { n: 'feed.py',           host: 'sensor', d: 'firma ed25519' },
      { n: 'escalada.py',       host: 'sensor', d: 'caducidad por reincidencia' },
    ],
    codigo: {
      archivo: 'scripts/engine/',
      pseudo: [
        'dashboard.py       — este panel',
        'motor_decision.py  — decide cada ventana',
        'heuristicos.py     — las 4 reglas',
        'publicar_feed.py   — publica el feed',
        'feed.py            — firma ed25519',
        'escalada.py        — caducidad por reincidencia',
      ],
      editar: 'cd ~/cyberflow/scripts/engine',
    },
  },
  cf_features: {
    que: 'Los extractores que convierten PCAP y eve.json en las 28 variables por IP y ventana. Están congelados: sus fórmulas no se tocan. Corren en el Sensor.',
    archivos: [
      { n: 'extract_multilayer_v2.py', host: 'sensor', d: 'ventaneo + variables L7' },
      { n: 'extract_multilayer_v3.py', host: 'sensor', d: 'decodifica cada trama' },
      { n: 'acumular_v3.py',           host: 'sensor', d: 'acumula la línea base' },
    ],
    codigo: {
      archivo: 'scripts/features/',
      pseudo: [
        'extract_multilayer_v2.py — ventaneo + variables L7',
        'extract_multilayer_v3.py — decodifica cada trama',
      ],
      editar: 'cd ~/cyberflow/scripts/features',
    },
  },
  cf_modeling: {
    que: 'El entrenamiento del modelo y el reentrenamiento nocturno con aprobación humana (saneo, deriva, candidato, promoción). Corre en el Sensor.',
    archivos: [
      { n: 'cyberflow_aprendizaje.py', host: 'sensor', d: 'aprendizaje nocturno' },
      { n: 'entrenar_preliminar.py',   host: 'sensor', d: 'entrena y fija el umbral' },
      { n: 'promover_preliminar.py',   host: 'sensor', d: 'promueve el candidato' },
    ],
    codigo: {
      archivo: 'scripts/modeling/cyberflow_aprendizaje.py',
      editar: 'cd ~/cyberflow/scripts/modeling',
    },
  },
  cf_enforce: {
    que: 'El agente que trae el feed, verifica la firma y aplica nftables. NO corre en el sensor: se instala en el Servidor (host protegido, p.ej. srv-dmz).',
    archivos: [
      { n: 'agente_enforce.py', host: 'servidor', d: 'verifica la firma y aplica nftables' },
    ],
    codigo: {
      archivo: 'scripts/enforce/agente_enforce.py',
      editar: '(se instala en el host protegido, p.ej. srv-dmz)',
    },
  },
  cf_setup: {
    que: 'La instalación: genera las unidades systemd y la configuración del sensor a partir del .toml. Corre en el Sensor.',
    archivos: [
      { n: 'cyberflow_config.py', host: 'sensor', d: 'genera las unidades systemd' },
    ],
  },
  cf_configs: {
    que: 'La configuración. El .toml manda: de ahí salen las unidades y el alcance. También el esquema de variables y las reglas de Suricata. Vive en el Sensor.',
    archivos: [
      { n: 'cyberflow.local.toml', host: 'sensor', d: 'config de esta red' },
      { n: 'features/*.json',      host: 'sensor', d: 'esquema de las 28 variables' },
      { n: 'suricata/*',           host: 'sensor', d: 'reglas de Suricata' },
    ],
    codigo: {
      archivo: 'configs/',
      pseudo: [
        'cyberflow.local.toml — configuración de ESTA red',
        'features/            — esquema de las 28 variables',
        'suricata/            — reglas de Suricata',
      ],
      editar: 'nano ~/cyberflow/configs/cyberflow.local.toml',
    },
  },
  cf_artifacts: {
    que: 'Lo que no es código: el modelo congelado (pipeline + manifiesto con su hash), la línea base y los lotes del aprendizaje. Están en el Sensor.',
    archivos: [
      { n: 'if_limpio_2026_10_*.joblib', host: 'sensor', d: 'modelo congelado' },
      { n: 'manifest-*.json',         host: 'sensor', d: 'umbral + orden + hash' },
      { n: 'linea-base/*.csv',        host: 'sensor', d: 'dataset acumulado' },
    ],
  },
  cf_docs: {
    que: 'La documentación: la evaluación del modelo vigente, las evidencias de las mediciones (tiempos, bloqueos en vivo) y las imágenes.',
  },
  cf_tests: {
    que: 'La batería de pruebas (unittest): la regla de acción, los contadores, la salud del panel, los drops, el historial y más.',
    codigo: {
      archivo: 'tests/',
      editar: '~/cf-venv/bin/python -m unittest discover -s tests',
    },
  },
  cf_deploy: {
    que: 'La instalación reproducible: scripts de despliegue y playbooks de Ansible. Es la única carpeta con piezas que corren FUERA del sensor: el relay en el Bastión y la unidad del agente en el Servidor.',
    archivos: [
      { n: 'instalar / desplegar',       host: 'sensor',   d: 'levanta el sensor desde cero' },
      { n: 'relay-feed.sh',              host: 'bastion',  d: 'copia el feed firmado a los hosts' },
      { n: 'ppi-enforce-agent-v2-dmz (unidad)', host: 'servidor', d: 'servicio del agente v2, ciclo 10 s' },
    ],
  },
  cf_mas: {
    que: 'Otras carpetas de scripts: dataset (construir el conjunto), evaluacion (comparar con Suricata), campaign (campañas de ataque), analysis, kali, f1/f6, articulo y entregables.',
  },
  // ---- Vista DECISION ----
  d_alert: {
    que: 'Una ventana con paquetes cuyo score queda por debajo del umbral. Con la política vigente (if_senal) el modelo solo es señal: marca la ventana para revisión y confirma la regla, pero por sí solo no publica medida.',
    nota: 'Sin paquetes en la ventana el modelo no puntúa, para no alertar por silencio de red.',
  },
  d_reglas: {
    que: 'Cuatro reglas versionadas. Fuerza bruta y escaneo de puertos piden BLOCK; abuso HTTP y DNS de alta entropía piden LIMIT.',
    nota: 'Sus umbrales son criterio razonado, no calibración estadística como el umbral del modelo.',
  },
  d_nunca: {
    que: 'Antes de combinar, el publicador descarta la infraestructura: bastión, sensor, gateways y DNS.',
    nota: 'Pase lo que pase en el motor, esas direcciones no llegan al feed.',
  },
  d_severa: {
    que: 'Por cada IP se queda con el veredicto más severo de los últimos 120 s: BLOCK gana a LIMIT.',
  },
  d_escalera: {
    que: 'La caducidad crece con la reincidencia en 24 h: 300 s, luego 1800 s, luego 3600 s. LIMIT es siempre 300 s.',
    nota: 'Desde el tercer BLOCK la entrada queda marcada para revisión humana. Nunca hay bloqueo automático indefinido.',
  },
  d_permit: {
    que: 'Sin señal del modelo ni de las reglas, la IP no entra al feed y no se le aplica nada.',
  },
  d_limit: {
    que: 'Limitación de tasa durante 300 s. Degrada sin cortar: es la respuesta cuando la señal es ambigua.',
  },
  d_block: {
    que: 'Corte del tráfico de esa IP hacia el host, con caducidad de 300, 1800 o 3600 s según la reincidencia.',
    nota: 'Desde el tercer bloqueo, revisión humana.',
  },
  // ---- Vista RESPUESTA ----
  p_nft: {
    que: 'La regla ya aplicada en el núcleo del host protegido. Es el final del tiempo de respuesta.',
    nota: 'En la Campaña B, de la señal a la medida aplicada pasaron unos 1,3 s, casi constantes; los escaneos quedaron bloqueados en 1,4–1,9 s de mediana desde el inicio. Históricamente, con temporizadores de 60 s, eran 51 a 141 s.',
  },
  p_noaplica: {
    que: 'Si la firma del feed no verifica, el agente no toca nada.',
    nota: 'Lo que ya estaba aplicado no se borra: caduca a su hora.',
  },
  p_caduca: {
    que: 'Cada entrada vive en un conjunto de nftables con caducidad propia. Al vencer, el núcleo la retira solo.',
  },
  p_manual: {
    que: 'Una persona puede retirar una entrada antes de que caduque.',
    cmd: 'nft delete element inet <tabla> <conjunto> { <ip> }',
    nota: 'El panel no lo hace: es de solo lectura a propósito.',
  },
  // ---- Vista METODOLOGICA (como se construyo) ----
  m_datos: {
    que: 'F1 · Línea base propia. Se capturó el tráfico REAL de esta red por espejo SPAN del troncal —no un dataset público ni simulado—, de dos fuentes de la misma copia: PCAP de capas 3/4 (tcpdump) y eventos de capa 7 de Suricata (eve.json). De ahí salen las 335 202 ventanas normales que definen «lo normal» de ESTA red. El modelo que venía del laboratorio marcaba como anómalo casi todo el tráfico normal de aquí, así que la línea base y la calibración se rehacen con datos propios.',
    nota: 'Datos reales, no simulados: aborda el salto simulación→realidad, poco frecuente en los trabajos revisados. El dataset y su hoja de datos se publican.',
  },
  m_feat: {
    que: 'F2 · 28 variables multicapa. Un extractor CONGELADO convierte cada ventana (10/30/60 s) en 28 variables por IP iniciadora: de red (L3), de transporte (L4) y de aplicación (L7, derivadas de Suricata). Atribuye cada paquete a quien inició el flujo, deduplica la copia del espejo y NO imputa: una ausencia es un cero estructural (no hubo DNS en esa ventana), no un dato inventado. Sus fórmulas no se tocan, para que la misma ventana dé siempre el mismo vector.',
    nota: 'La limpieza acota la ENTRADA (deduplicar el espejo, quitar plano de control), nunca las fórmulas. 27 de 28 variables muestran variación observable.',
  },
  m_modelo: {
    que: 'F3 · Detector híbrido: IF limpio con θ=−0,622389 (α = 0,01) y cuatro heurísticos (fuerza bruta, escaneo, abuso HTTP y DNS inusual). La evaluación offline del IF no es la evaluación del híbrido. La campaña del modelo limpio tiene resultados parciales; falta una batería completa y consistente.',
    nota: 'El modelo se elige comparando 7 candidatos, no a ciegas; el umbral se calibra en validación con objetivo de falsos positivos y se CONGELA antes de mirar el test.',
  },
  m_eval: {
    que: 'F4 · Evaluación justa (replay). Se reproduce el MISMO PCAP contra CyberFlow y contra Suricata, anclando cada decisión al reloj del paquete (no al de proceso), para que la comparación sea honesta. Sobre tráfico sin firma CyberFlow detecta 9 de 9 familias y Suricata 0 de 9. Hecho con N=3 corridas por familia; queda pendiente la campaña C3 (N=5, con fuerza bruta y tráfico legítimo intenso, midiendo también los falsos positivos de Suricata).',
    nota: 'Complementario a Suricata, no su reemplazo: él bloquea lo que tiene firma; CyberFlow detecta lo que no la tiene. El «parcial» es por C3, no por un resultado dudoso.',
  },
  m_resp: {
    que: 'F5 (aporte) · Respuesta graduada. La decisión se convierte en ACCIÓN, no solo en alerta: PERMIT, LIMIT (degradar la tasa, reversible) o BLOCK (cortar). El sensor publica un feed FIRMADO (ed25519); cada host lo trae, verifica la firma y aplica nftables en su propio kernel. La caducidad escala por reincidencia (300→1800→3600 s) y nunca es permanente de forma automática.',
    nota: 'Actuar, no solo detectar: una respuesta automática poco frecuente en los trabajos revisados. El sensor DECIDE pero no ejecuta: observa por espejo y la acción la aplica el agente en el host.',
  },
  m_desp: {
    que: 'F6 (aporte) · Desplegado de verdad. Corre sobre el sensor con systemd (servicios y temporizadores), con instalación reproducible y SIN salida a Internet (ruedas locales), y se verificó levantando un segundo sensor. 58 corridas sin caídas.',
    nota: 'Ninguno de los 15 artículos revisados despliega su sistema en operación real. La instalación y la replicación están documentadas (INSTALACION.md, REPLICACION.md).',
  },
  m_valid: {
    que: 'F7 (aporte) · Validación en dos planos. INTERNA: demo técnica en vivo, grabada (ataque → detección → respuesta → panel), sin instrumento. EXTERNA: aceptación con el modelo TAM y juicio de expertos (fiabilidad con alfa de Cronbach, validez de contenido con V de Aiken). En curso: por eso la fase está «en curso», no cerrada.',
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
      {paso: 'Solo normal (con exclusiones)', fichero: 'Kali apagada en la base', garantia: 'la intención es solo tráfico normal; la contaminación de la Kali que sí quedó documentada (nota S) se excluye por excluir_ventanas y el saneamiento del lote'},
    ],
    nota: 'Total usado para el IF vigente: 335 202 ventanas normales (204 148 + 65 633 + 65 421). Sin ataques: los de la Kali se reservaron para medir detección después.',
  },
  c_limpia: {
    que: 'Limpieza = acotar la ENTRADA, no tocar fórmulas. Se quitan el plano de control del router (CARP 112, pfsync 240), la segunda copia de cada trama que el espejo enseña dos veces y las entidades declaradas fuera de alcance.',
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
      {paso: 'FPR validación', fichero: 'ensayo-if-v2.json', garantia: '1,00 % (por construcción: α = 0,01)'},
      {paso: 'FPR prueba', fichero: 'Tabla 6 (4.1)', garantia: '0,87 % sobre 65 421 ventanas normales; IF offline'},
      {paso: 'Detección Kali', fichero: 'nota M', garantia: '50/84 = 59,5 % global'},
    ],
    nota: 'El corte usa validación con α=0,01. El 0,87 % es del IF offline, no del híbrido; evaluación reutilizada, no test ciego independiente.',
  },
  c_sel: {
    que: 'El OCSVM del laboratorio marca 99,57 % del tráfico normal como anómalo. El IF limpio obtiene FPR 0,87 % y recall 50/84, precisión 8,10 % (α = 0,01). Se mide transferencia a esta red; no superioridad intrínseca ni cumplimiento de una meta de aceptación independiente.',
    nota: 'La ablación 6/9, 7/9 y 9/9 es histórica del predecesor. El modelo limpio requiere su campaña final; no trasladar esas coberturas.',
    enlace: { href: '#s-modelo', txt: 'Ver «Pruebas previas» y la ablación' },
  },
  c_cong: {
    que: 'Pipeline con escalador e IF; percentil α=0,01 en validación: score_samples < −0,622389 (decision_function < −0,122389). No se reajusta durante la evaluación.',
    flujoTit: 'Qué queda fijo',
    flujo: [
      {paso: 'Pipeline', fichero: 'if_limpio_2026_10_desplegable.joblib', garantia: 'sha256 df547da0…fd60'},
      {paso: 'Umbral + orden de variables', fichero: 'manifest-if-limpio-2026-10.json', garantia: 'el motor rechaza un orden distinto al del extractor'},
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
    que: 'Acumulación: mientras el motor opera, un temporizador escribe cada 10 min filas de línea base (v3) con la misma cadena del motor. Es la materia prima del aprendizaje.',
    nota: 'Las filas acumuladas no entran tal cual a entrenar: cada noche pasan por el saneamiento (fila 3), que retira lo marcado y lo atípico.',
  },
  c_vivo: {
    que: 'Motor en vivo: puntúa cada IP cada 10 s y decide PERMIT o ALERT (LIMIT/BLOCK). Para el aprendizaje, cada IP que marca queda señalada: sus ventanas de ese momento no entrarán al entrenamiento.',
    nota: 'Es la primera defensa contra el envenenamiento: lo que el sistema ya consideró sospechoso nunca se aprende como normal.',
  },
  a_oro: {
    que: 'Conjunto de ORO: las ventanas normales de la partición de prueba de la calibración (nota L), congeladas en solo lectura con su sha256. Nunca entran a entrenar: son la referencia fija contra la que se mide la deriva y se comparan vigente y candidato.',
    flujoTit: 'De dónde sale',
    flujo: [
      {paso: 'Partición de la nota L', fichero: 'particionado-nota-L.csv', garantia: 'reconstruida y verificada: mismo sha256 que el del modelo desplegado'},
      {paso: 'Solo el test', fichero: 'oro/oro.csv', garantia: '65 421 ventanas · modo 0444'},
      {paso: 'Huella', fichero: 'oro/oro.json', garantia: 'si el oro cambia, el aprendizaje se detiene'},
    ],
    nota: 'Si la red cambia de verdad (nueva VLAN, Wazuh, AAA) el oro deja de representarla: entonces se recalibra entera y se crea un oro nuevo.',
  },
  a_san: {
    que: '① Saneamiento: cada noche se cierra el lote del día anterior y se filtra antes de que pueda entrenar.',
    flujoTit: 'Cuatro filtros',
    flujo: [
      {paso: 'Ventanas excluidas', fichero: 'excluir_ventanas', garantia: 'fuera los tramos declarados, como la ráfaga de la Kali del 27-sep'},
      {paso: 'Contaminación', fichero: 'motor_decision.log + eve.json', garantia: 'fuera las ventanas de IPs marcadas a ±5 min'},
      {paso: 'Atípicas', fichero: 'límites del oro', garantia: 'fuera la fila que se sale en 3 o más variables'},
      {paso: 'Lote anómalo', fichero: 'PSI frente al oro', garantia: 'PSI > 0,5: lote rechazado, lo revisa una persona'},
    ],
    nota: 'Un lote rechazado puede ser un cambio de red legítimo; se acepta a mano con «lote --dia … --aceptar» tras revisarlo. Caso real: el lote del 10-oct se rechazó con PSI 2,41, porque la red no tenía tráfico de usuarios.',
  },
  a_lin: {
    que: '② Linaje: cada lote queda registrado con su sha256, su origen y lo que se filtró, en un registro encadenado (cada línea lleva el hash de la anterior).',
    nota: 'Borrar o retocar un lote rompe la cadena: «verificar» lo detecta, doctor.sh lo marca en rojo y el candidato se niega a entrenar.',
  },
  a_der: {
    que: '④ Deriva: cada noche el modelo vigente se mide contra el oro (FPR) y contra el lote del día (PSI de sus puntuaciones y % que marcaría anómalo).',
    nota: 'Si la señal se sostiene 3 días, toca reentrenar antes de la cadencia de 30 días. La deriva solo adelanta el reentrenamiento: nunca cambia el modelo por sí sola.',
  },
  a_inf: {
    que: '③ Candidato con límite de influencia: se suman los lotes aceptados a la base de la calibración, con topes, y se repite la misma cadena (partición sin fuga → entrenar → umbral en validación → Pipeline + manifiesto).',
    flujoTit: 'Topes',
    flujo: [
      {paso: 'Fracción nueva', fichero: 'max_fraccion_nueva', garantia: 'lo nuevo ≤ 30 % del entrenamiento'},
      {paso: 'Por IP', fichero: 'max_fraccion_ip', garantia: 'ninguna IP > 10 % de lo nuevo'},
      {paso: 'Nunca el oro', fichero: 'claves (IP, ventana)', garantia: 'sus filas se excluyen del entrenamiento'},
    ],
    nota: 'Un equipo que inunda la red no puede mover el modelo. El candidato se escribe en candidatos/<id>/ y no toca el modelo en uso.',
  },
  a_ver: {
    que: 'Veredicto: vigente y candidato se puntúan sobre los MISMOS conjuntos (oro para el FPR, ataques etiquetados para la detección).',
    flujoTit: 'Tres resultados',
    flujo: [
      {paso: 'PROMOVIBLE', fichero: 'candidato.json', garantia: 'FPR ≤ vigente y detección ≥ vigente'},
      {paso: 'NO_PROMOVER', fichero: 'candidato.json', garantia: 'empeora una de las dos: se queda el vigente'},
      {paso: 'EVALUACION_INCOMPLETA', fichero: 'candidato.json', garantia: 'sin ataques etiquetados no se sabe si detecta igual'},
    ],
  },
  a_hum: {
    que: 'Aprobación humana: el modelo en uso solo cambia con «promover», que lanza una persona. Deja copia del .toml y apunta motor y panel al candidato; «revertir» lo deshace. Se conservan 3 modelos de respaldo.',
    nota: 'Por qué no es automático: un modelo que se despliega solo puede aprender un ataque lento como normal. Todo lo automático ocurre fuera del modelo en uso.',
  },
};

let topoSel = 'motor';
let topoUltimo = null;

// Declarada AQUI, no junto al resto del codigo de la seccion "Variables": la
// lee topoEstado(), y refresh() corre antes que aquel bloque. Un `let` leido
// antes de su declaracion lanza ReferenceError -zona muerta temporal- y se
// llevaba por delante el primer pintado entero del panel.
let varDatos = null;

// pcaps_ilegibles es un ACUMULADO desde que arranco el motor, no el estado de
// ahora. El caso conocido -tcpdump -Z deja el primer fichero de cada arranque a
// tcpdump:tcpdump y el motor no puede leerlo- da PermissionError una sola vez
// y deja el contador en 1 hasta el siguiente reinicio del motor: es ambar, no
// rojo. Cualquier otro motivo, o mas de uno, si es rojo.
function ilegiblesEstado(al) {
  const ile = al.pcaps_ilegibles;
  if (ile == null) return { estado: '', valor: 'sin medir', datos: { 'Ficheros ilegibles': 'sin medir' } };
  if (!ile) return { estado: 'ok', valor: 'anillo íntegro', datos: { 'Ficheros ilegibles': '0' } };
  const motivos = al.pcaps_ilegibles_motivo || {};
  const tipos = Object.keys(motivos);
  const conocido = ile === 1 && tipos.length === 1 && tipos[0] === 'PermissionError';
  const datos = { 'Ficheros ilegibles (acumulado desde que arrancó el motor)': String(ile) };
  tipos.forEach(t => { datos['Motivo ' + t] = motivos[t]; });
  if (conocido) datos['Lectura'] = 'primer fichero tras arrancar tcpdump (-Z lo deja a tcpdump:tcpdump); el resto del anillo se lee';
  return { estado: conocido ? 'warn' : 'bad',
           valor: conocido ? 'anillo legible · 1 histórico' : ile + ' ficheros ilegibles', datos: datos };
}

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
      const il = ilegiblesEstado(al);
      return {
        estado: !on ? 'bad' : il.estado,
        valor: !on ? 'inactivo' : il.valor,
        datos: Object.assign({ 'Servicio': on ? 'activo' : 'inactivo' }, il.datos),
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
      const il = ilegiblesEstado(al);
      return { estado: il.estado, valor: il.valor, datos: il.datos };
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
    case 'a_oro': case 'a_san': case 'a_lin': case 'a_der': case 'a_inf': case 'a_ver': case 'a_hum': {
      const e = aprEstado;
      if (!e || !e.disponible) return { estado: '', valor: 'aún sin datos', datos: {
        'Qué significa': 'el aprendizaje nocturno (00:30 UTC) todavía no ha dejado registro; es lo esperado hasta su primera corrida, NO un fallo',
        'Para verlo': 'abre la vista «Aprendizaje» o define la sección [reentrenamiento] del .toml' } };
      const p = e.politica, lotes = e.lotes || [], der = (e.deriva || []).filter(d => d.fpr_oro !== undefined);
      const ul = lotes.length ? lotes[lotes.length - 1] : null, ud = der.length ? der[der.length - 1] : null;
      const uc = e.candidatos.length ? e.candidatos[e.candidatos.length - 1] : null;
      const act = p.activo ? 'activo' : 'desactivado';
      const pct = (v) => (v === null || v === undefined) ? '—' : (v * 100).toFixed(2) + ' %';
      if (id === 'reentrenamiento') return { estado: p.activo ? 'ok' : 'warn', valor: act, datos: Object.assign({
        'Modo': p.modo, 'Cadencia': p.cadencia_dias + ' días o deriva ' + p.dias_deriva + ' días',
        'Lotes sin usar': String(e.lotes_disponibles), 'Último candidato': uc ? uc.id + ' · ' + uc.veredicto : 'ninguno' },
        p.activo ? {} : { 'Por qué en ámbar': 'está desactivado a propósito; aun así el modelo vigente sigue decidiendo igual. Se activa en [reentrenamiento] del .toml' }) };
      if (id === 'a_oro') return e.oro
        ? { estado: 'ok', valor: e.oro.filas + ' ventanas', datos: { 'sha256': e.oro.sha256.slice(0, 16) + '…', 'Creado': String(e.oro.generado).slice(0, 10) } }
        : { estado: 'warn', valor: 'no creado', datos: { 'Crear': 'cyberflow_aprendizaje.py oro --desde <particionado>' } };
      if (id === 'a_san') return ul
        ? { estado: ul.estado === 'aceptado' ? 'ok' : (ul.estado === 'rechazado' ? 'bad' : 'warn'), valor: ul.estado, datos: {
            'Lote': ul.dia, 'Filas': ul.filas.entrada + ' → ' + ul.filas.salida,
            'De IPs marcadas': String(ul.filas.contaminadas), 'Atípicas': String(ul.filas.atipicas), 'PSI máx': ul.psi_max === null ? '—' : String(ul.psi_max) } }
        : { estado: p.activo ? '' : 'warn', valor: p.activo ? 'primer lote a las 00:30 UTC' : act, datos: {} };
      if (id === 'a_lin') return { estado: e.registro_integro ? 'ok' : 'bad', valor: e.registro_integro ? 'íntegro' : 'ROTO', datos: {
        'Lotes registrados': String(lotes.length), 'Sin usar': String(e.lotes_disponibles) } };
      if (id === 'a_der') return ud
        ? { estado: e.deriva_sostenida ? 'bad' : (ud.senal ? 'warn' : 'ok'), valor: e.deriva_sostenida ? 'sostenida' : (ud.senal ? 'señal' : 'estable'), datos: {
            'Día': ud.dia, 'FPR en oro': pct(ud.fpr_oro), 'Anómalo en el lote': pct(ud.tasa_anomala_lote) } }
        : { estado: '', valor: 'sin medir', datos: {} };
      if (id === 'a_inf') return { estado: '', valor: Math.round(p.max_fraccion_nueva * 100) + ' % / ' + Math.round(p.max_fraccion_ip * 100) + ' %', datos: {
        'Último': uc && uc.filas ? pct(uc.filas.fraccion_nueva) + ' de filas nuevas' : 'sin candidatos', 'Próximo': e.proximo || 'por cadencia o deriva' } };
      if (id === 'a_ver') return uc
        ? { estado: uc.veredicto === 'PROMOVIBLE' ? 'ok' : (uc.veredicto === 'NO_PROMOVER' ? 'bad' : 'warn'), valor: uc.veredicto, datos: {
            'FPR oro (vigente → candidato)': pct((uc.resultados.vigente || {}).fpr_oro) + ' → ' + pct((uc.resultados.candidato || {}).fpr_oro),
            'Detección': pct((uc.resultados.vigente || {}).deteccion) + ' → ' + pct((uc.resultados.candidato || {}).deteccion) } }
        : { estado: '', valor: 'sin candidatos', datos: {} };
      const h = e.historial || [];
      return { estado: '', valor: h.length ? h[h.length - 1].accion + ' ' + h[h.length - 1].candidato : 'sin promociones', datos: {
        'Detector vigente': e.detector_vigente } };
    }
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
  pintarTopoModo();
  const v = topoV();
  const svg = document.getElementById('topo');
  const tabla = document.getElementById('topoTabla');
  if (v.tabla) {
    svg.style.display = 'none';
    tabla.style.display = 'block';
    tabla.innerHTML = validacionHTML();
    document.getElementById('topoDetail').innerHTML = validacionDetalleHTML();
    return;
  }
  svg.style.display = '';
  tabla.style.display = 'none';
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
  const PUNTA = ' marker-end="url(#topoPunta)"';
  // G3: el flujo de la IP seguida (solo en la vista Operacional, la que tiene
  // origen, sensor y agente en un mismo dibujo).
  let fl = null;
  try { fl = topoVista === 'completa' ? flujoActual() : null; } catch (e) { fl = null; }
  const flSet = fl ? new Set(flujoNodos(fl)) : null;
  const aristas = v.aristas.map(e => {
    const label = e.etiqueta
      ? `<text class="topo-edge-label" x="${e.ex}" y="${e.ey}" text-anchor="middle">${e.etiqueta}</text>` : '';
    if (flSet && flSet.has(e.desde) && flSet.has(e.hasta) && e.tipo !== 'descarte' && e.tipo !== 'previsto') {
      return `<path class="topo-edge flujo" d="${e.d}"${PUNTA}/>` + label;
    }
    // Con tipo, el conector dice su naturaleza (copia, previsto, persona...) y
    // no depende del estado vivo. Un enlace fisico no lleva punta.
    if (e.tipo) {
      return `<path class="topo-edge ${e.tipo}" d="${e.d}"${e.tipo === 'enlace' ? '' : PUNTA}/>` + label;
    }
    const vivo = est[e.desde].estado !== 'bad' && est[e.hasta].estado !== 'bad'
                 && est[e.desde].estado !== '';
    return `<path class="topo-edge ${vivo ? 'live' : 'dim'}" d="${e.d}"${PUNTA}/>` + label;
  }).join('');

  // Sobres (paquetes de datos) que recorren la tuberia en bucle: hacen visible que el dato
  // fluye. Una vista puede tener varios (v.packets) para mostrar ramas que se unifican, o uno
  // solo (v.packet). Cada sobre lleva una ficha doblada dentro para que se lea como "mensaje".
  const sobre = (d, dur, begin) =>
    `<g class="topo-pkt"><rect x="-12" y="-8.5" width="24" height="17" rx="3.5"/>`
    + `<path d="M-12,-7 L0,2 L12,-7"/><path class="pkt-ficha" d="M-6,0.5 h12 M-6,3.4 h8"/>`
    + `<animateMotion dur="${dur}" begin="${begin}" repeatCount="indefinite" calcMode="linear" path="${d}"/></g>`;
  const packet = v.packets
    ? v.packets.map(p => sobre(p.d, p.dur || '7s', p.begin || '0s')).join('')
    : (v.packet ? sobre(v.packet, '9s', '0s') : '');

  // Los hosts no pasan por topoEstado: se dibujan con su IP y su rol.
  const hosts = v.nodos.filter(n => n.host).map(n => {
    const cy = n.y + n.h / 2;
    return `<g class="topo-node topo-host ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      ${icoCirculo(n.icono, n.x + 25, cy, 16)}
      <text class="ttl" x="${n.x + 49}" y="${cy - 3}">${n.titulo}</text>
      <text class="hostip" x="${n.x + 49}" y="${cy + 11}">${n.ip}</text>
      <title>${n.titulo} · ${n.ip}${n.desc ? ' · ' + n.desc : ''}</title>
    </g>`;
  }).join('');

  const nodos = v.nodos.filter(n => !n.host).map(n => {
    const e = est[n.id];
    const cy = n.y + n.h / 2;
    const color = e.estado === 'ok' ? 'var(--ok)' : e.estado === 'warn' ? 'var(--amber)'
                : e.estado === 'bad' ? 'var(--danger)' : 'var(--border)';
    // Nodo de DECISION: rombo (diamante). Lleva el titulo centrado y una
    // etiqueta corta debajo; sus conectores salientes ya van rotulados.
    if (n.forma === 'rombo') {
      const cx = n.x + n.w / 2;
      const pts = `${cx},${n.y} ${n.x + n.w},${cy} ${cx},${n.y + n.h} ${n.x},${cy}`;
      const rsub = n.rsub
        ? `<text class="rombo-sub" x="${cx}" y="${cy + 13}" text-anchor="middle">${n.rsub}</text>` : '';
      return `<g class="topo-node ${e.estado} ${n.clase || ''} ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
        <polygon class="box rombo" points="${pts}"/>
        <text class="rombo-ttl" x="${cx}" y="${n.rsub ? cy - 1 : cy + 4}" text-anchor="middle">${n.titulo}</text>
        ${rsub}
        <circle class="led" cx="${cx}" cy="${n.y + 11}" r="4" fill="${color}"/>
      </g>`;
    }
    const etiqueta = n.tag
      ? `<text class="tag" x="${n.x + 49}" y="${n.y + n.h - 5}">${n.tag}</text>` : '';
    const desplazar = n.tag ? -8 : 0;
    // Con "Ver archivos" activo, cada nodo con ficheros muestra un contador; el
    // detalle de cada uno se abre pulsando el nodo (aparecen como cuadraditos).
    const nfiles = (topoArchivos && artefactos && artefactos[n.id]) ? artefactos[n.id].length : 0;
    const badge = nfiles
      ? `<text class="fbadge" x="${n.x + n.w - 24}" y="${n.y + n.h - 6}" text-anchor="end">▤ ${nfiles}</text>` : '';
    return `<g class="topo-node ${e.estado} ${n.clase || ''} ${nfiles ? 'tiene-archivos' : ''} ${topoSel === n.id ? 'sel' : ''}" data-node="${n.id}" tabindex="0" role="button" aria-label="${n.titulo}">
      <rect class="box" x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="9"/>
      ${icoCirculo(n.icono, n.x + 25, cy + desplazar * 0.5, 16)}
      <text class="ttl" x="${n.x + 49}" y="${cy - 3 + desplazar}">${n.titulo}</text>
      <text class="sub" x="${n.x + 49}" y="${cy + 12 + desplazar}">${e.valor}</text>
      ${etiqueta}${badge}
      <circle class="led" cx="${n.x + n.w - 13}" cy="${n.y + 13}" r="4" fill="${color}"/>
    </g>`;
  }).join('');

  // La punta de flecha toma el color de su conector (context-stroke).
  const defs = '<defs><marker id="topoPunta" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse"><path d="M0,0.8 L9.5,5 L0,9.2 Z" fill="context-stroke" stroke="none"/></marker></defs>';
  svg.innerHTML = defs + grupos + aristas + packet + hosts + nodos;
  svg.classList.toggle('con-flujo', !!flSet);
  if (flSet) {
    svg.style.setProperty('--flujo', flujoColor(fl));
    svg.querySelectorAll('.topo-node').forEach(g => g.classList.toggle('en-flujo', flSet.has(g.dataset.node)));
  } else svg.style.removeProperty('--flujo');
  try { renderFlujoBar(); } catch (e) { /* sin datos aun */ }
  aplicarZoom();
  renderTopoDetalle();
}

// --- Controles del diagrama: vista, escala y pantalla completa --------------
let topoZoom = null;   // null = ajustar al ancho disponible

// Ajuste por defecto: encuadra TODO el diagrama (ancho Y alto) dentro del
// lienzo, para que se vea entero de un vistazo. El lienzo tiene una altura
// acotada por CSS (min(76vh,760px)); en pantalla completa la hereda del padre.
function escalaAjuste() {
  const v = topoV();
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
  const v = topoV();
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

on('topoVista', 'click', (ev) => {
  const b = ev.target.closest('button[data-vista]');
  if (!b) return;
  topoVista = b.dataset.vista;
  document.querySelectorAll('#topoVista button').forEach(x => x.classList.toggle('active', x === b));
  topoZoom = null;   // cada vista tiene otro tamano: se reajusta
  // Si el nodo seleccionado no existe en la vista nueva, se cae al primero.
  if (!topoV().nodos.some(n => n.id === topoSel)) {
    const prim = topoV().nodos.find(n => !n.host) || topoV().nodos[0];
    topoSel = prim ? prim.id : null;
  }
  if (topoUltimo) renderTopologia(topoUltimo);
});

on('topoModo', 'click', (ev) => {
  const b = ev.target.closest('button[data-modo]');
  if (!b) return;
  topoModo = b.dataset.modo === 'operativa' ? 'operativa' : 'lab';
  try { localStorage.setItem('cf_topo_modo', topoModo); } catch (e) { /* sin persistir */ }
  if (!topoV().nodos.some(n => n.id === topoSel)) {
    const prim = topoV().nodos.find(n => !n.host) || topoV().nodos[0];
    topoSel = prim ? prim.id : null;
  }
  topoZoom = null;
  flujoFirma = null;
  if (topoUltimo) renderTopologia(topoUltimo); else pintarTopoModo();
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

// 18-nov: mapa táctil y con ratón. Arrastrar con un dedo o con el ratón mueve el mapa en los dos
// sentidos (izquierda-derecha y arriba-abajo); dos dedos hacen pellizco de zoom; Ctrl/⌘ + rueda
// (o pellizco en el trackpad) hace zoom centrado donde apuntas; la rueda normal o Shift+rueda
// desplazan. Un toque/clic sin mover sigue seleccionando el nodo; los botones +/−/Ajustar siguen.
(function () {
  const caja = document.getElementById('topoScroll');
  if (!caja || !window.PointerEvent) return;
  caja.style.touchAction = 'none';            // tomamos arrastre y pellizco nosotros
  function zoomHacia(nuevo, cx, cy) {
    const antes = escalaActual();
    nuevo = Math.max(0.25, Math.min(3, nuevo));
    if (Math.abs(nuevo - antes) < 0.001) return;
    const r = caja.getBoundingClientRect();
    const px = (caja.scrollLeft + (cx - r.left)) / antes;   // punto del diagrama bajo el cursor
    const py = (caja.scrollTop + (cy - r.top)) / antes;
    topoZoom = nuevo; aplicarZoom();
    caja.scrollLeft = px * nuevo - (cx - r.left);            // mantenerlo bajo el cursor
    caja.scrollTop = py * nuevo - (cy - r.top);
  }
  caja.addEventListener('wheel', ev => {
    if (ev.ctrlKey || ev.metaKey) {                         // Ctrl/⌘ + rueda = zoom
      ev.preventDefault();
      zoomHacia(escalaActual() * (ev.deltaY < 0 ? 1.12 : 1 / 1.12), ev.clientX, ev.clientY);
      return;
    }
    // Rueda normal: desplaza; Shift convierte la rueda vertical en horizontal.
    const dx = ev.shiftKey ? (ev.deltaY || ev.deltaX) : ev.deltaX;
    const dy = ev.shiftKey ? 0 : ev.deltaY;
    if (dx) { caja.scrollLeft += dx; ev.preventDefault(); }
    if (dy && (caja.scrollHeight > caja.clientHeight)) { caja.scrollTop += dy; }
  }, { passive: false });
  const pts = new Map();
  let distBase = 0, zoomBase = 1, arrastrando = false, movido = false;
  caja.addEventListener('pointerdown', ev => {
    pts.set(ev.pointerId, { x: ev.clientX, y: ev.clientY, x0: ev.clientX, y0: ev.clientY });
    if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      distBase = Math.hypot(a.x - b.x, a.y - b.y);
      zoomBase = escalaActual();
    }
  });
  caja.addEventListener('pointermove', ev => {
    const p = pts.get(ev.pointerId);
    if (!p) return;
    const dx = ev.clientX - p.x, dy = ev.clientY - p.y;
    p.x = ev.clientX; p.y = ev.clientY;
    if (pts.size === 2 && distBase) {                       // pellizco = zoom
      const [a, b] = [...pts.values()];
      ev.preventDefault();
      zoomHacia(zoomBase * (Math.hypot(a.x - b.x, a.y - b.y) / distBase), (a.x + b.x) / 2, (a.y + b.y) / 2);
      return;
    }
    if (pts.size === 1) {                                   // un dedo/ratón = arrastrar en los dos ejes
      if (!arrastrando && Math.hypot(ev.clientX - p.x0, ev.clientY - p.y0) < 4) return;  // deja pasar el toque/clic de selección
      arrastrando = true; movido = true;
      caja.classList.add('arrastrando');
      ev.preventDefault();
      try { caja.setPointerCapture(ev.pointerId); } catch (e) { /* ignora */ }
      caja.scrollLeft -= dx;
      caja.scrollTop -= dy;
    }
  });
  const soltar = ev => {
    pts.delete(ev.pointerId);
    if (pts.size < 2) distBase = 0;
    if (pts.size === 0) { arrastrando = false; caja.classList.remove('arrastrando'); }
  };
  caja.addEventListener('pointerup', soltar);
  caja.addEventListener('pointercancel', soltar);
  // Si hubo arrastre, no dejamos que el clic final seleccione un nodo por error.
  caja.addEventListener('click', ev => {
    if (movido) { ev.stopPropagation(); ev.preventDefault(); movido = false; }
  }, true);
})();

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
  // Si el visor esta abierto al entrar o salir de pantalla completa, recolocarlo
  // para que siga viendose (dentro del elemento expandido, o de vuelta al body).
  const m = document.getElementById('codeModal');
  if (m && !m.hidden) {
    const destino = document.fullscreenElement || document.body;
    if (m.parentElement !== destino) destino.appendChild(m);
  }
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

// Perfiles de trafico legitimo, cada uno con su icono (nodo "Clientes").
function perfilesHTML(perfiles) {
  if (!perfiles || !perfiles.length) return '';
  const COL = { ofimatica: '#2563eb', navegacion: '#0891b2', descargas: '#7c3aed', aplicacion: '#ea580c', ligero: '#16a34a', erratico: '#dc2626' };
  const fila = p => `<div class="perfil" style="--pc:${COL[p.icono] || 'var(--accent)'}"><span class="perfil-ico"><svg width="30" height="30" viewBox="0 0 18 18" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[p.icono] || ''}</svg></span>`
    + `<span class="perfil-n">${p.n}${p.ip ? '<small>' + p.ip + '</small>' : ''}</span>`
    + `<span class="perfil-d">${p.d || ''}</span>`
    + (p.ej ? `<span class="perfil-ej">p. ej. ${p.ej}</span>` : '') + `</div>`;
  return '<div class="cod-sub">Perfiles de tráfico legítimo</div>'
    + '<div class="perfiles">' + perfiles.map(fila).join('') + '</div>';
}

// Archivos del sistema de una carpeta, cada uno con el host donde corre.
const HOST_NOMBRE = { sensor: 'Sensor', servidor: 'Servidor', bastion: 'Bastión' };
function hostBadge(h) {
  const ic = HOST_ICON[h]
    ? '<svg width="11" height="11" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + TOPO_ICON[HOST_ICON[h]] + '</svg>'
    : '';
  return `<span class="host-badge host-${h}">${ic}${HOST_NOMBRE[h] || h}</span>`;
}
function archivosHostHTML(archivos) {
  if (!archivos || !archivos.length) return '';
  const fila = a => '<div class="arch"><span class="arch-ico"><svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + TOPO_ICON.fichero + '</svg></span>'
    + `<span class="arch-n">${a.n}</span>`
    + hostBadge(a.host)
    + (a.d ? `<span class="arch-d">${a.d}</span>` : '') + '</div>';
  return '<div class="cod-sub">Archivos del sistema · dónde corre cada uno</div>'
    + '<div class="archivos">' + archivos.map(fila).join('') + '</div>';
}

// Info de codigo del nodo: ruta del archivo, pseudocodigo y comando para editar.
function codigoHTML(c) {
  if (!c) return '';
  const nl = String.fromCharCode(10);
  const esc = s => s.split('<').join('&lt;');
  const pseudo = (c.pseudo && c.pseudo.length)
    ? '<div class="cod-sub">Pseudocódigo</div><pre class="topo-cmd">'
      + c.pseudo.map(esc).join(nl) + '</pre>' : '';
  const editar = c.editar
    ? '<div class="cod-sub">Editar</div><pre class="topo-cmd">' + esc(c.editar) + '</pre>' : '';
  return '<div class="cod-bloque"><div class="cod-sub">Archivo</div>'
    + '<code class="cod-ruta">' + esc(c.archivo || '') + '</code>' + pseudo + editar + '</div>';
}

function renderTopoDetalle() {
  if (!topoUltimo) return;
  const lista = topoV().nodos;
  const n = lista.find(x => x.id === topoSel) || lista[0];
  let e = topoEstado(n.id, topoUltimo);
  if (e.valor === '—' && n.val) e = Object.assign({}, e, { valor: n.val });
  const t = TOPO_TEXTO[n.id] || {};
  const filas = Object.entries(e.datos || {})
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  const cabIp = n.host && n.ip ? `<span class="state">${n.ip}</span>` : `<span class="state ${e.estado}">${e.valor}</span>`;
  const herr = herramientasHTML(n.id);
  const cuerpo =
    `<h3>${n.titulo}${cabIp}</h3>` +
    (t.que ? `<p>${t.que}</p>` : '') +
    (n.id === 'modelo' ? decisionModeloHTML() : '') +
    (t.leyenda ? '<div class="host-leyenda">' + t.leyenda.map(hostBadge).join('') + '</div>' : '') +
    perfilesHTML(t.perfiles) +
    archivosHostHTML(t.archivos) +
    (filas ? `<dl>${filas}</dl>` : '') +
    (t.cmd ? `<pre class="topo-cmd">${t.cmd.replace(/</g, '&lt;')}</pre>` : '') +
    (t.flujo ? flujoHTML(t.flujo, t.flujoTit) : '') +
    codigoHTML(t.codigo) +
    filesHTML(n.id) +
    (t.nota ? `<p class="dim">${t.nota}</p>` : '') +
    (t.enlace ? `<p><a href="${t.enlace.href}"${t.enlace.vtab ? ` data-vtab="${t.enlace.vtab}"` : ''}>${t.enlace.txt} &rarr;</a></p>` : '');
  document.getElementById('topoDetail').innerHTML = herr
    ? `<div class="det-con-herr"><div class="det-cuerpo">${cuerpo}</div>${herr}</div>` : cuerpo;
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
        ? `<button class="ver-codigo" data-ruta="${String(f.ruta).replace(/"/g, '&quot;')}" data-que="${String(f.que || '').replace(/"/g, '&quot;')}">◎ Ver contenido</button>`
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
  if (vc) { await verCodigo(vc.dataset.ruta, vc.dataset.que); return; }
  const f = ev.target.closest('.topo-file');
  if (!f) return;
  const clave = f.dataset.file;
  if (filesAbiertos.has(clave)) filesAbiertos.delete(clave); else filesAbiertos.add(clave);
  renderTopoDetalle();
});

// Pseudocodigo POR ARCHIVO, con ancla: cada paso apunta a un trozo real del
// codigo (un nombre de funcion). Al pulsarlo, el panel izquierdo salta a esa
// linea. Si un archivo no tiene guia, el panel derecho muestra su explicacion.
const GUIA_CODIGO = {
  'motor_decision.py': {
    explica: 'El bucle del motor: cada 10 s lee los PCAP ya cerrados del anillo, atribuye cada paquete a quien inició el flujo, extrae las variables por ventana y escribe la decisión.',
    editar: 'nano ~/cyberflow/scripts/engine/motor_decision.py && sudo systemctl restart ppi-motor',
    pseudo: [
      { t: 'Argumentos y configuración de arranque', ancla: 'def parse_args' },
      { t: 'Umbral del modelo (del manifiesto)', ancla: 'def load_threshold' },
      { t: 'Seguir eve.json en vivo', ancla: 'class EveTail' },
      { t: 'Listar los PCAP ya cerrados del anillo', ancla: 'def list_closed_pcap_files' },
      { t: 'Decodificar cada PCAP a paquetes', ancla: 'def parse_pcap_to_packets' },
      { t: 'Bucle principal cada 10 s', ancla: 'def main' },
      { t: 'IP fuera de alcance (no se puntúa)', ancla: 'def entidad_excluida' },
      { t: 'Aplicar la acción (solo en el host)', ancla: 'def apply_enforcement' },
    ],
  },
  'heuristicos.py': {
    explica: 'Las cuatro reglas deterministas sobre las variables de la ventana. Cada una devuelve una acción (BLOCK/LIMIT) o nada; evaluar() se queda con la más severa.',
    editar: 'nano ~/cyberflow/scripts/engine/heuristicos.py && sudo systemctl restart ppi-motor',
    pseudo: [
      { t: 'Versión de los umbrales', ancla: 'VERSION_UMBRALES' },
      { t: 'Fuerza bruta → BLOCK', ancla: 'def _brute_force' },
      { t: 'Escaneo de puertos → BLOCK', ancla: 'def _port_scan' },
      { t: 'Abuso HTTP → LIMIT', ancla: 'def _http_abuse' },
      { t: 'DNS de alta entropía → LIMIT', ancla: 'def _dns_entropy' },
      { t: 'Combina las reglas (la más severa)', ancla: 'def evaluar' },
    ],
  },
  'extract_multilayer_v2.py': {
    explica: 'El extractor congelado: de tramas PCAP y eventos eve.json a las 28 variables por IP y ventana. Sus fórmulas no se tocan.',
    editar: 'nano ~/cyberflow/scripts/features/extract_multilayer_v2.py && sudo systemctl restart ppi-motor',
    pseudo: [
      { t: 'Recorrer las tramas del PCAP', ancla: 'def iter_pcap_frames' },
      { t: 'Decodificar Ethernet / IPv4', ancla: 'def parse_ethernet_ipv4' },
      { t: 'Atribuir cada paquete a quien inició', ancla: 'def attribute_packets' },
      { t: 'Observaciones L7 (http · dns · tls)', ancla: 'def load_app_observations' },
      { t: 'Entropía de nombres (DNS)', ancla: 'def shannon_entropy_bits' },
      { t: 'Una fila por IP y ventana', ancla: 'def build_rows' },
    ],
  },
  'publicar_feed.py': {
    explica: 'Cada 10 s combina las decisiones recientes del motor por IP, aplica la escalera de reincidencia y publica el feed.',
    editar: 'nano ~/cyberflow/scripts/engine/publicar_feed.py',
    pseudo: [
      { t: 'Veredicto de una decisión', ancla: 'def _verdicto_de' },
      { t: 'De decisiones a entradas del feed', ancla: 'def decisiones_a_entradas' },
      { t: 'Versión de umbrales', ancla: 'def version_umbrales' },
      { t: 'Leer las decisiones recientes', ancla: 'def _leer_decisiones' },
      { t: 'Publicar (bucle principal)', ancla: 'def main' },
    ],
  },
  'feed.py': {
    explica: 'Construye, serializa y FIRMA el feed con ed25519. El host verifica la firma antes de aplicar nada.',
    editar: 'nano ~/cyberflow/scripts/engine/feed.py',
    pseudo: [
      { t: 'Construir el feed', ancla: 'def construir' },
      { t: 'Serializar a bytes', ancla: 'def serializar' },
      { t: 'Generar las claves', ancla: 'def generar_claves' },
      { t: 'Firmar (ed25519)', ancla: 'def firmar' },
      { t: 'Verificar la firma', ancla: 'def verificar' },
    ],
  },
  'escalada.py': {
    explica: 'La escalera de caducidad por reincidencia: 300 → 1800 → 3600 s dentro de 24 h.',
    editar: 'nano ~/cyberflow/scripts/engine/escalada.py',
    pseudo: [
      { t: 'Procesar una ofensa (sube el nivel)', ancla: 'def procesar' },
      { t: 'Podar lo viejo (decaimiento)', ancla: 'def podar' },
    ],
  },
  'cyberflow_aprendizaje.py': {
    explica: 'El reentrenamiento nocturno con aprobación humana: sanea el lote, mide la deriva contra el oro, entrena un candidato y lo deja listo para que una persona lo promueva.',
    editar: 'nano ~/cyberflow/scripts/modeling/cyberflow_aprendizaje.py',
    pseudo: [
      { t: 'PSI (índice de deriva)', ancla: 'def psi' },
      { t: 'Comprobar la política del .toml', ancla: 'def comprobar_politica' },
      { t: 'Conjunto de oro (fijo, nunca entrena)', ancla: 'def crear_oro' },
      { t: 'Cerrar el lote del día (saneo)', ancla: 'def cerrar_lote' },
      { t: 'Medir la deriva', ancla: 'def medir_deriva' },
      { t: 'Puntuar con el modelo', ancla: 'def puntuar' },
    ],
  },
  'extract_multilayer_v3.py': {
    explica: 'Variante v3 del extractor: las 28 variables de v2 más 3 de capa 2 (ARP, VLAN, MAC). Aquí vive la deduplicación de la copia del espejo, que evita contar dos veces cada trama.',
    editar: 'nano ~/cyberflow/scripts/features/extract_multilayer_v3.py',
    pseudo: [
      { t: 'Decodificar Ethernet (capa 2)', ancla: 'def parse_ethernet_l2' },
      { t: 'Trama con su contexto (VLAN, puerto)', ancla: 'def parse_con_contexto' },
      { t: 'Deduplicar la copia del espejo', ancla: 'def deduplicar_espejo' },
      { t: 'MACs que reenvían (gateways)', ancla: 'def forwarding_macs' },
      { t: 'VLAN nativa por puerto', ancla: 'def native_vlans' },
      { t: 'Cambios de vínculo IP↔MAC', ancla: 'def binding_changes' },
      { t: 'Una fila de 31 variables', ancla: 'def build_rows' },
    ],
  },
  'acumular_v3.py': {
    explica: 'El temporizador de la línea base: cada 10 min toma los PCAP ya cerrados y el tramo de eve.json, los pasa por el MISMO extractor que el motor y añade filas nuevas al dataset, sin duplicar.',
    editar: 'nano ~/cyberflow/scripts/features/acumular_v3.py',
    pseudo: [
      { t: 'PCAP ya cerrados del anillo', ancla: 'def pcaps_cerrados' },
      { t: 'Rebanada de eve.json del mismo tramo', ancla: 'def rebanada_eve' },
      { t: 'Claves (IP, ventana) ya escritas (no duplicar)', ancla: 'def claves_ya_escritas' },
      { t: 'Extraer y anexar (bucle)', ancla: 'def main' },
    ],
  },
  'particionar_linea_base.py': {
    explica: 'Parte la línea base en entrenamiento / validación / prueba SIN fuga temporal: por bloques horarios (cubren todo el ciclo diario) y con una banda de guarda para que ninguna ventana comparta paquetes entre grupos.',
    editar: 'python3 scripts/dataset/particionar_linea_base.py --help',
    pseudo: [
      { t: 'Partir por bloques horarios + banda de guarda', ancla: 'def particionar' },
      { t: 'Comprobar que no hay solape entre grupos', ancla: 'def comprobar' },
      { t: 'sha256 de cada salida', ancla: 'def sha256' },
      { t: 'Escribir las tres particiones', ancla: 'def main' },
    ],
  },
  'entrenar_preliminar.py': {
    explica: 'Entrena el modelo con tráfico normal limpio y CONGELA el umbral como el percentil α de validación. Guarda un paquete (modelo + escalador + umbral) que luego se promueve. No decide nada en vivo.',
    editar: 'python3 scripts/modeling/entrenar_preliminar.py --help',
    pseudo: [
      { t: 'Cargar filas (solo elegibles)', ancla: 'def cargar' },
      { t: 'Matriz de variables en el orden del esquema', ancla: 'def matriz' },
      { t: 'Entrenar y fijar el umbral en validación', ancla: 'def main' },
      { t: 'sha256 del paquete', ancla: 'def sha256' },
    ],
  },
  'promover_preliminar.py': {
    explica: 'Convierte el paquete de entrenamiento en el artefacto que el motor carga: un Pipeline + un manifiesto con el umbral, el orden de variables y los hashes. Se NIEGA a sobrescribir un artefacto existente (rollback seguro).',
    editar: 'python3 scripts/modeling/promover_preliminar.py --help',
    pseudo: [
      { t: 'Orden de variables del esquema', ancla: 'def orden_del_esquema' },
      { t: 'Comprobar que el paquete respeta ese orden', ancla: 'def comprobar_orden' },
      { t: 'Promover: Pipeline + manifiesto (no sobrescribe)', ancla: 'def promover' },
      { t: 'sha256 del artefacto', ancla: 'def sha256' },
    ],
  },
  'verificar_equivalencia_umbral.py': {
    explica: 'Comprueba que el umbral del modelo desplegado significa lo mismo en las dos escalas (score_samples y decision_function) y que el artefacto coincide con su manifiesto: hash, orden de variables y 0 decisiones distintas sobre filas reales.',
    editar: 'python3 scripts/modeling/verificar_equivalencia_umbral.py --help',
    pseudo: [
      { t: 'Umbral declarado en el manifiesto', ancla: 'def umbral_del_manifiesto' },
      { t: 'Estimador final del Pipeline', ancla: 'def estimador_final' },
      { t: 'Filas de muestra para comparar', ancla: 'def filas' },
      { t: 'Verificar equivalencia (hash + orden + umbral)', ancla: 'def verificar' },
    ],
  },
  'comparar_reentrenamiento.py': {
    explica: 'Ensayo en seco: compara el modelo ANTES y DESPUÉS de un reentrenamiento sobre los mismos conjuntos, y muestra el delta de cada métrica (FPR, detección) para decidir si el candidato mejora.',
    editar: 'python3 scripts/modeling/comparar_reentrenamiento.py --help',
    pseudo: [
      { t: 'Leer los dos informes (antes / después)', ancla: 'def leer' },
      { t: 'Delta por métrica (mejor = menor o mayor)', ancla: 'def delta' },
      { t: 'Formatear porcentajes', ancla: 'def pct' },
      { t: 'Imprimir la comparación', ancla: 'def main' },
    ],
  },
  'cyberflow_config.py': {
    explica: 'El generador de la instalación: lee cyberflow.local.toml y ESCRIBE las unidades de systemd (captura, motor, panel, temporizadores) y el alcance. El .toml manda; de aquí no sale nada que no esté declarado.',
    editar: 'python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --mostrar',
    pseudo: [
      { t: 'Cargar el .toml', ancla: 'def cargar' },
      { t: 'Comprobar la configuración (fail-closed)', ancla: 'def comprobar' },
      { t: '¿El panel queda expuesto? (regla nftables)', ancla: 'def panel_expuesto' },
      { t: 'Exclusiones de alcance', ancla: 'def exclusiones' },
      { t: 'Render de las unidades systemd', ancla: 'def render' },
    ],
  },
  'responder_iptables.py': {
    explica: 'La respuesta INLINE alternativa (sensor que también es router): bloquea con iptables/nftables las IP en alerta sostenida. Nunca toca la infraestructura (gateways, DNS). En el despliegue vigente la respuesta la hace el agente del host con el feed firmado; este es el camino directo.',
    editar: 'nano ~/cyberflow/scripts/engine/responder_iptables.py',
    pseudo: [
      { t: '¿La IP es infraestructura? (nunca bloquear)', ancla: 'def es_infraestructura' },
      { t: 'Leer el registro del motor', ancla: 'def parse_registro' },
      { t: 'Candidatos: alerta sostenida ≥ mínimo', ancla: 'def candidatos' },
      { t: 'Reglas iptables ya activas', ancla: 'def iptables_activas' },
      { t: 'Aplicar la regla', ancla: 'def aplicar_regla' },
    ],
  },
  'vista_vivo.py': {
    explica: 'La trazabilidad de «Datos en vivo»: toma las tramas del PCAP reciente y los eventos de eve.json y muestra, para cada uno, a QUÉ variable aporta. Es la misma cadena del motor, pero sobre el tramo reciente y para explicarse.',
    editar: 'nano ~/cyberflow/scripts/engine/vista_vivo.py',
    pseudo: [
      { t: 'Matriz variable ↔ trama/evento', ancla: 'def matriz_trazabilidad' },
      { t: 'Aportes de un paquete', ancla: 'def aportes_paquete' },
      { t: 'Aportes de un evento L7', ancla: 'def aportes_evento' },
      { t: 'Calcular el tramo reciente', ancla: 'def calcular' },
      { t: 'Flujo PCAP + eve para el panel', ancla: 'def flujo' },
    ],
  },
  'compare_frozen_models_metrics.py': {
    explica: 'Reproduce las métricas de los 7 modelos candidatos (binarias y de ranking) sobre los mismos datos congelados, con intervalos de Wilson. Es el soporte de la tabla de comparación del informe.',
    editar: 'python3 scripts/analysis/compare_frozen_models_metrics.py --help',
    pseudo: [
      { t: 'Leer las filas del dataset', ancla: 'def read_rows' },
      { t: 'Intervalo de confianza (Wilson)', ancla: 'def wilson' },
      { t: 'Construir el informe de los 7', ancla: 'def build_report' },
      { t: 'sha256 de los datos', ancla: 'def sha256' },
    ],
  },
  'significancia_modelos.py': {
    explica: 'Las pruebas de significancia entre los 7 candidatos: McNemar por pares y corrección de Holm, para no afirmar que un modelo es mejor por azar. Soporta la elección con rigor estadístico.',
    editar: 'python3 scripts/modeling/experiments/significancia_modelos.py --help',
    pseudo: [
      { t: 'McNemar entre dos modelos', ancla: 'def mcnemar' },
      { t: 'Vector a episodios', ancla: 'def a_episodio' },
      { t: 'Corrección de Holm (múltiples pares)', ancla: 'def holm' },
      { t: 'Informe', ancla: 'def informe' },
    ],
  },
};

// Diagrama de flujo POR ARCHIVO: las DECISIONES reales del codigo (rombos con
// sus ramas si/no) y los saltos a OTRO archivo (nodos 'archivo', pulsables).
// Cada 'ancla' es texto literal del codigo: al pulsar, el panel izquierdo salta
// a esa linea. Fiel a lo leido en cada fichero; auditado contra el codigo real.
const GUIA_FLUJO = {
  'extract_multilayer_v2.py': {
    titulo: 'De PCAP + eve.json a 28 variables',
    pasos: [
      { k: 'inicio', t: 'Ventana de 10/30/60 s por IP iniciadora' },
      { k: 'proc', t: 'Recorrer las tramas del PCAP', ancla: 'def iter_pcap_frames' },
      { k: 'proc', t: 'Decodificar Ethernet / IPv4', ancla: 'def parse_ethernet_ipv4' },
      { k: 'proc', t: 'Atribuir cada paquete a quien inició el flujo', ancla: 'def attribute_packets' },
      { k: 'proc', t: 'Observaciones L7 (http · dns · tls) de eve.json', ancla: 'def load_app_observations' },
      { k: 'dec', t: 'DNS: entropía de nombres', cond: 'si hay consultas DNS', si: 'bits de Shannon', no: 'se omite', ancla: 'def shannon_entropy_bits' },
      { k: 'io', t: 'Una fila de 28 variables por IP y ventana', ancla: 'def build_rows' },
      { k: 'archivo', t: 'El motor la puntúa', ir: 'motor_decision.py' },
    ],
  },
  'motor_decision.py': {
    titulo: 'Bucle del motor · cada 10 s, por ventana',
    pasos: [
      { k: 'inicio', t: 'PCAP ya cerrados del anillo', ancla: 'def list_closed_pcap_files' },
      { k: 'archivo', t: 'Extraer las 28 variables', ir: 'extract_multilayer_v2.py' },
      { k: 'dec', t: 'IP fuera de alcance', cond: 'entidad_excluida(ip)', si: 'no se puntúa', no: 'sigue', ancla: 'def entidad_excluida' },
      { k: 'dec', t: 'Ventana sin paquetes L3/L4', cond: 'packet_count_10s == 0', si: 'score=None · PERMIT (solo L7)', no: 'puntuar el modelo', ancla: 'no_live_packets' },
      { k: 'proc', t: 'Puntuar con el modelo (OCSVM)', ancla: 'score_samples' },
      { k: 'dec', t: 'Anomalía del modelo', cond: 'score < umbral', si: 'ALERT', no: 'PERMIT', ancla: '"ALERT" if score < threshold' },
      { k: 'dec', t: 'Ráfaga de 401 sobre un PERMIT', cond: 'http60 ≥ 5  y  fallo_auth ≥ 80%', si: 'ALERT (heurístico L7)', no: 'queda igual', ancla: 'auth_failure_heuristic' },
      { k: 'proc', t: 'Adjuntar el veredicto de los 4 heurísticos', ancla: 'heuristicos.evaluar' },
      { k: 'io', t: 'Escribir la decisión en motor_decision.log', ancla: 'args.log_path.open' },
      { k: 'dec', t: 'Aplicar la acción', cond: '--enforce  y  decisión == ALERT', si: 'bloquea / relay', no: 'solo observa', ancla: 'def apply_enforcement' },
      { k: 'archivo', t: 'publicar_feed.py lee el log cada 10 s', ir: 'publicar_feed.py' },
    ],
  },
  'heuristicos.py': {
    titulo: 'evaluar(row): la MÁS severa de 4 reglas',
    pasos: [
      { k: 'inicio', t: 'Variables L3/L4/L7 de la ventana', ancla: 'def evaluar' },
      { k: 'dec', t: 'Fuerza bruta', cond: 'req_http ≥ 5  y  fallo_auth ≥ 80%', si: 'BLOCK', no: '—', ancla: 'def _brute_force' },
      { k: 'dec', t: 'Escaneo de puertos', cond: '(intentos ≥ 20 · únicos ≥ 0,45 · compl ≤ 0,3)   Ó   (ráfaga ≥ 200 · compl ≤ 0,1)', si: 'BLOCK', no: '—', ancla: 'def _port_scan' },
      { k: 'dec', t: 'Abuso HTTP', cond: 'req ≥ 100  y  fallo_auth < 80%', si: 'LIMIT', no: '—', ancla: 'def _http_abuse' },
      { k: 'dec', t: 'DNS de alta entropía', cond: 'consultas ≥ 20  y  (NXDOMAIN ≥ 0,5  o  únicos ≥ 0,45)', si: 'LIMIT', no: '—', ancla: 'def _dns_entropy' },
      { k: 'proc', t: 'Se queda con la más severa (BLOCK > LIMIT)', ancla: '_SEVERIDAD' },
      { k: 'archivo', t: 'El motor lo adjunta a la decisión', ir: 'motor_decision.py' },
    ],
  },
  'publicar_feed.py': {
    titulo: 'Publicar el feed firmado · ciclo 10 s',
    pasos: [
      { k: 'proc', t: 'Leer las decisiones recientes del log', ancla: 'def _leer_decisiones' },
      { k: 'dec', t: 'Veredicto por decisión', cond: 'ALERT modelo → LIMIT · heurístico → su acción', si: 'la más severa', no: 'None', ancla: 'def _verdicto_de' },
      { k: 'proc', t: 'Agregar por IP el veredicto más severo', ancla: 'def decisiones_a_entradas' },
      { k: 'dec', t: 'IP en nunca-bloquear', cond: 'gateways · DNS · sensor · bastión', si: 'se omite', no: 'sigue', ancla: 'NUNCA_BLOQUEAR' },
      { k: 'archivo', t: 'Escalera de caducidad por reincidencia', ir: 'escalada.py' },
      { k: 'archivo', t: 'Construir y firmar el feed (ed25519)', ir: 'feed.py' },
      { k: 'archivo', t: 'El host lo trae y lo verifica', ir: 'agente_enforce.py' },
    ],
  },
  'escalada.py': {
    titulo: 'procesar(ip, acción): la caducidad',
    pasos: [
      { k: 'inicio', t: 'Estado por IP {bloqueos, último_visto}', ancla: 'def procesar' },
      { k: 'dec', t: 'Decaimiento', cond: '> 24 h sin reincidir', si: 'reinicia el contador', no: 'mantiene', ancla: 'VENTANA_DECAIMIENTO_S' },
      { k: 'dec', t: '¿Qué acción?', cond: 'BLOCK  vs  LIMIT', si: 'BLOCK: sube de nivel', no: 'LIMIT: 300 s plano', ancla: 'TIMEOUT_LIMIT_S' },
      { k: 'proc', t: '1º → 300 · 2º → 1800 · 3º+ → 3600 s (tope)', ancla: 'ESCALERA_BLOCK_S' },
      { k: 'dec', t: 'Reincidencia alta', cond: 'bloqueos ≥ 3', si: 'marca revisión humana', no: '—', ancla: 'REVISION_HUMANA_DESDE' },
      { k: 'fin', t: '∞ NUNCA automático: lo decide una persona' },
    ],
  },
  'feed.py': {
    titulo: 'Firmar en el sensor · verificar en el host',
    pasos: [
      { k: 'proc', t: 'Construir el feed (version · generado · entradas)', ancla: 'def construir' },
      { k: 'proc', t: 'Serializar a bytes (JSON canónico, sort_keys)', ancla: 'def serializar' },
      { k: 'proc', t: 'Firmar con ed25519 (clave privada, solo en el sensor)', ancla: 'def firmar' },
      { k: 'archivo', t: 'El relay lo copia al host', ir: 'agente_enforce.py' },
      { k: 'dec', t: '[en el host] firma válida', cond: 'con la clave pública', si: 'aplica nftables', no: 'no toca nada (fail-safe)', ancla: 'def verificar' },
    ],
  },
  'cyberflow_aprendizaje.py': {
    titulo: 'Aprendizaje nocturno · 00:30 UTC',
    pasos: [
      { k: 'inicio', t: 'Conjunto de oro fijo (NUNCA entrena)', ancla: 'def crear_oro' },
      { k: 'proc', t: 'Cerrar el lote del día (saneo)', ancla: 'def cerrar_lote' },
      { k: 'proc', t: 'Medir la deriva (PSI contra el oro)', ancla: 'def medir_deriva' },
      { k: 'dec', t: 'Política del .toml', cond: 'sección [reentrenamiento]', si: 'entrena candidato', no: 'se detiene', ancla: 'def comprobar_politica' },
      { k: 'proc', t: 'Entrenar candidato y puntuar vs oro', ancla: 'def puntuar' },
      { k: 'dec', t: 'Mejora sin fuga', cond: 'umbral congelado', si: 'deja candidato listo', no: 'descarta', ancla: 'def psi' },
      { k: 'fin', t: 'Una PERSONA lo promueve (vista Aprendizaje)' },
    ],
  },
  'agente_enforce.py': {
    titulo: 'Agente en el host protegido · ciclo 10 s',
    pasos: [
      { k: 'inicio', t: 'Traer el feed del relay (bastión)' },
      { k: 'dec', t: 'Firma ed25519 válida', cond: 'con la clave pública', si: 'sigue', no: 'no toca nada (fail-safe)' },
      { k: 'proc', t: 'Sincronizar nftables: LIMIT = rate-limit · BLOCK = drop + timeout' },
      { k: 'fin', t: 'El set caduca solo (timeout nativo de nftables)' },
    ],
  },
  'extract_multilayer_v3.py': {
    titulo: 'Trama → 31 variables (28 v2 + 3 de capa 2)',
    pasos: [
      { k: 'inicio', t: 'Trama del PCAP + su timestamp' },
      { k: 'proc', t: 'Decodificar Ethernet (MAC, VLAN, ethertype)', ancla: 'def parse_ethernet_l2' },
      { k: 'proc', t: 'Trama con contexto (VLAN nativa, puerto)', ancla: 'def parse_con_contexto' },
      { k: 'dec', t: 'Copia del espejo', cond: 'misma trama, TTL−1 entre VLAN', si: 'se descarta (no contar dos veces)', no: 'se conserva', ancla: 'def deduplicar_espejo' },
      { k: 'proc', t: 'Señales L2: MACs que reenvían · VLAN nativa · cambios IP↔MAC', ancla: 'def forwarding_macs' },
      { k: 'io', t: 'Una fila de 31 variables por IP y ventana', ancla: 'def build_rows' },
      { k: 'archivo', t: 'El motor usa las 28 del modelo', ir: 'motor_decision.py' },
    ],
  },
  'acumular_v3.py': {
    titulo: 'Línea base: acumular cada 10 min',
    pasos: [
      { k: 'inicio', t: 'Temporizador (cada 10 min)' },
      { k: 'proc', t: 'PCAP ya cerrados del anillo', ancla: 'def pcaps_cerrados' },
      { k: 'proc', t: 'Rebanada de eve.json del mismo tramo', ancla: 'def rebanada_eve' },
      { k: 'dec', t: '¿(IP, ventana) ya escrita?', cond: 'clave ya en el CSV', si: 'se omite (no duplicar)', no: 'se extrae', ancla: 'def claves_ya_escritas' },
      { k: 'io', t: 'Anexar filas nuevas al dataset', ancla: 'def main' },
      { k: 'archivo', t: 'El aprendizaje sanea este lote', ir: 'cyberflow_aprendizaje.py' },
    ],
  },
  'particionar_linea_base.py': {
    titulo: 'Partir sin fuga temporal',
    pasos: [
      { k: 'inicio', t: 'Línea base completa (una fila por ventana)' },
      { k: 'proc', t: 'Repartir por bloques horarios (cubren el ciclo diario)', ancla: 'def particionar' },
      { k: 'proc', t: 'Banda de guarda: ninguna ventana compartida entre grupos', ancla: 'def particionar' },
      { k: 'dec', t: 'Solape entre train/val/test', cond: 'ventanas que comparten paquetes', si: 'ERROR, no se escribe', no: 'sigue', ancla: 'def comprobar' },
      { k: 'io', t: 'Tres particiones + su sha256 (≈ 61/20/20)', ancla: 'def sha256' },
      { k: 'archivo', t: 'El test se congela como «oro»', ir: 'cyberflow_aprendizaje.py' },
    ],
  },
  'entrenar_preliminar.py': {
    titulo: 'Entrenar y CONGELAR el umbral',
    pasos: [
      { k: 'inicio', t: 'Partición de entrenamiento (solo normal, limpio)' },
      { k: 'proc', t: 'Cargar filas elegibles', ancla: 'def cargar' },
      { k: 'proc', t: 'Matriz en el orden del esquema', ancla: 'def matriz' },
      { k: 'proc', t: 'Entrenar el detector', ancla: 'def main' },
      { k: 'proc', t: 'Fijar el umbral = percentil α de VALIDACIÓN', ancla: 'def main' },
      { k: 'io', t: 'Paquete (modelo + escalador + umbral) + sha256', ancla: 'def sha256' },
      { k: 'archivo', t: 'Se promueve al artefacto del motor', ir: 'promover_preliminar.py' },
    ],
  },
  'promover_preliminar.py': {
    titulo: 'Paquete → artefacto del motor',
    pasos: [
      { k: 'inicio', t: 'Paquete de entrenar_preliminar.py', ancla: 'def promover' },
      { k: 'proc', t: 'Orden de variables del esquema', ancla: 'def orden_del_esquema' },
      { k: 'dec', t: '¿El paquete respeta ese orden?', cond: 'mismas variables, mismo orden', si: 'sigue', no: 'ERROR (el motor lo rechazaría)', ancla: 'def comprobar_orden' },
      { k: 'dec', t: '¿Ya existe el artefacto?', cond: 'no pisar un modelo en uso', si: 'se niega (rollback seguro)', no: 'escribe', ancla: 'def promover' },
      { k: 'io', t: 'Pipeline + manifiesto (umbral, orden, hash)', ancla: 'def promover' },
      { k: 'archivo', t: 'Se verifica la equivalencia', ir: 'verificar_equivalencia_umbral.py' },
    ],
  },
  'verificar_equivalencia_umbral.py': {
    titulo: 'Verificar artefacto ↔ manifiesto',
    pasos: [
      { k: 'inicio', t: 'Artefacto desplegado + su manifiesto', ancla: 'def verificar' },
      { k: 'proc', t: 'Umbral declarado (dos escalas)', ancla: 'def umbral_del_manifiesto' },
      { k: 'proc', t: 'Puntuar filas reales de muestra', ancla: 'def filas' },
      { k: 'dec', t: '¿Equivalente?', cond: 'hash + orden + 0 decisiones distintas', si: 'OK (reproducible)', no: 'FALLA (no se despliega)', ancla: 'def verificar' },
      { k: 'fin', t: 'Sale 0 solo si todo coincide' },
    ],
  },
  'cyberflow_config.py': {
    titulo: 'De .toml a unidades systemd',
    pasos: [
      { k: 'inicio', t: 'configs/cyberflow.local.toml', ancla: 'def cargar' },
      { k: 'dec', t: '¿Configuración válida?', cond: 'comprobar (fail-closed)', si: 'sigue', no: 'ERROR, no escribe nada', ancla: 'def comprobar' },
      { k: 'dec', t: '¿El panel queda expuesto?', cond: 'host/puerto accesibles', si: 'regla nftables «permitir solo bastión»', no: '—', ancla: 'def panel_expuesto' },
      { k: 'proc', t: 'Exclusiones de alcance (sensor, bastión, gateways)', ancla: 'def exclusiones' },
      { k: 'io', t: 'Render de las unidades (captura · motor · panel · timers)', ancla: 'def render' },
    ],
  },
  'responder_iptables.py': {
    titulo: 'Respuesta inline (sensor-router)',
    pasos: [
      { k: 'inicio', t: 'Registro del motor (decisiones)', ancla: 'def parse_registro' },
      { k: 'proc', t: 'Candidatos: alerta sostenida ≥ mínimo', ancla: 'def candidatos' },
      { k: 'dec', t: '¿La IP es infraestructura?', cond: 'gateway · DNS · sensor · bastión', si: 'NUNCA se bloquea', no: 'sigue', ancla: 'def es_infraestructura' },
      { k: 'dec', t: '¿Ya hay regla activa?', cond: 'iptables_activas', si: 'no se repite', no: 'aplica', ancla: 'def iptables_activas' },
      { k: 'proc', t: 'Aplicar la regla (drop / limit)', ancla: 'def aplicar_regla' },
      { k: 'fin', t: 'En el despliegue vigente esto lo hace el AGENTE del host con el feed firmado' },
    ],
  },
};

// Modo desarrollador: modal de dos paneles. Izquierda el codigo real con sus
// numeros de linea; derecha la explicacion y el pseudocodigo enlazado.
// El visor es un overlay a nivel de body. En pantalla completa el navegador
// solo pinta el subarbol del elemento expandido (#topoWrap), asi que la modal
// se MUEVE dentro de el al abrirse y vuelve al body al cerrarse.
function modalAlFrente() {
  const m = document.getElementById('codeModal');
  const destino = document.fullscreenElement || document.body;
  if (m.parentElement !== destino) destino.appendChild(m);
  return m;
}
function cerrarModal() {
  const m = document.getElementById('codeModal');
  if (!m) return;
  m.hidden = true;
  if (m.parentElement !== document.body) document.body.appendChild(m);
}

// --- Resaltado de sintaxis (sin dependencias; Python y generico) -----------
// Colores que SEPARAN funciones de palabras clave, cadenas, comentarios y
// numeros. El nombre de una funcion (definida o llamada) resalta en turquesa,
// para seguir el hilo del codigo y de un fichero a otro.
const PY_KW = new Set(('False None True and as assert async await break class '
  + 'continue def del elif else except finally for from global if import in is '
  + 'lambda nonlocal not or pass raise return try while with yield match case').split(' '));
const PY_BI = new Set(('self cls print len range int float str dict list set tuple '
  + 'bool bytes open super isinstance issubclass Path json time sys os min max sum '
  + 'abs enumerate zip sorted map filter any all next iter round type format').split(' '));
const BS = String.fromCharCode(92);  // la barra invertida, sin escribirla literal
function escH(s) {
  return String(s).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;');
}
function esAlfa(c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c === '_'; }
function esAlfaNum(c) { return esAlfa(c) || (c >= '0' && c <= '9'); }

// Resalta UNA linea de Python. st.tq lleva el estado de cadena triple entre
// lineas (los docstrings ocupan varias). Devuelve HTML.
function resaltarPy(linea, st) {
  let out = '', i = 0; const n = linea.length;
  if (st.tq) {
    const c = linea.indexOf(st.tq);
    if (c === -1) return '<span class="t-str">' + escH(linea) + '</span>';
    out += '<span class="t-str">' + escH(linea.slice(0, c + 3)) + '</span>';
    i = c + 3; st.tq = null;
  }
  let prevKw = '';
  while (i < n) {
    const c = linea[i];
    if (c === '#') { out += '<span class="t-com">' + escH(linea.slice(i)) + '</span>'; return out; }
    if ((c === '"' || c === "'") && linea.slice(i, i + 3) === c + c + c) {
      const d = c + c + c, cl = linea.indexOf(d, i + 3);
      if (cl === -1) { out += '<span class="t-str">' + escH(linea.slice(i)) + '</span>'; st.tq = d; return out; }
      out += '<span class="t-str">' + escH(linea.slice(i, cl + 3)) + '</span>'; i = cl + 3; continue;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n) { if (linea[j] === BS) { j += 2; continue; } if (linea[j] === c) { j++; break; } j++; }
      out += '<span class="t-str">' + escH(linea.slice(i, j)) + '</span>'; i = j; continue;
    }
    if (c === '@' && (i === 0 || linea[i - 1] === ' ')) {
      let j = i + 1; while (j < n && (esAlfaNum(linea[j]) || linea[j] === '.')) j++;
      out += '<span class="t-dec">' + escH(linea.slice(i, j)) + '</span>'; i = j; continue;
    }
    if (c >= '0' && c <= '9') {
      let j = i + 1; while (j < n && (esAlfaNum(linea[j]) || linea[j] === '.')) j++;
      out += '<span class="t-num">' + escH(linea.slice(i, j)) + '</span>'; i = j; continue;
    }
    if (esAlfa(c)) {
      let j = i + 1; while (j < n && esAlfaNum(linea[j])) j++;
      const w = linea.slice(i, j);
      let k = j; while (k < n && linea[k] === ' ') k++;
      const llamada = linea[k] === '(';
      let clase = '';
      if (PY_KW.has(w)) clase = 't-kw';
      else if (prevKw === 'def' || prevKw === 'class') clase = 't-def';
      else if (PY_BI.has(w) || llamada) clase = 't-call';
      out += clase ? '<span class="' + clase + '">' + escH(w) + '</span>' : escH(w);
      prevKw = (w === 'def' || w === 'class') ? w : '';
      i = j; continue;
    }
    out += escH(c); i++;
  }
  return out;
}

// Resaltado generico (toml, sh, json, log): comentario #, cadenas, numeros y
// los literales true/false/null.
const GEN_KW = new Set(['true', 'false', 'null', 'True', 'False', 'None']);
function resaltarGen(linea) {
  let out = '', i = 0; const n = linea.length;
  while (i < n) {
    const c = linea[i];
    if (c === '#') { out += '<span class="t-com">' + escH(linea.slice(i)) + '</span>'; return out; }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n) { if (linea[j] === BS) { j += 2; continue; } if (linea[j] === c) { j++; break; } j++; }
      out += '<span class="t-str">' + escH(linea.slice(i, j)) + '</span>'; i = j; continue;
    }
    if (c >= '0' && c <= '9') {
      let j = i + 1; while (j < n && (esAlfaNum(linea[j]) || linea[j] === '.' || linea[j] === ':' || linea[j] === '-')) j++;
      out += '<span class="t-num">' + escH(linea.slice(i, j)) + '</span>'; i = j; continue;
    }
    if (esAlfa(c)) {
      let j = i + 1; while (j < n && esAlfaNum(linea[j])) j++;
      const w = linea.slice(i, j);
      out += GEN_KW.has(w) ? '<span class="t-kw">' + escH(w) + '</span>' : escH(w);
      i = j; continue;
    }
    out += escH(c); i++;
  }
  return out;
}

// Linea (0-based) donde aparece por primera vez un ancla en el codigo cargado.
let _codeLineas = [];
function lineaDeAncla(a) {
  if (!a) return -1;
  for (let i = 0; i < _codeLineas.length; i++) if (_codeLineas[i].indexOf(a) !== -1) return i;
  return -1;
}
// Salta el panel izquierdo a la primera linea que contiene el ancla.
function saltarAAncla(ancla) {
  if (!ancla) return;
  const filas = [...document.querySelectorAll('#codeBody .cl')];
  filas.forEach(cl => cl.classList.remove('hl'));
  const obj = filas.find(cl => { const tx = cl.querySelector('.tx'); return tx && tx.textContent.indexOf(ancla) !== -1; });
  if (obj) { obj.classList.add('hl'); obj.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
}
// Ruta (de la whitelist) de un fichero por su nombre, en los artefactos ya
// cargados. Hace posible el salto "ir a otro codigo" del diagrama de flujo.
function rutaPorNombre(nombre) {
  if (!artefactos) return null;
  for (const k in artefactos) for (const f of (artefactos[k] || []))
    if (f.ruta && nombreFichero(f.ruta) === nombre && f.existe !== false) return f.ruta;
  return null;
}
function cambiarTabCodigo(ct) {
  document.querySelectorAll('#codeTabs button').forEach(b => b.classList.toggle('active', b.dataset.ct === ct));
  document.getElementById('ctPseudo').hidden = ct !== 'pseudo';
  document.getElementById('ctFlujo').hidden = ct !== 'flujo';
}
// Un nodo del diagrama de flujo: proceso, DECISION (rombo con ramas si/no),
// entrada/salida, o salto a OTRO fichero (chip pulsable).
function flujoNodoHTML(p) {
  const cls = 'flj-n ' + (p.k || 'proc');
  const attr = (p.ancla ? ' data-ancla="' + escSimple(p.ancla) + '"' : '')
    + (p.ir ? ' data-ir="' + escSimple(p.ir) + '"' : '');
  const ln = p.ancla ? lineaDeAncla(p.ancla) : -1;
  const numln = ln >= 0 ? '<span class="ln">línea ' + (ln + 1) + '</span>' : '';
  let cuerpo;
  if (p.k === 'dec') {
    const ramas = (p.si ? '<span class="si">sí · ' + escSimple(p.si) + '</span>' : '')
      + (p.no && p.no !== '—' ? '<span class="no">no · ' + escSimple(p.no) + '</span>' : '');
    cuerpo = numln + '◆ ' + escSimple(p.t)
      + (p.cond ? '<div class="cond">' + escSimple(p.cond) + '</div>' : '')
      + (ramas ? '<div class="flj-ram">' + ramas + '</div>' : '');
  } else if (p.k === 'archivo') {
    cuerpo = escSimple(p.t) + '<div class="cond">&rarr; ' + escSimple(p.ir || '') + '</div>';
  } else {
    cuerpo = numln + escSimple(p.t) + (p.cond ? '<div class="cond">' + escSimple(p.cond) + '</div>' : '');
  }
  return '<div class="' + cls + '"' + attr + '>' + cuerpo + '</div>';
}
function renderFlujo(nombre) {
  const cont = document.getElementById('codeFlujo');
  const f = GUIA_FLUJO[nombre];
  if (!f) { cont.innerHTML = '<p class="dim" style="font-size:.8rem">Este archivo no tiene diagrama de flujo; su recorrido está en el pseudocódigo.</p>'; return; }
  let h = '<div class="flj-tit">' + escSimple(f.titulo || nombre) + '</div><div class="flj">';
  f.pasos.forEach((p, i) => { if (i) h += '<div class="flj-arrow">&darr;</div>'; h += flujoNodoHTML(p); });
  cont.innerHTML = h + '</div>';
}

async function verCodigo(ruta, que) {
  const modal = modalAlFrente();
  const nombre = nombreFichero(ruta);
  document.getElementById('codeTitle').textContent = nombre;
  document.getElementById('codeSub').textContent = ruta;
  const body = document.getElementById('codeBody');
  body.textContent = 'cargando…';
  const guia = GUIA_CODIGO[nombre] || null;
  document.getElementById('codeExplica').textContent =
    (guia && guia.explica) || que || 'Archivo del sistema (solo lectura).';
  cambiarTabCodigo('pseudo');
  document.getElementById('codePseudo').innerHTML = '';
  document.getElementById('codeFlujo').innerHTML = '';
  document.getElementById('codeLlegar').innerHTML = '';
  _codeLineas = [];
  modal.hidden = false;
  // La pestaña de flujo solo se ofrece si este archivo tiene diagrama.
  document.querySelector('#codeTabs button[data-ct="flujo"]').style.display =
    GUIA_FLUJO[nombre] ? '' : 'none';
  try {
    const r = await fetch('/api/archivo?ruta=' + encodeURIComponent(ruta));
    const d = await r.json();
    if (!d || d.contenido == null) {
      body.textContent = (d && d.nota) || 'no disponible';
      document.getElementById('codeLlegar').innerHTML = '<b>Cómo llegar:</b> <code>' + escSimple(ruta) + '</code>';
      return;
    }
    const nl = String.fromCharCode(10);
    _codeLineas = String(d.contenido).split(nl);
    const esPy = nombre.slice(-3) === '.py';
    const st = { tq: null };
    body.innerHTML = _codeLineas.map((l, i) => {
      const tx = esPy ? resaltarPy(l, st) : resaltarGen(l);
      return '<div class="cl" data-i="' + i + '"><span class="ln">' + (i + 1) + '</span><span class="tx">' + (tx || ' ') + '</span></div>';
    }).join('');
    document.getElementById('codeSub').textContent =
      ruta + '  ·  ' + (d.bytes || 0) + ' bytes' + (d.truncado ? ' · truncado a 512 KB' : '');
    // Pseudocodigo con el numero de linea real de cada paso.
    const ol = document.getElementById('codePseudo');
    if (guia && guia.pseudo) {
      ol.innerHTML = guia.pseudo.map(p => {
        const ln = lineaDeAncla(p.ancla);
        const sub = p.ancla
          ? '<small>' + escSimple(p.ancla) + (ln >= 0 ? ' · línea ' + (ln + 1) : '') + '</small>' : '';
        return '<li data-ancla="' + escSimple(p.ancla || '') + '">' + escSimple(p.t) + sub + '</li>';
      }).join('');
    } else {
      ol.innerHTML = '<li class="nolink">Este archivo se muestra tal cual a la izquierda; su recorrido está en el diagrama de flujo.</li>';
    }
    // Como llegar: la ruta exacta y el comando para abrir/editar el fichero.
    const editar = (guia && guia.editar) || '';
    document.getElementById('codeLlegar').innerHTML =
      '<b>Cómo llegar:</b> <code>' + escSimple(ruta) + '</code>'
      + (editar ? '<span class="cmd">' + escSimple(editar) + '</span>' : '');
    renderFlujo(nombre);
  } catch (e) {
    body.textContent = 'error al cargar el archivo';
  }
}

// Pestañas del panel derecho: pseudocodigo vs diagrama de flujo.
on('codeTabs', 'click', (ev) => {
  const b = ev.target.closest('button[data-ct]');
  if (b) cambiarTabCodigo(b.dataset.ct);
});
// Al pulsar un paso del pseudocodigo: resaltar y saltar a su linea.
on('codePseudo', 'click', (ev) => {
  const li = ev.target.closest('li[data-ancla]');
  if (!li) return;
  document.querySelectorAll('#codePseudo li').forEach(x => x.classList.remove('sel'));
  li.classList.add('sel');
  saltarAAncla(li.getAttribute('data-ancla'));
});
// Nodos del diagrama de flujo: 'archivo' carga otro fichero; con ancla, salta.
on('codeFlujo', 'click', async (ev) => {
  const n = ev.target.closest('.flj-n');
  if (!n) return;
  if (n.dataset.ir) {
    const otra = rutaPorNombre(n.dataset.ir);
    if (otra) { await verCodigo(otra, ''); return; }
  }
  if (n.dataset.ancla) { cambiarTabCodigo('pseudo'); saltarAAncla(n.dataset.ancla); }
});
on('codeClose', 'click', cerrarModal);
on('codeModal', 'click', (ev) => { if (ev.target.id === 'codeModal') cerrarModal(); });
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') cerrarModal();
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
  // Captura degradada: drops subiendo ahora o algun PCAP ilegible desde el
  // arranque del motor. No es un servicio caido, pero tampoco "todo en marcha".
  const al = status.alcance || {};
  const cm = status.capture_metrics;
  const dropsSube = !!(cm && cm.drops_estado && cm.drops_estado.subiendo);
  const captDegradada = dropsSube || (al.pcaps_ilegibles || 0) > 0;
  const el = document.getElementById('sideState');
  let clase = 'ok', texto = 'Live', detalle = 'Motor en vivo: todo en marcha';
  if (caidos.length) { clase = 'bad'; texto = caidos.length + ' down'; detalle = caidos.length + ' servicio(s) caído(s)'; }
  else if (!cal) { clase = 'warn'; texto = 'No calib.'; detalle = 'Sin calibrar en esta red'; }
  else if (captDegradada) { clase = 'warn'; texto = 'Degraded'; detalle = 'Captura degradada · ver Alcance'; }
  el.className = 'side-state ' + clase;
  el.title = detalle;
  document.getElementById('sideStateText').textContent = texto;

  const c = status.counters || {};
  const alertas = (c.acciones_relevantes != null) ? c.acciones_relevantes
    : (c.alert_model || 0) + (c.alert_auth_heuristic || 0);
  ultimoPillHora = alertas;
  pintarPillAlertas();
}

let ultimoPillHora = 0;
function pintarPillAlertas() {
  const pill = document.getElementById('navAlertPill');
  const lb = document.getElementById('limpiarBtn'), ae = document.getElementById('alertasEscoba');
  if (lb && ae) ae.hidden = lb.hidden;
  if (!pill) return;
  let n = ultimoPillHora;
  if (limpioDesde) n = agruparEpisodios((lastDecisions || []).filter(d => accionDeDecision(d) !== 'PERMIT'
    && !enListaBlanca(d.entity_ip) && (d.logged_at || 0) >= limpioDesde)).length;
  pill.hidden = n === 0;
  pill.textContent = n;
}

// --- Navegacion por paginas: una seccion a la vez --------------------------
// Antes todo era una sola pagina larga y el menu solo hacia scroll (con un
// scrollspy que al desplazarse no cuadraba con lo que se veia). Ahora al pulsar
// el menu se muestra SOLO esa seccion, como paginas, y el enlace activo siempre
// coincide con el contenido. Respeta el atributo hidden del modo operativo.
const enlaces = new Map([...document.querySelectorAll('#nav a[data-sec]')].map(a => [a.dataset.sec, a]));
const seccionesPag = new Map([...document.querySelectorAll('.wrap > section[id]')].map(s => [s.id, s]));
// Titulo de cada seccion (el h2 de su cabecera), para nombrar los enlaces.
const SEC_TITULO = new Map([...seccionesPag.entries()].map(([id, s]) => {
  const h = s.querySelector('.sec-head h2');
  return [id, h ? h.textContent.trim() : id];
}));
// Vistas relacionadas: al pie de cada seccion, enlaces a las que siguen el hilo.
// Pensado para que desde cualquier vista se salte a la que uno suele querer ver
// despues. Solo se muestran las que existen y no estan ocultas por el modo.
const RELACIONES = {
  's-escenario':   ['s-alertas', 's-decisiones', 's-bloqueos'],
  's-salud':       ['s-alertas', 's-actividad', 's-decisiones'],
  's-actividad':   ['s-alertas', 's-decisiones', 's-bloqueos'],
  's-alertas':     ['s-decisiones', 's-bloqueos', 's-scores'],
  's-decisiones':  ['s-alertas', 's-scores', 's-bloqueos'],
  's-bloqueos':    ['s-alertas', 's-decisiones', 's-despliegue'],
  's-scores':      ['s-alertas', 's-decisiones', 's-modelo'],
  's-topologia':   ['s-despliegue', 's-variables', 's-vivo'],
  's-despliegue':  ['s-topologia', 's-bloqueos', 's-salud'],
  's-alcance':     ['s-topologia', 's-modelo', 's-variables'],
  's-variables':   ['s-vivo', 's-decisiones', 's-modelo'],
  's-vivo':        ['s-variables', 's-decisiones', 's-topologia'],
  's-modelo':      ['s-scores', 's-comparacion'],
  's-aprendizaje': ['s-modelo', 's-scores', 's-comparacion'],
  's-comparacion': ['s-modelo', 's-simulacion', 's-decisiones'],
  's-simulacion':  ['s-comparacion', 's-decisiones', 's-actividad'],
};
function pintarRelaciones(id) {
  const sec = seccionesPag.get(id);
  if (!sec) return;
  const rel = (RELACIONES[id] || []).filter(r => {
    const s = seccionesPag.get(r);
    return s && !s.hidden;
  });
  let foot = sec.querySelector(':scope > .rel-vistas');
  if (!rel.length) { if (foot) foot.remove(); return; }
  if (!foot) { foot = document.createElement('div'); foot.className = 'rel-vistas'; sec.appendChild(foot); }
  foot.innerHTML = '<span class="rel-lbl">Vistas relacionadas</span>'
    + rel.map(r => `<a href="#${r}" class="rel-link">${escSimple(SEC_TITULO.get(r) || r)} &rarr;</a>`).join('');
}
function primeraVisible() {
  for (const [id, s] of seccionesPag) { if (!s.hidden) return id; }
  return seccionesPag.keys().next().value;
}
// Frase de contexto bajo el titulo de cada seccion (la cabecera nombra la
// seccion; «solo lectura» ya lo dice una vez la barra lateral).
const SEC_SUB = {
  's-escenario': 'Un ataque por capa, o un falso positivo, seguido de la detección a la aplicación',
  's-salud': 'Estado general, cifras de la última hora y pulso de la ingesta',
  's-actividad': 'Volumen analizado y acciones por minuto u hora',
  's-alertas': 'Anomalías del modelo y alertas de reglas, con su acción',
  's-decisiones': 'Cada ventana decidida, con su motivo y su evidencia',
  's-bloqueos': 'Decisiones de limitación y bloqueo, publicación y caducidad',
  's-scores': 'Cuánto margen deja el tráfico respecto al umbral vigente',
  's-despliegue': 'Dónde corre cada componente y de dónde sale su estado',
  's-alcance': 'Qué observa CyberFlow, dónde responde y qué no puede confirmar',
};
function mostrarSeccion(id, subir) {
  const sec = seccionesPag.get(id);
  if (!sec || sec.hidden) id = primeraVisible();
  seccionesPag.forEach((s, k) => s.classList.toggle('pag-activa', k === id));
  enlaces.forEach((a, k) => a.classList.toggle('active', k === id));
  if (id === 's-topologia' && typeof renderFlujoBar === 'function') renderFlujoBar();
  const ht = document.getElementById('hTitulo'), hs = document.getElementById('hSub');
  if (ht) ht.textContent = SEC_TITULO.get(id) || 'CyberFlow';
  if (hs) hs.textContent = 'CyberFlow · ' + (SEC_SUB[id] || 'motor en vivo');
  pintarRelaciones(id);
  try { history.replaceState(null, '', '#' + id); } catch (e) { /* sin hash */ }
  if (subir !== false) window.scrollTo({ top: 0, behavior: 'auto' });
  // El Mapa se dibuja tambien mientras su seccion esta oculta (display:none ->
  // ancho 0 -> encaje al minimo). Al abrirlo, reajustar al ancho real.
  if (id === 's-topologia' && typeof aplicarZoom === 'function' && topoZoom == null) {
    setTimeout(aplicarZoom, 60);
  }
}
// Un solo delegado cubre el menu y los enlaces de contenido (p.ej. "Ver en
// vivo" del diagrama), todos con href="#s-...".
document.addEventListener('click', (ev) => {
  const a = ev.target.closest('a[href^="#s-"]');
  if (!a) return;
  const id = (a.getAttribute('href') || '').slice(1);
  if (!seccionesPag.has(id)) return;
  ev.preventDefault();
  mostrarSeccion(id);
});
// Seccion inicial: la del hash si es valida y visible; si no, la primera visible.
const hashInicial = (location.hash || '').slice(1);
mostrarSeccion(seccionesPag.has(hashInicial) ? hashInicial : primeraVisible());

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

// Serie reciente de una variable: el maximo entre entidades en cada una de las
// ultimas ventanas del dataset. Con rango del oro, lo que lo supera va en ambar.
function varFuera(v) {
  const m = v.muestra;
  if (!m || !m.ultimo || !v.rango) return false;
  return m.ultimo.valor > v.rango[1] || m.ultimo.valor < v.rango[0];
}
function varSerieSVG(v, w, h, clase) {
  const m = v.muestra;
  if (!m || !m.serie || m.serie.length < 2) return '';
  const s = m.serie;
  let lo = Math.min(...s), hi = Math.max(...s);
  if (v.rango && clase) { lo = Math.min(lo, v.rango[0]); hi = Math.max(hi, v.rango[1]); }
  if (hi === lo) { hi = lo + 1; }
  const y = val => (h - 3 - (val - lo) / (hi - lo) * (h - 6)).toFixed(1);
  const pts = s.map((val, i) => (i * w / (s.length - 1)).toFixed(1) + ',' + y(val)).join(' ');
  let g = '';
  if (v.rango && clase) {
    const y1 = parseFloat(y(v.rango[1])), y0 = parseFloat(y(v.rango[0]));
    g += `<rect x="0" y="${y1}" width="${w}" height="${Math.max(1, y0 - y1).toFixed(1)}" fill="var(--ok)" fill-opacity="0.09"/>`;
    g += `<line x1="0" y1="${y1}" x2="${w}" y2="${y1}" stroke="var(--ok)" stroke-opacity="0.55" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/>`;
  }
  const color = varFuera(v) ? 'var(--amber)' : capaColor(v.layer);
  g += `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
  return `<svg${clase ? ' class="' + clase + '"' : ''} viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Serie reciente de ${varEsc(v.name)}">${g}</svg>`;
}
function varAhoraHTML(v) {
  const m = v.muestra;
  if (!m || !m.ultimo) return '<span class="vs"><span class="sin">sin dato</span></span>';
  const fuera = varFuera(v);
  return `<span class="vs${fuera ? ' fuera' : ''}" title="${fuera ? 'Fuera del rango normal del conjunto de oro' : 'Máximo entre entidades en la última ventana del dataset'}">`
    + varSerieSVG(v, 96, 22, '') + varFmt(m.ultimo.valor) + '</span>';
}

function varDetalleHTML(v) {
  const m = v.muestra;
  let html = '<div class="var-det">';
  if (v.senal) html += `<p>${varEsc(v.senal)}</p>`;

  if (!m) {
    html += '<p class="var-vacio" style="padding:0">Sin muestra: el dataset todavía no existe o no contiene esta variable. No se inventa ningún ejemplo.</p>';
    return html + '</div>';
  }

  if (m.serie && m.serie.length > 1) {
    html += varSerieSVG(v, 600, 76, 'var-serie');
    html += '<div class="stats">'
      + `<span>última ventana <b>${m.ultimo ? varEsc(String(m.ultimo.ventana).slice(11, 19)) : '—'}</b></span>`
      + `<span>máximo ahora <b>${m.ultimo ? varFmt(m.ultimo.valor) : '—'}</b>${m.ultimo ? ' en ' + varEsc(m.ultimo.entidad) : ''}</span>`
      + (v.rango ? `<span>rango normal (oro) <b>${varFmt(v.rango[0])} a ${varFmt(v.rango[1])}</b></span>` : '<span>sin rango del oro</span>')
      + (varFuera(v) ? '<span style="color:var(--amber)"><b style="color:var(--amber)">fuera del rango</b></span>' : '')
      + `<span>${m.serie.length} ventanas en la serie</span>`
      + '</div>';
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
      + varAhoraHTML(v)
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
  if (d && varDatos.variables.some(v => v.rango)) {
    const nf = varDatos.variables.filter(varFuera).length;
    txt += nf ? ` · ${nf} variable${nf === 1 ? '' : 's'} fuera del rango normal del oro` : ' · todas dentro del rango normal del oro';
  }
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

// Modal "ojito": cómo se genera el tráfico normal de cada perfil.
(function(){
  var M = document.getElementById('pmodal');
  if (!M) return;
  var DOM = 'ad · srv · intranet · erp · correo · wiki  (todos .francos-sac.com)';
  var P = {
    ofimatica:  { ip:'10.10.20.21', ritmo:'~3 s',  exp:'Oficina típica: mezcla de web, DNS, API y HTTPS a tasa baja y estable.', acc:'web_pequena·50, web_media·20, dns·25, api_ok·15, api_auth·3, api_404·4, https·20, ping·5' },
    navegacion: { ip:'10.10.20.22', ritmo:'~1,5 s', exp:'Navegación intensa pero humana: variedad de destinos y algún abandono.', acc:'web_pequena·40, web_grande·25, https·35, dns·30, dns_inexistente·4, api_ok·10, abandono·6' },
    descargas:  { ip:'10.10.20.23', ritmo:'~8 s',  exp:'Transferencias grandes espaciadas: muchos bytes, pocos flujos.', acc:'web_grande·60, web_media·25, https·10, dns·5' },
    aplicacion: { ip:'10.10.20.24', ritmo:'~2 s',  exp:'Cliente de aplicación/API: patrón repetitivo con algún error 500 normal.', acc:'api_ok·45, api_post·25, api_500·6, api_lento·8, https·10, dns·10' },
    ligero:     { ip:'10.10.20.25', ritmo:'~12 s', exp:'Uso esporádico: tasa muy baja, pocas acciones.', acc:'dns·40, api_ok·25, web_pequena·20, ping·15' },
    erratico:   { ip:'10.10.20.26', ritmo:'~5 s',  exp:'Ráfagas y silencios a propósito: ensancha la línea base para que el modelo no la aprenda demasiado estrecha.', acc:'web_pequena·25, web_grande·15, dns·20, api_ok·15, puerto_cerrado·10, abandono·8, ping·7  (+ráfagas)' }
  };
  function esc(s){ return String(s).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;'); }
  function abrir(id){
    var p = P[id]; if (!p) return;
    var cmd = 'python3 clientes_lab.py --perfil ' + id + ' --origen ' + p.ip;
    document.getElementById('pmodalTit').textContent = 'Tráfico normal · ' + id;
    document.getElementById('pmodalBody').innerHTML =
      '<p class="lede-small">' + esc(p.exp) + '</p>'
    + '<div class="esc-code">' + esc(cmd) + '</div>'
    + '<dl>'
    + '<dt>Acciones que genera (peso relativo)</dt><dd>' + esc(p.acc) + '</dd>'
    + '<dt>Ritmo entre acciones</dt><dd>' + esc(p.ritmo) + ' (aleatorio alrededor de ese valor)</dd>'
    + '<dt>Dominios internos</dt><dd>' + esc(DOM) + '</dd>'
    + '</dl>'
    + '<p class="toolbar-hint">Cómo se genera (clientes_lab.py): elige una acción al azar según su peso y espera un tiempo aleatorio (distribución exponencial) alrededor del ritmo — por eso parece humano. Cada perfil se liga a UNA IP porque el motor puntúa por IP.</p>';
    M.classList.add('open');
  }
  function cerrar(){ M.classList.remove('open'); }
  document.addEventListener('click', function(e){
    var b = e.target.closest ? e.target.closest('.ojo') : null;
    if (b) { abrir(b.getAttribute('data-perfil')); return; }
    if (e.target === M || (e.target.closest && e.target.closest('.pmodal-x'))) cerrar();
  });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') cerrar(); });
})();
}

// Escenarios: catalogo estatico, se pide una vez (solo el admin tiene la seccion).
if (document.getElementById('simGrid')) cargarEscenarios();

// ---- Comparacion con Suricata: la tabla la calcula el evaluador del servidor
// (scripts/evaluacion/comparacion.py) desde el fichero de episodios.
function cmpCelda(c) {
  if (!c || c.n === 0) return '<td class="cmp-nm">no medido</td>';
  const coma = (v) => String(v).split('.').join(',');
  let t = c.detectados + '/' + c.n;
  if (c.detectados) {
    t += c.latencia_min_s === c.latencia_max_s ? ' · ' + coma(c.latencia_mediana_s) + ' s'
      : ' · ' + coma(c.latencia_mediana_s) + ' s [' + coma(c.latencia_min_s) + '–' + coma(c.latencia_max_s) + ']';
  }
  const cls = c.detectados === c.n ? 'cmp-bien' : (c.detectados === 0 ? 'cmp-mal' : '');
  return '<td class="num r ' + cls + '">' + t + '</td>';
}

const CMP_ESC = { l4: 'L4 · Escaneo de puertos', l7: 'L7 · Abuso HTTP', l3: 'L3 · Inundación ICMP',
                 l7dns: 'L7 · DNS de alta entropía', fp: 'Cliente legítimo intenso' };
function cmpTarjeta(c) {
  const s = c.suricata || {}, f = c.cyberflow || {};
  const titulo = CMP_ESC[c.escenario] || (c.escenario || 'Comparación');
  const top = (s.top || []).slice(0, 3).map(x => '<li><b>' + x.n + '</b>' + varEsc(x.firma) + '</li>').join('');
  const desg = (f.desglose || []).map(x => '<li><b>' + varEsc(x.n) + '</b>ventanas ' + varEsc(x.accion) + ' · ' + varEsc(x.origen) + '</li>').join('');
  const legit = c.escenario === 'fp';
  // «SURICATA STREAM/HTTP/DECODER…» son eventos del propio motor de Suricata (anomalías de flujo o
  // de protocolo), no firmas de ataque; las de ET Open/GPL sí describen una amenaza.
  const topS = s.top || [];
  // ET INFO / GPL INFO tampoco describen un ataque: son avisos informativos (p. ej. «Web Crawl using Curl»).
  const deMotor = topS.filter(x => /^SURICATA |^(ET|GPL) INFO /.test(x.firma)).reduce((a, x) => a + x.n, 0);
  const soloMotor = topS.length > 0 && deMotor === topS.reduce((a, x) => a + x.n, 0);
  let veredicto, clase;
  if (legit) {
    veredicto = f.con_accion ? 'CyberFlow actuó sobre tráfico legítimo: falso positivo.' : 'Tráfico legítimo: CyberFlow <b>no actúa</b>'
      + (s.alertas ? '; Suricata emite ' + s.alertas + ' alerta(s) que alguien tendría que revisar' + (soloMotor ? ' (de flujo e informativas, ninguna de ataque).' : '.') : '; Suricata tampoco alerta.');
    clase = f.con_accion ? '' : 'bien';
  } else if (f.con_accion && (!s.alertas || soloMotor)) {
    veredicto = (s.alertas ? 'Suricata no tiene <b>ninguna firma de ataque</b> para esto: solo eventos de flujo (SURICATA STREAM/HTTP) e informativos (ET INFO). '
                           : 'Suricata <b>no tiene firma</b> para esto. ')
      + 'CyberFlow lo identifica y <b>responde</b>' + (f.aplicada ? ' (' + varEsc(f.aplicada.accion) + ' aplicado en srv-dmz a las ' + varEsc(f.aplicada.hora) + ')' : '') + '.';
    clase = 'bien';
  } else if (f.con_accion && s.alertas > 50 * Math.max(1, f.con_accion)) {
    veredicto = 'Los dos lo ven. Suricata emite <b>' + s.alertas.toLocaleString('es') + ' alertas</b> (una por paquete) que alguien tiene que leer; '
      + 'CyberFlow lo resume en ' + f.con_accion + ' ventanas y <b>responde</b>' + (f.aplicada ? ' (' + varEsc(f.aplicada.accion) + ' aplicado a las ' + varEsc(f.aplicada.hora) + ')' : '') + '.';
    clase = 'bien';
  } else if (f.con_accion) {
    veredicto = 'Los dos lo ven. Suricata solo alerta; CyberFlow además <b>responde</b>' + (f.aplicada ? ' (' + varEsc(f.aplicada.accion) + ' aplicado en srv-dmz a las ' + varEsc(f.aplicada.hora) + ')' : '') + '.'; clase = 'bien';
  } else {
    veredicto = 'CyberFlow no actuó en este intervalo.'; clase = 'neutro';
  }
  return '<article class="cmp-card"><header><b>' + varEsc(titulo) + '</b><span class="ip">' + varEsc(c.ip) + '</span>'
    + '<span class="cuando">' + fmtTime(c.desde) + '–' + fmtTime(c.hasta) + (c.pcap && c.pcap.paquetes != null ? ' · ' + c.pcap.paquetes + ' paquetes' : '') + '</span></header>'
    + '<div class="cmp-dos"><div class="cmp-lado"><span class="quien">Suricata ' + varEsc(s.version || '') + ' · ' + (s.firmas ? s.firmas.toLocaleString('es') + ' firmas' : '') + '</span>'
    + '<span class="cifra">' + (s.alertas || 0) + '<small>alertas · ' + (s.firmas_distintas || 0) + ' firmas distintas</small></span>'
    + (top ? '<ul>' + top + '</ul>' : '<ul><li>ninguna firma disparó</li></ul>')
    + '<span class="ev">' + varEsc(s.evidencia || '') + '</span></div>'
    + '<div class="cmp-lado"><span class="quien">CyberFlow · modelo + reglas</span>'
    + '<span class="cifra">' + (f.con_accion || 0) + '<small>de ' + (f.ventanas || 0) + ' ventanas con acción</small></span>'
    + '<ul>' + (f.primera ? '<li><b>' + varEsc(f.primera.hora) + '</b>primera: ' + varEsc(f.primera.accion) + ' · ' + varEsc([f.primera.modelo, f.primera.regla].filter(Boolean).join(' + ')) + '</li>' : '<li>ninguna ventana pidió acción</li>')
    + desg + (f.aplicada ? '<li><b>' + varEsc(f.aplicada.hora) + '</b>' + varEsc(f.aplicada.accion) + ' aplicado en srv-dmz (acuse)</li>' : '') + '</ul>'
    + '<span class="ev">' + varEsc(f.evidencia || '') + '</span></div></div>'
    + '<footer class="' + clase + '">' + veredicto + '</footer></article>';
}

async function cargarComparacion() {
  const tb = document.getElementById('cmpTabla');
  const vivo = document.getElementById('cmpVivo');
  if (!tb) return;
  try {
    const r = await (await fetch('/api/comparacion')).json();
    const lista = r.en_vivo || [];
    if (vivo) {
      vivo.innerHTML = lista.length ? lista.map(cmpTarjeta).join('')
        : '<p class="estado-vacio">Aún no hay comparaciones. Se generan al final de cada escenario de la demo.</p>';
      const sub = document.getElementById('cmpVivoSub');
      if (sub) sub.textContent = lista.length ? lista.length + ' · la más reciente primero · evidencia en Sensor1 ~/feed/comparaciones/' : '';
    }
    if (r.error) { tb.innerHTML = '<tr class="empty-row"><td colspan="5">' + varEsc(r.error) + '</td></tr>'; return; }
    const conds = ['suricata', 'modelo', 'heuristicos', 'combinado'];
    let html = r.por_familia.map(f => '<tr><td>' + varEsc(f.nombre) + (f.con_firma ? ' <span class="badge heur">con firma</span>' : '') + '</td>'
      + conds.map(c => cmpCelda(f[c])).join('') + '</tr>').join('');
    html += '<tr class="cmp-total"><td>Total sin firma</td>' + conds.map(c => cmpCelda(r.sin_firma[c])).join('') + '</tr>';
    tb.innerHTML = html;
    document.getElementById('cmpNotas').innerHTML = (r.notas || []).map(n => '<li>' + varEsc(n) + '</li>').join('');
  } catch (e) {
    tb.innerHTML = '<tr class="empty-row"><td colspan="5">No se pudo cargar la comparación.</td></tr>';
  }
}
cargarComparacion();
setInterval(() => { const s = document.getElementById('s-comparacion'); if (s && s.classList.contains('pag-activa')) cargarComparacion(); }, 15000);

// ---- Datos en vivo -------------------------------------------------------
// Captura en vivo al estilo de Wireshark. Tres llamadas, todas solo admin:
//  - /api/vivo/flujo cada 1 s: SOLO lo escrito desde la llamada anterior en el
//    anillo PCAP y en eve.json (el cursor lo guarda esta pagina). Las filas
//    llegan con lo que se sabe de cada registro solo: son provisionales.
//  - /api/vivo cada 10 s: la cadena del motor sobre el tramo reciente. Lo que
//    devuelve se cruza por fichero#trama o por byte y la fila pasa a confirmada,
//    con la entidad que atribuye el motor y el valor real de cada variable.
//  - /api/trazabilidad una vez: la matriz sale del esquema y del codigo.
// El medidor cuenta TODO lo que entra, aunque el filtro oculte filas: es la
// prueba de que la ingesta no se detiene.
const VIVO_MAX = 1500;
const vivo = {
  tab: 'eve', pausa: false, cursor: {}, matriz: null, error: null, enCurso: false,
  filas: {eve: [], pcap: []}, porClave: {eve: new Map(), pcap: new Map()},
  motor: {eve: new Map(), pcap: new Map()}, motorInfo: null,
  num: {eve: 0, pcap: 0}, total: {eve: 0, pcap: 0, aportan: 0},
  estados: {}, tipos: {}, hist: [], prev: null, visto: {eve: null, pcap: null},
  sel: null, desde: null,
};

const vivoHora = (s) => s ? s.slice(11, 19) : '—';
const vivoUso = (f) => f.uso === 'modelo' ? '' : (f.uso === 'conteo' ? ' cnt' : ' l2');
function vivoNum(v) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return Math.abs(n) >= 100 ? n.toFixed(0) : String(+n.toFixed(4));
}
function vivoMB(b) { return b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : (b / 1024).toFixed(0) + ' KB'; }
function vivoTasa(n) { return n >= 100 ? n.toFixed(0) : n.toFixed(1); }

function vivoClase(r, fuente) {
  let c = '';
  if (fuente === 'eve') {
    c = {http: 'c-http', dns: 'c-dns', tls: 'c-tls', alert: 'c-alert'}[r.tipo] || '';
  } else if (r.proto === 'TCP') {
    c = r.flags.includes('RST') ? 'c-rst' : (r.flags.includes('SYN') || r.flags.includes('FIN') ? 'c-syn' : 'c-tcp');
  } else if (r.proto === 'UDP') {
    c = (r.puerto_src === 53 || r.puerto_dst === 53) ? 'c-dns' : 'c-udp';
  } else if (r.proto === 'ICMP') c = 'c-icmp';
  else if (r.proto === 'ARP') c = 'c-arp';
  return c + (r.estado === 'aporta' ? '' : ' c-fuera');
}

function vivoPasa(r, q) {
  if (!q) return true;
  const m = vivo.motor[vivo.tab].get(r.k);
  const feats = (m ? m.features : r.aportes) || [];
  const txt = [r.entidad, m && m.entidad, r.ip_src, r.ip_dst, r.origen, r.destino, r.evento, r.info,
    r.proto, r.tipo, r.flags, r.mac_src, r.vlan, r.estado].concat(feats.map(f => f.feature)).join(' ').toLowerCase();
  return txt.includes(q);
}

// Variable, ventana y valor: una linea por variable en tres columnas alineadas.
// En la lista van las dos mas especificas; todas, en el detalle (clic en la fila).
// Las genericas (toda trama suma a packet_rate y byte_rate) van al final.
const VIVO_GENERICAS = ['packet_rate_10s', 'byte_rate_10s', 'large_ip_ratio_10s', 'flow_attempt_count_30s',
  'http_request_count_60s', 'dns_query_count_60s', 'unique_dst_ip_ratio_30s', 'unique_dst_port_ratio_30s'];
function vivoOrden(feats) {
  const g = (f) => VIVO_GENERICAS.indexOf(f.feature);
  return feats.slice().sort((a, b) => (g(a) >= 0) - (g(b) >= 0) || g(a) - g(b));
}
function vivoCeldasVar(r, fuente) {
  const m = vivo.motor[fuente].get(r.k);
  const todas = vivoOrden(m ? m.features : (r.aportes || []));
  if (!todas.length) return '<td class="txt prov">' + varEsc(r.estado) + '</td><td></td><td></td>';
  const feats = todas.slice(0, 2), resto = todas.length - feats.length;
  const tip = (f) => varEsc(f.feature + ' · ventana ' + f.ventana_s + ' s · uso: ' + f.uso);
  const mas = resto ? '<span class="mas" title="' + varEsc(todas.slice(2).map(f => f.feature).join(', ')) +
    '">+' + resto + '</span>' : '';
  return '<td>' + feats.map((f, i) => '<span class="fl' + vivoUso(f) + '" title="' + tip(f) + '"><b>' +
      varEsc(f.feature) + '</b> ' + varEsc(f.aporte) + (i === 0 ? mas : '') + '</span>').join('') + '</td>' +
    '<td>' + feats.map(f => '<span class="fl"' + (m ? ' title="ventana que termina ' + vivoHora(m.ventana_fin) +
      ' UTC"' : '') + '>' + f.ventana_s + ' s</span>').join('') + '</td>' +
    '<td>' + feats.map(f => m
      ? '<span class="fl conf" title="Valor real de la variable en esa ventana (build_rows del motor)' +
        (f.parcial ? ': PARCIAL, la ventana empieza antes del tramo leído' : '') + '">' +
        vivoNum(f.valor) + (f.parcial ? '*' : '') + '</span>'
      : '<span class="fl pend" title="Pendiente: el motor procesa la trama cuando su fichero se cierra (rota cada 15 s)">…</span>').join('') + '</td>';
}

function vivoFila(r, fuente, nueva) {
  const m = vivo.motor[fuente].get(r.k);
  const ent = m ? '<span class="conf" title="Atribuida por la cadena del motor">' + varEsc(m.entidad) + '</span>'
    : (r.entidad ? '<span class="prov" title="Provisional: sin estado no se sabe quién inició el flujo">' + varEsc(r.entidad) + '</span>' : '—');
  const cls = vivoClase(r, fuente) + (nueva ? ' nueva' : '') + (vivo.sel === r.k ? ' sel' : '');
  const ini = '<tr data-k="' + varEsc(r.k) + '" data-c="' + (m ? 1 : 0) + '" class="' + cls + '"><td>' + r.no + '</td><td>' + varEsc(r.hora) + '</td>';
  if (fuente === 'eve') {
    return ini + '<td>' + ent + '</td><td class="txt" title="' + varEsc(r.info || '') + '">' +
      varEsc(r.evento || r.tipo) + '</td><td>' + varEsc(r.origen) + '<div class="sub">→ ' + varEsc(r.destino) +
      '</div></td>' + vivoCeldasVar(r, fuente) + '<td title="eve.json, byte ' + r.byte + '">@' + r.byte + '</td></tr>';
  }
  const ip = (a, p) => varEsc(a || '') + (p ? ':' + p : '');
  // La entidad no es columna de esta vista: va en el titulo de la IP y en el detalle.
  const entTxt = m ? m.entidad + ' (motor)' : (r.entidad ? r.entidad + ' (provisional)' : 'sin entidad');
  return ini + '<td>' + (r.vlan || '—') + '</td><td>' + varEsc(r.mac_src) + '</td><td title="Entidad: ' +
    varEsc(entTxt) + '">' + ip(r.ip_src, r.puerto_src) + '<div class="sub">→ ' + ip(r.ip_dst, r.puerto_dst) + '</div></td><td>' +
    varEsc(r.proto || '') + '</td><td>' + varEsc(r.flags || '') + '</td><td>' +
    (r.longitud === null ? r.capturada : r.longitud) + '</td>' + vivoCeldasVar(r, fuente) + '<td title="' +
    varEsc(r.fichero) + ', trama ' + r.trama + '">…' + varEsc(r.fichero.replace(/[.]pcap$/, '').slice(-6)) +
    ' #' + r.trama + '</td></tr>';
}

function vivoCabecera(fuente) {
  const cols = fuente === 'eve'
    ? ['No.', 'Hora UTC', 'Entidad', 'Evento', 'Origen → destino', 'Variable · aporte', 'Vent.', 'Valor', 'Fuente']
    : ['No.', 'Hora UTC', 'VLAN', 'MAC origen', 'IP origen → destino', 'Proto', 'Flags', 'Long.',
       'Variable · aporte', 'Vent.', 'Valor', 'Archivo'];
  return '<table><thead><tr>' + cols.map(c => '<th>' + c + '</th>').join('') + '</tr></thead><tbody></tbody></table>';
}

function vivoAlFinal(caja) {
  if (document.getElementById('vivoSeguir').checked) caja.scrollTop = caja.scrollHeight;
}

function renderVivo() {
  const caja = document.getElementById('vivoTabla');
  const res = document.getElementById('vivoResumen');
  const pie = document.getElementById('vivoPie');
  if (!caja) return;
  const q = (document.getElementById('vivoFiltro').value || '').trim().toLowerCase();
  const enMatriz = vivo.tab === 'matriz';
  for (const id of ['vivoTodosLbl', 'vivoSeguir', 'vivoLimpiar']) {
    const el = document.getElementById(id);
    (el.closest('label') || el).style.display = enMatriz ? 'none' : '';
  }
  document.getElementById('vivoDetalle').hidden = enMatriz || !vivo.sel;

  if (enMatriz) {
    if (!vivo.matriz) { caja.innerHTML = '<p class="var-vacio">Cargando matriz…</p>'; return; }
    const filas = vivo.matriz.filter(m => !q || (m.feature + ' ' + m.registro + ' ' + m.fuente).toLowerCase().includes(q));
    res.textContent = 'Fuente → registro → parser → variable → ventana → uso. Construida del esquema ' +
      '(multilayer-v2/v3), de build_rows y del código de heuristicos.py: si cambia el código, cambia la matriz. ' +
      'Las variables de PCAP se calculan después de quitar el plano de control y las copias del espejo.';
    caja.classList.remove('ws');
    caja.innerHTML = '<table class="matriz"><thead><tr><th>Fuente</th><th>Registro que la alimenta</th><th>Parser</th>' +
      '<th>Variable</th><th>Capa</th><th>Ventana</th><th>Uso</th><th>Heurísticos</th></tr></thead><tbody>' +
      filas.map(m => '<tr><td>' + varEsc(m.fuente) + '</td><td>' + varEsc(m.registro) + '</td><td class="m">' +
        varEsc(m.parser) + '</td><td class="m"><b>' + varEsc(m.feature) + '</b></td><td>' + varEsc(m.capa) +
        '</td><td>' + m.ventana_s + ' s</td><td>' + varEsc(m.uso) + '</td><td class="heur">' +
        varEsc((m.heuristicos || []).join(', ') || '—') + '</td></tr>').join('') + '</tbody></table>';
    pie.textContent = filas.length + ' columnas: 28 entran al modelo (v2), 3 de capa 2 se acumulan sin puntuarse (v3) ' +
      'y 3 son conteos que solo leen los heurísticos.';
    return;
  }
  caja.classList.add('ws');
  if (vivo.error) {
    caja.innerHTML = '<p class="var-vacio">' + varEsc(vivo.error) + '</p>';
    res.textContent = ''; pie.textContent = ''; return;
  }
  const fuente = vivo.tab;
  caja.innerHTML = vivoCabecera(fuente);
  const filas = vivo.filas[fuente].filter(r => vivoPasa(r, q));
  caja.querySelector('tbody').innerHTML = filas.map(r => vivoFila(r, fuente, false)).join('');
  if (!filas.length) caja.insertAdjacentHTML('beforeend', '<p class="var-vacio">Esperando registros' +
    (q ? ' que pasen el filtro' : ' que aporten a alguna variable') + '…</p>');
  vivoResumenTexto();
  vivoAlFinal(caja);
}

function vivoResumenTexto() {
  const res = document.getElementById('vivoResumen');
  const pie = document.getElementById('vivoPie');
  const todos = document.getElementById('vivoTodos').checked;
  const cuenta = (o) => Object.entries(o).sort((a, b) => b[1] - a[1]).map(([k, v]) => v + ' ' + k).join(' · ') || 'nada aún';
  const mi = vivo.motorInfo;
  if (vivo.tab === 'eve') {
    res.textContent = 'Recibidos: ' + cuenta(vivo.tipos) + '. ' +
      (todos ? 'Se listan todos.' : 'Se listan los que usa el motor (http, dns, tls).');
    pie.textContent = 'Verde: confirmado por el motor' + (mi ? ' (' + vivoHora(mi.calculado) + ' UTC)' : '') +
      ' · cursiva: provisional · *: ventana parcial.';
  } else {
    res.textContent = 'Recibidas: ' + cuenta(vivo.estados) + '. ' + (todos ? 'Se listan todas.'
      : 'Se listan las de señal propia (SYN, SYN-ACK, RST, ICMP, fragmento, ARP).');
    pie.textContent = '«…»: pendiente hasta que el fichero se cierre (cada 15 s)' +
      (mi && mi.pcap.tramo ? ' · motor al día hasta ' + vivoHora(mi.pcap.tramo.hasta) + ' UTC' : '') +
      ' · colores como en Wireshark.';
  }
}

function vivoIngerir(d) {
  const q = (document.getElementById('vivoFiltro').value || '').trim().toLowerCase();
  const caja = document.getElementById('vivoTabla');
  const tbody = caja ? caja.querySelector('tbody') : null;
  for (const fuente of ['pcap', 'eve']) {
    const f = d[fuente];
    if (f.ultimo_ts) vivo.visto[fuente] = f.ultimo_ts;
    vivo.total[fuente] += fuente === 'pcap' ? f.nuevas : f.nuevos;
    vivo.total.aportan += f.aportan;
    const acum = fuente === 'pcap' ? vivo.estados : vivo.tipos;
    for (const [k, v] of Object.entries(fuente === 'pcap' ? f.estados : f.tipos)) acum[k] = (acum[k] || 0) + v;
    const lista = vivo.filas[fuente], idx = vivo.porClave[fuente];
    const nuevas = [];
    for (const r of f.filas) {
      if (idx.has(r.k)) continue;
      r.no = ++vivo.num[fuente];
      lista.push(r); idx.set(r.k, r); nuevas.push(r);
    }
    while (lista.length > VIVO_MAX) idx.delete(lista.shift().k);
    if (fuente === vivo.tab && tbody && !vivo.error) {
      const html = nuevas.filter(r => vivoPasa(r, q)).map(r => vivoFila(r, fuente, true)).join('');
      if (html) {
        const vacio = caja.querySelector('.var-vacio');
        if (vacio) vacio.remove();
        tbody.insertAdjacentHTML('beforeend', html);
        while (tbody.rows.length > VIVO_MAX) tbody.deleteRow(0);
        vivoAlFinal(caja);
      }
    }
  }
  vivoMedidor(d);
  if (vivo.tab !== 'matriz') vivoResumenTexto();
}

function vivoSpark(id, serie) {
  const svg = document.getElementById(id);
  if (!svg) return;
  const max = Math.max(1, ...serie);
  const pts = serie.map((v, i) => (i * 120 / Math.max(1, serie.length - 1)).toFixed(1) + ',' + (27 - v / max * 25).toFixed(1));
  svg.innerHTML = serie.length < 2 ? '' : '<polygon points="0,28 ' + pts.join(' ') + ' 120,28"/><polyline points="' + pts.join(' ') + '"/>';
}

function vivoMedidor(d) {
  const ahora = d.servidor, prev = vivo.prev;
  let tp = 0, te = 0, bp = 0, be = 0;
  if (prev) {
    const dt = Math.max(0.2, ahora - prev.servidor);
    tp = d.pcap.nuevas / dt; te = d.eve.nuevos / dt;
    bp = d.pcap.bytes / dt; be = d.eve.bytes / dt;
    vivo.hist.push({p: tp, e: te});
    if (vivo.hist.length > 120) vivo.hist.shift();
  }
  vivo.prev = d;
  if (!vivo.desde) vivo.desde = ahora;
  const txt = (id, s) => { const el = document.getElementById(id); if (el) el.innerHTML = s; };
  txt('vmPcapTasa', prev ? vivoTasa(tp) : '…');
  txt('vmEveTasa', prev ? vivoTasa(te) : '…');
  vivoSpark('vmPcapSpark', vivo.hist.map(h => h.p));
  vivoSpark('vmEveSpark', vivo.hist.map(h => h.e));
  txt('vmPcapPie', d.pcap.activo ? varEsc(d.pcap.activo) + ' · ' + vivoMB(d.pcap.tam_activo) +
    (bp > 0 ? ' <span class="crece">+' + vivoMB(bp) + '/s</span>' : '') : 'sin ficheros en el anillo');
  txt('vmEvePie', d.eve.fichero ? 'eve.json · ' + vivoMB(d.eve.tam) +
    (be > 0 ? ' <span class="crece">+' + vivoMB(be) + '/s</span>' : '') : 'sin eve.json');
  const tot = vivo.total.pcap + vivo.total.eve;
  txt('vmTotal', tot.toLocaleString('es'));
  const min = Math.max(0, Math.round((ahora - vivo.desde) / 60));
  txt('vmTotalPie', vivo.total.pcap.toLocaleString('es') + ' tramas · ' + vivo.total.eve.toLocaleString('es') +
    ' eventos · ' + vivo.total.aportan.toLocaleString('es') + ' aportan · ' + min + ' min');
  // Edad del ultimo registro de cada fuente, con el reloj del sensor.
  const edad = (ts) => ts ? Math.max(0, ahora - ts) : Infinity;
  const ep = edad(vivo.visto.pcap), ee = edad(vivo.visto.eve), peor = Math.max(ep, ee);
  const fmt = (s) => s === Infinity ? 'nunca' : (s < 60 ? 'hace ' + s.toFixed(1) + ' s' : 'hace ' + Math.round(s / 60) + ' min');
  const dot = document.getElementById('vmDot');
  dot.className = 'vm-dot ' + (peor < 5 ? 'ok' : (peor < 30 ? 'lento' : 'parado'));
  txt('vmTitulo', peor < 5 ? 'EN VIVO · entrando datos' : (peor < 30 ? 'Ingesta lenta' : 'Sin datos nuevos'));
  txt('vmSub', 'última trama ' + fmt(ep) + ' · último evento ' + fmt(ee) +
    (d.pcap.omitido_bytes || d.eve.omitido_bytes ? ' · se saltó retraso acumulado' : ''));
}

function vivoDetalle(r, fuente) {
  const caja = document.getElementById('vivoDetalle');
  if (!r) { caja.hidden = true; return; }
  const m = vivo.motor[fuente].get(r.k);
  const kv = (k, v) => '<div class="kv">' + k + ': <b>' + varEsc(String(v)) + '</b></div>';
  const rama = (t, cuerpo, abierta) => '<details' + (abierta ? ' open' : '') + '><summary>' + t + '</summary>' + cuerpo + '</details>';
  let h = '';
  if (fuente === 'pcap') {
    h += rama('Trama ' + r.trama + ' de ' + varEsc(r.fichero) + ': ' + r.capturada + ' bytes capturados',
      kv('Hora (UTC)', r.hora) + kv('Clave', r.k), false);
    h += rama('Ethernet II: ' + varEsc(r.mac_src) + ' → ' + varEsc(r.mac_dst),
      kv('Origen', r.mac_src) + kv('Destino', r.mac_dst), false);
    if (r.vlan) h += rama('802.1Q: VLAN ' + r.vlan, kv('VLAN', r.vlan), false);
    if (r.proto === 'ARP') {
      h += rama('ARP: ' + varEsc(r.info), kv('Emisor', r.ip_src) + kv('Objetivo', r.ip_dst), true);
    } else if (r.longitud !== null) {
      h += rama('IPv4: ' + varEsc(r.ip_src) + ' → ' + varEsc(r.ip_dst),
        kv('Longitud total', r.longitud + ' B') + kv('TTL', r.ttl) + kv('Identificación', r.ip_id) +
        kv('Fragmentada', r.fragmentada ? 'sí' : 'no'), true);
      if (r.proto === 'TCP') h += rama('TCP: ' + r.puerto_src + ' → ' + r.puerto_dst + ' [' + varEsc(r.flags || '—') + ']',
        kv('Flags', r.flags || '—') + kv('Secuencia', r.seq) + kv('Datos', r.datos + ' B'), true);
      else if (r.proto === 'UDP') h += rama('UDP: ' + r.puerto_src + ' → ' + r.puerto_dst, '', false);
      else h += rama(varEsc(r.proto) + ': ' + varEsc(r.info || ''), '', false);
    } else {
      h += rama(varEsc(r.proto || 'otro') + ' (sin IPv4)', '', false);
    }
  } else {
    h += rama('Evento ' + varEsc(r.tipo) + ' en eve.json, byte ' + r.byte, kv('Hora (UTC)', r.hora) +
      kv('Origen', r.origen) + kv('Destino', r.destino) + kv('Protocolo', r.proto) + kv('Resumen', r.info || '—'), true);
    let crudo = r.crudo;
    try { crudo = JSON.stringify(JSON.parse(r.crudo), null, 2); } catch (e) { /* recortado */ }
    h += rama('Línea JSON tal como la escribió Suricata', '<pre>' + varEsc(crudo) + '</pre>', false);
  }
  const feats = m ? m.features : (r.aportes || []);
  const cf = kv('Estado', r.estado) +
    kv('Entidad', m ? m.entidad + ' (atribuida por el motor)' : (r.entidad ? r.entidad + ' (provisional)' : '—')) +
    (m ? kv('Ventana', 'termina ' + vivoHora(m.ventana_fin) + ' UTC') : kv('Motor', 'pendiente: aún no procesado')) +
    feats.map(f => kv(f.feature, f.aporte + ' · ventana ' + f.ventana_s + ' s · ' + f.uso +
      (m ? ' · valor ' + vivoNum(f.valor) + (f.parcial ? ' (parcial)' : '') : ''))).join('');
  h += rama('CyberFlow: ' + (feats.length ? feats.length + ' variable(s)' : 'no aporta') + (m ? ' · confirmada' : ' · provisional'), cf, true);
  caja.innerHTML = h;
  caja.hidden = false;
}

async function vivoPoll() {
  const sec = document.getElementById('s-vivo');
  if (!sec || sec.hidden || !sec.classList.contains('pag-activa') || vivo.pausa || vivo.enCurso) return;
  vivo.enCurso = true;
  try {
    const qs = new URLSearchParams({abierta: '1', todos: document.getElementById('vivoTodos').checked ? '1' : '0'});
    for (const k of ['pf', 'po', 'pn', 'eo']) if (vivo.cursor[k] !== undefined) qs.set(k, vivo.cursor[k]);
    const d = await (await fetch('/api/vivo/flujo?' + qs.toString())).json();
    if (d.error) {
      if (vivo.error !== d.error) { vivo.error = d.error; renderVivo(); }
      document.getElementById('vmTitulo').textContent = 'Sin captura';
      document.getElementById('vmSub').textContent = d.error;
      document.getElementById('vmDot').className = 'vm-dot parado';
      return;
    }
    const habiaError = vivo.error;
    vivo.error = null;
    vivo.cursor = d.cursor;
    if (habiaError) renderVivo();
    vivoIngerir(d);
  } catch (e) {
    document.getElementById('vmTitulo').textContent = 'Sin conexión con el panel';
    document.getElementById('vmDot').className = 'vm-dot parado';
  } finally {
    vivo.enCurso = false;
  }
}

async function vivoMotor() {
  const sec = document.getElementById('s-vivo');
  // Solo con «Datos en vivo» abierta: /api/vivo recorre el anillo PCAP y el eve.json
  // y era lo que mas CPU gastaba en el sensor aunque nadie mirara esta seccion.
  if (!sec || sec.hidden || !sec.classList.contains('pag-activa') || vivo.pausa || vivo.error) return;
  try {
    const d = await (await fetch('/api/vivo?abierta=1&todos=1&limite=3000')).json();
    if (d.error) return;
    vivo.motorInfo = d;
    for (const r of d.tramas) vivo.motor.pcap.set(r.fuente.fichero + '#' + r.fuente.trama, r);
    for (const r of d.eventos) vivo.motor.eve.set(String(r.fuente.byte), r);
    for (const fuente of ['pcap', 'eve']) {
      const mp = vivo.motor[fuente];
      while (mp.size > 8000) mp.delete(mp.keys().next().value);
    }
  } catch (e) { return; }
  // Las filas ya pintadas que ahora tienen confirmacion se repintan en su sitio.
  const caja = document.getElementById('vivoTabla');
  if (vivo.tab === 'matriz' || !caja) return;
  for (const tr of Array.from(caja.querySelectorAll('tbody tr[data-c="0"]'))) {
    if (!vivo.motor[vivo.tab].has(tr.dataset.k)) continue;
    const r = vivo.porClave[vivo.tab].get(tr.dataset.k);
    if (r) tr.outerHTML = vivoFila(r, vivo.tab, false);
  }
  if (vivo.sel && vivo.motor[vivo.tab].has(vivo.sel)) vivoDetalle(vivo.porClave[vivo.tab].get(vivo.sel), vivo.tab);
  vivoResumenTexto();
}

async function vivoCargarMatriz() {
  if (vivo.matriz) return;
  try { vivo.matriz = (await (await fetch('/api/trazabilidad')).json()).filas || []; }
  catch (e) { vivo.matriz = []; }
  renderVivo();
}

if (document.getElementById('vivoTabla')) {
  on('vivoTabs', 'click', (ev) => {
    const b = ev.target.closest('button[data-vtab]');
    if (!b) return;
    vivo.tab = b.dataset.vtab;
    vivo.sel = null;
    document.querySelectorAll('#vivoTabs button').forEach(x => x.classList.toggle('active', x === b));
    renderVivo();
    if (vivo.tab === 'matriz') vivoCargarMatriz();
  });
  on('vivoFiltro', 'input', renderVivo);
  on('vivoTodos', 'change', renderVivo);
  on('vivoSeguir', 'change', () => vivoAlFinal(document.getElementById('vivoTabla')));
  on('vivoPausa', 'click', () => {
    vivo.pausa = !vivo.pausa;
    document.getElementById('vivoPausa').textContent = vivo.pausa ? 'Reanudar' : 'Pausar';
    if (vivo.pausa) {
      document.getElementById('vmTitulo').textContent = 'En pausa';
      document.getElementById('vmDot').className = 'vm-dot';
    } else vivoPoll();
  });
  on('vivoLimpiar', 'click', () => {
    vivo.filas = {eve: [], pcap: []};
    vivo.porClave = {eve: new Map(), pcap: new Map()};
    vivo.sel = null;
    renderVivo();
  });
  on('vivoTabla', 'click', (ev) => {
    const tr = ev.target.closest('tbody tr[data-k]');
    if (!tr || vivo.tab === 'matriz') return;
    vivo.sel = tr.dataset.k;
    document.querySelectorAll('#vivoTabla tr.sel').forEach(x => x.classList.remove('sel'));
    tr.classList.add('sel');
    document.getElementById('vivoSeguir').checked = false;
    vivoDetalle(vivo.porClave[vivo.tab].get(vivo.sel), vivo.tab);
  });
  // Enlaces "Ver en vivo" del diagrama: abren la pestaña de su fuente.
  document.addEventListener('click', (ev) => {
    const a = ev.target.closest('a[data-vtab]');
    if (!a) return;
    const b = document.querySelector('#vivoTabs button[data-vtab="' + a.dataset.vtab + '"]');
    if (b) b.click();
  });
  renderVivo();
  vivoPoll().then(vivoMotor);
  setInterval(vivoPoll, 1000);
  setInterval(vivoMotor, 10000);
}

// ---- Aprendizaje supervisado --------------------------------------------
// Solo lee /api/aprendizaje (el estado que escribe cyberflow_aprendizaje.py).
// Ensena las cuatro defensas con su cifra; promover es un comando para copiar,
// nunca un boton: el panel no cambia el modelo.
const aprPct = (v) => (v === null || v === undefined) ? '—' : (v * 100).toFixed(2) + ' %';
const aprNum = (v, d) => (v === null || v === undefined) ? '—' : Number(v).toFixed(d === undefined ? 3 : d);
const APR_VEREDICTO = {PROMOVIBLE: 'v-ok', NO_PROMOVER: 'v-no', EVALUACION_INCOMPLETA: 'v-inc'};
const APR_LOTE = {aceptado: 'v-ok', aceptado_a_mano: 'v-inc', rechazado: 'v-no', insuficiente: 'v-inc'};

function aprTarjeta(titulo, valor, cls, sub) {
  return '<div class="card ' + (cls || '') + '"><div class="label">' + titulo + '</div>' +
    '<div class="value">' + valor + '</div><div class="sub">' + sub + '</div></div>';
}

// Serie diaria con el limite de la politica. Un punto por noche; lo que falta
// (null) no se une con una linea que afirmaria un valor intermedio.
function graficoDias(svg, dias, series, limites, fmt) {
  if (!svg) return;
  const W = Math.max(280, svg.clientWidth || 420), H = 170;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  if (!dias.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">Sin mediciones todavía</text>`;
    return;
  }
  const X0 = 52, X1 = W - 14, Y0 = 22, Y1 = H - 26;
  let hi = 0;
  series.forEach(s => s.valores.forEach(v => { if (v != null && v > hi) hi = v; }));
  limites.forEach(l => { if (l.valor != null && l.valor > hi) hi = l.valor; });
  hi = hi * 1.18 || 1;
  const px = i => dias.length === 1 ? (X0 + X1) / 2 : X0 + i / (dias.length - 1) * (X1 - X0);
  const py = v => Y1 - v / hi * (Y1 - Y0);
  let g = `<line x1="${X0}" y1="${Y0}" x2="${X0}" y2="${Y1}" stroke="var(--border)"/><line x1="${X0}" y1="${Y1}" x2="${X1}" y2="${Y1}" stroke="var(--border)"/>`;
  [0, hi / 2, hi].forEach(v => {
    g += `<text x="${X0 - 6}" y="${(py(v) + 3).toFixed(1)}" text-anchor="end">${fmt(v)}</text>`;
    if (v) g += `<line x1="${X0}" y1="${py(v).toFixed(1)}" x2="${X1}" y2="${py(v).toFixed(1)}" stroke="var(--border)" stroke-dasharray="2 4"/>`;
  });
  limites.forEach(l => {
    if (l.valor == null) return;
    const y = py(l.valor).toFixed(1);
    g += `<line x1="${X0}" y1="${y}" x2="${X1}" y2="${y}" stroke="var(--danger)" stroke-width="1.2" stroke-dasharray="5 4"/>`;
    g += `<text x="${X1}" y="${(py(l.valor) - 4).toFixed(1)}" text-anchor="end" style="fill:var(--danger)">${l.etq}</text>`;
  });
  series.forEach((s, k) => {
    let tramo = [];
    const cerrar = () => {
      if (tramo.length > 1) g += `<polyline points="${tramo.join(' ')}" fill="none" stroke="${s.color}" stroke-width="1.6" stroke-linejoin="round"/>`;
      tramo = [];
    };
    s.valores.forEach((v, i) => {
      if (v == null) { cerrar(); return; }
      tramo.push(px(i).toFixed(1) + ',' + py(v).toFixed(1));
    });
    cerrar();
    s.valores.forEach((v, i) => {
      if (v == null) return;
      g += `<circle cx="${px(i).toFixed(1)}" cy="${py(v).toFixed(1)}" r="3.2" fill="${s.colores ? s.colores[i] : s.color}"><title>${dias[i]} · ${s.nombre} ${fmt(v)}</title></circle>`;
    });
    g += `<circle cx="${X0 + 6 + k * 100}" cy="9" r="3.2" fill="${s.color}"/><text x="${X0 + 14 + k * 100}" y="12">${s.nombre}</text>`;
  });
  const marcas = dias.length > 2 ? [0, Math.floor((dias.length - 1) / 2), dias.length - 1] : dias.map((d, i) => i);
  marcas.forEach((i, n) => {
    g += `<text x="${px(i).toFixed(1)}" y="${H - 8}" text-anchor="${n === 0 ? 'start' : (n === marcas.length - 1 && marcas.length > 1 ? 'end' : 'middle')}">${String(dias[i]).slice(5)}</text>`;
  });
  svg.innerHTML = g;
}

function renderAprendizaje(e) {
  aprEstado = e;                     // lo leen tambien los nodos de la topologia
  const pie = document.getElementById('aprPie');
  if (!e.disponible) {
    document.getElementById('aprDefensas').innerHTML =
      '<p class="var-vacio">' + varEsc(e.motivo || 'sin datos') + '</p>';
    for (const id of ['aprCandidato', 'aprPolitica', 'aprLotes', 'aprDeriva']) document.getElementById(id).innerHTML = '';
    pie.textContent = '';
    return;
  }
  const p = e.politica, lotes = e.lotes || [], der = e.deriva || [];
  const ul = lotes.length ? lotes[lotes.length - 1] : null;
  const ud = der.length ? der[der.length - 1] : null;
  const uc = e.candidatos.length ? e.candidatos[e.candidatos.length - 1] : null;
  const f = ul ? ul.filas : null;

  document.getElementById('aprDefensas').innerHTML =
    aprTarjeta('1 · Saneamiento', ul ? ul.estado : 'sin lotes',
      ul ? (ul.estado === 'aceptado' ? 'ok' : (ul.estado === 'rechazado' ? 'bad' : 'amber')) : '',
      ul ? ('lote ' + ul.dia + ': ' + f.entrada + ' → ' + f.salida + ' filas · ' + f.contaminadas +
            ' de IPs marcadas · ' + f.atipicas + ' atípicas · PSI máx ' + aprNum(ul.psi_max, 2))
         : (p.activo ? 'el primer lote se cierra a las 00:30 UTC' : 'desactivado: no se cierran lotes')) +
    aprTarjeta('2 · Linaje', e.registro_integro ? 'íntegro' : 'ROTO', e.registro_integro ? 'ok' : 'bad',
      lotes.length + ' lotes registrados con sha256 encadenado · ' + e.lotes_disponibles + ' disponibles para entrenar (un lote rechazado no cuenta)') +
    aprTarjeta('3 · Límite de influencia', Math.round(p.max_fraccion_nueva * 100) + ' % / ' +
      Math.round(p.max_fraccion_ip * 100) + ' %', 'accent',
      'datos nuevos como máximo del entrenamiento / de lo nuevo por IP' +
      (uc && uc.filas ? ' · último candidato: ' + aprPct(uc.filas.fraccion_nueva) + ' nuevo' : '')) +
    aprTarjeta('4 · Deriva', ud && ud.fpr_oro !== undefined ? (e.deriva_sostenida ? 'sostenida' : (ud.senal ? 'señal' : 'estable')) : 'sin medir',
      ud && ud.fpr_oro !== undefined ? (e.deriva_sostenida ? 'bad' : (ud.senal ? 'amber' : 'ok')) : '',
      ud && ud.fpr_oro !== undefined ? ('FPR en oro ' + aprPct(ud.fpr_oro) + ' · PSI de scores ' +
        aprNum(ud.psi_puntuaciones, 2) + ' · anómalo en el lote ' + aprPct(ud.tasa_anomala_lote))
        : (e.oro ? 'se mide cada noche' : 'falta el conjunto de oro'));

  let c = '<p class="var-vacio">Aún no hay candidatos. ' + varEsc(e.proximo ? 'Reentrenamiento pendiente por ' + e.proximo + ', pero no se genera un candidato sin lotes aceptados suficientes (un lote rechazado no cuenta).' : 'Se entrena por cadencia (' + p.cadencia_dias + ' días) o por deriva sostenida.') + '</p>';
  if (!p.activo) {
    c = '<div class="note"><span><strong>Desactivado</strong> (reentrenamiento.activo = false). El modelo en uso no cambia y no se cierran lotes. ' +
      'Para activarlo: crear el conjunto de oro con <code>cyberflow_aprendizaje.py oro --desde &lt;particionado&gt;</code>, poner ' +
      '<code>activo = true</code> y <code>base</code> en [reentrenamiento] y regenerar las unidades (docs/APRENDIZAJE.md).</span></div>';
  }
  if (uc) {
    const r = uc.resultados || {}, va = r.vigente || {}, ca = r.candidato || {};
    const cmd = '.venv/bin/python scripts/modeling/cyberflow_aprendizaje.py --config configs/' +
      (e.toml || 'cyberflow.local.toml') + ' promover ' + uc.id;
    c = '<div class="apr-cand"><div><b class="num">' + varEsc(uc.id) + '</b> ' +
      '<span class="badge ' + (APR_VEREDICTO[uc.veredicto] || '') + '">' + varEsc(uc.veredicto) + '</span></div>' +
      '<div class="sub" style="color:var(--text-dim);font-size:0.78rem;margin-top:0.3rem">' + varEsc(uc.motivo || '') + ' · ' + varEsc(uc.razon || '') + '</div>' +
      '<table><tr><th></th><th>Vigente</th><th>Candidato</th></tr>' +
      '<tr><td>FPR en oro</td><td class="num">' + aprPct(va.fpr_oro) + '</td><td class="num">' + aprPct(ca.fpr_oro) + '</td></tr>' +
      '<tr><td>Detección</td><td class="num">' + aprPct(va.deteccion) + '</td><td class="num">' + aprPct(ca.deteccion) + '</td></tr>' +
      '<tr><td>Detector</td><td class="num">' + varEsc(va.detector || '—') + '</td><td class="num">' + varEsc(ca.detector || '—') + '</td></tr></table>' +
      (uc.veredicto === 'PROMOVIBLE'
        ? '<div style="position:relative"><pre class="topo-cmd">' + varEsc(cmd) + '</pre>' +
          '<button class="sim-copiar apr-copiar" data-cmd="' + varEsc(cmd) + '">copiar</button></div>' +
          '<div class="sub" style="color:var(--text-dim);font-size:0.76rem">Deja copia del .toml; se deshace con «revertir». Después, los dos comandos con sudo que imprime.</div>'
        : '') + '</div>';
  }
  document.getElementById('aprCandidato').innerHTML = c;

  const filasPol = [
    // El valor interno del .toml sigue siendo «supervisado»; lo que significa
    // para quien lee es que nada se promueve sin una persona.
    ['activo', p.activo ? 'sí' : 'no'],
    ['modo', p.modo === 'supervisado'
      ? '<span title="valor en el .toml: supervisado">Promoción con aprobación humana</span>' : varEsc(String(p.modo))],
    ['cadencia', p.cadencia_dias + ' días · mínimo ' + p.dias_minimos + ' lotes'],
    ['deriva', 'PSI > ' + p.psi_alerta + ' o anómalo > ' + aprPct(p.tasa_anomala_max) + ' durante ' + p.dias_deriva + ' días'],
    ['saneamiento', '±' + p.margen_contaminacion_s + ' s de IPs marcadas · atípica en ≥ ' + p.max_variables_atipicas + ' variables · lote fuera si PSI > ' + p.psi_rechazo_lote],
    ['promoción', 'FPR ≤ vigente + ' + aprPct(p.tolerancia_fpr) + ' y detección ≥ vigente'],
    ['restauración', 'se conservan ' + p.conservar_modelos + ' modelos'],
    ['conjunto de oro', e.oro ? (e.oro.filas + ' filas · ' + varEsc(e.oro.sha256.slice(0, 12)) + '…') : 'no creado'],
  ];
  document.getElementById('aprPolitica').innerHTML = '<table>' +
    filasPol.map(x => '<tr><td>' + x[0] + '</td><td class="num">' + x[1] + '</td></tr>').join('') + '</table>';

  document.getElementById('aprLotes').innerHTML = '<table><tr><th>Día</th><th>Estado</th><th>Entrada → salida</th>' +
    '<th>Marcadas</th><th>Atípicas</th><th>PSI máx</th><th>sha256</th></tr>' +
    (lotes.length ? lotes.slice(-10).reverse().map(l => '<tr><td class="num">' + l.dia + '</td>' +
      '<td><span class="badge ' + (APR_LOTE[l.estado] || '') + '">' + l.estado + '</span></td>' +
      '<td class="num">' + l.filas.entrada + ' → ' + l.filas.salida + '</td>' +
      '<td class="num">' + l.filas.contaminadas + '</td><td class="num">' + l.filas.atipicas + '</td>' +
      '<td class="num">' + aprNum(l.psi_max, 2) + '</td><td class="num">' + l.sha256.slice(0, 10) + '…</td></tr>').join('')
      : '<tr class="empty-row"><td colspan="7">Sin lotes todavía</td></tr>') + '</table>';

  const medidas = der.filter(d => d.fpr_oro !== undefined);
  const ult = lotes.slice(-30), med = medidas.slice(-30);
  graficoDias(document.getElementById('aprGLote'), ult.map(l => l.dia),
    [{ nombre: 'PSI máx', color: 'var(--accent)', valores: ult.map(l => l.psi_max),
       colores: ult.map(l => l.estado === 'rechazado' ? 'var(--danger)' : 'var(--accent)') }],
    [{ valor: p.psi_rechazo_lote, etq: 'rechazo ' + p.psi_rechazo_lote }], v => v.toFixed(2).split('.').join(','));
  graficoDias(document.getElementById('aprGPsi'), med.map(d => d.dia),
    [{ nombre: 'PSI', color: 'var(--accent)', valores: med.map(d => d.psi_puntuaciones),
       colores: med.map(d => d.senal ? 'var(--amber)' : 'var(--accent)') }],
    [{ valor: p.psi_alerta, etq: 'alerta ' + p.psi_alerta }], v => v.toFixed(2).split('.').join(','));
  graficoDias(document.getElementById('aprGTasa'), med.map(d => d.dia),
    [{ nombre: 'FPR en oro', color: 'var(--ok)', valores: med.map(d => d.fpr_oro) },
     { nombre: 'anómalo', color: 'var(--accent)', valores: med.map(d => d.tasa_anomala_lote) }],
    [{ valor: p.tasa_anomala_max, etq: 'máx. ' + aprPct(p.tasa_anomala_max) }], v => (v * 100).toFixed(1).split('.').join(',') + ' %');
  document.getElementById('aprDeriva').innerHTML = '<table><tr><th>Día</th><th>FPR en oro</th>' +
    '<th>PSI de scores</th><th>Anómalo en el lote</th><th>ALERT del motor</th><th>Señal</th></tr>' +
    (medidas.length ? medidas.slice(-10).reverse().map(d => '<tr><td class="num">' + d.dia + '</td>' +
      '<td class="num">' + aprPct(d.fpr_oro) + '</td><td class="num">' + aprNum(d.psi_puntuaciones, 2) + '</td>' +
      '<td class="num">' + aprPct(d.tasa_anomala_lote) + '</td><td class="num">' + aprPct(d.tasa_alert_motor) + '</td>' +
      '<td>' + (d.senal ? '<span class="badge v-inc">sí</span>' : '<span class="badge v-ok">no</span>') + '</td></tr>').join('')
      : '<tr class="empty-row"><td colspan="6">Sin mediciones todavía</td></tr>') + '</table>';

  const h = e.historial || [];
  pie.textContent = (e.demo ? 'DATOS DE EJEMPLO (modo demo): no son mediciones. ' : '') +
    'Detector vigente: ' + e.detector_vigente +
    (h.length ? ' · última acción: ' + h[h.length - 1].accion + ' ' + h[h.length - 1].candidato + ' (' + h[h.length - 1].fecha + ')' : ' · sin promociones todavía');
}

async function cargarAprendizaje() {
  try {
    renderAprendizaje(await (await fetch('/api/aprendizaje')).json());
  } catch (err) {
    renderAprendizaje({disponible: false, motivo: 'No se pudo leer el estado: ' + err});
  }
}

on('aprCandidato', 'click', async (ev) => {
  const b = ev.target.closest('.apr-copiar');
  if (!b) return;
  try {
    await navigator.clipboard.writeText(b.dataset.cmd);
    b.textContent = 'copiado ✓';
    setTimeout(() => { b.textContent = 'copiar'; }, 1500);
  } catch (err) {
    b.textContent = 'copia manual';
  }
});

if (document.getElementById('aprDefensas')) {
  cargarAprendizaje();
  // Cambia una vez al dia: cada cinco minutos sobra.
  setInterval(cargarAprendizaje, 300000);
}

// ---- Sesion: quien eres y en que modo miras ------------------------------
// El modo es del ADMIN y solo del admin: alterna entre la vista operativa y la
// de desarrollo. No es un permiso -esta autorizado a las dos- sino una forma de
// quitarse de encima lo que no necesita mientras opera. Por eso vive en
// localStorage y no en la sesion: es preferencia, no autorizacion.
const SESION = JSON.parse(document.getElementById('datosSesion').textContent);
// Alcance NO esta aqui: explica que observa y que no confirma el panel, y eso
// lo necesita quien opera, no solo quien desarrolla.
// G1 (validacion externa, D5): el Mapa pasa a la vista operativa, porque es
// donde se sigue el flujo de una IP.
const DEV_SECS = ['s-variables', 's-vivo', 's-modelo', 's-comparacion', 's-simulacion'];
// G1: en operativo el MENU se queda en cinco entradas (Resumen, Escenario,
// Alertas, Respuestas, Mapa). Estas secciones NO se ocultan: el recorrido
// guiado, «Ver Actividad →», «Ver decisiones →» y las vistas relacionadas
// siguen llevando a ellas. Solo dejan de ocupar sitio en el menu.
const OPS_FUERA_DEL_MENU = ['s-actividad', 's-decisiones', 's-scores', 's-despliegue'];

// Un encabezado de grupo sin enlaces visibles debajo se oculta (p.ej. DATOS,
// MODELO y EVALUACION en el modo operativo).
function pintarGruposNav() {
  let grupo = null, visibles = 0;
  const cerrar = () => { if (grupo) grupo.hidden = visibles === 0; };
  for (const el of document.querySelectorAll('#nav > .nav-grupo, #nav > a')) {
    if (el.classList.contains('nav-grupo')) { cerrar(); grupo = el; visibles = 0; }
    else if (!el.hidden) visibles += 1;
  }
  cerrar();
}

function aplicarModo(modo) {
  const dev = modo === 'desarrollo';
  for (const id of DEV_SECS) {
    const sec = document.getElementById(id);
    if (sec) sec.hidden = !dev;
    const enlace = document.querySelector('#nav a[data-sec="' + id + '"]');
    if (enlace) enlace.hidden = !dev;
  }
  for (const id of OPS_FUERA_DEL_MENU) {
    const enlace = document.querySelector('#nav a[data-sec="' + id + '"]');
    if (enlace) enlace.hidden = !dev;
  }
  // 17-nov: Aprendizaje no se muestra en ningún modo.
  for (const id of ['s-aprendizaje']) {
    const sec = document.getElementById(id); if (sec) sec.hidden = true;
    const enlace = document.querySelector('#nav a[data-sec="' + id + '"]'); if (enlace) enlace.hidden = true;
  }
  pintarGruposNav();
  const b = document.getElementById('modoBtn');
  if (b) {
    b.dataset.modo = modo;
    b.textContent = 'Vista: ' + (dev ? 'Desarrollo' : 'Operación') + ' · cambiar';
  }
  try { localStorage.setItem('cyberflow_modo', modo); } catch (e) { /* sin persistir */ }
  // Si la seccion que se veia quedo oculta al pasar a operativo, saltar a una
  // visible para no dejar el contenido en blanco.
  if (typeof mostrarSeccion === 'function') {
    const activa = [...seccionesPag.values()].find(s => s.classList.contains('pag-activa'));
    if (!activa || activa.hidden) mostrarSeccion(primeraVisible(), false);
    else pintarRelaciones(activa.id);   // refresca el pie segun el modo nuevo
  }
}

const ROL_NOMBRE = { admin: 'Administrador', lector: 'Lector' };
document.getElementById('quien').textContent = SESION.usuario + ' · ' + (ROL_NOMBRE[SESION.rol] || SESION.rol);
pintarGruposNav();
on('navGuia', 'click', (ev) => {
  ev.preventDefault();
  const b = document.getElementById('tourBtn');
  if (b) b.click();
});

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

// ---- Recorrido guiado de la demo -------------------------------------------
// El mismo orden que se defiende en la sustentación: el ataque (Kali) -> la IP
// aparece en Actividad -> su porqué en Decisiones -> la orden firmada en
// Respuestas -> la prueba en el host (consola Herdr SRV-DMZ). Cada paso se pone
// en verde (o en su color de acción) cuando ocurre, con datos de /api/escenario.
const RG_PASOS = [
  { k: 'ataque', t: 'Ataque', sec: 's-escenario', cli: 'Herdr · ORIGEN' },
  { k: 'actividad', t: 'Actividad', sec: 's-actividad', cli: '' },
  { k: 'decisiones', t: 'Decisiones', sec: 's-decisiones', cli: 'Herdr · SENSOR1: mira-motor.sh' },
  { k: 'respuestas', t: 'Respuestas', sec: 's-bloqueos', cli: '' },
  { k: 'host', t: 'Host (CLI)', sec: null, cli: 'Herdr · SRV-DMZ' },
];
let rgPaso = 0, rgOculto = false;
try { rgOculto = sessionStorage.getItem('cf_rg_oculto') === '1'; } catch (e) { /* sin persistir */ }

function rgEstado() {
  // Estado de cada paso: '' pendiente, 'ok' hecho, 'limit'/'alerta' hecho con acción.
  const D = escDatos, s = ESC_CATALOGO.find(x => x.id === (esc && esc.id)) || {};
  const legit = s.tipo === 'tráfico legítimo';
  const filas = (D && D.decisiones) || [];
  const acc = filas.filter(f => f.accion !== 'PERMIT');
  const peor = acc.some(f => f.accion === 'BLOCK') ? 'alerta' : (acc.length ? 'limit' : '');
  const ent = D && D.feed && D.feed.entrada;
  const apl = (D && D.aplicacion) || [];
  const aplicada = apl.some(a => a.regla);
  const liberada = apl.some(a => (a.eventos || []).some(e => e.evento === 'liberada'));
  if (legit) {
    const visto = filas.length > 0, limpio = visto && !acc.length;
    return { ataque: visto ? 'ok' : '', actividad: limpio ? 'ok' : (acc.length ? peor : ''),
             decisiones: limpio ? 'ok' : (acc.length ? peor : ''), respuestas: limpio ? 'ok' : (ent ? peor : ''),
             host: limpio ? 'ok' : (aplicada ? peor : '') };
  }
  return { ataque: filas.length ? 'ok' : '', actividad: acc.length ? peor : '', decisiones: acc.length ? peor : '',
           respuestas: ent ? (ent.accion === 'BLOCK' ? 'alerta' : 'limit') : '',
           host: aplicada ? (apl.find(a => a.regla).regla.accion === 'BLOCK' ? 'alerta' : 'limit') : (liberada ? 'ok' : '') };
}

function rgDetalle(k) {
  // Lo pequeño bajo cada paso: el dato que lo prueba.
  const D = escDatos;
  if (!D) return 'esperando…';
  const filas = D.decisiones || [];
  const acc = filas.filter(f => f.accion !== 'PERMIT');
  const ent = D.feed && D.feed.entrada;
  const apl = (D.aplicacion || []).find(a => a.regla);
  const prim = acc.length ? acc.reduce((a, b) => (a.logged_at < b.logged_at ? a : b)) : null;
  if (k === 'ataque') return filas.length ? filas.length + ' ventanas' : 'lanza el comando';
  if (k === 'actividad' || k === 'decisiones') return prim ? prim.accion + escDelta(prim.logged_at) : (filas.length ? 'todo PERMIT' : '—');
  if (k === 'respuestas') return ent ? ent.accion + ' · caduca ' + fmtTime(ent.hasta) : 'sin orden';
  if (k === 'host') {
    const lib = (D.aplicacion || []).some(a => (a.eventos || []).some(e => e.evento === 'liberada'));
    return apl ? apl.regla.accion + ' en nftables' : (lib ? 'liberada' : 'sin regla');
  }
  return '';
}

function renderRg() {
  const caja = document.getElementById('rg'), abrir = document.getElementById('rgAbrir');
  if (!caja) return;
  const activo = escActivo();
  caja.hidden = !activo || rgOculto;
  // 16-nov: el acceso al recorrido queda siempre a la vista. Sin seguimiento lleva a
  // Escenario (allí se elige y se pulsa «Iniciar seguimiento»); con él, reabre la barra.
  if (abrir) {
    abrir.hidden = activo && !rgOculto;
    abrir.classList.toggle('sin-esc', !activo);
    const t = abrir.querySelector('.rg-txt');
    if (t) t.textContent = activo ? 'Recorrido de la demo' : 'Recorrido de la demo ▸ elegir escenario';
  }
  document.body.classList.toggle('con-rg', activo && !rgOculto);
  if (!activo || rgOculto) return;
  const s = ESC_CATALOGO.find(x => x.id === esc.id) || {};
  document.getElementById('rgEsc').innerHTML = '<span class="k">' + varEsc(s.capa || '') + '</span>' + varEsc(s.nombre || '')
    + '<span class="ip">' + varEsc(esc.ip) + '</span>';
  document.getElementById('rgReloj').textContent = escMmss(Date.now() / 1000 - esc.t0);
  const est = rgEstado();
  document.getElementById('rgPasos').innerHTML = RG_PASOS.map((p, i) =>
    '<li class="' + (est[p.k] || '') + (i === rgPaso ? ' actual' : '') + '"><button type="button" data-tp="' + i + '">'
    + '<span class="num">' + (i + 1) + '</span><span class="lbl"><b>' + (p.k === 'ataque' && ((ESC_CATALOGO.find(x => x.id === (esc && esc.id)) || {}).tipo === 'tráfico legítimo') ? 'Tráfico' : p.t) + '</b><small>' + varEsc(rgDetalle(p.k)) + '</small></span></button></li>').join('');
  const p = RG_PASOS[rgPaso];
  document.getElementById('rgFrase').textContent = (s.rg && s.rg[p.k]) || '';
  const cli = rgCli(p.k, s);
  document.getElementById('rgCli').innerHTML = cli ? '<span class="h">' + varEsc(cli[0]) + '</span>' + varEsc(cli[1]) : '';
  document.getElementById('rgSig').textContent = rgPaso < RG_PASOS.length - 1 ? 'Siguiente →' : 'Ver los 5 pasos';
}

function rgCli(k, s) {
  const ip = esc.ip;
  if (k === 'ataque') return [s.id === 'fp' ? 'CLIENTES $' : 'KALI $', s.comando || ''];
  if (k === 'decisiones') return ['SENSOR1 $', '~/cf-demo/mira-motor.sh ' + ip];
  if (k === 'host') return ['SRV-DMZ $', '~/cf-demo/en-firewall.sh ' + ip];
  return null;
}

function rgResaltar(el) {
  if (!el) return;
  document.querySelectorAll('.rg-foco').forEach(x => x.classList.remove('rg-foco'));
  el.classList.add('rg-foco');
  el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  setTimeout(() => el.classList.remove('rg-foco'), 6000);
}

function rgIr(i) {
  rgPaso = Math.max(0, Math.min(RG_PASOS.length - 1, i));
  const p = RG_PASOS[rgPaso], ip = esc.ip;
  const legit = ((ESC_CATALOGO.find(x => x.id === esc.id) || {}).tipo === 'tráfico legítimo');
  if (p.k === 'ataque') { mostrarSeccion('s-escenario', false); rgResaltar(document.getElementById('escDet')); }
  else if (p.k === 'actividad') {
    mostrarSeccion('s-actividad'); renderTopIps();
    setTimeout(() => rgResaltar(document.querySelector('#topIps tr[data-ip="' + ip + '"]') || document.getElementById('topIps').closest('.tbl-wrap')), 120);
  } else if (p.k === 'decisiones') {
    document.getElementById('ipFilter').value = ip;
    decVista = legit ? 'todas' : 'accion'; pintarDecVista(); renderDecisionsTable();
    mostrarSeccion('s-decisiones');
    setTimeout(() => rgResaltar(document.querySelector('#decisions tr')), 160);
  } else if (p.k === 'respuestas') {
    mostrarSeccion('s-bloqueos');
    setTimeout(() => rgResaltar([...document.querySelectorAll('#blocked tr')].find(tr => tr.textContent.includes(ip))
      || document.getElementById('blocked').closest('.tbl-wrap')), 160);
  } else if (p.k === 'host') {
    mostrarSeccion('s-escenario', false);
    setTimeout(() => rgResaltar(document.querySelector('#escPasos li:last-child')), 120);
  }
  renderRg();
}

on('rgPasos', 'click', (ev) => { const b = ev.target.closest('button[data-tp]'); if (b) rgIr(+b.dataset.tp); });
on('rgSig', 'click', () => {
  if (rgPaso < RG_PASOS.length - 1) rgIr(rgPaso + 1);
  else { mostrarSeccion('s-escenario', false); setTimeout(() => rgResaltar(document.getElementById('escPasos')), 100); }
});
on('rgCerrar', 'click', () => { rgOculto = true; try { sessionStorage.setItem('cf_rg_oculto', '1'); } catch (e) { /* */ } renderRg(); });
on('rgAbrir', 'click', () => {
  if (!escActivo()) { if (typeof mostrarSeccion === 'function') mostrarSeccion('s-escenario', true); return; }
  rgOculto = false; try { sessionStorage.removeItem('cf_rg_oculto'); } catch (e) { /* */ } renderRg(); });
setInterval(renderRg, 1000);
renderRg();

</script>
"""


VIVO_MIN_S = 30.0
_VIVO_LOCK = threading.Lock()
_VIVO_ULTIMO: dict = {}
STATUS_CACHE_S = 3.0
_STATUS_CACHE: dict = {}
_STATUS_LOCK = threading.Lock()
_RENDIMIENTO: dict = {"desde": time.time(), "rutas": {}, "volcado": 0.0}
_RENDIMIENTO_LOCK = threading.Lock()


def medir_ruta(ruta: str, segundos: float, nbytes: int, destino: Path | None) -> None:
    if not ruta.startswith("/api/"):
        ruta = "(pagina)"
    with _RENDIMIENTO_LOCK:
        r = _RENDIMIENTO["rutas"].setdefault(ruta, {"n": 0, "s": 0.0, "max_s": 0.0, "bytes": 0})
        r["n"] += 1
        r["s"] += segundos
        r["max_s"] = max(r["max_s"], segundos)
        r["bytes"] += nbytes
        if destino is None or time.monotonic() - _RENDIMIENTO["volcado"] < 30:
            return
        _RENDIMIENTO["volcado"] = time.monotonic()
        dur = max(1.0, time.time() - _RENDIMIENTO["desde"])
        filas = sorted(({"ruta": k, "peticiones": v["n"], "por_min": round(v["n"] * 60 / dur, 1),
                         "ms_medio": round(1000 * v["s"] / v["n"], 1), "ms_max": round(1000 * v["max_s"]),
                         "cpu_s_por_min": round(v["s"] * 60 / dur, 2),
                         "kb_medio": round(v["bytes"] / v["n"] / 1024, 1)}
                        for k, v in _RENDIMIENTO["rutas"].items()),
                       key=lambda f: -f["cpu_s_por_min"])
        datos = {"desde": _RENDIMIENTO["desde"], "segundos": round(dur), "rutas": filas}
    try:
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(datos, indent=1), encoding="utf-8")
        tmp.replace(destino)
    except OSError:
        pass


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


# Almacen incremental de decisiones (3-nov, segunda version). Antes cada tramo
# (1, 4, 16 y 32 MiB) se volvia a parsear entero cada 2,5 s: en el Sensor1 eso
# era la CPU al 100 % y el panel en 5 GB con 66 hilos esperando. Ahora se parsea
# una vez la cola de DECISIONES_VENTANA_BYTES y despues solo los bytes nuevos;
# cada tramo es un corte por desplazamiento del mismo almacen. La politica del
# modelo se recalcula solo en la zona que las ventanas nuevas pueden cambiar.
# Los dicts se comparten: los llamadores no los modifican.
DECISIONES_CACHE_S = 2.0
DECISIONES_VENTANA_BYTES = 33_554_432
_ALMACENES: dict = {}
_ALMACENES_LOCK = threading.Lock()


def _malloc():
    """glibc: pocas arenas (un servidor con muchos hilos fragmenta mucho) y una
    forma de devolver al sistema la memoria liberada. Nada fuera de Linux."""
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        libc.mallopt(-8, 2)            # M_ARENA_MAX = 2
        return libc
    except (OSError, AttributeError):
        return None


_LIBC = _malloc()
_ULTIMO_TRIM = [0.0]


def _devolver_memoria() -> None:
    if _LIBC is not None and time.monotonic() - _ULTIMO_TRIM[0] > 60:
        _ULTIMO_TRIM[0] = time.monotonic()
        try:
            _LIBC.malloc_trim(0)
        except Exception:              # noqa: BLE001 - es solo higiene de memoria
            pass


def _almacen(log_path: Path) -> dict:
    """Pone al dia el almacen de `log_path` (como mucho cada DECISIONES_CACHE_S)
    y lo devuelve bloqueado por el llamador via a["lock"]."""
    clave = str(log_path)
    with _ALMACENES_LOCK:
        a = _ALMACENES.get(clave)
        if a is None:
            a = _ALMACENES[clave] = {"lock": threading.Lock(), "t": -1e9, "ino": None,
                                     "pos": 0, "resto": b"", "offs": [], "recs": [],
                                     "inicio_partido": False}
    with a["lock"]:
        if time.monotonic() - a["t"] < DECISIONES_CACHE_S:
            return a
        a["t"] = time.monotonic()
        try:
            st = log_path.stat()
        except OSError:
            a.update(ino=None, pos=0, resto=b"", offs=[], recs=[])
            return a
        if a["ino"] != st.st_ino or st.st_size < a["pos"]:          # rotado o truncado
            ini = max(0, st.st_size - DECISIONES_VENTANA_BYTES)
            a.update(ino=st.st_ino, pos=ini, resto=b"", offs=[], recs=[], inicio_partido=ini > 0)
        if st.st_size > a["pos"]:
            with log_path.open("rb") as fh:
                fh.seek(a["pos"])
                datos = fh.read(st.st_size - a["pos"])
            base = a["pos"] - len(a["resto"])
            buf = a["resto"] + datos
            a["pos"] += len(datos)
            ini = 0
            if a["inicio_partido"]:
                nl = buf.find(b"\n")
                ini = nl + 1 if nl >= 0 else len(buf)
                a["inicio_partido"] = nl < 0
            fin = buf.rfind(b"\n")
            if fin < ini:
                a["resto"] = buf[ini:]
                return a
            a["resto"] = buf[fin + 1:]
            nuevos, offs = [], []
            p = ini
            while p <= fin:
                q = buf.index(b"\n", p)
                linea = buf[p:q]
                if b'"decision"' in linea:
                    try:
                        ev = json.loads(linea)
                    except ValueError:
                        ev = None
                    if isinstance(ev, dict) and ev.get("event") == "decision":
                        nuevos.append(ev)
                        offs.append(base + p)
                p = q + 1
            if nuevos:
                recs, offsets = a["recs"], a["offs"]
                previo = recs[-1].get("logged_at", 0) if recs else None
                recs.extend(nuevos)
                offsets.extend(offs)
                t_nuevo = min(float(d.get("logged_at", 0)) for d in nuevos)
                if previo is not None and t_nuevo < float(previo):
                    orden = sorted(range(len(recs)), key=lambda k: recs[k].get("logged_at", 0))
                    a["recs"] = recs = [recs[k] for k in orden]
                    a["offs"] = offsets = [offsets[k] for k in orden]
                # Una ventana nueva puede volver «sostenida» otra de hasta 120 s antes,
                # que a su vez necesita 120 s de contexto: se recalcula desde t-240 s
                # con contexto desde t-360 s y lo anterior se deja como estaba.
                corte, ctx_t = t_nuevo - 2 * VENTANA_SOSTENIDA_S, t_nuevo - 3 * VENTANA_SOSTENIDA_S
                k = len(recs)
                while k > 0 and float(recs[k - 1].get("logged_at", 0)) >= ctx_t:
                    k -= 1
                ctx = recs[k:]
                fijas = [(d, d["politica_modelo"]) for d in ctx
                         if float(d.get("logged_at", 0)) < corte and "politica_modelo" in d]
                anotar_politica_modelo(ctx)
                for d, v in fijas:
                    d["politica_modelo"] = v
            limite = a["pos"] - DECISIONES_VENTANA_BYTES
            if a["offs"] and a["offs"][0] < limite - DECISIONES_VENTANA_BYTES // 8:
                k = bisect.bisect_left(a["offs"], limite)
                del a["offs"][:k]
                del a["recs"][:k]
                _devolver_memoria()
        return a


def _decisiones_tramo(log_path: Path, max_bytes: int) -> list[dict]:
    """Decisiones de los ultimos `max_bytes` del registro, de la mas antigua a la
    mas reciente (copia de la lista; los dicts son compartidos)."""
    a = _almacen(log_path)
    with a["lock"]:
        k = bisect.bisect_left(a["offs"], a["pos"] - max_bytes)
        tramo = a["recs"][k:]
    if _CADENA_V2 is not None:
        _CADENA_V2.anotar(tramo)        # cadena_v2 en cada decision, desde las trazas reales
    return tramo


def read_decisions(log_path: Path, limit: int, max_bytes: int = 1_048_576) -> list[dict]:
    records = _decisiones_tramo(log_path, max_bytes)
    return records[-limit:][::-1]


PERIODO_MAX_BYTES = 33_554_432   # 32 MiB del final del registro
PERIODO_MAX_FILAS = 5000


def consultar_periodo(log_path: Path, desde: float | None, hasta: float | None,
                      limite: int = PERIODO_MAX_FILAS,
                      max_bytes: int = PERIODO_MAX_BYTES) -> dict:
    """Decisiones con ``logged_at`` en [desde, hasta], mas recientes primero.

    Devuelve tambien lo que de verdad se pudo consultar: desde cuando hay
    registro en el tramo leido y si se corto por el tope de filas. Asi el panel
    dice «periodo consultado» y no deja creer que un hueco es ausencia de
    decisiones cuando en realidad el registro no llegaba tan atras.
    """
    todas = read_decisions(log_path, limit=10_000_000, max_bytes=max_bytes)
    registro_desde = min((float(d.get("logged_at", 0)) for d in todas), default=None)
    registro_hasta = max((float(d.get("logged_at", 0)) for d in todas), default=None)
    sel = [d for d in todas
           if (desde is None or float(d.get("logged_at", 0)) >= desde)
           and (hasta is None or float(d.get("logged_at", 0)) <= hasta)]
    return {
        "desde": desde, "hasta": hasta,
        "registro_desde": registro_desde, "registro_hasta": registro_hasta,
        "total": len(sel), "truncado": len(sel) > limite, "limite": limite,
        "decisiones": sel[:limite],
    }


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
    try:
        sello = (str(log_path), log_path.stat().st_size // 262_144)
    except OSError:
        sello = None
    if sello is not None and _CACHE_ALCANCE.get("sello") == sello \
            and time.monotonic() - _CACHE_ALCANCE.get("t", 0) < 15:
        return dict(_CACHE_ALCANCE["datos"])
    alcance = _leer_alcance(log_path)
    _CACHE_ALCANCE.update(sello=sello, t=time.monotonic(), datos=alcance)
    return dict(alcance)


_CACHE_ALCANCE: dict = {}


def _leer_alcance(log_path: Path) -> dict:
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
    # Infraestructura protegida (DNS/AD, gateways...): sus reglas se registran pero
    # nunca se publican ni aplican, asi que no son alertas con accion (politica A).
    acciones = [None if str(d.get("entity_ip", "")) in NUNCA_BLOQUEAR else accion_de(d) for d in recent]
    return {
        "total": len(recent),
        "block": sum(1 for a in acciones if a and a[0] == "BLOCK"),
        "limit": sum(1 for a in acciones if a and a[0] == "LIMIT"),
        "ips_con_accion": len({d.get("entity_ip") for d, a in zip(recent, acciones) if a}),
        # Las anomalias marginales cuentan aparte: el panel las agrupa, no las borra.
        "alert_model_marginal": sum(1 for d in recent if es_marginal(d)),
        "acciones_relevantes": sum(1 for d, a in zip(recent, acciones) if a and not es_marginal(d)),
        "acciones_regla": sum(1 for d, a in zip(recent, acciones) if a and isinstance(d.get("heuristico"), dict)
                              and d["heuristico"].get("accion") in SEVERIDAD_ACCION),
        "revision_modelo": sum(1 for d in recent if d.get("politica_modelo") == "sostenida"
                               and str(d.get("entity_ip", "")) not in NUNCA_BLOQUEAR
                               and not (isinstance(d.get("heuristico"), dict) and d["heuristico"].get("accion"))),
        "infra_protegida": sum(1 for d in recent if str(d.get("entity_ip", "")) in NUNCA_BLOQUEAR
                               and (d.get("decision") == "ALERT" or isinstance(d.get("heuristico"), dict))),
        "alert_model": alert_ocsvm,
        "alert_auth_heuristic": alert_auth_heuristic,
        "permit_model": permit_model,
        "permit_heuristic": permit_heuristic,
        "entidades": len({d.get("entity_ip") for d in recent if d.get("entity_ip")}),
    }


# Un evento stats de Suricata mas viejo que esto ya no describe "ahora": su
# contador de drops es historia, no una perdida en curso.
UMBRAL_STATS_VIEJO_S = 120

# Ultima muestra de captura vista, para calcular el delta de drops entre dos
# lecturas del mismo contador acumulado (el servidor es un proceso de larga
# vida; con una sola lectura no hay forma de saber si los drops crecen).
_CAPTURA_PREVIA: dict = {}


def _epoch_de_ts(ts: str | None) -> float | None:
    """Epoch (s) de una marca ISO de Suricata, o None si no se puede leer.

    Suricata escribe la zona como +0000; datetime.fromisoformat la quiere como
    +00:00. Se normaliza antes de convertir.
    """
    if not ts:
        return None
    s = str(ts).strip()
    if len(s) >= 6 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def drops_estado(capture_metrics: dict | None, previa: dict | None,
                 ahora: float | None) -> dict:
    """Estado de los drops de captura comparando dos muestras.

    ``kernel_drops`` es un ACUMULADO desde que arranco Suricata, no "lo que se
    cae ahora". Un valor > 0 heredado del arranque no es una perdida en curso.
    Se mira el incremento entre la muestra previa y la actual (por su marca
    ``medido_en``) y, aparte, si el evento stats esta tan viejo que ya no
    describe el presente. ``previa`` es ``{"medido_en", "total"}`` de la lectura
    anterior. Funcion pura: el estado se guarda fuera.
    """
    if not capture_metrics or "kernel_packets" not in capture_metrics:
        return {"nivel": "sin_dato", "total": None, "delta": None,
                "subiendo": False, "atrasado": True, "marca": None}
    total = (int(capture_metrics.get("kernel_drops", 0) or 0)
             + int(capture_metrics.get("kernel_ifdrops", 0) or 0))
    marca = capture_metrics.get("medido_en")
    t = _epoch_de_ts(marca)
    atrasado = t is None or (ahora is not None and ahora - t > UMBRAL_STATS_VIEJO_S)
    delta = None
    if (previa and previa.get("total") is not None
            and previa.get("medido_en") != marca and total >= previa["total"]):
        delta = total - previa["total"]
    subiendo = bool(delta)
    nivel = "subiendo" if subiendo else ("atrasado" if atrasado else "estable")
    return {"nivel": nivel, "total": total, "delta": delta, "subiendo": subiendo,
            "atrasado": atrasado, "marca": marca}


def resumen_salud(modo: str, services: dict, counters: dict, drops: dict,
                  calibracion: dict | None) -> dict:
    """La franja de salud del panel: nivel + mensaje, decidida en el SERVIDOR.

    Una sola verdad y, al no vivir en JS, se puede probar. Separa la salud de
    SERVICIO de la actividad de RESPUESTA: una accion LIMIT/BLOCK -incluida la
    de un heuristico, sin ALERT del modelo- es actividad efectiva del sistema y
    no puede quedar bajo "todo operando con normalidad". Una accion de regla se
    nombra como accion, no como "alerta del modelo".
    """
    if modo == "demo":
        return {"nivel": "warn",
                "msg": "MODO DEMO — datos de ejemplo del repositorio",
                "sub": "Estás viendo cómo funciona CyberFlow con decisiones de muestra, "
                       "sin captura en vivo ni sensor. Para usarlo en tu red, sigue la "
                       "instalación (modo despliegue)."}
    todos_activos = all(services.values()) if services else True
    n_block = int(counters.get("block", 0) or 0)
    n_limit = int(counters.get("limit", 0) or 0)
    n_alert_modelo = int(counters.get("alert_model", 0) or 0)
    n_alert_fb = int(counters.get("alert_auth_heuristic", 0) or 0)
    n_accion = n_block + n_limit
    subiendo_drops = bool(drops.get("subiendo"))
    if not todos_activos:
        return {"nivel": "bad",
                "msg": "Atención: un servicio no está activo",
                "sub": "Revisar con journalctl — el motor puede no estar observando "
                       "tráfico real ahora mismo."}
    # El modelo sin calibrar para esta red no mide nada: sus ALERT son ruido. Una
    # accion por regla determinista NO depende del modelo, asi que se nombra aparte.
    if calibracion and not calibracion.get("calibrado_en_esta_red"):
        sub = ("El umbral viene de otra red. %d alerta(s) del modelo en la última hora: "
               "trátalas como ruido hasta recalibrar con tráfico propio." % n_alert_modelo)
        if n_accion:
            sub += (" Hay %d acción(es) de respuesta por reglas deterministas, "
                    "que no dependen del modelo." % n_accion)
        if subiendo_drops:
            sub += " Además, Suricata está descartando paquetes ahora."
        return {"nivel": "warn",
                "msg": "Modelo sin calibrar para esta red — las alertas del modelo aún no son fiables",
                "sub": sub}
    if n_accion > 0 or n_alert_modelo > 0 or n_alert_fb > 0:
        partes = []
        if n_block:
            partes.append("%d BLOCK" % n_block)
        if n_limit:
            partes.append("%d LIMIT" % n_limit)
        if n_alert_modelo:
            partes.append("%d anomalía(s) del modelo" % n_alert_modelo)
        if n_alert_fb:
            partes.append("%d alerta(s) de fuerza bruta" % n_alert_fb)
        # Lo que el sensor sabe es que DECIDIO una accion; si el host la aplico no
        # se ve desde aqui. Por eso «decisiones registradas», no «respuesta activa».
        if n_accion > 0:
            msg = "Servicios operativos · %d decisión(es) LIMIT/BLOCK en la última hora" % n_accion
        else:
            msg = "Servicios operativos · %d alerta(s) en la última hora" % (n_alert_modelo + n_alert_fb)
        return {"nivel": "warn", "msg": msg,
                "sub": " · ".join(partes) + " · detalle en Respuestas"}
    if subiendo_drops:
        d = drops.get("delta")
        return {"nivel": "warn",
                "msg": "Atención: Suricata está descartando paquetes",
                "sub": ("Subió %s desde la última muestra. Las features del motor pueden "
                        "quedar incompletas mientras ocurra — ver «Drops de captura» abajo."
                        % ("+%d" % d if d else "ahora"))}
    # Todo normal, pero el estado de drops se dice con su frescura: nunca "sin
    # drops" cuando en realidad no hay dato fresco que lo respalde.
    if drops.get("nivel") == "sin_dato":
        cola = " Estado de drops: dato no disponible."
    elif drops.get("atrasado"):
        cola = " Estado de drops: dato atrasado (el último stats de Suricata es viejo)."
    else:
        cola = " Sin aumento de drops reciente."
    return {"nivel": "ok",
            "msg": "Todo operando con normalidad",
            "sub": "Servicios activos, sin acciones ni alertas en la última hora." + cola}


def bucket_activity(decisions: list[dict], bucket_seconds: int, count: int) -> list[dict]:
    """Agrega decisiones en cubos de tamano fijo para graficar actividad.

    Generaliza el sparkline de 60 minutos (bucket_seconds=60, count=60) y el
    de 24 horas (bucket_seconds=3600, count=24) con la misma logica. Cubos
    vacios se incluyen con ceros -- el frontend los necesita para dibujar
    una linea de tiempo continua, no solo los intervalos con actividad.
    """
    now = time.time()
    buckets = [{"offset": i, "alert": 0, "permit": 0, "limit": 0, "block": 0}
               for i in range(count, -1, -1)]
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
        # La accion (LIMIT/BLOCK) no coincide con ALERT: una regla puede pedir
        # BLOCK con el modelo en PERMIT. El grafico cuenta acciones.
        # Infraestructura protegida (p. ej. el DNS con dns_entropy): nunca se
        # actua sobre ella, asi que no pinta LIMIT/BLOCK (= compute_counters).
        if str(item.get("entity_ip", "")) in NUNCA_BLOQUEAR:
            continue
        accion = accion_de(item)
        if accion is not None:
            bucket[accion[0].lower()] += 1
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


# --------------------------------------------------------------- acciones
#
# La ACCION que corresponde a cada decision, con la misma regla que
# publicar_feed.py: un heuristico confirmado manda (BLOCK o LIMIT); un ALERT del
# modelo degrada a LIMIT; un ALERT de heuristico «legacy» (*_heuristic) bloquea.
# Ojo: en un ataque real el modelo puede decir PERMIT y el heuristico pedir BLOCK
# (escaneo del 6-oct): por eso el panel avisa por ACCION, no por decision.

SEVERIDAD_ACCION = {"BLOCK": 2, "LIMIT": 1}
ESCALERA_BLOCK_S = {1: 300, 2: 1800, 3: 3600}     # = escalada.py
TIMEOUT_LIMIT_S = 300
CADENCIA_FEED_S = 10                              # cadena escalonada cada 10 s
REGLA_LEGACY = {"auth_failure_heuristic": "fallos de autenticación repetidos"}
NUNCA_BLOQUEAR = {"10.10.10.30", "10.10.60.11", "10.10.30.1", "10.10.40.1",
                  "10.10.60.1", "10.10.20.1", "10.10.10.20"}   # = publicar_feed.py

# Lista blanca (16-nov-2026): IPs de infraestructura conocida (p. ej. Zabbix) cuyas alertas se
# agrupan aparte en el panel. Es un fichero editable, no codigo: configs/lista-blanca.json.
# El panel NO decide nada: solo agrupa la vista y dice si el feed v2 todavia publica una medida
# sobre esa IP (lo que hace el publicador no cambia por editar este fichero).
LISTA_BLANCA_PATH = RAIZ_REPO / "configs" / "lista-blanca.json"


def leer_lista_blanca(ruta: Path = LISTA_BLANCA_PATH) -> list[dict]:
    """Entradas validas de la lista blanca ({ip, nombre, motivo, alta}); [] si falta o es ilegible."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out, vistas = [], set()
    for e in (datos.get("entradas") or []) if isinstance(datos, dict) else []:
        if not isinstance(e, dict):
            continue
        ip = str(e.get("ip", "")).strip()
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        if ip in vistas:
            continue
        vistas.add(ip)
        out.append({"ip": ip, "nombre": str(e.get("nombre", "")), "motivo": str(e.get("motivo", "")),
                    "alta": str(e.get("alta", ""))})
    return out


def estado_lista_blanca(ruta: Path, feed_v2: Path | None, ahora: float) -> dict:
    """Lista blanca + la medida que el feed v2 publica HOY sobre cada IP (None si ninguna)."""
    entradas = leer_lista_blanca(ruta)
    vig: dict[str, dict] = {}
    feed_ok = False
    if feed_v2 is not None:
        try:
            feed = json.loads(feed_v2.read_text(encoding="utf-8"))
            feed_ok = True
            for x in feed.get("entradas") or []:
                if isinstance(x, dict) and float(x.get("hasta", 0)) > ahora:
                    vig[str(x.get("ip", ""))] = x
        except (OSError, ValueError, TypeError):
            pass
    for e in entradas:
        m = vig.get(e["ip"])
        e["medida_feed"] = ({"accion": m.get("accion"), "hasta": m.get("hasta"), "motivo": m.get("motivo"),
                             "destino": m.get("destino")} if m else None)
    return {"ruta": str(ruta), "feed_leido": feed_ok, "entradas": entradas}


def accion_de(d: dict) -> tuple[str, str, str] | None:
    """(accion, motivo, origen) de una decision, o None si no pide accion."""
    if _CADENA_V2 is not None:
        # Cadena v2 (4A): la accion es la medida que PUBLICO el publicador v2 (traza),
        # nunca una deduccion del panel. Una anomalia del IF sin medida no es LIMIT.
        return cadena_v2.medida_como_accion(d)
    candidatos = []
    if d.get("decision") == "ALERT":
        det = str(d.get("detector_name", ""))
        if det.endswith("_heuristic"):
            candidatos.append(("BLOCK", REGLA_LEGACY.get(det, "regla determinista"), det))
        elif MODELO_SOLO_ACTUA and d.get("politica_modelo") in (None, "sostenida"):
            # = publicar_feed: con la politica A el modelo solo no pide accion
            candidatos.append(("LIMIT", "anomalía del modelo", "modelo"))
    h = d.get("heuristico")
    if isinstance(h, dict) and h.get("accion") in SEVERIDAD_ACCION:
        candidatos.append((h["accion"], str(h.get("motivo", "")), str(h.get("heuristico", "regla"))))
    if not candidatos:
        return None
    # A igual severidad gana la regla: su motivo dice mas que «anomalia del modelo».
    return max(candidatos, key=lambda c: (SEVERIDAD_ACCION[c[0]], c[2] != "modelo"))



# 3-nov (noche): motor de las campañas otra vez (demo: 0.05 / 3 / False).
MARGEN_MARGINAL = 0.0    # misma cifra que el navegador (MARGEN_MARGINAL en el JS)
VENTANA_SOSTENIDA_S = 120  # = tramo que lee publicar_feed (--ventana-segundos)
MIN_VENTANAS_MODELO = 1    # = publicar_feed.MIN_VENTANAS_MODELO
MODELO_SOLO_ACTUA = True   # = publicar_feed.MODELO_SOLO_ACTUA (politica A = False)


def anotar_politica_modelo(decisiones: list[dict]) -> None:
    """Marca cada ALERT solo-modelo como «marginal», «suelta» o «sostenida».

    Es la misma politica que publicar_feed.py (3-nov): el modelo solo, sin regla
    que lo confirme, publica LIMIT con anomalia CLARA (score < umbral - 0,05) y
    SOSTENIDA (3 ventanas claras de la misma IP a <= 120 s). Las otras dos se
    registran y se ven, pero no piden accion. Escribe el campo en cada dict.

    Con la cadena v2 activa no se anota: esa politica es la del publicador v1.
    """
    if _CADENA_V2 is not None:
        return
    claras: dict[str, list[float]] = {}
    solo = []
    for d in decisiones:
        if d.get("decision") != "ALERT" or str(d.get("detector_name", "")).endswith("_heuristic"):
            continue
        h = d.get("heuristico")
        if isinstance(h, dict) and h.get("accion") in SEVERIDAD_ACCION:
            continue
        solo.append(d)
        s, u = d.get("score"), d.get("threshold")
        marginal = (isinstance(s, (int, float)) and isinstance(u, (int, float))
                    and s >= u - MARGEN_MARGINAL)
        d["politica_modelo"] = "marginal" if marginal else "suelta"
        if not marginal:
            claras.setdefault(str(d.get("entity_ip")), []).append(float(d.get("logged_at", 0)))
    for d in solo:
        if d["politica_modelo"] != "suelta":
            continue
        t = float(d.get("logged_at", 0))
        ts = claras.get(str(d.get("entity_ip")), [])
        if sum(1 for x in ts if abs(x - t) <= VENTANA_SOSTENIDA_S) >= MIN_VENTANAS_MODELO:
            d["politica_modelo"] = "sostenida"


def es_marginal(d: dict, margen: float = MARGEN_MARGINAL) -> bool:
    """ALERT solo del modelo con el score a menos de `margen` por debajo del umbral.

    Es una anomalia real y su LIMIT se publica; el panel solo la agrupa para que
    no tape las detecciones claras. Una regla disparada nunca es marginal.
    """
    if d.get("decision") != "ALERT" or str(d.get("detector_name", "")).endswith("_heuristic"):
        return False
    h = d.get("heuristico")
    if isinstance(h, dict) and h.get("accion") in SEVERIDAD_ACCION:
        return False
    s, u = d.get("score"), d.get("threshold")
    if not isinstance(s, (int, float)) or not isinstance(u, (int, float)):
        return False
    return s >= u - margen


def estado_escenario(log_path: Path, ip: str, desde: str, ahora: float,
                     feed_path: Path | None, estado_path: Path | None,
                     acuse_dir: Path | None = None) -> dict:
    """Lo que la seccion «Escenario en vivo» necesita de una IP desde un instante.

    Solo lectura y acotado: la cola del registro (4 MiB), las decisiones de esa
    IP, su entrada del feed firmado y su respuesta vigente. La aplicacion en el
    host la informa el propio host (acuse que trae el relay); el sensor no la
    ve por si mismo.
    """
    try:
        ip = str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        return {"error": "IP no válida"}
    try:
        t0 = float(desde)
    except (TypeError, ValueError):
        t0 = ahora - 120
    t0 = max(t0, ahora - 3 * 3600)
    decisiones = read_decisions(log_path, limit=50_000, max_bytes=4_194_304)
    horas = [float(d["logged_at"]) for d in decisiones if isinstance(d.get("logged_at"), (int, float))]
    recientes = [d for d in decisiones if float(d.get("logged_at", 0)) >= ahora - 60]
    filas = []
    for d in decisiones:
        if d.get("entity_ip") != ip or float(d.get("logged_at", 0)) < t0:
            continue
        a = accion_de(d)
        filas.append({
            "logged_at": d.get("logged_at"), "window_end_utc": d.get("window_end_utc"),
            "decision": d.get("decision"), "score": d.get("score"), "threshold": d.get("threshold"),
            "detector_name": d.get("detector_name"), "heuristico": d.get("heuristico"),
            "accion": a[0] if a else "PERMIT", "motivo": a[1] if a else "",
            "origen": a[2] if a else "", "marginal": es_marginal(d), "politica_modelo": d.get("politica_modelo"),
            "cadena_v2": d.get("cadena_v2"),
        })
        if len(filas) >= 400:
            break
    feed = None
    if feed_path is not None:
        try:
            f = json.loads(Path(feed_path).read_text(encoding="utf-8"))
            entradas = f.get("entradas") or []
            feed = {"generado": f.get("generado"), "entradas": len(entradas),
                    "entrada": next((e for e in entradas if e.get("ip") == ip), None)}
        except (OSError, ValueError, AttributeError):
            feed = None
    vig = [v for v in acciones_vigentes(decisiones, ahora, feed_path, estado_path) if v.get("ip") == ip]
    return {
        "ahora": ahora, "ip": ip, "desde": t0,
        "ultima_decision": max(horas) if horas else None,
        "decisiones_60s": len(recientes),
        "ips_60s": len({d.get("entity_ip") for d in recientes if d.get("entity_ip")}),
        "decisiones": filas, "feed": feed, "vigente": vig[0] if vig else None,
        "margen_marginal": MARGEN_MARGINAL,
        "aplicacion": acuses_de_ip(acuse_dir, ip, t0, ahora) if acuse_dir is not None else None,
    }


# Un acuse mas viejo que esto ya no describe el firewall de ahora (el relay lo
# trae cada 10 s; tres vueltas perdidas = dato atrasado).
ACUSE_VIEJO_S = 35


DEMO_IPS = ("10.10.20.30", "10.10.20.21")   # Kali (ataques) y cliente legítimo del laboratorio
PREP_VALIDA_S = 600                          # = LIBERACION_VALIDA_S del agente


def pedir_preparacion(ruta: Path, usuario: str, ahora: float) -> dict:
    """Deja la petición «preparar demo». No toca ningún host: la lleva el feed FIRMADO
    (publicar_feed la incluye) y el agente de cada host decide si la aplica."""
    pet = {"id": secrets.token_hex(6), "t": ahora, "ips": list(DEMO_IPS), "por": usuario}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(pet), encoding="utf-8")
    tmp.replace(ruta)
    return pet


def pedir_limpieza_v2(ctl: Path, usuario: str, ahora: float) -> dict:
    """«Dejar limpio» en la cadena v2: deja el control D5 (reset_origen de la Kali) que el
    publicador consume sin reiniciarse. Si ya hay uno pendiente no se pisa."""
    if ctl.exists():
        return {"ok": False, "motivo": "ya hay una limpieza pendiente: espera el acuse del publicador"}
    pet = {"accion": "reset_origen", "id": secrets.token_hex(16), "origen": DEMO_IPS[0],
           "por": usuario, "t": ahora}
    tmp = ctl.with_name(ctl.name + ".panel.tmp")
    tmp.write_text(json.dumps(pet), encoding="utf-8")
    tmp.replace(ctl)
    try:   # copia de registro, como las del ejecutor de campañas
        (ctl.parent / "solicitudes" / (pet["id"] + ".json")).write_text(json.dumps(pet), encoding="utf-8")
    except OSError:
        pass
    return {"ok": True, "id": pet["id"]}


def estado_limpieza_v2(ctl: Path, feed_v2: Path, ident: str, ahora: float) -> dict:
    """Acuse del publicador para ESA petición y si el feed aún restringe la Kali o el cliente."""
    ack = None
    try:
        a = json.loads(ctl.with_name(ctl.name + ".ack").read_text(encoding="utf-8"))
        if isinstance(a, dict) and a.get("id") == ident:
            ack = a
    except (OSError, ValueError):
        pass
    kali = None
    try:
        feed = json.loads(feed_v2.read_text(encoding="utf-8"))
        kali = any(isinstance(e, dict) and e.get("ip") in DEMO_IPS and float(e.get("hasta", 0)) > ahora
                   for e in feed.get("entradas") or [])
    except (OSError, ValueError, TypeError):
        pass
    return {"id": ident, "pendiente": ctl.exists(), "ack": ack, "kali_en_feed": kali}


def estado_preparacion(ruta: Path, log_path: Path, feed_path: Path | None, acuse_dir: Path | None,
                       ahora: float) -> dict:
    """Lista de comprobación para empezar una demo: motor, feed, agente y cada IP sin regla."""
    checks = []

    def chk(ok, texto, detalle="", espera=False):
        checks.append({"estado": "ok" if ok else ("esp" if espera else "mal"), "texto": texto, "detalle": detalle})
        return ok

    try:
        pet = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pet = None
    t_pet = float(pet.get("t", 0)) if isinstance(pet, dict) else 0.0
    try:
        edad_m = ahora - Path(log_path).stat().st_mtime
    except OSError:
        edad_m = None
    chk(edad_m is not None and edad_m < 30, "Motor en vivo",
        "última ventana hace %d s" % edad_m if edad_m is not None else "sin registro")
    feed = {}
    if feed_path is not None:
        try:
            feed = json.loads(Path(feed_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            feed = {}
    gen = feed.get("generado") if isinstance(feed.get("generado"), (int, float)) else None
    chk(gen is not None and ahora - gen < 30, "Feed firmado al día",
        "publicado hace %d s" % (ahora - gen) if gen else "sin feed")
    if pet:
        en_feed = any(isinstance(x, dict) and x.get("id") == pet.get("id") for x in feed.get("liberaciones") or [])
        chk(en_feed or False, "Petición dentro del feed firmado", "id " + str(pet.get("id")), espera=not en_feed)
    acs = [] if acuse_dir is None else acuses_resumen(acuse_dir, ahora)
    host = next((a for a in acs if a.get("host") == "srv-dmz"), acs[0] if acs else None)
    if host is None:
        chk(False, "Acuse de srv-dmz", "no llega")
    else:
        chk(host.get("agente") == "active" and not host.get("atrasado"), "Agente de srv-dmz activo",
            "acuse hace %d s" % (host.get("edad") or 0))
    for ip in DEMO_IPS:
        regla = (host or {}).get("reglas", {}).get(ip) if host else None
        lib = ((host or {}).get("liberadas") or {}).get(ip) if host else None
        desde = lib.get("desde") if isinstance(lib, dict) else None
        fresca = host is not None and (host.get("edad") or 0) < 40 and (ahora - (host.get("edad") or 0)) >= t_pet
        liberada_ahora = bool(desde and desde >= t_pet - 5) if pet else True
        ok = host is not None and regla is None and (liberada_ahora or not pet) and fresca
        det = ("con " + regla.get("accion", "?") + " en nftables") if regla else (
            "liberada a las " + time.strftime("%H:%M:%S", time.localtime(desde)) if desde and liberada_ahora else "sin regla")
        chk(ok, "%s sin regla en srv-dmz" % ip, det, espera=not ok and bool(pet) and ahora - t_pet < 120)
    listo = all(c["estado"] == "ok" for c in checks)
    return {"listo": listo, "checks": checks, "peticion": pet,
            "peticion_edad": None if not pet else ahora - t_pet, "ahora": ahora}


def acuses_resumen(acuse_dir: Path, ahora: float) -> list[dict]:
    """Por host protegido: que tiene aplicado, que libero un humano y que dejo fuera de alcance."""
    out = []
    try:
        ficheros = sorted(Path(acuse_dir).glob("*.json"))[:20]
    except OSError:
        return out
    for f in ficheros:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        gen = d.get("generado") if isinstance(d.get("generado"), (int, float)) else None
        pasada = d.get("ultima_pasada") or {}
        out.append({
            "host": d.get("host") or f.stem, "edad": None if gen is None else max(0.0, ahora - gen),
            "atrasado": gen is None or ahora - gen > ACUSE_VIEJO_S, "agente": d.get("agente"),
            "error": d.get("error"),
            "reglas": {ip: r for ip, r in (d.get("reglas") or {}).items() if isinstance(r, dict)},
            "liberadas": d.get("liberadas") or {},
            "sombra": pasada.get("sombra") if isinstance(pasada.get("sombra"), dict) else {},
        })
    return out


def acuses_de_ip(acuse_dir: Path, ip: str, t0: float, ahora: float) -> list[dict]:
    """Paso 5 con datos del host: lo que cada host protegido dice tener en nftables.

    Lee ~/feed/acuses/<host>.json (los deja el relay del bastion). Por host:
    regla vigente de la IP (BLOCK/LIMIT con caducidad), liberacion humana,
    eventos de la IP desde t0 (aplicada, cambiada, retirada, liberada) y la
    edad del acuse. Es un informe del host, no una orden firmada.
    """
    out = []
    try:
        ficheros = sorted(Path(acuse_dir).glob("*.json"))[:20]
    except OSError:
        return out
    for f in ficheros:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        gen = d.get("generado") if isinstance(d.get("generado"), (int, float)) else None
        regla = (d.get("reglas") or {}).get(ip)
        lib = (d.get("liberadas") or {}).get(ip)
        eventos = [e for e in (d.get("eventos") or [])
                   if isinstance(e, dict) and e.get("ip") == ip and float(e.get("t") or 0) >= t0 - 1]
        pasada = d.get("ultima_pasada") or {}
        sombra = pasada.get("sombra") if isinstance(pasada.get("sombra"), dict) else {}
        out.append({
            "host": d.get("host") or f.stem, "generado": gen, "fuera_de_alcance": sombra.get(ip),
            "edad": None if gen is None else max(0.0, ahora - gen),
            "atrasado": gen is None or ahora - gen > ACUSE_VIEJO_S,
            "agente": d.get("agente"), "error": d.get("error"),
            "regla": regla, "liberada": lib, "eventos": eventos[-20:],
            "ultima_pasada": {"hora": pasada.get("hora"), "estado": pasada.get("estado"),
                              "errores": pasada.get("errores")} if pasada else None,
        })
    return out


def acciones_vigentes(decisions: list[dict], ahora: float, feed_path: Path | None = None,
                      estado_path: Path | None = None, nunca: set[str] = NUNCA_BLOQUEAR) -> list[dict]:
    """LIMIT/BLOCK en vigor ahora, por IP.

    Dos fuentes. El feed publicado (feed.json) trae la caducidad exacta de lo
    que se publico en el ultimo minuto. Lo anterior se reconstruye del registro
    del motor con la misma escalera: ultima ofensa + 300 s (LIMIT) o 300/1800/
    3600 s (BLOCK, nivel leido de estado.json) + la cadencia del feed. Lo que el
    agente del host aplica es exactamente eso; el sensor no tiene otra forma de
    saberlo, porque el bloqueo ocurre en el host.

    Con la cadena v2 activa la unica fuente es el feed v2 firmado (en sombra: propuestas);
    no se reconstruye nada desde el registro con la escalera v1.
    """
    if _CADENA_V2 is not None:
        return _CADENA_V2.vigentes(ahora)
    vigentes: dict[str, dict] = {}
    # Tres estados distintos que el panel no debe mezclar: registrada (el motor
    # la decidio), publicada (esta en el feed firmado) y aplicada en el host
    # (eso solo lo sabe el agente; aqui nunca se afirma).
    en_feed: set[str] = set()
    if feed_path is not None:
        try:
            feed = json.loads(Path(feed_path).read_text(encoding="utf-8"))
            for e in feed.get("entradas", []):
                if e.get("ip"):
                    en_feed.add(str(e["ip"]))
                if float(e.get("hasta", 0)) > ahora and e.get("ip"):
                    vigentes[e["ip"]] = {
                        "ip": e["ip"], "accion": e.get("accion"), "motivo": e.get("motivo", ""),
                        "origen": e.get("detector", ""), "nivel": e.get("nivel"),
                        "hasta": float(e["hasta"]), "revisar_humano": bool(e.get("revisar_humano")),
                        "fuente": "feed"}
        except (OSError, ValueError, TypeError):
            pass
    estado = {}
    if estado_path is not None:
        try:
            estado = json.loads(Path(estado_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            estado = {}

    ofensas: dict[str, list[tuple[float, str, str, str]]] = {}
    for d in decisions:
        a = accion_de(d)
        ip = str(d.get("entity_ip", ""))
        if a is None or not ip or ip in nunca:
            continue
        ofensas.setdefault(ip, []).append((float(d.get("logged_at", 0)), *a))
    for ip, lista in ofensas.items():
        lista.sort()
        t_ultima = lista[-1][0]
        # El episodio: ofensas encadenadas con huecos de menos de 5 min.
        inicio = t_ultima
        for t, *_ in reversed(lista):
            if inicio - t > TIMEOUT_LIMIT_S:
                break
            inicio = t
        episodio = [o for o in lista if o[0] >= inicio]
        accion, motivo, origen = max(((o[1], o[2], o[3]) for o in episodio),
                                     key=lambda o: SEVERIDAD_ACCION[o[0]])
        if accion == "BLOCK":
            nivel = max(1, min(3, int((estado.get(ip) or {}).get("bloqueos", 1) or 1)))
            hasta = t_ultima + ESCALERA_BLOCK_S[nivel] + CADENCIA_FEED_S
        else:
            nivel = 0
            hasta = t_ultima + TIMEOUT_LIMIT_S + CADENCIA_FEED_S
        previo = vigentes.get(ip)
        if previo is None:
            if hasta > ahora:
                vigentes[ip] = {"ip": ip, "accion": accion, "motivo": motivo, "origen": origen,
                                "nivel": nivel, "hasta": hasta, "revisar_humano": nivel >= 3,
                                "fuente": "registro"}
            previo = vigentes.get(ip)
        if previo is not None:
            previo["desde"] = inicio
            previo["ultima"] = t_ultima
            previo["ofensas"] = len(episodio)
            previo["registrada"] = True
    salida = []
    for v in vigentes.values():
        v["expira_s"] = max(0, int(v["hasta"] - ahora))
        v["publicada"] = v["ip"] in en_feed
        v.setdefault("registrada", False)
        salida.append(v)
    salida.sort(key=lambda v: (-SEVERIDAD_ACCION.get(v["accion"], 0), -v["hasta"]))
    return salida


COMPARACION_POR_OMISION = Path(__file__).resolve().parents[2] / "docs" / "evaluacion" / "comparacion-suricata.json"


_CACHE_HISTORIAL: dict[str, object] = {}
SEPARACION_EPISODIO_S = 600      # dos ofensas a mas de 10 min son episodios distintos


def historial_acciones(log_path: Path, ahora: float, horas: int = 24,
                       max_bytes: int = 33_554_432, nunca: set[str] | None = None,
                       cache_s: float = 30.0) -> dict:
    """Episodios de LIMIT/BLOCK de las ultimas horas, uno por IP y racha.

    «Respuestas registradas como vigentes» ensena lo vigente; esto, lo que ya paso. Se lee
    la cola del registro y solo se interpretan las lineas que pueden pedir una
    accion (un ALERT o un heuristico), que son muy pocas. `desde` dice hasta
    donde alcanza de verdad el registro leido: si no llega a las horas pedidas,
    el panel lo dice en vez de dar a entender que antes no hubo nada.
    """
    c = _CACHE_HISTORIAL
    if c.get("ruta") == str(log_path) and ahora - float(c.get("t", 0)) < cache_s:
        return c["datos"]                                   # type: ignore[return-value]
    if nunca is None:
        nunca = NUNCA_BLOQUEAR
    limite = ahora - horas * 3600
    # Del almacen incremental (ya con la politica del modelo anotada): antes se
    # releian y parseaban 32 MiB cada 30 s solo para esta vista.
    tramo = _decisiones_tramo(log_path, max_bytes)
    primera = float(tramo[0].get("logged_at", 0)) if tramo else None
    ofensas: dict[str, list[tuple[float, str, str, str]]] = {}
    leidas = [d for d in tramo if d.get("decision") == "ALERT" or d.get("heuristico")]
    for d in leidas:
        t = d.get("logged_at")
        ip = str(d.get("entity_ip", ""))
        if not isinstance(t, (int, float)) or t < limite or not ip or ip in nunca:
            continue
        a = accion_de(d)
        if a is not None:
            ofensas.setdefault(ip, []).append((float(t), *a))
    episodios = []
    for ip, lista in ofensas.items():
        lista.sort()
        racha = [lista[0]]
        for o in lista[1:] + [None]:                       # type: ignore[list-item]
            if o is not None and o[0] - racha[-1][0] <= SEPARACION_EPISODIO_S:
                racha.append(o)
                continue
            peor = max(racha, key=lambda x: (SEVERIDAD_ACCION[x[1]], x[3] != "modelo"))
            caduca = racha[-1][0] + (ESCALERA_BLOCK_S[1] if peor[1] == "BLOCK" else TIMEOUT_LIMIT_S) \
                + CADENCIA_FEED_S
            episodios.append({
                "ip": ip, "accion": peor[1], "motivo": peor[2], "origen": peor[3],
                "inicio": racha[0][0], "fin": racha[-1][0], "ventanas": len(racha),
                "vigente": caduca > ahora, "caduca": caduca,
            })
            if o is not None:
                racha = [o]
    episodios.sort(key=lambda e: e["inicio"], reverse=True)
    datos = {"ahora": ahora, "horas": horas,
             "desde": max(limite, primera) if primera is not None else None,
             "episodios": episodios[:200]}
    c.update(ruta=str(log_path), t=ahora, datos=datos)
    return datos


_CACHE_FILAS: dict[str, object] = {}


def contar_filas(path: Path) -> int | None:
    """Filas de datos de un CSV que crece, sin releerlo entero cada vez.

    El panel refresca cada 5 s y el dataset pasa de 70 MB: se recuerda hasta
    donde se conto y solo se leen los bytes nuevos. Si el fichero encoge o
    cambia de ruta (rotacion), se cuenta desde cero.
    """
    try:
        tam = path.stat().st_size
    except OSError:
        return None
    c = _CACHE_FILAS
    if c.get("ruta") != str(path) or tam < int(c.get("pos", 0)):
        c.clear()
        c.update(ruta=str(path), pos=0, n=0)
    if tam > int(c["pos"]):
        try:
            with path.open("rb") as fh:
                fh.seek(int(c["pos"]))
                n = int(c["n"])
                while True:
                    bloque = fh.read(1 << 20)
                    if not bloque:
                        break
                    n += bloque.count(b"\n")
                c["n"], c["pos"] = n, fh.tell()
        except OSError:
            return None
    return max(0, int(c["n"]) - 1)          # menos la cabecera


def pulso_ingesta(decisions: list[dict], eve_path: Path | None, dataset: Path | None,
                  feed_path: Path | None, ahora: float) -> dict:
    """Lo que entra y lo que se acumula, con la hora de cada cosa.

    Devuelve contadores y marcas de tiempo, no tasas: la tasa la saca el
    navegador de dos lecturas seguidas. Lo que no se puede leer va como None,
    nunca como cero.
    """
    def ficha(p: Path | None) -> dict | None:
        if p is None:
            return None
        try:
            st = p.stat()
        except OSError:
            return None
        return {"bytes": st.st_size, "mtime": st.st_mtime}

    horas = [d["logged_at"] for d in decisions
             if isinstance(d.get("logged_at"), (int, float))]
    feed = None
    if feed_path is not None:
        try:
            f = json.loads(feed_path.read_text(encoding="utf-8"))
            feed = {"generado": f.get("generado"), "entradas": len(f.get("entradas") or [])}
        except (OSError, ValueError, AttributeError):
            feed = None
    ds = ficha(dataset)
    if ds is not None and dataset is not None:
        ds["filas"] = contar_filas(dataset)
    return {
        "ahora": ahora,
        "ultima_decision": max(horas) if horas else None,
        "decisiones_60s": sum(1 for t in horas if t >= ahora - 60),
        "eve": ficha(eve_path),
        "dataset": ds,
        "feed": feed,
    }


def comparaciones_en_vivo(carpeta: Path | None, maximo: int = 12) -> list[dict]:
    """Resumenes que deja comparar-suricata.sh (uno por escenario de la demo).

    Cada fichero es la evidencia de una comparacion: el mismo PCAP del espejo
    analizado por Suricata + ET Open en otra VM y las decisiones del motor en el
    mismo intervalo. El panel solo los lee; la mas reciente primero.
    """
    if carpeta is None or not Path(carpeta).is_dir():
        return []
    salida = []
    for f in sorted(Path(carpeta).glob("cmp-*.json"), reverse=True)[:maximo]:
        try:
            salida.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return salida


def estado_comparacion(ruta: Path | None) -> dict:
    """Tabla de la comparacion con Suricata, calculada por el evaluador."""
    ruta = ruta or COMPARACION_POR_OMISION
    try:
        modulo = Path(__file__).resolve().parents[1] / "evaluacion"
        if str(modulo) not in sys.path:
            sys.path.insert(0, str(modulo))
        import comparacion
        return comparacion.evaluar(json.loads(Path(ruta).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, ImportError) as err:
        return {"error": "No se pudo leer la comparación (%s): %s" % (Path(ruta).name, err)}


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


EVALUACION_VIGENTE = Path(__file__).resolve().parents[2] / "docs" / "evaluacion" / "modelo-vigente.json"


DESPLIEGUE_INVENTARIO = Path(__file__).resolve().parents[2] / "docs" / "evaluacion" / "despliegue.json"


def inventario_despliegue(ruta: Path = DESPLIEGUE_INVENTARIO) -> dict:
    """Inventario declarado del despliegue (sensor, relay, agentes).

    Es un fichero versionado, no una sonda: el panel corre en el sensor y no
    tiene credenciales de los demas hosts. La vivacidad del sensor la pone el
    navegador cruzando esto con los servicios reales de /api/status.
    """
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"cadena": [], "error": "no se encontro el inventario de despliegue"}


def evaluacion_del_vigente(detector_name: str, ruta: Path = EVALUACION_VIGENTE) -> dict | None:
    """Cifras medidas del detector en uso que el manifiesto no trae.

    Solo se devuelven si el fichero nombra a ESTE detector: ensenar las cifras
    de otro modelo es justo lo que el panel no debe hacer. Sin fichero, None, y
    el panel muestra «—».
    """
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if datos.get("detector") != detector_name:
        return None
    return datos


def red_analizada(explicita: str | None, config_toml: Path | None) -> str | None:
    """La red de entidades: el argumento, o [red] red_entidades del .toml."""
    if explicita:
        return str(explicita)
    for candidato in (config_toml, TOML_LOCAL):
        try:
            if candidato and Path(candidato).is_file():
                with Path(candidato).open("rb") as fh:
                    red = tomllib.load(fh).get("red", {}).get("red_entidades")
                if red:
                    return str(red)
        except (OSError, ValueError):
            continue
    return None


TOML_LOCAL = Path(__file__).resolve().parents[2] / "configs" / "cyberflow.local.toml"


def estado_aprendizaje(config_toml: Path | None, demo: bool = False,
                       respaldo: Path | None = TOML_LOCAL) -> dict:
    """Estado del reentrenamiento supervisado, para la seccion del admin.

    Solo lee ficheros (registro, lotes, deriva, candidatos); no carga modelos.
    Sin --config-toml -unidades generadas antes de existir esta seccion- se usa
    el .local.toml de la propia raiz, que es el que leen el motor y el timer.
    """
    if config_toml is None and respaldo is not None and Path(respaldo).is_file():
        config_toml = respaldo
    if config_toml is None:
        return {"disponible": False,
                "motivo": "El panel no recibio --config-toml: regenere las unidades "
                          "con cyberflow_config.py para ver el aprendizaje."}
    try:
        modulo = Path(__file__).resolve().parents[1] / "modeling"
        if str(modulo) not in sys.path:
            sys.path.insert(0, str(modulo))
        import cyberflow_aprendizaje as ap
        e = ap.estado(ap.cargar_config(config_toml))
    except (OSError, ValueError, KeyError, SystemExit) as err:
        return {"disponible": False, "motivo": "No se pudo leer el aprendizaje: %s" % err}
    e["disponible"] = True
    e["demo"] = demo
    e["toml"] = Path(config_toml).name
    return e


# estado_aprendizaje verifica el sha256 de CADA lote CSV del registro: con los
# lotes acumulados son minutos de CPU y E/S. Cada pagina abierta lo pedia al
# cargar, y con varios hilos a la vez el panel dejo de responder (3-nov). El
# estado cambia una vez al dia (timer de aprendizaje): se calcula una vez y se
# sirve desde cache hasta APRENDIZAJE_CACHE_S o hasta que el registro cambie.
APRENDIZAJE_CACHE_S = 600
_CACHE_APRENDIZAJE: dict = {}
_CACHE_APRENDIZAJE_LOCK = threading.Lock()


def _sello_aprendizaje(config_toml: Path | None) -> tuple | None:
    """mtime/tamano del directorio de aprendizaje y sus .jsonl (registro, deriva...)."""
    try:
        import cyberflow_aprendizaje as ap                      # ya importado por estado_aprendizaje
        d = Path(ap.cargar_config(config_toml)["dir"])
        return tuple(sorted((f.name, f.stat().st_mtime_ns, f.stat().st_size)
                            for f in d.glob("*.jsonl")))
    except Exception:                                            # noqa: BLE001 - solo invalida antes
        return None


def estado_aprendizaje_cacheado(config_toml: Path | None, demo: bool = False) -> dict:
    with _CACHE_APRENDIZAJE_LOCK:
        c = _CACHE_APRENDIZAJE
        sello = _sello_aprendizaje(config_toml) if c else None
        if c and time.monotonic() - c["t"] < APRENDIZAJE_CACHE_S and c["sello"] == sello:
            return c["datos"]
        datos = estado_aprendizaje(config_toml, demo)
        c.update(t=time.monotonic(), datos=datos, sello=_sello_aprendizaje(config_toml))
        return datos


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
                         "/api/vivo", "/api/vivo/flujo", "/api/trazabilidad",
                         "/api/aprendizaje", "/api/comparacion", "/api/despliegue",
                         "/api/demo/estado", "/api/demo/limpieza"})

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


def modo_panel_de(args) -> str:
    """«v2» salvo seleccion EXPLICITA de la demo historica (--modo-panel v1-historico,
    --sin-cadena-v2 o --demo). No depende de que existan los ficheros de la cadena v2."""
    if getattr(args, "demo", False) or getattr(args, "sin_cadena_v2", False):
        return "v1-historico"
    return getattr(args, "modo_panel", "v2") or "v2"


BOTON_PREPARAR = '<button type="button" class="btn-prep" id="prepBtn">'


def html_solo_lectura_v2(html: str) -> str:
    """En modo v2 el boton «Preparar demo» sale ya oculto y deshabilitado del servidor:
    no depende de que /api/status responda ni de que las fuentes v2 existan."""
    return html.replace(BOTON_PREPARAR, BOTON_PREPARAR[:-1] + ' hidden disabled '
                        'title="Panel de solo lectura en modo v2">')


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
  h1 { margin:0 0 0.2rem; font-size:1.15rem; letter-spacing:-0.01em; text-align:center; }
  h1 .logo { display:block; width:100%; max-width:240px; height:auto; margin:0 auto 0.4rem; }
  p.sub { text-align:center; }
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
  <h1><img class="logo" src="data:image/png;base64,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" alt="CyberFlow"></h1>
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


_CACHE_ORO: dict[str, object] = {}


def rango_oro(config_toml: Path | None, nombres: list[str],
              respaldo: Path | None = None) -> dict:
    """Rango normal de cada variable segun el conjunto de oro: {nombre: [lo, hi]}.

    Son los mismos cuantiles con los que el saneamiento decide que una fila es
    atipica (cuantil_referencia de la politica), asi el panel y el aprendizaje
    no usan dos definiciones de «normal». El oro no cambia: se calcula una vez
    y se guarda mientras el fichero sea el mismo. Sin oro, vacio.
    """
    if respaldo is None:
        respaldo = TOML_LOCAL
    if config_toml is None and respaldo is not None and Path(respaldo).is_file():
        config_toml = respaldo
    if config_toml is None:
        return {}
    try:
        modulo = Path(__file__).resolve().parents[1] / "modeling"
        if str(modulo) not in sys.path:
            sys.path.insert(0, str(modulo))
        import cyberflow_aprendizaje as ap
        cfg = ap.cargar_config(config_toml)
        ruta = ap.ruta_politica(cfg, "oro")
        if ruta is None or not ruta.is_file():
            return {}
        st = ruta.stat()
        sello = (str(ruta), st.st_mtime_ns, st.st_size)
        if _CACHE_ORO.get("sello") == sello:
            return _CACHE_ORO["rangos"]          # type: ignore[return-value]
        q = float(cfg["politica"]["cuantil_referencia"])
        columnas: dict[str, list[float]] = {}
        with ruta.open(newline="", encoding="utf-8") as fh:
            import csv
            lector = csv.reader(fh)
            cabecera = next(lector, [])
            idx = [(n, cabecera.index(n)) for n in nombres if n in cabecera]
            for n, _ in idx:
                columnas[n] = []
            for fila in lector:
                for n, i in idx:
                    try:
                        columnas[n].append(float(fila[i]))
                    except (ValueError, IndexError):
                        pass
        rangos = {n: [ap.cuantil(v, 1 - q), ap.cuantil(v, q)] for n, v in columnas.items() if v}
        _CACHE_ORO.update(sello=sello, rangos=rangos)
        return rangos
    except (OSError, ValueError, KeyError, SystemExit):
        return {}


def muestra_del_dataset(dataset: Path, nombres: list[str],
                        max_bytes: int = 524_288) -> dict:
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

        # Las ultimas ventanas, en orden: de cada una se toma el maximo entre
        # entidades, que es lo que un analista mira primero en una variable.
        por_ventana: dict[str, list[list[str]]] = {}
        if i_ven is not None:
            for c in filas:
                por_ventana.setdefault(c[i_ven], []).append(c)
        ultimas = sorted(por_ventana)[-60:]

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
            serie: list[float] = []
            ultimo = None
            for ven in ultimas:
                mejor = None
                for c in por_ventana[ven]:
                    try:
                        v = float(c[i])
                    except ValueError:
                        continue
                    if mejor is None or v > mejor[0]:
                        mejor = (v, c)
                if mejor is not None:
                    serie.append(mejor[0])
                    ultimo = fila_ejemplo(mejor[1], mejor[0])
            salida[nombre] = {
                "serie": serie,
                "ultimo": ultimo,
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
                      descripciones_path: Path, dataset: Path | None,
                      rangos: dict | None = None) -> dict:
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
            "rango": (rangos or {}).get(f["name"]),
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


def artefactos_aprendizaje(r: Path, config_usada: Path, log_path: Path,
                           eve_path: Path) -> dict:
    """Ficheros de cada paso del aprendizaje supervisado (fila 3 de la vista)."""
    apr = r / "artifacts" / "aprendizaje"
    base = ""
    try:
        with config_usada.open("rb") as fh:
            base = tomllib.load(fh).get("reentrenamiento", {}).get("base", "")
    except (OSError, ValueError):
        pass

    def ultimo(patron: str, tipo: str, que: str) -> dict:
        hallados = sorted(apr.glob(patron))
        if hallados:
            return _stat_fichero(hallados[-1], tipo, que)
        return {"ruta": str(apr / patron), "tipo": tipo, "que": que, "existe": False}

    script = _stat_fichero(r / "scripts/modeling/cyberflow_aprendizaje.py", "py",
                           "cyberflow_aprendizaje.py")
    return {
        "c_vivo": [_stat_fichero(log_path, "log", "decisiones: de aqui salen las IPs marcadas"),
                   _stat_fichero(r / "scripts/engine/motor_decision.py", "py", "el motor")],
        "a_oro": [_stat_fichero(apr / "oro/oro.csv", "csv", "conjunto de oro, solo lectura"),
                  _stat_fichero(apr / "oro/oro.json", "json", "su sha256 y su origen")]
                 + ([_stat_fichero(r / base, "csv", "base: particion de la calibracion")]
                    if base else []),
        "a_san": [dict(script, que="orden «lote»: los tres filtros"),
                  ultimo("lotes/lote-*.csv", "csv", "ultimo lote saneado"),
                  _stat_fichero(eve_path, "json", "alertas de Suricata (contaminacion)")],
        "a_lin": [_stat_fichero(apr / "registro.jsonl", "jsonl",
                                "registro encadenado: sha256 de cada lote"),
                  dict(script, que="orden «verificar»: comprueba la cadena")],
        "a_der": [_stat_fichero(apr / "deriva.jsonl", "jsonl", "una medicion por noche"),
                  dict(script, que="orden «deriva»")],
        "a_inf": [ultimo("candidatos/*/modelo.joblib", "joblib", "ultimo candidato"),
                  _stat_fichero(r / "scripts/modeling/promover_preliminar.py", "py",
                                "paquete -> Pipeline + manifiesto"),
                  _stat_fichero(r / "scripts/dataset/particionar_linea_base.py", "py",
                                "particion sin fuga")],
        "a_ver": [ultimo("candidatos/*/candidato.json", "json",
                         "veredicto, resultados y linaje del candidato")],
        "a_hum": [_stat_fichero(apr / "modelos.jsonl", "jsonl", "historial promover/revertir"),
                  _stat_fichero(config_usada, "toml", "lo que cambia «promover» (con copia)"),
                  _stat_fichero(Path("/etc/systemd/system/cyberflow-aprendizaje.timer"),
                                "timer", "temporizador nocturno (00:30 UTC)")],
    }


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
        "reentrenamiento": [rel("scripts/modeling/cyberflow_aprendizaje.py", "py",
                                "reentrenamiento con aprobación humana: lote, deriva, candidato"),
                            rel("artifacts/aprendizaje/registro.jsonl", "jsonl",
                                "linaje: un registro encadenado por lote"),
                            _stat_fichero(config_usada, "toml", "politica: seccion [reentrenamiento]")],
        "clientes": [rel("scripts/laboratorio/clientes_lab.py", "py",
                         "genera el trafico legitimo: perfiles, acciones y horarios (factor_horario)"),
                     rel("scripts/laboratorio/clientes_config.py", "py",
                         "orquestador: genera las unidades systemd, un servicio por IP"),
                     rel("scripts/laboratorio/servidor_lab.py", "py",
                         "servidor de pruebas: endpoints que alimentan cada variable")],
        "servidor": [rel("scripts/laboratorio/servidor_lab.py", "py",
                         "servidor HTTP/HTTPS del laboratorio: /estatico/<n>k y /api/*")],
        **artefactos_aprendizaje(r, config_usada, log_path, eve_path),
        "heuristicos": [rel("scripts/engine/heuristicos.py", "py",
                            "las cuatro reglas y sus umbrales")],
        "control": [rel("scripts/engine/responder_iptables.py", "py",
                        "bloqueo con interlock de calibracion"),
                    rel("scripts/engine/publicar_feed.py", "py",
                        "fusiona por IP la accion mas severa y aplica nunca-bloquear"),
                    rel("scripts/engine/escalada.py", "py",
                        "escalera de caducidad por reincidencia (300/1800/3600 s)")],
        # El tramo de respuesta distribuida (feed firmado + agente en el host).
        # Se declara aqui para que el visor pueda MOSTRAR su codigo: antes estos
        # ficheros se citaban en los diagramas pero /api/archivo los rechazaba.
        "feed": [rel("scripts/engine/publicar_feed.py", "py",
                     "publica el feed firmado desde las decisiones del motor"),
                 rel("scripts/engine/feed.py", "py",
                     "construye y FIRMA el feed (ed25519 via openssl)"),
                 rel("scripts/engine/escalada.py", "py",
                     "caducidad por reincidencia; nunca bloqueo permanente automatico")],
        "agente": [rel("scripts/enforce/agente_enforce.py", "py",
                       "trae el feed, verifica la firma y aplica nftables (corre en el host)")],
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
        "--comparacion", type=Path, default=None,
        help="episodios de la comparacion con Suricata (docs/evaluacion/comparacion-suricata.json)")
    parser.add_argument(
        "--feed-path", type=Path, default=Path.home() / "feed" / "feed.json",
        help="feed publicado por publicar_feed.py: caducidad exacta de cada accion")
    parser.add_argument(
        "--peticion-preparar", type=Path, default=Path.home() / "feed" / "peticiones" / "preparar.json",
        help="petición «Preparar demo» del panel; publicar_feed la mete en el feed firmado")
    parser.add_argument(
        "--comparaciones-dir", type=Path, default=Path.home() / "feed" / "comparaciones",
        help="resumenes de comparar-suricata.sh (seccion CyberFlow frente a Suricata)")
    parser.add_argument(
        "--acuse-dir", type=Path, default=Path.home() / "feed" / "acuses",
        help="acuses de aplicacion de los hosts protegidos (los deja el relay): paso 5 del escenario")
    parser.add_argument(
        "--feed-estado", type=Path, default=Path.home() / "feed" / "estado.json",
        help="estado de la escalera del publicador: nivel de reincidencia por IP")
    parser.add_argument(
        "--control-d5", type=Path, default=Path.home() / "feed-v2" / "d5" / "control" / "control.json",
        help="«Dejar limpio» (v2): control D5 que consume publicar_feed_v2_d5 (--control-d5)")
    parser.add_argument(
        "--cadena-v2-dir", type=Path, default=Path.home() / "feed-v2",
        help="salidas del publicador v2 (senales-if.jsonl, traza.jsonl, feed.json) que lee el "
             "panel en modo v2. Si faltan, el panel sigue en v2 y lo declara como incidencia")
    parser.add_argument(
        "--modo-panel", choices=("v2", "v1-historico"), default="v2",
        help="v2 (por omision, el de la investigacion): la accion es solo la medida que publico el "
             "publicador v2. v1-historico: la politica v1 del panel, solo para presentar la demo "
             "historica. Nunca se pasa de v2 a v1 por un fallo de las fuentes (cierre de la 4A)")
    parser.add_argument(
        "--sin-cadena-v2", action="store_true",
        help="equivale a --modo-panel v1-historico (seleccion explicita; solo demo historica)")
    parser.add_argument(
        "--modo-respuesta", choices=("sombra", "activo"), default="sombra",
        help="modo declarado del agente v2: en sombra las medidas son propuestas y su aplicacion "
             "«no ejecutada»; en activo, sin evidencia del host, «desconocido»")
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
        "--config-toml",
        type=Path,
        default=None,
        help="el .toml del despliegue: de el sale la politica de reentrenamiento "
             "y donde estan sus lotes, su deriva y sus candidatos",
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
    model_summary["evaluacion"] = evaluacion_del_vigente(args.detector_name)
    global _CADENA_V2
    modo_panel = modo_panel_de(args)
    if modo_panel == "v2":
        # Cierre de la 4A: el modo v2 NO depende de que existan sus ficheros. Si faltan al
        # arrancar (o desaparecen despues), el panel sigue en v2 y lo muestra como incidencia.
        _CADENA_V2 = cadena_v2.IndiceV2(args.cadena_v2_dir, args.modo_respuesta)
        inc = _CADENA_V2.resumen(time.time())["incidencias"]
        print(f"panel: modo v2, cadena desde {args.cadena_v2_dir} (modo {args.modo_respuesta}); "
              "«Preparar demo» deshabilitado"
              + ("; INCIDENCIA: " + "; ".join(inc) if inc else ""), file=sys.stderr, flush=True)
    else:
        print("panel: modo v1-historico seleccionado explicitamente (politica v1 del panel)",
              file=sys.stderr, flush=True)
    red_vigilada = None if args.demo else red_analizada(args.entity_network, args.config_toml)
    # Sin --dataset, el que declara el .toml en [rutas]: asi el pulso puede decir
    # cuantas filas se llevan acumuladas sin tocar la unidad del servicio.
    if args.dataset is None and args.config_toml and not args.demo:
        try:
            rutas = tomllib.loads(Path(args.config_toml).read_text(encoding="utf-8")).get("rutas", {})
            candidato = Path(rutas.get("raiz", ".")) / rutas["dataset"]
            if candidato.is_file():
                args.dataset = candidato
        except (OSError, KeyError, ValueError, TypeError):
            pass

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
    if _CADENA_V2 is not None:
        HTML_POR_ROL = {rol: html_solo_lectura_v2(h) for rol, h in HTML_POR_ROL.items()}

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

            if path == "/api/demo/limpiar":
                s = self._sesion()
                if not s or s.get("rol") != "admin" or self.headers.get("X-CyberFlow") != "1":
                    self.send_error(403)
                    return
                if _CADENA_V2 is None:
                    self._send_json({"ok": False, "motivo": "solo con la cadena v2 (usa «Preparar demo»)"})
                    return
                try:
                    r = pedir_limpieza_v2(args.control_d5, s["usuario"], time.time())
                except OSError as ex:
                    r = {"ok": False, "motivo": "el panel no puede escribir el control D5 (%s)" % ex.__class__.__name__}
                auditar(args.auditoria, "dejar-limpio", s["usuario"], self._origen(), s["rol"],
                        "id=%s ok=%s" % (r.get("id"), r.get("ok")))
                self._send_json(r)
                return

            if path == "/api/demo/preparar":
                if _CADENA_V2 is not None:
                    # 4A: el panel es de solo lectura; la peticion viajaba por el feed v1.
                    body = json.dumps({"ok": False, "motivo": "panel de solo lectura con la cadena v2: "
                                       "«Preparar demo» deshabilitado"}).encode("utf-8")
                    self.send_response(409)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                s = self._sesion()
                # Solo un administrador, y solo desde el propio panel (cabecera propia:
                # un formulario de otro sitio no puede añadirla sin CORS).
                if not s or s.get("rol") != "admin" or self.headers.get("X-CyberFlow") != "1":
                    self.send_error(403)
                    return
                pet = pedir_preparacion(args.peticion_preparar, s["usuario"], time.time())
                auditar(args.auditoria, "preparar-demo", s["usuario"], self._origen(), s["rol"],
                        ",".join(pet["ips"]) + " id=" + pet["id"])
                self._send_json({"ok": True, "peticion": pet})
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
            self._bytes_resp = len(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            # Rendimiento por ruta (3-nov): cuantas, cuanto tardan y cuanto pesan.
            # Se vuelca cada 30 s a logs/panel_rendimiento.json para ver que
            # vista carga al sensor sin tener que adivinar.
            t0 = time.perf_counter()
            self._bytes_resp = 0
            try:
                self._do_get()
            finally:
                medir_ruta(self.path.partition("?")[0], time.perf_counter() - t0,
                           self._bytes_resp, args.log_path.parent / "panel_rendimiento.json")

        def _do_get(self) -> None:
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
                # Todas las pestanas sondean cada 5 s y cada estado lanza systemctl y
                # sudo: se calcula una vez cada STATUS_CACHE_S y se comparte.
                with _STATUS_LOCK:
                    if "datos" in _STATUS_CACHE and \
                            time.monotonic() - _STATUS_CACHE.get("t", -1e9) < STATUS_CACHE_S:
                        self._send_json(_STATUS_CACHE["datos"])
                        return
                    _STATUS_CACHE["t"] = time.monotonic()
                decisions = read_decisions(args.log_path, limit=2000)
                ahora = time.time()
                servicios = service_status([] if args.demo else service_names)
                contadores = compute_counters(decisions, detector_modelo=args.detector_name)
                calibr = {"calibrado_en_esta_red": args.calibrado_en_esta_red}
                # eve.json primero: no necesita privilegios. El ayudante queda
                # como respaldo para despliegues que lo tengan.
                captura = (suricata_stats_desde_eve(args.eve_path)
                           or suricata_metrics(args.suricata_metrics_command))
                # Drops: delta contra la lectura anterior, para no pintar en rojo
                # un acumulado heredado del arranque. El estado se adjunta a la
                # propia metrica y se memoriza para la proxima lectura.
                de = drops_estado(captura, _CAPTURA_PREVIA.get("v"), ahora)
                if captura is not None:
                    captura["drops_estado"] = de
                    _CAPTURA_PREVIA["v"] = {"medido_en": de.get("marca"),
                                            "total": de.get("total")}
                _STATUS_CACHE["datos"] = datos_status = (
                    {
                        "modo": "demo" if args.demo else "live",
                        "services": servicios,
                        # La franja de salud se decide aqui (una sola verdad,
                        # testeable): el frontend solo la pinta.
                        "salud": resumen_salud(
                            "demo" if args.demo else "live",
                            servicios, contadores, de, calibr),
                        "model": model_summary,
                        "blocked": enforcement_list(args.enforce_command),
                        "vigentes": acciones_vigentes(
                            decisions, ahora,
                            None if args.demo else args.feed_path,
                            None if args.demo else args.feed_estado),
                        "acuses": [] if args.demo else acuses_resumen(args.acuse_dir, ahora),
                        # Con la cadena v2 los acuses del agente v1 son evidencia HISTORICA de
                        # aplicacion (el agente v1 esta parado), no el estado actual del host.
                        "acuses_v1_historicos": _CADENA_V2 is not None,
                        "cadena_v2": _CADENA_V2.resumen(ahora) if _CADENA_V2 is not None
                        else {"activa": False},
                        "counters": contadores,
                        "activity": bucket_by_minute(decisions),
                        "capture_metrics": captura,
                        "alcance": dict(leer_alcance(args.log_path),
                                        **({"red_entidades": red_vigilada} if red_vigilada else {})),
                        "pulso": pulso_ingesta(
                            decisions, None if args.demo else args.eve_path,
                            args.dataset, None if args.demo else args.feed_path,
                            ahora),
                        "calibracion": calibr,
                    }
                )
                self._send_json(datos_status)
                return
            if path == "/api/escenario":
                params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                self._send_json(estado_escenario(
                    args.log_path, urllib.parse.unquote(params.get("ip", "")),
                    params.get("desde", ""), time.time(),
                    None if args.demo else args.feed_path,
                    None if args.demo else args.feed_estado,
                    None if args.demo else args.acuse_dir))
                return
            if path == "/api/acciones":
                self._send_json(historial_acciones(args.log_path, time.time()))
                return
            if path == "/api/lista-blanca":
                self._send_json(estado_lista_blanca(
                    LISTA_BLANCA_PATH, None if args.demo else args.cadena_v2_dir / "feed.json", time.time()))
                return
            if path == "/api/despliegue":
                self._send_json(inventario_despliegue())
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
                    # El rango del oro, una vez leido el esquema: no depende
                    # del dataset y se calcula una sola vez por fichero de oro.
                    rangos = rango_oro(
                        args.config_toml,
                        [v["name"] for v in _CACHE_VARIABLES["datos"]["variables"]])
                    for v in _CACHE_VARIABLES["datos"]["variables"]:
                        v["rango"] = rangos.get(v["name"])
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
            if path in ("/api/vivo", "/api/vivo/flujo", "/api/trazabilidad"):
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
                if params.get("abierta") != "1":
                    # Una pestaña con el JS de antes pedía esto aunque la sección
                    # estuviera cerrada, y cada /api/vivo es ~1 min de CPU con el GIL.
                    self._send_json({"error": "Versión antigua del panel en esta pestaña: "
                                              "recárgala con Ctrl+F5."})
                    return
                try:
                    if path == "/api/vivo/flujo":
                        # El cursor lo guarda el navegador. Del fichero solo se
                        # acepta el NOMBRE, y vista_vivo lo busca entre los del
                        # anillo: no hay ruta que se pueda colar.
                        cursor = {}
                        pf = urllib.parse.unquote(params.get("pf", ""))
                        if pf and "/" not in pf and "\\" not in pf:
                            cursor["pf"] = pf
                        for clave in ("po", "pn", "eo"):
                            if params.get(clave, "").isdigit():
                                cursor[clave] = int(params[clave])
                        self._send_json(vista_vivo.flujo(
                            args.eve_path, cfg, cursor, todos=params.get("todos") == "1"))
                        return
                    limite = params.get("limite", "150")
                    # Un solo cálculo a la vez y como mucho uno cada VIVO_MIN_S: si ya
                    # hay uno en marcha se sirve el último (o se avisa), no se encola.
                    if not _VIVO_LOCK.acquire(blocking=False):
                        self._send_json(_VIVO_ULTIMO.get("datos") or {"error": "calculando"})
                        return
                    try:
                        if "datos" in _VIVO_ULTIMO and time.monotonic() - _VIVO_ULTIMO["t"] < VIVO_MIN_S:
                            datos_vivo = _VIVO_ULTIMO["datos"]
                        else:
                            datos_vivo = vista_vivo.calcular_con_cache(
                                args.eve_path, cfg, todos=params.get("todos") == "1",
                                limite=min(int(limite), 3000) if limite.isdigit() else 150)
                            _VIVO_ULTIMO.update(t=time.monotonic(), datos=datos_vivo)
                    finally:
                        _VIVO_LOCK.release()
                    self._send_json(datos_vivo)
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": "%s: %s" % (type(exc).__name__, exc)})
                return
            if path == "/api/demo/limpieza":
                params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                self._send_json(estado_limpieza_v2(args.control_d5, args.cadena_v2_dir / "feed.json",
                                                   urllib.parse.unquote(params.get("id", ""))[:64], time.time()))
                return
            if path == "/api/demo/estado":
                self._send_json(estado_preparacion(args.peticion_preparar, args.log_path, args.feed_path,
                                                   None if args.demo else args.acuse_dir, time.time()))
                return
            if path == "/api/comparacion":
                datos = estado_comparacion(args.comparacion)
                datos["en_vivo"] = comparaciones_en_vivo(args.comparaciones_dir)
                self._send_json(datos)
                return
            if path == "/api/aprendizaje":
                self._send_json(estado_aprendizaje_cacheado(args.config_toml, args.demo))
                return
            if path == "/api/decisions":
                params = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
                if "desde" in params or "hasta" in params:
                    def _t(v):
                        try:
                            return float(v) if v else None
                        except ValueError:
                            return None
                    self._send_json(consultar_periodo(
                        args.log_path, _t(params.get("desde")), _t(params.get("hasta"))))
                    return
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
                self._send_json(histogram_scores(decisions, model_summary["threshold"],
                                                 num_buckets=24))
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
