#!/usr/bin/env pwsh
<#
.SYNOPSIS
SoulChord 全量构建脚本 — 从源码到 NSIS 安装包
.DESCRIPTION
1. 检查环境  2. 安装 Python 依赖  3. PyInstaller 构建 3 个后端
4. pkg/便携 Node 构建 Netease  5. 构建 Electron 前端
6. electron-builder 打包 NSIS  7. 验证输出
#>
$ErrorActionPreference = "Stop"

# 强制 Python UTF-8 模式（修复 .pth 文件含中文字符路径时的 GBK 解码问题）
$env:PYTHONUTF8 = "1"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BuildDir    = Join-Path $ProjectRoot "build"
$DistPy      = Join-Path $ProjectRoot "dist_py"
$ElectronDir = [IO.Path]::Combine($ProjectRoot, "SoulChord-deskpet-skin", "SoulChord-front")

Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      SoulChord Build Pipeline        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray

# ═══════════════════════════════════════════════
# Step 0: 检查前置条件
# ═══════════════════════════════════════════════
Write-Host "`n[0/7] Checking prerequisites..." -ForegroundColor Yellow

$pythonVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) { throw "Python not found in PATH" }
Write-Host "  ✓ Python: $pythonVer" -ForegroundColor Green

$nodeVer = node --version 2>&1
if ($LASTEXITCODE -ne 0) { throw "Node.js not found in PATH" }
Write-Host "  ✓ Node.js: $nodeVer" -ForegroundColor Green

$npmVer = npm --version 2>&1
if ($LASTEXITCODE -ne 0) { throw "npm not found in PATH" }
Write-Host "  ✓ npm: $npmVer" -ForegroundColor Green

try { pyinstaller --version 2>$null | Out-Null; Write-Host "  ✓ PyInstaller" -ForegroundColor Green }
catch { Write-Host "  Installing PyInstaller..." -ForegroundColor Yellow; pip install pyinstaller }

# ═══════════════════════════════════════════════
# Step 1: 安装 Python 依赖
# ═══════════════════════════════════════════════
Write-Host "`n[1/7] Installing Python dependencies..." -ForegroundColor Yellow

Push-Location $ProjectRoot
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install agent deps failed" }
Pop-Location

Push-Location ([IO.Path]::Combine($ProjectRoot, "api", "music_agent_api"))
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install music_agent_api deps failed" }
Pop-Location

Push-Location ([IO.Path]::Combine($ProjectRoot, "api", "QQMusicApi-main"))
pip install -e ".[web]"
if ($LASTEXITCODE -ne 0) { throw "pip install qqmusic_api deps failed" }
Pop-Location

Write-Host "  ✓ Python dependencies installed" -ForegroundColor Green

# ═══════════════════════════════════════════════
# Step 2: PyInstaller 构建 3 个 Python 后端
# ═══════════════════════════════════════════════
Write-Host "`n[2/7] Building Python services with PyInstaller..." -ForegroundColor Yellow

if (Test-Path $DistPy) { Remove-Item -Recurse -Force $DistPy }
New-Item -ItemType Directory -Path $DistPy -Force | Out-Null

# Agent Runtime
Write-Host "  → Agent Runtime..." -ForegroundColor Yellow
Push-Location $ProjectRoot
pyinstaller (Join-Path $BuildDir "agent.spec") --clean --distpath (Join-Path $DistPy "agent")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller agent failed" }
Write-Host "    ✓ agent.exe" -ForegroundColor Green
Pop-Location

# Music Agent API
Write-Host "  → Music Agent API..." -ForegroundColor Yellow
Push-Location $ProjectRoot
pyinstaller (Join-Path $BuildDir "music_api.spec") --clean --distpath (Join-Path $DistPy "music_api")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller music_api failed" }
Write-Host "    ✓ music_api.exe" -ForegroundColor Green
Pop-Location

# QQMusicApi
Write-Host "  → QQMusicApi..." -ForegroundColor Yellow
Push-Location $ProjectRoot
pyinstaller (Join-Path $BuildDir "qqmusic_api.spec") --clean --distpath (Join-Path $DistPy "qqmusic_api")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller qqmusic_api failed" }
Write-Host "    ✓ qqmusic_api.exe" -ForegroundColor Green
Pop-Location

# ═══════════════════════════════════════════════
# Step 3: 构建 NeteaseCloudMusicApi
# ═══════════════════════════════════════════════
Write-Host "`n[3/7] Building NeteaseCloudMusicApi..." -ForegroundColor Yellow

$neteaseDir = Join-Path $DistPy "netease"
New-Item -ItemType Directory -Path $neteaseDir -Force | Out-Null

