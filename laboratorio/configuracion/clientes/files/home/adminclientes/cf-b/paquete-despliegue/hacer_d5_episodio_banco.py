#!/usr/bin/env python3
"""DECISIÓN E (autorizada solo para banco): deriva `d5_episodio_banco.py` de la COPIA de `d5_episodio.py` con D5 sin reinicio. Solo banco, datos
sintéticos, sin conexión al orquestador del laboratorio. No instala nada y no modifica el original.

Qué cambia (3 sustituciones exactas, cada una una sola vez):
 1. Nota en el docstring: copia de banco.
 2. Puerta.una_vez: la frescura del feed se mide desde el INSTANTE DE LA SOLICITUD (`t_limpio` que devuelve la limpieza) y no desde que vuelve
    la limpieza: sin reinicio el publicador republica antes de acusar, así que el feed «nuevo» es anterior al retorno.
 3. Antes de la CLI se añaden: `limpiar_sin_reinicio` (sustituye a `sensor_limpiar`: solicita la limpieza por el canal de control y exige un ACUSE),
    `RunnersBanco` (sensor/srv con ayudante nft inyectable) y `PuertaBanco` (BLOQUEO tras cualquier fallo o resultado incierto; las llamadas
    siguientes conservan la evidencia y NO emiten solicitudes; una reanudación exige decisión manual registrada: quién y por qué).
Efecto en la campaña real: el reintento automático de la puerta (que repetía la limpieza) deja de existir; tras un fallo la puerta espera una
decisión manual. Resolver la espera de la puerta (Hallazgo 2) es una decisión aparte.
Uso: hacer_d5_episodio_banco.py <d5_episodio.py> <salida>."""
import sys

