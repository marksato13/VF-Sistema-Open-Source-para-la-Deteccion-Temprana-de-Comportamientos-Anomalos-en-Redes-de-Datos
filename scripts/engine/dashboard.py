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
from datetime import datetime
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
    /* 13-oct: subido de #7c8bad a #8d9cbd. El anterior daba 4,59:1 sobre las
       tarjetas (AA justo, sin margen) y se perdia proyectado; este da 5,68:1
       y sigue 2,3x mas tenue que --text, asi que la jerarquia se mantiene. */
    --text-dim: #8d9cbd;
    --accent: #5eead4;
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
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--sans); font-size: 15px; line-height: 1.5;
  }

  /* --- Distribucion: barra lateral fija + contenido --- */
  .shell { display: grid; grid-template-columns: 224px minmax(0, 1fr); }
  /* Sin esto, el ancho de contenido minimo de la barra (su nav) estira la
     columna mas que la pantalla y el documento desborda en movil: el min-width:0
     deja que la pista encoja por debajo del contenido y la barra scrollee dentro. */
  .shell > * { min-width: 0; }
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
    .shell { display: block; }
    .side {
      position: static; height: auto; border-right: none; border-bottom: 1px solid var(--border);
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
  #histogram { display: block; width: 100%; height: 190px; }
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
  .al-card.al-block { border-left-color: var(--danger); }
  .al-card.al-limit { border-left-color: var(--amber); }
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
  .topo-pkt { fill: var(--accent); filter: drop-shadow(0 0 4px var(--accent)); }
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
  .perfiles { display: grid; gap: 0.35rem; margin: 0.4rem 0 0.2rem; }
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
  .cmp-fig { background: #0f1722; border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem; margin-bottom: 0.9rem; }
  .cmp-fig svg { width: 100%; height: auto; display: block; }
  .cmp-notas { margin: 0.5rem 0 0; padding-left: 1.1rem; color: var(--text-dim); font-size: 0.8rem; line-height: 1.5; }
  td.cmp-bien { color: var(--ok); } td.cmp-mal { color: var(--danger); } td.cmp-nm { color: var(--text-dim); font-style: italic; }
  tr.cmp-total td { font-weight: 600; border-top: 2px solid var(--border); }

  /* Actividad: cifras por accion y las IPs que mas actuaron. */
  .act-cols { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1rem; margin-top: 0.9rem; }
  @media (max-width: 900px) { .act-cols { grid-template-columns: 1fr; } }
  .act-h { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); margin: 0 0 0.45rem; font-weight: 600; }

  /* Alertas flotantes: una por IP y accion, apiladas arriba a la derecha. */
  .toasts { position: fixed; top: 16px; right: 16px; z-index: 400; display: flex; flex-direction: column; gap: 10px; width: min(380px, calc(100vw - 32px)); pointer-events: none; }
  .toast { pointer-events: auto; background: var(--surface-2); border: 1px solid var(--border); border-left: 5px solid var(--amber);
    border-radius: 10px; padding: 0.75rem 0.9rem 0.7rem; box-shadow: 0 10px 30px rgba(0,0,0,0.45); cursor: pointer;
    animation: toast-in .25s ease-out; }
  .toast.block { border-left-color: var(--danger); }
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
</style>

<div class="shell">
<aside class="side">
  <div class="brand">CyberFlow<small>Motor en vivo</small></div>
  <div class="side-state" id="sideState"><span class="dot"></span><span id="sideStateText">conectando&hellip;</span></div>
  <nav id="nav">
    <div class="nav-grupo">Vigilancia</div>
    <a href="#s-salud" data-sec="s-salud"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/></svg>Salud</a>
    <a href="#s-actividad" data-sec="s-actividad"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,12 7,12 9,6 13,18 15,12 22,12"/></svg>Actividad</a>
    <a href="#s-alertas" data-sec="s-alertas"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.8 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13.5"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg>Alertas<span class="pill" id="navAlertPill" hidden></span></a>
    <a href="#s-decisiones" data-sec="s-decisiones"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>Decisiones</a>
    <a href="#s-bloqueos" data-sec="s-bloqueos"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>Bloqueos</a>
    <a href="#s-scores" data-sec="s-scores"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg>Scores</a>
    <!--ADMIN-->
    <div class="nav-grupo">Sistema</div>
    <a href="#s-topologia" data-sec="s-topologia"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg>Mapa del sistema</a>
    <a href="#s-despliegue" data-sec="s-despliegue"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="3" y="17" width="6" height="5" rx="1"/><rect x="15" y="17" width="6" height="5" rx="1"/><path d="M12 7v4M6 17v-3h12v3"/></svg>Despliegue</a>
    <a href="#s-alcance" data-sec="s-alcance"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><line x1="5" y1="19" x2="19" y2="5"/></svg>Alcance</a>
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
      <button id="avisosBtn" class="btn-avisos" type="button" data-on="1"
        title="Alertas flotantes cuando una IP recibe LIMIT o BLOCK">Avisos: sí</button>
      <span class="quien" id="quien"></span>
      <form method="post" action="/logout"><button class="btn-salir" type="submit">Salir</button></form>
    </div>
  </header>

  <div class="toasts" id="toasts" aria-live="polite"></div>

  <!-- El resumen (KPIs, barra de salud y pulso) vive en la pagina Salud, no
       como franja repetida en todas: antes se veia identico en cada seccion y
       daba sensacion de que "todo mostraba lo mismo". El estado sigue siempre a
       la vista en la barra lateral (punto + texto + pastilla de alertas). -->
  <section id="s-salud">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.9" fill="currentColor" stroke="none"/></svg><h2>Salud del sistema</h2></div>
    <div class="kpi-row" id="kpis"></div>
    <div class="healthbar" id="healthbar"></div>
    <div class="pulso" id="pulso" aria-label="Pulso de la ingesta"></div>
    <div class="grid" id="health"></div>
  </section>

  <!--ADMIN-->
  <section id="s-topologia">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="5" cy="6" r="2.4"/><circle cx="19" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7 7.4 10.4 16M16.9 7.5 13.6 16"/></svg><h2>Mapa del sistema</h2></div>
    <p class="lede-small">Pulsa un componente para ver su detalle.</p>
    <div class="topo-wrap" id="topoWrap">
      <div class="topo-canvas" id="topoCanvas">
        <div class="topo-bar">
          <div class="range-toggle" id="topoVista">
            <button data-vista="metodologica" class="active">1 · Fases del método</button>
            <button data-vista="red">2 · Red y captura</button>
            <button data-vista="completa">3 · Operacional</button>
            <button data-vista="construccion">4 · Construcción y entrenamiento</button>
            <button data-vista="decision">5 · Decisión</button>
            <button data-vista="respuesta">6 · Respuesta</button>
            <button data-vista="carpetas">7 · Carpetas</button>
            <button data-vista="validacion">8 · Validación</button>
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
    <p class="lede-small">Dónde está instalado cada componente y cómo viaja el feed firmado del sensor a los hosts protegidos. El sensor no tiene credenciales de los demás hosts: su estado sale de los servicios reales; el resto es el despliegue declarado.</p>
    <div class="desp" id="despliegue"></div>
    <p class="toolbar-hint" id="desplieguePie"></p>
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
    <div class="fam-wrap" id="modeloFamilias"></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="16.5" r="0.7" fill="currentColor" stroke="none"/></svg><span id="modeloDebil"><strong>Punto débil conocido:</strong> un PERMIT del modelo no descarta un ataque por sí solo; los heurísticos cubren lo que el modelo no ve.</span></div>

    <p class="lede-small" id="pruebasPrevias" style="margin-top:1.4rem"><strong style="color:var(--text)">Pruebas previas &mdash; comparación exploratoria de modelos (laboratorio).</strong> Se compararon <strong>7 candidatos</strong> con las mismas variables y la misma partición (<code>compare_frozen_models_metrics.py</code>, auditable desde <em>Mapa &rarr; Ver archivos</em>). El conjunto positivo son 179 ventanas de anomalía; el negativo, 276 ventanas normales de prueba. Se reportan F1, MCC, ROC&#8209;AUC y precisión media, sin reentrenar y verificando cada modelo contra el manifiesto. Ahí ganó el OCSVM, pero <strong>la selección se hizo tras ver la prueba</strong> (sesgo declarado) y no transfirió a esta red.</p>

    <p class="lede-small" style="margin-top:1rem"><strong style="color:var(--text)">Comparación sobre ESTA red &mdash; la que decide el despliegue.</strong> El ganador de laboratorio (OCSVM), con su umbral, marca el <strong>99,6 %</strong> del tráfico normal de esta red como anomalía: inservible aquí. Por eso se vuelve a comparar sobre datos propios &mdash; <strong>65 421 ventanas normales</strong> del conjunto de oro (para el FPR) y <strong>84 ventanas de ataque</strong> de la Kali (para la detección) &mdash;, cargando cada <code>joblib</code> congelado sin reentrenar.</p>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Modelo</th><th class="r">ROC-AUC</th><th class="r">PR-AUC</th><th class="r">FPR</th><th class="r">Det. @ FPR 5%</th></tr></thead>
      <tbody>
        <tr><td style="box-shadow:inset 3px 0 0 var(--ok)"><b>IF recalibrado (desplegado)</b></td><td class="num r">0,923</td><td class="num r">0,203</td><td class="num r">4,45&#8239;%</td><td class="num r"><b>66,7&#8239;%</b></td></tr>
        <tr><td>IF scaled (lab)</td><td class="num r">0,825</td><td class="num r">0,004</td><td class="num r">30,3&#8239;%</td><td class="num r">16,7&#8239;%</td></tr>
        <tr><td>IF primary (lab)</td><td class="num r">0,828</td><td class="num r">0,004</td><td class="num r">29,1&#8239;%</td><td class="num r">16,7&#8239;%</td></tr>
        <tr><td>IF uniform (lab)</td><td class="num r">0,796</td><td class="num r">0,005</td><td class="num r">34,1&#8239;%</td><td class="num r">16,7&#8239;%</td></tr>
        <tr><td>OCSVM <small style="color:var(--text-dim)">(ganó en lab)</small></td><td class="num r">0,456</td><td class="num r">0,001</td><td class="num r">99,6&#8239;%</td><td class="num r">0,0&#8239;%</td></tr>
        <tr><td>LOF (lab)</td><td class="num r">0,299</td><td class="num r">0,001</td><td class="num r">76,8&#8239;%</td><td class="num r">0,0&#8239;%</td></tr>
        <tr><td>Elliptic Envelope (lab)</td><td class="num r">0,344</td><td class="num r">0,001</td><td class="num r">86,9&#8239;%</td><td class="num r">6,0&#8239;%</td></tr>
      </tbody>
    </table></div>
    <p class="toolbar-hint"><b>Gana el Isolation Forest recalibrado</b> en todas las métricas robustas al desbalance. A igualdad de FPR (5&#8239;%) detecta 66,7&#8239;% frente al 16,7&#8239;% del mejor de laboratorio; el OCSVM queda en ROC-AUC 0,456 (por debajo del azar). Diferencia significativa vs OCSVM/LOF (McNemar + Holm, p&lt;0,001). Gráficos (ROC, PR, separación de scores) en el repositorio de orquestación.</p>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Cómo se comparó.</strong> Dos lecturas: (1) con el <strong>umbral calibrado</strong> de cada modelo &rarr; mide si transfiere a esta red; (2) recalibrando todos al <strong>mismo 5&#8239;% de FPR</strong> sobre el oro &rarr; compara solo la arquitectura, a igualdad de falsos positivos. Se usan métricas robustas al desbalance (prevalencia 0,13&#8239;%): ROC-AUC, PR-AUC, FPR y detección; la precisión y el F1 son bajos para todos por construcción (miles de FP frente a decenas de TP), por eso no son el titular.</span></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>El cálculo (matemático).</strong> El Isolation Forest aísla cada ventana con árboles aleatorios: cuanto <strong>más corto el camino</strong> para aislarla, más rara &rarr; score de anomalía. <code>score_samples(x)</code> devuelve ese score y la decisión es <code>score &lt; &theta;</code>, con el umbral <strong>&theta; congelado como el percentil &alpha;=0,05 de validación</strong> (objetivo de 5&#8239;% de FPR fijado ANTES de mirar la prueba: &theta;&nbsp;=&nbsp;&minus;0,568892). <strong>ROC-AUC</strong> = probabilidad de ordenar un ataque por delante de un normal; <strong>PR-AUC</strong> = área precisión-recall (la honesta con desbalance). La significancia entre pares se mide con <strong>McNemar</strong> sobre sus aciertos/errores y se corrige por comparaciones múltiples con <strong>Holm</strong>.</span></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Archivos y código</strong> (auditables desde <em>Mapa &rarr; Ver archivos</em>, con pseudocódigo y diagrama de flujo): <code>entrenar_preliminar.py</code> entrena y congela el umbral; <code>promover_preliminar.py</code> arma el Pipeline + manifiesto; <code>verificar_equivalencia_umbral.py</code> comprueba hash, orden y umbral; <code>compare_frozen_models_metrics.py</code> reproduce las métricas de los 7; <code>significancia_modelos.py</code> hace McNemar + Holm. Los 7 candidatos congelados están en <code>artifacts/model/candidates/*.joblib</code>.</span></div>
    <p class="lede-small">Y la detección no la hace el modelo solo. La <strong>ablación por componentes</strong> mide qué aporta cada pieza sobre 9 episodios (3 familias con 3 repeticiones):</p>
    <div class="grid">
      <div class="card"><div class="label">Modelo solo</div><div class="value">6 / 9</div></div>
      <div class="card"><div class="label">Heurísticos solos</div><div class="value">7 / 9</div></div>
      <div class="card accent"><div class="label">Modelo + heurísticos</div><div class="value">9 / 9</div></div>
    </div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span>La <strong>complementariedad es el resultado medido</strong>: el modelo detectó flood HTTP y escaneo en esta batería, pero <strong>0/3 DNS</strong>; el heurístico DNS cubrió ese hueco. La fuerza bruta en vivo la confirma el heurístico <code>brute_force</code>. La combinación cubrió 9/9 episodios de las tres primeras familias; no significa que el modelo solo los cubra. La comparación con Suricata y sus límites están en la nota 32 del repositorio de orquestación.</span></div>
  </section>

  <section id="s-comparacion">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18V8M10 18V4M16 18v-6M22 18H2"/></svg><h2>Comparación con Suricata</h2></div>
    <p class="lede-small"><b>Por qué Suricata:</b> es el IDS de firmas de referencia, el estándar con el que contrastar. <b>Cómo se comparó:</b> el MISMO PCAP de cada episodio se reprodujo a los dos con el reloj del paquete y la configuración congelada (Suricata con ET Open, 53 013 reglas); qué es un ataque lo fija la REFERENCIA —el orquestador que lanzó el ataque—, no las alertas de ninguno. <b>Qué se mide:</b> detección por episodio, no bloqueo, porque en el espejo SPAN Suricata es IDS (ve una copia, no está en línea). <b>Resultado:</b> Suricata detecta lo que tiene firma (Nikto); CyberFlow detecta además lo que NO la tiene (escaneo, flood, DNS: 0 para Suricata) y encima BLOQUEA, que Suricata en SPAN no puede. No lo reemplaza: lo complementa.</p>
    <div class="cmp-fig">
      <svg viewBox="0 0 900 250" role="img" aria-label="Protocolo: entrada común y referencia independiente, cuatro condiciones, evaluación por episodio">
        <defs><marker id="cmpFl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#8aa0b4"/></marker></defs>
        <g font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="13" fill="#dce8f5">
          <rect x="10" y="30" width="190" height="72" rx="10" fill="#15202c" stroke="#3a5169"/>
          <text x="105" y="60" text-anchor="middle" font-weight="600">Entrada común</text>
          <text x="105" y="80" text-anchor="middle" fill="#9fb2c4" font-size="12">ataques · Nikto · tramo normal</text>
          <rect x="10" y="150" width="190" height="72" rx="10" fill="#2a1d12" stroke="#b5741b"/>
          <text x="105" y="180" text-anchor="middle" font-weight="600">Referencia</text>
          <text x="105" y="200" text-anchor="middle" fill="#e8c9a4" font-size="12">guion y orquestador</text>
          <rect x="290" y="10" width="250" height="44" rx="9" fill="#15202c" stroke="#3a5169"/>
          <text x="415" y="37" text-anchor="middle">Suricata · firmas</text>
          <rect x="290" y="66" width="250" height="44" rx="9" fill="#15202c" stroke="#3a5169"/>
          <text x="415" y="93" text-anchor="middle">Solo modelo · score</text>
          <rect x="290" y="122" width="250" height="44" rx="9" fill="#15202c" stroke="#3a5169"/>
          <text x="415" y="149" text-anchor="middle">Solo heurísticos · eventos EVE</text>
          <rect x="290" y="178" width="250" height="44" rx="9" fill="#0e3b3a" stroke="#5eead4"/>
          <text x="415" y="205" text-anchor="middle" font-weight="600">CyberFlow · combinado</text>
          <rect x="640" y="60" width="250" height="130" rx="10" fill="#15202c" stroke="#3a5169"/>
          <text x="765" y="92" text-anchor="middle" font-weight="600">Evaluación por episodio</text>
          <text x="765" y="116" text-anchor="middle" fill="#9fb2c4" font-size="12">detección por familia</text>
          <text x="765" y="136" text-anchor="middle" fill="#9fb2c4" font-size="12">latencia desde el inicio</text>
          <text x="765" y="156" text-anchor="middle" fill="#9fb2c4" font-size="12">falsos positivos aparte</text>
        </g>
        <g stroke="#8aa0b4" stroke-width="1.6" fill="none" marker-end="url(#cmpFl)">
          <path d="M200,66 L288,32"/><path d="M200,66 L288,88"/><path d="M200,66 L288,144"/><path d="M200,66 L288,200"/>
          <path d="M540,32 L638,110"/><path d="M540,88 L638,118"/><path d="M540,144 L638,128"/><path d="M540,200 L638,136"/>
        </g>
        <path d="M105,222 L105,242 L765,242 L765,194" stroke="#b5741b" stroke-width="1.6" fill="none" stroke-dasharray="5 4" marker-end="url(#cmpFl)"/>
      </svg>
    </div>
    <div class="tbl-wrap"><table><thead><tr><th>Familia</th><th class="r">Suricata</th><th class="r">Solo modelo</th><th class="r">Solo heurísticos</th><th class="r">CyberFlow</th></tr></thead><tbody id="cmpTabla"></tbody></table></div>
    <p class="toolbar-hint">Celda: episodios detectados / medidos · latencia mediana [mín–máx]. CyberFlow lee eventos de EVE, no alertas de Suricata. En SPAN, Suricata es IDS: se compara detección, no bloqueo.</p>
    <p class="toolbar-hint"><span class="badge heur">ejecutada</span> Batería N=3 por familia, con el mismo PCAP y la configuración fija. <span class="badge">propuesta</span> Campaña C3: N=5 por familia, fuerza bruta, tráfico legítimo intenso y 2 h de tráfico normal con los falsos positivos de Suricata medidos.</p>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Suricata NO está apagada:</strong> corre EN VIVO en el sensor y CyberFlow <strong>consume sus eventos</strong> (http/dns/tls) para las variables de capa 7 &mdash; es una <em>fuente</em> del sistema. Lo que se midió por <strong>replay</strong> (mismo PCAP a los dos, anclado al reloj del paquete) es su <strong>detección</strong>, no sus alertas en vivo: así los dos ven exactamente la misma entrada y la comparación de detección es limpia.</span></div>
    <div class="note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="0.7" fill="currentColor" stroke="none"/></svg><span><strong>Falsos positivos de Suricata: MEDIDO (14-oct).</strong> Sobre ~4 min de tráfico benigno real (112 556 paquetes, 335 flujos de clientes) reproducido con ET Open en el comparador: <strong>0 falsos positivos de firma de amenaza sobre los clientes</strong> (las 11 alertas restantes son anomalías de stream del espejo SPAN, no amenazas). Es el <strong>tradeoff precisión/recall</strong>: Suricata es muy preciso pero <strong>ciego a lo sin firma</strong> (0/3 DNS/flood/escaneo); CyberFlow detecta eso a cambio de un FPR de modelo del 4,45&#8239;% &mdash; acotado: va a LIMIT, nunca a BLOCK. Se complementan. (Detalle: <em>FPR-SURICATA-BENIGNO-2026-10-14.md</em>.)</span></div>
    <ul class="cmp-notas" id="cmpNotas"></ul>
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
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="14" width="4" height="7"/><rect x="10" y="8" width="4" height="13"/><rect x="17" y="3" width="4" height="18"/></svg><h2>Distribución de scores recientes</h2></div>
    <p class="lede-small">Qué tan cerca del umbral está pasando el tráfico reciente &mdash; no solo si alertó o no, sino cuánto margen hubo. La línea marca el umbral operativo.</p>
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
        <p class="act-h">IPs con más acciones</p>
        <div class="tbl-wrap">
          <table><thead><tr><th>IP</th><th class="r">Acciones</th><th>Última</th></tr></thead><tbody id="topIps"></tbody></table>
        </div>
      </div>
    </div>
  </section>

  <section id="s-alertas">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.8 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13.5"/><line x1="12" y1="17" x2="12" y2="17.01"/></svg><h2>Alertas</h2></div>
    <p class="sec-sub">Cada ventana en la que el sistema detectó algo: una <b>anomalía del modelo</b> (score por debajo del umbral) o una <b>regla disparada</b> (escaneo, fuerza bruta, abuso HTTP, DNS). A la derecha, la acción que provoca.</p>
    <div class="alertas-resumen" id="alertasResumen"></div>
    <div class="range-toggle" id="alertasFiltro">
      <button data-af="todas" class="active">Todas</button>
      <button data-af="modelo">Anomalía del modelo</button>
      <button data-af="regla">Reglas</button>
    </div>
    <div class="alertas-lista" id="alertasLista"></div>
  </section>

  <section id="s-bloqueos">
    <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg><h2>IPs bloqueadas ahora</h2></div>
    <p class="sec-sub" id="vigentesSub">LIMIT y BLOCK que el agente aplica en el host. <b>Reconstruido del registro del motor y del feed publicado</b>, no leído del nftables remoto: es el estado que el sensor <i>sabe</i> que publicó, no una verificación directa en el host. Por eso puede diferir del feed instantáneo (0 entradas entre ciclos) o del historial (un episodio ya caducado).</p>
    <div class="tbl-wrap">
      <table><thead><tr><th>IP</th><th>Acción</th><th>Motivo</th><th>Desde</th><th>Expira en</th><th>Reincidencia</th></tr></thead><tbody id="blocked"></tbody></table>
    </div>
    <p class="act-h" style="margin-top:1.2rem">Acciones de las últimas 24 h <span class="th-sub" id="histSub"></span></p>
    <div class="spark-wrap" style="margin-bottom:0.8rem">
      <svg id="histChart" class="hist-chart" role="img" aria-label="Línea de tiempo de acciones por IP en las últimas 24 horas"></svg>
      <div class="spark-legend">
        <span><i class="swatch" style="background:var(--danger)"></i>BLOCK</span>
        <span><i class="swatch" style="background:var(--amber)"></i>LIMIT</span>
        <span>cada barra es una racha de ventanas de la misma IP; la zona rayada es anterior al registro leído</span>
      </div>
    </div>
    <div class="tbl-wrap tbl-scroll" style="max-height:280px">
      <table><thead><tr><th>Inicio</th><th>IP</th><th>Acción</th><th>Motivo</th><th>Duración</th><th class="r">Ventanas</th><th>Estado</th></tr></thead><tbody id="histTabla"></tbody></table>
    </div>
  </section>

  <section id="s-decisiones">
    <div class="sec-head-row">
      <div class="sec-head"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg><h2>Decisiones recientes</h2></div>
      <div class="toolbar">
        <div class="range-toggle" id="decVista">
          <button data-dv="accion" class="active">Con acción</button>
          <button data-dv="limit">LIMIT</button>
          <button data-dv="block">BLOCK</button>
          <button data-dv="todas">Todas</button>
        </div>
        <input type="text" id="ipFilter" placeholder="Filtrar por IP..." class="ip-filter">
        <button id="exportCsv" class="export-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><polyline points="7,10 12,15 17,10"/><path d="M4 18v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          Exportar CSV
        </button>
      </div>
    </div>
    <div class="spark-wrap dec-chart">
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
        <thead><tr><th>Hora</th><th>IP</th><th>Acción</th><th>Motivo</th><th>Modelo <span class="th-sub">score frente al umbral</span></th><th class="r">Paquetes</th></tr></thead>
        <tbody id="decisions"></tbody>
      </table>
    </div>
  </section>
</div>

<style>
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
    const viejo = document.getElementById(id);
    if (viejo) viejo.remove();
    const m = motivoDeDecision(g.d);
    const el = document.createElement('div');
    el.className = 'toast ' + (g.acc === 'BLOCK' ? 'block' : 'limit');
    el.id = id;
    el.innerHTML = '<div class="t-cab"><span class="badge acc-' + g.acc.toLowerCase() + '">' + g.acc + '</span>'
      + '<span class="t-ip">' + varEsc(g.ip) + '</span>'
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
    setTimeout(() => el.remove(), g.acc === 'BLOCK' ? 45000 : 15000);
  }
  while (cont.children.length > 4) cont.lastElementChild.remove();
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
  return new Date(t * 1000).toLocaleTimeString('es-PE', { hour12: false });
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
    tile('Anomalías del modelo (1h)', alertas,
         cal ? 'no equivalen a ataques confirmados' : 'modelo sin calibrar: ruido',
         !cal ? 'warn' : (alertas > 0 ? 'bad' : 'ok'));
}

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
  const w = Math.max(320, svg.clientWidth || 900), h = 190;
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
  { sel: '#kpis', t: 'Las cifras clave', d: 'Cuatro números de un vistazo: entidades vigiladas, ventanas analizadas por hora, cuántos scores rozan el umbral y las alertas reales de la última hora.' },
  { sel: '#s-topologia', t: 'El recorrido del paquete', d: 'De la red al veredicto: captura → variables por capa → modelo y heurísticos → decisión → respuesta en el host. Pulsa cualquier componente para ver qué hace.' },
  { sel: '#topoVista', t: 'Siete vistas', d: 'De la red a la validación: cada botón es un diagrama del mismo sistema.' },
  { sel: '#topoArchivosBtn', t: 'Código auditable', d: 'En modo desarrollador, pulsa Ver archivos, elige un componente y un archivo; en su ficha pulsa ◎ Ver contenido. El visor es de solo lectura y solo muestra rutas permitidas.' },
  { sel: '#s-modelo', t: 'El detector activo y su umbral', d: 'El detector desplegado aprende la normalidad de esta red; el umbral se fijó con validación. Aquí ves el modelo activo y sus métricas, no una etiqueta fija de OCSVM.' },
  { sel: '#pruebasPrevias', t: 'Pruebas previas', d: 'Siete modelos se compararon en el estudio; la ablación sobre nueve episodios separa modelo solo (6), heurísticos solos (7) y ambos combinados (9). No confundas el 9/9 del sistema con el modelo solo.' },
  { sel: '#s-scores', t: 'Distribución de scores', d: 'No solo si alertó o no, sino cuánto margen hubo respecto al umbral. Rojo = ALERT, verde = PERMIT.' },
  { sel: '#s-decisiones', t: 'Las decisiones', d: 'Cada ventana con su decisión, su score frente al umbral (la mini-barra) y el motivo. Filtrable por IP y exportable.' },
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
    + ficha('Dataset acumulado', filas == null ? '—' : filas.toLocaleString('es'), 'filas',
            p.dataset ? 'escrito ' + pulsoHace(edad(p.dataset.mtime))
              + (filas != null && filas > pulsoFilas0 ? ' · +' + (filas - pulsoFilas0).toLocaleString('es') + ' en esta sesión' : '')
              : 'sin dato',
            p.dataset ? edad(p.dataset.mtime) : null, 1200, '')
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
    stamp.textContent = 'Actualizado ' + new Date().toLocaleTimeString();

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
        card('Detector', escSimple(DETECTOR_LABEL[m.detector_name] || m.detector_name || 'no disponible'), 'txt'),
        card('Umbral', coma(m.threshold, 4), 'accent'),
      ];
      if (ev) {
        // Cifras medidas del detector en uso (docs/evaluacion/modelo-vigente.json).
        const dk = ev.deteccion_kali;
        tarjetas.push(card('FPR en el oro', coma(ev.fpr_oro.valor * 100, 2) + ' %<small>' + ev.fpr_oro.ventanas.toLocaleString('es') + ' ventanas</small>'));
        tarjetas.push(card('Detección del modelo solo', coma(100 * dk.detectadas / dk.total, 1) + ' %<small>' + dk.detectadas + ' de ' + dk.total + ' ventanas de ataque</small>', 'accent'));
      } else {
        tarjetas.push(card('FPR benigno', pct(m.test_fpr, 2)));
        tarjetas.push(card('Detección global', pct(m.detection_rate, 1), 'accent'));
        tarjetas.push(card('Detección Kali-real', pct(m.kali_real_detection_rate, 1), 'accent'));
      }
      modelEl.innerHTML = tarjetas.join('');
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

    renderVigentes(status.vigentes || [], status.blocked || []);

    const c = status.counters;
    ultimosCounters = c;
    counters.innerHTML = [
      card('Ventanas analizadas', (c.total || 0).toLocaleString('es')),
      card('BLOCK', c.block || 0, c.block > 0 ? 'bad' : ''),
      card('LIMIT', c.limit || 0, c.limit > 0 ? 'amber' : ''),
      card('IPs con acción', c.ips_con_accion || 0, c.ips_con_accion > 0 ? 'amber' : ''),
      card('Anomalías del modelo', c.alert_model || 0, c.alert_model > 0 ? 'bad' : ''),
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

    lastDecisions = await (await fetch('/api/decisions?limit=600')).json();
    markSeenAndCountNewAlerts(lastDecisions);
    renderDecisionsTable();
    renderAlertas();
    renderTopIps();
  } catch (e) {
    stamp.textContent = 'Error al actualizar: ' + e;
  }
}

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
  const sev = { BLOCK: 2, LIMIT: 1, PERMIT: 0 };
  let acc = 'PERMIT';
  if (d.decision === 'ALERT') {
    acc = String(d.detector_name || '').endsWith('_heuristic') ? 'BLOCK' : 'LIMIT';
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
function renderAlertas() {
  const lista = document.getElementById('alertasLista');
  const resumen = document.getElementById('alertasResumen');
  if (!lista || !resumen) return;
  const coma3 = v => (v == null ? '—' : Number(v).toFixed(3).split('.').join(','));
  const todas = (lastDecisions || []).filter(d => accionDeDecision(d) !== 'PERMIT');
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
  const listadas = Math.min(h.length, totalHora);
  resumen.innerHTML = `<div class="al-num ${totalHora ? 'hay' : ''}">${totalHora}</div>`
    + `<div class="al-num-t">alerta(s) en la última hora`
    + `<small>${nReg} por reglas · ${nMod} anomalía(s) del modelo`
    + (totalHora > listadas ? ` · se listan las ${listadas} más recientes` : '')
    + `</small></div>`;
  let rows = todas;
  if (alertasFiltro === 'modelo') rows = rows.filter(d => alertaTipos(d).modelo);
  if (alertasFiltro === 'regla') rows = rows.filter(d => alertaTipos(d).regla);
  rows = rows.slice(0, 80);
  if (!rows.length) {
    lista.innerHTML = '<p class="dim" style="padding:0.7rem 0">Sin alertas en el periodo cargado — el sistema está en PERMIT.</p>';
    return;
  }
  lista.innerHTML = rows.map(d => {
    const acc = accionDeDecision(d);
    const t = alertaTipos(d);
    const tags = [];
    if (t.regla) tags.push('<span class="al-tag regla">Regla: ' + varEsc(t.regla) + '</span>');
    if (t.modelo) tags.push('<span class="al-tag modelo">Anomalía del modelo</span>');
    const motivo = (d.heuristico && d.heuristico.motivo) ? varEsc(d.heuristico.motivo)
      : (d.score != null ? 'score ' + coma3(d.score) + ' por debajo del umbral ' + coma3(d.threshold) : '');
    return `<div class="al-card al-${acc.toLowerCase()}">`
      + `<div class="al-sev"><span class="badge acc-${acc.toLowerCase()}">${acc}</span></div>`
      + `<div class="al-main"><div class="al-top"><span class="al-ip">${varEsc(d.entity_ip)}</span>`
      + `<span class="al-hace">${haceTexto(d.logged_at)}</span></div>`
      + `<div class="al-tags">${tags.join(' ')}</div>`
      + `<div class="al-motivo">${motivo}</div></div>`
      + `<div class="al-mini">${miniBarraScore(d.score)}</div></div>`;
  }).join('');
}
on('alertasFiltro', 'click', (ev) => {
  const b = ev.target.closest('button[data-af]');
  if (!b) return;
  alertasFiltro = b.dataset.af;
  document.querySelectorAll('#alertasFiltro button').forEach(x => x.classList.toggle('active', x === b));
  renderAlertas();
});

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

// Acciones vigentes: del feed publicado (caducidad exacta) o reconstruidas del
// registro con la misma escalera. Si el host tuviera nftables local, tambien.
function renderVigentes(vigentes, locales) {
  const filas = vigentes.map(v => {
    const total = v.accion === 'BLOCK' ? ({ 1: 300, 2: 1800, 3: 3600 }[v.nivel] || 300) + 60 : 360;
    const pct = Math.max(2, Math.min(100, Math.round(100 * v.expira_s / total)));
    const color = v.accion === 'BLOCK' ? 'var(--danger)' : 'var(--amber)';
    const reinc = v.accion === 'BLOCK'
      ? 'nivel ' + (v.nivel || 1) + (v.revisar_humano ? ' · revisar' : '')
      : '—';
    return `<tr class="row-${v.accion.toLowerCase()}"><td class="ip">${varEsc(v.ip)}</td>`
      + `<td><span class="badge acc-${v.accion.toLowerCase()}">${v.accion}</span></td>`
      + `<td class="why">${varEsc(v.origen || '')}${v.motivo ? ' · ' + varEsc(v.motivo) : ''}</td>`
      + `<td class="num">${v.desde ? fmtTime(v.desde) : '—'}${v.ofensas ? '<span class="hace">' + v.ofensas + ' ventanas</span>' : ''}</td>`
      + `<td class="num">${duracionTexto(v.expira_s)}<div class="vig-barra"><i style="width:${pct}%;background:${color}"></i></div></td>`
      + `<td>${reinc}<div class="vig-fuente">${v.fuente === 'feed' ? 'feed publicado' : 'según registro'}</div></td></tr>`;
  });
  for (const b of locales) {
    filas.push(`<tr class="row-block"><td class="ip">${varEsc(b.ip)}</td><td><span class="badge acc-block">BLOCK</span></td>`
      + `<td class="why">nftables local</td><td class="num">—</td>`
      + `<td class="num">${b.expires_seconds != null ? duracionTexto(b.expires_seconds) : '?'}</td><td>—</td></tr>`);
  }
  document.getElementById('blocked').innerHTML = filas.length ? filas.join('')
    : '<tr class="empty-row"><td colspan="6">Ninguna IP limitada ni bloqueada ahora mismo.</td></tr>';
}

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
    return `<tr class="row-${e.accion.toLowerCase()}" data-ip="${varEsc(e.ip)}" style="cursor:pointer" title="Pulsa para filtrar las decisiones de esta IP">`
      + `<td class="num">${fmtTime(e.inicio)}<span class="hace">${haceTexto(e.inicio)}</span></td>`
      + `<td class="ip">${varEsc(e.ip)}</td><td><span class="badge acc-${e.accion.toLowerCase()}">${e.accion}</span></td>`
      + `<td class="why">${e.origen && e.origen !== 'modelo' ? '<span class="badge heur">' + varEsc(e.origen) + '</span> ' : ''}${varEsc(e.motivo || '')}</td>`
      + `<td class="num">${dur > 0 ? duracionTexto(dur) : 'una ventana'}</td><td class="num r">${e.ventanas}</td>`
      + `<td>${e.vigente ? '<span class="badge acc-' + e.accion.toLowerCase() + '">en vigor</span>' : '<span class="hace" style="display:inline">caducada</span>'}</td></tr>`;
  }).join('') : '<tr class="empty-row"><td colspan="7">Ninguna IP limitada ni bloqueada en este tramo.</td></tr>';
}
async function cargarHistorial() {
  if (!document.getElementById('histChart')) return;
  try { renderHistorial(await (await fetch('/api/acciones')).json()); } catch (e) { /* se reintenta en el siguiente ciclo */ }
}
cargarHistorial();
setInterval(cargarHistorial, 30000);

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
        est = serv[c.servicio] ? 'activo' : 'inactivo';
      }
      const meta = c.cadencia || c.detalle || c.fichero || c.unidad || '';
      return `<div class="desp-comp ${cls}"><span class="c-dot"></span><span class="c-n">${varEsc(c.nombre)}`
        + (est ? ` <span class="hace" style="display:inline">${est}</span>` : '') + `</span>`
        + (meta ? `<span class="c-u" title="${varEsc(c.unidad || '')}">${varEsc(meta)}</span>` : '') + `</div>`;
    }).join('');
    return `<div class="desp-card ${n.rol}"><div class="desp-rol">${ROL[n.rol] || n.rol}</div>`
      + `<div class="desp-h">${varEsc(n.titulo)}</div>`
      + `<div class="desp-host">${varEsc(n.host)} · ${varEsc(n.ip)}</div>`
      + `<div class="desp-meta">VLAN ${varEsc(n.vlan || '—')} · ${varEsc(n.donde || '')}</div>`
      + comps + (n.nota ? `<div class="desp-nota">${varEsc(n.nota)}</div>` : '') + `</div>`;
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
    : '<tr class="empty-row"><td colspan="3">Ninguna IP con acciones en la última hora.</td></tr>';
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

