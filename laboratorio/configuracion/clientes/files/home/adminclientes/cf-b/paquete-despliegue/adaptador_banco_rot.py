#!/usr/bin/env python3
"""PROPUESTA DE BANCO (#3): adaptador de prueba que reconcilia con la auditoría REPARTIDA en generaciones rotadas. Hereda del adaptador
validado (adaptador_banco.py, sin cambios) y solo sustituye el diagnóstico. Sigue aislado: no se conecta a d5_episodio.py ni al orquestador.

Reglas (iguales a las del adaptador validado, más la rotación):
 - UNA solicitud por llamada; si el acuse falta o es incierto NO se emite otra (ni con id nuevo): fallida, evidencia conservada.
 - consumido + publicado del MISMO id, estén en el mismo fichero o en generaciones distintas  -> consumida_y_publicada (determinada).
 - consumido rechazado -> consumida_rechazada (determinada). Control aún presente / retirado por el cliente -> no_consumida (determinada).
 - consumido sin publicado -> consumida_sin_publicacion (INCIERTA).
 - publicado SIN consumido (falta parte de la traza, p. ej. una generación rotada ya borrada) -> indeterminada: no se afirma nada.
 - sin líneas del id, auditoría ausente, ilegible, directorio o fuera de retención -> indeterminada.
 - Todo lo que no es determinado es FALLIDO, conserva la traza (resultado + copia de las generaciones de la auditoría) y no reintenta."""
import os
import shutil
import time

import adaptador_banco as ab
import auditoria_d5 as A


def diagnosticar_rot(control, id_, origen, feed, estado, traza, auditoria=None, retiro_del_cliente=False, ahora=time.time, **kw):
    r = ab.diagnosticar(control, id_, origen, feed, estado, traza, None, retiro_del_cliente, ahora)
    aud = A.leer(auditoria, **kw) if auditoria else None
    r["auditoria_disponible"] = bool(aud and aud["generaciones"])
    r["auditoria"] = None if aud is None else {k: aud[k] for k in ("generaciones", "ilegibles", "problemas", "estable", "intentos")}
    lin = [x for x in (aud["lineas"] if aud else []) if x.get("id") == id_]
    cons = [x for x in lin if x.get("evento") == "consumido"]
    pub = [x for x in lin if x.get("evento") == "publicado"]
    r["auditoria_del_id"] = lin
    r["motivo"] = None
    if r["control_presente"] or retiro_del_cliente:
        r.update(categoria="no_consumida", determinada=True, secuencia_publicada=None, trazabilidad="no_aplica")
    elif cons and not cons[-1].get("ok"):
        r.update(categoria="consumida_rechazada", determinada=True, secuencia_publicada=None, trazabilidad="completa")
    elif cons and pub:
        r.update(categoria="consumida_y_publicada", determinada=True, secuencia_publicada=pub[-1].get("secuencia"),
                 trazabilidad="completa", generaciones_del_id=sorted({x["_gen"] for x in cons + pub}))
        r["feed_posterior_o_igual"] = (r["feed"]["secuencia"] or 0) >= (pub[-1].get("secuencia") or 0)
    elif cons:
        r.update(categoria="consumida_sin_publicacion", determinada=False, secuencia_publicada=None, trazabilidad="incompleta",
                 motivo="hay `consumido` y no hay `publicado` (ilegible, fuera de retención o nunca escrito)")
    elif pub:
        r.update(categoria="indeterminada", determinada=False, secuencia_publicada=None, trazabilidad="incompleta",
                 motivo="hay `publicado` sin `consumido`: falta parte de la traza; no se afirma nada")
    else:
        why = ("auditoría ausente" if aud is None or not aud["generaciones"] else "auditoría con problemas: " + "; ".join(aud["problemas"])
               if aud["problemas"] else "líneas ilegibles en la auditoría (%d)" % aud["ilegibles"] if aud["ilegibles"]
               else "sin líneas de ese id (fuera de retención o no escrita)")
        r.update(categoria="indeterminada", determinada=False, secuencia_publicada=None, trazabilidad="incompleta", motivo=why)
    # Registro explícito: solo `consumida_y_publicada` confirma la publicación; con traza faltante o incompleta queda «publicación sin confirmar»
    r["publicacion"] = ("confirmada" if r["categoria"] == "consumida_y_publicada"
                        else "no_aplica" if r["categoria"] in ("no_consumida", "consumida_rechazada") else "publicación sin confirmar")
    return r


class AdaptadorBancoRot(ab.AdaptadorBanco):
    def limpiar(self, origen):
        r = ab.cli.solicitar_reset(self.control, origen, self.esperar_s, ahora=self.ahora, dormir=self.dormir, sondeo=self.sondeo)
        if r["ok"]:
            return {"ok": True, "rc": 0, "estado": "acuse", "incierto": False, "secuencia": r.get("secuencia"), "duplicada": r.get("duplicada", False),
                    "quitado": r.get("quitado")}
        if r["estado"] == "pendiente_previa":
            return {"ok": False, "rc": r["rc"], "estado": r["estado"], "incierto": False, "evidencia": None}
        d = diagnosticar_rot(self.control, r.get("id"), origen, self.feed, self.estado, self.traza, self.auditoria,
                             retiro_del_cliente=(r["estado"] == "sin_acuse_no_procesada"), ahora=self.ahora)
        ev = ab._guardar_evidencia(self.control, r.get("id"), {"resultado_cliente": r, "diagnostico": d})
        copia = None
        if self.auditoria is not None:                              # la traza se conserva: copia cruda de cada generación legible
            copia = ev[:-5] + ".auditoria"
            os.makedirs(copia, exist_ok=True)
            for p in A.generaciones(self.auditoria):
                if os.path.isfile(p):
                    shutil.copy2(p, copia)
        return {"ok": False, "rc": r["rc"], "estado": r["estado"], "categoria": d["categoria"], "determinada": d["determinada"],
                "incierto": not d["determinada"], "evidencia": ev, "traza_auditoria": copia, "secuencia": d["secuencia_publicada"],
                "id": r.get("id"), "motivo": d["motivo"], "trazabilidad": d["trazabilidad"], "publicacion": d["publicacion"]}
