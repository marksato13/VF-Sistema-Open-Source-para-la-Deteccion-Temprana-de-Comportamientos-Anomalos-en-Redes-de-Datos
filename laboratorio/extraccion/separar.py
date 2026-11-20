# Separa la parte publicable (solo CyberFlow) de una extraccion saneada; el resto queda en la copia privada.
# Uso: python separar.py <extraccion> <destino_publico> <copia_privada>
import shutil, re, sys
from pathlib import Path
src, pub, priv = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
for d in (pub, priv):
    if d.exists(): shutil.rmtree(d)
shutil.copytree(src, priv)                      # copia completa, privada
VMS = {"SENSOR1-CYBERFLOW","SENSOR2-CYBERFLOW","SRV-DMZ-CYBERFLOW","VM-SURICATA-CYBERFLOW","LAB-ATACANTE","LAB-CLIENTES"}
BAST_HOME = re.compile(r"^(0[6-9]|1[0-5])-.*|relay-feed\.sh|orq\.sh$")
n = 0
for f in sorted(p for p in src.rglob("*") if p.is_file()):
    rel = f.relative_to(src).as_posix(); eq = rel.split("/")[0]; resto = rel[len(eq)+1:]
    if eq in ("sensor1","sensor2","srvdmz","kali","clientes","suricata"):
        if resto.endswith("authorized_keys") or resto.endswith("authorized_keys.sha256"): continue
        ok = True
    elif eq == "bastion":
        ok = (resto.startswith(("sistema/","paquetes/","red/ip-","red/escucha","red/resolv"))
              or re.match(r"servicios/unidad-ppi-", resto)
              or re.match(r"files/etc/systemd/system/ppi-", resto)
              or resto.startswith("files/opt/cyberflow/")
              or (resto.startswith("files/home/gadmin/") and "/" not in resto[18:] and BAST_HOME.match(resto[18:])))
    elif eq.startswith("sw-"):
        ok = resto in ("version.txt","vlan-brief.txt","interfaces-trunk.txt","monitor-session-all.txt","etherchannel-summary.txt","inventory.txt")
    elif eq.startswith("esxi-"):
        vms = src / eq / "vms.txt"
        tiene = any(v in (vms.read_text(errors="replace") if vms.exists() else "") for v in VMS)
        ok = tiene and (resto in ("version.txt","host.txt") or (resto.startswith("vmx/") and Path(resto).stem in VMS))
    else:
        ok = rel == "_registro.txt"
    if ok:
        out = pub / rel; out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, out); n += 1
# los esxi sin VMs de CyberFlow no aparecen; vms.txt publico solo con las de CyberFlow
for v in pub.glob("esxi-*"):
    t = (src / v.name / "vms.txt").read_text(errors="replace").splitlines()
    (v / "vms-cyberflow.txt").write_text("\n".join(t[:1] + [l for l in t[1:] if any(x in l for x in VMS)]) + "\n", encoding="utf-8")
print("publicos:", n, "| equipos:", sorted(p.name for p in pub.iterdir() if p.is_dir()))
