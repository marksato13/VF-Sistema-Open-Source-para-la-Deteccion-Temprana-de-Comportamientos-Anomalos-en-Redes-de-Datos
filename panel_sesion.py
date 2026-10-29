"""Copia temporal del panel (sesion de ataques) en 127.0.0.1:8799, solo lectura.

Igual que panel_local.py pero con temporizador largo (2.5 h) para cubrir toda
la bateria de ataques sin relanzar. Lee los argumentos de la unidad
ppi-dashboard, quita login/TLS y arranca el mismo codigo. No toca el servicio
real ni escribe nada.
"""
import os, shlex, subprocess, sys, threading
sys.path.insert(0, "scripts/engine")

unidad = subprocess.run(["systemctl", "cat", "ppi-dashboard"], capture_output=True, text=True).stdout
lineas, dentro = [], False
for l in unidad.splitlines():
    s = l.strip()
    if s.startswith("ExecStart="):
        dentro = True
        s = s[len("ExecStart="):]
    if dentro:
        lineas.append(s.rstrip("\\").strip())
        if not l.rstrip().endswith("\\"):
            break
args = shlex.split(" ".join(lineas))
i = next(k for k, a in enumerate(args) if a.endswith("dashboard.py"))
args = args[i + 1:]
QUITAR = {"--usuarios", "--clave-sesion", "--tls-cert", "--tls-key", "--auditoria", "--host", "--port",
          "--sesion-minutos", "--intentos-max", "--bloqueo-minutos"}
limpio, k = [], 0
while k < len(args):
    a = args[k]
    if a.split("=")[0] in QUITAR:
        k += 1 if "=" in a else 2
        continue
    limpio.append(a)
    k += 1
sys.argv = ["dashboard.py"] + limpio + ["--sin-autenticacion", "--host", "127.0.0.1", "--port", "8799"]
print("argumentos:", " ".join(a for a in limpio if a.startswith("--")), flush=True)
threading.Timer(18000, lambda: os._exit(0)).start()
import dashboard
sys.exit(dashboard.main())
