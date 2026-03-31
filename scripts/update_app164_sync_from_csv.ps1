$subdomain = "xtf5wpxp3gk2"
$guestSpaceId = "3"
$appId = 164
$apiToken = "GtPvBi1Ne221KMvlSViaePrds1297d7Rj4h3xC91"
$csvPath = "C:\\VANZAI_project\\kintone_app\\project_types_sjis.csv"

$base = "https://$subdomain.cybozu.com/k/guest/$guestSpaceId/v1"
$headers = @{"X-Cybozu-API-Token" = $apiToken}
$headersJson = @{"X-Cybozu-API-Token" = $apiToken; "Content-Type" = "application/json"}

function Normalize-Value([string]$value) {
  if (-not $value) { return "" }
  return $value.Trim()
}

function Normalize-Pipe([string]$value) {
  if (-not $value) { return "" }
  $parts = $value.Split("|") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
  return ($parts -join "|")
}

Write-Output "============================================================"
Write-Output "App164: CSV同期（name/parent/category_level）"
Write-Output "============================================================"

$csvRows = Import-Csv -Path $csvPath -Encoding UTF8
$recordsResponse = Invoke-RestMethod -Method Get -Uri "$base/records.json?app=$appId&query=limit%20500" -Headers $headers
$records = $recordsResponse.records

$recordMap = @{}
foreach ($record in $records) {
  $typeId = $record.type_id.value
  if ($typeId) { $recordMap[$typeId] = $record }
}

$updates = @()
$missing = @()

foreach ($row in $csvRows) {
  $typeId = Normalize-Value $row.type_id
  if (-not $typeId) { continue }

  if (-not $recordMap.ContainsKey($typeId)) {
    $missing += $typeId
    continue
  }

  $record = $recordMap[$typeId]
  $recordId = $record.'$id'.value
  if (-not $recordId) { continue }

  $nameCsv = Normalize-Value $row.name
  $levelCsv = Normalize-Value $row.category_level
  $parentMajorCsv = Normalize-Pipe (Normalize-Value $row.parent_major)
  $parentMiddleCsv = Normalize-Value $row.parent_middle

  $nameCurrent = Normalize-Value $record.name.value
  $levelCurrent = Normalize-Value $record.category_level.value
  $parentMajorCurrent = Normalize-Pipe (Normalize-Value $record.parent_major.value)
  $parentMiddleCurrent = Normalize-Value $record.parent_middle.value

  if (($nameCsv -eq $nameCurrent) -and ($levelCsv -eq $levelCurrent) -and ($parentMajorCsv -eq $parentMajorCurrent) -and ($parentMiddleCsv -eq $parentMiddleCurrent)) {
    continue
  }

  $recordUpdate = @{ id = $recordId; record = @{} }
  if ($nameCsv -ne $nameCurrent) { $recordUpdate.record.name = @{ value = $nameCsv } }
  if ($levelCsv -ne $levelCurrent) { $recordUpdate.record.category_level = @{ value = $levelCsv } }
  if ($parentMajorCsv -ne $parentMajorCurrent) { $recordUpdate.record.parent_major = @{ value = $parentMajorCsv } }
  if ($parentMiddleCsv -ne $parentMiddleCurrent) { $recordUpdate.record.parent_middle = @{ value = $parentMiddleCsv } }

  $updates += $recordUpdate
}

if ($missing.Count -gt 0) {
  Write-Output ("CSVにあるがKintoneに無いtype_id: {0}" -f ($missing -join ", "))
}

if ($updates.Count -eq 0) {
  Write-Output "更新対象なし"
  exit 0
}

$batchSize = 100
for ($i = 0; $i -lt $updates.Count; $i += $batchSize) {
  $batch = $updates[$i..([Math]::Min($i + $batchSize - 1, $updates.Count - 1))]
  $payload = @{ app = $appId; records = $batch } | ConvertTo-Json -Depth 6
  $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
  Invoke-RestMethod -Method Put -Uri "$base/records.json" -Headers $headersJson -Body $payloadBytes | Out-Null
}

Write-Output ("更新完了: {0}件" -f $updates.Count)


