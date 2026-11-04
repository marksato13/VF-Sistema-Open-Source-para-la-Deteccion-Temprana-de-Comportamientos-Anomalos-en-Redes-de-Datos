"""Panel alineado con la cadena v2 (Etapa 4A, 4-nov-2026).

El panel ya no deduce la acción con la política v1: muestra lo que dejaron las fuentes
reales (señales del IF, regla del motor, traza del publicador v2, feed v2) y dice
«desconocido» o «sin evidencia» cuando una fuente falta. Casos exigidos en la 4A:
solo IF, regla con medida, sombra, fuente ausente y evidencia histórica de aplicación;
además, que la interfaz siga siendo de solo lectura.
"""
from __future__ import annotations

import http.client
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "engine"))

import cadena_v2  # noqa: E402
import dashboard as db  # noqa: E402

T0 = 1_793_760_000.0


def decision(ip, t, decision="PERMIT", score=-0.5, heur=None, did=None):
    d = {"event": "decision", "entity_ip": ip, "logged_at": t, "decision": decision,
         "decision_if": decision, "detector_name": "if_limpio_2026_10", "score": score,
         "threshold": -0.5694, "window_end_utc": "w%d" % int(t), "heuristico": heur,
         "heuristicos": [heur] if heur else []}
    d["decision_id"] = did or "%s|%s" % (ip, d["window_end_utc"])
    return d


def publicacion(sec, t, nuevos=(), entradas=()):
    return {"evento": "publicacion", "secuencia": sec, "generado": t, "publicado_en": t + 0.01,
            "expira": t + 60, "politica": "if_senal", "entradas": list(entradas), "nuevos": list(nuevos)}


def escribir(d: Path, senales=None, traza=None, feed=None):
    d.mkdir(parents=True, exist_ok=True)
    if senales is not None:
        (d / "senales-if.jsonl").write_text("".join(json.dumps(s) + "\n" for s in senales), encoding="utf-8")
    if traza is not None:
        (d / "traza.jsonl").write_text("".join(json.dumps(p) + "\n" for p in traza), encoding="utf-8")
    if feed is not None:
        (d / "feed.json").write_text(json.dumps(feed), encoding="utf-8")


class ConCadena(unittest.TestCase):
    modo = "sombra"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "feed-v2"
        self._previo = db._CADENA_V2

    def tearDown(self):
        db._CADENA_V2 = self._previo
        self.tmp.cleanup()

    def activar(self, modo=None):
        db._CADENA_V2 = cadena_v2.IndiceV2(self.dir, modo or self.modo)
        return db._CADENA_V2


class SoloIF(ConCadena):
    """Una anomalía del IF sin medida publicada NO es LIMIT (if_senal no publica el IF solo)."""

    def test_anomalia_if_sin_medida_no_es_accion(self):
        d = decision("10.10.20.24", T0 + 10, "ALERT", score=-0.58)
        escribir(self.dir, senales=[{"decision_id": d["decision_id"], "ip": d["entity_ip"], "score": -0.58,
                                     "alfa_superados": ["0.05"], "logged_at": T0 + 10}],
                 traza=[publicacion(1, T0), publicacion(2, T0 + 20)],
                 feed={"secuencia": 2, "generado": T0 + 20, "entradas": []})
        idx = self.activar()
        idx.anotar([d])
        c = d["cadena_v2"]
        self.assertEqual(c["if"]["estado"], "senal")
        self.assertEqual(c["medida"]["estado"], "no_publicada")
        self.assertEqual(c["aplicacion"], "no_aplica")
        self.assertIsNone(db.accion_de(d))
        cont = db.compute_counters([dict(d, logged_at=time.time())], detector_modelo="if_limpio_2026_10")
        self.assertEqual((cont["limit"], cont["block"]), (0, 0))
        self.assertEqual(db.acciones_vigentes([d], T0 + 30), [])

    def test_sin_v2_el_panel_v1_si_lo_marcaria_limit(self):
        # Control: sin la cadena v2, la política v1 del panel lo pintaba LIMIT (el defecto que se corrige).
        db._CADENA_V2 = None
        d = decision("10.10.20.24", T0 + 10, "ALERT", score=-0.58)
        self.assertEqual(db.accion_de(d)[0], "LIMIT")