NUEVO = '''# ------------------------------------------------------------------ BANCO: D5 sin reinicio (decisión E, solo banco)
def limpiar_sin_reinicio(adaptador, origen, real, ahora=time.time):
    """Sustituye a `sensor_limpiar`: pide la limpieza por el canal de control (adaptador aislado) y SOLO un acuse válido devuelve ok.
    `t_limpio` = instante de la solicitud (el feed posterior es el «nuevo»). Sin acuse, o con resultado incierto: ok False con la evidencia."""
    if origen != ORIGEN:
        return {"ok": False, "rc": 2, "motivo": "la limpieza D5 solo admite el origen del experimento %s" % ORIGEN}
    t = ahora()
    base = {"t": t, "t_limpio": t, "origen": origen, "modo": "real" if real else "seco"}
    if not real:
        return dict(base, ok=True, rc=0, hay_que_quitar=None)
    r = adaptador.limpiar(origen)
    if r["ok"]:
        q = r.get("quitado") or {}
        return dict(base, ok=True, rc=0, quitado=q, hay_que_quitar=bool(q.get("vigentes") or q.get("escalada")), secuencia=r.get("secuencia"),
                    acuse=True, duplicada=bool(r.get("duplicada")))
    return dict(base, ok=False, rc=r.get("rc") or 1, incierto=bool(r.get("incierto")), publicacion=r.get("publicacion"), secuencia=r.get("secuencia"),
                evidencia=r.get("evidencia"), traza_auditoria=r.get("traza_auditoria"),
                motivo="sin acuse válido: %s%s" % (r.get("estado"), (" / " + r["categoria"]) if r.get("categoria") else ""))


class RunnersBanco:
    """Los `runners` de `Puerta` para el banco: sensor (limpiar/feed) con el adaptador y el feed local; srv (nft/retirar/agente) con un ayudante inyectable."""

    def __init__(self, adaptador, feed_p, traza_p, helper, real=True, ahora=time.time):
        self.adaptador, self.feed_p, self.traza_p, self.helper, self.real, self.ahora = adaptador, feed_p, traza_p, helper, real, ahora

    def sensor(self, cmd, **kw):
        if cmd == "limpiar":
            return limpiar_sin_reinicio(self.adaptador, kw["origen"], self.real, self.ahora)
        if cmd == "feed":
            return sensor_feed(self.feed_p, kw["origen"], kw["desde"], self.ahora)
        raise ValueError(cmd)

    def srv(self, cmd, **kw):
        if cmd == "nft":
            return srv_nft(kw["origen"], self.helper)
        if cmd == "retirar":
            return srv_retirar(kw["origen"], self.real, self.helper)
        if cmd == "agente":
            return srv_agente(self.traza_p, kw["origen"], kw["desde"])
        raise ValueError(cmd)


class PuertaBanco(Puerta):
    """Puerta con BLOQUEO: solo un acuse válido (y el resto de comprobaciones) deja pasar. Tras cualquier `lista = False` queda bloqueada:
    las llamadas siguientes devuelven la evidencia del caso y NO emiten solicitudes (ni con id nuevo). `reanudar_manual` exige quién y por qué.
    La puerta REAL crea una `Puerta` nueva en cada llamada (`compuerta_b.puerta_fn`) y el proceso puede reiniciarse: por eso, con `estado_bloqueo`,
    el bloqueo vive en un FICHERO (escritura atómica) y un cerrojo `flock` serializa las instancias; un fichero ilegible cuenta como bloqueado."""

    def __init__(self, runners, registro=None, estado_bloqueo=None, **kw):
        super().__init__(runners, **kw)
        self.registro, self.estado_bloqueo = registro, estado_bloqueo
        self.bloqueada, self.intentos_de_puerta, self.omitidas = None, 0, 0

    def _log(self, reg):
        if self.registro is not None:
            with open(self.registro, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(dict(reg, t=self.ahora()), sort_keys=True, default=str) + "\\n")

    def _cerrojo(self):
        if not self.estado_bloqueo:
            return None
        try:
            import fcntl
        except ImportError:                                   # pragma: no cover (solo Linux)
            return None
        fh = open(self.estado_bloqueo + ".lock", "a")
        fcntl.flock(fh, fcntl.LOCK_EX)
        return fh

    def _bloqueo_actual(self):
        if self.estado_bloqueo and os.path.exists(self.estado_bloqueo):
            try:
                with open(self.estado_bloqueo, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return {"motivos": ["fichero de bloqueo ilegible: se trata como bloqueado"], "pasos": [], "ilegible": True}
        return self.bloqueada

    def _fijar_bloqueo(self, res):
        self.bloqueada = res
        if self.estado_bloqueo:
            tmp = self.estado_bloqueo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True, default=str))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.estado_bloqueo)

    def una_vez(self):
        cerrojo = self._cerrojo()
        try:
            b = self._bloqueo_actual()
            if b is not None:
                self.bloqueada = b
                self.omitidas += 1
                self._log({"evento": "omitida_por_puerta_bloqueada", "motivos": b.get("motivos")})
                return {"lista": False, "bloqueada": True, "pasos": [], "evidencia_del_caso": b,
                        "motivos": ["puerta bloqueada tras un caso fallido o incierto: requiere reanudación manual registrada"]}
            self.intentos_de_puerta += 1
            res = super().una_vez()
            self._log({"evento": "puerta_lista" if res["lista"] else "puerta_bloqueada", "motivos": res.get("motivos"), "pasos": [p["paso"] for p in res.get("pasos", [])]})
            if not res["lista"]:
                self._fijar_bloqueo(res)
            return res
        finally:
            if cerrojo:
                cerrojo.close()

    def preparar_episodio(self, intentos=5, espera_entre=30.0, auditoria=None):
        """Un solo intento: no hay reintento automático (repetiría la solicitud)."""
        res = self.una_vez()
        res["intento"], res["t"] = 1, self.ahora()
        if auditoria:
            with open(auditoria, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True, default=str) + "\\n")
        return {"lista": res["lista"], "intentos": 1, "historial": [res], "bloqueada": self._bloqueo_actual() is not None}

    def reanudar_manual(self, quien, motivo):
        if not str(quien).strip() or not str(motivo).strip():
            raise ValueError("la reanudación requiere quién la decide y por qué")
        cerrojo = self._cerrojo()
        try:
            b = self._bloqueo_actual()
            if b is None:
                raise ValueError("no hay un bloqueo que reanudar")
            self._log({"evento": "reanudacion_manual", "por": quien, "motivo": motivo,
                       "caso_bloqueado": [p.get("evidencia") for p in b.get("pasos", []) if p.get("evidencia")]})
            if self.estado_bloqueo and os.path.exists(self.estado_bloqueo):                  # el caso bloqueado se ARCHIVA, no se borra
                os.replace(self.estado_bloqueo, "%s.reanudado-%d.json" % (self.estado_bloqueo, int(self.ahora() * 1000)))
            self.bloqueada = None
        finally:
            if cerrojo:
                cerrojo.close()


def puerta_fn_banco(directorio, runners, **kw):
    """Equivale al `puerta_fn` de `compuerta_b.puerta` (que crea una Puerta NUEVA en cada llamada): el bloqueo persiste en `puerta-bloqueo.json`."""
    return PuertaBanco(runners, registro=os.path.join(directorio, "puerta-banco.jsonl"), estado_bloqueo=os.path.join(directorio, "puerta-bloqueo.json"),
                       **kw).preparar_episodio(auditoria=os.path.join(directorio, "puertas-D5.jsonl"))

'''
MARCA_CLI = "# ------------------------------------------------------------------ CLI"
SUST = [
    ('"""Limpieza D5 por episodio de la Campaña B. Solo biblioteca estándar.\n',
     '"""[COPIA DE BANCO: D5 sin reinicio, decisión E; no instalada, no conectada al orquestador]\nLimpieza D5 por episodio de la Campaña B. Solo biblioteca estándar.\n'),
    ("        t_limpio = self.ahora()\n", '        t_limpio = r.get("t_limpio", self.ahora())          # BANCO: desde la solicitud, no desde el retorno\n'),
    (MARCA_CLI, NUEVO + MARCA_CLI),
]


def main(origen, salida):
    t = open(origen, encoding="utf-8").read()
    mal = []
    for a, b in SUST:
        if t.count(a) != 1:
            mal.append((t.count(a), a[:60]))
        t = t.replace(a, b, 1)
    if salida == "-":                                           # solo lectura: el derivado va a stdout (los guiones de aceptación lo comparan sin escribir nada)
        sys.stdout.write(t)
        print("sustituciones: %d, fallidas: %s" % (len(SUST), mal or "ninguna"), file=sys.stderr)
    else:
        open(salida, "w", encoding="utf-8", newline="\n").write(t)
        print("sustituciones: %d, fallidas: %s" % (len(SUST), mal or "ninguna"))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
