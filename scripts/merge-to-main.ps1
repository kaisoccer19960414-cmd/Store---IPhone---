param(
    [string]$BranchName
)

function Invoke-Step {
    param([string]$Command)
    Write-Host "-> $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Command" -ForegroundColor Red
        Write-Host "Stopping. Please check for conflicts." -ForegroundColor Yellow
        exit 1
    }
}

function Invoke-CommitStep {
    # git commitは「変更が無い」場合、失敗扱い(終了コード1)になるが、
    # これはエラーではなく正常なケースなので、区別して無視する
    param([string]$Command)
    Write-Host "-> $Command" -ForegroundColor Cyan
    $output = Invoke-Expression $Command 2>&1 | Out-String
    Write-Host $output
    if ($LASTEXITCODE -ne 0) {
        if ($output -match "nothing to commit") {
            Write-Host "SKIP: no changes to commit, continuing." -ForegroundColor Yellow
        } else {
            Write-Host "FAILED: $Command" -ForegroundColor Red
            exit 1
        }
    }
}

if ([string]::IsNullOrWhiteSpace($BranchName)) {
    Write-Host "ERROR: Branch name is required." -ForegroundColor Red
    exit 1
}

Invoke-Step "git checkout main"
Invoke-Step "git pull origin main"
Invoke-Step "git merge $BranchName"
Invoke-Step "npm run prod"
Invoke-Step "git add ."
Invoke-CommitStep 'git commit -m "switch config to production"'
Invoke-Step "git push origin main"

Write-Host ""
Write-Host "DONE: merged $BranchName into main and pushed." -ForegroundColor Green