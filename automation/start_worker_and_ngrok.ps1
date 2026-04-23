$ErrorActionPreference = "Stop"

$automationDir = "F:\Workspaces\youtube\podcast english\automation"
$configPath = Join-Path $automationDir "worker_config.json"
$config = Get-Content -Raw -Path $configPath | ConvertFrom-Json
$port = [int]$config.port

$workerScript = Join-Path $automationDir "local_worker_server.py"
$workerLog = Join-Path $automationDir "worker_server.log"
$workerErrLog = Join-Path $automationDir "worker_server.err.log"
$ngrokLog = Join-Path $automationDir "ngrok.log"
$ngrokErrLog = Join-Path $automationDir "ngrok.err.log"

$workerProc = Start-Process python -ArgumentList "`"$workerScript`"" -PassThru -WindowStyle Hidden -RedirectStandardOutput $workerLog -RedirectStandardError $workerErrLog
$ngrokProc = Start-Process ngrok -ArgumentList "http $port --log=stdout" -PassThru -WindowStyle Hidden -RedirectStandardOutput $ngrokLog -RedirectStandardError $ngrokErrLog

Start-Sleep -Seconds 6

$tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 10
$publicUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1 -ExpandProperty public_url)

$runtime = [ordered]@{
  worker_pid = $workerProc.Id
  ngrok_pid = $ngrokProc.Id
  public_url = $publicUrl
  started_at = (Get-Date).ToString("s")
}

$runtimePath = Join-Path $automationDir "worker_runtime.json"
$runtime | ConvertTo-Json | Set-Content -Path $runtimePath -Encoding UTF8

Write-Output "Worker PID: $($workerProc.Id)"
Write-Output "ngrok PID: $($ngrokProc.Id)"
Write-Output "Public URL: $publicUrl"
Write-Output "Runtime file: $runtimePath"
