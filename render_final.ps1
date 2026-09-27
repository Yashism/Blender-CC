<#
.SYNOPSIS
  Bolt's Night Shift Ep. 5 "Blind Corner": final render + deliverables, with Blender as the only tool.

.DESCRIPTION
  Run from the project folder (e.g. C:\blender-cc):

    powershell -ExecutionPolicy Bypass -File .\render_final.ps1 -Calibrate   # ~15 min test, writes a report
    powershell -ExecutionPolicy Bypass -File .\render_final.ps1              # the full render (overnight)

  Steps: (1) Pillow check/install into .pydeps (one time, needs internet), (2) in-cab screen images +
  audio, (3) optional calibration, (4) the 1440 frames at 1920x1080 (Cycles on the GPU), (5) captions,
  9:16 cut and the two MP4s + SRT in renders\final.
  Safe to re-run at any time: finished frames are kept and skipped, so a second night just continues.
  To stop: close the window or press Ctrl+C (at most the frame in progress is lost).

.PARAMETER Blender          Path to blender.exe (found automatically if it is in C:\blender-4.5 or Program Files).
.PARAMETER Calibrate        Render a few test frames, print an estimate for the whole episode, then stop.
.PARAMETER CalibrateFrames  How many frames to time with -Calibrate (default 6).
.PARAMETER Samples          Cycles samples for the story shots (default 64).
.PARAMETER CardsSamples     Samples for the simple rule/brand card shots (default 32).
.PARAMETER Frames           Only these frames, e.g. 1-720 (the MP4s are made once all 1440 exist).
.PARAMETER MaxHours         Stop cleanly after this many hours of rendering (e.g. 9 to be done by morning).
.PARAMETER FinishOnly       Skip rendering; only make the captions, MP4s and SRT from the finished frames.
.PARAMETER CPU              Force CPU rendering (only if the GPU misbehaves; about 3.5x slower).
.PARAMETER RebuildScreens   Re-make the in-cab screen images even though they are all present.
.PARAMETER Res              Render size (default 1920x1080; smaller only for quick tests).
#>
[CmdletBinding()]
param(
    [string]$Blender = "",
    [switch]$Calibrate,
    [int]$CalibrateFrames = 6,
    [int]$Samples = 64,
    [int]$CardsSamples = 32,
    [string]$Frames = "",
    [double]$MaxHours = 0,
    [switch]$FinishOnly,
    [switch]$CPU,
    [switch]$RebuildScreens,
    [string]$Res = "1920x1080"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location -LiteralPath $Root
$StartTime = Get-Date

$FinalDir = Join-Path $Root "renders/final"
$LogDir = Join-Path $FinalDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("run_{0:yyyyMMdd_HHmmss}.log" -f $StartTime)

function Say([string]$Text, [string]$Color = "White") {
    Write-Host $Text -ForegroundColor $Color
    Add-Content -LiteralPath $LogFile -Value $Text
}
function Step([string]$Text) {
    Say ""
    Say ("=" * 78) Cyan
    Say ("  " + $Text + "   [" + (Get-Date -Format "HH:mm") + "]") Cyan
    Say ("=" * 78) Cyan
}
function Fail([string]$Text) {
    Say ""
    Say ("ERROR: " + $Text) Red
    Say ("Log file: " + $LogFile) Yellow
    Allow-Sleep
    exit 1
}

# ------------------------------------------------------------------ keep Windows awake while running
$script:AwakeSet = $false
function Keep-Awake {
    try {
        if (-not ("Ep05.Power" -as [type])) {
            Add-Type -Namespace Ep05 -Name Power -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
"@
        }
        # ES_CONTINUOUS (0x80000000) + ES_SYSTEM_REQUIRED (0x1): no sleep while this window runs.
        [void][Ep05.Power]::SetThreadExecutionState([uint32]2147483649)
        $script:AwakeSet = $true
        Say "Windows will not go to sleep while this runs (back to normal when it ends)." Green
    } catch {
        Say "Could not stop Windows from sleeping automatically. Please set Settings > System >" Yellow
        Say "Power > 'Make my device sleep after' to Never (plugged in) for tonight." Yellow
    }
}
function Allow-Sleep {
    if ($script:AwakeSet) {
        try { [void][Ep05.Power]::SetThreadExecutionState([uint32]2147483648) } catch { }
        $script:AwakeSet = $false
    }
}

# ------------------------------------------------------------------ Blender
function Find-Blender {
    if ($Blender) {
        $p = $Blender.Trim('"', "'", " ")
        if (Test-Path -LiteralPath $p -PathType Leaf) { return (Resolve-Path -LiteralPath $p).Path }
        if (Test-Path -LiteralPath (Join-Path $p "blender.exe")) { return (Join-Path $p "blender.exe") }
        Fail "Blender not found at '$Blender'."
    }
    $candidates = @("C:\blender-4.5\blender.exe")
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Blender Foundation\Blender 4.5\blender.exe")
    }
    $candidates += @(Get-ChildItem -Path "C:\blender-4.5*\blender.exe" -ErrorAction SilentlyContinue |
                     ForEach-Object { $_.FullName })
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c -PathType Leaf)) { return $c }
    }
    Say "Blender 4.5 was not found in C:\blender-4.5 or in Program Files." Yellow
    $p = Read-Host "Paste the full path to blender.exe (or press Enter to quit)"
    $p = $p.Trim('"', "'", " ")
    if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return $p }
    Fail "Blender not found. Re-run with -Blender 'C:\path\to\blender.exe'."
}