class ReglaConMedida(ConCadena):
    def _preparar(self):
        heur = {"heuristico": "port_scan", "accion": "BLOCK", "motivo": "40 puertos"}
        d = decision("10.10.20.30", T0 + 10, "PERMIT", heur=heur)
        item = {"evento_id": d["decision_id"] + "|port_scan", "decision_id": d["decision_id"],
                "ip": "10.10.20.30", "regla": "port_scan", "tipo": "nueva", "accion": "BLOCK",
                "id": "e1", "hasta": T0 + 310, "destino": "srv-dmz"}
        escribir(self.dir, senales=[], traza=[publicacion(1, T0), publicacion(2, T0 + 20, [item], ["e1"])],
                 feed={"secuencia": 2, "generado": T0 + 20,
                       "entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": T0 + 310, "id": "e1",
                                     "evento_id": item["evento_id"], "detector": "port_scan",
                                     "motivo": "port_scan: 40 puertos", "nivel": 1, "destino": "srv-dmz"}]})
        return d

    def test_la_medida_publicada_es_la_accion_y_es_propuesta_en_sombra(self):
        d = self._preparar()
        self.activar("sombra").anotar([d])
        a = db.accion_de(d)
        self.assertEqual(a[0], "BLOCK")
        self.assertIn("propuesta en sombra", a[1])
        self.assertEqual(a[2], "port_scan")
        c = d["cadena_v2"]
        self.assertEqual((c["medida"]["estado"], c["medida"]["secuencia"], c["medida"]["id"]), ("nueva", 2, "e1"))
        self.assertTrue(c["propuesta"])
        self.assertEqual((c["agente"], c["aplicacion"], c["efecto"]), ("desconocido", "no_ejecutada", "sin_evidencia"))
        self.assertEqual(c["reglas"][0]["regla"], "port_scan")
        v = db.acciones_vigentes([d], T0 + 30)
        self.assertEqual(len(v), 1)
        self.assertEqual((v[0]["fuente"], v[0]["estado_respuesta"], v[0]["aplicacion"]),
                         ("feed_v2", "propuesta (sombra)", "no_ejecutada"))

    def test_en_modo_activo_sin_evidencia_la_aplicacion_es_desconocida(self):
        d = self._preparar()
        self.activar("activo").anotar([d])
        self.assertFalse(d["cadena_v2"]["propuesta"])
        self.assertEqual(d["cadena_v2"]["aplicacion"], "desconocido")
        self.assertEqual(db.acciones_vigentes([d], T0 + 30)[0]["aplicacion"], "desconocido")

    def test_rechazada_y_sin_punto_no_son_accion(self):
        d = decision("10.10.20.31", T0 + 10, "ALERT", heur=None)
        d["detector_name"] = "auth_failure_heuristic"
        item = {"decision_id": d["decision_id"], "ip": "10.10.20.31", "regla": "auth_failure_heuristic",
                "tipo": "rechazada", "accion": "BLOCK", "id": None, "hasta": None, "motivo_rechazo": "sin_vista_http"}
        escribir(self.dir, senales=[], traza=[publicacion(1, T0), publicacion(2, T0 + 20, [item])],
                 feed={"secuencia": 2, "generado": T0 + 20, "entradas": []})
        self.activar().anotar([d])
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "rechazada")
        self.assertIsNone(db.accion_de(d))

    def test_varias_decisiones_cada_una_con_su_id(self):
        d = self._preparar()
        otra = decision("10.10.20.30", T0 + 15, "PERMIT")
        self.activar().anotar([d, otra])
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "nueva")
        self.assertEqual(otra["cadena_v2"]["medida"]["estado"], "no_publicada")


