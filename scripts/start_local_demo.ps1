$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $demoRoot
$demoSettingsPath = Join-Path $demoRoot '.env.demo'
if (-not (Test-Path -LiteralPath $demoSettingsPath)) { throw 'Configure .env.demo first; see README.md.' }
$demoSettings = @{}
Get-Content -LiteralPath $demoSettingsPath | ForEach-Object {
    if ($_ -and -not $_.StartsWith('#') -and $_.Contains('=')) {
        $demoParts = $_ -split '=', 2
        $demoSettings[$demoParts[0]] = $demoParts[1]
    }
}
if ($demoSettings.MONGODB_URI -notmatch '@127\.0\.0\.1:27018/') {
    throw 'This helper only starts the local MongoDB preview. Start your configured database separately and use scripts/run_demo.py --serve.'
}
if (-not (Get-NetTCPConnection -LocalPort 27018 -State Listen -ErrorAction SilentlyContinue)) {
    $demoMongoExe = Join-Path $demoRoot 'work/runtime/mongodb-win32-x86_64-windows-8.0.19/bin/mongod.exe'
    $demoMongoData = Join-Path $demoRoot 'work/runtime/mongo-data'
    $demoMongoLog = Join-Path $demoRoot 'work/runtime/mongodb.log'
    if (-not (Test-Path -LiteralPath $demoMongoExe) -or -not (Test-Path -LiteralPath $demoMongoData)) {
        throw 'Portable MongoDB is not installed here. Use the documented Docker setup instead.'
    }
    $demoMongoArgs = @('--dbpath', ('"' + $demoMongoData + '"'), '--bind_ip', '127.0.0.1', '--port', '27018', '--auth', '--logpath', ('"' + $demoMongoLog + '"'), '--logappend')
    $demoMongoProcess = Start-Process -FilePath $demoMongoExe -ArgumentList $demoMongoArgs -WindowStyle Hidden -PassThru
    $demoMongoProcess.Id | Set-Content -LiteralPath (Join-Path $demoRoot 'work/runtime/mongo.pid')
    Start-Sleep -Seconds 3
}
if (Get-NetTCPConnection -LocalPort 5055 -State Listen -ErrorAction SilentlyContinue) {
    Write-Output 'Port 5055 is already listening. Open http://127.0.0.1:5055/database-lab.html if it is the demo.'
} else {
    & (Join-Path $demoRoot '.venv/Scripts/python.exe') scripts/run_demo.py --serve
}
