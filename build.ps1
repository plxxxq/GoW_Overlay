$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$scriptFile = Join-Path $projectDir "src\gow_overlay.py"
$iconFile = Join-Path $projectDir "assets\GoW_Overlay.ico"
$splashFile = Join-Path $projectDir "assets\GoW_Overlay.png"
$versionFile = Join-Path $projectDir "version_info.txt"
$desktopDir = [Environment]::GetFolderPath("Desktop")
$outputDir = Join-Path $desktopDir "GoW Overlay"
$buildDir = Join-Path $env:TEMP "GoW_Overlay_build"
$specDir = Join-Path $env:TEMP "GoW_Overlay_spec"

foreach ($requiredFile in @($scriptFile, $iconFile, $splashFile, $versionFile)) {
    if (-not (Test-Path $requiredFile)) {
        throw "Arquivo não encontrado: $requiredFile"
    }
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null

py -m pip install --upgrade pyinstaller requests websocket-client pywin32 obsws-python pystray pillow

py -m PyInstaller `
    --onefile `
    --noconsole `
    --clean `
    --name "GoW Overlay" `
    --icon $iconFile `
    --version-file $versionFile `
    --add-data "$iconFile;." `
    --add-data "$splashFile;." `
    --hidden-import pystray `
    --hidden-import pystray._win32 `
    --hidden-import PIL `
    --distpath $outputDir `
    --workpath $buildDir `
    --specpath $specDir `
    $scriptFile

$exeFile = Join-Path $outputDir "GoW Overlay.exe"

if (-not (Test-Path $exeFile)) {
    throw "A compilação terminou, mas o EXE não foi encontrado."
}

Write-Host ""
Write-Host "EXE criado com sucesso:" -ForegroundColor Green
Write-Host $exeFile -ForegroundColor Cyan
Start-Process explorer.exe "/select,`"$exeFile`""
