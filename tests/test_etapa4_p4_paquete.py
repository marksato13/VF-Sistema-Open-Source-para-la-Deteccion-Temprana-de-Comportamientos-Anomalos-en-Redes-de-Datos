"""P4 del cierre complementario 4A: coherencia feed + firma en la entrega relé -> agente (2026-11-06).

Hipótesis a probar: el rechazo ``firma_invalida`` de srv-dmz (06:26:26,990 del 04-nov y otros 12) ocurre cuando el
agente lee entre los dos ``mv`` del relé (firma nueva, feed anterior). Aquí se reproduce de forma DETERMINISTA con el
código real (relé TransporteLocal + agente) y se comprueba que la entrega por paquete lo elimina sin debilitar nada:
la firma se sigue verificando, un paquete dañado nunca se acepta y las secuencias antiguas se siguen rechazando.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(RAIZ / "scripts" / "enforce"))
sys.path.insert(0, str(RAIZ / "deploy" / "enforcement"))

import feed  # noqa: E402
import agente_enforce_v2 as ag  # noqa: E402
import relay_eventos as rele  # noqa: E402

HAY_OPENSSL = shutil.which("openssl") is not None
T0 = 1_800_000_000.0


class HelperSombra:
    """Sombra: solo 'listar'. Cualquier otra llamada es un fallo de la prueba."""
    def listar(self):
        return {"sets": {"bloqueados": {}, "limitados": {}}}

    def __call__(self, ops):
        raise AssertionError("en sombra no se llama al helper para cambiar nada")


@pytest.fixture
def claves(tmp_path):
    if not HAY_OPENSSL:
        pytest.skip("sin openssl")
    priv, pub = tmp_path / "priv.pem", tmp_path / "pub.pem"
    feed.generar_claves(str(priv), str(pub))
    return priv, pub


def generacion(priv, seq, ahora=T0):
    datos = feed.serializar(feed.construir_v2([], seq, ahora, 600))
    return datos, feed.firmar(datos, str(priv))


def publicar_origen(d: Path, datos: bytes, firma: bytes) -> None:
    """Como publicar_feed_v2.publicar: firma y feed, cada uno por rename."""
    for nombre, b in (("feed.sig", firma), ("feed.json", datos)):
        tmp = d / (".%s.tmp" % nombre)
        tmp.write_bytes(b)
        os.replace(tmp, d / nombre)


def agente(tmp_path, pub, **kw):
    a = argparse.Namespace(perfil="dmz", clave_publica=pub, estado=tmp_path / "estado.json",
                           traza=tmp_path / "traza.jsonl", helper="x", aplicar=False, **kw)
    return ag.Agente(a, helper=HelperSombra(), reloj=lambda: T0 + 1)


def eventos(tmp_path):
    return [json.loads(l) for l in (tmp_path / "traza.jsonl").read_text().splitlines()]


def montar(tmp_path, pub, entrega, transporte=None):
    o, d = tmp_path / "origen", tmp_path / "destino"
    o.mkdir(); d.mkdir()
    r = rele.Rele({"dir": str(o), "host": None, "identidad": None}, [{"nombre": "srv-dmz", "dir": str(d)}],
                  transporte or rele.TransporteLocal(), tmp_path / "rele.jsonl", rele.verificador(str(pub)),
                  reloj=lambda: T0 + 1, entrega=entrega)
    return o, d, r


class TransporteConPausa(rele.TransporteLocal):
    """Ejecuta ``entre`` en mitad de la confirmación: tras el PRIMER mv de la pareja, o antes del único mv del
    paquete (el punto más tardío en que un lector puede intercalarse)."""
    def __init__(self, entre):
        self.entre = entre

    def confirmar(self, destino):
        d = Path(destino["dir"])
        shutil.move(str(d / ".feed.sig.tmp"), str(d / "feed.sig"))
        self.entre()
        shutil.move(str(d / ".feed.json.tmp"), str(d / "feed.json"))
        return None

    def confirmar_paquete(self, destino):
        self.entre()
        return super().confirmar_paquete(destino)


# ----------------------------------------------------------------------------------- reproducción (causa probada)

def test_reproduce_firma_invalida_entre_los_dos_mv(tmp_path, claves):
    priv, pub = claves
    vistos = []
    a = agente(tmp_path, pub, paquete=None, feed=tmp_path / "destino" / "feed.json",
               firma=tmp_path / "destino" / "feed.sig")

    def lector_intercalado():
        try:
            _, datos, firma = ag.leer_generacion(a.a)
        except OSError:                           # primera entrega: aún no hay feed.json
            vistos.append("sin_feed")
            return
        vistos.append(a.procesar(datos, firma))

    o, d, r = montar(tmp_path, pub, "pareja", TransporteConPausa(lector_intercalado))
    publicar_origen(o, *generacion(priv, 764))
    r.paso()
    assert vistos == ["sin_feed"]
    _, datos, firma = ag.leer_generacion(a.a)
    assert a.procesar(datos, firma)["estado"] == "aceptado"   # 764 completa
    publicar_origen(o, *generacion(priv, 765))
    vistos.clear()
    r.paso()                                      # entrega de 765: el lector cae entre los dos mv
    assert vistos == [{"estado": "rechazado", "motivo": "firma_invalida"}]
    _, datos, firma = ag.leer_generacion(a.a)     # siguiente sondeo del agente (0,5 s en el laboratorio)
    assert a.procesar(datos, firma)["estado"] == "aceptado"
    assert json.loads(datos)["secuencia"] == 765  # la MISMA secuencia, aceptada después: como en srv-dmz


@pytest.mark.parametrize("seq_inicial", [1, 764])
def test_paquete_lector_intercalado_ve_siempre_una_generacion_completa(tmp_path, claves, seq_inicial):
    priv, pub = claves
    vistos = []
    a = agente(tmp_path, pub, paquete=tmp_path / "destino" / "feed.par", feed=None, firma=None)

    def lector_intercalado():
        try:
            _, datos, firma = ag.leer_generacion(a.a)
        except OSError:
            vistos.append("sin_paquete")
            return
        vistos.append((a.procesar(datos, firma)["estado"], json.loads(datos)["secuencia"]))

    o, d, r = montar(tmp_path, pub, "paquete", TransporteConPausa(lector_intercalado))
    for s in range(seq_inicial, seq_inicial + 4):
        publicar_origen(o, *generacion(priv, s))
        r.paso()
    assert vistos[0] == "sin_paquete"             # antes de la primera entrega no hay nada que leer
    # justo antes del único mv, el lector ve la generación ANTERIOR completa (verifica y se acepta)
    assert vistos[1:] == [("aceptado", s) for s in range(seq_inicial, seq_inicial + 3)]
    assert not any(e.get("motivo") == "firma_invalida" for e in eventos(tmp_path))
    _, datos, firma = ag.leer_generacion(a.a)
    assert json.loads(datos)["secuencia"] == seq_inicial + 3


# ----------------------------------------------------------------------------------- contrato del paquete

def test_paquete_ida_y_vuelta_y_daños():
    p = feed.empaquetar(b'{"a":1}', b"FIRMA")
    assert feed.desempaquetar(p) == (b'{"a":1}', b"FIRMA")
    o = json.loads(p)
    casos = {
        "paquete_no_json": p[: len(p) // 2],                       # incompleto (corte a mitad)
        "paquete_formato": json.dumps(dict(o, formato="otro/1")).encode(),
        "paquete_base64": json.dumps(dict(o, feed_b64="@@@")).encode(),
        "paquete_huella": json.dumps(dict(o, sha256_firma="0" * 64)).encode(),
    }
    for motivo, malo in casos.items():
        with pytest.raises(ValueError, match=motivo):
            feed.desempaquetar(malo)
    with pytest.raises(ValueError):
        feed.desempaquetar(b"")


def test_firma_incorrecta_en_paquete_integro_se_rechaza(tmp_path, claves):
    priv, pub = claves
    otra_priv = tmp_path / "otra.pem"
    feed.generar_claves(str(otra_priv), str(tmp_path / "otra.pub"))
    datos, _ = generacion(priv, 5)
    firma_ajena = feed.firmar(datos, str(otra_priv))
    a = agente(tmp_path, pub, paquete=None, feed=None, firma=None)
    assert a.procesar(*feed.desempaquetar(feed.empaquetar(datos, firma_ajena))) == \
        {"estado": "rechazado", "motivo": "firma_invalida"}
    assert a.estado["secuencia"] is None          # nada avanzó


def test_secuencia_anterior_y_duplicados(tmp_path, claves):
    priv, pub = claves
    a = agente(tmp_path, pub, paquete=None, feed=None, firma=None)
    assert a.procesar(*generacion(priv, 10))["estado"] == "aceptado"
    assert a.procesar(*generacion(priv, 10))["estado"] == "repetido"
    assert a.procesar(*generacion(priv, 9))["estado"] == "rechazado"
    a2 = agente(tmp_path, pub, paquete=None, feed=None, firma=None)   # reinicio del agente: estado persistido
    assert a2.procesar(*generacion(priv, 10))["estado"] == "repetido"
    assert a2.procesar(*generacion(priv, 9))["estado"] == "rechazado"


# ----------------------------------------------------------------------------------- interrupciones y reintentos

class TransporteQueFalla(rele.TransporteLocal):
    def __init__(self):
        self.fallar_subida = self.fallar_confirmacion = self.subida_parcial = False

    def subir(self, destino, nombre, datos):
        if self.fallar_subida:
            return "red"
        if self.subida_parcial:              # el ssh se corta tras escribir la mitad
            (Path(destino["dir"]) / (".%s.tmp" % nombre)).write_bytes(datos[: len(datos) // 2])
            return "cortado"
        return super().subir(destino, nombre, datos)

    def confirmar_paquete(self, destino):
        return "red" if self.fallar_confirmacion else super().confirmar_paquete(destino)


def test_interrupciones_dejan_la_generacion_anterior_y_se_reintenta(tmp_path, claves):
    priv, pub = claves
    t = TransporteQueFalla()
    o, d, r = montar(tmp_path, pub, "paquete", t)
    publicar_origen(o, *generacion(priv, 1))
    assert "entregado_en" in r.paso()["destinos"]["srv-dmz"]
    antes = (d / "feed.par").read_bytes()
    publicar_origen(o, *generacion(priv, 2))
    for modo in ("fallar_subida", "subida_parcial", "fallar_confirmacion"):
        setattr(t, modo, True)
        assert "error" in r.paso()["destinos"]["srv-dmz"]
        setattr(t, modo, False)
        assert (d / "feed.par").read_bytes() == antes          # el destino sigue con la generación 1 íntegra
        assert feed.desempaquetar(antes)
    assert "entregado_en" in r.paso()["destinos"]["srv-dmz"]  # reintento sin nueva publicación
    assert json.loads(feed.desempaquetar((d / "feed.par").read_bytes())[0])["secuencia"] == 2
    assert r.paso() is None                                     # sin cambios: no se reenvía


def test_reinicio_del_rele_reenvia_y_el_agente_lo_ve_repetido(tmp_path, claves):
    priv, pub = claves
    o, d, r = montar(tmp_path, pub, "paquete")
    publicar_origen(o, *generacion(priv, 3))
    r.paso()
    a = agente(tmp_path, pub, paquete=d / "feed.par", feed=None, firma=None)
    _, datos, firma = ag.leer_generacion(a.a)
    assert a.procesar(datos, firma)["estado"] == "aceptado"
    r2 = rele.Rele(r.origen, r.destinos, rele.TransporteLocal(), None, r.verificar, entrega="paquete")
    assert "entregado_en" in r2.paso()["destinos"]["srv-dmz"]   # reenvío tras reinicio
    _, datos, firma = ag.leer_generacion(a.a)
    assert a.procesar(datos, firma)["estado"] == "repetido"


def test_rele_no_entrega_pareja_incoherente_del_origen(tmp_path, claves):
    priv, pub = claves
    o, d, r = montar(tmp_path, pub, "paquete")
    d1, s1 = generacion(priv, 1)
    d2, _ = generacion(priv, 2)
    publicar_origen(o, d2, s1)                                   # firma de 1 con feed de 2 (lectura a medias)
    assert r.paso()["evento"] == "pareja_inconsistente"
    assert not (d / "feed.par").exists()


def test_agente_cli_paquete_invalido_no_se_acepta(tmp_path, claves):
    priv, pub = claves
    d = tmp_path / "destino"; d.mkdir()
    import time
    datos, firma = generacion(priv, 7, ahora=time.time())
    (d / "feed.par").write_bytes(feed.empaquetar(datos, firma)[:-40])      # incompleto
    base = ["--perfil", "dmz", "--paquete", str(d / "feed.par"), "--clave-publica", str(pub),
            "--estado", str(tmp_path / "e.json"), "--traza", str(tmp_path / "traza.jsonl"),
            "--helper", "%s -c pass" % sys.executable]
    assert ag.main(base) == 1
    ev = eventos(tmp_path)
    assert ev[-1]["evento"] == "rechazo" and ev[-1]["motivo"] == "paquete_invalido"
    (d / "feed.par").write_bytes(feed.empaquetar(datos, firma))
    assert ag.main(base) == 0
    assert eventos(tmp_path)[-1]["estado"] == "aceptado"


def test_agente_cli_exige_un_solo_modo(tmp_path):
    with pytest.raises(SystemExit):
        ag.main(["--perfil", "dmz", "--paquete", "p", "--feed", "f", "--firma", "s", "--clave-publica", "k",
                 "--estado", str(tmp_path / "e")])
    with pytest.raises(SystemExit):
        ag.main(["--perfil", "dmz", "--feed", "f", "--clave-publica", "k", "--estado", str(tmp_path / "e")])


# ----------------------------------------------------------------------------------- comando forzado (srv-dmz)

@pytest.mark.skipif(shutil.which("sh") is None or os.name == "nt", reason="requiere sh POSIX")
def test_comando_forzado_admite_paquete_y_nada_mas(tmp_path):
    import subprocess
    sc = str(RAIZ / "deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh")
    d = str(tmp_path)
    (tmp_path / "feed.par").write_bytes(b"VIEJO")

    def correr(modo, orden, entrada=b""):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND=orden)
        return subprocess.run(["sh", sc, modo, d], input=entrada, capture_output=True, env=env)

    assert correr("recibir", "cat > %s/.feed.par.tmp" % d, b"NUEVO").returncode == 0
    assert (tmp_path / "feed.par").read_bytes() == b"VIEJO"            # nada visible hasta el mv
    assert correr("recibir", "mv -f %s/.feed.par.tmp %s/feed.par" % (d, d)).returncode == 0
    assert (tmp_path / "feed.par").read_bytes() == b"NUEVO"
    for malo in ("cat > %s/feed.par" % d, "mv -f %s/.feed.par.tmp /tmp/x" % d,
                 "mv -f %s/.feed.par.tmp %s/feed.par; id" % (d, d), "cat %s/feed.par" % d):
        assert correr("recibir", malo).returncode != 0
    assert correr("servir", "cat > %s/.feed.par.tmp" % d, b"X").returncode != 0
    # las órdenes de la pareja siguen admitidas (reversión)
    assert correr("recibir", "cat > %s/.feed.sig.tmp" % d, b"S").returncode == 0


# ----------------------------------------------------------------------------------- concurrencia real (Linux)

def _concurrencia(tmp_path, entrega, n=400):
    """Escritor (publicador + relé) y lector (como el bucle del agente) a la vez. Firma barata = sha256 del feed:
    lo que se mide es si la PAREJA visible es coherente, no la criptografía (probada arriba con openssl)."""
    o, d = tmp_path / ("o-" + entrega), tmp_path / ("d-" + entrega)
    o.mkdir(); d.mkdir()
    sig = lambda b: hashlib.sha256(b).hexdigest().encode()          # noqa: E731
    r = rele.Rele({"dir": str(o), "host": None, "identidad": None}, [{"nombre": "x", "dir": str(d)}],
                  TransporteConPausa(lambda: None), None, lambda b, s: s == sig(b), entrega=entrega)
    a = argparse.Namespace(paquete=d / "feed.par" if entrega == "paquete" else None,
                           feed=d / "feed.json", firma=d / "feed.sig")
    fin = threading.Event()
    malas, buenas, vistas = [0], [0], set()

    def lector():
        while not fin.is_set():
            try:
                _, datos, firma = ag.leer_generacion(a)
            except OSError:
                continue
            if datos is None or firma != sig(datos):
                malas[0] += 1
            else:
                buenas[0] += 1
                vistas.add(json.loads(datos)["secuencia"])

    th = threading.Thread(target=lector)
    th.start()
    try:
        for s in range(1, n + 1):
            b = json.dumps({"secuencia": s, "relleno": "x" * 200}).encode()
            publicar_origen(o, b, sig(b))
            r.paso()
    finally:
        fin.set()
        th.join()
    _, datos, firma = ag.leer_generacion(a)          # tras la última entrega
    vistas.add(json.loads(datos)["secuencia"])
    return malas[0], buenas[0], vistas


@pytest.mark.skipif(os.name == "nt", reason="rename sobre un fichero abierto: semántica POSIX (banco Linux)")
def test_concurrencia_paquete_cero_incoherentes(tmp_path):
    malas, buenas, vistas = _concurrencia(tmp_path, "paquete")
    assert malas == 0 and buenas > 0 and max(vistas) == 400
