# =====================================================================
#  desplegar-laboratorio.ps1 - copia el generador de trafico a la VM de
#  clientes, saltando por el bastion.
# ---------------------------------------------------------------------
#  PARTE 1 de 2. No pide contrasena: escribe en el home de adminclientes.
#  La PARTE 2 -instalar las unidades y arrancarlas- si necesita sudo, va
#  aparte y se ejecuta en la VM.
#
#  Uso:   pwsh .\desplegar-laboratorio.ps1
#         pwsh .\desplegar-laboratorio.ps1 -Simular
# =====================================================================
param(
    [switch]$Simular,
    [string]$Repo = "C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\producto-limpio"
)

$ErrorActionPreference = "Stop"

$BASTION = "gadmin@10.10.10.30"
$CLIENTES = "adminclientes@10.10.20.20"
$CLAVE   = "$env:USERPROFILE\.ssh\id_ed25519"
$CLAVE_R = "~/.ssh/cyberflow-to-clientes"
$REMOTO  = "/home/adminclientes/laboratorio"

$FICHEROS = @("clientes_lab.py", "clientes_config.py")

if (-not (Test-Path (Join-Path $Repo "scripts\laboratorio\clientes_lab.py"))) {
    throw "no parece el repositorio del producto: $Repo"
}

function EnClientes([string]$Orden) {
    ssh -o BatchMode=yes -o ConnectTimeout=15 -i $CLAVE $BASTION `
        "ssh -n -o BatchMode=yes -i $CLAVE_R $CLIENTES '$Orden'"
    if ($LASTEXITCODE -ne 0) { throw "fallo en la VM de clientes: $Orden" }
}

Write-Host "Comprobando el camino..."
EnClientes "hostname && python3 -V"

if (-not $Simular) { EnClientes "mkdir -p $REMOTO" }

foreach ($f in $FICHEROS) {
    $origen = Join-Path $Repo "scripts\laboratorio\$f"
    $sha = (Get-FileHash $origen -Algorithm SHA256).Hash.ToLower()
    Write-Host ""
    Write-Host ("-> {0}   sha256 local {1}" -f $f, $sha.Substring(0, 16))
    if ($Simular) { Write-Host "   (simulacion: no se copia)"; continue }

    # base64 -di ignora el retorno de carro que anade la tuberia de PowerShell;
    # con base64 -d a secas aborta con "invalid input".
    $tmpB64 = Join-Path $env:TEMP ("cf_lab_" + $f + ".b64")
    [IO.File]::WriteAllText($tmpB64, [Convert]::ToBase64String([IO.File]::ReadAllBytes($origen)))
    $orden = "ssh -o BatchMode=yes -i $CLAVE_R $CLIENTES " +
             "'base64 -di > $REMOTO/$f && sha256sum $REMOTO/$f'"
    $salida = Get-Content $tmpB64 -Raw |
              ssh -o BatchMode=yes -o ConnectTimeout=15 -i $CLAVE $BASTION $orden
    Remove-Item $tmpB64 -ErrorAction SilentlyContinue

    if (($salida -split "\s+")[0] -ne $sha) {
        throw "el fichero llego corrupto: $f"
    }
    Write-Host "   sha256 remoto CUADRA"
}

if ($Simular) { Write-Host ""; Write-Host "Simulacion terminada."; return }

Write-Host ""
Write-Host "Comprobando la configuracion en la propia VM..."
EnClientes "cd $REMOTO && python3 clientes_config.py --comprobar"

Write-Host ""
Write-Host "PARTE 1 hecha. Nada corre todavia." -ForegroundColor Yellow
Write-Host ""
Write-Host "PARTE 2 - en la VM de clientes (pedira tu contrasena):"
Write-Host ""
Write-Host "  ssh gadmin@10.10.10.30"
Write-Host "  ssh -i ~/.ssh/cyberflow-to-clientes adminclientes@10.10.20.20"
Write-Host "  cd $REMOTO"
Write-Host "  python3 clientes_lab.py --perfil ofimatica --una-vuelta   # prueba antes de nada"
Write-Host "  sudo python3 clientes_config.py --escribir"
Write-Host "  sudo systemctl daemon-reload"
Write-Host "  sudo systemctl enable --now cyberflow-lab.target"
Write-Host ""
Write-Host "PARA PARAR LOS SEIS:"
Write-Host "  sudo systemctl stop cyberflow-lab.target"
