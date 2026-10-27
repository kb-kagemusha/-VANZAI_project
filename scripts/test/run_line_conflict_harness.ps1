# 試験用PostgreSQLだけで競合試験基盤を起動する。
# 本番DB、.env、実在の稼働者は読まない。LINE承認の競合試験合格とは別である。
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

python -c "import psycopg" 
if ($LASTEXITCODE -ne 0) {
    Write-Error "試験用ドライバがありません。pip install 'psycopg[binary]' を実行してください。"
}

$url = "postgresql+psycopg://vanzai_conflict:vanzai_conflict@127.0.0.1:54329/vanzai_conflict"
$previousConflictUrl = $env:VANZAI_CONFLICT_TEST_URL
$previousDatabaseUrl = $env:DATABASE_URL
$env:VANZAI_CONFLICT_TEST_URL = $url
$env:DATABASE_URL = $url

$useDocker = [bool](Get-Command docker -ErrorAction SilentlyContinue)
try {
    if ($useDocker) {
        docker compose -f docker-compose.conflict-test.yml up -d --wait
    } else {
        & (Join-Path $PSScriptRoot "start_conflict_postgres.ps1")
    }
    python -m pytest tests/postgres_conflict/test_harness_ready.py tests/postgres_conflict/test_worker_edit_conflict.py tests/postgres_conflict/test_staffing_conflict.py -q --tb=short
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    if ($useDocker) {
        docker compose -f docker-compose.conflict-test.yml down -v
    }
    if ($null -eq $previousConflictUrl) {
        Remove-Item Env:VANZAI_CONFLICT_TEST_URL -ErrorAction SilentlyContinue
    } else {
        $env:VANZAI_CONFLICT_TEST_URL = $previousConflictUrl
    }
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    } else {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
}
