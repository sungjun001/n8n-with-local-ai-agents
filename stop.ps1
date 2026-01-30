# Claude API Services Stop Script for PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$iconStop = [System.Char]::ConvertFromUtf32(0x1F6D1)
$iconSparkles = [System.Char]::ConvertFromUtf32(0x2728)

Write-Host "$iconStop Stopping Claude API Services..." -ForegroundColor Red

# 1. Claude Server & Monitor 종료
Write-Host "Stopping Claude Server & Monitor..." -ForegroundColor Red
Set-Location -Path "claude-docker"
docker-compose down
Set-Location -Path ".."

# 2. n8n 종료
Write-Host "Stopping n8n Services..." -ForegroundColor Red
Set-Location -Path "n8n-v2"
# 모든 가능성 있는 설정 파일에 대해 종료 시도
if (Test-Path "docker-compose.local.yml") { docker-compose -f docker-compose.local.yml down }
if (Test-Path "docker-compose.dev.yml") { docker-compose -f docker-compose.dev.yml down }
if (Test-Path "docker-compose.yml") { docker-compose down }
Set-Location -Path ".."

# 3. Nginx Proxy 종료
Write-Host "Stopping Nginx Proxy..." -ForegroundColor Red
Set-Location -Path "nginx-proxy"
docker-compose down
Set-Location -Path ".."

Write-Host "$iconSparkles All services stopped." -ForegroundColor Red
