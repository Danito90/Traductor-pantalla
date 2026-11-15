param(
    [string]$Compiler = '',
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'),
    [string]$Redistributable = ''
)

$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot

if (-not $Compiler) {
    $Installed = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Installed) { $Compiler = $Installed.Source }
    else { $Compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe' }
}
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Instalá Inno Setup 6.3 o posterior o indicá -Compiler.' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Creá el entorno .venv e instalá el proyecto con el extra build.' }

Push-Location -LiteralPath $Project
try {
    & $Python packaging/prepare_models.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la preparación de modelos.' }
    & $Python packaging/prepare_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la recopilación de licencias.' }

    $Redist = Join-Path $Project 'build\VC_redist.x64.exe'
    if ($Redistributable) {
        if ((Resolve-Path -LiteralPath $Redistributable).Path -ne $Redist) {
            Copy-Item -LiteralPath $Redistributable -Destination $Redist -Force
        }
    } elseif (-not (Test-Path -LiteralPath $Redist)) {
        Invoke-WebRequest -Uri 'https://aka.ms/vc14/vc_redist.x64.exe' -OutFile $Redist
    }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Redist
    if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(,|$)') {
        throw 'No se pudo validar la firma de Microsoft en VC_redist.x64.exe.'
    }

    & $Python -m PyInstaller --noconfirm --clean packaging/traductor-pantalla.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falló el empaquetado de la aplicación.' }
    & $Compiler packaging/traductor-pantalla.iss
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación de Inno Setup.' }
    Get-Item -LiteralPath (Join-Path $Project 'dist\TraductorPantalla-Setup-x64.exe')
} finally {
    Pop-Location
}
