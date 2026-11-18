# =====================================================================
#  desplegar-al-sensor.ps1 - copia al sensor los ficheros corregidos
# ---------------------------------------------------------------------
#  PARTE 1 de 2. Esta parte NO pide contrasena: solo escribe en
#  /home/m4rk/cyberflow, que pertenece a m4rk.
#
#  La PARTE 2 -regenerar las unidades de systemd y reiniciar- si necesita
#  tu contrasena de sudo, asi que va aparte y se ejecuta en el sensor.
#
#  Uso:   pwsh .\desplegar-al-sensor.ps1
#         pwsh .\desplegar-al-sensor.ps1 -Simular     (no copia nada)
#
#  Antes de sobrescribir, guarda una copia .anterior de cada fichero que
#  ya existiera. Para deshacer, ver el final de este fichero.
# =====================================================================
param(
    [switch]$Simular,
    # Ruta al repositorio. Por omision, la de este equipo. Se pasa explicita
    # -y no derivada de $PSScriptRoot- para que el guion funcione igual desde
    # cualquier sitio: copiarlo a otra carpeta no debe romperlo.
    [string]$Repo = "C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\producto-limpio"
)

$ErrorActionPreference = "Stop"

$REPO = $Repo
if (-not (Test-Path (Join-Path $REPO "scripts\setup\cyberflow_config.py"))) {
    throw "no parece el repositorio del producto: $REPO  (pasa -Repo <ruta>)"
}
$BASTION = "gadmin@10.10.10.30"
$SENSOR  = "m4rk@10.10.60.11"
$CLAVE   = "$env:USERPROFILE\.ssh\id_ed25519"
$REMOTO  = "/home/m4rk/cyberflow"

# Cada fichero, con su destino. El motor y el generador de unidades ya
# existen alla y se respaldan; los dos de v3 son nuevos.
$FICHEROS = @(
    @{ Local = "scripts/engine/motor_decision.py";            Respaldar = $true  },
    @{ Local = "scripts/engine/dashboard.py";                 Respaldar = $true  },
    @{ Local = "scripts/setup/cyberflow_config.py";           Respaldar = $true  },
    @{ Local = "scripts/features/extract_multilayer_v3.py";   Respaldar = $false },
    @{ Local = "scripts/features/acumular_v3.py";             Respaldar = $false },
    @{ Local = "configs/features/multilayer-v3.json";         Respaldar = $false }
)

function Invocar-EnSensor([string]$Orden) {
    ssh -o BatchMode=yes -o ConnectTimeout=15 -i $CLAVE $BASTION `
        "ssh -o BatchMode=yes -i ~/.ssh/cyberflow-to-sensor $SENSOR '$Orden'"
    if ($LASTEXITCODE -ne 0) { throw "fallo en el sensor: $Orden" }
}

Write-Host "Comprobando el camino al sensor..."
Invocar-EnSensor "hostname && test -d $REMOTO && echo 'repositorio encontrado'"

foreach ($f in $FICHEROS) {
    $origen = Join-Path $REPO ($f.Local -replace "/", "\")
    if (-not (Test-Path $origen)) { throw "no existe en local: $origen" }

    $destino = "$REMOTO/$($f.Local)"
    $sha = (Get-FileHash $origen -Algorithm SHA256).Hash.ToLower()
    Write-Host ""
    Write-Host ("-> {0}" -f $f.Local)
    Write-Host ("   sha256 local {0}" -f $sha.Substring(0, 16))

    if ($Simular) { Write-Host "   (simulacion: no se copia)"; continue }

    if ($f.Respaldar) {
        # -n: si ya hay un .anterior de un despliegue previo, no lo pisa.
        Invocar-EnSensor "cp -n $destino $destino.anterior 2>/dev/null; true"
    }

    # base64 -di ignora el retorno de carro que anade la tuberia de
    # PowerShell; sin eso, base64 -d aborta con 'invalid input'.
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($origen))
    $tmpB64 = Join-Path $env:TEMP ("cf_" + [IO.Path]::GetFileName($origen) + ".b64")
    [IO.File]::WriteAllText($tmpB64, $b64)

    $orden = "ssh -o BatchMode=yes -i ~/.ssh/cyberflow-to-sensor $SENSOR " +
             "'base64 -di > $destino && sha256sum $destino'"
    $salida = Get-Content $tmpB64 -Raw |
              ssh -o BatchMode=yes -o ConnectTimeout=15 -i $CLAVE $BASTION $orden
    Remove-Item $tmpB64 -ErrorAction SilentlyContinue

    $shaRemoto = ($salida -split "\s+")[0]
    if ($shaRemoto -ne $sha) {
        throw "el fichero llego corrupto: local $sha, remoto $shaRemoto"
    }
    Write-Host "   sha256 remoto CUADRA"
}

if ($Simular) { Write-Host ""; Write-Host "Simulacion terminada."; return }

Write-Host ""
Write-Host "Comprobando que el interprete del sensor los acepta..."
Invocar-EnSensor "cd $REMOTO && .venv/bin/python -c `"import ast,sys; [ast.parse(open(f).read()) for f in ['scripts/engine/motor_decision.py','scripts/features/extract_multilayer_v3.py','scripts/setup/cyberflow_config.py']]; import json; json.load(open('configs/features/multilayer-v3.json')); print('los cuatro ficheros son validos')`""

Write-Host ""
Write-Host "PARTE 1 hecha. Nada esta activo todavia: falta reiniciar." -ForegroundColor Yellow
Write-Host ""
Write-Host "PARTE 2 - entra al sensor y ejecuta (te pedira tu contrasena):"
Write-Host ""
Write-Host "  ssh gadmin@10.10.10.30"
Write-Host "  ssh -i ~/.ssh/cyberflow-to-sensor m4rk@10.10.60.11"
Write-Host "  cd /home/m4rk/cyberflow"
Write-Host "  sudo python3 scripts/setup/cyberflow_config.py --escribir"
Write-Host "  sudo systemctl daemon-reload"
Write-Host "  sudo systemctl restart ppi-motor-capture ppi-motor ppi-dashboard"
Write-Host ""
Write-Host "AVISO: el [panel] del cyberflow.toml dice 127.0.0.1 y permitir=[],"
Write-Host "       pero el panel corre en 10.10.60.11:8788 con permitir 10.10.10.30."
Write-Host "       Regenerar las unidades SIN corregir antes el .toml devolveria el"
Write-Host "       panel a loopback y perderias el acceso por el tunel."
Write-Host ""
Write-Host "PARA DESHACER, en el sensor:"
Write-Host "  cd /home/m4rk/cyberflow"
Write-Host "  cp scripts/engine/motor_decision.py.anterior scripts/engine/motor_decision.py"
Write-Host "  cp scripts/engine/dashboard.py.anterior scripts/engine/dashboard.py"
Write-Host "  cp scripts/setup/cyberflow_config.py.anterior scripts/setup/cyberflow_config.py"
Write-Host "  sudo cp /etc/systemd/system/ppi-motor-capture.service.anterior /etc/systemd/system/ppi-motor-capture.service"
Write-Host "  sudo systemctl daemon-reload && sudo systemctl restart ppi-motor-capture ppi-motor"
