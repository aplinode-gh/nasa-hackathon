param([switch]$Force)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$sites = @(
  @{ key = 'karachi'; lat = 24.86; lon = 67.01; province = 'Sindh' },
  @{ key = 'hyderabad'; lat = 25.39; lon = 68.37; province = 'Sindh' },
  @{ key = 'sukkur'; lat = 27.70; lon = 68.86; province = 'Sindh' },
  @{ key = 'larkana'; lat = 27.56; lon = 68.21; province = 'Sindh' },
  @{ key = 'lahore'; lat = 31.52; lon = 74.36; province = 'Punjab' },
  @{ key = 'faisalabad'; lat = 31.42; lon = 73.08; province = 'Punjab' },
  @{ key = 'multan'; lat = 30.19; lon = 71.47; province = 'Punjab' },
  @{ key = 'rawalpindi'; lat = 33.60; lon = 73.04; province = 'Punjab' },
  @{ key = 'gujranwala'; lat = 32.19; lon = 74.19; province = 'Punjab' },
  @{ key = 'sialkot'; lat = 32.49; lon = 74.52; province = 'Punjab' },
  @{ key = 'sargodha'; lat = 32.08; lon = 72.67; province = 'Punjab' },
  @{ key = 'bahawalpur'; lat = 29.40; lon = 71.68; province = 'Punjab' },
  @{ key = 'sahiwal'; lat = 30.67; lon = 73.11; province = 'Punjab' },
  @{ key = 'vehari'; lat = 30.04; lon = 72.35; province = 'Punjab' },
  @{ key = 'dera_ghazi_khan'; lat = 30.05; lon = 70.64; province = 'Punjab' },
  @{ key = 'peshawar'; lat = 34.01; lon = 71.58; province = 'Khyber Pakhtunkhwa' },
  @{ key = 'mardan'; lat = 34.20; lon = 72.04; province = 'Khyber Pakhtunkhwa' },
  @{ key = 'swat'; lat = 34.78; lon = 72.36; province = 'Khyber Pakhtunkhwa' },
  @{ key = 'quetta'; lat = 30.18; lon = 66.99; province = 'Balochistan' },
  @{ key = 'turbat'; lat = 26.00; lon = 63.05; province = 'Balochistan' },
  @{ key = 'gwadar'; lat = 25.13; lon = 62.33; province = 'Balochistan' },
  @{ key = 'islamabad'; lat = 33.68; lon = 73.05; province = 'Islamabad' },
  @{ key = 'gilgit'; lat = 35.92; lon = 74.31; province = 'Gilgit-Baltistan' },
  @{ key = 'muzaffarabad'; lat = 34.37; lon = 73.47; province = 'Azad Kashmir' }
)

$start = '20150101'
$end = '20241231'
$parameters = 'T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M,ALLSKY_SFC_SW_DWN'

$appRoot = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $appRoot 'datasets\power'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Remove-Bom([string]$path) {
  $text = [System.IO.File]::ReadAllText($path)
  [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

$manifest = @()

foreach ($site in $sites) {
  $path = Join-Path $outDir "$($site.key).csv"

  if (-not $Force -and (Test-Path $path) -and ((Get-Item $path).Length -gt 1000)) {
    $rowCount = (Get-Content $path | Measure-Object -Line).Lines - 1
    Write-Host "Skipping $($site.key) (already saved, $rowCount rows)"
    Remove-Bom $path
    $manifest += [pscustomobject]@{
      site = $site.key; province = $site.province; latitude = $site.lat
      longitude = $site.lon; rows = $rowCount; file = "power/$($site.key).csv"
    }
    continue
  }

  $uri = "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=$parameters&community=AG&longitude=$($site.lon)&latitude=$($site.lat)&start=$start&end=$end&format=JSON"
  Write-Host "Fetching $($site.key) ($($site.lat), $($site.lon))..."

  $attempt = 0
  while ($true) {
    try {
      $response = Invoke-RestMethod -Uri $uri -TimeoutSec 180
      break
    } catch {
      $attempt++
      if ($attempt -ge 5) { throw }
      Write-Host "  retry $attempt for $($site.key): $($_.Exception.Message)"
      Start-Sleep -Seconds (3 * $attempt)
    }
  }

  $parameterData = $response.properties.parameter
  $dates = $parameterData.T2M_MAX.PSObject.Properties.Name

  $rows = foreach ($date in $dates) {
    [pscustomobject]@{
      site = $site.key
      province = $site.province
      date = $date
      t2m_max = $parameterData.T2M_MAX.$date
      t2m_min = $parameterData.T2M_MIN.$date
      prectotcorr = $parameterData.PRECTOTCORR.$date
      rh2m = $parameterData.RH2M.$date
      ws2m = $parameterData.WS2M.$date
      allsky_sfc_sw_dwn = $parameterData.ALLSKY_SFC_SW_DWN.$date
    }
  }

  $rows | Export-Csv -Path $path -NoTypeInformation -Encoding UTF8
  Remove-Bom $path
  $manifest += [pscustomobject]@{
    site = $site.key; province = $site.province; latitude = $site.lat
    longitude = $site.lon; rows = $dates.Count; file = "power/$($site.key).csv"
  }
  Write-Host "  saved $($dates.Count) rows -> $path"
  Start-Sleep -Milliseconds 700
}

$manifest | Export-Csv -Path (Join-Path $appRoot 'datasets\power_manifest.csv') -NoTypeInformation -Encoding UTF8
Remove-Bom (Join-Path $appRoot 'datasets\power_manifest.csv')
Write-Host "Done. $($manifest.Count) site files written to $outDir"
