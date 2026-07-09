param(
    [string]$BranchName
)

function Invoke-Step {
    param([string]$Command)
    Write-Host "→ $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ここで失敗しました: $Command" -ForegroundColor Red
        Write-Host "処理を中断します。内容を確認してください(コンフリクトの可能性があります)。" -ForegroundColor Yellow
        exit 1
    }
}

if ([string]::IsNullOrWhiteSpace($BranchName)) {
    Write-Host "❌ ブランチ名が指定されていません。" -ForegroundColor Red
    exit 1
}

Invoke-Step "git checkout main"
Invoke-Step "git pull origin main"
Invoke-Step "git merge $BranchName"
Invoke-Step "npm run prod"
Invoke-Step "git add ."
Invoke-Step 'git commit -m "config切り替え(本番用)"'
Invoke-Step "git push origin main"

Write-Host ""
Write-Host "✅ 本番反映が完了しました($BranchName → main)" -ForegroundColor Green