function Invoke-Blender([string]$Title, [string[]]$BArgs) {
    Say ("> blender " + ($BArgs -join " ")) DarkGray
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"      # Blender writes harmless notes to stderr
    try {
        & $script:BlenderExe @BArgs 2>&1 | ForEach-Object {
            $line = "$_"
            Write-Host $line
            Add-Content -LiteralPath $LogFile -Value $line
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($null -eq $code) { $code = 0 }
    return [int]$code
}

function Blender-Py([string]$Script, [string[]]$ScriptArgs) {
    $a = @("-b", "--factory-startup", "-q", "--python-exit-code", "1", "-P", $Script, "--") + $ScriptArgs
    return (Invoke-Blender $Script $a)
}

# ================================================================== start
Say ""
Say "Bolt's Night Shift, Ep. 5 'Blind Corner' - final render" Cyan
Say ("Project: " + $Root)
Say ("Log:     " + $LogFile)

$script:BlenderExe = Find-Blender
$ver = ""
$old = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $ver = "" + (& $script:BlenderExe --version 2>$null | Select-Object -First 1)
} catch { } finally { $ErrorActionPreference = $old }
Say ("Blender: " + $script:BlenderExe + "  (" + $ver + ")")
if ($ver -and ($ver -notmatch "Blender 4\.5")) {
    Say "WARNING: this project is made for Blender 4.5 LTS; other versions may look different." Yellow
}

# disk space (frames ~10 GB + temporary captioned frames ~10 GB)
try {
    $drive = (Get-Item -LiteralPath $Root).PSDrive
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    Say ("Free disk space on " + $drive.Name + ": " + $freeGB + " GB")
    if ($freeGB -lt 25) {
        Say "WARNING: less than 25 GB free. The finished frames need about 10 GB and the finishing" Yellow
        Say "step temporarily needs about 10 GB more. Please free up space if you can." Yellow
    }
} catch { }

# power
try {
    $bat = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue
    if ($bat -and (@(1, 4, 5) -contains [int]$bat.BatteryStatus)) {
        Say "WARNING: the laptop is running on battery. Please plug in the charger." Yellow
    }
} catch { }
Say "Tip: plug in the charger, set Power mode to 'Best performance', and leave the lid OPEN." DarkGray
Keep-Awake

try {
    # -------------------------------------------------------------- 1. Pillow
    Step "1/5  Checking Pillow (image library) inside Blender's Python"
    $rc = Blender-Py "scripts/ep05/pydeps.py" @("ensure")
    if ($rc -ne 0) { Fail "Pillow is not available (see the message above). Connect to the internet and run again." }

    if (-not $FinishOnly) {
        # ---------------------------------------------------------- 2. screen images + audio
        Step "2/5  In-cab screen images and audio"
        # The screen images ship with the project (assets/ui/seq, one per frame). They are only
        # re-made when some are missing or with -RebuildScreens, so a git checkout stays clean.
        $seqDir = Join-Path $Root "assets/ui/seq"
        $seqCount = @(Get-ChildItem -Path $seqDir -Filter "ui_*.png" -ErrorAction SilentlyContinue).Count
        if ($RebuildScreens -or $seqCount -lt 1440) {
            Say "Making the in-cab screen images ($seqCount of 1440 present)..."
            $rc = Blender-Py "scripts/ep05/pydeps.py" @("run", "scripts/ep05/screen_seq.py")
            if ($rc -ne 0) { Fail "Making the in-cab screen images failed." }
        } else {
            Say "In-cab screen images: all 1440 present." Green
        }
        $rc = Blender-Py "scripts/ep05/pydeps.py" @("run", "scripts/ep05/sfx.py", "--out", "renders/final/ep05_audio.wav")
        if ($rc -ne 0) { Fail "Making the audio failed." }

        $common = @("--samples", "$Samples", "--cards-samples", "$CardsSamples", "--res", $Res)
        if ($CPU) { $common += @("--device", "cpu") }

        # ---------------------------------------------------------- 3. calibration
        if ($Calibrate) {
            Step "3/5  Calibration: timing $CalibrateFrames test frames (the first GPU run also prepares the GPU, ~5 min)"
            $rc = Blender-Py "scripts/ep05/render_final.py" (@("--calibrate", "$CalibrateFrames") + $common)
            if ($rc -ne 0) { Fail "Calibration failed (exit code $rc)." }
            $rep = Join-Path $FinalDir "calibration/report.txt"
            Say ""
            Say "Calibration done. Please send us the text of:" Green
            Say ("    " + $rep) Green
            Say "(the test images are next to it). Then start the full render with:" Green
            Say "    powershell -ExecutionPolicy Bypass -File .\render_final.ps1" Green
            return
        }

        # ---------------------------------------------------------- 4. render
        Step "4/5  Rendering the episode frames (resumes automatically; Ctrl+C or closing the window stops)"
        $rargs = @() + $common
        if ($Frames) { $rargs += @("--frames", $Frames) }
        if ($MaxHours -gt 0) { $rargs += @("--max-hours", ("{0}" -f $MaxHours)) }
        $rc = Blender-Py "scripts/ep05/render_final.py" $rargs
        if ($rc -eq 3) {
            Say ""
            Say "Stopped before the end (time limit). Finished frames are saved." Yellow
            Say "Run the same command again (e.g. tomorrow night) and it continues where it stopped." Yellow
            return
        } elseif ($rc -eq 4) {
            Fail "Some frames failed to render. Run the same command again to retry them."
        } elseif ($rc -ne 0) {
            Fail "The render stopped with an error (exit code $rc). Run the same command again to resume; if it keeps failing, send us the log."
        }
        if ($Frames) {
            Say ""
            Say "The requested frames ($Frames) are done. Run without -Frames to render the rest and make the videos." Green
            return
        }
    }

    # -------------------------------------------------------------- 5. finish
    Step "5/5  Captions, 9:16 cut, MP4 videos and subtitles"
    $rc = Blender-Py "scripts/ep05/finish_final.py" @()
    if ($rc -ne 0) { Fail "The finishing step failed (exit code $rc)." }

    $mins = [math]::Round(((Get-Date) - $StartTime).TotalMinutes)
    Say ""
    Say ("ALL DONE in " + $mins + " minutes. Deliverables are in " + $FinalDir + ":") Green
    Say "    ep05_blind_corner_16x9.mp4   (1920x1080)" Green
    Say "    ep05_blind_corner_9x16.mp4   (1080x1920, Reels)" Green
    Say "    ep05_captions.srt" Green
    try { Invoke-Item -LiteralPath $FinalDir } catch { }
} finally {
    Allow-Sleep
}