class FuenteAusente(ConCadena):
    def test_sin_senales_ni_traza_todo_desconocido_y_sin_fallback_v1(self):
        escribir(self.dir, feed={"secuencia": 1, "generado": T0, "entradas": []})
        d = decision("10.10.20.24", T0 + 10, "ALERT", score=-0.58)
        idx = self.activar()
        idx.anotar([d])
        c = d["cadena_v2"]
        self.assertEqual(c["if"]["estado"], "desconocido")
        self.assertEqual(c["medida"]["estado"], "desconocido")
        self.assertIsNone(db.accion_de(d))           # NO vuelve a la política v1 (LIMIT)
        r = idx.resumen(T0 + 20)
        self.assertFalse(r["fuentes"]["traza"]["ok"])
        self.assertFalse(r["fuentes"]["senales_if"]["ok"])
        self.assertEqual(r["agente"]["estado"], "desconocido")

    def test_ventana_sin_score_es_sin_puntuar_no_desconocida(self):
        escribir(self.dir, senales=[], traza=[publicacion(1, T0), publicacion(2, T0 + 20)], feed={"entradas": []})
        d = decision("10.10.20.21", T0 + 10, "PERMIT", score=None)
        self.activar().anotar([d])
        self.assertEqual(d["cadena_v2"]["if"]["estado"], "sin_puntuar")
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "no_publicada")

    def test_decision_fuera_de_la_cobertura_de_la_traza_es_desconocida(self):
        escribir(self.dir, senales=[], traza=[publicacion(1, T0 + 100), publicacion(2, T0 + 110)],
                 feed={"secuencia": 2, "generado": T0 + 110, "entradas": []})
        antes = decision("10.10.20.24", T0 + 10, "ALERT")     # anterior a la traza leída
        despues = decision("10.10.20.24", T0 + 200, "ALERT")  # posterior a la última publicación
        self.activar().anotar([antes, despues])
        self.assertEqual(antes["cadena_v2"]["medida"]["estado"], "desconocido")
        self.assertEqual(despues["cadena_v2"]["medida"]["estado"], "desconocido")

    def test_feed_ilegible_no_inventa_vigentes(self):
        escribir(self.dir, senales=[], traza=[publicacion(1, T0)])
        (self.dir / "feed.json").write_text("{roto", encoding="utf-8")
        idx = self.activar()
        self.assertEqual(idx.vigentes(T0), [])
        r = idx.resumen(T0)
        self.assertFalse(r["fuentes"]["feed"]["ok"])
        self.assertTrue(r["feed_atrasado"])

    def test_recarga_cuando_crece_la_traza(self):
        d = decision("10.10.20.30", T0 + 10, "PERMIT")
        escribir(self.dir, senales=[], traza=[publicacion(1, T0)], feed={"entradas": []})
        idx = self.activar()
        idx.anotar([d])
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "desconocido")   # aún sin publicar
        time.sleep(0.02)
        with open(self.dir / "traza.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(publicacion(2, T0 + 20)) + "\n")
        idx.anotar([d])
        self.assertEqual(d["cadena_v2"]["medida"]["estado"], "no_publicada")


def _bloque_js(script: str, nombre: str) -> str:
    """Extrae «function nombre(...) {...}» o «const NOMBRE = ...;» del JS servido."""
    m = re.search(r"(?:^|\n)(function %s\(.*?\)\s*\{)" % re.escape(nombre), script)
    if m:
        i = script.index("{", m.start(1))
        prof = 0
        for j in range(i, len(script)):
            prof += {"{": 1, "}": -1}.get(script[j], 0)
            if prof == 0:
                return script[m.start(1):j + 1]
    m = re.search(r"\n(const %s = .*?;)[ \t]*(?://[^\n]*)?\n" % re.escape(nombre), script, re.S)
    if m:
        return m.group(1)
    raise AssertionError("no está en el JS servido: " + nombre)


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "sin node: la comprobación del JS no se puede omitir en el cierre de la 4A")
class JsDelPanel(unittest.TestCase):
    """La lógica del navegador, ejecutada con Node sobre el JS que sirve el panel."""

    @classmethod
    def setUpClass(cls):
        html = db.html_por_rol(db.HTML, "admin")
        cls.script = html.split("<script>", 1)[1].split("</script>", 1)[0]

    def test_sintaxis(self):
        subprocess.run([NODE, "--check", "-"], input=self.script, text=True, encoding="utf-8",
                       check=True, capture_output=True, timeout=30)

    def test_comportamiento(self):
        piezas = [_bloque_js(self.script, n) for n in (
            "MODELO_SOLO_ACTUA", "NUNCA_BLOQUEAR_JS", "esInfraProtegida", "MEDIDAS_V2", "medidaV2",
            "accionDeDecision", "TXT_MEDIDA_V2", "cadenaV2HTML", "estadoEnHosts")]
        prueba = r"""
let ACUSES = [], ACUSES_V1_HISTORICOS = false;
const varEsc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
%s
const ok = (c, m) => { if (!c) { console.error('FALLO: ' + m); process.exitCode = 1; } };
// solo IF: ALERT del modelo con cadena v2 y sin medida -> PERMIT (con v1 seria LIMIT)
const soloIf = {decision: 'ALERT', detector_name: 'if_limpio_2026_10', entity_ip: '10.10.20.24',
  cadena_v2: {if: {estado: 'senal', score: -0.58, alfa_superados: ['0.05']}, reglas: [], decision: 'ALERT',
  medida: {estado: 'no_publicada'}, propuesta: false, agente: 'desconocido', aplicacion: 'no_aplica', efecto: 'sin_evidencia'}};
ok(accionDeDecision(soloIf) === 'PERMIT', 'IF solo no es LIMIT');
ok(accionDeDecision(Object.assign({}, soloIf, {cadena_v2: undefined})) === 'LIMIT', 'control v1: LIMIT');
// regla con medida publicada (sombra)
const regla = {decision: 'PERMIT', entity_ip: '10.10.20.30', heuristico: {heuristico: 'port_scan', accion: 'BLOCK'},
  cadena_v2: {if: {estado: 'sin_senal'}, reglas: [{regla: 'port_scan', accion: 'BLOCK'}], decision: 'PERMIT',
  medida: {estado: 'nueva', accion: 'BLOCK', secuencia: 7}, propuesta: true, agente: 'desconocido',
  aplicacion: 'no_ejecutada', efecto: 'sin_evidencia'}};
ok(accionDeDecision(regla) === 'BLOCK', 'medida publicada = BLOCK');
const h = cadenaV2HTML(regla);
ok(h.includes('propuesta (sombra)') && h.includes('no ejecutada (modo sombra)') && h.includes('sin evidencia'), 'detalle sombra');
ok(h.includes('feed n.º 7'), 'correlación con la secuencia del feed');
// medida rechazada / sin punto -> PERMIT; fuente ausente -> desconocido
ok(accionDeDecision({cadena_v2: {medida: {estado: 'rechazada', accion: 'BLOCK'}}}) === 'PERMIT', 'rechazada');
const desc = cadenaV2HTML({cadena_v2: {if: {estado: 'desconocido'}, reglas: [], medida: {estado: 'desconocido'}, aplicacion: 'no_aplica'}});
ok(desc.includes('desconocido · la traza v2 no cubre') && desc.includes('1 · Señal IF</dt><dd>desconocido'), 'fuente ausente');
// evidencia historica de aplicacion (acuse v1 con agente v1 parado)
ACUSES = [{host: 'srv-dmz', reglas: {'10.10.20.30': {accion: 'BLOCK'}}, atrasado: false}];
ACUSES_V1_HISTORICOS = true;
ok(estadoEnHosts('10.10.20.30').includes('aplicación v1 (histórica): srv-dmz: BLOCK'), 'acuse v1 histórico');
ok(estadoEnHosts('10.10.20.99').includes('sin evidencia de aplicación'), 'sin acuse = sin evidencia');
ok(!estadoEnHosts('10.10.20.30').includes('aplicado'), 'no se afirma aplicación actual');
ACUSES_V1_HISTORICOS = false;
ok(estadoEnHosts('10.10.20.30').includes('BLOCK aplicado'), 'sin v2 el acuse se lee como antes');
""" % "\n".join(piezas)
        r = subprocess.run([NODE, "-"], input=prueba, text=True, encoding="utf-8", capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)


