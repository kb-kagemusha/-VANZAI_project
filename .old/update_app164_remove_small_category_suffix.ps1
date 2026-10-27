$subdomain = "xtf5wpxp3gk2"
$guestSpaceId = "3"
$appId = 164
$apiToken = "GtPvBi1Ne221KMvlSViaePrds1297d7Rj4h3xC91"
$suffix = "(小カテゴリ有)"

$base = "https://$subdomain.cybozu.com/k/guest/$guestSpaceId/v1"
$headers = @{"X-Cybozu-API-Token" = $apiToken}

function Strip-Suffix([string]$value) {
  if (-not $value) { return "" }
  return ($value -replace [regex]::Escape($suffix), "").Trim()
}

function Normalize-Pipe([string]$value) {
  if (-not $value) { return "" }
  $parts = $value.Split("|") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
  return ($parts -join "|")
}

Write-Output "============================================================"
Write-Output "App164: '(小カテゴリ有)' 除去更新"
Write-Output "============================================================"

$recordsResponse = Invoke-RestMethod -Method Get -Uri "$base/records.json?app=$appId&query=limit%20500" -Headers $headers
$records = $recordsResponse.records
Write-Output ("対象レコード数: {0}" -f $records.Count)

$updates = @()
foreach ($record in $records) {
  $recordId = $record.'$id'.value
  if (-not $recordId) { continue }

  $name = $record.name.value
  $parentMajor = $record.parent_major.value
  $parentMiddle = $record.parent_middle.value

  $newName = Strip-Suffix $name
  $newParentMajor = Normalize-Pipe (Strip-Suffix $parentMajor)
  $newParentMiddle = Strip-Suffix $parentMiddle

  if (($newName -eq $name) -and ($newParentMajor -eq $parentMajor) -and ($newParentMiddle -eq $parentMiddle)) {
    continue
  }

  $recordUpdate = @{ id = $recordId; record = @{} }
  if ($newName -ne $name) { $recordUpdate.record.name = @{ value = $newName } }
  if ($newParentMajor -ne $parentMajor) { $recordUpdate.record.parent_major = @{ value = $newParentMajor } }
  if ($newParentMiddle -ne $parentMiddle) { $recordUpdate.record.parent_middle = @{ value = $newParentMiddle } }

  $updates += $recordUpdate
}

if ($updates.Count -eq 0) {
  Write-Output "更新対象なし"
  exit 0
}

$batchSize = 100
for ($i = 0; $i -lt $updates.Count; $i += $batchSize) {
  $batch = $updates[$i..([Math]::Min($i + $batchSize - 1, $updates.Count - 1))]
  $payload = @{ app = $appId; records = $batch } | ConvertTo-Json -Depth 6
  Invoke-RestMethod -Method Put -Uri "$base/records.json" -Headers ($headers + @{"Content-Type" = "application/json"}) -Body $payload | Out-Null
}

Write-Output ("更新完了: {0}件" -f $updates.Count)

