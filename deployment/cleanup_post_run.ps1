param(
  [switch]$CleanRemote
)

$ErrorActionPreference = "Stop"

function Remove-IfExists {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [switch]$Directory
  )
  if (Test-Path -LiteralPath $Path) {
    if ($Directory) {
      Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
    } else {
      Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
    }
    Write-Host "Removed: $Path"
  }
}

# Run-local artifacts (safe to remove)
Get-ChildItem -Force -Name ".tmp_perf_*" -ErrorAction SilentlyContinue | ForEach-Object {
  Remove-IfExists -Path $_ -Directory
}
Get-ChildItem -Force -Name ".tmp_run_*" -ErrorAction SilentlyContinue | ForEach-Object {
  Remove-IfExists -Path $_ -Directory
}

@(
  "deploy_*.zip",
  "sentinel_patch.zip",
  ".deploy_verify.txt",
  "npx_mermaid_log.txt",
  ".tmp_remote_probe.py"
) | ForEach-Object {
  Get-ChildItem -Force -Name $_ -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-IfExists -Path $_
  }
}

if ($CleanRemote) {
  Write-Host "Cleaning remote /tmp deploy artifacts on sentinelServer..."
  ssh -o BatchMode=yes sentinelServer "rm -f /tmp/sentinel_patch.zip /tmp/verify_deploy_hash.py /tmp/codex_remote_probe.py"
  if ($LASTEXITCODE -ne 0) {
    throw "Remote cleanup failed."
  }
  Write-Host "Remote cleanup complete."
}

Write-Host "Cleanup complete."
