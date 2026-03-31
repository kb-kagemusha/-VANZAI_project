$subdomain = "xtf5wpxp3gk2"
$guestSpaceId = "3"
$appId = 164
$apiToken = "GtPvBi1Ne221KMvlSViaePrds1297d7Rj4h3xC91"

$base = "https://$subdomain.cybozu.com/k/guest/$guestSpaceId/v1"
$headersGet = @{"X-Cybozu-API-Token" = $apiToken}
$headersJson = @{"X-Cybozu-API-Token" = $apiToken; "Content-Type" = "application/json"}

function Normalize-Value([string]$value) {
  if (-not $value) { return "" }
  return $value.Trim()
}

Write-Output "============================================================"
Write-Output "App164: 重複削除 + 飲食:表記へ名称修正"
Write-Output "============================================================"

$recordsResponse = Invoke-RestMethod -Method Get -Uri "$base/records.json?app=$appId&query=limit%20500" -Headers $headersGet
$records = $recordsResponse.records
Write-Output ("対象レコード数: {0}" -f $records.Count)

# 1) 重複検出
$dupGroups = @{}
foreach ($record in $records) {
  $id = $record.'$id'.value
  if (-not $id) { continue }
  $level = Normalize-Value $record.category_level.value
  $name = Normalize-Value $record.name.value
  $parentMajor = Normalize-Value $record.parent_major.value
  $parentMiddle = Normalize-Value $record.parent_middle.value
  if ($level -eq 'minor' -and $parentMiddle) {
    $key = "$level|$name|$parentMiddle"
  } else {
    $key = "$level|$name|$parentMajor|$parentMiddle"
  }
  if (-not $dupGroups.ContainsKey($key)) { $dupGroups[$key] = @() }
  $dupGroups[$key] += [pscustomobject]@{
    id = [int]$id
    name = $name
    level = $level
    parent_major = $parentMajor
    parent_middle = $parentMiddle
  }
}

$deleteIds = @()
foreach ($key in $dupGroups.Keys) {
  $group = $dupGroups[$key]
  if ($group.Count -le 1) { continue }
  $keep = $group | Where-Object { $_.parent_major -match '\|' } | Sort-Object id | Select-Object -First 1
  if (-not $keep) {
    $keep = $group | Sort-Object id | Select-Object -First 1
  }
  $toDelete = $group | Where-Object { $_.id -ne $keep.id }
  $deleteIds += $toDelete | ForEach-Object { $_.id }
}

# 2) 名称修正（minorのみ、飲食○○ → 飲食:○○）
$renameUpdates = @()
foreach ($record in $records) {
  $id = $record.'$id'.value
  if (-not $id) { continue }
  $level = Normalize-Value $record.category_level.value
  $name = Normalize-Value $record.name.value
  if ($level -ne 'minor') { continue }
  if ($name -match '^飲食(.+)$' -and $name -notmatch '^飲食:') {
    $newName = "飲食:$($Matches[1])"
    $renameUpdates += @{ id = $id; record = @{ name = @{ value = $newName } } }
  }
}

# 3) 重複削除
if ($deleteIds.Count -gt 0) {
  Write-Output ("重複削除対象: {0}件" -f $deleteIds.Count)
  $batchSize = 100
  for ($i = 0; $i -lt $deleteIds.Count; $i += $batchSize) {
    $batch = $deleteIds[$i..([Math]::Min($i + $batchSize - 1, $deleteIds.Count - 1))]
    $payload = @{ app = $appId; ids = $batch } | ConvertTo-Json -Depth 5
    $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    Invoke-RestMethod -Method Delete -Uri "$base/records.json" -Headers $headersJson -Body $payloadBytes | Out-Null
  }
} else {
  Write-Output "重複削除対象なし"
}

# 4) 名称更新
if ($renameUpdates.Count -gt 0) {
  if ($deleteIds.Count -gt 0) {
    $deleteSet = @{}
    $deleteIds | ForEach-Object { $deleteSet[$_] = $true }
    $renameUpdates = $renameUpdates | Where-Object { -not $deleteSet[[int]$_.id] }
  }
  Write-Output ("名称修正対象: {0}件" -f $renameUpdates.Count)
  $batchSize = 100
  for ($i = 0; $i -lt $renameUpdates.Count; $i += $batchSize) {
    $batch = $renameUpdates[$i..([Math]::Min($i + $batchSize - 1, $renameUpdates.Count - 1))]
    $payload = @{ app = $appId; records = $batch } | ConvertTo-Json -Depth 6
    $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    Invoke-RestMethod -Method Put -Uri "$base/records.json" -Headers $headersJson -Body $payloadBytes | Out-Null
  }
} else {
  Write-Output "名称修正対象なし"
}

Write-Output "完了"