function filasFiltradas() {
  const query = document.getElementById('ipFilter').value.trim();
  let rows = lastDecisions;
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
function renderDecChart() {
  const svg = document.getElementById('decChart');
  if (!svg) return;
  const query = document.getElementById('ipFilter').value.trim();
  const datos = (query ? lastDecisions.filter(d => d.entity_ip.includes(query)) : lastDecisions)
    .filter(d => d.logged_at);
  const W = Math.max(320, svg.clientWidth || 900), H = 170;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const X0 = 64, X1 = W - 10, Y0 = 10, Y1 = H - 46, YS = H - 30;
  decPuntos = [];
  if (!datos.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">Sin decisiones que graficar.</text>`;
    return;
  }
  const ahora = Date.now() / 1000;
  const t0 = Math.min(...datos.map(d => d.logged_at)), t1 = Math.max(ahora, t0 + 60);
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
    s += `<text x="${x.toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 ? 'start' : (i === 4 ? 'end' : 'middle')}">${i === 4 ? 'ahora' : fmtTime(t)}</text>`;
  }
  const estilo = { PERMIT: ['var(--accent)', 2, 0.4], LIMIT: ['var(--amber)', 3.8, 0.95], BLOCK: ['var(--danger)', 4.4, 1] };
  // Los PERMIT primero: las acciones se dibujan encima y no quedan tapadas.
  ['PERMIT', 'LIMIT', 'BLOCK'].forEach(tipo => {
    datos.forEach(d => {
      if (accionDeDecision(d) !== tipo) return;
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
function decDetalleHTML(d, accion) {
  const h = d.heuristico;
  const margen = d.score != null && d.threshold != null ? d.score - d.threshold : null;
  const caduca = accion === 'LIMIT' ? '300 s' : (accion === 'BLOCK' ? '300, 1800 o 3600 s según reincidencia' : 'no aplica');
  const fila = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
  return '<dl>'
    + fila('Ventana (UTC)', varEsc(String(d.window_end_utc || '—')))
    + fila('Detector', varEsc(String(d.detector_name || '—')))
    + fila('Score y umbral', d.score != null ? d.score.toFixed(4) + ' frente a ' + (d.threshold != null ? d.threshold.toFixed(4) : '—') : 'sin puntuar: ventana sin paquetes')
    + fila('Margen al umbral', margen == null ? '—' : (margen >= 0 ? '+' : '') + margen.toFixed(4) + (margen < 0 ? ' · anomalía' : ' · normal'))
    + fila('Regla', h && h.heuristico ? varEsc(h.heuristico) + ' → ' + varEsc(h.accion || '') : 'ninguna')
    + fila('Qué midió la regla', h && h.motivo ? varEsc(h.motivo) : '—')
    + fila('Paquetes en 10 s', d.packet_count_10s ?? '—')
    + fila('Historia cubierta', d.history_coverage_s != null ? d.history_coverage_s + ' s' : '—')
    + fila('Acción y caducidad', accion + ' · ' + caduca)
    + '</dl>';
}
on('decisions', 'click', (ev) => {
  const tr = ev.target.closest('tr.dec-fila');
  if (!tr) return;
  const k = tr.dataset.key;
  if (decAbiertas.has(k)) decAbiertas.delete(k); else decAbiertas.add(k);
  renderDecisionsTable();
});

function renderDecisionsTable() {
  const { rows, query } = filasFiltradas();
  const nAcc = lastDecisions.filter(d => accionDeDecision(d) !== 'PERMIT').length;
  const quees = { accion: 'con acción', limit: 'con LIMIT', block: 'con BLOCK' }[decVista];
  document.getElementById('filterHint').textContent =
    (quees ? (decVista === 'accion' ? nAcc : rows.length) + ' ' + quees + ' de ' + lastDecisions.length + ' decisiones recientes' : lastDecisions.length + ' decisiones recientes')
    + (query ? ' · ' + rows.length + ' coinciden con «' + query + '»' : '');
  renderDecChart();
  document.getElementById('decisions').innerHTML = rows.length ? rows.map(d => {
    const accion = accionDeDecision(d);
    const accBadge = `<span class="badge acc-${accion.toLowerCase()}">${accion}</span>`;
    const isAlert = d.decision === 'ALERT';
    const modelo = d.score != null
      ? `<span class="modelo-celda"><span class="${isAlert ? 'm-alert' : 'm-permit'}">${isAlert ? 'ALERT' : 'normal'}</span>`
        + `<span>${d.score.toFixed(3)}</span>${miniBarraScore(d.score)}</span>`
      : '<span class="modelo-celda"><span class="m-permit">sin puntuar</span></span>';
    const m = motivoDeDecision(d);
    const motivoTxt = m.regla && m.regla !== 'modelo'
      ? `<span class="badge heur" title="regla determinista, sin firma">${varEsc(m.regla)}</span> ${varEsc(m.texto)}`
      : (m.regla === 'modelo' ? varEsc(m.texto) : varEsc(DETECTOR_LABEL[d.detector_name] || d.detector_name || ''));
    const key = d.entity_ip + '|' + d.window_end_utc;
    const cls = 'dec-fila ' + (accion !== 'PERMIT' ? 'row-' + accion.toLowerCase() : '') + (nuevasClaves.has(key) ? ' row-nueva' : '');
    return `<tr class="${cls}" data-key="${varEsc(key)}" title="Pulsa para ver el detalle"><td class="num">${fmtTime(d.logged_at)}<span class="hace">${haceTexto(d.logged_at)}</span></td>`
      + `<td class="ip">${varEsc(d.entity_ip)}</td><td>${accBadge}</td><td class="why">${motivoTxt}</td>`
      + `<td>${modelo}</td><td class="num r">${d.packet_count_10s ?? '—'}</td></tr>`
      + (decAbiertas.has(key) ? `<tr class="dec-det"><td colspan="6">${decDetalleHTML(d, accion)}</td></tr>` : '');
  }).join('') : `<tr class="empty-row"><td colspan="6">${query ? 'Ninguna decisión coincide con el filtro.'
      : (decVista === 'accion' ? 'Ninguna acción reciente: todo el tráfico se permitió.' : 'Sin decisiones recientes.')}</td></tr>`;
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
  // Cortafuegos: muro de ladrillos. Conmutador: caja con flujo bidireccional.
  firewall: '<rect x="2" y="3.3" width="14" height="11.4" rx="1"/><path d="M2 7.1h14M2 10.9h14M6.6 3.3v3.8M11.4 3.3v3.8M4.3 7.1v3.8M9 7.1v3.8M13.7 7.1v3.8M6.6 10.9v3.8M11.4 10.9v3.8"/>',
  switch:   '<rect x="1.6" y="5.4" width="14.8" height="7.2" rx="1.3"/><path d="M4 9h10"/><path d="M6.4 6.9 4 9l2.4 2.1M11.6 6.9 14 9l-2.4 2.1"/>',
  carpeta:  '<path d="M2 4.6h4.4l1.5 2H16v7.8H2Z"/><path d="M2 8.6h14"/>',
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
      { id: 'gateway',  x: 24, y: 280, w: 176, h: 48, icono: 'firewall', titulo: 'Firewall', host: true, ip: '10.10.20.1',      desc: 'enruta entre VLAN' },
      { id: 'red',       x: 286, y: 70,  w: 176, h: 58, icono: 'red',    titulo: 'Red de la entidad',  tag: 'VLAN 10-100' },
      { id: 'span',      x: 286, y: 158, w: 176, h: 58, icono: 'switch', titulo: 'Espejo SPAN',        tag: 'CORE-STACK' },
      { id: 'nic',       x: 286, y: 246, w: 176, h: 58, icono: 'nic',    titulo: 'Interfaz en escucha', tag: 'ens37 · SIN IP' },
      { id: 'captura',   x: 540, y: 110, w: 176, h: 58, icono: 'captura', titulo: 'tcpdump',           tag: 'SERVICIO' },
      { id: 'pcap',      x: 540, y: 192, w: 176, h: 46, icono: 'fichero', titulo: 'anillo live-*.pcap', tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'suricata',  x: 540, y: 274, w: 176, h: 58, icono: 'lupa',   titulo: 'Suricata',           tag: 'SERVICIO' },
      { id: 'eve',       x: 540, y: 356, w: 176, h: 46, icono: 'fichero', titulo: 'eve.json',          tag: 'ARTEFACTO', clase: 'artefacto' },
      { id: 'motor',     x: 806, y: 110, w: 176, h: 58, icono: 'cpu',    titulo: 'Parser de paquetes', tag: 'TRAMA → FLUJO · L2·L3·L4' },
      { id: 'variables', x: 806, y: 220, w: 176, h: 58, icono: 'tabla',  titulo: 'Variables / 10 s',   tag: 'POR IP Y VENTANA' },
      { id: 'parser_eve', x: 806, y: 330, w: 176, h: 58, icono: 'reglas', titulo: 'Parser de eventos', tag: 'JSON → L7 · HTTP·DNS·TLS', val: 'http · dns · tls' },
      { id: 'descartes', x: 806, y: 420, w: 176, h: 48, icono: 'tijera', titulo: 'Fuera del cálculo',  tag: 'SUMIDERO', clase: 'sumidero' },
      { id: 'reentrenamiento', x: 1060, y: 70, w: 176, h: 58, icono: 'ciclo', titulo: 'Aprendizaje', tag: 'SUPERVISADO · CADA NOCHE' },
      { id: 'modelo',    x: 1060, y: 158, w: 176, h: 58, icono: 'modelo', titulo: 'Modelo recalibrado', tag: 'IF · CALIBRADO' },
      { id: 'heuristicos', x: 1060, y: 276, w: 176, h: 58, icono: 'reglas', titulo: 'Heurísticos',     tag: 'DETERMINISTAS' },
      { id: 'control',   x: 1336, y: 158, w: 176, h: 58, icono: 'decision', titulo: 'Decisión', forma: 'rombo', rsub: 'PERMIT / acción' },
      { id: 'feed',      x: 1336, y: 246, w: 176, h: 58, icono: 'fichero', titulo: 'Feed firmado',     tag: 'ed25519 · CADA 60 s' },
      { id: 'relay',     x: 1336, y: 334, w: 176, h: 52, icono: 'espejo', titulo: 'Relay (bastión)',   val: 'réplica · cada 60 s' },
      { id: 'agente',    x: 1336, y: 416, w: 176, h: 58, icono: 'escudo', titulo: 'Agente en host',   tag: 'PULL 60 s · nftables' },
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
      { id: 'm_modelo', x: 492,  y: 78, w: 196, h: 62, icono: 'modelo',   titulo: 'IF + heurísticos',      tag: 'θ = −0,568892', val: 'hecho' },
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
      { x: 20, y: 396, w: 1520, h: 150, txt: 'Aprendizaje supervisado: cada noche, lo promueve una persona', n: 3 },
    ],
    nodos: [
      { id: 'c_datos',   x: 40,   y: 72,  w: 200, h: 64, icono: 'disco',    titulo: 'Datos de la red',      tag: 'SPAN → PCAP + eve.json', val: '335 202 ventanas' },
      { id: 'c_limpia',  x: 296,  y: 72,  w: 200, h: 64, icono: 'tijera',   titulo: 'Limpieza y alcance',   tag: 'espejo · control · excluidas', val: 'sin imputación' },
      { id: 'c_part',    x: 552,  y: 72,  w: 200, h: 64, icono: 'tabla',    titulo: 'Partición',            tag: 'train / validación / test', val: '204 148 / 65 633 / 65 421' },
      { id: 'c_cand',    x: 808,  y: 72,  w: 200, h: 64, icono: 'modelo',   titulo: 'Candidatos',           tag: 'IF · LOF · OCSVM · EE', val: '7 (laboratorio) · IF aquí' },
      { id: 'c_metr',    x: 1064, y: 72,  w: 200, h: 64, icono: 'lupa',     titulo: 'Comparar métricas',    tag: 'FPR · recall · F1 · AUC', val: 'criterio fijado antes' },
      { id: 'c_sel',     x: 1320, y: 72,  w: 200, h: 64, icono: 'decision', titulo: 'Selección', forma: 'rombo', rsub: 'IF → esta red' },
      { id: 'c_cong',    x: 1320, y: 252, w: 200, h: 64, icono: 'cpu',      titulo: 'Congelar modelo', tag: 'α=0,05 · −0,568892', val: 'sha256 d27f6871…' },
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
      { id: 'atacante',  x: 24,  y: 60,  w: 176, h: 48, icono: 'lupa',   titulo: 'Atacante (Kali)',  host: true, ip: '10.10.20.30',     desc: '' },
      { id: 'clientes',  x: 24,  y: 118, w: 176, h: 48, icono: 'red',    titulo: 'Clientes',         host: true, ip: '10.10.20.21-.26', desc: '' },
      { id: 'servidor',  x: 24,  y: 216, w: 176, h: 48, icono: 'disco',  titulo: 'srv-dmz · objetivo', host: true, ip: '10.10.30.10',   desc: '' },
      { id: 'r_bastion', x: 24,  y: 316, w: 176, h: 48, icono: 'ojo',    titulo: 'VM-GESTION',       host: true, ip: '10.10.10.30',     desc: '' },
      { id: 'r_dns',     x: 24,  y: 374, w: 176, h: 48, icono: 'red',    titulo: 'DNS / AD',         host: true, ip: '10.10.10.20',     desc: '' },
      { id: 'gateway',   x: 330, y: 70,  w: 196, h: 48, icono: 'firewall', titulo: 'Firewall A/B',   host: true, ip: 'enruta entre VLAN', desc: '' },
      { id: 'span',      x: 330, y: 216, w: 196, h: 58, icono: 'switch', titulo: 'CORE-STACK',       tag: 'NO ENRUTA · ESPEJA' },
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
  // combina por IP cada 60 s sobre los ultimos 120 s y fija la caducidad.
  // Fuentes: motor_decision.py, heuristicos.py, publicar_feed.py, escalada.py.
  decision: {
    w: 1560, h: 520,
    packet: 'M230,149 L330,99 L630,99 L1060,140 L1160,174 L140,330 L240,359 L820,359 L920,388 L1140,440',
    grupos: [
      { x: 12, y: 32,  w: 1536, h: 236, txt: 'Motor · decide cada ventana', n: 1 },
      { x: 12, y: 296, w: 1536, h: 112, txt: 'Publicador · cada 60 s, últimos 120 s, por IP', n: 2 },
    ],
    nodos: [
      { id: 'variables',   x: 40,   y: 120, w: 190, h: 58, icono: 'tabla',  titulo: 'Variables / 10 s', tag: 'POR IP Y VENTANA' },
      { id: 'descartes',   x: 40,   y: 204, w: 190, h: 48, icono: 'tijera', titulo: 'IP excluida',      tag: 'SE CUENTA · NO SE PUNTÚA', clase: 'sumidero' },
      { id: 'modelo',      x: 330,  y: 70,  w: 200, h: 58, icono: 'modelo', titulo: 'Isolation Forest', tag: 'SOLO CON PAQUETES' },
      { id: 'heuristicos', x: 330,  y: 170, w: 200, h: 58, icono: 'reglas', titulo: 'Heurísticos',      tag: 'TAMBIÉN SIN PAQUETES (L7)' },
      { id: 'd_alert',     x: 630,  y: 70,  w: 200, h: 58, icono: 'decision', titulo: 'ALERT del modelo', tag: 's(x) < −0,568892', val: 'pasa a LIMIT' },
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
      { d: 'M135,178 L135,204',                      desde: 'variables',   hasta: 'descartes',  tipo: 'descarte' },
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
      { id: 'feed',       x: 320,  y: 110, w: 176, h: 58, icono: 'fichero', titulo: 'Feed firmado',  tag: 'DECISIÓN 17–18 s (N=2)' },
      { id: 'relay',      x: 592,  y: 110, w: 176, h: 58, icono: 'espejo',  titulo: 'Relay',         tag: 'RÉPLICA', val: 'cada 60 s' },
      { id: 'agente',     x: 860,  y: 110, w: 176, h: 58, icono: 'escudo',  titulo: 'Agente',        tag: 'VERIFICA LA FIRMA' },
      { id: 'p_nft',      x: 1110, y: 110, w: 176, h: 58, icono: 'escudo',  titulo: 'nftables',      tag: 'RESPUESTA 51–141 s', val: 'LIMIT · BLOCK', clase: 'acc-block' },
      { id: 'p_noaplica', x: 860,  y: 230, w: 176, h: 58, icono: 'tijera',  titulo: 'Firma inválida', tag: 'LO VIGENTE CADUCA', val: 'no aplica nada', clase: 'sumidero' },
      { id: 'p_caduca',   x: 1110, y: 230, w: 176, h: 58, icono: 'ciclo',   titulo: 'Caduca sola',   tag: 'TIMEOUT DEL SET', val: '300 · 1800 · 3600 s' },
      { id: 'p_manual',   x: 1356, y: 110, w: 176, h: 58, icono: 'ojo',     titulo: 'Retirada manual', tag: 'UNA PERSONA', val: 'nft delete element' },
    ],
    aristas: [
      { d: 'M216,139 L320,139',   desde: 'control', hasta: 'feed',       etiqueta: 'cada 60 s', ex: 268, ey: 130 },
      { d: 'M496,139 L592,139',   desde: 'feed',    hasta: 'relay',      tipo: 'fijo', etiqueta: 'cada 60 s', ex: 544, ey: 130 },
      { d: 'M768,139 L860,139',   desde: 'relay',   hasta: 'agente',     tipo: 'fijo', etiqueta: 'pull · 60 s', ex: 814, ey: 130 },
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

let topoVista = 'metodologica';
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
    nota: 'La red enruta a través del cortafuegos, así que todo el tráfico entre VLAN pasa por el troncal espejado.',
  },
  span: {
    que: 'La sesión de espejo del conmutador copia el troncal del cortafuegos hacia el puerto del sensor.',
    nota: 'Desde el sensor no se puede leer el estado de la sesión: se infiere de que lleguen paquetes. Si deja de llegar tráfico, el problema puede estar aquí y el panel no lo distingue de una red en silencio.',
    cmd: 'monitor session 1 source interface Gi1/0/23 , Gi2/0/23 both\\nmonitor session 1 destination interface Gi2/0/19 encapsulation replicate\\n! Gi1/0/23 y Gi2/0/23: troncales del Firewall A/B\\n! Gi2/0/19: hacia el hipervisor del sensor (172.17.25.2)\\n! encapsulation replicate: conserva la etiqueta 802.1Q -> el sensor ve la VLAN',
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
    que: 'Una VM con seis alias .21-.26, cada uno un perfil de tráfico legítimo contra el servidor. Así la línea base tiene variedad realista, no un único patrón.',
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
    nota: 'Seis IP sobre una sola MAC, a propósito: el motor puntúa por IP, así que son seis entidades distintas para el modelo.',
  },
  servidor: {
    que: 'El host protegido (srv-dmz, 10.10.30.10, VLAN 30 DMZ): servidor HTTP/HTTPS objetivo del ensayo y donde se APLICA la respuesta. Escucha 80 y 443 (web) y 22 (SSH). Corre el agente que trae el feed firmado y sincroniza nftables en su propio kernel.',
    flujoTit: 'Qué corre en el host y cómo bloquea',
    flujo: [
      {paso: 'Servicio web', fichero: 'HTTP 80 · HTTPS 443', garantia: 'objetivo del tráfico legítimo y de los ataques'},
      {paso: 'Agente de enforcement', fichero: 'ppi-enforce-agent.timer (pull 60 s)', garantia: 'trae el feed del relay, verifica la firma ed25519 y aplica nftables'},
      {paso: 'BLOCK = drop', fichero: 'set cyberflow_bloqueados (con timeout)', garantia: 'ip saddr @bloqueados → drop; caduca solo'},
      {paso: 'LIMIT = rate-limit', fichero: 'set cyberflow_limitados (con timeout)', garantia: 'limit rate over 100/s burst 5 → drop el exceso'},
    ],
    cmd: 'table inet cyberflow {\\n  set cyberflow_bloqueados { type ipv4_addr; flags timeout }\\n  set cyberflow_limitados  { type ipv4_addr; flags timeout }\\n  chain entrada {\\n    type filter hook input priority filter - 10; policy accept;\\n    ip saddr @cyberflow_bloqueados drop\\n    ip saddr @cyberflow_limitados limit rate over 100/second burst 5 packets drop\\n  }\\n}',
    nota: 'Tabla AISLADA (policy accept): solo cae lo que trae el feed; nunca gateways ni DNS. El sudoers del agente solo permite «nft» sin contraseña, nada más. Fail-safe: si la firma no verifica, no toca la tabla. Aparece con pocos paquetes PROPIOS porque el motor atribuye cada flujo a quien lo inicia, no al destino.',
  },
  gateway: {
    que: 'La segmentación del laboratorio: un cortafuegos pfSense en alta disponibilidad (par A/B con VIP CARP) que enruta entre VLAN y es la puerta de enlace de cada una (VLAN 20 clientes/Kali · 30 DMZ · 60 sensor · 10 gestión). Todo el tráfico entre VLAN cruza el troncal, que es el que se espeja (SPAN) hacia el sensor.',
    flujoTit: 'Reglas implementadas (lo que el ensayo comprobó)',
    flujo: [
      {paso: 'Atacante → DMZ: solo 443', fichero: 'VLAN 20 → VLAN 30', garantia: 'HTTPS permitido; puerto 80 FILTERED; ICMP bloqueado'},
      {paso: 'Clientes → DMZ', fichero: 'VLAN 20 → VLAN 30', garantia: 'tráfico legítimo a 80/443 para la línea base'},
      {paso: 'Sensor sin salida a Internet', fichero: 'VLAN 60 · egress denegado', garantia: 'propiedad de seguridad: nada de bots externos'},
      {paso: 'Troncal espejado', fichero: 'SPAN del trunk → sensor', garantia: 'el sensor ve una COPIA, no está en línea: observa, no corta'},
    ],
    nota: 'El escaneo de puertos se valida de extremo a extremo porque opera a nivel TCP/flujo, que el sensor observa por el espejo SPAN. En la validación del 14-oct el puerto 80 estaba ABIERTO E2E (Kali→DMZ), así que los ataques HTTP en claro —flood (http_abuse→LIMIT) y fuerza bruta sobre el endpoint de laboratorio (brute_force→BLOCK)— también se validaron de extremo a extremo; sobre 443 Suricata solo ve TLS cifrado. El DNS de alta entropía (DGA) se detecta aunque vaya al resolutor de gestión, no a la DMZ. El cortafuegos es de SOLO LECTURA para CyberFlow: la respuesta la aplica el agente en el host, no aquí. En el ARP spoofing la IP de la puerta de enlace pasa a verse con dos MAC: esa es la anomalía de capa 2 que mueve unique_src_mac_30s.',
  },
  reentrenamiento: {
    que: 'El modelo envejece: la normalidad cambia con el tiempo. Cada noche el sistema sanea un lote, mide la deriva y, cuando toca, entrena y evalúa un candidato. Desplegarlo lo decide una persona: un modelo que se cambia solo podría aprender un ataque lento como normal.',
    flujoTit: 'Reentrenamiento supervisado (cyberflow_aprendizaje.py)',
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
    que: 'El plano de gestión del sensor, que sale por ens34: la sesión SSH del administrador, el panel HTTPS y el envío del feed al relay del bastión cada 60 s. Separado del plano de captura (ens37).',
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
    que: 'El modelo one-class RECALIBRADO en esta red (IsolationForest). Aprende la normalidad propia; el umbral se congela desde validación (score_samples < -0,568892).',
    codigo: {
      archivo: 'modelo congelado en artifacts/ · entrenamiento en scripts/modeling/',
      pseudo: [
        'score ← modelo.score_samples(features)',
        'si score < umbral (−0,568892): ALERT → LIMIT',
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
    que: 'Fusiona las dos señales en UNA decisión por entidad y ventana. El motor registra PERMIT o ALERT (score bajo el umbral, o heurístico); la ALERT se traduce en acción: LIMIT (degradar la tasa) para la anomalía del modelo y para abuso HTTP o DNS, BLOCK (cortar) para fuerza bruta o escaneo confirmados.',
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
        'cada 60 s:',
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
      archivo: 'scripts/enforce/agente_enforce.py   (corre en el host protegido)',
      pseudo: [
        'cada 60 s:',
        '  feed ← traer del relay (bastión)',
        '  si la firma ed25519 no verifica: no tocar nada (fail-safe)',
        '  sincronizar nftables: LIMIT=rate-limit, BLOCK=drop con timeout',
      ],
      editar: 'nano ~/enforce/agente_enforce.py && sudo systemctl restart ppi-enforce-agent.timer   (en srv-dmz)',
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
  relay: {
    que: 'El bastión copia el feed firmado del sensor a la red interna. Los hosts lo traen de aquí: nunca hablan con el sensor.',
    nota: 'Es uno de los tres temporizadores de 60 s (publicador, relay, agente) que dominan el tiempo de respuesta.',
  },
  // ---- Vista RED Y CAPTURA ----
  r_bastion: {
    que: 'La VM de gestión (10.10.10.30, VLAN 10). Es el BASTIÓN del laboratorio: el único punto de entrada por SSH a todas las máquinas (sensor, servidor, Kali, clientes); guarda las claves SSH de cada host, así que toda la administración pasa por aquí. Además, aquí corre el RELAY del feed de enforcement.',
    flujoTit: 'Qué es el «relay del feed»',
    flujo: [
      {paso: 'Qué es el feed', fichero: 'feed.json + feed.sig', garantia: 'la lista FIRMADA (ed25519) de acciones por IP —PERMIT/LIMIT/BLOCK con caducidad— que publica el sensor'},
      {paso: 'Qué hace el relay', fichero: 'ppi-relay-feed.timer · cada 60 s', garantia: 'relay-feed.sh TRAE (pull) el feed del sensor y lo EMPUJA (push) al host protegido'},
      {paso: 'Por qué hace falta', fichero: 'red segmentada por VLAN', garantia: 'el host de la DMZ no habla con el sensor directamente; el bastión alcanza a los dos y hace de puente'},
      {paso: 'Por qué es seguro', fichero: 'relay TONTO', garantia: 'solo copia bytes: la firma la pone el sensor y la verifica el host, así que el bastión no puede forjar ni alterar un bloqueo'},
    ],
    nota: 'Modelo «un feed / N agentes (pull)»: el sensor NO tiene credenciales de los hosts; publica una lista firmada y cada host la trae y la verifica. Por eso el bastión, aunque administre, no es un camino hacia el cortafuegos. Está en la lista «nunca bloquear» (como los gateways y el DNS) para que un falso positivo no corte la propia vía de gestión. La VM también expone el panel al exterior por Tailscale (vm-gestion.tail83bf9c.ts.net).',
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
    que: 'El entrenamiento del modelo y el aprendizaje supervisado nocturno (saneo, deriva, candidato, promoción). Corre en el Sensor.',
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
      { n: 'if_recalibrado_*.joblib', host: 'sensor', d: 'modelo congelado' },
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
      { n: 'ppi-enforce-agent (unidad)', host: 'servidor', d: 'temporizador del agente, cada 60 s' },
    ],
  },
  cf_mas: {
    que: 'Otras carpetas de scripts: dataset (construir el conjunto), evaluacion (comparar con Suricata), campaign (campañas de ataque), analysis, kali, f1/f6, articulo y entregables.',
  },
  // ---- Vista DECISION ----
  d_alert: {
    que: 'Una ventana con paquetes cuyo score queda por debajo del umbral. El modelo no bloquea: su alerta se traduce en LIMIT.',
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
    nota: 'Medido desde el inicio del ataque: entre 51 y 141 s. Lo dominan los tres temporizadores de 60 s, no el cómputo.',
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
    que: 'F3 · Detector híbrido. Dos señales sobre las mismas variables. (1) Un modelo NO supervisado —Isolation Forest, recalibrado en esta red, con el umbral congelado θ=−0,568892— marca lo que se desvía de lo normal aprendido. (2) Cuatro heurísticos deterministas cubren los patrones donde el modelo mide flojo (fuerza bruta, escaneo de puertos, abuso HTTP, DNS de alta entropía). La ablación lo justifica: solo el modelo detecta 6 de 9 familias, solo los heurísticos 7 de 9, y combinados 9 de 9.',
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
      {paso: 'Detección Kali', fichero: 'nota M', garantia: '54/84 = 64,3 % global; HTTP 35/43'},
    ],
    nota: 'El criterio se fija ANTES de mirar la prueba: umbral desde validación con objetivo de FPR 5 %. El 4,45 % es del modelo sobre tráfico normal, no del sistema completo con heurísticos.',
  },
  c_sel: {
    que: 'Por qué ganó: el OCSVM traído del laboratorio, con su umbral, marcaba como anómalo casi todo el tráfico normal de esta red —inservible aquí—. El IF recalibrado en ESTA red cumple el objetivo de falsos positivos en prueba (4,45 % sobre 65 421 ventanas normales) y detecta 54 de 84 ventanas de ataque (64,3 %). Se elige el que funciona en la red donde opera, no el que ganó en otra.',
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
    enlace: { href: '#s-aprendizaje', txt: 'Ver el estado en «Aprendizaje»' },
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
  const v = TOPO_VISTAS[topoVista];
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
  const aristas = v.aristas.map(e => {
    const label = e.etiqueta
      ? `<text class="topo-edge-label" x="${e.ex}" y="${e.ey}" text-anchor="middle">${e.etiqueta}</text>` : '';
    // Con tipo, el conector dice su naturaleza (copia, previsto, persona...) y
    // no depende del estado vivo. Un enlace fisico no lleva punta.
    if (e.tipo) {
      return `<path class="topo-edge ${e.tipo}" d="${e.d}"${e.tipo === 'enlace' ? '' : PUNTA}/>` + label;
    }
    const vivo = est[e.desde].estado !== 'bad' && est[e.hasta].estado !== 'bad'
                 && est[e.desde].estado !== '';
    return `<path class="topo-edge ${vivo ? 'live' : 'dim'}" d="${e.d}"${PUNTA}/>` + label;
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

  // La punta de flecha toma el color de su conector (context-stroke).
  const defs = '<defs><marker id="topoPunta" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse"><path d="M0,0.8 L9.5,5 L0,9.2 Z" fill="context-stroke" stroke="none"/></marker></defs>';
  svg.innerHTML = defs + grupos + aristas + packet + hosts + nodos;
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
  const fila = p => `<div class="perfil"><span class="perfil-ico"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${TOPO_ICON[p.icono] || ''}</svg></span>`
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
    explica: 'Cada 60 s combina las decisiones del motor por IP, aplica la escalera de reincidencia y publica el feed.',
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
    explica: 'El aprendizaje supervisado nocturno: sanea el lote, mide la deriva contra el oro, entrena un candidato y lo deja listo para que una persona lo promueva.',
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
      { k: 'archivo', t: 'publicar_feed.py lee el log cada 60 s', ir: 'publicar_feed.py' },
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
    titulo: 'Publicar el feed firmado · cada 60 s',
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
    titulo: 'Agente en el host protegido · cada 60 s',
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
  let clase = 'ok', texto = 'todo en marcha';
  if (caidos.length) { clase = 'bad'; texto = caidos.length + ' servicio(s) caído(s)'; }
  else if (!cal) { clase = 'warn'; texto = 'sin calibrar'; }
  else if (captDegradada) { clase = 'warn'; texto = 'captura degradada · ver Alcance'; }
  el.className = 'side-state ' + clase;
  document.getElementById('sideStateText').textContent = texto;

  const c = status.counters || {};
  const alertas = (c.alert_model || 0) + (c.alert_auth_heuristic || 0);
  const pill = document.getElementById('navAlertPill');
  pill.hidden = alertas === 0;
  pill.textContent = alertas;
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
  's-modelo':      ['s-scores', 's-aprendizaje', 's-comparacion'],
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
function mostrarSeccion(id, subir) {
  const sec = seccionesPag.get(id);
  if (!sec || sec.hidden) id = primeraVisible();
  seccionesPag.forEach((s, k) => s.classList.toggle('pag-activa', k === id));
  enlaces.forEach((a, k) => a.classList.toggle('active', k === id));
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

async function cargarComparacion() {
  const tb = document.getElementById('cmpTabla');
  if (!tb) return;
  try {
    const r = await (await fetch('/api/comparacion')).json();
    if (r.error) { tb.innerHTML = '<tr class="empty-row"><td colspan="5">' + varEsc(r.error) + '</td></tr>'; return; }
    const conds = ['suricata', 'modelo', 'heuristicos', 'combinado'];
    let html = r.por_familia.map(f => '<tr><td>' + varEsc(f.nombre) + (f.con_firma ? ' <span class="badge heur">con firma</span>' : '') + '</td>'
      + conds.map(c => cmpCelda(f[c])).join('') + '</tr>').join('');
    html += '<tr class="cmp-total"><td>Total sin firma</td>' + conds.map(c => cmpCelda(r.sin_firma[c])).join('') + '</tr>';
    const fp = r.falsos_positivos;
    const fpTxt = (x) => x.valor === 'no medido' ? '<td class="cmp-nm">no medido</td>'
      : '<td class="num">' + x.valor + (x.de ? ' / ' + x.de : '') + '</td>';
    html += '<tr><td>Falsos positivos <span class="hace">ventanas normales con acción</span></td>' + conds.map(c => fpTxt(fp[c])).join('') + '</tr>';
    tb.innerHTML = html;
    document.getElementById('cmpNotas').innerHTML = (r.notas || []).map(n => '<li>' + varEsc(n) + '</li>').join('');
  } catch (e) {
    tb.innerHTML = '<tr class="empty-row"><td colspan="5">No se pudo cargar la comparación.</td></tr>';
  }
}
cargarComparacion();

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
  if (!sec || sec.hidden || vivo.pausa || vivo.enCurso) return;
  vivo.enCurso = true;
  try {
    const qs = new URLSearchParams({todos: document.getElementById('vivoTodos').checked ? '1' : '0'});
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
  if (!sec || sec.hidden || vivo.pausa || vivo.error) return;
  try {
    const d = await (await fetch('/api/vivo?todos=1&limite=3000')).json();
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
    ['activo', p.activo ? 'sí' : 'no'], ['modo', p.modo],
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
const DEV_SECS = ['s-topologia', 's-variables', 's-vivo', 's-modelo', 's-comparacion', 's-alcance', 's-simulacion', 's-aprendizaje'];

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
  // Si la seccion que se veia quedo oculta al pasar a operativo, saltar a una
  // visible para no dejar el contenido en blanco.
  if (typeof mostrarSeccion === 'function') {
    const activa = [...seccionesPag.values()].find(s => s.classList.contains('pag-activa'));
    if (!activa || activa.hidden) mostrarSeccion(primeraVisible(), false);
    else pintarRelaciones(activa.id);   // refresca el pie segun el modo nuevo
  }
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
    acciones = [accion_de(d) for d in recent]
    return {
        "total": len(recent),
        "block": sum(1 for a in acciones if a and a[0] == "BLOCK"),
        "limit": sum(1 for a in acciones if a and a[0] == "LIMIT"),
        "ips_con_accion": len({d.get("entity_ip") for d, a in zip(recent, acciones) if a}),
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
        if n_accion > 0:
            msg = "Servicios activos · respuesta activa en la última hora"
        else:
            msg = "Servicios activos · %d alerta(s) en la última hora" % (n_alert_modelo + n_alert_fb)
        return {"nivel": "warn", "msg": msg,
                "sub": "El sistema está respondiendo: " + " · ".join(partes)
                       + ". Revisar Decisiones y Bloqueos abajo."}
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
CADENCIA_FEED_S = 60                              # el publicador corre cada minuto
REGLA_LEGACY = {"auth_failure_heuristic": "fallos de autenticación repetidos"}
NUNCA_BLOQUEAR = {"10.10.10.30", "10.10.60.11", "10.10.30.1", "10.10.40.1",
                  "10.10.60.1", "10.10.20.1", "10.10.10.20"}   # = publicar_feed.py


def accion_de(d: dict) -> tuple[str, str, str] | None:
    """(accion, motivo, origen) de una decision, o None si no pide accion."""
    candidatos = []
    if d.get("decision") == "ALERT":
        det = str(d.get("detector_name", ""))
        if det.endswith("_heuristic"):
            candidatos.append(("BLOCK", REGLA_LEGACY.get(det, "regla determinista"), det))
        else:
            candidatos.append(("LIMIT", "anomalía del modelo", "modelo"))
    h = d.get("heuristico")
    if isinstance(h, dict) and h.get("accion") in SEVERIDAD_ACCION:
        candidatos.append((h["accion"], str(h.get("motivo", "")), str(h.get("heuristico", "regla"))))
    if not candidatos:
        return None
    # A igual severidad gana la regla: su motivo dice mas que «anomalia del modelo».
    return max(candidatos, key=lambda c: (SEVERIDAD_ACCION[c[0]], c[2] != "modelo"))


def acciones_vigentes(decisions: list[dict], ahora: float, feed_path: Path | None = None,
                      estado_path: Path | None = None, nunca: set[str] = NUNCA_BLOQUEAR) -> list[dict]:
    """LIMIT/BLOCK en vigor ahora, por IP.

    Dos fuentes. El feed publicado (feed.json) trae la caducidad exacta de lo
    que se publico en el ultimo minuto. Lo anterior se reconstruye del registro
    del motor con la misma escalera: ultima ofensa + 300 s (LIMIT) o 300/1800/
    3600 s (BLOCK, nivel leido de estado.json) + la cadencia del feed. Lo que el
    agente del host aplica es exactamente eso; el sensor no tiene otra forma de
    saberlo, porque el bloqueo ocurre en el host.
    """
    vigentes: dict[str, dict] = {}
    if feed_path is not None:
        try:
            feed = json.loads(Path(feed_path).read_text(encoding="utf-8"))
            for e in feed.get("entradas", []):
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
            previo["ofensas"] = len(episodio)
    salida = []
    for v in vigentes.values():
        v["expira_s"] = max(0, int(v["hasta"] - ahora))
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

    «IPs bloqueadas ahora» ensena lo vigente; esto ensena lo que ya paso. Se lee
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
    lineas = tail_lines(log_path, max_bytes=max_bytes)
    primera = None
    for linea in lineas[:50]:
        try:
            primera = float(json.loads(linea)["logged_at"])
            break
        except (ValueError, KeyError, TypeError):
            continue
    ofensas: dict[str, list[tuple[float, str, str, str]]] = {}
    for linea in lineas:
        if '"ALERT"' not in linea and '"accion"' not in linea:
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue
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
                "vigente": caduca > ahora,
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
                         "/api/aprendizaje", "/api/comparacion", "/api/despliegue"})

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
                                "reentrenamiento supervisado: lote, deriva, candidato"),
                            rel("artifacts/aprendizaje/registro.jsonl", "jsonl",
                                "linaje: un registro encadenado por lote"),
                            _stat_fichero(config_usada, "toml", "politica: seccion [reentrenamiento]")],
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
        "--feed-estado", type=Path, default=Path.home() / "feed" / "estado.json",
        help="estado de la escalera del publicador: nivel de reincidencia por IP")
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
                self._send_json(
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
                return
            if path == "/api/acciones":
                self._send_json(historial_acciones(args.log_path, time.time()))
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
                    self._send_json(vista_vivo.calcular_con_cache(
                        args.eve_path, cfg, todos=params.get("todos") == "1",
                        limite=min(int(limite), 3000) if limite.isdigit() else 150))
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": "%s: %s" % (type(exc).__name__, exc)})
                return
            if path == "/api/comparacion":
                self._send_json(estado_comparacion(args.comparacion))
                return
            if path == "/api/aprendizaje":
                self._send_json(estado_aprendizaje(args.config_toml, args.demo))
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
