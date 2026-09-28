<#
.SYNOPSIS
  RAMS AI Camera launch film (v6): final 1080p render on your GPU + post + music + per-shot clips.

.DESCRIPTION
  Run from the project folder (e.g. C:\blender-cc):

    powershell -ExecutionPolicy Bypass -File .\render_film.ps1 -Calibrate   # ~10 min: times 5 frames, prints an ETA
    powershell -ExecutionPolicy Bypass -File .\render_film.ps1              # the full render + post

  Steps: (1) Pillow inside Blender's Python (one time, needs internet), (2) the music file, (3) ffmpeg
  (downloaded once into .tools if it is not installed), (4) optional calibration, (5) the 2436 film frames
  at 1920x1080 on the GPU + dissolve handles, (6) post: grade, titles, graphics, transitions, the logo
  ending, music -> MP4, plus one clip per shot.
  Safe to re-run at any time: finished frames are kept and skipped, so an interrupted run just continues.
  To stop: close the window or press Ctrl+C (at most the frame in progress is lost).

.PARAMETER Blender     Path to blender.exe (found automatically in C:\blender-4.5 or Program Files).
.PARAMETER Music       Path to "Can You Hear The Music" (mp3). Copied to assets\music once.
.PARAMETER NoMusic     Make the film without music.
.PARAMETER Calibrate   Render a few test frames, print an estimate for the whole film, then stop.
.PARAMETER Samples     Cycles samples (default 96; 64 is faster and still clean).
.PARAMETER Frames      Only these frames, e.g. 1-1000 (the video is made once all frames exist).
.PARAMETER MaxHours    Stop cleanly after this many hours of rendering.
.PARAMETER PostOnly    Skip rendering; only run the post (video + clips) from the finished frames.
.PARAMETER CPU         Force CPU rendering (only if the GPU misbehaves; much slower).
.PARAMETER Res         Render size (default 1920x1080).
#>
[CmdletBinding()]
param(
    [string]$Blender = "",
    [string]$Music = "",
    [switch]$NoMusic,
    [switch]$Calibrate,
    [int]$Samples = 96,
    [string]$Frames = "",
    [double]$MaxHours = 0,
    [switch]$PostOnly,
    [switch]$CPU,
    [string]$Res = "1920x1080"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location -LiteralPath $Root
$StartTime = Get-Date

$FilmDir = Join-Path $Root "renders/launch/film6"
$FramesDir = Join-Path $FilmDir "frames_final"
$LogDir = Join-Path $FilmDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("run_{0:yyyyMMdd_HHmmss}.log" -f $StartTime)
$MusicDst = Join-Path $Root "assets/music/Can_You_Hear_The_Music.mp3"
$FilmOut = Join-Path $FilmDir "RAMS_AI_Camera_film_v6_1080p.mp4"

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

function Invoke-Blender([string[]]$BArgs) {
    Say ("> blender " + ($BArgs -join " ")) DarkGray
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"      # Blender writes harmless notes to stderr
    try {
        & $script:BlenderExe @BArgs 2>&1 | ForEach-Object {
            $line = "$_"
            # keep the console readable: hide Cycles' per-sample progress lines
            if ($line -notmatch "^Fra:\d+ .*\| (Sample|Rendered) ") { Write-Host $line }
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

# ================================================================== start
Say ""
Say "RAMS AI Camera - launch film v6 - final render" Cyan
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
    Say ("Free disk space on " + $drive.Name + ": " + $freeGB + " GB  (the frames need ~12 GB, the post ~10 GB more)")
    if ($freeGB -lt 25) { Say "WARNING: less than 25 GB free. Please free up space if you can." Yellow }
} catch { }
Keep-Awake

try {
    # -------------------------------------------------------------- 1. Pillow
    Step "1/6  Checking Pillow (image library) inside Blender's Python"
    $rc = Blender-Py "scripts/ep05/pydeps.py" @("ensure")
    if ($rc -ne 0) { Fail "Pillow is not available (see the message above). Connect to the internet and run again." }

    # -------------------------------------------------------------- 2. music
    Step "2/6  Music"
    if ($NoMusic) {
        Say "-NoMusic: the film is made without music." Yellow
    } elseif (Test-Path -LiteralPath $MusicDst) {
        Say "Music found: assets\music\Can_You_Hear_The_Music.mp3" Green
    } else {
        $src = ""
        if ($Music) { $src = $Music.Trim('"', "'", " ") }
        if (-not $src) {
            $hit = @()
            foreach ($d in @("$env:USERPROFILE\Downloads", "$env:USERPROFILE\Music", "$env:USERPROFILE\Desktop", $Root)) {
                $hit += @(Get-ChildItem -Path $d -Recurse -Depth 2 -Include "*Hear*Music*.mp3" -ErrorAction SilentlyContinue)
            }
            if ($hit.Count -gt 0) {
                $src = $hit[0].FullName
                Say ("Found the track: " + $src) Green
            } else {
                Say "The music file 'Can You Hear The Music' (mp3) was not found in Downloads / Music / Desktop." Yellow
                $src = (Read-Host "Paste the full path to the mp3 (or press Enter to make the film without music)").Trim('"', "'", " ")
            }
        }
        if ($src -and (Test-Path -LiteralPath $src -PathType Leaf)) {
            New-Item -ItemType Directory -Force -Path (Split-Path $MusicDst) | Out-Null
            Copy-Item -LiteralPath $src -Destination $MusicDst -Force
            Say "Music copied to assets\music\Can_You_Hear_The_Music.mp3" Green
        } else {
            Say "No music: the film is made silent (re-run -PostOnly -Music <mp3> later to add it)." Yellow
            $NoMusic = $true
        }
    }

    # -------------------------------------------------------------- 3. ffmpeg
    Step "3/6  ffmpeg (video encoder)"
    $env:FFMPEG = Find-FFmpeg
    Say ("ffmpeg: " + $env:FFMPEG) Green

    if (-not $PostOnly) {
        $common = @("--samples", "$Samples", "--res", $Res, "--out", "renders/launch/film6/frames_final")
        if ($CPU) { $common += @("--device", "cpu") }

        # ---------------------------------------------------------- 4. calibration
        if ($Calibrate) {
            Step "4/6  Calibration: timing 5 test frames (the first GPU run also compiles kernels, a few minutes)"
            $rc = Blender-Py "scripts/launch/render_film6.py" (@("--calibrate", "5") + $common)
            if ($rc -ne 0) { Fail "Calibration failed (exit code $rc)." }
            Say ""
            Say ("Calibration done; the estimate is above and in " + (Join-Path $FilmDir "calibration\report.txt")) Green
            Say "Start the full render with:" Green
            Say "    powershell -ExecutionPolicy Bypass -File .\render_film.ps1" Green
            return
        }

        # ---------------------------------------------------------- 5. render
        Step "5/6  Rendering the film frames on the GPU (resumes automatically; Ctrl+C or closing the window stops)"
        $rargs = @() + $common
        if ($Frames) { $rargs += @("--frames", $Frames) }
        if ($MaxHours -gt 0) { $rargs += @("--max-hours", ("{0}" -f $MaxHours)) }
        $rc = Blender-Py "scripts/launch/render_film6.py" $rargs
        if ($rc -eq 3) {
            Say ""
            Say "Stopped before the end. Finished frames are saved; run the same command again to continue." Yellow
            return
        } elseif ($rc -eq 2) {
            Fail "No usable GPU was found. Update the NVIDIA driver, or run with -CPU (much slower)."
        } elseif ($rc -ne 0) {
            Fail "The render stopped with an error (exit code $rc). Run the same command again to resume; if it keeps failing, send the log."
        }
        if ($Frames) {
            Say ""
            Say "The requested frames ($Frames) are done. Run without -Frames to render the rest and make the video." Green
            return
        }
    }

    # -------------------------------------------------------------- 6. post
    Step "6/6  Post: grade, titles, graphics, transitions, logo ending, music -> MP4 + per-shot clips"
    $pargs = @("run", "scripts/launch/post_film6.py", "--src", "renders/launch/film6/frames_final",
               "--out", "renders/launch/film6/RAMS_AI_Camera_film_v6_1080p.mp4", "--size", $Res, "--clips")
    if ($NoMusic) { $pargs += @("--no-music") }
    $rc = Blender-Py "scripts/ep05/pydeps.py" $pargs
    if ($rc -ne 0) { Fail "The post step failed (exit code $rc)." }

    $mins = [math]::Round(((Get-Date) - $StartTime).TotalMinutes)
    Say ""
    Say ("ALL DONE in " + $mins + " minutes. In " + $FilmDir + ":") Green
    Say "    RAMS_AI_Camera_film_v6_1080p.mp4   (the film, 1920x1080, with music)" Green
    Say "    clips\01_... .mp4 + CLIP_LIST.txt  (one clip per shot)  and  v6_clips.zip" Green
    try { Invoke-Item -LiteralPath $FilmDir } catch { }
} finally {
    Allow-Sleep
}
