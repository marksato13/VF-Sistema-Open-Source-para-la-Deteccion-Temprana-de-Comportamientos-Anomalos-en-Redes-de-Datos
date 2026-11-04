"""Regresiones del cierre complementario de la 4A (4-nov-2026): cobertura y estados del panel v2.

Defectos reproducidos en a27889d (cadena_v2.py) y corregidos:
A. Una decisión posterior a la última publicación, todavía sin señal registrada, salía «sin señal IF».
B. Una medida «desconocida» terminaba con aplicación «no aplica».
C. Al arrancar sin traza.jsonl el panel elegía solo la política v1 (y «Preparar demo» volvía).
Cada prueba de este fichero falla con a27889d y pasa con la corrección.
"""
from __future__ import annotations

import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_panel_cadena_v2 import (NODE, REPO, T0, _bloque_js, _puerto_libre, decision,  # noqa: E402
                                  escribir, publicacion)

import cadena_v2  # noqa: E402
import dashboard as db  # noqa: E402


def senal(d, alfas=("0.05",)):
    return {"decision_id": d["decision_id"], "ip": d["entity_ip"], "score": d["score"],
            "alfa_superados": list(alfas), "logged_at": d["logged_at"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "feed-v2"
        self._previo = db._CADENA_V2

    def tearDown(self):
        db._CADENA_V2 = self._previo
        self.tmp.cleanup()

    def indice(self, modo="sombra"):
        db._CADENA_V2 = cadena_v2.IndiceV2(self.dir, modo)
        return db._CADENA_V2

    def traza_normal(self, **kw):
        """Publicaciones cada 20 s de T0 a T0+60 (como el publicador desplegado)."""
        escribir(self.dir, senales=kw.get("senales", []),
                 traza=[publicacion(i + 1, T0 + 20 * i) for i in range(4)],
                 feed=kw.get("feed", {"secuencia": 4, "generado": T0 + 60, "entradas": []}))


class DecisionesPosteriores(Base):
    """A: posterior a la última publicación = procesamiento pendiente, no ausencia."""

    def test_posterior_con_traza_fresca_es_pendiente_y_no_sin_senal(self):
        self.traza_normal()
        d = decision("10.10.20.24", T0 + 65, "PERMIT", score=-0.30)
        self.indice().anotar([d], ahora=T0 + 66)
        c = d["cadena_v2"]
        self.assertEqual(c["if"]["estado"], "pendiente")
        self.assertEqual(c["medida"]["estado"], "pendiente")
        self.assertEqual(c["aplicacion"], "desconocido")
        self.assertEqual(c["cobertura"], "pendiente")

    def test_margen_de_lectura_antes_de_la_ultima_publicacion(self):
        self.traza_normal()
        d = decision("10.10.20.24", T0 + 59, "PERMIT", score=-0.30)   # 1 s antes de la última
        self.indice().anotar([d], ahora=T0 + 61)
        self.assertEqual(d["cadena_v2"]["if"]["estado"], "pendiente")

    def test_dentro_de_la_cobertura_si_es_sin_senal_y_no_aplica(self):
        self.traza_normal()
        d = decision("10.10.20.24", T0 + 30, "PERMIT", score=-0.30)
        self.indice().anotar([d], ahora=T0 + 61)
        c = d["cadena_v2"]
        self.assertEqual((c["if"]["estado"], c["medida"]["estado"], c["aplicacion"]),
                         ("sin_senal", "no_publicada", "no_aplica"))


class RetrasoYFuenteAntigua(Base):
    def test_publicador_retrasado_es_fuente_desactualizada(self):
        self.traza_normal()
        d = decision("10.10.20.24", T0 + 70, "ALERT", score=-0.60)
        self.indice().anotar([d], ahora=T0 + 160)        # última publicación hace 100 s
        c = d["cadena_v2"]
        self.assertEqual(c["if"]["estado"], "fuente_desactualizada")
        self.assertEqual(c["medida"]["estado"], "fuente_desactualizada")
        self.assertEqual(c["aplicacion"], "desconocido")
        self.assertIsNone(db.accion_de(d))

    def test_fuente_antigua_se_declara_incidencia_y_conserva_lo_cubierto(self):
        self.traza_normal()
        idx = self.indice()
        d = decision("10.10.20.24", T0 + 30, "PERMIT", score=-0.30)
        idx.anotar([d], ahora=T0 + 600)
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "no_publicada")   # lo ya cubierto sigue
        r = idx.resumen(T0 + 600)
        self.assertEqual(r["estado"], "incidencia")
        self.assertFalse(r["traza_fresca"])
        self.assertTrue(any("desactualizada" in x for x in r["incidencias"]))

    def test_hueco_entre_publicaciones_no_demuestra_ausencia(self):
        escribir(self.dir, senales=[], traza=[publicacion(1, T0), publicacion(2, T0 + 100)],
                 feed={"secuencia": 2, "generado": T0 + 100, "entradas": []})
        d = decision("10.10.20.24", T0 + 50, "PERMIT", score=-0.30)
        idx = self.indice()
        idx.anotar([d], ahora=T0 + 101)
        self.assertEqual(d["cadena_v2"]["if"]["estado"], "desconocido")
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "desconocido")
        self.assertEqual(d["cadena_v2"]["aplicacion"], "desconocido")
        self.assertEqual(idx.resumen(T0 + 101)["huecos_traza"], 1)