$neteaseBuilt = $false

Push-Location (Join-Path $BuildDir "netease-wrapper")
npm install | Out-Null

try {
    npx pkg . --targets node18-win-x64 --output (Join-Path $neteaseDir "netease_api.exe")
    if ($LASTEXITCODE -eq 0) { $neteaseBuilt = $true }
}
catch { }
Pop-Location

if ($neteaseBuilt) {
    Write-Host "  ✓ netease_api.exe (pkg)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ pkg failed, falling back to portable Node.js..." -ForegroundColor Yellow

# ── Fallback: portable Node.js ──
Write-Host "  → Downloading portable Node.js..." -ForegroundColor Yellow
$nodeUrl = "https://nodejs.org/dist/v18.20.4/node-v18.20.4-win-x64.zip"
$nodeZip = Join-Path $env:TEMP "node-v18.20.4-win-x64.zip"
try {
    Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeZip -UseBasicParsing
}
catch {
    Write-Host "  ✗ Download failed. Build with --skip-netease flag to skip Netease." -ForegroundColor Red
    exit 1
}

$nodeTemp = Join-Path $neteaseDir "temp_node"
Expand-Archive -Path $nodeZip -DestinationPath $nodeTemp -Force
Move-Item ([IO.Path]::Combine($nodeTemp, "node-v18.20.4-win-x64", "node.exe")) $neteaseDir -Force
Remove-Item -Recurse -Force $nodeTemp
Remove-Item $nodeZip -Force

Write-Host "  → Installing NeteaseCloudMusicApi..." -ForegroundColor Yellow
Push-Location $neteaseDir
npm init -y | Out-Null
npm install NeteaseCloudMusicApi | Out-Null

# Write launcher.js via .NET to avoid PowerShell parsing JS syntax
$jsCode = @'
const path = require('path');
process.env.PORT = process.env.PORT || '3000';
try {
  const api = require('NeteaseCloudMusicApi');
  if (typeof api === 'function') api();
  else if (api.serve) api.serve();
  else if (api.default) api.default();
  else console.error('Cannot start NeteaseCloudMusicApi');
} catch (e) {
  console.error('Failed to start:', e.message);
  process.exit(1);
}
'@
[System.IO.File]::WriteAllText((Join-Path $neteaseDir "launcher.js"), $jsCode, [System.Text.UTF8Encoding]::new($false))
Pop-Location

Write-Host "  ✓ NeteaseCloudMusicApi (portable Node.js)" -ForegroundColor Green
}

# ═══════════════════════════════════════════════
# Step 4: 构建 Electron 前端
# ═══════════════════════════════════════════════
Write-Host "`n[4/7] Building Electron frontend..." -ForegroundColor Yellow

Push-Location $ElectronDir
npm install | Out-Null
npm run build
if ($LASTEXITCODE -ne 0) { throw "Electron frontend build failed" }
Pop-Location
Write-Host "  ✓ Frontend built" -ForegroundColor Green

# ═══════════════════════════════════════════════
# Step 5: electron-builder 打包
# ═══════════════════════════════════════════════
Write-Host "`n[5/7] Packaging with electron-builder..." -ForegroundColor Yellow

Push-Location $ElectronDir
# 使用 npmmirror 镜像避免 GitHub 下载失败（中国网络环境）
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
npm run electron:build
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }
Pop-Location
Write-Host "  ✓ Package created" -ForegroundColor Green

# ═══════════════════════════════════════════════
# Step 6: 验证输出
# ═══════════════════════════════════════════════
Write-Host "`n[6/7] Verifying output..." -ForegroundColor Yellow

$releaseDir = Join-Path $ElectronDir "release"
if (Test-Path $releaseDir) {
    $installers = Get-ChildItem -Path $releaseDir -Recurse -Filter "*.exe" | Sort-Object Length -Descending
    foreach ($exe in $installers) {
        $size = [math]::Round($exe.Length / 1MB, 1)
        Write-Host "  → $($exe.Name)  ($size MB)" -ForegroundColor Green
    }
} else {
    Write-Host "  ✗ Release directory not found!" -ForegroundColor Red
}

# ═══════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════
Write-Host "`n╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       Build Complete! 🎉              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "Installer: $releaseDir" -ForegroundColor Green
Write-Host ""

# ── Show size summary ──
if (Test-Path $DistPy) {
    $totalPy = (Get-ChildItem -Path $DistPy -Recurse | Measure-Object -Property Length -Sum).Sum
    Write-Host "Backend size: $([math]::Round($totalPy / 1MB, 1)) MB" -ForegroundColor Gray
}
