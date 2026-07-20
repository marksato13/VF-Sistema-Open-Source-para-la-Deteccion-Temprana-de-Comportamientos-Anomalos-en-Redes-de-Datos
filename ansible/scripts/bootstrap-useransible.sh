#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP_USER="${BOOTSTRAP_USER:-m4rk}"
ANSIBLE_PUBLIC_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller'
ANSIBLE_PRIVATE_KEY='/home/m4rk/.ssh/id_ed25519_ppi_ansible'
HOSTS=(10.10.10.20 10.10.10.30 10.10.10.40 10.10.10.50)

remote_command=$(printf '%q' "
set -e
if ! id -u useransible >/dev/null 2>&1; then
  useradd -m -s /bin/bash useransible
fi
install -d -m 700 -o useransible -g useransible /home/useransible/.ssh
printf '%s\\n' '$ANSIBLE_PUBLIC_KEY' > /home/useransible/.ssh/authorized_keys
chown useransible:useransible /home/useransible/.ssh/authorized_keys
chmod 600 /home/useransible/.ssh/authorized_keys
id useransible
stat -c '%U:%G %a %n' /home/useransible/.ssh /home/useransible/.ssh/authorized_keys
")

echo 'BOOTSTRAP DE USERANSIBLE'
echo 'Se solicitará la contraseña SSH y/o sudo de cada VM.'
echo

failed=0
for host in "${HOSTS[@]}"; do
  echo "=== $host ==="
  if ssh -tt \
      -o StrictHostKeyChecking=yes \
      -o ConnectTimeout=10 \
      "${BOOTSTRAP_USER}@${host}" \
      "sudo bash -c ${remote_command}"; then
    if ssh \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=yes \
        -o ConnectTimeout=5 \
        -i "$ANSIBLE_PRIVATE_KEY" \
        "useransible@${host}" 'id && hostname'; then
      echo "OK: useransible validado en $host"
    else
      echo "ERROR: la cuenta se creó, pero la clave no autenticó en $host"
      failed=1
    fi
  else
    echo "ERROR: bootstrap incompleto en $host"
    failed=1
  fi
  echo
done

if [[ "$failed" -eq 0 ]]; then
  echo 'COMPLETADO: useransible funciona en las cuatro VMs.'
else
  echo 'INCOMPLETO: revisa los errores mostrados antes de continuar.'
fi

read -r -p 'Presiona Enter para cerrar.'
exit "$failed"