class FuentesAusentes(Base):
    def test_senales_ausentes_no_son_cero_senales(self):
        escribir(self.dir, traza=[publicacion(i + 1, T0 + 20 * i) for i in range(4)],
                 feed={"secuencia": 4, "generado": T0 + 60, "entradas": []})
        d = decision("10.10.20.24", T0 + 30, "PERMIT", score=-0.30)
        idx = self.indice()
        idx.anotar([d], ahora=T0 + 61)
        self.assertEqual(d["cadena_v2"]["if"]["estado"], "fuente_ausente")
        self.assertIsNone(idx.resumen(T0 + 61)["senales_if"])

    def test_medida_desconocida_mantiene_aplicacion_desconocida(self):
        escribir(self.dir, senales=[], feed={"secuencia": 4, "generado": T0 + 60, "entradas": []})
        d = decision("10.10.20.24", T0 + 30, "ALERT", score=-0.60)
        idx = self.indice()
        idx.anotar([d], ahora=T0 + 61)
        c = d["cadena_v2"]
        self.assertEqual(c["medida"]["estado"], "fuente_ausente")
        self.assertEqual(c["aplicacion"], "desconocido")
        self.assertEqual(c["if"]["estado"], "desconocido")     # sin traza, la cobertura no se demuestra
        r = idx.resumen(T0 + 61)
        self.assertIsNone(r["decisiones_con_medida"])
        self.assertTrue(any("traza.jsonl" in x for x in r["incidencias"]))

    def test_traza_sin_publicaciones_es_fuente_ausente(self):
        escribir(self.dir, senales=[], feed={"entradas": []})
        (self.dir / "traza.jsonl").write_text("no es json\n", encoding="utf-8")
        d = decision("10.10.20.24", T0 + 30, "PERMIT", score=-0.30)
        self.indice().anotar([d], ahora=T0 + 61)
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "fuente_ausente")

    def test_desaparecen_durante_la_ejecucion_y_se_recuperan(self):
        self.traza_normal()
        idx = self.indice()
        d = decision("10.10.20.24", T0 + 30, "ALERT", score=-0.60)
        idx.anotar([d], ahora=T0 + 61)
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "no_publicada")
        aparte = Path(self.tmp.name) / "aparte"
        self.dir.rename(aparte)                                  # las fuentes desaparecen
        idx.anotar([d], ahora=T0 + 62)
        c = d["cadena_v2"]
        self.assertEqual((c["if"]["estado"], c["medida"]["estado"], c["aplicacion"]),
                         ("fuente_ausente", "fuente_ausente", "desconocido"))
        self.assertIsNone(db.accion_de(d))                      # sin volver a la política v1 (LIMIT)
        r = idx.resumen(T0 + 62)
        self.assertTrue(r["activa"])
        self.assertTrue(any("ausente" in x for x in r["incidencias"]))
        aparte.rename(self.dir)                                  # y vuelven
        idx.anotar([d], ahora=T0 + 63)
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "no_publicada")
        self.assertEqual(idx.resumen(T0 + 63)["estado"], "ok")


class IFDelMotorExplicito(Base):
    def test_decision_if_del_motor_y_senal_alfa_no_se_mezclan(self):
        d = decision("10.10.20.24", T0 + 30, "PERMIT", score=-0.55)   # PERMIT del motor, α 0,05 superado
        self.traza_normal(senales=[senal(d)])
        self.indice().anotar([d], ahora=T0 + 61)
        c = d["cadena_v2"]
        self.assertEqual(c["if_motor"]["fuente"], "registro del motor (decision_if)")
        self.assertEqual((c["if_motor"]["decision_if"], c["if_motor"]["score"]), ("PERMIT", -0.55))
        self.assertEqual((c["if"]["estado"], c["if"]["fuente"], c["if"]["alfa_superados"]),
                         ("senal", "senales-if.jsonl", ["0.05"]))


