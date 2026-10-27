# 試験専用の PostgreSQL 16 を 127.0.0.1:54329 で起動する。
# バイナリとデータはユーザーのローカル領域に置く。本番DBと .env は使わない。
$ErrorActionPreference = "Stop"
$root = Join-Path $env:LOCALAPPDATA "vanzai-conflict-pg"
$bin = Join-Path $root "pgsql\bin"
$data = Join-Path $root "data"
$initdb = Join-Path $bin "initdb.exe"
if (-not (Test-Path $initdb)) {
    Write-Error "PostgreSQL 16 のバイナリがありません。$root に展開してください。"
}

if (-not (Test-Path $data)) {
    $pw = Join-Path $root "pw.txt"
    Set-Content -Path $pw -Value "vanzai_conflict" -NoNewline
    & $initdb -D $data -U vanzai_conflict -E UTF8 --locale=C --auth=scram-sha-256 --pwfile=$pw
    Remove-Item $pw -Force
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$previousPgPassword = $env:PGPASSWORD
$env:PGPASSWORD = "vanzai_conflict"
try {
    & (Join-Path $bin "pg_isready.exe") -h 127.0.0.1 -p 54329 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & (Join-Path $bin "pg_ctl.exe") -D $data -l (Join-Path $root "server.log") -w start -o "-p 54329 -h 127.0.0.1"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $exists = & (Join-Path $bin "psql.exe") -h 127.0.0.1 -p 54329 -U vanzai_conflict -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'vanzai_conflict'"
    if ($exists.Trim() -ne "1") {
        & (Join-Path $bin "psql.exe") -h 127.0.0.1 -p 54329 -U vanzai_conflict -d postgres -c "CREATE DATABASE vanzai_conflict"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} finally {
    if ($null -eq $previousPgPassword) {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    } else {
        $env:PGPASSWORD = $previousPgPassword
    }
}
