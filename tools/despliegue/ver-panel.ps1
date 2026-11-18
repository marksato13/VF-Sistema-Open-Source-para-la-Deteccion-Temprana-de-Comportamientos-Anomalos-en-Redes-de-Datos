# =====================================================================
#  ver-panel.ps1 - abre el panel de CyberFlow (PRODUCCION) en el navegador
# ---------------------------------------------------------------------
#  El panel escucha en 10.10.60.11:8788 DEL SENSOR con TLS + login, y el
#  cortafuegos solo acepta conexiones desde el bastion (10.10.10.30). Por
#  eso el tunel es de UN SOLO SALTO: es el bastion (origen permitido) quien
#  conecta al panel.
#
#     portatil:8788  ->  (bastion conecta a)  10.10.60.11:8788
#
#  Uso:   pwsh .\ver-panel.ps1
#  Luego: abre https://127.0.0.1:8788/  (certificado autofirmado: acepta el
#         aviso del navegador) e inicia sesion como admin.
#  Salir: Ctrl+C en esta ventana (el tunel se cierra; el panel sigue vivo).
#
#  No lleva credenciales: usa tu clave ~/.ssh/id_ed25519 hacia el bastion.
#  Si prefieres ver el panel SIN login (copia de solo lectura), usa
#  ver-panel-demo.ps1.
# =====================================================================
$ErrorActionPreference = "Stop"
$Puerto = 8788
$DestinoPanel = "10.10.60.11:8788"
$Bastion = "gadmin@10.10.10.30"

$ocupado = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue
if ($ocupado) {
    Write-Host "El puerto $Puerto ya esta en uso: probablemente el tunel ya esta abierto."
    Start-Process "https://127.0.0.1:$Puerto/"
    return
}

Write-Host "Abriendo tunel hacia el panel de CyberFlow (produccion)..."
$tunel = Start-Process ssh -PassThru -NoNewWindow -ArgumentList @(
    "-i", "$env:USERPROFILE\.ssh\id_ed25519",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-L", "${Puerto}:${DestinoPanel}",
    $Bastion, "-N"
)

# Esperar a que el panel responda (401 = vivo, pide login) antes de abrir.
$listo = $false
foreach ($i in 1..20) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest "https://127.0.0.1:$Puerto/api/status" -UseBasicParsing -TimeoutSec 3 -SkipCertificateCheck
        $listo = $true; break
    } catch {
        # 401 tambien significa "vivo": el servidor respondio pidiendo login.
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $listo = $true; break }
    }
    if ($tunel.HasExited) { break }
}

if (-not $listo) {
    Write-Host "El panel no responde. Comprueba:" -ForegroundColor Red
    Write-Host "  - que el bastion este accesible (ssh gadmin@10.10.10.30)"
    Write-Host "  - que el servicio corra: systemctl is-active ppi-dashboard (en el sensor)"
    if (-not $tunel.HasExited) { Stop-Process $tunel -Force }
    exit 1
}

Write-Host "Panel en https://127.0.0.1:$Puerto/  (acepta el certificado autofirmado e inicia sesion como admin)." -ForegroundColor Green
Write-Host "Ctrl+C para cerrar el tunel." -ForegroundColor Green
Start-Process "https://127.0.0.1:$Puerto/"
try { Wait-Process -Id $tunel.Id } finally {
    if (-not $tunel.HasExited) { Stop-Process $tunel -Force }
}