class ModoExplicito(unittest.TestCase):
    """C: el modo v2 no depende de los ficheros; v1 solo por selección explícita."""

    def args(self, **kw):
        base = {"demo": False, "sin_cadena_v2": False, "modo_panel": "v2"}
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_seleccion_de_modo(self):
        self.assertEqual(db.modo_panel_de(self.args()), "v2")
        self.assertEqual(db.modo_panel_de(self.args(modo_panel="v1-historico")), "v1-historico")
        self.assertEqual(db.modo_panel_de(self.args(sin_cadena_v2=True)), "v1-historico")
        self.assertEqual(db.modo_panel_de(self.args(demo=True)), "v1-historico")

    def test_boton_preparar_sale_oculto_del_servidor_en_v2(self):
        html = db.html_por_rol(db.HTML, "admin")
        self.assertIn(db.BOTON_PREPARAR, html)                # el marcado que se sustituye existe
        v2 = db.html_solo_lectura_v2(html)
        self.assertIn('id="prepBtn" hidden disabled', v2)
        self.assertNotIn(db.BOTON_PREPARAR, v2)


@unittest.skipUnless(NODE, "sin node: la comprobación del JS no se puede omitir en el cierre de la 4A")
class JsEstados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = db.html_por_rol(db.HTML, "admin")
        cls.script = html.split("<script>", 1)[1].split("</script>", 1)[0]

    def test_textos_de_estado_franja_y_boton(self):
        piezas = [_bloque_js(self.script, n) for n in (
            "MEDIDAS_V2", "medidaV2", "TXT_MEDIDA_V2", "TXT_SENAL_V2", "TXT_APLICACION_V2",
            "cadenaV2HTML", "franjaV2HTML", "pintarCadenaV2")]
        prueba = r"""
const varEsc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const boton = {hidden: true, disabled: true};
const document = {getElementById: id => id === 'prepBtn' ? boton : null, querySelector: () => null,
  createElement: () => ({setAttribute() {}}), body: {insertBefore() {}}};
%s
const ok = (c, m) => { if (!c) { console.error('FALLO: ' + m); process.exitCode = 1; } };
const pend = cadenaV2HTML({cadena_v2: {if_motor: {fuente: 'registro del motor (decision_if)', decision_if: 'PERMIT', score: -0.3, umbral: -0.5694},
  if: {estado: 'pendiente'}, reglas: [], decision: 'PERMIT', medida: {estado: 'pendiente'}, aplicacion: 'desconocido'}});
ok(pend.includes('1b · Señal α publicada</dt><dd>pendiente'), 'señal pendiente');
ok(!pend.includes('sin señal'), 'pendiente no es sin señal');
ok(pend.includes('4 · Medida</dt><dd>pendiente'), 'medida pendiente');
ok(pend.includes('desconocido (sin evidencia)') && !pend.includes('no aplica'), 'aplicación desconocida');
ok(pend.includes('1a · IF del motor</dt><dd>decision_if PERMIT') && pend.includes('registro del motor (decision_if)'), 'IF del motor explícito');
const aus = cadenaV2HTML({cadena_v2: {if: {estado: 'fuente_ausente'}, reglas: [], medida: {estado: 'fuente_ausente'}, aplicacion: 'desconocido'}});
ok(aus.includes('senales-if.jsonl ausente o ilegible') && aus.includes('traza v2 ausente o ilegible'), 'fuente ausente');
ok(medidaV2({cadena_v2: {medida: {estado: 'fuente_ausente'}}}) === 'PERMIT', 'sin medida no hay acción');
const fr = franjaV2HTML({activa: true, modo: 'sombra', politica: null, feed_atrasado: true, feed_entradas: 0,
  incidencias: ['traza.jsonl ausente o ilegible (FileNotFoundError)'], fuentes: {senales_if: {ok: true}, traza: {ok: false}, feed: {ok: false}}});
ok(fr.includes('INCIDENCIA: traza.jsonl ausente'), 'incidencia visible');
ok(fr.includes('medidas en el feed: <b>desconocido') && !fr.includes('0 medida(s)'), 'feed ausente no es cero');
ok(fr.includes('traza <b>ausente o ilegible'), 'traza ausente nombrada');
pintarCadenaV2(undefined);
ok(boton.hidden === true && boton.disabled === true, 'sin /api/status el botón no reaparece');
pintarCadenaV2(null);
ok(boton.hidden === true, 'cadena nula no reactiva el botón');
""" % "\n".join(piezas)
        r = subprocess.run([NODE, "-"], input=prueba, text=True, encoding="utf-8", capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)


