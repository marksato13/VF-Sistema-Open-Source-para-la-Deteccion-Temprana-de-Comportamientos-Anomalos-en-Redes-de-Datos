#!/usr/bin/env python3
"""Arma el paquete de la Campaña B con SHA256SUMS (sin copiarlo a ningún host). Uso: empaquetar_b.py <salida_dir>
Incluye herramientas y guiones de ejecución (no pruebas ni mutadores) y un MANIFIESTO con el contenido; las pruebas se
hashean aparte (SHA256SUMS-pruebas). Los LF se conservan tal cual (hash sobre bytes). rc 0 si todo se copió y verifica."""
import hashlib
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
EJECUCION = ["herramientas/d5_episodio.py", "herramientas/orquestar_b.py", "herramientas/registrar_alfa.py",
             "herramientas/analizar_b.py", "herramientas/compuerta_b.py", "herramientas/crear_manifiesto_alfa.py", "herramientas/verificar_umbral_motor.py", "generador/generar_campana_b.py", "generador/vigia_4c_b.py", "generador/esquema_campana.py", "guiones/g01b_lanzar_bateria_b.sh", "guiones/b_activar_srvdmz.sh", "guiones/b_revertir_srvdmz.sh",
             "guiones/b_r6_control.sh", "guiones/b_preflight_apartar_A.sh", "guiones/b_r7_sensor.sh"]
PRUEBAS = ["herramientas/hacer_g01b.py", "herramientas/hacer_vigia_b.py", "herramientas/mutar_vigia_b.py", "generador/vigia_4c_original.py", "herramientas/hacer_generador_b.py", "herramientas/arnes_integracion.py", "generador/generar_campana_original.py", "herramientas/empaquetar_b.py", "herramientas/mutar_analizar_b.py", "herramientas/mutar_d5.py"] + sorted(
    "tests/" + f for f in os.listdir(os.path.join(RAIZ, "tests")) if f.startswith("test_") and f.endswith(".py"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(salida):
    os.makedirs(salida, exist_ok=True)
    for grupo, nombre in ((EJECUCION, "SHA256SUMS"), (PRUEBAS, "SHA256SUMS-pruebas")):
        lineas = []
        for rel in grupo:
            dst = os.path.join(salida, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(RAIZ, rel), dst)
            lineas.append("%s  ./%s\n" % (sha(dst), rel))
        open(os.path.join(salida, nombre), "w", newline="\n").write("".join(lineas))
    mal = [rel for rel in EJECUCION + PRUEBAS if sha(os.path.join(salida, rel)) != sha(os.path.join(RAIZ, rel))]
    print("empaquetados %d archivos de ejecución y %d de pruebas en %s; diferencias: %s" % (len(EJECUCION), len(PRUEBAS), salida, mal or "ninguna"))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
