"""Director de la demo de CyberFlow: conduce los paneles de Herdr paso a paso.

Cada escenario (escenarios/NN-*/escenario.yaml) es una lista de pasos. El director
explica el paso, escribe el comando en el panel de la maquina que toca, espera
el resultado o el hito (deteccion, publicacion, aplicacion) midiendo el tiempo y
dice donde verlo en el panel web. Todo queda en registros/<fecha>.csv.

Cada corrida escribe ademas evidencias/<fecha>-corrida<N>/EVIDENCIA.md, que se
reescribe tras cada paso: comando y maquina, que hace, salida de la consola
(leida del panel de Herdr), ruta de la misma evidencia en la GUI, captura del
panel web (si llega) y lo que le falta a la GUI (corrida 1) o la mejora visible
(corrida 2).

Capturas: en los pasos con «captura», el director deja capturas/pendiente.json
y espera hasta 75 s a que aparezca capturas/<nombre>.png (la toma Claude con la
extension de Chrome). Si no llega, sigue y el .md la marca pendiente.

Teclas: Enter/Espacio = siguiente · r = repetir comando · s = saltar paso ·
        q = salir · a = automatico si/no
Uso:    python director.py               (menu de escenarios)
        python director.py demo --auto --corrida 1   (los 4 defendibles: L4, HTTP, L3, FP)
        python director.py 05 --auto     (un escenario, sin pulsar teclas)
        python director.py todos --auto --sin-comparar
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parent
BASTION = "gadmin@10.10.10.30"
ESTADO_HERDR = AQUI / "estado-herdr.json"
PROMPT = {"kali": "kali)-[", "clientes": "adminclientes@clientesadmin"}
PROMPT_BASTION = "gadmin@VM-GESTION"
SALTOS = {"sensor": ("sensor1", "m4rk@cyberflow-sensor"), "srvdmz": ("srvdmz", "adminsrvdmz@srv-dmz"),
          "bastion": (None, PROMPT_BASTION)}

R, B, D = "\033[0m", "\033[1m", "\033[2m"
CIAN, AMA, ROJO, VERDE, MAG = "\033[1;36m", "\033[1;33m", "\033[1;31m", "\033[1;32m", "\033[1;35m"
COLOR_PANEL = {"origen": ROJO, "sensor": CIAN, "srvdmz": AMA, "bastion": MAG}
NOMBRE_PANEL = {"sensor": "SENSOR1", "srvdmz": "SRV-DMZ", "bastion": "BASTIÓN · Suricata"}
MAQUINA = {"kali": "[KALI adminatacante]", "clientes": "[CLIENTES adminclientes]", "sensor": "[SENSOR1 m4rk]",
           "srvdmz": "[SRV-DMZ adminsrvdmz]", "bastion": "[BASTIÓN gadmin]"}
DEMO = ["05", "03", "01", "04"]          # los defendibles, en orden de demo
PANEL_WEB = "https://10.10.60.11:8788"
ESPERA_CAPTURA = 75

try:
    import msvcrt  # Windows
except ImportError:  # pragma: no cover
    msvcrt = None


# ---------------------------------------------------------------- herdr / ssh
def herdr(*args: str, timeout: float = 30) -> str:
    r = subprocess.run(["herdr", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout


def bastion(cmd: str, timeout: float = 30) -> str:
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", BASTION, cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout.strip()


class Paneles:
    def __init__(self):
        self.ids = json.loads(ESTADO_HERDR.read_text(encoding="utf-8"))
        self.origen_host = self.ids.get("origen_host", "kali")

    def id(self, panel: str) -> str:
        return self.ids["origen" if panel == "origen" else panel]

    def etiqueta(self, panel: str, activo: bool):
        nombre = ("ORIGEN · " + self.origen_host.upper()) if panel == "origen" else NOMBRE_PANEL[panel]
        herdr("pane", "rename", self.id(panel), ("▶ " if activo else "") + nombre)

    def todas_las_etiquetas(self, activo: str | None = None):
        for p in ("origen", "sensor", "srvdmz", "bastion"):
            self.etiqueta(p, p == activo)

    def ejecutar(self, panel: str, comando: str):
        herdr("pane", "run", self.id(panel), comando)

    def ctrl_c(self, panel: str):
        herdr("pane", "send-keys", self.id(panel), "ctrl+c")

    def leer(self, panel: str, lineas: int = 30, fuente: str = "recent-unwrapped") -> str:
        """Lo que se ve en la consola del panel (texto plano) para el .md de evidencia."""
        t = herdr("pane", "read", self.id(panel), "--source", fuente, "--lines", str(lineas))
        filas = [l.rstrip() for l in t.splitlines()]
        while filas and not filas[-1].strip():
            filas.pop()
        return "\n".join(filas)

    def esperar_texto(self, panel: str, texto: str, ms: int) -> bool:
        r = subprocess.run(["herdr", "pane", "wait-output", self.id(panel), "--match", texto,
                            "--source", "recent", "--lines", "60", "--timeout", str(ms)],
                           capture_output=True, text=True)
        return r.returncode == 0

    def asegurar_conexiones(self):
        """Antes de la demo: cada consola debe estar en su máquina. Si una sesión SSH se cayó
        (el panel volvió al PowerShell local), se reconecta por el bastión."""
        for panel, (alias, prompt) in SALTOS.items():
            self.ctrl_c(panel)
            time.sleep(0.4)
            filas = [l for l in self.leer(panel, 6, "visible").splitlines() if l.strip()]
            if prompt in " ".join(filas[-2:]):
                continue
            if PROMPT_BASTION not in " ".join(filas[-2:]):
                self.ejecutar(panel, "ssh -t " + BASTION)
                self.esperar_texto(panel, PROMPT_BASTION, 20000)
            if alias:
                self.ejecutar(panel, "ssh " + alias)
                self.esperar_texto(panel, prompt, 20000)
        objetivo = self.origen_host
        self.origen_host = ""
        self.usar_origen(objetivo)

    def usar_origen(self, host: str):
        """El panel ORIGEN salta a la maquina del escenario (Kali o clientes)."""
        def ultima() -> str:
            filas = [l for l in self.leer("origen", 6, "visible").splitlines() if l.strip()]
            return " ".join(filas[-2:])  # el prompt de Kali ocupa dos lineas

        if self.origen_host == host and PROMPT[host] in ultima():
            return
        self.ctrl_c("origen")
        time.sleep(0.6)
        # Solo se sale si el panel está DENTRO de la máquina anterior: un «exit» de más cerraría
        # la sesión del bastión (y el panel entero, como pasó el 3-nov).
        if any(p in ultima() for p in PROMPT.values()):
            self.ejecutar("origen", "exit")
            self.esperar_texto("origen", PROMPT_BASTION, 10000)
            time.sleep(0.5)
        if PROMPT_BASTION not in ultima():
            self.ejecutar("origen", "ssh -t " + BASTION)
            self.esperar_texto("origen", PROMPT_BASTION, 20000)
        self.ejecutar("origen", "ssh " + host)
        self.esperar_texto("origen", PROMPT[host], 20000)
        self.origen_host = host
        self.ids["origen_host"] = host
        ESTADO_HERDR.write_text(json.dumps(self.ids, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- pantalla
def mmss(s: float) -> str:
    s = max(0, int(round(s)))
    return "%02d:%02d" % (s // 60, s % 60)


def ancho() -> int:
    try:
        return max(60, min(170, os.get_terminal_size().columns - 2))
    except OSError:
        return 120


def envolver(texto: str, w: int, sangria: str = "  ") -> list[str]:
    palabras, lineas, actual = texto.split(), [], sangria
    for p in palabras:
        if len(actual) + len(p) + 1 > w:
            lineas.append(actual)
            actual = sangria
        actual += ("" if actual == sangria else " ") + p
    lineas.append(actual)
    return lineas


class Pantalla:
    def __init__(self, esc: dict, total: int, corrida: int):
        self.esc, self.total, self.corrida = esc, total, corrida
        self.hitos: dict[str, str] = {}
        self.t0_local: float | None = None
        self.historial: list[str] = []

    def anotar(self, n: int, texto: str, ok: bool = True):
        reloj = (" +" + mmss(time.time() - self.t0_local)) if self.t0_local else "      "
        self.historial.append("%s%s%s%s  %2d  %s%s%s" % (D, time.strftime("%H:%M:%S"), reloj, R, n,
                                                       VERDE if ok else AMA, "✔" if ok else "·", R) + " " + texto)

    def pintar(self, i: int, paso: dict, cuerpo: list[str], pie: str, auto: bool):
        w = ancho()
        barra = "".join("■" if k < i else ("▶" if k == i else "·") for k in range(self.total))
        reloj = ("  ⏱ +" + mmss(time.time() - self.t0_local)) if self.t0_local else ""
        out = ["\033[H\033[2J",
               "%s%s%s  %s%s%s   paso %d/%d  %s%s%s%s   %scorrida %d%s" % (
                   B, self.esc["titulo"], R, D, self.esc.get("capa", ""), R, i + 1, self.total, CIAN, barra, R,
                   reloj, D, self.corrida, R)]
        if self.hitos:
            out.append("  " + "   ".join("%s%s%s %s" % (VERDE, k, R, v) for k, v in self.hitos.items()))
        out.append(D + "─" * w + R)
        out += cuerpo
        gui = paso.get("gui")
        if self.corrida >= 2 and paso.get("gui_mejora"):
            gui = paso["gui_mejora"]
        if gui:
            out.append("  %s🖥  GUI en paralelo → %s%s" % (VERDE, gui, R))
        if self.corrida == 1 and paso.get("gui_falta"):
            out += [D + l + R for l in envolver("⚠ falta en la GUI: " + paso["gui_falta"], w, "     ")]
        if self.historial:
            out.append(D + "─ historial " + "─" * (w - 12) + R)
            out += ["  " + h for h in self.historial[-9:]]
        out.append(D + "─" * w + R)
        out.append("  " + pie + ("   %s[auto]%s" % (AMA, R) if auto else ""))
        sys.stdout.write("\n".join(out) + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------- evidencia (.md)
def recortar(texto: str, cmd: str) -> str:
    """Desde la ultima linea donde se tecleo el comando: solo la salida de ESTA orden."""
    filas = texto.splitlines()
    clave = cmd.strip()[:25]
    for k in range(len(filas) - 1, -1, -1):
        if clave and clave in filas[k]:
            filas = filas[k:]
            break
    return "\n".join(f for f in filas if not f.startswith("· listo"))


def bloque(texto: str, lang: str = "text") -> str:
    return "```%s\n%s\n```" % (lang, texto.replace("```", "'''")) if texto.strip() else "_(sin salida)_"


class Evidencia:
    """EVIDENCIA.md de la corrida, reescrito tras cada paso."""

    def __init__(self, carpeta: Path, corrida: int):
        self.dir, self.corrida = carpeta, corrida
        self.cap = carpeta / "capturas"
        self.cap.mkdir(parents=True, exist_ok=True)
        self.inicio = time.strftime("%Y-%m-%d %H:%M:%S")
        self.escs: list[dict] = []

    def escenario(self, esc: dict, carpeta: str):
        self.escs.append({"esc": esc, "carpeta": carpeta, "pasos": [], "hitos": {}, "preparar": ""})
        self.escribir()

    def paso(self, **kw):
        self.escs[-1]["pasos"].append(kw)
        self.escribir()

    def hito(self, nombre: str, detalle: str):
        self.escs[-1]["hitos"][nombre] = detalle
        self.escribir()

    def captura_png(self, nombre: str) -> list[str]:
        """La captura principal y las de otras secciones del panel (<nombre>-<seccion>.png)."""
        fs = sorted(self.cap.glob(nombre + ".png")) + sorted(self.cap.glob(nombre + "-*.png"))
        return ["capturas/" + f.name for f in fs]

    def escribir(self):
        L = ["# Evidencia de la demo CyberFlow · corrida %d" % self.corrida, "",
             "- Inicio: %s (hora de la laptop) · actualizado %s" % (self.inicio, time.strftime("%H:%M:%S")),
             "- Consolas: Herdr, espacio «CYBERFLOW DEMO» (ORIGEN · DIRECTOR · SENSOR1 · SRV-DMZ · BASTIÓN).",
             "- GUI: panel web %s, sección «Escenario en vivo»." % PANEL_WEB,
             "- Corrida 1 = la GUI tal como estaba: se anota lo que le falta. Corrida 2 = la GUI mejorada: se anota "
             "lo que ahora enseña. Corrida 3+ = recorrido guiado (Actividad → Decisiones → Respuestas → Host). "
             "Lo que es «solo CLI» lo es a propósito.", "- Guion defendible: ../../GUION-DEMO.md", ""]
        L += ["## Resumen", "", "| Escenario | IP | Detección | Publicación | Aplicación |", "|---|---|---|---|---|"]
        for e in self.escs:
            h = e["hitos"]
            sin = h.get("Sin acción (PERMIT)")
            L.append("| %s | %s | %s | %s | %s |" % (e["esc"]["titulo"], e["esc"]["ip"],
                                                   ("PERMIT: " + sin) if sin else h.get("Detección", "—"),
                                                   "no se publica nada" if sin else h.get("Publicación", "—"),
                                                   "sin regla en el host" if sin else h.get("Aplicación", "—")))
        clave = "gui_falta" if self.corrida == 1 else "gui_mejora"
        notas = []
        for e in self.escs:
            for p in e["pasos"]:
                n = p.get(clave)
                if n and n not in notas:
                    notas.append(n)
        L += ["", "## %s" % ("Lo que le falta a la GUI (corrida 1)" if self.corrida == 1
                            else "Lo que la GUI enseña ahora (corrida 2)"), ""]
        reales = [n for n in notas if not n.startswith("Solo CLI")]
        L += ["- " + n for n in reales] or ["- (nada anotado todavía)"]
        cli = sorted({p["gui_falta"] for e in self.escs for p in e["pasos"]
                      if (p.get("gui_falta") or "").startswith("Solo CLI")})
        if cli:
            L += ["", "Evidencia que queda solo en la consola, por diseño:", ""] + ["- " + n[10:] for n in cli]
        for k, e in enumerate(self.escs, 1):
            esc = e["esc"]
            L += ["", "## %d. %s" % (k, esc["titulo"]), "",
                  "%s · tipo: %s · IP observada: `%s` · origen: %s" % (esc.get("capa", ""), esc["tipo"], esc["ip"],
                                                                      MAQUINA.get(esc.get("origen", "kali"), "")), ""]
            if e["preparar"]:
                L += ["Preparación (automática, %s): %s" % (MAQUINA["srvdmz"], e["preparar"]), ""]
            for p in e["pasos"]:
                L += ["### Paso %d · %s" % (p["n"], p["titulo"]), "",
                      "- Hora: %s%s · resultado: **%s**%s" % (
                          p["hora"], (" · +%s desde el ataque" % p["t"]) if p.get("t") else "", p["estado"],
                          (" · " + p["detalle"]) if p.get("detalle") else "")]
                if p.get("comando"):
                    L += ["- Dónde: `%s` → lo ejecuta el director en el panel Herdr «%s»" % (p["maquina"], p["panel_nombre"]),
                          "", bloque(p["comando"], "bash"), ""]
                if p.get("procedimiento"):
                    L += ["- Qué hace: " + p["procedimiento"]]
                if p.get("salida") is not None:
                    L += ["- Salida en la consola (leída del panel Herdr «%s»):" % p.get("panel_nombre", ""), "",
                          bloque(p["salida"]), ""]
                gui = p.get("gui_mejora") if self.corrida >= 2 and p.get("gui_mejora") else p.get("gui")
                if gui:
                    L += ["- En la GUI (en paralelo): " + gui]
                if p.get("captura"):
                    pngs = self.captura_png(p["captura"])
                    if pngs:
                        L += ["", "**CyberFlow (GUI) en ese instante:**", ""]
                        L += ["![%s](%s)" % (Path(x).stem, x) for x in pngs]
                        L.append("")
                    else:
                        L += ["- Captura `%s.png`: _pendiente (no llegó a tiempo)_" % p["captura"]]
                if p.get("consolas"):
                    L += ["", "<details><summary>Las cinco consolas de Herdr en el mismo instante</summary>", ""]
                    for nom, txt in p["consolas"].items():
                        L += ["**%s**" % nom, "", bloque(txt), ""]
                    L += ["</details>", ""]
                if (p.get("gui_falta") or "").startswith("Solo CLI"):
                    L += ["- ℹ " + p["gui_falta"]]
                elif self.corrida == 1 and p.get("gui_falta"):
                    L += ["- ⚠ Falta en la GUI: " + p["gui_falta"]]
                if self.corrida >= 2 and p.get("gui_mejora"):
                    L += ["- ✔ Mejora visible: " + p["gui_mejora"]]
                L.append("")
        tmp = self.dir / "EVIDENCIA.md.tmp"
        tmp.write_text("\n".join(L) + "\n", encoding="utf-8")
        tmp.replace(self.dir / "EVIDENCIA.md")


def pedir_captura(ev: Evidencia, nombre: str, ip: str, t0: float | None, ruta: str, pant: "Pantalla",
                  i: int, paso: dict, cuerpo: list[str], pie: str, auto: bool) -> bool:
    """Deja el pedido y espera la imagen; s = seguir sin ella."""
    png = ev.cap / (nombre + ".png")
    if png.exists():
        png.unlink()
    pedido = ev.cap / "pendiente.json"
    pedido.write_text(json.dumps({"nombre": nombre, "ip": ip, "t0": t0, "ruta": ruta, "pedido": time.time()},
                                 ensure_ascii=False), encoding="utf-8")
    fin = time.time() + ESPERA_CAPTURA
    try:
        while time.time() < fin:
            if png.exists():
                return True
            pant.pintar(i, paso, cuerpo + ["", "  %s📷 esperando captura de la GUI «%s»: %d s · s = seguir sin ella%s"
                                           % (AMA, nombre, int(fin - time.time()), R)], pie, auto)
            if tecla(1) == "s":
                return False
        return False
    finally:
        try:
            pedido.unlink()
        except OSError:
            pass


def tecla(espera: float | None) -> str | None:
    """Lee una tecla sin bloquear mas de `espera` segundos (None = bloquea)."""
    fin = None if espera is None else time.time() + espera
    while fin is None or time.time() < fin:
        if msvcrt and msvcrt.kbhit():
            c = msvcrt.getwch()
            return {"\r": "enter", " ": "enter"}.get(c, c.lower())
        if not msvcrt and espera is None:
            return input().strip().lower() or "enter"
        time.sleep(0.05)
    return None


# ---------------------------------------------------------------- hitos
def leer_estado(ip: str, t0_sensor: float) -> dict:
    try:
        return json.loads(bastion("bash ~/cf-demo/estado.sh %s %d" % (ip, int(t0_sensor) - 2), timeout=25) or "{}")
    except (ValueError, subprocess.TimeoutExpired):
        return {}


def hito_cumplido(hito: str, st: dict, t0: float) -> tuple[bool, str]:
    s, h = st.get("sensor") or {}, st.get("host") or {}
    if hito == "deteccion":
        p = s.get("primera")
        if p:
            peor = s.get("peor") or p
            return True, "+%s %s por %s · %s" % (mmss(p["t"] - t0), peor["accion"], s.get("quien"),
                                                (peor.get("motivo") or "")[:60])
        return False, "%d ventana(s) de la IP, sin acción todavía" % s.get("ventanas", 0)
    if hito == "publicacion":
        f = (s.get("feed") or {})
        e = f.get("entrada")
        p = s.get("primera")
        # la orden cuenta solo si la emitio un detector que disparo en ESTE escenario
        det = set(s.get("detectores") or [])
        propia = e and (e.get("detector") in det or (e.get("detector", "").startswith("if_") and "modelo" in det)
                        )
        if propia and p and f.get("generado", 0) >= p["t"]:
            nivel = e.get("nivel", 0)
            extra = " · reincidencia nivel %d" % nivel if nivel else ""
            return True, "+%s %s en el feed firmado (%s), caduca %s%s" % (
                mmss(f["generado"] - t0), e["accion"], e.get("detector"),
                time.strftime("%H:%M:%S", time.localtime(e["hasta"])), extra)
        return False, "aún no está en el feed"
    if hito == "aplicacion":
        if h.get("agente") and h.get("agente") != "active":
            return True, "agente EN SOMBRA: orden publicada, no aplicada"
        if h.get("nft") in ("BLOCK", "LIMIT"):
            # si el director estuvo esperando una captura, la hora real la da el acuse del host
            t = time.time() + st.get("_offset", 0)
            ap = (st.get("acuse") or {}).get("aplicada_t")
            if ap:
                t = min(t, ap)
            return True, "+%s %s aplicado en nftables de srv-dmz" % (mmss(t - t0), h["nft"])
        return False, "el agente aún no la aplica"
    if hito == "sin_accion":
        # tráfico legítimo: el hito se cumple si, pasado el tiempo, no hubo NINGUNA acción
        e = (s.get("feed") or {}).get("entrada")
        if s.get("primera") or e or h.get("nft") in ("BLOCK", "LIMIT"):
            p = s.get("peor") or s.get("primera") or {}
            return False, "FALSO POSITIVO: %s por %s · %s" % (p.get("accion") or (e or {}).get("accion", "?"),
                                                             s.get("quien") or "?", (p.get("motivo") or "")[:60])
        return True, "%d ventanas analizadas · 0 con acción · %d anomalías marginales del modelo descartadas · " \
                     "fuera del feed y del firewall" % (s.get("ventanas", 0), s.get("marginales", 0))
    return False, "?"


class Vigia(threading.Thread):
    """Desde el ataque consulta el estado cada ~3 s y guarda la PRIMERA vez que se cumple cada hito.

    Así una espera de captura de la GUI no retrasa la hora medida de publicación o aplicación.
    """

    def __init__(self, ip: str, t0: float, offset: float):
        super().__init__(daemon=True)
        self.ip, self.t0, self.offset = ip, t0, offset
        self.primero: dict[str, str] = {}
        self.ultimo: dict = {}
        self.parar = False

    def run(self):
        while not self.parar:
            st = leer_estado(self.ip, self.t0)
            st["_offset"] = self.offset
            self.ultimo = st
            for h in ("deteccion", "publicacion", "aplicacion"):
                if h not in self.primero:
                    ok, det = hito_cumplido(h, st, self.t0)
                    if ok:
                        self.primero[h] = det
            time.sleep(1.5)


# ---------------------------------------------------------------- escenario
TITULO_TIPO = {"decir": "Se dice", "ejecutar": "Comando", "ataque": "ATAQUE", "panel": "GUI",
               "esperar": "Espera de hito", "comparar": "Comparación con Suricata"}


def correr(carpeta: Path, pan: Paneles, auto: bool, comparar: bool, reg: csv.writer, ev: Evidencia, corrida: int):
    esc = yaml.safe_load((carpeta / "escenario.yaml").read_text(encoding="utf-8"))
    ip = esc["ip"]
    pasos = [p for p in esc["pasos"] if comparar or p["tipo"] != "comparar"]
    pant = Pantalla(esc, len(pasos), corrida)
    ev.escenario(esc, carpeta.name)
    t0_sensor, offset, aplicada = None, 0.0, False
    ult_origen = 0.0
    fin_cmp = None
    idx_ataque, cmd_ataque = None, ""
    vigia: Vigia | None = None
    pan.usar_origen(esc.get("origen", "kali"))
    # Punto de partida limpio: si la IP quedó en el firewall por un escenario anterior, se libera.
    # Una ofensa nueva renueva la orden y el agente la vuelve a aplicar.
    limpio = False
    for _ in range(3):
        try:
            r = bastion("ssh -o BatchMode=yes srvdmz '~/cf-demo/desbloquear.sh %s 15 >/dev/null 2>&1; "
                        "~/cf-demo/en-firewall.sh %s'" % (ip, ip), timeout=30)
        except subprocess.TimeoutExpired:
            r = ""
        if r.strip().endswith("NO"):
            limpio = True
            break
        time.sleep(3)
    reg.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), esc["titulo"], "preparar", "srvdmz",
                  "desbloquear.sh %s 15" % ip, "ok" if limpio else "IP sigue en el firewall", "", ""])
    ev.escs[-1]["preparar"] = ("`~/cf-demo/desbloquear.sh %s 15` y comprobación con `en-firewall.sh`: %s" %
                               (ip, "la IP parte sin regla (NO)" if limpio else "la IP SIGUE en el firewall"))
    pant.anotar(0, "preparación: %s %s" % (ip, "sin regla" if limpio else "SIGUE en el firewall"), limpio)
    for p in ("sensor", "srvdmz"):
        pan.ctrl_c(p)
    pan.todas_las_etiquetas()

    def log(paso, estado, detalle="", salida=None, n=None):
        t = "" if t0_sensor is None else "%.1f" % (time.time() + offset - t0_sensor)
        cmd_ = paso.get("comando", "").replace("{ip}", ip)
        if paso.get("tipo") == "comparar":
            cmd_ = "~/cf-demo/comparar-suricata.sh %s <inicio> <aplicación>" % ip
        reg.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), esc["titulo"], paso.get("tipo"), paso.get("panel", ""),
                      cmd_, estado, detalle, t])
        pnl = paso.get("panel") or ("bastion" if paso.get("tipo") == "comparar" else None)
        maq = MAQUINA.get(pan.origen_host if pnl == "origen" else pnl or "", "")
        nombre_pnl = ("ORIGEN · " + pan.origen_host.upper()) if pnl == "origen" else NOMBRE_PANEL.get(pnl or "", "")
        titulo = TITULO_TIPO.get(paso.get("tipo"), paso.get("tipo"))
        if paso.get("tipo") == "esperar":
            titulo += " · " + paso["hito"]
        if paso.get("tipo") == "panel":
            titulo += " · " + paso["ruta"]
        else:
            titulo += " · " + (paso.get("explica") or paso.get("texto") or "").strip().split(". ")[0][:110]
        ok = estado in ("ok", "mostrado")
        pant.anotar(n or 0, "%s · %s%s" % (TITULO_TIPO.get(paso.get("tipo"), ""), estado,
                                           (" · " + detalle[:70]) if detalle else ""), ok)
        ev.paso(n=n or 0, titulo=titulo, hora=time.strftime("%H:%M:%S"), t=t, estado=estado, detalle=detalle,
                comando=cmd_ if pnl else "", maquina=maq, panel_nombre=nombre_pnl,
                procedimiento=paso.get("procedimiento") or (paso.get("texto") if paso.get("tipo") == "decir" else ""),
                salida=salida, gui=paso.get("ruta") if paso.get("tipo") == "panel" else paso.get("gui"),
                gui_falta=paso.get("gui_falta"), gui_mejora=paso.get("gui_mejora"),
                captura=paso.get("_captura"), consolas=paso.get("_consolas"))

    i = 0
    while i < len(pasos):
        paso = pasos[i]
        tipo = paso["tipo"]
        cmd = paso.get("comando", "").replace("{ip}", ip)
        panel = paso.get("panel")
        if paso.get("si") == "aplicada" and not aplicada:
            log(paso, "omitido", "sin aplicación real en el host", n=i + 1)
            i += 1
            continue
        cuerpo: list[str] = []
        w = ancho()
        if tipo == "decir":
            cuerpo += [AMA + l + R for l in envolver("«" + paso["texto"].strip() + "»", w)]
        elif tipo in ("ejecutar", "ataque"):
            nombre = ("ORIGEN · " + pan.origen_host.upper()) if panel == "origen" else NOMBRE_PANEL[panel]
            maq = MAQUINA.get(pan.origen_host if panel == "origen" else panel, "")
            cuerpo += envolver(paso["explica"], w)
            cuerpo.append("  %s▶ %s%s  %s%s%s   %s$ %s%s" % (COLOR_PANEL[panel], nombre, R, D, maq, R, B, cmd, R))
            if paso.get("procedimiento"):
                cuerpo += [D + l + R for l in envolver("Qué hace: " + paso["procedimiento"], w, "     ")]
            if paso.get("sudo"):
                cuerpo.append("  %sPide la contraseña de sudo: escríbela tú en el panel %s.%s" % (ROJO, nombre, R))
        elif tipo == "panel":
            cuerpo += envolver(paso["explica"], w)
            cuerpo.append("  %s🖥  PANEL WEB → %s%s" % (VERDE, paso["ruta"], R))
        elif tipo == "esperar":
            cuerpo += envolver(paso["explica"], w)
        elif tipo == "comparar":
            cuerpo += envolver(paso["explica"], w)
            cuerpo.append("  %s▶ BASTIÓN · Suricata%s   %s$ comparar-suricata.sh %s <inicio> <ahora>%s" % (MAG, R, B, ip, R))
        pie = "%sEnter%s ejecutar/seguir · %sr%s repetir · %ss%s saltar · %sa%s auto · %sq%s salir" % (
            B, R, B, R, B, R, B, R, B, R)
        pant.pintar(i, paso, cuerpo, pie, auto)

        k = tecla(2.5 if auto else None)
        if k == "q":
            log(paso, "salida", n=i + 1)
            return False
        if k == "a":
            auto = not auto
            continue
        if k == "s":
            log(paso, "saltado", n=i + 1)
            i += 1
            continue
        nombre_cap = "%s-%s" % (carpeta.name[:2], paso["captura"]) if paso.get("captura") else None

        def capturar():
            if nombre_cap:
                # las cinco consolas en el mismo instante que la captura de la GUI
                paso["_consolas"] = {
                    ("ORIGEN · " + pan.origen_host.upper()): pan.leer("origen", 16, "visible"),
                    "SENSOR1": pan.leer("sensor", 16, "visible"),
                    "SRV-DMZ": pan.leer("srvdmz", 16, "visible"),
                    "BASTIÓN · Suricata": pan.leer("bastion", 12, "visible"),
                    "DIRECTOR": herdr("pane", "read", pan.ids["director"], "--source", "visible", "--lines", "40"),
                }
                ok_c = pedir_captura(ev, nombre_cap, ip, pant.t0_local, paso.get("gui_mejora") if corrida >= 2 and
                                     paso.get("gui_mejora") else paso.get("ruta") or paso.get("gui", ""),
                                     pant, i, paso, cuerpo, pie, auto)
                paso["_captura"] = nombre_cap
                pant.anotar(i + 1, "captura GUI %s %s" % (nombre_cap, "ok" if ok_c else "pendiente"), ok_c)

        # -- acción del paso
        if tipo in ("ejecutar", "ataque"):
            pan.todas_las_etiquetas(panel)
            if panel in ("sensor", "srvdmz"):
                pan.ctrl_c(panel)
                time.sleep(0.4)
                herdr("pane", "run", pan.id(panel), "clear")
            if tipo == "ataque":
                # la prueba del firewall «antes» no debe caer en la misma ventana de 10 s que el ataque
                falta = 12 - (time.time() - ult_origen)
                while falta > 0:
                    pant.pintar(i, paso, cuerpo + ["", "  %s… separando la prueba previa del ataque: %d s%s"
                                                   % (D, int(falta) + 1, R)], pie, auto)
                    time.sleep(min(1, falta))
                    falta = 12 - (time.time() - ult_origen)
                t_local = time.time()
                try:
                    t0_sensor = float(bastion("bash ~/cf-demo/estado.sh reloj", timeout=15))
                    offset = t0_sensor - time.time() + (time.time() - t_local) / 2
                except (ValueError, subprocess.TimeoutExpired):
                    t0_sensor, offset = time.time(), 0.0
                pant.t0_local = time.time()
                if vigia:
                    vigia.parar = True
                vigia = Vigia(ip, t0_sensor, offset)
                vigia.start()
            if panel == "origen" and idx_ataque is not None:
                # la salida del ataque ya terminó (o casi): se guarda antes de la siguiente orden en ORIGEN
                ev.escs[-1]["pasos"][idx_ataque]["salida"] = recortar(pan.leer("origen", 40), cmd_ataque)
                ev.escribir()
                idx_ataque = None
            ok = True
            if paso.get("espera"):
                # marca única calculada en la máquina remota: no se confunde con salidas anteriores
                n = int(time.time() * 10) % 1000000
                pan.ejecutar(panel, "%s; echo \"· listo $((%d+1))\"" % (cmd, n))
                ok = pan.esperar_texto(panel, "· listo %d" % (n + 1), 120000)
                salida = recortar(pan.leer(panel, 40), cmd)
            else:
                pan.ejecutar(panel, cmd)
                time.sleep(4)
                salida = pan.leer(panel, 25, "visible") if panel in ("sensor", "srvdmz") else \
                    recortar(pan.leer(panel, 40), cmd)
            if panel == "origen":
                ult_origen = time.time()
            log(paso, "ok" if ok else "sin la salida esperada", salida=salida, n=i + 1)
            if tipo == "ataque":
                idx_ataque, cmd_ataque = len(ev.escs[-1]["pasos"]) - 1, cmd
            capturar()
            if paso.get("_captura"):
                ev.escs[-1]["pasos"][-1]["captura"] = paso["_captura"]
                ev.escs[-1]["pasos"][-1]["consolas"] = paso.get("_consolas")
                ev.escribir()
        elif tipo == "esperar":
            hito = paso["hito"]
            if t0_sensor is None:
                log(paso, "sin ataque previo", n=i + 1)
                i += 1
                continue
            limite = time.time() + paso.get("max", 120)
            hecho, detalle = False, ""
            legit = hito == "sin_accion"
            while time.time() < limite:
                if legit:
                    st = dict(vigia.ultimo) if vigia and vigia.ultimo else leer_estado(ip, t0_sensor)
                    if not st.get("sensor") or not st.get("host"):
                        # lectura vacía (ssh lento): no cuenta como «sin acción» ni como fallo
                        st = leer_estado(ip, t0_sensor)
                    if not st.get("sensor") or not st.get("host"):
                        tecla(1.5)
                        continue
                    hecho, detalle = hito_cumplido(hito, st, t0_sensor)
                    restante = int(limite - time.time())
                    pant.pintar(i, paso, cuerpo + ["", "  %s%s%s" % (VERDE if hecho else ROJO,
                                                                     "✔ sin acción hasta ahora" if hecho else "✘ actuó",
                                                                     R), "  " + detalle,
                                                    "  %sobservando %d s más · s = cerrar ya%s" % (D, restante, R)],
                                pie, auto)
                    if not hecho or tecla(2) == "s":
                        break
                    continue
                if vigia and hito in vigia.primero:
                    hecho, detalle = True, vigia.primero[hito]
                else:
                    st = dict(vigia.ultimo) if vigia and vigia.ultimo else leer_estado(ip, t0_sensor)
                    st["_offset"] = offset
                    hecho, detalle = hito_cumplido(hito, st, t0_sensor)
                restante = int(limite - time.time())
                cuerpo2 = cuerpo + ["", "  %s%s%s  %s" % (VERDE if hecho else AMA,
                                                           "✔ " + hito.upper() if hecho else "… esperando " + hito,
                                                           R, detalle),
                                    "  %slímite en %d s · s = saltar%s" % (D, restante, R)]
                pant.pintar(i, paso, cuerpo2, pie, auto)
                if hecho:
                    break
                if tecla(1.5) == "s":
                    break
            if legit:
                # veredicto final con una lectura fresca, no con la última del vigía
                st = leer_estado(ip, t0_sensor)
                if st.get("sensor") and st.get("host"):
                    hecho, detalle = hito_cumplido(hito, st, t0_sensor)
            nombre = {"deteccion": "Detección", "publicacion": "Publicación", "aplicacion": "Aplicación",
                      "sin_accion": "Sin acción (PERMIT)"}[hito]
            pant.hitos[nombre] = detalle if hecho else "no en %d s" % paso.get("max", 120)
            if hito == "aplicacion":
                aplicada = hecho and "nftables" in detalle
                # Suricata compara solo el tráfico del ataque: antes de las pruebas de firewall
                fin_cmp = time.time() + offset
            ev.hito(nombre, pant.hitos[nombre])
            # lo que se ve en ese momento en la consola que prueba el hito
            consola = {"deteccion": ("sensor", 14), "publicacion": ("sensor", 8), "aplicacion": ("srvdmz", 20),
                       "sin_accion": ("sensor", 14)}[hito]
            pnl_h = dict(paso, panel=consola[0])
            log(pnl_h, "ok" if hecho else "no alcanzado", detalle, salida=pan.leer(consola[0], consola[1], "visible"),
                n=i + 1)
            ev.escs[-1]["pasos"][-1]["comando"] = ""
            pant.pintar(i, paso, cuerpo + ["", "  %s%s%s" % (VERDE if hecho else ROJO, pant.hitos[nombre], R)], pie, auto)
            if hecho:
                capturar()
                if paso.get("_captura"):
                    ev.escs[-1]["pasos"][-1]["captura"] = paso["_captura"]
                    ev.escs[-1]["pasos"][-1]["consolas"] = paso.get("_consolas")
                    ev.escribir()
            tecla(3 if auto else 1.5)
        elif tipo == "comparar":
            if t0_sensor is None:
                log(paso, "sin ataque previo", n=i + 1)
                i += 1
                continue
            pan.todas_las_etiquetas("bastion")
            fin = fin_cmp or (time.time() + offset)
            n = int(time.time()) % 100000
            # la marca se calcula en el bastión: el texto tecleado no coincide con el impreso
            pan.ejecutar("bastion", "clear; ~/cf-demo/comparar-suricata.sh %s %d %d %s; echo FIN-CMP-$((%d+1))"
                         % (ip, int(t0_sensor) - 2, int(fin), esc.get("panel_id", ""), n))
            ok = pan.esperar_texto("bastion", "FIN-CMP-%d" % (n + 1), 300000)
            log(paso, "ok" if ok else "no terminó", salida=recortar(pan.leer("bastion", 45), "comparar-suricata"),
                n=i + 1)
            capturar()
            if paso.get("_captura"):
                ev.escs[-1]["pasos"][-1]["captura"] = paso["_captura"]
                ev.escs[-1]["pasos"][-1]["consolas"] = paso.get("_consolas")
                ev.escribir()
        else:
            if tipo == "panel":
                capturar()
            log(paso, "mostrado", n=i + 1)
            if auto:
                time.sleep(1.5)
        i += 1
    if vigia:
        vigia.parar = True
    if idx_ataque is not None:
        ev.escs[-1]["pasos"][idx_ataque]["salida"] = recortar(pan.leer("origen", 40), cmd_ataque)
        ev.escribir()
    pan.todas_las_etiquetas()
    resumen = ["  %s%s%s %s" % (VERDE, k, R, v) for k, v in pant.hitos.items()] or ["  (sin hitos)"]
    pant.pintar(len(pasos) - 1, pasos[-1], ["  %sEscenario terminado.%s" % (B, R)] + resumen,
                "Enter: volver al menú", auto)
    tecla(4 if auto else None)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("escenario", nargs="?", help="número (05), nombre o «todos»")
    ap.add_argument("--auto", action="store_true", help="avanza solo (para ensayar y medir)")
    ap.add_argument("--sin-comparar", action="store_true", help="omite la comparación con Suricata")
    ap.add_argument("--corrida", type=int, default=1, help="1 = anota lo que falta en la GUI; 2 = la GUI mejorada")
    a = ap.parse_args()
    if os.name == "nt":
        os.system("")  # activa ANSI en la consola de Windows
    carpetas = sorted(p for p in (AQUI / "escenarios").iterdir() if (p / "escenario.yaml").exists())
    (AQUI / "registros").mkdir(exist_ok=True)
    ruta = AQUI / "registros" / time.strftime("%Y%m%d-%H%M%S.csv")
    pan = Paneles()
    pan.asegurar_conexiones()
    ev = Evidencia(AQUI / "evidencias" / ("%s-corrida%d" % (time.strftime("%Y%m%d-%H%M"), a.corrida)), a.corrida)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        reg = csv.writer(fh)
        reg.writerow(["hora_local", "escenario", "tipo", "panel", "comando", "estado", "detalle", "t_desde_ataque_s"])
        if a.escenario:
            if a.escenario == "demo":
                sel = [c for n in DEMO for c in carpetas if c.name.startswith(n)]
            elif a.escenario == "todos":
                sel = carpetas
            else:
                sel = [c for c in carpetas if c.name.startswith(a.escenario) or a.escenario in c.name]
            for c in sel:
                if not correr(c, pan, a.auto, not a.sin_comparar, reg, ev, a.corrida):
                    break
                fh.flush()
            return
        while True:
            sys.stdout.write("\033[H\033[2J%sCyberFlow · demo guiada%s   (registro: %s)\n\n" % (B, R, ruta.name))
            for n, c in enumerate(carpetas, 1):
                e = yaml.safe_load((c / "escenario.yaml").read_text(encoding="utf-8"))
                sys.stdout.write("  %s%d%s  %-48s %s%s · %s%s\n" % (CIAN, n, R, e["titulo"], D, e.get("capa", ""), e["tipo"], R))
            sys.stdout.write("\n  número = correr · q = salir\n")
            sys.stdout.flush()
            k = tecla(None)
            if k == "q":
                return
            if k and k.isdigit() and 1 <= int(k) <= len(carpetas):
                correr(carpetas[int(k) - 1], pan, a.auto, not a.sin_comparar, reg, ev, a.corrida)
                fh.flush()


if __name__ == "__main__":
    main()
