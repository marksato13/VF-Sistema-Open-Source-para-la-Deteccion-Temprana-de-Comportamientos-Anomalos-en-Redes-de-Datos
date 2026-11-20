#!/usr/bin/env python3
"""Envoltorio de la Campaña B (bastión). NO modifica el generador de A: lo invoca como comando externo, episodio a episodio.

Por episodio: 1) puerta D5 (d5_episodio.Puerta); si no pasa, el episodio NO inicia y la campaña se detiene (rc 3);
2) marca de inicio; 3) comando del episodio (el que se declare en el plan); 4) marca de fin. Al terminar escribe
<fase_dir>/replay/rc.txt = «rc=<rc> (orquestador de la campaña B; no hubo replay)», que es lo que exige `cf-4b-rotacion cierre`.
Plan (JSON): {"origen": "10.10.20.30", "episodios": [{"id": "...", "comando": ["prog", "arg", ...]}, ...]}
Los comandos remotos de la puerta se ejecutan con prefijos ssh declarados (--ssh-sensor / --ssh-srv), p. ej. "ssh -n -o BatchMode=yes -i K u@h".
Por omisión MODO seco: no llama a nada, solo imprime lo que haría (rc 0). --real ejecuta.
rc: 0 completa; 3 puerta no pasó (se detuvo); 4 un comando de episodio falló (se detuvo); 2 uso.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d5_episodio as d5  # noqa: E402


class SshRunners:
    def __init__(self, ssh_sensor, ssh_srv, remoto="python3 -I ~/cf-b/herramientas/d5_episodio.py", run=subprocess.run):
        self.p = {"sensor": shlex.split(ssh_sensor), "srv": shlex.split(ssh_srv)}
        self.remoto, self.run = remoto, run

    def _go(self, host, sub, **kw):
        args = " ".join("--%s %s" % (k, shlex.quote(str(v))) for k, v in kw.items())
        sudo = "sudo -n " if sub == "srv-agente" else ""     # la traza del agente es de cfagente
        orden = self.p[host] + ["%s%s %s %s" % (sudo, self.remoto, sub, args)]
        r = self.run(orden, capture_output=True, text=True, timeout=120)
        for linea in reversed((r.stdout or "").strip().splitlines()):
            try:
                return json.loads(linea)
            except ValueError:
                continue
        return {"ok": False, "rc": 255, "motivo": "sin JSON de %s (rc=%s)" % (sub, r.returncode)}

    SUB = {"sensor": {"limpiar": "sensor-limpiar --real", "feed": "sensor-feed"},
           "srv": {"nft": "srv-nft", "retirar": "srv-retirar --real", "agente": "srv-agente"}}

    def sensor(self, cmd, **kw):
        return self._go("sensor", self.SUB["sensor"][cmd], **kw)

    def srv(self, cmd, **kw):
        return self._go("srv", self.SUB["srv"][cmd], **kw)


def escribir_rc(fase_dir, rc):
    os.makedirs(os.path.join(fase_dir, "replay"), exist_ok=True)
    with open(os.path.join(fase_dir, "replay", "rc.txt"), "w", encoding="utf-8") as fh:
        fh.write("rc=%d (orquestador de la campaña B; no hubo replay)\n" % rc)


def orquestar(plan, runners, fase_dir, real, auditoria, ahora=time.time, dormir=time.sleep, correr=subprocess.run,
              puerta_kw=None):
    marcas = os.path.join(fase_dir, "marcas-B.jsonl")

    def marca(**d):
        if real:
            os.makedirs(fase_dir, exist_ok=True)
            with open(marcas, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(dict(d, t=ahora()), sort_keys=True) + "\n")
    rc = 0
    hechos = []
    for ep in plan["episodios"]:
        if not real:
            print("SECO: puerta D5 y luego %s -> %s" % (ep["id"], shlex.join(ep["comando"])))
            hechos.append(ep["id"])
            continue
        pu = d5.Puerta(runners, origen=plan.get("origen", d5.ORIGEN), ahora=ahora, dormir=dormir, **(puerta_kw or {}))
        res = pu.preparar_episodio(auditoria=auditoria)
        marca(evento="puerta", episodio_id=ep["id"], lista=res["lista"], intentos=res["intentos"])
        if not res["lista"]:
            rc = 3
            break
        marca(evento="inicio", episodio_id=ep["id"])
        r = correr(ep["comando"], capture_output=True, text=True)
        marca(evento="fin", episodio_id=ep["id"], rc=r.returncode)
        if r.returncode != 0:
            rc = 4
            break
        hechos.append(ep["id"])
    if real:
        escribir_rc(fase_dir, rc)
    return rc, hechos


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", required=True)
    p.add_argument("--fase-dir", default=os.path.expanduser("~/cf-e4/4c"))
    p.add_argument("--auditoria", default=os.path.expanduser("~/cf-b/puertas-D5.jsonl"))
    p.add_argument("--ssh-sensor", default="")
    p.add_argument("--ssh-srv", default="")
    p.add_argument("--real", action="store_true")
    a = p.parse_args(argv)
    plan = json.load(open(a.plan, encoding="utf-8"))
    if a.real and not (a.ssh_sensor and a.ssh_srv):
        print("PARADA: --real exige --ssh-sensor y --ssh-srv")
        return 2
    rc, hechos = orquestar(plan, SshRunners(a.ssh_sensor or "x", a.ssh_srv or "x"), a.fase_dir, a.real, a.auditoria)
    print(json.dumps({"rc": rc, "episodios_hechos": len(hechos), "modo": "real" if a.real else "seco"}))
    return rc


if __name__ == "__main__":
    sys.exit(main())
