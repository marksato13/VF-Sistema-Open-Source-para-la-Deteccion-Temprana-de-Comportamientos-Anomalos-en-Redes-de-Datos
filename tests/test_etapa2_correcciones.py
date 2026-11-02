"""Cierre tecnico de la Etapa 2: regresiones de las correcciones 2 (rele), 3 (perfil fijo
del helper) y 7 (instrumentacion del LIMIT).

Sin red y sin tocar el host. Las pruebas con firma real necesitan openssl (banco Docker);
las del fichero de perfil necesitan root (propietario uid 0), y las de nft real, root y nft.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_etapa2_cadena import (  # noqa: E402
    HAY_OPENSSL, NFT_REAL, T0, HelperFalso, Reloj, ag, agente, entrada, feed, feed_v2, firmado, helper, hx, rele,
)

RAIZ = Path(__file__).resolve().parents[1]
ES_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


@pytest.fixture
def claves(tmp_path):
    if not HAY_OPENSSL:
        pytest.skip("sin openssl")
    priv, pubk = tmp_path / "p.pem", tmp_path / "pub.pem"
    feed.generar_claves(str(priv), str(pubk))
    return priv, pubk


# ============================================================================
# Punto 2. Coherencia feed/firma en el rele
# ============================================================================

class Origen:
    """Directorio del sensor con escritura controlada de cada fichero por separado."""

    def __init__(self, d: Path):
        self.d = d
        d.mkdir(exist_ok=True)

    def poner(self, datos=None, firma=None):
        if firma is not None:
            (self.d / "feed.sig").write_bytes(firma)
        if datos is not None:
            (self.d / "feed.json").write_bytes(datos)


def nuevo_rele(tmp_path, origen, destinos, pubk, transporte=None):
    return rele.Rele({"dir": str(origen.d), "host": None, "identidad": None},
                     [{"nombre": n, "dir": str(d)} for n, d in destinos],
                     transporte or rele.TransporteLocal(), tmp_path / "traza-rele.jsonl",
                     rele.verificador(str(pubk)))


def traza(ruta):
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []


def pareja(d: Path):
    return (d / "feed.json").read_bytes(), (d / "feed.sig").read_bytes()


def dos_feeds(priv):
    f1 = feed_v2([entrada(hasta=T0 + 300)], seq=1)
    f2 = feed_v2([entrada(hasta=T0 + 600, ev="e2")], seq=2, ahora=T0 + 10)
    return firmado(priv, f1), firmado(priv, f2)


def test_rele_firma_nueva_con_feed_anterior_no_se_entrega(tmp_path, claves):
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(d1, s1)
    r = nuevo_rele(tmp_path, o, [("srv-dmz", dst)], pubk)
    assert "entregado_en" in r.paso()["destinos"]["srv-dmz"]
    o.poner(firma=s2)                       # el publicador renombro solo la firma
    assert r.paso()["evento"] == "pareja_inconsistente"
    assert pareja(dst) == (d1, s1)          # el destino conserva la pareja anterior, coherente
    assert r.entregado["srv-dmz"].endswith(rele.hashlib.sha256(s1).hexdigest()[:16])
    o.poner(datos=d2)                       # llega el feed: pareja coherente
    reg = r.paso()
    assert reg["secuencia"] == 2 and pareja(dst) == (d2, s2)
    t = traza(tmp_path / "traza-rele.jsonl")
    assert [x["evento"] for x in t].count("pareja_inconsistente") == 1


def test_rele_feed_nuevo_con_firma_anterior_no_se_entrega(tmp_path, claves):
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(d1, s1)
    r = nuevo_rele(tmp_path, o, [("srv-dmz", dst)], pubk)
    r.paso()
    o.poner(datos=d2)
    for _ in range(3):                       # sondeos repetidos: una sola traza, ninguna entrega
        assert r.paso()["evento"] == "pareja_inconsistente"
    assert pareja(dst) == (d1, s1)
    o.poner(firma=s2)
    assert r.paso()["secuencia"] == 2 and pareja(dst) == (d2, s2)
    assert [x["evento"] for x in traza(tmp_path / "traza-rele.jsonl")].count("pareja_inconsistente") == 1


def test_rele_correccion_de_firma_sin_cambio_del_feed(tmp_path, claves):
    """El defecto original: con el mismo feed, la firma corregida no se reenviaba."""
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(d2, s1)                          # feed nuevo con firma vieja desde el principio
    r = nuevo_rele(tmp_path, o, [("srv-dmz", dst)], pubk)
    assert r.paso()["evento"] == "pareja_inconsistente"
    assert not (dst / "feed.json").exists() and "srv-dmz" not in r.entregado
    o.poner(firma=s2)                        # solo cambia la firma
    reg = r.paso()
    assert "entregado_en" in reg["destinos"]["srv-dmz"] and pareja(dst) == (d2, s2)


def test_rele_sigue_la_pareja_no_el_feed(tmp_path):
    """Misma secuencia y mismo feed, firma distinta (valida): se reenvia la pareja."""
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(b'{"secuencia": 1}\n', b"A")
    r = rele.Rele({"dir": str(o.d), "host": None, "identidad": None}, [{"nombre": "srv-dmz", "dir": str(dst)}],
                  rele.TransporteLocal(), None, verificar=lambda d, f: True)
    r.paso()
    o.poner(firma=b"B")
    assert r.paso() is not None and (dst / "feed.sig").read_bytes() == b"B"
    assert r.paso() is None


class TransporteInestable(rele.TransporteLocal):
    """El feed cambia entre la primera y la segunda lectura (renombrado durante la lectura)."""

    def __init__(self, origen: Origen, nuevo: bytes):
        self.origen, self.nuevo, self.lecturas = origen, nuevo, 0

    def traer(self, o, nombre):
        datos = super().traer(o, nombre)
        if nombre == "feed.json":
            self.lecturas += 1
            if self.lecturas == 1:
                self.origen.poner(datos=self.nuevo)
        return datos


def test_rele_cambio_de_publicacion_durante_la_lectura(tmp_path, claves):
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(d1, s1)
    r = nuevo_rele(tmp_path, o, [("srv-dmz", dst)], pubk, TransporteInestable(o, d2))
    assert r.paso() is None
    assert not (dst / "feed.json").exists()
    assert traza(tmp_path / "traza-rele.jsonl")[0]["evento"] == "lectura_inestable"


class TransporteQueFalla(rele.TransporteLocal):
    def __init__(self):
        self.fallar_en = None  # "feed.json" (subida) o "confirmar"

    def subir(self, destino, nombre, datos):
        if self.fallar_en == nombre:
            return "simulado"
        return super().subir(destino, nombre, datos)

    def confirmar(self, destino):
        if self.fallar_en == "confirmar":
            return "simulado"
        return super().confirmar(destino)


@pytest.mark.parametrize("donde", ["feed.json", "confirmar"])
def test_rele_entrega_parcial_conserva_la_pareja_anterior_y_reintenta(tmp_path, claves, donde):
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    o, dst = Origen(tmp_path / "o"), tmp_path / "srv"
    dst.mkdir()
    o.poner(d1, s1)
    t = TransporteQueFalla()
    r = nuevo_rele(tmp_path, o, [("srv-dmz", dst)], pubk, t)
    r.paso()
    o.poner(d2, s2)
    t.fallar_en = donde
    reg = r.paso()
    assert "error" in reg["destinos"]["srv-dmz"]
    assert pareja(dst) == (d1, s1)          # lo visible sigue siendo la pareja anterior, firmada
    assert feed.verificar(*pareja(dst), str(pubk))
    t.fallar_en = None
    reg = r.paso()                           # reintento sin nueva publicacion
    assert "entregado_en" in reg["destinos"]["srv-dmz"] and pareja(dst) == (d2, s2)


def test_rele_destino_ausente_y_reinicio_del_rele_con_agente(tmp_path, claves):
    """Destino ausente -> reintento; reinicio del rele -> reenvio que el agente trata como repetido
    sin ampliar la caducidad."""
    priv, pubk = claves
    (d1, s1), _ = dos_feeds(priv)
    o, srv, dc = Origen(tmp_path / "o"), tmp_path / "srv", tmp_path / "dc1"
    srv.mkdir()
    o.poner(d1, s1)
    r = nuevo_rele(tmp_path, o, [("srv-dmz", srv), ("dc1", dc)], pubk)
    reg = r.paso()
    assert "entregado_en" in reg["destinos"]["srv-dmz"] and "error" in reg["destinos"]["dc1"]
    dc.mkdir()
    assert list(r.paso()["destinos"]) == ["dc1"]
    reloj = Reloj(T0 + 5)
    a, h, _ = agente(tmp_path, pubk, "dmz", reloj)
    assert a.procesar(*pareja(srv))["estado"] == "aceptado"
    expira = h.sets["bloqueados"]["10.10.20.30"]
    llamadas = len(h.llamadas)
    r2 = nuevo_rele(tmp_path, o, [("srv-dmz", srv), ("dc1", dc)], pubk)   # reinicio: memoria vacia
    assert set(r2.paso()["destinos"]) == {"srv-dmz", "dc1"}
    reloj.t = T0 + 40
    assert a.procesar(*pareja(srv))["estado"] == "repetido"
    assert h.sets["bloqueados"]["10.10.20.30"] == expira and len(h.llamadas) == llamadas


def test_agente_pareja_a_medias_rechazo_y_recuperacion_sin_ampliar(tmp_path, claves):
    """El agente lee feed nuevo con firma vieja: rechazo sin tocar nada; con la firma correcta
    aplica con timeout = hasta - ahora (la espera no amplia la caducidad)."""
    priv, pubk = claves
    (d1, s1), (d2, s2) = dos_feeds(priv)
    reloj = Reloj(T0 + 11)
    a, h, _ = agente(tmp_path, pubk, "dmz", reloj)
    assert a.procesar(d2, s1)["motivo"] == "firma_invalida"
    assert h.llamadas == [] and a.estado["secuencia"] is None
    reloj.t = T0 + 50
    assert a.procesar(d2, s2)["estado"] == "aceptado"
    op = [o for ops in h.llamadas for o in ops if o["op"] == "anadir"][0]
    assert op["timeout"] == int(T0 + 600 - (T0 + 50)) or op["timeout"] == pytest.approx(550, abs=1)


def test_agente_reintenta_el_mismo_feed_si_falla_el_helper(tmp_path, claves):
    """main(--seguir): el helper falla una vez; sin otra publicacion se reintenta el MISMO feed."""
    priv, pubk = claves
    d = feed_v2([entrada(hasta=time.time() + 300)], seq=1, ahora=time.time())
    datos, firma = firmado(priv, d)
    (tmp_path / "feed.json").write_bytes(datos)
    (tmp_path / "feed.sig").write_bytes(firma)
    falso = tmp_path / "helper_falso.py"
    falso.write_text(
        "import json, sys, pathlib\n"
        "p = json.loads(sys.stdin.read())\n"
        "marca = pathlib.Path(%r)\n"
        "ops = [o['op'] for o in p['operaciones']]\n"
        "if ops == ['listar']:\n"
        "    print(json.dumps({'ok': True, 'estado': {'sets': {}}})); sys.exit(0)\n"
        "if not marca.exists():\n"
        "    marca.write_text('1'); print(json.dumps({'ok': False, 'error_nft': 'simulado'})); sys.exit(0)\n"
        "print(json.dumps({'ok': True}))\n" % str(tmp_path / "ya_fallo"), encoding="utf-8")
    argv = ["--perfil", "dmz", "--feed", str(tmp_path / "feed.json"), "--firma", str(tmp_path / "feed.sig"),
            "--clave-publica", str(pubk), "--estado", str(tmp_path / "st.json"), "--traza",
            str(tmp_path / "traza.jsonl"), "--helper", "%s %s" % (sys.executable, falso), "--aplicar",
            "--seguir", "--sondeo-segundos", "0.05", "--reintento-segundos", "0.2", "--observar-segundos", "999",
            "--max-iteraciones", "40"]
    hilo = threading.Thread(target=ag.main, args=(argv,))
    hilo.start()
    hilo.join(30)
    eventos = [json.loads(x)["evento"] for x in (tmp_path / "traza.jsonl").read_text().splitlines()]
    assert "rechazo" in eventos and "reintento" in eventos
    assert eventos.index("reintento") > eventos.index("rechazo")
    assert "aplicacion" in eventos[eventos.index("reintento"):]
    assert json.loads((tmp_path / "st.json").read_text())["secuencia"] == 1


# ============================================================================
# Punto 3. Perfil del helper fijado por host
# ============================================================================

def anadir(set_="bloqueados", ip="10.10.20.30"):
    return {"op": "anadir", "id": "00000000000000a1", "set": set_, "ip": ip, "timeout": 60}


@pytest.mark.parametrize("pedido,autorizado", [("dmz", "dns"), ("dns", "dmz")])
def test_helper_perfil_cruzado_rechazado(pedido, autorizado):
    """dmz en DC1 (perfil del host dns) y dns en srv-dmz (perfil del host dmz)."""
    r = hx({"perfil": pedido, "operaciones": [anadir()]}, autorizado=autorizado)
    assert r == {"ok": False, "rechazo": "perfil_no_autorizado"} or r.get("rechazo") == "perfil_no_autorizado"


@pytest.mark.parametrize("campo,valor", [("tabla", "inet filter"), ("cadena", "input"), ("nft", "flush ruleset"),
                                         ("familia", "inet")])
def test_helper_no_admite_tabla_cadena_ni_texto(campo, valor):
    op = dict(anadir())
    op[campo] = valor
    r = hx({"perfil": "dns", "operaciones": [op]})
    assert not r["ok"]


@pytest.mark.parametrize("op", ["flush", "borrar_tabla", "ruleset", "ejecutar"])
def test_helper_rechaza_operaciones_fuera_del_contrato(op):
    assert not hx({"perfil": "dns", "operaciones": [{"op": op}]})["ok"]


def test_helper_texto_nunca_toca_el_ruleset_general():
    for perfil in ("dns", "dmz"):
        pet = {"perfil": perfil, "operaciones": [{"op": "asegurar"}, anadir(), anadir("limitados", "10.10.20.31"),
                                                 {"op": "quitar", "set": "bloqueados", "ip": "10.10.20.30"}]}
        p, ops = helper.validar(pet, perfil)
        texto = helper.texto(p, ops)
        for linea in texto.splitlines():
            if linea.strip():
                assert ("inet %s " % helper.TABLAS[perfil]) in linea + " ", linea
                assert "ruleset" not in linea


def test_helper_excepciones_de_infraestructura_siguen_vigentes():
    for ip in sorted(helper.NUNCA):
        r = hx({"perfil": "dmz", "operaciones": [anadir(ip=ip)]})
        assert not r["ok"], ip


def test_helper_caducidad_acotada():
    op = dict(anadir())
    op["timeout"] = 10 ** 7
    assert not hx({"perfil": "dmz", "operaciones": [op]})["ok"]


@pytest.mark.skipif(not ES_ROOT, reason="necesita root (propietario uid 0)")
class TestFicheroDePerfil:
    def preparar(self, tmp_path, contenido="dns\n", modo=0o644, modo_dir=0o755):
        d = tmp_path / "etc"
        d.mkdir(mode=modo_dir)
        os.chmod(d, modo_dir)
        f = d / "perfil"
        f.write_text(contenido)
        os.chmod(f, modo)
        return f

    def test_valido(self, tmp_path):
        assert helper.leer_perfil_autorizado(str(self.preparar(tmp_path))) == "dns"

    def test_falta(self, tmp_path):
        with pytest.raises(helper.Rechazo, match="perfil_no_configurado"):
            helper.leer_perfil_autorizado(str(tmp_path / "no-existe"))

    def test_contenido_invalido(self, tmp_path):
        with pytest.raises(helper.Rechazo):
            helper.leer_perfil_autorizado(str(self.preparar(tmp_path, "todo\n")))

    def test_escribible_por_otros(self, tmp_path):
        with pytest.raises(helper.Rechazo, match="configuracion_insegura"):
            helper.leer_perfil_autorizado(str(self.preparar(tmp_path, modo=0o666)))

    def test_directorio_escribible(self, tmp_path):
        with pytest.raises(helper.Rechazo, match="configuracion_insegura"):
            helper.leer_perfil_autorizado(str(self.preparar(tmp_path, modo_dir=0o777)))

    def test_enlace_simbolico(self, tmp_path):
        real = self.preparar(tmp_path)
        enlace = real.parent / "enlace"
        enlace.symlink_to(real)
        with pytest.raises(helper.Rechazo, match="configuracion_insegura"):
            helper.leer_perfil_autorizado(str(enlace))

    def test_duenio_no_root(self, tmp_path):
        f = self.preparar(tmp_path)
        os.chown(f, 65534, 65534)
        with pytest.raises(helper.Rechazo, match="configuracion_insegura"):
            helper.leer_perfil_autorizado(str(f))

    def test_main_lee_el_perfil_antes_que_la_peticion(self, tmp_path, capsys, monkeypatch):
        f = self.preparar(tmp_path, "dmz\n")
        import io
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(
            json.dumps({"perfil": "dns", "operaciones": [anadir()]}).encode())))
        rc = helper.main(argv=["cf-nft-helper"], ruta_perfil=str(f))
        assert rc != 0 and "perfil_no_autorizado" in capsys.readouterr().out

    def test_main_rechaza_argumentos(self, tmp_path, capsys):
        f = self.preparar(tmp_path)
        assert helper.main(argv=["cf-nft-helper", "--perfil", "dmz"], ruta_perfil=str(f)) != 0


# ============================================================================
# Punto 7. Instrumentacion del LIMIT: regla, coincidencias, descartes y efecto, separados
# ============================================================================

def feed_limit(seq, hasta, ev, ip="10.10.20.40"):
    return feed_v2([entrada(ip=ip, destino="dc1", alcance="dns", accion="LIMIT", hasta=hasta, ev=ev)],
                   seq=seq, ahora=T0)


def eventos(tmp_path, perfil="dns"):
    return [json.loads(x) for x in (tmp_path / ("traza-%s.jsonl" % perfil)).read_text().splitlines()]


def test_limit_coincidencia_no_es_descarte(tmp_path, claves):
    priv, pubk = claves
    reloj = Reloj(T0 + 1)
    a, h, _ = agente(tmp_path, pubk, "dns", reloj)
    assert a.procesar(*firmado(priv, feed_limit(1, T0 + 300, "e1")))["estado"] == "aceptado"
    e = [x for x in eventos(tmp_path) if x["evento"] == "confirmacion"][-1]
    assert e["confirmadas"] and not e["no_confirmadas"]          # regla aplicada y confirmada
    # trafico por debajo del limite: coincide, no se descarta
    h.contadores[("limitados", "10.10.20.40")] = 4
    reloj.t += 5
    a.observar()
    ev = eventos(tmp_path)
    pc = [x for x in ev if x["evento"] == "primera_coincidencia"]
    assert pc and pc[0]["nota"] == "coincidencia_no_implica_descarte"
    assert not [x for x in ev if x["evento"] == "primer_descarte"]
    assert not any("primer_efecto" in x.get("evento", "") for x in ev)
    # por encima: descartes por origen
    h.contadores[("limitados", "10.10.20.40")] = 60
    h.descartes["10.10.20.40"] = 41
    reloj.t += 5
    a.observar()
    ev = eventos(tmp_path)
    pd = [x for x in ev if x["evento"] == "primer_descarte"]
    assert len(pd) == 1
    cont = [x for x in ev if x["evento"] == "contadores"]
    ultimo = cont[-1]
    assert json.dumps(ultimo).count("41") >= 1


def test_limit_dos_origenes_contadores_separados(tmp_path, claves):
    priv, pubk = claves
    reloj = Reloj(T0 + 1)
    a, h, _ = agente(tmp_path, pubk, "dns", reloj)
    f = feed_v2([entrada(ip="10.10.20.40", destino="dc1", alcance="dns", accion="LIMIT", ev="e1"),
                 entrada(ip="10.10.20.41", destino="dc1", alcance="dns", accion="LIMIT", ev="e2")], seq=1, ahora=T0)
    assert a.procesar(*firmado(priv, f))["estado"] == "aceptado"
    h.contadores[("limitados", "10.10.20.40")] = 50
    h.descartes["10.10.20.40"] = 30
    h.contadores[("limitados", "10.10.20.41")] = 3
    reloj.t += 5
    a.observar()
    iv = a.estado["intervalos"]
    por_ip = {x["ip"]: x for x in iv.values()}
    assert por_ip["10.10.20.40"]["descartes"] == 30 and por_ip["10.10.20.41"]["descartes"] == 0
    assert por_ip["10.10.20.41"]["coincidencias"] == 3


def test_limit_renovacion_id_nuevo_contadores_desde_cero(tmp_path, claves):
    priv, pubk = claves
    reloj = Reloj(T0 + 1)
    a, h, _ = agente(tmp_path, pubk, "dns", reloj)
    a.procesar(*firmado(priv, feed_limit(1, T0 + 120, "e1")))
    h.contadores[("limitados", "10.10.20.40")] = 20
    h.descartes["10.10.20.40"] = 9
    reloj.t += 5
    a.observar()
    id1 = h.ids[("limitados", "10.10.20.40")]
    reloj.t = T0 + 30
    assert a.procesar(*firmado(priv, feed_limit(2, T0 + 900, "e2")))["estado"] == "aceptado"  # renovacion
    id2 = h.ids[("limitados", "10.10.20.40")]
    assert id2 != id1 and h.contadores[("limitados", "10.10.20.40")] == 0
    assert "10.10.20.40" not in h.descartes                         # el helper reinicia los descartes
    reloj.t += 5
    a.observar()
    iv = a.estado["intervalos"]
    assert iv[id1]["descartes"] == 9 and iv[id2]["descartes"] == 0


def test_limit_caducidad_y_reinicio_del_agente(tmp_path, claves):
    priv, pubk = claves
    reloj = Reloj(T0 + 1)
    a, h, _ = agente(tmp_path, pubk, "dns", reloj)
    a.procesar(*firmado(priv, feed_limit(1, T0 + 100, "e1")))
    id1 = h.ids[("limitados", "10.10.20.40")]
    h.contadores[("limitados", "10.10.20.40")] = 7
    reloj.t += 5
    a.observar()
    a.guardar()
    # reinicio del agente: estado releido; los ids vienen del comentario de nft
    a2 = ag.Agente(a.a, helper=h, reloj=reloj)
    assert a2.estado["secuencia"] == 1 and id1 in a2.estado["intervalos"]
    reloj.t = T0 + 101                                               # caduca de forma nativa
    a2.observar()
    ret = [x for x in eventos(tmp_path) if x["evento"] == "retirada"]
    assert ret and ret[-1].get("id") == id1


@pytest.mark.skipif(not NFT_REAL, reason="necesita root y nft (banco)")
def test_limit_nft_real_descartes_por_origen(tmp_path):
    """Regla real del helper: el set de descartes cuenta por origen solo lo que supera el limite."""
    import subprocess
    pet = {"perfil": "dns", "operaciones": [{"op": "asegurar"}, anadir("limitados", "10.10.20.40")]}
    r = helper.ejecutar(pet, "dns")
    assert r["ok"], r
    try:
        texto = subprocess.run(["nft", "list", "table", "inet", helper.TABLAS["dns"]],
                               capture_output=True, text=True).stdout
        assert "descartes_limite" in texto and "update @descartes_limite" in texto
        lst = helper.ejecutar({"perfil": "dns", "operaciones": [{"op": "listar"}]}, "dns")
        lim = lst["estado"]["sets"]["limitados"]["10.10.20.40"]
        assert lim["id"] == "00000000000000a1"
        assert "descartes_limite" in lst["estado"]
    finally:
        subprocess.run(["nft", "delete", "table", "inet", helper.TABLAS["dns"]], capture_output=True)
