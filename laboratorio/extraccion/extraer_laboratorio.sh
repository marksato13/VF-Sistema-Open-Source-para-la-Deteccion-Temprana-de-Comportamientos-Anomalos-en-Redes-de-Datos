#!/bin/bash
# Extraccion de la configuracion del laboratorio CyberFlow — corre en el BASTION (gadmin).
# Solo lectura en todos los equipos. Deja una carpeta por equipo en $SALIDA.
#
# Uso:  bash extraer_laboratorio.sh [SALIDA] [equipo ...]
#       sin equipos = todos. Ejemplo para repetir uno:  bash extraer_laboratorio.sh /tmp/x srvdmz
#
# Requiere el ~/.ssh/config del bastion (alias sensor1, srvdmz, kali, sw-*, esxi-*...).
# Despues: sanear.py (quita secretos) e inventario.py (genera INVENTARIO.md).
set -u
DIR=$(cd "$(dirname "$0")" && pwd)
SALIDA=${1:-/tmp/cf-extraccion-$(date -u +%Y%m%dT%H%MZ)}
shift || true
mkdir -p "$SALIDA"

LINUX="bastion sensor1 sensor2 srvdmz kali clientes suricata"
SWITCHES="sw-core-stack sw-dist-stack sw-access-sw5 sw-access-sw7 sw-access-sw8"
ESXI="esxi-hv-backup esxi-hv-siem esxi-hv-datos esxi-hv-borde-a esxi-hv-local3 esxi-hv-servicios esxi-hv-borde-b"
PEDIDOS="${*:-$LINUX $SWITCHES $ESXI}"
SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=8"

estado() { echo "$(date -u +%T) $1: $2" | tee -a "$SALIDA/_registro.txt"; }

linux() {
  local h=$1 d="$SALIDA/$1"; mkdir -p "$d"
  if [ "$h" = bastion ]; then
    bash "$DIR/recolector_linux.sh" > "$d.tgz" 2>"$d.err"
  else
    ssh -o BatchMode=yes -o ConnectTimeout=8 "$h" 'bash -s' < "$DIR/recolector_linux.sh" > "$d.tgz" 2>"$d.err"
  fi
  if [ -s "$d.tgz" ] && tar -xzf "$d.tgz" -C "$d" 2>/dev/null; then
    rm -f "$d.tgz" "$d.err"; estado "$h" "OK ($(find "$d" -type f | wc -l) ficheros)"
  else
    estado "$h" "SIN ACCESO: $(tail -1 "$d.err" 2>/dev/null)"; rm -f "$d.tgz"; mv "$d.err" "$d/_sin-acceso.txt" 2>/dev/null
  fi
}

switch() {
  local h=$1 d="$SALIDA/$1"; mkdir -p "$d"
  local ok=0 cmd f
  for cmd in "show running-config" "show version" "show vlan brief" "show interfaces status" \
             "show interfaces trunk" "show monitor session all" "show etherchannel summary" \
             "show spanning-tree summary" "show ip interface brief" "show cdp neighbors" \
             "show switch" "show inventory"; do
    f=$(echo "$cmd" | sed 's/^show //; s/ /-/g').txt
    timeout 40 $SSH "$h" "$cmd" 2>&1 | grep -v '^\*\{5,\}' > "$d/$f" && [ -s "$d/$f" ] && ok=1
  done
  [ $ok = 1 ] && estado "$h" "OK (switch)" || estado "$h" "SIN ACCESO"
}

esxi() {
  local h=$1 d="$SALIDA/$1"; mkdir -p "$d/vmx"
  timeout 30 $SSH "$h" 'vmware -vl' > "$d/version.txt" 2>&1 || { estado "$h" "SIN ACCESO"; return; }
  timeout 60 $SSH "$h" '
    echo "### cpu";        esxcli hardware cpu global get
    echo "### memoria";    esxcli hardware memory get
    echo "### plataforma"; esxcli hardware platform get
    echo "### nics";       esxcli network nic list
    echo "### vmk";        esxcli network ip interface ipv4 get
    echo "### vswitch";    esxcli network vswitch standard list
    echo "### portgroup";  esxcli network vswitch standard portgroup list
    echo "### almacen";    esxcli storage filesystem list
    echo "### ntp";        esxcli system ntp get
  ' > "$d/host.txt" 2>&1
  timeout 30 $SSH "$h" 'vim-cmd vmsvc/getallvms' > "$d/vms.txt" 2>&1
  # .vmx de cada VM (CPU, memoria, discos, NICs y portgroups): lo que hace falta para recrearla
  timeout 120 $SSH "$h" 'vim-cmd vmsvc/getallvms | tail -n +2 | while read -r id rest; do
      p=$(echo "$rest" | grep -o "\[[^]]*\] [^ ]*\.vmx"); [ -n "$p" ] || continue
      ds=$(echo "$p" | sed "s/^\[\([^]]*\)\] .*/\1/"); rel=$(echo "$p" | sed "s/^\[[^]]*\] //")
      echo "=====VMX $id $rel"; cat "/vmfs/volumes/$ds/$rel" 2>/dev/null; done' > "$d/_vmx.txt" 2>&1
  awk -v dd="$d" '/^=====VMX /{n=$3; sub(/.*\//,"",n); f=dd"/vmx/"n; next} f{print > f}' "$d/_vmx.txt"
  rm -f "$d/_vmx.txt"
  estado "$h" "OK (esxi, $(ls "$d/vmx" | wc -l) vmx)"
}

estado inicio "salida $SALIDA"
for h in $PEDIDOS; do
  case " $LINUX " in *" $h "*) linux "$h"; continue;; esac
  case " $SWITCHES " in *" $h "*) switch "$h"; continue;; esac
  case " $ESXI " in *" $h "*) esxi "$h"; continue;; esac
  estado "$h" "equipo desconocido"
done
estado fin "listo"