class ServidorSinTraza(unittest.TestCase):
    """C, de punta a punta: arranque sin traza.jsonl -> modo v2 con incidencia; luego se recupera."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.ahora = ahora = time.time()
        cls.v2 = d / "feed-v2"
        cls.v2.mkdir()
        cls.alerta = decision("10.10.20.24", ahora - 30, "ALERT", score=-0.60)
        (d / "motor_decision.log").write_text(json.dumps(cls.alerta) + "\n", encoding="utf-8")
        cls.peticion = d / "peticiones" / "preparar.json"
        cls.puerto = _puerto_libre()
        cls.proc = subprocess.Popen(
            [sys.executable, str(REPO / "scripts/engine/dashboard.py"),
             "--log-path", str(d / "motor_decision.log"), "--manifest-path", str(REPO / "artifacts/model/manifest.json"),
             "--detector-name", "ocsvm_scaled",
             "--schema", str(REPO / "configs/features/multilayer-v2.json"),
             "--schema-extra", str(REPO / "configs/features/multilayer-v3.json"),
             "--descripciones", str(REPO / "configs/features/descripciones.json"),
             "--cadena-v2-dir", str(cls.v2), "--peticion-preparar", str(cls.peticion),
             "--acuse-dir", str(d / "acuses"), "--feed-path", str(d / "feed-v1.json"),
             "--feed-estado", str(d / "estado-v1.json"), "--services", "",
             "--sin-autenticacion", "--host", "127.0.0.1", "--port", str(cls.puerto)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(120):
            try:
                cls.pedir("/api/decisions?limit=5")
                return
            except Exception:
                time.sleep(0.25)
        cls.proc.terminate()
        raise AssertionError("el panel no arrancó: %s" % (cls.proc.stdout.read() if cls.proc.stdout else ""))

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        cls.tmp.cleanup()

    @classmethod
    def pedir(cls, ruta, metodo="GET"):
        c = http.client.HTTPConnection("127.0.0.1", cls.puerto, timeout=10)
        c.request(metodo, ruta, headers={"X-CyberFlow": "1"})
        r = c.getresponse()
        return r.status, r.read()

    def decision_api(self):
        st, cuerpo = self.pedir("/api/decisions?limit=10")
        self.assertEqual(st, 200)
        return {d["entity_ip"]: d for d in json.loads(cuerpo)}["10.10.20.24"]

    def test_1_arranca_en_v2_con_incidencia_y_sin_politica_v1(self):
        st, cuerpo = self.pedir("/api/status")
        s = json.loads(cuerpo)
        self.assertTrue(s["cadena_v2"]["activa"])
        self.assertEqual(s["cadena_v2"]["estado"], "incidencia")
        self.assertTrue(any("traza.jsonl" in x for x in s["cadena_v2"]["incidencias"]))
        self.assertEqual((s["counters"]["limit"], s["counters"]["block"]), (0, 0))  # v1 habría dado LIMIT
        c = self.decision_api()["cadena_v2"]
        self.assertEqual((c["medida"]["estado"], c["aplicacion"]), ("fuente_ausente", "desconocido"))

    def test_2_preparar_demo_deshabilitado_sin_fuentes(self):
        st, cuerpo = self.pedir("/api/demo/preparar", "POST")
        self.assertEqual(st, 409)
        self.assertFalse(self.peticion.exists())
        st, html = self.pedir("/")
        self.assertEqual(st, 200)
        self.assertIn(b'id="prepBtn" hidden disabled', html)

    def test_3_las_fuentes_se_recuperan_sin_reiniciar(self):
        a = self.ahora
        escribir(self.v2, senales=[senal(self.alerta)],
                 traza=[publicacion(i + 1, a - 60 + 20 * i) for i in range(4)],
                 feed={"secuencia": 4, "generado": a, "entradas": []})
        c = self.decision_api()["cadena_v2"]
        self.assertEqual((c["if"]["estado"], c["medida"]["estado"], c["aplicacion"]),
                         ("senal", "no_publicada", "no_aplica"))
        time.sleep(db.STATUS_CACHE_S + 0.5)          # /api/status se cachea STATUS_CACHE_S
        s = json.loads(self.pedir("/api/status")[1])
        self.assertEqual(s["cadena_v2"]["politica"], "if_senal")
        self.assertEqual(s["cadena_v2"]["estado"], "ok")


if __name__ == "__main__":
    unittest.main()
