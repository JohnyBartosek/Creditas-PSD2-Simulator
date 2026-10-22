# Download (pull) or upload (commit + push) this repository.
param(
    [Parameter(Position = 0)]
    [ValidateSet("download", "upload", "status", "menu")]
    [string]$Action = "menu"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Invoke-Git {
    # $args, not a declared parameter: PowerShell would otherwise swallow -v.
    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($args -join ' ') exited with code $LASTEXITCODE"
    }
}

function Get-BranchState {
    $branch = "$((& git branch --show-current))".Trim()
    if (-not $branch) {
        throw "Detached HEAD. Checkout a branch before using this script."
    }

    Invoke-Git fetch origin

    $upstream = "origin/$branch"
    & git rev-parse --verify --quiet $upstream 2>$null | Out-Null
    $hasUpstream = $LASTEXITCODE -eq 0
    $behind = 0
    $ahead = 0
    if ($hasUpstream) {
        $counts = (& git rev-list --left-right --count "${upstream}...HEAD").Trim() -split '\s+'
        $behind = [int]$counts[0]
        $ahead = [int]$counts[1]
    }
    else {
        $ahead = [int](& git rev-list --count HEAD)
    }

    $dirty = @(& git status --porcelain)
    return [pscustomobject]@{
        Branch      = $branch
        Upstream    = $upstream
        HasUpstream = $hasUpstream
        Behind      = $behind
        Ahead       = $ahead
        Dirty       = @($dirty | Where-Object { $_ })
    }
}

function Show-SensitiveWarning {
    param([string[]]$Paths)
    $hits = @($Paths | Where-Object { $_ -match 'token|secret|password|credential|entra_config' })
    if ($hits.Count -eq 0) {
        return
    }
    Write-Host ""
    Write-Host "These files may contain secrets:"
    foreach ($path in $hits) {
        Write-Host "  $path"
    }
}

function Invoke-Status {
    $state = Get-BranchState
    Write-Host "Branch $($state.Branch): $($state.Ahead) to upload, $($state.Behind) to download, $($state.Dirty.Count) local change(s)."
    Write-Host ""
    Invoke-Git remote -v
    Write-Host ""
    Invoke-Git status
}

function Get-UnmergedPaths {
    return @(& git diff --name-only --diff-filter=U | Where-Object { $_ })
}

function Repair-UnmergedIndex {
    # git stash cannot run while the index still has conflict stages.
    # That is the "needs merge" / "could not write index" failure.
    $unmerged = Get-UnmergedPaths
    if ($unmerged.Count -eq 0) {
        return
    }

    Write-Host "An unfinished merge is blocking the download:"
    foreach ($path in $unmerged) {
        Write-Host "  $path"
    }
    Write-Host "Clearing the conflict from the index."
    Invoke-Git reset --mixed

    $marked = @()
    foreach ($path in $unmerged) {
        if ((Test-Path -LiteralPath $path) -and (Select-String -LiteralPath $path -Pattern '^<<<<<<< ' -Quiet)) {
            $marked += $path
        }
    }
    if ($marked.Count -gt 0) {
        Write-Host "These files still contain conflict markers, so they are put back to the last commit:"
        foreach ($path in $marked) {
            Write-Host "  $path"
        }
        Write-Host "Anything already saved with 'git stash' is left as it is."
        Invoke-Git restore --source=HEAD --worktree --staged -- @marked
    }
}

function Invoke-Download {
    $state = Get-BranchState
    if (-not $state.HasUpstream) {
        throw "Branch '$($state.Branch)' has no origin/$($state.Branch). Nothing to download."
    }
    Repair-UnmergedIndex
    $state = Get-BranchState
    if ($state.Ahead -gt 0 -and $state.Behind -gt 0) {
        throw "Branch '$($state.Branch)' has diverged from origin ($($state.Ahead) local, $($state.Behind) remote). This script does not merge or rebase."
    }
    if ($state.Behind -eq 0) {
        if ($state.Ahead -gt 0) {
            Write-Host "Nothing new on origin/$($state.Branch). $($state.Ahead) local commit(s) are not uploaded yet."
        }
        else {
            Write-Host "Already up to date with origin/$($state.Branch)."
        }
        return
    }

    $stashed = $false
    if ($state.Dirty.Count -gt 0) {
        Write-Host "Local changes are in the way of downloading $($state.Behind) commit(s)."
        Write-Host "They can be set aside and restored after the download."
        $confirm = Read-Host "Continue? [y/N]"
        if ($confirm -notmatch '^(y|yes)$') {
            Write-Host "Download cancelled."
            return
        }
        Invoke-Git stash push --include-untracked -m "git_sync download"
        $stashed = $true
    }

    Write-Host "Downloading $($state.Behind) commit(s) from origin/$($state.Branch)."
    try {
        Invoke-Git pull --ff-only origin $state.Branch
    }
    finally {
        if ($stashed) {
            Write-Host "Restoring local changes."
            & git stash pop
            if ($LASTEXITCODE -ne 0) {
                throw "Download finished, but restoring local changes failed. They remain in 'git stash'."
            }
        }
    }
    Write-Host "Download finished."
}

