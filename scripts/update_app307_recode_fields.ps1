$subdomain = "xtf5wpxp3gk2"
$guestSpaceId = "3"
$appId = 307
$apiToken = "Ki5axXHTyeA2obkyQ8Eybh22qwIZujoBLGegZQXd"

$base = "https://$subdomain.cybozu.com/k/guest/$guestSpaceId/v1"
$headersGet = @{"X-Cybozu-API-Token" = $apiToken}
$headersJson = @{"X-Cybozu-API-Token" = $apiToken; "Content-Type" = "application/json"}

function Invoke-JsonRequest([string]$method, [string]$url, $body) {
  $payload = $body | ConvertTo-Json -Depth 30
  $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
  return Invoke-RestMethod -Method $method -Uri $url -Headers $headersJson -Body $payloadBytes
}

$mapping = @(
  @{ old = "文字列__1行_"; new = "assignment_id"; label = "ID" },
  @{ old = "文字列__1行__0"; new = "company_name"; label = "会社名" },
  @{ old = "文字列__1行__1"; new = "owner_name"; label = "責任者" },
  @{ old = "文字列__1行__2"; new = "main_staff"; label = "メイン担当者" },
  @{ old = "文字列__1行__3"; new = "category_major"; label = "大カテゴリ" },
  @{ old = "文字列__1行__4"; new = "category_middle"; label = "中カテゴリ" },
  @{ old = "文字列__1行__5"; new = "category_minor"; label = "小カテゴリ" },
  @{ old = "文字列__1行__6"; new = "start_date"; label = "開始期間" },
  @{ old = "文字列__1行__7"; new = "end_date"; label = "終了期間" },
  @{ old = "文字列__1行__8"; new = "address"; label = "住所" },
  @{ old = "文字列__1行__9"; new = "gathering_time"; label = "集合時間" },
  @{ old = "文字列__1行__10"; new = "start_time"; label = "開始時間" },
  @{ old = "文字列__1行__11"; new = "end_time"; label = "終了時間" },
  @{ old = "文字列__1行__12"; new = "dismissal_time"; label = "解散時間" },
  @{ old = "文字列__1行__13"; new = "work_hours"; label = "1日稼働時間(h)" },
  @{ old = "文字列__1行__14"; new = "detail_url"; label = "詳細リンク" },
  @{ old = "文字列__1行__15"; new = "sales_rule"; label = "販売ルール" },
  @{ old = "文字列__1行__16"; new = "headcount_required"; label = "必要人数" },
  @{ old = "文字列__1行__17"; new = "base_reward"; label = "ベース報酬" },
  @{ old = "文字列__1行__18"; new = "incentive"; label = "インセンティブ" },
  @{ old = "文字列__1行__19"; new = "notes"; label = "備考" },
  @{ old = "文字列__1行__20"; new = "assignment_title"; label = "案件タイトル" },
  @{ old = "文字列__1行__21"; new = "facility_name"; label = "施設名" },
  @{ old = "文字列__1行__22"; new = "event_name"; label = "イベント名" },
  @{ old = "数値"; new = "headcount_director"; label = "人数内訳:ディレクター" },
  @{ old = "数値_0"; new = "headcount_staff"; label = "人数内訳:スタッフ" },
  @{ old = "数値_1"; new = "base_reward_director"; label = "ベース報酬:ディレクター" },
  @{ old = "数値_5"; new = "base_reward_assistant_director"; label = "ベース報酬:アシスタントディレクター" },
  @{ old = "数値_4"; new = "base_reward_staff"; label = "ベース報酬:スタッフ" }
)

Write-Output "============================================================"
Write-Output "App307: field recode (add new fields + layout + data copy)"
Write-Output "============================================================"

$fields = Invoke-RestMethod -Method Get -Uri "$base/preview/app/form/fields.json?app=$appId" -Headers $headersGet
$props = $fields.properties
$propNames = $props.PSObject.Properties.Name

$propertiesToAdd = @{}
$mappingDict = @{}
foreach ($item in $mapping) {
  $oldCode = $item.old
  $newCode = $item.new
  $mappingDict[$oldCode] = $newCode
  if (-not ($propNames -contains $oldCode)) {
    Write-Output "WARN: old code missing: $oldCode"
    continue
  }
  if ($propNames -contains $newCode) {
    Write-Output "SKIP: new code already exists: $newCode"
    continue
  }
  $oldProp = $props.$oldCode
  $newProp = $oldProp | ConvertTo-Json -Depth 30 | ConvertFrom-Json
  if ($newProp.PSObject.Properties.Name -contains 'id') {
    $newProp.PSObject.Properties.Remove('id') | Out-Null
  }
  if ($newProp.PSObject.Properties.Name -contains 'code') {
    $newProp.code = $newCode
  }
  $newProp.label = $item.label
  $propertiesToAdd[$newCode] = $newProp
}

