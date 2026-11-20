#!/usr/bin/env python3
"""Quita secretos de una extraccion del laboratorio antes de publicarla (el repo es publico).

Uso:  python sanear.py <carpeta_extraccion>
      Reescribe los ficheros de texto en su sitio, borra los que no deben publicarse
      y termina con codigo 1 si tras sanear queda algo con pinta de secreto (no se commitea).

Que se quita:
- Cisco IOS: enable/username secret|password, snmp-server community, key-string, claves
  tacacs/radius, ppp/chap, wpa-psk, crypto key, lineas «password 7 ...».
- Ficheros de configuracion: password=, passwd=, secret=, token=, api_key=, psk=, PreSharedKey...
- Bloques PEM de clave privada (por si alguno se colara).
- ESXi .vmx: nada secreto salvo encryption.*/keySafe (se quitan).
Las IPs, MACs, nombres de equipo y usuarios del laboratorio se dejan: describen la topologia.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

R = "«REDACTADO»"
REGLAS: list[tuple[re.Pattern, str]] = [
    # Cisco
    (re.compile(r"^(\s*enable (?:secret|password)(?: \d+)?) \S+.*$", re.M), r"\1 " + R),
    (re.compile(r"^(\s*username \S+(?: privilege \d+)?(?: \S+)*? (?:secret|password)(?: \d+)?) \S+.*$", re.M), r"\1 " + R),
    (re.compile(r"^(\s*snmp-server community) \S+(.*)$", re.M), r"\1 " + R + r"\2"),
    (re.compile(r"^(\s*snmp-server host \S+(?: version \S+)?) \S+(.*)$", re.M), r"\1 " + R + r"\2"),
    (re.compile(r"^(\s*(?:key-string|key \d+|server-private \S+ key|tacacs-server key|radius-server key|"
                r"ppp chap password|wpa-psk ascii|ip ospf authentication-key|ip ospf message-digest-key \d+ md5|"
                r"standby \d+ authentication|ntp authentication-key \d+ md5))\s+\S+.*$", re.M), r"\1 " + R),
    (re.compile(r"^(\s*(?:password|secret)(?: \d+)?) \S+\s*$", re.M), r"\1 " + R),
    (re.compile(r"^(\s*key \d+ \S+) .*$", re.M), r"\1 " + R),
    (re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----).*?(-----END [A-Z ]*PRIVATE KEY-----)", re.S), r"\1\n" + R + r"\n\2"),
    (re.compile(r"(crypto pki certificate chain \S+\n)((?: .*\n)+)", re.M), r"\1 " + R + "\n"),
    # ficheros clave=valor / yaml / ini
    (re.compile(r"(?im)^(\s*[\w.-]*(?:password|passwd|secret|token|api[_-]?key|apikey|psk|presharedkey|"
                r"auth[_-]?key|private[_-]?key|tlspskidentity|community)[\w.-]*\s*[:=]\s*)(?!\s*$)(?!«)(.+)$"), r"\1" + R),
    (re.compile(r"(?i)(--(?:password|passwd|token|secret)[= ])\S+"), r"\1" + R),
    # VMware
    (re.compile(r'(?m)^((?:encryption|keySafe|dataFileKey)\S*\s*=\s*).*$'), r'\1"' + R + '"'),
]
# lineas que, si quedan tras sanear, bloquean la publicacion
SOSPECHOSO = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|(?i:(?:password|secret|passwd)\s*(?:7|5|8|9)\s+[A-Za-z0-9$./]{8,})"
    r"|(?i:\$[156y]\$[^\s:]{8,})|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bpa]-[0-9A-Za-z-]{10,}")
NUNCA = re.compile(r"(?i)(^|/)(shadow|gshadow|.*\.key|.*priv.*\.pem|id_(rsa|ed25519|ecdsa)(\..*)?|.*\.env|"
                   r".*\.p12|.*\.pfx|.*\.kdbx)$")


def main() -> int:
    raiz = Path(sys.argv[1])
    cambiados = borrados = 0
    for f in sorted(p for p in raiz.rglob("*") if p.is_file()):
        rel = f.relative_to(raiz).as_posix()
        if NUNCA.search(rel) and not rel.endswith(".pub"):
            f.unlink(); borrados += 1; print("borrado (no publicable):", rel); continue
        try:
            t = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            f.unlink(); borrados += 1; print("borrado (binario):", rel); continue
        if "PRIVATE KEY-----" in t:   # 20-nov: una clave.pem paso el filtro por nombre
            f.unlink(); borrados += 1; print("borrado (clave privada):", rel); continue
        n = t
        for pat, rep in REGLAS:
            n = pat.sub(rep, n)
        if n != t:
            f.write_text(n, encoding="utf-8", newline="\n"); cambiados += 1
    quedan = []
    for f in sorted(p for p in raiz.rglob("*") if p.is_file()):
        for i, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if SOSPECHOSO.search(linea):
                quedan.append("%s:%d: %s" % (f.relative_to(raiz).as_posix(), i, linea.strip()[:120]))
    print("ficheros saneados: %d · borrados: %d · sospechosos tras sanear: %d" % (cambiados, borrados, len(quedan)))
    for q in quedan[:50]:
        print("  SOSPECHOSO", q)
    return 1 if quedan else 0


if __name__ == "__main__":
    sys.exit(main())
