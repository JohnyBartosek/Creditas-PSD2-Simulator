# Stops running Reflex instances of this project.
$root = (Resolve-Path -LiteralPath $PSScriptRoot).Path.TrimEnd('\')

$processes = @(Get-CimInstance Win32_Process | Where-Object {
    $command = $_.CommandLine
    if (-not $command) { return $false }
    if ($command -notlike "*$root*") { return $false }
    return $command -match 'reflex\.exe'
})

if ($processes.Count -eq 0) {
    Write-Host "No running Reflex instances for this project."
    exit 0
}

$ids = [System.Collections.Generic.HashSet[int]]::new()
foreach ($process in $processes) {
    [void]$ids.Add([int]$process.ProcessId)
}

$roots = @($processes | Where-Object { -not $ids.Contains([int]$_.ParentProcessId) })
$failed = $false
foreach ($process in $roots) {
    Write-Host "Stopping PID $($process.ProcessId)"
    & taskkill.exe /PID $process.ProcessId /T /F
    if ($LASTEXITCODE -ne 0) {
        $failed = $true
    }
}

if ($failed) {
    exit 1
}
exit 0