function Invoke-Upload {
    $name = "$((& git config --get user.name 2>$null))".Trim()
    $email = "$((& git config --get user.email 2>$null))".Trim()
    if (-not $name -or -not $email) {
        throw "git user.name and user.email must be set before upload. This script does not change git config."
    }

    $state = Get-BranchState
    Write-Host "Branch: $($state.Branch)"
    if ($state.HasUpstream) {
        Write-Host "Compared with origin/$($state.Branch): $($state.Ahead) to upload, $($state.Behind) to download."
    }
    else {
        Write-Host "No remote branch origin/$($state.Branch) yet."
    }

    if ((Get-UnmergedPaths).Count -gt 0) {
        throw "Unresolved merge. Finish or clear it before upload:`n$((Get-UnmergedPaths) -join "`n")"
    }

    if ($state.Behind -gt 0) {
        throw "origin/$($state.Branch) has $($state.Behind) commit(s) you do not have. Download first."
    }

    if ($state.Dirty.Count -eq 0 -and $state.Ahead -eq 0 -and $state.HasUpstream) {
        Write-Host "Nothing to upload."
        return
    }

    $candidatePaths = @()
    if ($state.Dirty.Count -gt 0) {
        Write-Host ""
        Write-Host "Local changes:"
        Invoke-Git status --short
        Write-Host ""
        Invoke-Git diff --stat
        $tracked = @(& git diff --name-only HEAD)
        $untracked = @(& git ls-files --others --exclude-standard)
        $candidatePaths = @($tracked + $untracked | Where-Object { $_ })
        Show-SensitiveWarning -Paths $candidatePaths

        $confirm = Read-Host "Commit these changes and push to origin? [y/N]"
        if ($confirm -notmatch '^(y|yes)$') {
            Write-Host "Upload cancelled."
            return
        }

        $message = Read-Host "Commit message (empty cancels)"
        if ([string]::IsNullOrWhiteSpace($message)) {
            Write-Host "Upload cancelled."
            return
        }

        Invoke-Git add -A
        $staged = @(& git diff --cached --name-only | Where-Object { $_ })
        if ($staged.Count -eq 0) {
            Write-Host "Nothing staged. Ignored files were left out."
            return
        }
        Invoke-Git commit -m $message
    }
    else {
        $confirm = Read-Host "Push $($state.Ahead) existing commit(s) to origin? [y/N]"
        if ($confirm -notmatch '^(y|yes)$') {
            Write-Host "Upload cancelled."
            return
        }
    }

    if ($state.HasUpstream) {
        Invoke-Git push origin $state.Branch
    }
    else {
        Invoke-Git push -u origin $state.Branch
    }
    Write-Host "Upload finished."
}

function Invoke-Menu {
    do {
        Write-Host ""
        $branchName = "$((& git branch --show-current))".Trim()
        Write-Host "Git sync  ($branchName)"
        Write-Host "  1  Download"
        Write-Host "  2  Upload"
        Write-Host "  3  Status"
        Write-Host "  0  Exit"
        $choice = Read-Host "Choice"
        try {
            switch ($choice) {
                "1" { Invoke-Download }
                "2" { Invoke-Upload }
                "3" { Invoke-Status }
                "0" { return }
                default { Write-Host "Unknown choice." }
            }
        }
        catch {
            Write-Host $_.Exception.Message
        }
    } while ($true)
}

try {
    switch ($Action) {
        "download" { Invoke-Download }
        "upload" { Invoke-Upload }
        "status" { Invoke-Status }
        "menu" { Invoke-Menu }
    }
}
catch {
    Write-Host $_.Exception.Message
    exit 1
}
