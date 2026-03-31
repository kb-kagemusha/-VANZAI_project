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

$oldCodes = @(
  '文字列__1行_',
  '文字列__1行__0',
  '文字列__1行__1',
  '文字列__1行__2',
  '文字列__1行__3',
  '文字列__1行__4',
  '文字列__1行__5',
  '文字列__1行__6',
  '文字列__1行__7',
  '文字列__1行__8',
  '文字列__1行__9',
  '文字列__1行__10',
  '文字列__1行__11',
  '文字列__1行__12',
  '文字列__1行__13',
  '文字列__1行__14',
  '文字列__1行__15',
  '文字列__1行__16',
  '文字列__1行__17',
  '文字列__1行__18',
  '文字列__1行__19',
  '文字列__1行__20',
  '文字列__1行__21',
  '文字列__1行__22',
  '数値',
  '数値_0',
  '数値_1',
  '数値_5',
  '数値_4'
)

Write-Output "============================================================"
Write-Output "App307: delete old Japanese field codes"
Write-Output "============================================================"

$layoutResp = Invoke-RestMethod -Method Get -Uri "$base/preview/app/form/layout.json?app=$appId" -Headers $headersGet
$layout = $layoutResp.layout

function Remove-Codes($node, $removeSet) {
  if ($null -eq $node) { return $null }
  if ($node -is [System.Array]) {
    $updated = @()
    foreach ($child in $node) {
      $result = Remove-Codes $child $removeSet
      if ($null -ne $result) {
        $updated += $result
      }
    }
    return $updated
  }

  if ($node.PSObject.Properties.Name -contains 'code') {
    if ($removeSet.ContainsKey($node.code)) {
      return $null
    }
  }

  if ($node.PSObject.Properties.Name -contains 'layout') {
    $node.layout = @(Remove-Codes $node.layout $removeSet)
  }
  if ($node.PSObject.Properties.Name -contains 'fields') {
    $node.fields = @(Remove-Codes $node.fields $removeSet)
    if ($node.fields.Count -eq 0) {
      return $null
    }
  }

  return $node
}

$removeSet = @{}
$oldCodes | ForEach-Object { $removeSet[$_] = $true }
$layout = @(Remove-Codes $layout $removeSet)

Invoke-JsonRequest -method Put -url "$base/preview/app/form/layout.json" -body @{ app = $appId; layout = $layout } | Out-Null
Write-Output "Layout cleaned."

Invoke-JsonRequest -method Delete -url "$base/preview/app/form/fields.json" -body @{ app = $appId; fields = $oldCodes } | Out-Null
Write-Output "Old fields deleted."

Invoke-JsonRequest -method Post -url "$base/preview/app/deploy.json" -body @{ apps = @(@{ app = $appId }) } | Out-Null
Write-Output "Deploy requested."
