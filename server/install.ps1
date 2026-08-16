# mini-IDM kurulum scripti (Python kaynagindan).
#
# Yapar:
#   1. requirements.txt bagimliliklarini kurar
#   2. Windows Baslangic klasorune bir kisayol koyar -> her acilista
#      pencere gostermeden, sadece sistem tepsisinde sessizce baslar
#   3. Masaustune "elle ac" kisayolu koyar -> pencereyi gorunur acar
#
# Calistir:  powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "mini-IDM kuruluyor..." -ForegroundColor Cyan

Write-Host "`nBagimliliklar kuruluyor (pip install)..."
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install basarisiz oldu." }

$pythonExe = (Get-Command python -ErrorAction Stop).Source
$pythonwExe = Join-Path (Split-Path $pythonExe -Parent) "pythonw.exe"
if (-not (Test-Path $pythonwExe)) {
    Write-Warning "pythonw.exe bulunamadi, konsollu python.exe kullanilacak."
    $pythonwExe = $pythonExe
}

$appPath = Join-Path $ScriptDir "app.py"
$iconPath = Join-Path $ScriptDir "mini_idm\app_icon.ico"
$wsh = New-Object -ComObject WScript.Shell

# --- Baslangic klasoru: Windows acilinca sessizce (tepside) baslar ---
$startupDir = [Environment]::GetFolderPath("Startup")
$startupLnk = Join-Path $startupDir "mini-IDM.lnk"
$sc = $wsh.CreateShortcut($startupLnk)
$sc.TargetPath = $pythonwExe
$sc.Arguments = "`"$appPath`" --hidden"
$sc.WorkingDirectory = $ScriptDir
$sc.IconLocation = $iconPath
$sc.Description = "mini-IDM indirme yoneticisi (arka planda baslar)"
$sc.Save()
Write-Host "Baslangic kisayolu olusturuldu: $startupLnk" -ForegroundColor Green

# --- Masaustu: elle acmak icin, pencere gorunur baslar ---
$desktopDir = [Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $desktopDir "mini-IDM.lnk"
$sc2 = $wsh.CreateShortcut($desktopLnk)
$sc2.TargetPath = $pythonwExe
$sc2.Arguments = "`"$appPath`""
$sc2.WorkingDirectory = $ScriptDir
$sc2.IconLocation = $iconPath
$sc2.Description = "mini-IDM indirme yoneticisi"
$sc2.Save()
Write-Host "Masaustu kisayolu olusturuldu: $desktopLnk" -ForegroundColor Green

Write-Host "`nKurulum tamam." -ForegroundColor Cyan
Write-Host "- Bir sonraki Windows acilisinda mini-IDM otomatik olarak tepside baslayacak."
Write-Host "- Kaldirmak icin: powershell -ExecutionPolicy Bypass -File uninstall.ps1"

Start-Process -FilePath $pythonwExe -ArgumentList "`"$appPath`"" -WorkingDirectory $ScriptDir
Write-Host "`nmini-IDM simdi baslatildi." -ForegroundColor Green
