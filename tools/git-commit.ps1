<#
  MatSelect UTF-8 safe git commit helper (ASCII-only source).
  Usage:
    .\tools\git-commit.ps1 -Paths backend/app/api -Message "feat(api): ..."
    .\tools\git-commit.ps1 -All -Message "chore(repo): ..."
  Why: PowerShell passes Chinese args to git as GBK, corrupting commit
  messages. This helper writes the message to a UTF-8 file and uses
  `git commit -F`.
#>
[CmdletBinding(DefaultParameterSetName = 'Paths')]
param(
  [Parameter(ParameterSetName = 'Paths', Mandatory = $true)][string[]]$Paths,
  [Parameter(ParameterSetName = 'All', Mandatory = $true)][switch]$All,
  [Parameter(Mandatory = $true)][string]$Message,
  [string[]]$ExtraBody = @()
)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
git config --local i18n.commitEncoding utf-8 2>&1 | Out-Null
git config --local i18n.logOutputEncoding utf-8 2>&1 | Out-Null
git config --local core.quotepath false 2>&1 | Out-Null
$msgFile = Join-Path $root '.gitmessage.tmp'
$content = $Message
if ($ExtraBody.Count -gt 0) { $content += "`n`n" + ($ExtraBody -join "`n") }
[System.IO.File]::WriteAllText($msgFile, $content + "`n", (New-Object System.Text.UTF8Encoding($false)))
if ($All) { git add -A 2>&1 | Out-Null } else { git add -- $Paths 2>&1 | Out-Null }
$staged = @(git diff --cached --name-only 2>$null)
if ($staged.Count -eq 0) {
  Write-Host '[git-commit] nothing staged, skipped.'
  Remove-Item $msgFile -ErrorAction SilentlyContinue
  exit 0
}
git commit -F $msgFile 2>&1 | Out-Null
$code = $LASTEXITCODE
Remove-Item $msgFile -ErrorAction SilentlyContinue
Write-Host "[git-commit] exit=$code branch=$((git rev-parse --abbrev-ref HEAD) -join '')"
exit $code