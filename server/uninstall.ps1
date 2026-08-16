# mini-IDM'i kaldirir: acilis/masaustu kisayollarini siler ve calisiyorsa
# uygulamayi kapatir. Python paketlerine (requirements.txt) dokunmaz.
#
# Calistir:  powershell -ExecutionPolicy Bypass -File uninstall.ps1

$startupLnk = Join-Path ([Environment]::GetFolderPath("Startup")) "mini-IDM.lnk"
$desktopLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "mini-IDM.lnk"

foreach ($lnk in @($startupLnk, $desktopLnk)) {
    if (Test-Path $lnk) {
        Remove-Item $lnk -Force
        Write-Host "Silindi: $lnk" -ForegroundColor Green
    }
}

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*app.py*' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "mini-IDM sureci durduruldu (PID $($_.ProcessId))" -ForegroundColor Green
    }

Write-Host "`nmini-IDM kaldirildi. Bagimliliklari da kaldirmak istersen:"
Write-Host "  python -m pip uninstall -y pywebview pystray Pillow requests"