def _puerto_libre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class ServidorSoloLectura(unittest.TestCase):
    """Servidor real (HTTP, sin autenticación) con la cadena v2: API y escritura deshabilitada."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        ahora = time.time()
        cls.v2 = d / "feed-v2"
        ifd = decision("10.10.20.24", ahora - 30, "ALERT", score=-0.58)
        heur = {"heuristico": "port_scan", "accion": "BLOCK", "motivo": "40 puertos"}
        reg = decision("10.10.20.30", ahora - 25, "PERMIT", heur=heur)
        item = {"evento_id": reg["decision_id"] + "|port_scan", "decision_id": reg["decision_id"], "ip": "10.10.20.30",
                "regla": "port_scan", "tipo": "nueva", "accion": "BLOCK", "id": "e1", "hasta": ahora + 300}
        escribir(cls.v2, senales=[{"decision_id": ifd["decision_id"], "ip": ifd["entity_ip"], "score": -0.58,
                                   "alfa_superados": ["0.05"], "logged_at": ahora - 30}],
                 traza=[publicacion(1, ahora - 60), publicacion(2, ahora - 20, [item], ["e1"])],
                 feed={"secuencia": 2, "generado": ahora - 20, "entradas": [
                     {"ip": "10.10.20.30", "accion": "BLOCK", "hasta": ahora + 300, "id": "e1", "detector": "port_scan",
                      "motivo": "port_scan: 40 puertos", "nivel": 1, "evento_id": item["evento_id"]}]})
        cls.log = d / "motor_decision.log"
        cls.log.write_text("".join(json.dumps(x) + "\n" for x in (ifd, reg)), encoding="utf-8")
        cls.peticion = d / "peticiones" / "preparar.json"
        cls.puerto = _puerto_libre()
        cls.proc = subprocess.Popen(
            [sys.executable, str(REPO / "scripts/engine/dashboard.py"),
             "--log-path", str(cls.log), "--manifest-path", str(REPO / "artifacts/model/manifest.json"),
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

    def test_decisiones_llevan_la_cadena_v2(self):
        st, cuerpo = self.pedir("/api/decisions?limit=10")
        self.assertEqual(st, 200)
        por_ip = {d["entity_ip"]: d for d in json.loads(cuerpo)}
        self.assertEqual(por_ip["10.10.20.24"]["cadena_v2"]["medida"]["estado"], "no_publicada")
        self.assertEqual(por_ip["10.10.20.24"]["cadena_v2"]["if"]["estado"], "senal")
        self.assertEqual(por_ip["10.10.20.30"]["cadena_v2"]["medida"]["estado"], "nueva")

    def test_status_vigentes_son_propuestas_y_resume_las_fuentes(self):
        st, cuerpo = self.pedir("/api/status")
        self.assertEqual(st, 200)
        s = json.loads(cuerpo)
        self.assertTrue(s["cadena_v2"]["activa"])
        self.assertEqual(s["cadena_v2"]["politica"], "if_senal")
        self.assertTrue(s["acuses_v1_historicos"])
        self.assertEqual([(v["ip"], v["estado_respuesta"]) for v in s["vigentes"]], [("10.10.20.30", "propuesta (sombra)")])
        self.assertEqual((s["counters"]["limit"], s["counters"]["block"]), (0, 1))

    def test_escenario_no_marca_limit_por_el_if(self):
        st, cuerpo = self.pedir("/api/escenario?ip=10.10.20.24&desde=%d" % (time.time() - 120))
        filas = json.loads(cuerpo)["decisiones"]
        self.assertTrue(filas)
        self.assertEqual({f["accion"] for f in filas}, {"PERMIT"})

    def test_preparar_demo_deshabilitado_y_sin_escritura(self):
        st, cuerpo = self.pedir("/api/demo/preparar", "POST")
        self.assertEqual(st, 409)
        self.assertIn("solo lectura", json.loads(cuerpo)["motivo"])
        self.assertFalse(self.peticion.exists())


if __name__ == "__main__":
    unittest.main()
