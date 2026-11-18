# =====================================================================
#  ver-panel-demo.ps1 - abre una COPIA de solo lectura del panel, SIN login
# ---------------------------------------------------------------------
#  Plan B para la demo: arranca en el sensor una copia del panel (mismo
#  codigo, mismos datos en vivo) escuchando en 127.0.0.1:8799, SIN TLS y
#  SIN login, y la trae a tu portatil por el bastion. Util si el login de
#  produccion da problemas. La copia se apaga sola a las 5 h.
#
#     portatil:8788 -> bastion:28801 -> sensor:127.0.0.1:8799
#
#  Uso:   pwsh .\ver-panel-demo.ps1
#  Luego: se abre http://127.0.0.1:8788/  (sin login). Pulsa "Modo
#         desarrollo" arriba a la derecha para ver todas las secciones.
#  Salir: Ctrl+C (el tunel se cierra; la copia se apaga sola).
# =====================================================================
$ErrorActionPreference = "Stop"
$Local = 8788
$Inter = 28801
$Bastion = "gadmin@10.10.10.30"
$ClaveSensor = "~/.ssh/cyberflow-to-sensor"
$Sensor = "m4rk@10.10.60.11"

if (Get-NetTCPConnection -LocalPort $Local -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "El puerto $Local ya esta en uso: probablemente el tunel ya esta abierto."
    Start-Process "http://127.0.0.1:$Local/"; return
}

Write-Host "1/3 Arrancando la copia de solo lectura en el sensor..."
# start_ps.sh es idempotente (si 8799 ya escucha, no hace nada). La llamada
# puede quedar colgada por setsid; no la esperamos, el sondeo de abajo confirma.
Start-Process ssh -NoNewWindow -ArgumentList @(
    "-i", "$env:USERPROFILE\.ssh\id_ed25519", "-o", "ConnectTimeout=10", $Bastion,
    "ssh -i $ClaveSensor -o StrictHostKeyChecking=no $Sensor 'cd ~/cyberflow && bash start_ps.sh'"
) | Out-Null

Write-Host "2/3 Abriendo el tunel por el bastion..."
$tunel = Start-Process ssh -PassThru -NoNewWindow -ArgumentList @(
    "-i", "$env:USERPROFILE\.ssh\id_ed25519",
    "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30",
    "-L", "${Local}:localhost:${Inter}",
    $Bastion,
    "ssh -i $ClaveSensor -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N -L ${Inter}:127.0.0.1:8799 $Sensor"
)

Write-Host "3/3 Esperando a que responda..."
$listo = $false
foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Local/api/status" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $listo = $true; break }
    } catch {}
    if ($tunel.HasExited) {
        Write-Host "El tunel murio. Si dice 'address already in use', cambia `$Inter a otro numero (p.ej. 28802)." -ForegroundColor Red
        break
    }
}

if (-not $listo) {
    Write-Host "La copia no respondio. Prueba el panel de produccion con ver-panel.ps1." -ForegroundColor Red
    if (-not $tunel.HasExited) { Stop-Process $tunel -Force }
    exit 1
}

Write-Host "Copia del panel en http://127.0.0.1:$Local/  (sin login). Pulsa 'Modo desarrollo'. Ctrl+C para cerrar." -ForegroundColor Green
Start-Process "http://127.0.0.1:$Local/"
try { Wait-Process -Id $tunel.Id } finally {
    if (-not $tunel.HasExited) { Stop-Process $tunel -Force }
}