if ($propertiesToAdd.Count -gt 0) {
  Write-Output ("Add fields: {0}" -f ($propertiesToAdd.Keys -join ', '))
  try {
    Invoke-JsonRequest -method Post -url "$base/preview/app/form/fields.json" -body @{ app = $appId; properties = $propertiesToAdd } | Out-Null
  } catch {
    Write-Output "ERROR: failed to add fields."
    Write-Output $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
      Write-Output $_.ErrorDetails.Message
    }
    exit 1
  }
} else {
  Write-Output "No new fields to add."
}

$fields = Invoke-RestMethod -Method Get -Uri "$base/preview/app/form/fields.json?app=$appId" -Headers $headersGet
$fieldsByCode = $fields.properties

$layoutResp = Invoke-RestMethod -Method Get -Uri "$base/preview/app/form/layout.json?app=$appId" -Headers $headersGet
$layout = $layoutResp.layout

function Collect-Codes($node, $set) {
  if ($null -eq $node) { return }
  if ($node -is [System.Array]) {
    foreach ($child in $node) { Collect-Codes $child $set }
    return
  }
  if ($node.PSObject.Properties.Name -contains 'code') {
    $set[$node.code] = $true
  }
  if ($node.PSObject.Properties.Name -contains 'layout') {
    Collect-Codes $node.layout $set
  }
  if ($node.PSObject.Properties.Name -contains 'fields') {
    Collect-Codes $node.fields $set
  }
}

$codesInLayout = @{}
Collect-Codes $layout $codesInLayout

$rowsToAdd = @()
foreach ($item in $mapping) {
  $newCode = $item.new
  if ($codesInLayout.ContainsKey($newCode)) {
    continue
  }
  $fieldType = if ($fieldsByCode.PSObject.Properties.Name -contains $newCode) { $fieldsByCode.$newCode.type } else { 'SINGLE_LINE_TEXT' }
  $rowsToAdd += @{
    type = 'ROW'
    fields = @(@{
      type = $fieldType
      code = $newCode
      size = @{ width = '200' }
    })
  }
}

if ($rowsToAdd.Count -gt 0) {
  $layout += $rowsToAdd
}
try {
  Invoke-JsonRequest -method Put -url "$base/preview/app/form/layout.json" -body @{ app = $appId; layout = $layout } | Out-Null
  Write-Output "Layout updated."
} catch {
  Write-Output "ERROR: failed to update layout."
  Write-Output $_.Exception.Message
  if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
    Write-Output $_.ErrorDetails.Message
  }
  exit 1
}

try {
  Invoke-JsonRequest -method Post -url "$base/preview/app/deploy.json" -body @{ apps = @(@{ app = $appId }) } | Out-Null
  Write-Output "Deploy requested."
} catch {
  Write-Output "ERROR: failed to deploy."
  Write-Output $_.Exception.Message
  exit 1
}

$recordsToUpdate = @()
$offset = 0
$limit = 500
$allFields = @('$id') + ($mapping | ForEach-Object { $_.old }) + ($mapping | ForEach-Object { $_.new })
$allFields = $allFields | Select-Object -Unique

while ($true) {
  $query = "order by `$id asc limit $limit offset $offset"
  $resp = Invoke-RestMethod -Method Get -Uri "$base/records.json?app=$appId&query=$([uri]::EscapeDataString($query))" -Headers $headersGet
  $records = $resp.records
  if (-not $records -or $records.Count -eq 0) { break }

  foreach ($record in $records) {
    $id = $record.'$id'.value
    $update = @{}
    foreach ($item in $mapping) {
      $oldCode = $item.old
      $newCode = $item.new
      $oldValue = $record.$oldCode.value
      $newValue = $record.$newCode.value
      if ($newValue -eq $null -or $newValue -eq '') {
        if ($oldValue -ne $null -and $oldValue -ne '') {
          $update[$newCode] = @{ value = $oldValue }
        }
      }
    }
    if ($update.Count -gt 0) {
      $recordsToUpdate += @{ id = $id; record = $update }
    }
  }

  if ($records.Count -lt $limit) { break }
  $offset += $limit
}

if ($recordsToUpdate.Count -gt 0) {
  Write-Output ("Records to update: {0}" -f $recordsToUpdate.Count)
  $batchSize = 100
  for ($i = 0; $i -lt $recordsToUpdate.Count; $i += $batchSize) {
    $batch = $recordsToUpdate[$i..([Math]::Min($i + $batchSize - 1, $recordsToUpdate.Count - 1))]
    try {
      Invoke-JsonRequest -method Put -url "$base/records.json" -body @{ app = $appId; records = $batch } | Out-Null
    } catch {
      Write-Output "ERROR: failed to update records."
      Write-Output $_.Exception.Message
      exit 1
    }
  }
} else {
  Write-Output "No record updates required."
}

Write-Output "Done."
