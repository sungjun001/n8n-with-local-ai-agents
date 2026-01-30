# Claude API Services Start Script for PowerShell
param([string]$env = "local")

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$iconRocket = [System.Char]::ConvertFromUtf32(0x1F680)
$iconGlobe = [System.Char]::ConvertFromUtf32(0x1F310)
$iconSparkles = [System.Char]::ConvertFromUtf32(0x2728)

Write-Host "$iconRocket Starting Claude API Services ($env mode)..." -ForegroundColor Blue

# 1. 네트워크 생성 함수
function Create-NetworkIfMissing {
    param([string]$networkName)
    $networkExists = docker network ls --filter name=^${networkName}$ --format "{{.Name}}"
    if (-not $networkExists) {
        Write-Host "Creating network: $networkName" -ForegroundColor Yellow
        docker network create $networkName | Out-Null
    } else {
        Write-Host "Network exists: $networkName" -ForegroundColor DarkGray
    }
}

Write-Host "$iconGlobe Checking Docker networks..." -ForegroundColor Green
Create-NetworkIfMissing "web"
Create-NetworkIfMissing "n8n-v2-network"

# 2. Nginx Proxy 실행
Write-Host "Starting Nginx Proxy..." -ForegroundColor Green
Set-Location -Path "nginx-proxy"
docker-compose up -d
Set-Location -Path ".."

# 3. n8n 실행
Write-Host "Starting n8n Services..." -ForegroundColor Green
Set-Location -Path "n8n-v2"
$composeFile = "docker-compose.$env.yml"
if (Test-Path $composeFile) {
    Write-Host "Using configuration: $composeFile" -ForegroundColor Cyan
    docker-compose -f $composeFile up -d
} elseif (Test-Path "docker-compose.yml") {
    Write-Host "Using configuration: docker-compose.yml" -ForegroundColor Cyan
    docker-compose up -d
} else {
    Write-Host "Error: No docker-compose file found in n8n-v2 for environment '$env'" -ForegroundColor Red
}
Set-Location -Path ".."

# 4. Claude Server & Monitor 실행
Write-Host "Starting Claude Server & Monitor..." -ForegroundColor Green
Set-Location -Path "claude-docker"
docker-compose up -d
Set-Location -Path ".."

Write-Host "$iconSparkles All services started successfully!" -ForegroundColor Blue
