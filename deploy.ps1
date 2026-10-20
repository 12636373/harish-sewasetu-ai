# ==============================================================================
# Sewa Setu — Production Deployment Script (Windows PowerShell)
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Sewa Setu — Old Age Pension Portal & MCP Deployment" -ForegroundColor Cyan
Write-Host "  Department of Social Welfare, Government of Purvanchal" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Docker & Docker Compose
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH."
    exit 1
}

# 2. Setup .env file
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    
    $randPass = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_})
    $randSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    
    (Get-Content ".env") | 
        ForEach-Object { $_ -replace 'ADMIN_PASSWORD=change-me-to-a-secure-password', "ADMIN_PASSWORD=$randPass" } |
        ForEach-Object { $_ -replace 'SECRET_KEY=generate_random_secret_key_here', "SECRET_KEY=$randSecret" } |
        Set-Content ".env"
    Write-Host "[*] Generated secure credentials in .env" -ForegroundColor Green
}

# 3. Build & Launch Containers
Write-Host "[*] Building container images..." -ForegroundColor Yellow
docker compose build

Write-Host "[*] Starting production stack in background..." -ForegroundColor Yellow
docker compose up -d

# 4. Wait for Health Check
Write-Host "[*] Waiting for services to become healthy..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$healthy = $false
$healthUrl = "http://127.0.0.1:8000/health"

while ($attempt -lt $maxAttempts -and -not $healthy) {
    $attempt++
    Start-Sleep -Seconds 3
    try {
        $res = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res.StatusCode -eq 200) {
            $healthy = $true
            Write-Host "[+] Portal and services are healthy!" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "    Waiting for DB initialization and app startup (Attempt $attempt/$maxAttempts)..." -ForegroundColor Gray
    }
}

if (-not $healthy) {
    Write-Host "[-] Warning: Health check did not return 200 within timeout." -ForegroundColor Red
    Write-Host "    Check logs with: docker compose logs -f" -ForegroundColor Red
    exit 1
}

# 5. Print Deployment Summary
$envContent = Get-Content ".env"
$adminUser = "admin"
$adminPass = "sewasetu123"
$baseUrl = "http://localhost:8000"

foreach ($line in $envContent) {
    if ($line -match "^PUBLIC_BASE_URL=(.*)$") { $baseUrl = $matches[1] }
    if ($line -match "^ADMIN_USERNAME=(.*)$") { $adminUser = $matches[1] }
    if ($line -match "^ADMIN_PASSWORD=(.*)$") { $adminPass = $matches[1] }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT SUCCESSFUL" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Portal URL:               $baseUrl"
Write-Host "  Officer Login (Admin):    $baseUrl/admin"
Write-Host "  Username:                 $adminUser"
Write-Host "  Password:                 $adminPass"
Write-Host "  Eval Dashboard:           $baseUrl/eval-dashboard"
Write-Host "  Citizen MCP Endpoint:     $baseUrl/mcp/citizen"
Write-Host "  Officer MCP Endpoint:     $baseUrl/mcp/officer"
Write-Host "  Resource Metadata:        $baseUrl/.well-known/oauth-protected-resource"
Write-Host "  Authorization Server:     $baseUrl/.well-known/oauth-authorization-server"
Write-Host "  Health Check:             $baseUrl/health"
Write-Host "==========================================================" -ForegroundColor Green
