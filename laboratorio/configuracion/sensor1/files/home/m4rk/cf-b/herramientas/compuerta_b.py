#!/usr/bin/env python3
"""Compuerta D5 de la Campaña B, sin tocar el generador ni el vigía firmados. Solo biblioteca estándar. Corre en el bastión.

El generador de A lanza los 25 episodios en un proceso y antes de cada uno lee un permiso que escribe el vigía por un canal SSH a la Kali.
Dos modos:
  filtro  --dir D -- <ssh ... kali>   se usa como --ssh-kali del vigía. Recibe el permiso por stdin y la orden como último argumento.
          Si la puerta D5 está pendiente, convierte `continuar` en `pausa`. Lee las marcas que vuelven en la salida:
          `inicio` de un episodio -> puerta pendiente (el permiso queda en pausa durante todo el episodio); `fin` -> episodio terminado.
          Reenvía el permiso y la salida sin más cambios (rc del ssh).
  puerta  --dir D --ssh-sensor S --ssh-srv V   proceso continuo: cuando hay puerta pendiente y no hay episodio en curso, espera
          --espera-fin s (el agente registra sus últimos contadores) y pasa la puerta (d5_episodio.Puerta); si pasa y no ha
          empezado otro episodio mientras tanto, la libera. Si no pasa, el siguiente episodio ESPERA (el permiso sigue en pausa).
Estado compartido: D/gate.json (con bloqueo de fichero). Marcas vistas: D/marcas-vistas.jsonl. Puertas: D/puertas-D5.jsonl.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import fcntl
except ImportError:  # pragma: no cover (Windows: solo para importar)
    fcntl = None

INICIAL = {"pendiente": True, "en_episodio": False, "n_inicios": 0, "episodio": None, "fin_en": None, "liberada_en": None}


class Estado:
    def __init__(self, d):
        self.d = d
        os.makedirs(d, exist_ok=True)
        self.ruta, self.lock = os.path.join(d, "gate.json"), os.path.join(d, "gate.lock")

    def __enter__(self):
        self.fh = open(self.lock, "a")
        if fcntl:
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        try:
            self.st = dict(INICIAL, **json.load(open(self.ruta)))
        except (OSError, ValueError):
            self.st = dict(INICIAL)
        return self.st

    def __exit__(self, *a):
        tmp = self.ruta + ".tmp"
        json.dump(self.st, open(tmp, "w"), sort_keys=True)
        os.replace(tmp, self.ruta)
        self.fh.close()


def filtrar(d, orden, stdin_text, run=subprocess.run, ahora=time.time, por_episodio=False):
    """por_episodio=True: el permiso `continuar` se emite SOLO para el siguiente episodio del orden publicado
    (campo `episodio`); exige el generador con --permiso-por-episodio. Un permiso para el episodio N no vale para N+1."""
    permiso = json.loads(stdin_text)
    with Estado(d) as st:
        t = ahora()
        if permiso.get("estado") == "continuar":
            motivo = None
            if st["pendiente"]:
                motivo = "D5 puerta pendiente (limpieza y comprobaciones previas al episodio)"
            elif por_episodio and not st.get("orden"):
                motivo = "orden de episodios aún desconocida (falta la marca campana_inicio)"
            elif por_episodio and st["n_inicios"] >= len(st["orden"]):
                motivo = "no quedan episodios en el orden"
            if motivo:
                permiso["estado"] = "pausa"
                permiso["causas"] = list(permiso.get("causas") or []) + [motivo]
            elif por_episodio:
                permiso["episodio"] = st["orden"][st["n_inicios"]]
        permiso["compuerta_b"] = {"pendiente": st["pendiente"], "en_episodio": st["en_episodio"], "decidido_en": t,
                                  "n_inicios": st["n_inicios"]}
    r = run(orden, input=json.dumps(permiso, ensure_ascii=False) + "\n", capture_output=True, text=True)
    salida = r.stdout or ""
    vistas = []
    if r.returncode == 0:
        for l in salida.splitlines()[1:]:
            try:
                m = json.loads(l)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("evento") in ("inicio", "fin", "campana_inicio"):
                vistas.append(m)
    if vistas:
        with Estado(d) as st:
            for m in vistas:
                if m["evento"] == "campana_inicio":
                    st["orden"] = list(m.get("orden") or [])
                elif m["evento"] == "inicio":
                    st.update(en_episodio=True, pendiente=True, episodio=m.get("episodio_id"), n_inicios=st["n_inicios"] + 1)
                else:
                    st.update(en_episodio=False, fin_en=ahora())
        with open(os.path.join(d, "marcas-vistas.jsonl"), "a", encoding="utf-8") as fh:
            for m in vistas:
                fh.write(json.dumps(m, sort_keys=True) + "\n")
    return r.returncode, salida, r.stderr or ""


def paso_puerta(d, puerta_fn, ahora=time.time, dormir=time.sleep, espera_fin=15.0):
    """Un turno del proceso de puerta. Devuelve 'nada' | 'liberada' | 'fallida' | 'interrumpida'."""
    with Estado(d) as st:
        if not st["pendiente"] or st["en_episodio"]:
            return "nada"
        n0, fin = st["n_inicios"], st["fin_en"]
    if fin is not None and ahora() < fin + espera_fin:
        dormir(max(0.0, fin + espera_fin - ahora()))
    res = puerta_fn()
    with Estado(d) as st:
        if st["en_episodio"] or st["n_inicios"] != n0:
            return "interrumpida"                # empezó otro episodio mientras la puerta corría: no se libera
        if res["lista"]:
            st.update(pendiente=False, liberada_en=ahora())
            return "liberada"
    return "fallida"


def bucle(d, puerta_fn, sondeo=2.0, ahora=time.time, dormir=time.sleep, max_iter=0, espera_fin=15.0):
    n = 0
    while True:
        r = paso_puerta(d, puerta_fn, ahora, dormir, espera_fin)
        with open(os.path.join(d, "compuerta.log"), "a") as fh:
            if r != "nada":
                fh.write("%.3f %s\n" % (ahora(), r))
        n += 1
        if max_iter and n >= max_iter:
            return r
        dormir(sondeo)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="modo", required=True)
    f = sub.add_parser("filtro")
    f.add_argument("--dir", required=True)
    f.add_argument("--por-episodio", action="store_true", help="permiso ligado al siguiente episodio (generador con --permiso-por-episodio)")
    f.add_argument("orden", nargs=argparse.REMAINDER)
    g = sub.add_parser("puerta")
    g.add_argument("--dir", required=True)
    g.add_argument("--ssh-sensor", required=True)
    g.add_argument("--ssh-srv", required=True)
    g.add_argument("--espera-fin", type=float, default=15.0)
    a = p.parse_args(argv)
    if a.modo == "filtro":
        orden = a.orden[1:] if a.orden and a.orden[0] == "--" else a.orden
        rc, out, err = filtrar(a.dir, orden, sys.stdin.read(), por_episodio=a.por_episodio)
        sys.stdout.write(out)
        sys.stderr.write(err)
        return rc
    import d5_episodio as d5
    import orquestar_b as ob
    runners = ob.SshRunners(a.ssh_sensor, a.ssh_srv)

    def puerta_fn():
        return d5.Puerta(runners).preparar_episodio(auditoria=os.path.join(a.dir, "puertas-D5.jsonl"))
    bucle(a.dir, puerta_fn, espera_fin=a.espera_fin)


if __name__ == "__main__":
    sys.exit(main())
