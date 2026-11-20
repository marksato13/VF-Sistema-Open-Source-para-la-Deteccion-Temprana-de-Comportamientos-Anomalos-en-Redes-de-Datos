#!/usr/bin/env python3
"""Deriva generar_campana_b.py del generar_campana.py firmado de A con el CAMBIO MÍNIMO: permiso ligado al episodio.
Con --permiso-por-episodio el permiso debe traer `episodio` == el siguiente episodio a lanzar; si no, es PAUSA. La cancelación
sigue valiendo siempre. Sin la opción, el comportamiento es idéntico al original. Cada sustitución debe aplicarse una vez.
Uso: hacer_generador_b.py <generar_campana.py> <salida>"""
import sys

SUST = [
    ("def leer_permiso(ruta: Path, nonce: str, arranque: float, ahora: float) -> tuple[str, str]:",
     "def leer_permiso(ruta: Path, nonce: str, arranque: float, ahora: float, siguiente: str | None = None,\n"
     "                 por_episodio: bool = False) -> tuple[str, str]:"),
    ('    if emitido < arranque - 5:\n',
     '    if por_episodio and p.get("episodio") != siguiente:      # campaña B: el permiso vale solo para ESE episodio\n'
     '        return "pausa", f"permiso para {p.get(\'episodio\')!r}, no para {siguiente!r}"\n'
     '    if emitido < arranque - 5:\n'),
    ("    def __init__(self, ruta: Path, nonce: str, max_espera: float, sondeo: float, marcas, arranque: float):",
     "    def __init__(self, ruta: Path, nonce: str, max_espera: float, sondeo: float, marcas, arranque: float,\n"
     "                 por_episodio: bool = False):"),
    ("        self.marcas, self.arranque = marcas, arranque\n",
     "        self.marcas, self.arranque = marcas, arranque\n        self.por_episodio = por_episodio\n"),
    ("            estado, motivo = leer_permiso(self.ruta, self.nonce, self.arranque, ahora)",
     "            estado, motivo = leer_permiso(self.ruta, self.nonce, self.arranque, ahora, siguiente, self.por_episodio)"),
    ('    ap.add_argument("--permiso-sondeo", type=float, default=5.0, help="s entre lecturas del permiso en pausa")\n',
     '    ap.add_argument("--permiso-sondeo", type=float, default=5.0, help="s entre lecturas del permiso en pausa")\n'
     '    ap.add_argument("--permiso-por-episodio", action="store_true",\n'
     '                    help="campaña B: el permiso debe nombrar al siguiente episodio (campo `episodio`)")\n'),
    ("    comp = (Compuerta(a.permiso, a.nonce, a.permiso_max_espera, a.permiso_sondeo, marcas, arranque)",
     "    comp = (Compuerta(a.permiso, a.nonce, a.permiso_max_espera, a.permiso_sondeo, marcas, arranque, a.permiso_por_episodio)"),
]


def main(origen, salida):
    t = open(origen, encoding="utf-8").read()
    mal = []
    for a, b in SUST:
        if t.count(a) != 1:
            mal.append((t.count(a), a[:60]))
        t = t.replace(a, b, 1)
    open(salida, "w", encoding="utf-8", newline="\n").write(t)
    print("sustituciones: %d, fallidas: %s" % (len(SUST), mal or "ninguna"))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
