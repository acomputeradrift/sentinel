param(
  [string]$RemoteHost = "sentinelServer",
  [string]$CapturePath = "temp/_deploy_capture.txt",
  [string]$ArchivePath = "sentinel_patch.zip",
  [string]$RemoteArchivePath = "/tmp/sentinel_patch.zip",
  [string]$RemoteAppRoot = "/opt/sentinel/app",
  [string]$ServiceName = "sentinel",
  [string[]]$RequiredRemoteMarkers = @()
)

$ErrorActionPreference = "Stop"

# UTF-8 for console and for all capture writes so Cursor’s Read tool sees plain text (not UTF-16 “binary”) over UNC/SMB.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Ensure-DirectoryForFile {
  param([Parameter(Mandatory = $true)][string]$Path)
  $dir = Split-Path -Parent $Path
  if ([string]::IsNullOrWhiteSpace($dir)) {
    return
  }
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

function Write-Capture {
  param([Parameter(Mandatory = $true)][string]$Text)
  $Text | Out-File -FilePath $CapturePath -Append -Encoding utf8
}

function Run-Step {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )
  Write-Capture "=== $Name ==="
  try {
    # Capture first, then UTF-8 Out-File — avoids *>> UTF-16 mix and keeps $LASTEXITCODE from native exes (git/ssh).
    $stepOutput = & $Action 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    $stepOutput | Out-File -FilePath $CapturePath -Append -Encoding utf8
    Write-Capture "EXIT:$exitCode"
    if ($exitCode -ne 0) {
      throw "Step '$Name' failed with exit code $exitCode."
    }
  } catch {
    Write-Capture "FAILED:$($_.Exception.Message)"
    throw
  }
}

Ensure-DirectoryForFile -Path $CapturePath
Set-Content -Path $CapturePath -Value "" -Encoding utf8
Write-Capture "DEPLOY_START_UTC:$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Capture "PWD:$((Get-Location).Path)"

Run-Step -Name "git status -sb" -Action {
  git status -sb
}

$porcelain = (git status --porcelain | Out-String).Trim()
if (-not [string]::IsNullOrWhiteSpace($porcelain)) {
  Write-Capture "FAILED: Working tree is not clean."
  Write-Capture $porcelain
  throw "Deploy blocked: working tree is not clean."
}
Write-Capture "CLEAN_TREE:yes"

Run-Step -Name "git rev-parse HEAD" -Action {
  git rev-parse HEAD
}

Run-Step -Name "remove old archive" -Action {
  Remove-Item -Force $ArchivePath -ErrorAction SilentlyContinue
}

Run-Step -Name "git archive HEAD src" -Action {
  git archive --format=zip -o $ArchivePath HEAD src
}

Run-Step -Name "verify archive member src/sentinel/generation/render_core.py" -Action {
  python -c "import zipfile; z=zipfile.ZipFile(r'$ArchivePath'); print([n for n in z.namelist() if n=='src/sentinel/generation/render_core.py'])"
}

Run-Step -Name "scp archive to remote" -Action {
  scp -o BatchMode=yes $ArchivePath "${RemoteHost}:${RemoteArchivePath}"
}

Run-Step -Name "extract archive on remote" -Action {
  ssh -o BatchMode=yes $RemoteHost "sudo python3 -m zipfile -e $RemoteArchivePath $RemoteAppRoot"
}

if ($RequiredRemoteMarkers.Count -gt 0) {
  foreach ($marker in $RequiredRemoteMarkers) {
    if ([string]::IsNullOrWhiteSpace($marker)) { continue }
    Run-Step -Name "verify remote marker $marker" -Action {
      ssh -o BatchMode=yes $RemoteHost "grep -q '$marker' $RemoteAppRoot/src/sentinel/generation/render_core.py && echo MARKER_OK:$marker"
    }
  }
} else {
  Write-Capture "REMOTE_MARKER_CHECK:skipped (no RequiredRemoteMarkers provided)"
}

Run-Step -Name "restart service" -Action {
  ssh -o BatchMode=yes $RemoteHost "sudo -n systemctl restart $ServiceName"
}

Run-Step -Name "warmup sleep" -Action {
  Start-Sleep -Seconds 8
}

Run-Step -Name "health check" -Action {
  ssh -o BatchMode=yes $RemoteHost "curl -sS --max-time 15 http://127.0.0.1/health"
}

Run-Step -Name "commissioning header check" -Action {
  ssh -o BatchMode=yes $RemoteHost "curl -sS --max-time 15 -I http://127.0.0.1/commissioning/ | head -n 8"
}

Write-Capture "RESULT:SUCCESS"
Write-Capture "DEPLOY_END_UTC:$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Host "Deploy succeeded. Capture: $CapturePath"
