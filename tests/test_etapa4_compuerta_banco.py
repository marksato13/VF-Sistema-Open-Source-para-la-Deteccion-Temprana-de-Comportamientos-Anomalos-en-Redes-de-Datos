"""Etapa 4, banco de la compuerta: generar_campana.py (con --permiso) + vigia_4c.py bucle, de extremo a extremo.

Comandos inofensivos (python -c "print('intentos=1')") en lugar de los ataques, tiempos a escala (contexto 0,3 s,
observación 0,2 s) y SSH simulado: el «sensor», «srv-dmz» y la «Kali» los atiende una función que lee y escribe
ficheros locales. Lo que se prueba es la ejecución EFECTIVA: el generador real obedece el permiso que emite el vigía.
  - una pausa impide el siguiente episodio; al reanudar sigue el orden publicado (escenarios-4c.json, semilla 20261102)
  - una cancelación detiene la batería y no se lanza ningún episodio más
  - sin vigía (pérdida del canal) el permiso caduca, se pausa y, pasado el máximo, se cancela solo
  - un permiso de otra corrida (nonce distinto) no autoriza nada
  - sin --permiso el generador hace los 25 episodios en el mismo orden (comportamiento anterior)
El generador vive en el repo de documentación: CAMPANA_DIR o la ruta hermana por omisión.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "etapa4"))
import vigia_4c as vg  # noqa: E402

CAMPANA = Path(os.environ.get("CAMPANA_DIR", RAIZ.parent / "orquestacion-limpio" / "03-entregables"
                              / "13-respuesta-observaciones-validacion-interna" / "seccion4-resultados"
                              / "campana-2026-10-26-deteccion-respuesta"))
GEN = CAMPANA / "scripts" / "generar_campana.py"
ESC = CAMPANA / "etapa4-preparacion-2026-11-02" / "escenarios-4c.json"
pytestmark = pytest.mark.skipif(not GEN.exists() or not ESC.exists(), reason="repo de documentación no disponible")

LANZADOR = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import generar_campana as g
g.esq.validar = lambda cfg, **kw: []                                   # tiempos de banco < mínimos de campaña
g.esq.comando_de = lambda cfg, s: [sys.executable, "-c", "print('intentos=1')"]   # inofensivo
sys.exit(g.main(sys.argv[2:]))
'''


def config_banco(tmp: Path) -> Path:
    cfg = json.loads(ESC.read_text(encoding="utf-8"))
    cfg["tiempos_s"] = {"calentamiento_inicial": 0.2, "contexto_antes": 0.3, "observacion_despues": 0.2}
    for s in cfg["escenarios"]:
        s["timeout_s"] = 10
    p = tmp / "escenarios-banco.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def orden_publicado() -> list[str]:
    sys.path.insert(0, str(GEN.parent))
    import generar_campana as g
    cfg = json.loads(ESC.read_text(encoding="utf-8"))
    return [f"{s['id']}-r{r}" for s, r in g.plan_orden(cfg) if s.get("habilitado")]


def lanzar_generador(tmp: Path, *extra) -> subprocess.Popen:
    (tmp / "lanzador.py").write_text(LANZADOR, encoding="utf-8")
    return subprocess.Popen([sys.executable, str(tmp / "lanzador.py"), str(GEN.parent), "--config",
                             str(config_banco(tmp)), "--salida-dir", str(tmp / "corrida"), "--autorizado", *extra],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)


def marcas(tmp: Path) -> list[dict]:
    p = tmp / "corrida" / "marcas.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


class Lab:
    """Sensor, srv-dmz y Kali simulados. `regla(fines)` decide qué devuelve cada uno según los episodios terminados."""

    def __init__(self, tmp: Path, regla, kali_cae_tras=None):
        self.tmp, self.regla, self.kali_cae_tras = tmp, regla, kali_cae_tras
        self.permiso = tmp / "permiso.json"
        self.arranque_motor = time.time() - 3600

    def fines(self):
        return sum(1 for m in marcas(self.tmp) if m.get("evento") == "fin")

    def __call__(self, cmd, entrada=None, timeout=60):
        t0 = time.time()
        host, orden = cmd[0], cmd[-1]
        r = self.regla(self.fines())
        if orden == "date":
            return 0, f"{time.time()}\n", "", t0, time.time()
        if host == "sensor":
            nr = r.get("nr", 0)
            arr = r.get("arranque", self.arranque_motor)
            u = {"ok": True, "activo": "active", "nrestarts": nr, "arranque_epoch": arr}
            s = {"ok": True, "reloj_epoch": time.time(), "unidades": {k: dict(u) for k in vg.UNIDADES},
                 "tcpdump": {"ok": True, "lecturas": [{"t": time.time() - 1, "pid": 7, "descartados_kernel": 0}]},
                 "anillo": {"ok": True, "salto_max_s": 5.0},
                 "archivador": {"ok": True, "lineas_fallo": 0, "perdidos": 0},
                 "eve": {"ok": True, "cursor": 0, "fuera": []}}
            return 0, json.dumps(s), "", t0, time.time()
        if host == "srvdmz":
            return r.get("srv", 0), "estado=sombra\n", "", t0, time.time()
        if host == "kali":
            if self.kali_cae_tras is not None and self.fines() >= self.kali_cae_tras:
                return 255, "", "ssh: connect to host kali port 22: Connection timed out", t0, time.time()
            tmpf = self.permiso.with_suffix(".tmp")
            tmpf.write_text(entrada, encoding="utf-8")
            # En Windows, sustituir el fichero mientras el generador lo lee da PermissionError (en la Kali, Linux,
            # mv -f es atómico). Se reintenta; si no se puede, el canal «falla» (rc 1) y el permiso no se renueva.
            for _ in range(20):
                try:
                    os.replace(tmpf, self.permiso)
                    break
                except PermissionError:
                    time.sleep(0.01)
            else:
                return 1, "", "no se pudo instalar el permiso", t0, time.time()
            n = int(orden.split()[-1])
            lineas = [json.dumps(m) for m in marcas(self.tmp)][n - 1:]
            return 0, f"{time.time()}\n" + "".join(l + "\n" for l in lineas), "", t0, time.time()
        raise AssertionError(cmd)


def crit_banco():
    c = dict(vg.CRIT)
    # validez 3 s (30 rondas): con 1 s, una ronda lenta por carga de la máquina dejaba caducar el permiso y el
    # generador pausaba por «caducado» (correcto, fallo cerrado), lo que hacía la prueba dependiente de la carga
    c.update(intervalo_s=0.1, validez_s=3.0, reanudar_limpio_s=1.0, historia_motor_s=0.5, cada_srvdmz_s=0.3)
    return c


def args_vigia(tmp: Path, nonce: str, max_dur=60.0):
    return SimpleNamespace(dir=str(tmp / "vigia"), nonce=nonce, planificados=25, ssh_sensor="sensor",
                           orden_sensor="obs", ssh_srvdmz="srvdmz", orden_srvdmz="estado", ssh_kali="kali",
                           orden_kali="permiso {N}", orden_reloj="date", max_duracion=max_dur)


def correr_vigia(tmp, lab, nonce, max_dur=60.0):
    res = {}
    th = threading.Thread(target=lambda: res.setdefault("rc", vg.bucle(args_vigia(tmp, nonce, max_dur), crit_banco(),
                                                                        ejecutar=lab)), daemon=True)
    th.start()
    for _ in range(100):
        if lab.permiso.exists():
            break
        time.sleep(0.05)
    return th, res


def eventos(ms, *tipos):
    return [m for m in ms if m.get("evento") in tipos]


def test_pausa_impide_el_siguiente_y_reanudar_mantiene_el_orden(tmp_path):
    # tras el 3.er episodio el motor «reinicia» (P1): pausa hasta 1 s limpio y 0,5 s de historia del motor
    estado = {}

    def regla(fines):
        if fines >= 3 and "t" not in estado:
            estado["t"] = time.time()
        return {"nr": 1, "arranque": estado["t"]} if "t" in estado else {}
    lab = Lab(tmp_path, regla)
    th, res = correr_vigia(tmp_path, lab, "N-PAUSA")
    g = lanzar_generador(tmp_path, "--permiso", str(lab.permiso), "--nonce", "N-PAUSA", "--permiso-sondeo", "0.05")
    out, _ = g.communicate(timeout=120)
    th.join(timeout=30)
    ms = marcas(tmp_path)
    assert g.returncode == 0, out
    inicios = [m["episodio_id"] for m in eventos(ms, "inicio")]
    assert inicios == orden_publicado()                       # 25, sin repetir ni reordenar
    pausas = eventos(ms, "pausa")
    assert pausas, out
    # la causa P1 dura una ronda; después el permiso sigue en pausa por la regla de reanudación (5 min, a escala)
    rondas = [json.loads(l) for l in (tmp_path / "vigia" / "vigia.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(c.startswith("P1") for r in rondas if r.get("evento") == "ronda" for c in r["permiso"]["causas"])
    # además, al arrancar, el generador rechaza el permiso que el vigía emitió antes de su arranque, y en Windows
    # una lectura que coincide con la sustitución del fichero da «permiso ilegible»: las dos son pausas de fallo
    # cerrado, no permisos concedidos
    transitorios = ("antes del arranque", "permiso ilegible")
    assert all(any(k in p["motivo"] for k in ("P1", "reanudación", "historia del motor") + transitorios)
               for p in pausas), [p["motivo"] for p in pausas]
    pausas = [p for p in pausas if not any(k in p["motivo"] for k in transitorios)]
    assert pausas
    # entre la primera pausa y su reanudación no se lanzó ningún episodio
    i_p = ms.index(pausas[0])
    i_r = next(i for i, m in enumerate(ms) if m.get("evento") == "reanudacion" and i > i_p)
    assert not eventos(ms[i_p:i_r], "inicio")
    # la pausa empezó después del fin del 3.er episodio y el siguiente lanzado es el 4.º del orden
    assert len(eventos(ms[:i_p], "fin")) >= 3
    assert eventos(ms[i_r:], "inicio")[0]["episodio_id"] == orden_publicado()[len(eventos(ms[:i_p], "inicio"))]
    assert res.get("rc") == 0 and (tmp_path / "vigia" / "vigia.jsonl").exists()
    assert "canal de control" in (tmp_path / "vigia" / "accesos-kali.log").read_text(encoding="utf-8")


def test_cancelacion_detiene_la_bateria(tmp_path):
    lab = Lab(tmp_path, lambda fines: {"srv": 1} if fines >= 5 else {})       # X2 tras el 5.º
    th, res = correr_vigia(tmp_path, lab, "N-CANCEL")
    g = lanzar_generador(tmp_path, "--permiso", str(lab.permiso), "--nonce", "N-CANCEL", "--permiso-sondeo", "0.05")
    out, _ = g.communicate(timeout=120)
    th.join(timeout=30)
    ms = marcas(tmp_path)
    assert g.returncode == 3, out
    can = eventos(ms, "cancelacion")
    assert len(can) == 1 and "X2" in can[0]["causa"]
    assert not eventos(ms[ms.index(can[0]):], "inicio")      # nada después de cancelar
    n = len(eventos(ms, "inicio"))
    assert 5 <= n < 25 and [m["episodio_id"] for m in eventos(ms, "inicio")] == orden_publicado()[:n]
    assert eventos(ms, "campana_fin")[0]["estado"] == "cancelada"
    assert res.get("rc") == 3
    assert any(json.loads(l).get("evento") == "reversion_necesaria"
               for l in (tmp_path / "vigia" / "vigia.jsonl").read_text(encoding="utf-8").splitlines())


def test_perdida_del_canal_caduca_pausa_y_cancela_sola(tmp_path):
    lab = Lab(tmp_path, lambda fines: {}, kali_cae_tras=4)
    th, res = correr_vigia(tmp_path, lab, "N-PERDIDA", max_dur=20.0)
    g = lanzar_generador(tmp_path, "--permiso", str(lab.permiso), "--nonce", "N-PERDIDA", "--permiso-sondeo", "0.05",
                         "--permiso-max-espera", "2")
    out, _ = g.communicate(timeout=120)
    ms = marcas(tmp_path)
    assert g.returncode == 3, out
    assert any("caducado" in p["motivo"] for p in eventos(ms, "pausa"))
    assert "sin permiso válido" in eventos(ms, "cancelacion")[0]["causa"]
    assert len(eventos(ms, "inicio")) < 25
    th.join(timeout=30)


def test_permiso_de_otra_corrida_no_autoriza(tmp_path):
    viejo = tmp_path / "permiso.json"
    viejo.write_text(json.dumps({"nonce": "CORRIDA-ANTERIOR", "estado": "continuar", "emitido_epoch": time.time(),
                                 "valido_hasta_epoch": time.time() + 3600}), encoding="utf-8")
    g = lanzar_generador(tmp_path, "--permiso", str(viejo), "--nonce", "N-NUEVA", "--permiso-sondeo", "0.05",
                         "--permiso-max-espera", "1")
    out, _ = g.communicate(timeout=60)
    ms = marcas(tmp_path)
    assert g.returncode == 3 and not eventos(ms, "inicio"), out
    assert "nonce" in eventos(ms, "pausa")[0]["motivo"]


def test_permiso_emitido_antes_del_arranque_no_vale(tmp_path):
    viejo = tmp_path / "permiso.json"
    viejo.write_text(json.dumps({"nonce": "N", "estado": "continuar", "emitido_epoch": time.time() - 600,
                                 "valido_hasta_epoch": time.time() + 3600}), encoding="utf-8")
    g = lanzar_generador(tmp_path, "--permiso", str(viejo), "--nonce", "N", "--permiso-sondeo", "0.05",
                         "--permiso-max-espera", "1")
    out, _ = g.communicate(timeout=60)
    assert g.returncode == 3 and not eventos(marcas(tmp_path), "inicio"), out


def test_sin_permiso_comportamiento_anterior(tmp_path):
    g = lanzar_generador(tmp_path)
    out, _ = g.communicate(timeout=120)
    assert g.returncode == 0, out
    ms = marcas(tmp_path)
    assert [m["episodio_id"] for m in eventos(ms, "inicio")] == orden_publicado()
    assert not eventos(ms, "pausa", "cancelacion")
