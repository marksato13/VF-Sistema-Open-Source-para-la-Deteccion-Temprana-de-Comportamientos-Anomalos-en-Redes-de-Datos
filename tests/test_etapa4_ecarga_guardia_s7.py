"""Banco aislado de la corrección de E-carga v2 del 07-nov: puerta y cruce de C1, parada al salir del muestreo y S7.
SIN acceso al laboratorio: los dobles de tests/ecarga_banco/bin sustituyen a ssh, systemctl, sudo, curl, date y sleep.
Reloj simulado: $FAKE_DIR/reloj (date) y salto_sleep (sleep). Nada arranca, para ni consulta un host real.

Igual que en test_etapa4_ecarga_prep.py: las pruebas «regresion» fallan con 975e715 y pasan con esta versión. Con la versión
anterior, C1 es el bloque manual literal del procedimiento publicado en 55f560a.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_etapa4_ecarga_prep import (D, EVAL, H, Lab, _cli, completo, e2e, fuentes, lab, lineas, log_fin, ruta,  # noqa: F401
                                     s7_fuente, s7_trazas, serie)

C1_ANTERIOR = r'''
[ "$(date +%s)" -lt "$TG" ] || { echo "T_g ya pasó: no se arranca" | tee "$X/manual/arranque.rc"; exit 2; }
while [ "$(date +%s)" -lt "$TG" ]; do sleep 0.2; done
date -u +%FT%T.%NZ | tee "$X/manual/arranque.txt"
$CLI 'bash -s arrancar' < $E/generadores.sh 2>&1 | tee -a "$X/manual/arranque.txt"; rc=${PIPESTATUS[0]}
echo "arrancar rc=$rc" | tee "$X/manual/arranque.rc"
if [ $rc != 0 ]; then
  $CLI 'bash -s parar' < $E/generadores.sh; echo "parar rc=$?" | tee -a "$X/manual/arranque.rc"
  echo "E-carga ABORTADA en el arranque: no hay ventana que evaluar" | tee -a "$X/manual/arranque.rc"
fi
'''
T0 = 1794193200          # T_g de la franja: múltiplo de 30, para que el bucle simulado caiga en epochs redondos


def carpeta(lab):
    x = lab.tmp / "X"
    (x / "manual").mkdir(parents=True)
    (x / "bastion").mkdir()
    return x


def muestreo_bg(lab, x, fin_s, parada_s, modo="real", **env):
    e = dict(lab.env, **{k: str(v) for k, v in env.items()})
    ahora = int(time.time())
    return subprocess.Popen(["bash", str(lab.pkg / "muestreo_bastion.sh"), str(x / "bastion"), str(ahora + fin_s),
                             str(ahora + parada_s), modo], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def esperar(cond, max_s=30):
    t = time.time()
    while time.time() - t < max_s:
        if cond():
            return True
        time.sleep(0.05)
    return False


def lee(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def jl(p):
    return [json.loads(x) for x in lee(p).splitlines() if x.strip()]


def guardia_lista(x):
    return esperar(lambda: lee(x / "bastion" / "guardia.jsonl").strip() != "")


def orden_c1(lab, x, t_g, e):
    if (lab.pkg / "arrancar_c1.sh").exists():
        return ["bash", str(lab.pkg / "arrancar_c1.sh"), str(x), str(t_g)], e
    e.update(X=str(x), E=str(lab.pkg), TG=str(t_g), CLI="ssh -o BatchMode=yes -i k adminclientes@10.10.20.20")
    return ["bash", "-c", C1_ANTERIOR], e


def c1(lab, x, t_g=None, **env):
    """Emite C1 como el procedimiento de la versión probada. rc, salida"""
    t_g = int(time.time()) + 1 if t_g is None else t_g
    cmd, e = orden_c1(lab, x, t_g, dict(lab.env, **{k: str(v) for k, v in env.items()}))
    r = subprocess.run(cmd, capture_output=True, text=True, env=e, timeout=120)
    return r.returncode, r.stdout + r.stderr


def resultados(x):
    return [j["resultado"] for j in jl(x / "bastion" / "parada.jsonl")]


# ======================================================================================= H1: parada previa y arranque
def starts(lab):
    return lab.llamadas().count("sudo -n systemctl start cyberflow-lab.target")


def caso_parada_previa(lab):
    x = carpeta(lab)
    lab.marca("memdisp", "500000")
    p = muestreo_bg(lab, x, 7, 6, CF_INTERVALO=1)
    assert esperar(lambda: "confirmada" in resultados(x)), lee(x / "bastion" / "eventos.log")
    rc, out = c1(lab, x)
    vivos_tras_c1 = len(lab.procesos())
    p.wait(timeout=60)
    return dict(c1_rc=rc, vivos_tras_c1=vivos_tras_c1, vivos_al_final=len(lab.procesos()), rc_muestreo=p.returncode,
                ordenes_arrancar=starts(lab), salida=out, x=x)


def test_regresion_c1_no_arranca_con_parada_confirmada_antes_de_tg(lab):
    r = caso_parada_previa(lab)
    assert r["ordenes_arrancar"] == 0 and r["vivos_tras_c1"] == 0 and r["vivos_al_final"] == 0, r
    assert r["c1_rc"] == 2 and r["rc_muestreo"] == 0
    d = jl(r["x"] / "manual" / "c1-puerta.jsonl")[-1]
    assert d["autoriza"] is False and any("PARADA-SOLICITADA" in m for m in d["motivos"]), d
    fin = json.loads(lee(r["x"] / "manual" / "RESULTADO-C1"))
    assert fin["resultado"] == "NO_AUTORIZADO" and "PARADA-SOLICITADA" in fin["motivo"]


def test_regresion_parada_confirmada_no_es_definitiva(lab):
    """Tras una parada confirmada, unos generadores arrancados por cualquier camino vuelven a pararse."""
    x = carpeta(lab)
    lab.marca("memdisp", "500000")
    p = muestreo_bg(lab, x, 7, 6, CF_INTERVALO=1)
    assert esperar(lambda: "confirmada" in resultados(x))
    lab.arrancar_directo()
    p.wait(timeout=60)
    assert lab.parado() and p.returncode == 0, lee(x / "bastion" / "eventos.log")
    assert "reabierta" in resultados(x)


def test_c1_arranque_normal_y_parada_a_su_hora(lab):
    x = carpeta(lab)
    p = muestreo_bg(lab, x, 11, 9, CF_INTERVALO=1)
    assert guardia_lista(x)
    rc, out = c1(lab, x)
    assert rc == 0, out
    assert len(lab.procesos()) == 6 and "arrancar rc=0" in lee(x / "manual" / "arranque.rc")
    d = jl(x / "manual" / "c1-puerta.jsonl")
    assert len(d) == 1 and d[0]["autoriza"] is True and d[0]["muestreador_vivo"] is True
    assert json.loads(lee(x / "manual" / "RESULTADO-C1"))["resultado"] == "ARRANCADO"
    p.wait(timeout=60)
    assert p.returncode == 0 and lab.parado()
    assert json.loads(lee(x / "bastion" / "RESULTADO-PARADA"))["resultado"] == "confirmada"


def test_c1_no_se_repite(lab):
    x = carpeta(lab)
    (x / "manual" / "arranque.rc").write_text("arrancar rc=0\n")
    rc, out = c1(lab, x)
    assert rc == 2 and "no se repite" in out and "systemctl" not in lab.llamadas()


# ------- puerta con un muestreador simulado: las lecturas se escriben a mano para fijar cada caso
class Falso:
    def __init__(self, lab, modo="real", version="2026-11-07.1"):
        self.lab, self.x = lab, carpeta(lab)
        self.o = self.x / "bastion"
        d = lab.tmp / "falso"
        d.mkdir()
        (d / "muestreo_bastion.sh").write_text("sleep 300\n")
        self.p = subprocess.Popen(["bash", str(d / "muestreo_bastion.sh"), str(self.o), "1", "1", modo])
        self.pid = self.p.pid
        (self.o / "muestreo.pid").write_text(
            f"{self.pid} 2026-11-09T02:58:00Z inicio muestreo v{version} modo={modo} fin=1794197880 parada=1794197820 intentos_max=6\n")
        self.lectura()

    def lectura(self, **kw):
        g = {"parar": False, "motivos": [], "avisos": [], "muestras": 3, "t": int(time.time())}
        g.update(kw)
        (self.o / "guardia.jsonl").write_text(json.dumps(g) + "\n")

    def __del__(self):
        self.p.kill()


def c1_denegado(f, fragmento):
    rc, out = c1(f.lab, f.x)
    assert rc == 2, out
    assert "arrancar" not in lee(f.lab.fake / "ssh.log") and "systemctl start" not in f.lab.llamadas(), out
    assert not f.lab.procesos()
    fin = json.loads(lee(f.x / "manual" / "RESULTADO-C1"))
    assert fin["resultado"] == "NO_AUTORIZADO" and fragmento in fin["motivo"], fin
    assert fragmento in lee(f.x / "manual" / "arranque.rc")


@pytest.fixture
def falso(lab):
    ruta("arrancar_c1.sh")
    return Falso(lab)


def test_puerta_control_positivo_con_muestreador_simulado(falso):
    rc, out = c1(falso.lab, falso.x)
    assert rc == 0, out
    assert len(falso.lab.procesos()) == 6


def test_puerta_guardia_sin_lecturas(falso):
    (falso.o / "guardia.jsonl").unlink()
    c1_denegado(falso, "guardia: sin lecturas")


def test_puerta_guardia_fichero_vacio(falso):
    (falso.o / "guardia.jsonl").write_text("\n")
    c1_denegado(falso, "guardia: sin lecturas")


def test_puerta_guardia_ultima_linea_vacia_tras_fallo_de_guardia(falso):
    (falso.o / "guardia.jsonl").write_text(lee(falso.o / "guardia.jsonl") + "\n")
    c1_denegado(falso, "guardia: última lectura inválida")


def test_puerta_guardia_no_json(falso):
    (falso.o / "guardia.jsonl").write_text('{"parar": fal\n')
    c1_denegado(falso, "guardia: última lectura inválida")


@pytest.mark.parametrize("campo", [{"parar": None}, {"parar": "false"}, {"muestras": 0}, {"t": None}, {"avisos": None}])
def test_puerta_guardia_campos_invalidos(falso, campo):
    falso.lectura(**campo)
    c1_denegado(falso, "guardia: última lectura inválida")


def test_puerta_guardia_desactualizada(falso):
    falso.lectura(t=int(time.time()) - 62)
    c1_denegado(falso, "guardia: lectura desactualizada")


def test_puerta_guardia_con_hora_futura(falso):
    falso.lectura(t=int(time.time()) + 120)
    c1_denegado(falso, "guardia: lectura con hora futura")


def test_puerta_guardia_sin_lectura_en_la_ultima_muestra(falso):
    t = int(time.time())
    falso.lectura(t=t, avisos=[f"SIN_LECTURA {t}: recursos"])
    c1_denegado(falso, "guardia: última lectura incompleta")


def test_puerta_sin_lectura_antigua_ya_recuperada_no_impide(falso):
    t = int(time.time())
    falso.lectura(t=t, avisos=[f"SIN_LECTURA {t - 30}: recursos"])
    rc, out = c1(falso.lab, falso.x)
    assert rc == 0, out


def test_puerta_guardia_pidio_parar(falso):
    falso.lectura(parar=True, motivos=["x"])
    c1_denegado(falso, "alguna lectura de la guardia pide parar")


def test_puerta_guardia_pidio_parar_en_una_lectura_anterior(falso):
    g = json.dumps({"parar": True, "motivos": ["x"], "avisos": [], "muestras": 2, "t": int(time.time()) - 30})
    (falso.o / "guardia.jsonl").write_text(g + "\n" + lee(falso.o / "guardia.jsonl"))
    c1_denegado(falso, "alguna lectura de la guardia pide parar")


@pytest.mark.parametrize("fichero", ["PARADA-SOLICITADA", "PARADA-NO-CONFIRMADA", "C1-PARADA-NO-CONFIRMADA", "RESULTADO-PARADA",
                                     "parada.jsonl"])
def test_puerta_solicitud_previa(falso, fichero):
    (falso.o / fichero).write_text("algo\n")
    c1_denegado(falso, fichero)


def test_puerta_muestreador_caido(falso):
    falso.p.kill()
    falso.p.wait()
    c1_denegado(falso, "no está vivo")


def test_puerta_pid_de_otro_proceso(falso):
    p = subprocess.Popen(["sleep", "60"])
    try:
        t = lee(falso.o / "muestreo.pid").replace(str(falso.pid), str(p.pid), 1)
        (falso.o / "muestreo.pid").write_text(t)
        c1_denegado(falso, "no es muestreo_bastion.sh")
    finally:
        p.kill()


def test_puerta_muestreo_pid_ausente(falso):
    (falso.o / "muestreo.pid").unlink()
    c1_denegado(falso, "muestreo.pid ausente")


def test_puerta_muestreador_termino(falso):
    with (falso.o / "muestreo.pid").open("a") as fh:
        fh.write("2026-11-09T04:18:00Z fin muestreo; parada=confirmada intentos=1\n")
    c1_denegado(falso, "ya terminó")


def test_puerta_muestreador_de_la_version_anterior(lab):
    ruta("arrancar_c1.sh")
    c1_denegado(Falso(lab, version="2026-11-06.2"), "versión 2026-11-06.2")


def test_puerta_muestreador_seco(lab):
    ruta("arrancar_c1.sh")
    c1_denegado(Falso(lab, modo="seco"), "modo seco")


def test_c1_tg_ya_paso(falso):
    rc, out = c1(falso.lab, falso.x, t_g=int(time.time()) - 1)
    assert rc == 2 and "T_g ya pasó" in lee(falso.x / "manual" / "RESULTADO-C1")
    assert "arrancar" not in lee(falso.lab.fake / "ssh.log")


def test_c1_cerrojo_ocupado_por_una_parada(falso):
    p = subprocess.Popen(["flock", str(falso.o / "ordenes.lock"), "sleep", "6"])
    time.sleep(0.5)
    try:
        c1_denegado(falso, "cerrojo ocupado")
    finally:
        p.kill()


def test_puerta_rota_no_autoriza(falso):
    (falso.lab.pkg / "puerta_c1.py").write_text("raise SystemExit('rota')\n")
    c1_denegado(falso, "la puerta no dio una respuesta válida")


def test_solicitud_durante_la_espera_de_tg_impide_arrancar(falso):
    p = subprocess.Popen(["bash", str(falso.lab.pkg / "arrancar_c1.sh"), str(falso.x), str(int(time.time()) + 3)],
                         env=falso.lab.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1)
    (falso.o / "PARADA-SOLICITADA").write_text("1 guardia\n")
    out, _ = p.communicate(timeout=30)
    assert p.returncode == 2, out
    assert "arrancar" not in lee(falso.lab.fake / "ssh.log")


# ------- cruce entre arranque y parada
def caso_cruce_lento(lab, retardo=4):
    x = carpeta(lab)
    lab.config(start_retardo=retardo)
    p = muestreo_bg(lab, x, 16, 15, CF_INTERVALO=1)
    assert guardia_lista(x)
    e = dict(lab.env)
    t_g = int(time.time()) + 1
    cmd, e = orden_c1(lab, x, t_g, e)
    a = subprocess.Popen(cmd, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert esperar(lambda: "systemctl start" in lab.llamadas() or "sudo -n systemctl start" in lab.llamadas())
    lab.marca("memdisp", "500000")                       # la guardia pide parar mientras el start sigue sin terminar
    out, _ = a.communicate(timeout=60)
    vivos_tras_c1 = len(lab.procesos())
    p.communicate(timeout=60)
    return dict(c1_rc=a.returncode, vivos_tras_c1=vivos_tras_c1, vivos_al_final=len(lab.procesos()), rc_muestreo=p.returncode,
                ordenes=[l.split(" :: ")[1] for l in lee(lab.fake / "ssh.log").splitlines() if "bash -s parar" in l or "bash -s arrancar" in l],
                salida=out, x=x, parado=lab.parado())


def test_regresion_cruce_arranque_lento_y_parada(lab):
    r = caso_cruce_lento(lab)
    assert r["vivos_al_final"] == 0 and r["parado"], r
    assert r["c1_rc"] == 3 and r["rc_muestreo"] == 0, r
    assert r["vivos_tras_c1"] == 0
    assert r["ordenes"][0].endswith("arrancar") and r["ordenes"][1].endswith("parar"), r["ordenes"]
    assert json.loads(lee(r["x"] / "manual" / "RESULTADO-C1"))["resultado"] == "ABORTADO_PARADO"


def test_regresion_cruce_arranque_parcial(lab):
    x = carpeta(lab)
    lab.config(start="parcial")
    p = muestreo_bg(lab, x, 9, 8, CF_INTERVALO=1)
    assert guardia_lista(x)
    rc, out = c1(lab, x)
    p.communicate(timeout=60)
    assert lab.parado() and not lab.procesos(), out
    assert rc == 3 and "arrancar rc=4" in lee(x / "manual" / "arranque.rc") and p.returncode == 0


def test_cruce_ssh_cortado_y_arranque_remoto_tardio(lab):
    """El peor orden: la orden de parada se confirma ANTES de que el start remoto termine. La vigilancia lo corrige."""
    ruta("arrancar_c1.sh")
    x = carpeta(lab)
    lab.config(start_retardo=3)
    lab.marca("ssh_corta_arrancar", "1")
    p = muestreo_bg(lab, x, 14, 13, CF_INTERVALO=1)
    assert guardia_lista(x)
    rc, out = c1(lab, x)
    assert rc == 3, out                                  # arrancar rc 255, parada confirmada con nada vivo todavía
    assert esperar(lambda: "reabierta" in resultados(x), 25), lee(x / "bastion" / "eventos.log")
    p.communicate(timeout=60)
    assert p.returncode == 0 and lab.parado() and not lab.procesos()
    assert resultados(x).count("confirmada") >= 2


def test_cruce_muestreador_muere_durante_el_arranque(lab):
    ruta("arrancar_c1.sh")
    x = carpeta(lab)
    lab.config(start_retardo=2)
    p = muestreo_bg(lab, x, 30, 29, CF_INTERVALO=1)
    assert guardia_lista(x)
    a = subprocess.Popen(["bash", str(lab.pkg / "arrancar_c1.sh"), str(x), str(int(time.time()) + 1)], env=lab.env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert esperar(lambda: "systemctl start" in lab.llamadas())
    p.kill()
    out, _ = a.communicate(timeout=60)
    assert a.returncode == 3, out
    assert lab.parado() and "muestreador no vivo" in lee(x / "manual" / "RESULTADO-C1")


def test_cruce_parada_no_confirmada_exige_intervencion(lab):
    ruta("arrancar_c1.sh")
    x = carpeta(lab)
    lab.config(start="parcial", stop="sin_efecto")
    p = muestreo_bg(lab, x, 4, 3, CF_INTERVALO=1, CF_MAX_INTENTOS=2)
    assert guardia_lista(x)
    rc, out = c1(lab, x, CF_C1_INTENTOS=2)
    p.communicate(timeout=90)
    assert rc == 4, out
    assert (x / "bastion" / "C1-PARADA-NO-CONFIRMADA").exists() and "INTERVENCIÓN" in lee(x / "manual" / "arranque.rc")
    assert p.returncode == 4 and not lab.parado()
    assert json.loads(lee(x / "bastion" / "RESULTADO-PARADA"))["intervencion_necesaria"] is True


# =================================================================================== H2: parada al salir, reloj simulado
def reloj(lab, modo="real", salto=None, fin=120, parada=60, **env):
    ruta("muestreo_bastion.sh")
    lab.marca("reloj", str(T0))
    if salto:
        lab.marca("salto_sleep", f"{salto[0]} {T0 + salto[1]}")
    e = dict(lab.env, CF_INTERVALO="30", **{k: str(v) for k, v in env.items()})
    o = lab.tmp / "obs"
    r = subprocess.run(["bash", str(lab.pkg / "muestreo_bastion.sh"), str(o), str(T0 + fin), str(T0 + parada), modo],
                       capture_output=True, text=True, env=e, timeout=200)
    fin_l = [l for l in lee(o / "muestreo.pid").splitlines() if "fin muestreo" in l]
    res = jl(o / "RESULTADO-PARADA")
    return dict(rc=r.returncode, ordenes_parar=lee(lab.fake / "ssh.log").count("bash -s parar"),
                estado=fin_l[-1].split("parada=")[1].split()[0] if fin_l else None,
                resultado=res[0] if res else None, parado=lab.parado(), o=o, salida=r.stdout + r.stderr)


def test_h2_parada_normal(lab):
    lab.arrancar_directo()
    r = reloj(lab)
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (0, 1, "confirmada", True), r
    assert r["resultado"]["resultado"] == "confirmada" and r["resultado"]["comprobacion_final_rc"] == 0


def test_regresion_h2_salto_de_reloj_antes_de_parada_hasta_despues_de_fin(lab):
    lab.arrancar_directo()
    r = reloj(lab, salto=(1, 125))
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (0, 1, "confirmada", True), r
    assert "PARADA pendiente al salir del bucle" in lee(r["o"] / "eventos.log")
    assert r["resultado"]["intervencion_necesaria"] is False


def test_h2_parada_ya_confirmada_no_repite(lab):
    lab.arrancar_directo()
    lab.marca("memdisp", "500000")
    r = reloj(lab)
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (0, 1, "confirmada", True), r
    assert "comprobar-parado" in lee(lab.fake / "ssh.log")


def test_regresion_h2_salto_con_fallo_transitorio_que_se_recupera(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_parar", "1")
    r = reloj(lab, salto=(1, 125))
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (0, 2, "confirmada", True), r
    assert [j["resultado"] for j in jl(r["o"] / "parada.jsonl") if j["resultado"] not in ("solicitada", "comprobacion_final")] \
        == ["fallida", "confirmada"]


def test_regresion_h2_salto_con_intentos_agotados(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_parar", "99")
    r = reloj(lab, salto=(1, 125), CF_MAX_INTENTOS=3)
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (4, 3, "agotada", False), r
    assert (r["o"] / "PARADA-NO-CONFIRMADA").exists()
    assert r["resultado"]["resultado"] == "agotada" and r["resultado"]["intervencion_necesaria"] is True and r["resultado"]["rc"] == 4
    assert "muestras.txt" in os.listdir(r["o"]) and "eventos.log" in os.listdir(r["o"])


def test_h2_seco_con_salto_no_envia_ordenes(lab):
    lab.arrancar_directo()
    r = reloj(lab, modo="seco", salto=(1, 125))
    assert (r["rc"], r["ordenes_parar"], r["estado"]) == (0, 0, "ninguna"), r
    assert "bash -s parar" not in lee(lab.fake / "ssh.log") and "comprobar-parado" not in lee(lab.fake / "ssh.log")
    assert r["resultado"]["resultado"] == "seco_sin_orden" and len(lab.procesos()) == 6


def test_h2_comprobacion_final_fallida_reabre_y_se_recupera(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_comprobar", "1")
    r = reloj(lab)
    assert (r["rc"], r["ordenes_parar"], r["estado"]) == (0, 2, "confirmada"), r
    assert "reabierta" in [j["resultado"] for j in jl(r["o"] / "parada.jsonl")]


def test_h2_comprobacion_final_nunca_confirma_es_acotada(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_comprobar", "99")
    r = reloj(lab, CF_MAX_INTENTOS=3)
    assert (r["rc"], r["ordenes_parar"], r["estado"]) == (4, 3, "agotada"), r
    assert r["resultado"]["intervencion_necesaria"] is True


def test_h2_bucle_sin_ninguna_vuelta(lab):
    lab.arrancar_directo()
    r = reloj(lab, fin=-10, parada=-20)
    assert (r["rc"], r["ordenes_parar"], r["estado"], r["parado"]) == (0, 1, "confirmada", True), r


def test_h2_parada_posterior_a_fin_no_se_acepta(lab):
    lab.arrancar_directo()
    r = reloj(lab, fin=60, parada=120)
    assert r["rc"] == 2 and r["ordenes_parar"] == 0 and "PARADA_EPOCH <= FIN_EPOCH" in r["salida"]


def test_h2_senal_deja_resultado_interrumpido(lab):
    x = carpeta(lab)
    p = muestreo_bg(lab, x, 60, 59, CF_INTERVALO=1)
    assert guardia_lista(x)
    p.send_signal(signal.SIGTERM)
    p.communicate(timeout=30)
    assert p.returncode == 143
    r = json.loads(lee(x / "bastion" / "RESULTADO-PARADA"))
    assert r["resultado"] == "interrumpido" and r["intervencion_necesaria"] is True


def test_h2_resultado_se_escribe_tambien_en_segundo_plano(lab):
    """Sin stdout ni terminal, el operador lee RESULTADO-PARADA."""
    x = carpeta(lab)
    lab.arrancar_directo()
    e = dict(lab.env)
    ahora = int(time.time())
    subprocess.Popen(["setsid", "nohup", "bash", str(lab.pkg / "muestreo_bastion.sh"), str(x / "bastion"), str(ahora + 2),
                      str(ahora + 1), "real"], env=e, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert esperar(lambda: (x / "bastion" / "RESULTADO-PARADA").exists(), 40)
    assert json.loads(lee(x / "bastion" / "RESULTADO-PARADA"))["resultado"] == "confirmada"
    assert not (x / "bastion" / ".RESULTADO-PARADA.tmp").exists()


# ================================================================== recorrido completo con los epoch de la franja
def test_recorrido_completo_con_reloj_simulado(lab):
    """B4 -> C1 en T_g -> ventana -> parada a su hora -> fin -> D4/D5 -> veredicto, con los epoch publicados (r4 §3.2) y
    15 s simulados por cada segundo real. Con dobles: no demuestra nada sobre los hosts."""
    ruta("arrancar_c1.sh")
    T_G, PARADA, FIN, B4 = 1794193200, 1794197820, 1794197880, 1794193200 - 130
    velocidad = 15.0
    lab.unidad("ppi-relay-eventos.service", LoadState="loaded", ActiveState="active", SubState="running", MainPID="1200", NRestarts="0")
    lab.marca("reloj", str(B4))
    lab.marca("reloj_externo")
    alto = threading.Event()

    def relojero():
        t0 = time.monotonic()
        while not alto.is_set():
            q = lab.fake / "reloj.tmp"
            q.write_text(f"{B4 + (time.monotonic() - t0) * velocidad:.3f}\n")
            q.replace(lab.fake / "reloj")
            time.sleep(0.02)

    h = threading.Thread(target=relojero, daemon=True)
    h.start()
    x = carpeta(lab)
    o = x / "bastion"
    e = dict(lab.env, CF_INTERVALO="30", CF_ESPERA="1", CF_ESPERA_MAX="20", CF_ESTABLE="5", CF_T_ARRANQUE="60", CF_T_PARADA="60")
    try:
        p = subprocess.Popen(["bash", str(lab.pkg / "muestreo_bastion.sh"), str(o), str(FIN), str(PARADA), "real"], env=e,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert guardia_lista(x)
        rc, out = c1(lab, x, t_g=T_G, **{k: e[k] for k in ("CF_ESPERA", "CF_ESPERA_MAX", "CF_ESTABLE", "CF_T_ARRANQUE", "CF_T_PARADA")})
        assert rc == 0, out
        assert len(lab.procesos()) == 6
        fin_out, _ = p.communicate(timeout=480)
    finally:
        alto.set()
        h.join()
    assert p.returncode == 0, fin_out
    assert starts(lab) == 1 and lab.parado()
    ini = lee(x / "manual" / "arranque.txt").splitlines()[0]
    assert ini.startswith("2026-11-09T03:00:0"), ini                     # 03:00:00Z = T_g, la orden no se adelanta
    conf = [j for j in jl(o / "parada.jsonl") if j["resultado"] == "confirmada"]
    assert len(conf) == 1 and PARADA <= conf[0]["t"] <= FIN + 60, conf
    assert "fin previsto" in conf[0]["motivo"]
    assert json.loads(lee(o / "RESULTADO-PARADA"))["resultado"] == "confirmada"

    # D4 y D5 sobre las muestras de este recorrido; el resto de fuentes es sintético, como en test_etapa4_ecarga_prep.py
    ag, re_, _ = s7_trazas()
    (lab.home / "relay-v2").mkdir()
    (lab.home / "relay-v2" / "traza.jsonl").write_text(re_)
    lab.marca("traza_agente", ag)
    d4 = subprocess.run(["bash", str(lab.pkg / "s7_post.sh"), str(o), str(x / "manual" / "s7"), str(int(D)), str(int(H))],
                        capture_output=True, text=True, env=dict(lab.env))
    assert d4.returncode == 0, d4.stdout + d4.stderr
    s = lab.tmp / "fuentes"
    args = fuentes(s, lineas(serie(D - 3, H + 20)), completo(), pcap_log=s / "obs_pcap.log")
    rc, out, err = _cli(ruta("derivar_bastion.py"), o / "muestras.txt", D, H)
    assert rc == 0, err
    (s / "bas.json").write_text(out)
    args[args.index("--s7") + 1] = x / "manual" / "s7" / "s7.json"
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert rc == 0, err
    rc, out, err = _cli(EVAL, "veredicto", "--entrada", s / "entrada.json")
    r = json.loads(out)
    assert json.loads(lee(x / "manual" / "s7" / "s7.json"))["S7"]["valor"] is True, lee(x / "manual" / "s7" / "s7.json")
    e_ = json.loads(lee(s / "entrada.json"))
    assert all(e_["S"][k] is True for k in ("S1", "S6", "S7", "S8", "S9", "S10")), e_["S"]
    assert r["habilita_condicion_3"] is True and rc == 0, r


# ======================================================================================================= H3: S7
def s7(tmp, **kw):
    ruta("derivar_s7.py")
    return s7_fuente(tmp, **kw)


def test_s7_caso_original_entrega_aceptada_sin_feed_seq(tmp_path):
    r = s7(tmp_path, entregas=[100, 101], feed=lambda i: "ERROR")
    assert r["S7"]["valor"] is None and "feed_seq" in r["S7"]["motivo"], r
    assert r["comprobaciones"]["entregas_aceptadas"]["valor"] is True


def test_s7_lista_vacia_de_lecturas_del_publicador(tmp_path):
    ag, re_, _ = s7_trazas(entregas=[100, 101])
    mu = "".join(f"### x {D - 60 + 30 * i:.0f}\nS home_libre_kb=1\n" for i in range(125))
    for n, c in (("a", ag), ("r", re_), ("m", mu)):
        (tmp_path / n).write_text(c)
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "a", tmp_path / "r", tmp_path / "m", D, H)
    r = json.loads(out)
    assert r["S7"]["valor"] is None and "ninguna lectura feed_seq" in r["S7"]["motivo"], r


def test_s7_una_sola_lectura(tmp_path):
    r = s7(tmp_path, feed_fijo=[(D + 100, "700")])
    assert r["S7"]["valor"] is None and "una sola lectura" in r["S7"]["motivo"], r


def test_s7_lectura_fallida_en_medio(tmp_path):
    r = s7(tmp_path, feed=lambda i: "ERROR" if i == 40 else str(500 + i))
    assert r["S7"]["valor"] is None and "fallidas" in r["S7"]["motivo"], r


def test_s7_lectura_fallida_sin_linea(tmp_path):
    ag, re_, mu = s7_trazas()
    b = mu.split("### ")
    b[50] = b[50].replace("S feed_seq=", "S ERROR ssh_rc=255 ")
    (tmp_path / "a").write_text(ag); (tmp_path / "r").write_text(re_); (tmp_path / "m").write_text("### ".join(b))
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "a", tmp_path / "r", tmp_path / "m", D, H)
    assert json.loads(out)["S7"]["valor"] is None


def test_s7_secuencia_valida(tmp_path):
    r = s7(tmp_path)
    assert r["S7"] == {"valor": True, "motivo": None}, r
    assert all(c["valor"] is True for c in r["comprobaciones"].values())


def test_s7_secuencia_constante_no_es_retroceso(tmp_path):
    assert s7(tmp_path, feed=lambda i: "700")["S7"]["valor"] is True


def test_s7_retroceso_es_false(tmp_path):
    r = s7(tmp_path, feed=lambda i: str(500 + i - (10 if i >= 60 else 0)))
    assert r["S7"]["valor"] is False and "retroceso" in r["S7"]["motivo"], r


def test_s7_retroceso_prevalece_sobre_lectura_fallida(tmp_path):
    r = s7(tmp_path, feed=lambda i: "ERROR" if i == 5 else str(500 + i - (10 if i >= 60 else 0)))
    assert r["S7"]["valor"] is False and "fallidas" not in r["S7"]["motivo"], r


def test_s7_entregada_sin_aceptar_es_false(tmp_path):
    r = s7(tmp_path, entregas=[100, 101, 102], aceptar=[100, 102])
    assert r["S7"]["valor"] is False and "sin aceptar" in r["S7"]["motivo"], r


def test_s7_aceptadas_fuera_de_orden_es_false(tmp_path):
    r = s7(tmp_path, entregas=[100, 101, 102], aceptar=[100, 102, 101])
    assert r["S7"]["valor"] is False and "fuera de orden" in r["S7"]["motivo"], r


def test_s7_sin_entregas_es_null(tmp_path):
    ag, re_, mu = s7_trazas(d=D - 7200, a=D - 3600)         # hay trazas, pero de otra hora
    _, _, mu = s7_trazas()
    (tmp_path / "a").write_text(ag); (tmp_path / "r").write_text(re_); (tmp_path / "m").write_text(mu)
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "a", tmp_path / "r", tmp_path / "m", D, H)
    r = json.loads(out)
    assert r["S7"]["valor"] is None and "ninguna entrega" in r["S7"]["motivo"], r


def test_s7_una_aceptada_no_permite_comparar_orden(tmp_path):
    r = s7(tmp_path, entregas=[100])
    assert r["S7"]["valor"] is None and "no hay orden que comparar" in r["S7"]["motivo"], r


def test_s7_hueco_de_lecturas_sin_cobertura(tmp_path):
    f = [(t, str(i)) for i, t in enumerate(x for x in serie(D - 30, H + 30, (30,)) if not D + 1000 < x < D + 1200)]
    r = s7(tmp_path, feed_fijo=f)
    assert r["S7"]["valor"] is None and "cobertura" in r["S7"]["motivo"], r


def test_s7_lecturas_fuera_de_la_ventana_no_cuentan(tmp_path):
    f = [(D - 5000 + 30 * i, str(i)) for i in range(50)]
    r = s7(tmp_path, feed_fijo=f)
    assert r["S7"]["valor"] is None and "ninguna lectura" in r["S7"]["motivo"], r


def test_s7_traza_del_agente_no_legible_con_rc(tmp_path):
    ag, re_, mu = s7_trazas()
    (tmp_path / "r").write_text(re_); (tmp_path / "m").write_text(mu); (tmp_path / "a").write_text("")
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "a", tmp_path / "r", tmp_path / "m", D, H, "--rc-agente", 255)
    r = json.loads(out)
    assert r["S7"]["valor"] is None and "rc 255" in r["S7"]["motivo"], r


@pytest.mark.parametrize("cual", ["agente", "rele"])
def test_s7_traza_vacia_o_ilegible(tmp_path, cual):
    ag, re_, mu = s7_trazas()
    (tmp_path / "m").write_text(mu)
    for n, c in (("agente", ag), ("rele", re_)):
        (tmp_path / n).write_text("" if n == cual else c)
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "agente", tmp_path / "rele", tmp_path / "m", D, H)
    assert json.loads(out)["S7"]["valor"] is None
    (tmp_path / cual).write_text('{"evento": ')
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "agente", tmp_path / "rele", tmp_path / "m", D, H)
    assert json.loads(out)["S7"]["valor"] is None


def test_s7_fichero_inexistente_no_rompe(tmp_path):
    rc, out, err = _cli(ruta("derivar_s7.py"), tmp_path / "no", tmp_path / "no", tmp_path / "no", D, H)
    assert rc == 0 and json.loads(out)["S7"]["valor"] is None


def test_s7_datos_reales_del_06_nov_coinciden_con_obs_post_p4():
    o = os.environ.get("OBS06")
    if not o:
        pytest.skip("sin OBS06")
    b = Path(o) / "bastion"
    rc, out, err = _cli(ruta("derivar_s7.py"), b / "traza-agente-copia.jsonl", b / "traza-rele-copia-sin-nul.jsonl", b / "muestras.txt",
                        1793940600, 1793944200)
    r = json.loads(out)
    c = r["comprobaciones"]
    assert c["entregas_aceptadas"]["entregas"] == 180 and c["entregas_aceptadas"]["secuencia_ini_fin"] == [4527, 4706]
    assert c["entregas_aceptadas"]["no_aceptadas"] == 0 and c["aceptadas_en_orden"]["aceptadas"] == 180
    assert c["publicador_sin_retroceso"]["secuencia_ini_fin"] == [4524, 4709]
    assert r["S7"]["valor"] is True, r


def test_s7_post_copia_trazas_y_falla_a_null(lab):
    ruta("s7_post.sh")
    ag, re_, mu = s7_trazas()
    (lab.home / "relay-v2").mkdir()
    (lab.home / "relay-v2" / "traza.jsonl").write_text("\0" + re_)
    o = lab.tmp / "obs"
    o.mkdir()
    (o / "muestras.txt").write_text(mu)
    lab.marca("traza_agente", ag)
    r = subprocess.run(["bash", str(lab.pkg / "s7_post.sh"), str(o), str(lab.tmp / "s1"), str(int(D)), str(int(H))],
                       capture_output=True, text=True, env=lab.env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(lee(lab.tmp / "s1" / "s7.json"))["S7"]["valor"] is True
    lab.marca("traza_agente_falla")
    r = subprocess.run(["bash", str(lab.pkg / "s7_post.sh"), str(o), str(lab.tmp / "s2"), str(int(D)), str(int(H))],
                       capture_output=True, text=True, env=lab.env)
    d = json.loads(lee(lab.tmp / "s2" / "s7.json"))
    assert r.returncode == 0 and d["S7"]["valor"] is None and "rc 255" in d["S7"]["motivo"]
    r = subprocess.run(["bash", str(lab.pkg / "s7_post.sh"), str(o), str(lab.tmp / "s2"), str(int(D)), str(int(H))],
                       capture_output=True, text=True, env=lab.env)
    assert r.returncode == 2 and "ya existe" in r.stdout


# ------- de punta a punta
def e2e_s7(tmp, **s7kw):
    return e2e(tmp, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp / "obs_pcap.log", s7=s7kw)


def test_e2e_s7_ausencia_de_evidencia_no_habilita_condicion_3(tmp_path):
    ruta("derivar_s7.py")
    rc, r, e, t = e2e_s7(tmp_path, entregas=[100, 101], feed=lambda i: "ERROR")
    assert e["S"]["S7"] is None and t["campos"]["S.S7"]["fuente"] == "s7" and "feed_seq" in t["campos"]["S.S7"]["motivo_fuente"]
    assert r["habilita_condicion_3"] is False and r["estabilidad_tecnica"] == "no demostrable" and rc == 1, r


@pytest.mark.parametrize("kw,esperado,habilita,estab", [
    ({}, True, True, "estable con carga suficiente"),
    ({"feed": lambda i: str(500 + i - (10 if i >= 60 else 0))}, False, False, "no estable"),
    ({"feed_fijo": [(D + 100, "700")]}, None, False, "no demostrable"),
], ids=["true", "false", "null"])
def test_e2e_s7_mismo_valor_de_la_fuente_a_la_entrada(tmp_path, kw, esperado, habilita, estab):
    ruta("derivar_s7.py")
    rc, r, e, t = e2e_s7(tmp_path, **kw)
    fuente = json.loads(lee(tmp_path / "s7.json"))["S7"]["valor"]
    assert fuente is esperado and e["S"]["S7"] is esperado and t["campos"]["S.S7"]["valor"] is esperado
    assert t["fuentes"]["s7"]["estado"] == "leída" and len(t["fuentes"]["s7"]["sha256"]) == 64
    assert r["habilita_condicion_3"] is habilita and r["estabilidad_tecnica"] == estab, r


def test_e2e_s7_de_otro_periodo_o_version_queda_null(tmp_path):
    ruta("derivar_s7.py")
    args = fuentes(tmp_path, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    d = json.loads(lee(tmp_path / "s7.json"))
    assert d["S7"]["valor"] is True
    d["periodo"] = [D + 1, H + 1]
    (tmp_path / "s7.json").write_text(json.dumps(d))
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert json.loads(lee(tmp_path / "entrada.json"))["S"]["S7"] is None
    assert any("s7: otro periodo" in a for a in json.loads(lee(tmp_path / "traza.json"))["avisos"])


def test_e2e_sin_fichero_s7_queda_null(tmp_path):
    ruta("derivar_s7.py")
    args = fuentes(tmp_path, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    i = args.index("--s7")
    del args[i:i + 2]
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert json.loads(lee(tmp_path / "entrada.json"))["S"]["S7"] is None


def test_regresion_manual_s7_ya_no_se_admite(tmp_path):
    args = fuentes(tmp_path, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    i = args.index("--salida-entrada")
    ev = tmp_path / "ev.txt"
    if "--s7" in map(str, args):
        args[i:i] = ["--manual", f"S7=true:{ev}"]
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert rc == 2 and "--manual solo admite" in err, (rc, err)
