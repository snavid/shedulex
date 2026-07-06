# Backup Shedulex Postgres and .env (Windows PowerShell).
# Usage (from project root):
#   .\scripts\backup.ps1
#   .\scripts\backup.ps1 -WithChroma

param([switch]$WithChroma)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Invoke-Docker {
    param(
        [Parameter(Mandatory)][string[]]$Args,
        [int]$TimeoutSec = 30,
        [switch]$AllowFailure
    )
    $argLine = ($Args | ForEach-Object {
        if ($_ -match '\s') { """$_""" } else { $_ }
    }) -join " "

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "docker"
    $psi.Arguments = $argLine
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try { $proc.Kill($true) } catch {}
        throw "Docker timed out after ${TimeoutSec}s: docker $argLine"
    }

    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    if ($proc.ExitCode -ne 0 -and -not $AllowFailure) {
        throw "docker $argLine failed (exit $($proc.ExitCode)): $stderr"
    }
    return [PSCustomObject]@{
        ExitCode = $proc.ExitCode
        StdOut   = $stdout
        StdErr   = $stderr
    }
}

$PgContainer = if ($env:PG_CONTAINER) { $env:PG_CONTAINER } else { "shedulex-postgres" }
$PgUser = "shedulex"
if (Test-Path ".env") {
    $line = Get-Content ".env" | Where-Object { $_ -match '^\s*POSTGRES_USER=' } | Select-Object -First 1
    if ($line -match 'POSTGRES_USER=(.+)') { $PgUser = $Matches[1].Trim().Trim('"') }
}

Write-Host "==> Checking Docker (20s timeout)..."
try {
    $info = Invoke-Docker -Args @("info") -TimeoutSec 20
    if ($info.ExitCode -ne 0) { throw $info.StdErr }
    Write-Host "==> Docker OK."
} catch {
    Write-Host ""
    Write-Host "ERROR: Docker is not responding." -ForegroundColor Red
    Write-Host $_.Exception.Message
    Write-Host ""
    Write-Host "Fix:"
    Write-Host "  1. Open Docker Desktop — wait until it says 'Engine running'"
    Write-Host "  2. Test:  docker version"
    Write-Host "  3. If that hangs too, restart Docker Desktop from the system tray"
    Write-Host "  4. Then run:  docker compose up -d postgres"
    Write-Host "  5. Retry:     .\scripts\backup.ps1"
    exit 1
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $Root "backups\shedulex-$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Write-Host "==> Backup directory: $dest"

$running = $false
try {
    $inspect = Invoke-Docker -Args @("inspect", "-f", "{{.State.Running}}", $PgContainer) -TimeoutSec 15 -AllowFailure
    if ($inspect.ExitCode -eq 0 -and $inspect.StdOut.Trim() -eq "true") {
        $running = $true
    }
} catch {}

if (-not $running) {
    Write-Host "==> Postgres not running — starting stack..."
    try {
        Invoke-Docker -Args @("compose", "up", "-d", "postgres") -TimeoutSec 120 | Out-Null
    } catch {
        Write-Host "==> compose failed, trying docker start $PgContainer ..."
        Invoke-Docker -Args @("start", $PgContainer) -TimeoutSec 60 -AllowFailure | Out-Null
    }
}

Write-Host "==> Waiting for Postgres ($PgContainer)..."
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $check = Invoke-Docker -Args @(
            "exec", $PgContainer,
            "pg_isready", "-U", $PgUser, "-d", "shedulex_master"
        ) -TimeoutSec 10 -AllowFailure
        if ($check.ExitCode -eq 0) {
            $ready = $true
            break
        }
    } catch {}
    Write-Host "    attempt $i/30 ..."
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host ""
    Write-Host "ERROR: Postgres not ready after 60s." -ForegroundColor Red
    Write-Host "Run:  docker compose up -d postgres"
    Write-Host "Then: docker exec $PgContainer pg_isready -U $PgUser -d shedulex_master"
    exit 1
}
Write-Host "==> Postgres is ready."

$sqlPath = Join-Path $dest "postgres-all.sql"
Write-Host "==> Dumping all Postgres databases (may take a minute)..."
try {
    $dump = Invoke-Docker -Args @(
        "exec", $PgContainer,
        "pg_dumpall", "-U", $PgUser, "-c"
    ) -TimeoutSec 300
    [System.IO.File]::WriteAllText($sqlPath, $dump.StdOut)
} catch {
    Write-Host "ERROR: pg_dumpall failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (Test-Path ".env") {
    Copy-Item ".env" (Join-Path $dest "env.backup")
    Write-Host "==> Copied .env to env.backup"
}

if ($WithChroma) {
    try {
        $vol = (Invoke-Docker -Args @("volume", "ls", "-q") -TimeoutSec 15).StdOut -split "`n" |
            Where-Object { $_ -match "chroma_data" } | Select-Object -First 1
        if ($vol) {
            Write-Host "==> Archiving chroma_data volume..."
            Invoke-Docker -Args @(
                "run", "--rm",
                "-v", "${vol}:/data:ro",
                "-v", "${dest}:/backup",
                "alpine", "tar", "czf", "/backup/chroma-data.tar.gz", "-C", "/data", "."
            ) -TimeoutSec 300 | Out-Null
        }
    } catch {
        Write-Host "WARN: chroma backup skipped: $($_.Exception.Message)"
    }
}

$bytes = (Get-Item $sqlPath).Length
if ($bytes -lt 1000) {
    Write-Host "ERROR: postgres-all.sql too small ($bytes bytes)." -ForegroundColor Red
    exit 1
}

@"
timestamp=$stamp
host=$env:COMPUTERNAME
"@ | Set-Content (Join-Path $dest "manifest.txt")

Write-Host ""
Write-Host "Backup complete: $dest" -ForegroundColor Green
Write-Host "  postgres-all.sql  ($bytes bytes)"
