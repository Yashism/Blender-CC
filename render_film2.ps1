<#
.SYNOPSIS
  RAMS film 2 "See. Detect. Protect.": final 1080p render on your NVIDIA GPU + sound + post -> one MP4.

.DESCRIPTION
  Run from the unzipped folder (e.g. C:\film2):

    powershell -ExecutionPolicy Bypass -File .\render_film2.ps1 -Calibrate   # ~15 min: 10 test frames + an ETA
    powershell -ExecutionPolicy Bypass -File .\render_film2.ps1              # the whole film

  Steps: (1) Pillow inside Blender's Python (one time, needs internet), (2) ffmpeg (downloaded once into
  .tools if it is not installed), (3) the music edit and the sound effects, (4) the 3,160 film frames at
  1920x1080 on the GPU, (5) the AI-vision post (scan, HUD, counters, titles, logo) + music -> one MP4,
  plus one clip per shot.
  Safe to re-run at any time: finished frames are kept and skipped, so an interrupted run just continues.
  To stop: close the window or press Ctrl+C (at most the frame in progress is lost).

.PARAMETER Blender     Path to blender.exe (found automatically in C:\blender-4.5* or Program Files).
.PARAMETER Calibrate   Render one test frame from each of the 10 shots, print an estimate, then stop.
.PARAMETER Samples     Cycles samples (default 64, adaptive + denoised, as the Kaggle final).
.PARAMETER MaxHours    Stop cleanly after this many hours of rendering (run again later to continue).
.PARAMETER PostOnly    Skip rendering; only redo the post (film + clips) from the finished frames.
.PARAMETER NoMusic     Make the film without music (sound effects only).
.PARAMETER CPU         Force CPU rendering (only if the GPU misbehaves; much slower).
.PARAMETER Res         Render size (default 1920x1080).
#>
[CmdletBinding()]
param(
    [string]$Blender = "",
    [switch]$Calibrate,
    [int]$Samples = 64,
    [double]$MaxHours = 0,
    [switch]$PostOnly,
    [switch]$NoMusic,
    [switch]$CPU,
    [string]$Res = "1920x1080"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location -LiteralPath $Root
$StartTime = Get-Date

$OutDir = Join-Path $Root "renders/film2_1080"
$FramesDir = Join-Path $OutDir "frames"
$LogDir = Join-Path $OutDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("run_{0:yyyyMMdd_HHmmss}.log" -f $StartTime)
$FilmName = "RAMS_AI_Camera_film2_1080p.mp4"
$NFrames = 3160
$CalFrames = "180,440,570,710,840,1050,1350,1670,2230,2880"     # one per shot

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
        if (-not ("RamsFilm.Power" -as [type])) {
            Add-Type -Namespace RamsFilm -Name Power -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
"@
        }
        [void][RamsFilm.Power]::SetThreadExecutionState([uint32]2147483649)
        $script:AwakeSet = $true
        Say "Windows will not go to sleep while this runs (back to normal when it ends)." Green
    } catch {
        Say "Could not stop Windows from sleeping automatically; set sleep to 'Never' while it renders." Yellow
    }
}
function Allow-Sleep {
    if ($script:AwakeSet) {
        try { [void][RamsFilm.Power]::SetThreadExecutionState([uint32]2147483648) } catch { }
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

$script:FrameSecs = @()
function Invoke-Blender([string[]]$BArgs) {
    Say ("> blender " + ($BArgs -join " ")) DarkGray
    $script:FrameSecs = @()
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"      # Blender writes harmless notes to stderr
    try {
        & $script:BlenderExe @BArgs 2>&1 | ForEach-Object {
            $line = "$_"
            # keep the console readable: hide Cycles' per-sample progress lines
            if ($line -notmatch "^Fra:\d+ .*\| (Sample|Rendered) ") { Write-Host $line }
            if ($line -match "^\[film2\] frame \d+ \(\d+/\d+\) ([\d.]+)s") { $script:FrameSecs += [double]$Matches[1] }
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
    return (Invoke-Blender $a)
}

function Py([string]$Script, [string[]]$ScriptArgs) {
    # plain-python scripts (post, cut) run on Blender's own Python, with Pillow from .pydeps
    return (Blender-Py "scripts/ep05/pydeps.py" (@("run", $Script) + $ScriptArgs))
}

# ------------------------------------------------------------------ ffmpeg
function Find-FFmpeg {
    $local = Get-ChildItem -Path (Join-Path $Root ".tools/ffmpeg") -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($local) { return $local.FullName }
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Say "ffmpeg (the video encoder) is not installed; downloading it once into .tools\ffmpeg (~90 MB)..." Yellow
    $tools = Join-Path $Root ".tools"
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $zip = Join-Path $tools "ffmpeg.zip"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $tools "ffmpeg") -Force
        Remove-Item -LiteralPath $zip -Force
    } catch {
        Fail ("Could not download ffmpeg: " + $_ + "`nInstall it yourself (winget install Gyan.FFmpeg) and run again.")
    }
    $local = Get-ChildItem -Path (Join-Path $tools "ffmpeg") -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $local) { Fail "ffmpeg.exe not found after the download." }
    return $local.FullName
}


function Device-Args {
    if ($CPU) { return @("--device", "cpu") }
    return @("--device", "gpu")
}
function Check-Rc([int]$rc, [string]$What) {
    if ($rc -eq 2) { Fail "No usable NVIDIA GPU was found. Update the NVIDIA driver, or run with -CPU (much slower)." }
    if ($rc -ne 0) { Fail "$What stopped with an error (exit code $rc). Run the same command again to resume; if it keeps failing, send the log." }
}

# ================================================================== start
Say ""
Say "RAMS - film 2 'See. Detect. Protect.' - final render" Cyan
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
try {
    $drive = (Get-Item -LiteralPath $Root).PSDrive
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    Say ("Free disk space on " + $drive.Name + ": " + $freeGB + " GB  (the frames need ~6 GB, the post ~15 GB more while it runs)")
    if ($freeGB -lt 25) { Say "WARNING: less than 25 GB free. Please free up space if you can." Yellow }
} catch { }
Keep-Awake

try {
    # -------------------------------------------------------------- 1. Pillow
    Step "1/5  Checking Pillow (image library) inside Blender's Python"
    $rc = Blender-Py "scripts/ep05/pydeps.py" @("ensure")
    if ($rc -ne 0) { Fail "Pillow is not available (see the message above). Connect to the internet and run again." }

    # -------------------------------------------------------------- 2. ffmpeg
    Step "2/5  ffmpeg (video encoder)"
    $env:FFMPEG = Find-FFmpeg
    Say ("ffmpeg: " + $env:FFMPEG) Green

    # -------------------------------------------------------------- calibration
    if ($Calibrate) {
        Step "Calibration: one test frame from each shot (the first GPU run also compiles kernels, a few minutes)"
        $cal = Join-Path $OutDir "calibration"
        Get-ChildItem -LiteralPath $cal -Filter "f_*" -ErrorAction SilentlyContinue | Remove-Item -Force
        $rc = Blender-Py "scripts/apps/film2.py" (@("--render", $cal, "--res", $Res, "--samples", "$Samples", "--jpeg",
                                                    "--pass-scale", "0.5", "--frames", $CalFrames) + (Device-Args))
        Check-Rc $rc "Calibration"
        $secs = @($script:FrameSecs | Select-Object -Skip 1)          # the first frame also compiles kernels
        if ($secs.Count -eq 0) { $secs = @($script:FrameSecs) }
        if ($secs.Count -eq 0) { Fail "Calibration rendered no frames (see the log)." }
        $avg = ($secs | Measure-Object -Average).Average
        $hours = $avg * $NFrames / 3600
        $report = @(("Average {0:N1} s per frame (one frame per shot) x {1} frames" -f $avg, $NFrames),
                    ("Whole film: about {0:N1} hours of rendering at {1} samples, {2}, plus ~30-60 min of post." -f $hours, $Samples, $Res))
        Set-Content -LiteralPath (Join-Path $cal "report.txt") -Value $report
        Say ""
        foreach ($l in $report) { Say $l Green }
        Say ("Test frames are in " + $cal + " (open a few to check the look).") Green
        Say "Start the full render with:" Green
        Say "    powershell -ExecutionPolicy Bypass -File .\render_film2.ps1" Green
        return
    }

    # -------------------------------------------------------------- 3. music + sound effects
    Step "3/5  Music edit and sound effects"
    $mp3 = Join-Path $Root "assets/music/In_Motion.mp3"
    $music = Join-Path $Root "assets/music/In_Motion_film2.wav"
    if ($NoMusic) {
        Say "-NoMusic: the film is made with sound effects only." Yellow
    } elseif (Test-Path -LiteralPath $mp3) {
        $rc = Py "scripts/apps/music_edit.py" @()
        if ($rc -ne 0) { Fail "The music edit failed (exit code $rc)." }
    } else {
        Say "assets\music\In_Motion.mp3 is missing: the film is made with sound effects only." Yellow
        $NoMusic = $true
    }
    $rc = Py "scripts/apps/sfx_film2.py" @()
    if ($rc -ne 0) { Fail "The sound effects step failed (exit code $rc)." }

    # -------------------------------------------------------------- 4. render
    if (-not $PostOnly) {
        Step "4/5  Rendering the 3,160 film frames on the GPU (resumes automatically; Ctrl+C or closing the window stops)"
        New-Item -ItemType Directory -Force -Path $FramesDir | Out-Null
        Get-ChildItem -LiteralPath $FramesDir -Filter "*.part.*" -ErrorAction SilentlyContinue | Remove-Item -Force
        $done = @(Get-ChildItem -LiteralPath $FramesDir -Filter "f_*.jpg" -ErrorAction SilentlyContinue).Count
        Say ("" + $done + " / " + $NFrames + " frames already done") Cyan
        $ra = @("--render", $FramesDir, "--res", $Res, "--samples", "$Samples", "--jpeg", "--pass-scale", "0.5") + (Device-Args)
        if ($MaxHours -gt 0) { $ra += @("--max-hours", ("{0}" -f $MaxHours)) }
        $rc = Blender-Py "scripts/apps/film2.py" $ra
        if ($rc -eq 3) {
            Say ""
            Say "Stopped after -MaxHours. Finished frames are saved; run the same command again to continue." Yellow
            return
        }
        Check-Rc $rc "The render"
    }
    $done = @(Get-ChildItem -LiteralPath $FramesDir -Filter "f_*.jpg" -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -notmatch "\.part\." }).Count
    if ($done -lt $NFrames) { Fail "Only $done of $NFrames frames exist. Run without -PostOnly to render the rest." }

    # -------------------------------------------------------------- 5. post
    Step "5/5  AI-vision post (scan, HUD, counters, titles, logo) + sound -> MP4 + one clip per shot"
    $jobs = [math]::Max(1, [math]::Min(8, [Environment]::ProcessorCount - 1))      # each worker holds 1080p frames
    $pa = @("--src", $FramesDir, "--out", (Join-Path $OutDir $FilmName), "--size", $Res, "--clips", "--jobs", "$jobs")
    if ($NoMusic) { $pa += @("--no-music") } else { $pa += @("--music", $music) }
    $rc = Py "scripts/apps/post_film2.py" $pa
    if ($rc -ne 0) { Fail "The post step failed (exit code $rc). Run with -PostOnly to retry it without rendering." }

    $mins = [math]::Round(((Get-Date) - $StartTime).TotalMinutes)
    Say ""
    Say ("ALL DONE in " + $mins + " minutes. In " + $OutDir + ":") Green
    Say ("    " + $FilmName + "   (the film, 1920x1080, music + sound effects)") Green
    Say "    clips\01_... .mp4 ... 11_end_logo.mp4  and  film2_clips.zip   (one clip per shot)" Green
    try { Invoke-Item -LiteralPath $OutDir } catch { }
} finally {
    Allow-Sleep
}
