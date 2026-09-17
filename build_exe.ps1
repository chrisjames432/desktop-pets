$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; executable was not built.' }
    python -m PyInstaller --clean --noconfirm DesktopPets.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed. Install requirements-build.txt first.' }
    Write-Output 'Built dist\DesktopPets.exe. Test it on Windows without Python before sharing.'
} finally {
    Pop-Location
}
