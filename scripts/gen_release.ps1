$ErrorActionPreference = "Stop"

Push-Location (Join-Path $PSScriptRoot "..")

try {
    # HyperDrive.exe isn't committed: build it with dependencies\hyperdrive.spec and copy it here
    if (-not (Test-Path "HyperDrive.exe")) {
        throw "HyperDrive.exe not found. Build it and copy it to the repository root first."
    }

    $zip = "HyperDrive-windows.zip"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "HyperDrive", $zip

    New-Item -Path "HyperDrive" -ItemType Directory | Out-Null

    Copy-Item -Recurse -Force "assets" "HyperDrive\assets"

    # Already embedded inside release exe
    Remove-Item -Force -ErrorAction SilentlyContinue "HyperDrive\assets\versions.json"

    # Copy layout excluding game_images, game_screenshots and symlinks
    $layout = (Resolve-Path "layout").Path
    Get-ChildItem -Path $layout -Recurse | Where-Object {
        $relative = $_.FullName.Substring($layout.Length + 1)
        $relative -notmatch "^game_(images|screenshots)([\\/]|$)" -and
        -not $_.Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint)
    } | ForEach-Object {
        $destination = Join-Path "HyperDrive\layout" $_.FullName.Substring($layout.Length + 1)
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
        } else {
            New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
            Copy-Item -Path $_.FullName -Destination $destination -Force
        }
    }

    # The executable embeds the files from src it uses, but ResolvePath looks
    # for them next to it first and they've been needed there before
    Copy-Item -Recurse -Force "src" "HyperDrive\src"
    Get-ChildItem -Path "HyperDrive\src" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

    # Only the files committed to user_data: running the program (or importing
    # SettingsManager while building) writes settings.json and other user
    # files there, and those mustn't ship and overwrite the user's own
    $tracked = @(git -c core.quotepath=off ls-files -- "user_data")
    if ($LASTEXITCODE -ne 0) {
        throw "Couldn't list the files in user_data with git."
    }
    foreach ($file in $tracked) {
        $destination = Join-Path "HyperDrive" $file
        New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
        Copy-Item -LiteralPath $file -Destination $destination -Force
    }
    New-Item -Path "HyperDrive\stage_strike_app" -ItemType Directory | Out-Null
    Copy-Item -Recurse -Force "stage_strike_app\build" "HyperDrive\stage_strike_app\build"
    Copy-Item -Force "LICENSE" "HyperDrive\LICENSE"
    Copy-Item -Force "HyperDrive.exe" "HyperDrive\HyperDrive.exe"

    # ZipFile writes the entries with forward slashes (HyperDrive/layout/...),
    # which Compress-Archive doesn't do on every PowerShell version
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        (Resolve-Path "HyperDrive").Path,
        (Join-Path (Get-Location).Path $zip),
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    Remove-Item -Recurse -Force "HyperDrive"
}
finally {
    Pop-Location
}
