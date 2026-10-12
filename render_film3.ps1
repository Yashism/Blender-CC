<#
.SYNOPSIS
  RAMS film 3 "Inside the Camera": final 1080p render on your NVIDIA GPU + post + music -> one MP4.

.DESCRIPTION
  Run from the unzipped folder (e.g. C:\film3):

    powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -Calibrate   # ~10 min: 2 test frames per scene + an ETA
    powershell -ExecutionPolicy Bypass -File .\render_film3.ps1              # the whole film

  Steps: (1) Pillow inside Blender's Python (one time, needs internet), (2) ffmpeg (downloaded once into
  .tools if it is not installed), (3) the 1,472 frames of the eight scenes at 1920x1080 on the GPU,
  (4) post for each clip (labels, titles, graphics, the logo), (5) the cut with music -> one MP4.
  Safe to re-run at any time: finished frames are kept and skipped, so an interrupted run just continues.
  To stop: close the window or press Ctrl+C (at most the frame in progress is lost).

.PARAMETER Blender     Path to blender.exe (found automatically in C:\blender-4.5* or Program Files).
.PARAMETER Calibrate   Render 2 test frames per scene, print an estimate for the whole film, then stop.
.PARAMETER Samples     Cycles samples (default 128, adaptive + denoised; 64 is faster and still clean).
.PARAMETER Clips       Which clips to render, e.g. a,b,c (default all: a,b,c,d,e,f). For two PCs.
.PARAMETER PostOnly    Skip rendering; only redo the post (clip videos) and the cut.
.PARAMETER CutOnly     Only join the six finished clip videos with the music.
.PARAMETER CPU         Force CPU rendering (only if the GPU misbehaves; much slower).
.PARAMETER Res         Render size (default 1920x1080).
#>
[CmdletBinding()]
param(
    [string]$Blender = "",
    [switch]$Calibrate,
    [int]$Samples = 128,
    [string]$Clips = "a,b,c,d,e,f",
    [switch]$PostOnly,
    [switch]$CutOnly,
    [switch]$CPU,
    [string]$Res = "1920x1080"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location -LiteralPath $Root
$StartTime = Get-Date

$OutRel = "renders/inside_1080"
$OutDir = Join-Path $Root $OutRel
$LogDir = Join-Path $OutDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("run_{0:yyyyMMdd_HHmmss}.log" -f $StartTime)
$FilmName = "RAMS_Inside_the_Camera_1080p.mp4"

# scene -> script, frame count, two calibration frames
$Scenes = [ordered]@{
    "a"       = @{ Script = "clip_a.py";       N = 432; Cal = "300,301" }
    "b"       = @{ Script = "clip_b.py";       N = 240; Cal = "150,151" }
    "c_pov"   = @{ Script = "clip_c_pov.py";   N = 106; Cal = "64,65" }
    "c_nn"    = @{ Script = "clip_c_nn.py";    N = 86;  Cal = "40,41" }
    "d"       = @{ Script = "clip_d.py";       N = 240; Cal = "150,151" }
    "e_stage" = @{ Script = "clip_e_stage.py"; N = 104; Cal = "60,61" }
    "e_aisle" = @{ Script = "clip_e_aisle.py"; N = 88;  Cal = "40,41" }
    "f"       = @{ Script = "clip_f.py";       N = 176; Cal = "100,101" }
}
$ClipScenes = @{ "a" = @("a"); "b" = @("b"); "c" = @("c_pov", "c_nn"); "d" = @("d"); "e" = @("e_stage", "e_aisle"); "f" = @("f") }

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
            if ($line -match "^\[inside\] frame \d+ ([\d.]+)s") { $script:FrameSecs += [double]$Matches[1] }
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

# ------------------------------------------------------------------ one scene
function Scene-Args([string]$Key, [string]$Dir, [string]$MapsDir) {
    $a = @("--res", $Res, "--samples", "$Samples")
    if ($CPU) { $a += @("--device", "cpu") } else { $a += @("--device", "gpu") }
    if ($Key -eq "c_nn") { $a += @("--maps", $MapsDir) }
    return $a
}
function Check-Rc([int]$rc, [string]$What) {
    if ($rc -eq 2) { Fail "No usable NVIDIA GPU was found. Update the NVIDIA driver, or run with -CPU (much slower)." }
    if ($rc -ne 0) { Fail "$What stopped with an error (exit code $rc). Run the same command again to resume; if it keeps failing, send the log." }
}
function Make-Maps([string]$PovDir, [string]$MapsDir) {
    $f64 = Get-ChildItem -LiteralPath $PovDir -Filter "f_0064.*" | Where-Object { $_.Name -notmatch "\.part\." } | Select-Object -First 1
    if (-not $f64) { Fail "Clip C: frame 64 of the camera view is missing in $PovDir." }
    $rc = Py "scripts/inside/nn_maps.py" @("--frame", $f64.FullName, "--anchors", (Join-Path $PovDir "anchors.json"),
                                          "--fr", "64", "--out", $MapsDir)
    Check-Rc $rc "The network-map step (clip C)"
}

# ================================================================== start
Say ""
Say "RAMS - film 3 'Inside the Camera' - final render" Cyan
Say ("Project: " + $Root)
Say ("Log:     " + $LogFile)

$sel = @($Clips.ToLower().Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($c in $sel) { if (-not $ClipScenes.ContainsKey($c)) { Fail "Unknown clip '$c' in -Clips (use letters a..f, e.g. -Clips a,b,c)." } }

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
    Say ("Free disk space on " + $drive.Name + ": " + $freeGB + " GB  (the frames need ~6 GB, the post ~2 GB more)")
    if ($freeGB -lt 12) { Say "WARNING: less than 12 GB free. Please free up space if you can." Yellow }
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
        Step "3/5  Calibration: 2 test frames per scene (the first GPU run also compiles kernels, a few minutes)"
        $cal = Join-Path $OutDir "calibration"
        $total = 0.0
        $report = @()
        foreach ($k in $Scenes.Keys) {
            $sc = $Scenes[$k]
            $dir = Join-Path $cal $k
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
            if ($k -eq "c_nn") { Make-Maps (Join-Path $cal "c_pov") (Join-Path $cal "nn_maps") }
            $a = @("--stills", $dir, "--frames", $sc.Cal) + (Scene-Args $k $dir (Join-Path $cal "nn_maps"))
            $rc = Blender-Py ("scripts/inside/" + $sc.Script) $a
            Check-Rc $rc "Calibration of scene $k"
            $sec = if ($script:FrameSecs.Count -gt 0) { $script:FrameSecs[-1] } else { 0 }
            $est = $sec * $sc.N
            $total += $est
            $line = "{0,-8} {1,6:N1} s/frame x {2,4} frames = {3,6:N0} min" -f $k, $sec, $sc.N, ($est / 60)
            $report += $line
            Say $line Green
        }
        $hours = $total / 3600 * 1.08                     # + scene loading per run
        $report += ""
        $report += ("Whole film: about {0:N1} hours of rendering at {1} samples, {2}, plus ~15 min of post." -f $hours, $Samples, $Res)
        Set-Content -LiteralPath (Join-Path $cal "report.txt") -Value $report
        Say ""
        Say $report[-1] Green
        Say ("Test frames are in " + $cal + " (open a few to check the look).") Green
        Say "Start the full render with:" Green
        Say "    powershell -ExecutionPolicy Bypass -File .\render_film3.ps1" Green
        return
    }

    # -------------------------------------------------------------- 3. render
    if (-not ($PostOnly -or $CutOnly)) {
        Step ("3/5  Rendering clips " + ($sel -join ", ") + " on the GPU (resumes automatically; Ctrl+C or closing the window stops)")
        $maps = Join-Path $OutDir "nn_maps"
        foreach ($c in $sel) {
            foreach ($k in $ClipScenes[$c]) {
                $sc = $Scenes[$k]
                $dir = Join-Path $OutDir ("clip_" + $k)
                New-Item -ItemType Directory -Force -Path $dir | Out-Null
                Get-ChildItem -LiteralPath $dir -Filter "*.part.*" -ErrorAction SilentlyContinue | Remove-Item -Force
                $done = @(Get-ChildItem -LiteralPath $dir -Filter "f_*.png" -ErrorAction SilentlyContinue).Count
                if ($done -ge $sc.N) { Say ("scene " + $k + ": all " + $sc.N + " frames already done") Green; continue }
                if ($k -eq "c_nn") { Make-Maps (Join-Path $OutDir "clip_c_pov") $maps }
                Say ("scene " + $k + ": " + $done + "/" + $sc.N + " frames done, rendering the rest...") Cyan
                $t0 = Get-Date
                $rc = Blender-Py ("scripts/inside/" + $sc.Script) (@("--render", $dir) + (Scene-Args $k $dir $maps))
                Check-Rc $rc "Rendering scene $k"
                Say ("scene " + $k + " done in " + [math]::Round(((Get-Date) - $t0).TotalMinutes) + " min") Green
            }
        }
    }

    # -------------------------------------------------------------- 4. post
    if (-not $CutOnly) {
        Step "4/5  Post: labels, titles, graphics and the logo -> one video per clip"
        foreach ($c in $sel) {
            $out = Join-Path $OutDir ("clip_" + $c + ".mp4")
            $pa = @("--clip", $c, "--out", $out, "--size", $Res)
            switch ($c) {
                "c" { $pa += @("--src", (Join-Path $OutDir "clip_c_pov"), "--nn", (Join-Path $OutDir "clip_c_nn")) }
                "e" { $pa += @("--src", (Join-Path $OutDir "clip_e_stage"), "--src2", (Join-Path $OutDir "clip_e_aisle")) }
                default { $pa += @("--src", (Join-Path $OutDir ("clip_" + $c))) }
            }
            foreach ($k in $ClipScenes[$c]) {
                $n = @(Get-ChildItem -LiteralPath (Join-Path $OutDir ("clip_" + $k)) -Filter "f_*.png" -ErrorAction SilentlyContinue).Count
                if ($n -lt $Scenes[$k].N) { Fail "Scene $k has only $n of $($Scenes[$k].N) frames. Render it first (run without -PostOnly)." }
            }
            $rc = Py "scripts/inside/post_inside.py" $pa
            if ($rc -ne 0) { Fail "The post step for clip $c failed (exit code $rc)." }
            Say ("clip " + $c + " -> " + $out) Green
        }
    }

    # -------------------------------------------------------------- 5. cut
    Step "5/5  The cut: six clips + music -> one film"
    $missing = @("a", "b", "c", "d", "e", "f" | Where-Object { -not (Test-Path -LiteralPath (Join-Path $OutDir ("clip_" + $_ + ".mp4"))) })
    if ($missing.Count -gt 0) {
        Say ("Clip videos still missing: " + ($missing -join ", ") + ". Copy them from the other PC into " + $OutDir) Yellow
        Say "and run:  powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -CutOnly" Yellow
        return
    }
    $rc = Py "scripts/inside/cut_film3.py" @("--dir", $OutDir, "--out", (Join-Path $OutDir $FilmName))
    if ($rc -ne 0) { Fail "The cut failed (exit code $rc)." }
    Copy-Item -LiteralPath (Join-Path $Root "assets/music/CREDITS.md") -Destination (Join-Path $OutDir "MUSIC_CREDIT.md") -Force

    $mins = [math]::Round(((Get-Date) - $StartTime).TotalMinutes)
    Say ""
    Say ("ALL DONE in " + $mins + " minutes. In " + $OutDir + ":") Green
    Say ("    " + $FilmName + "   (the film, 1920x1080, with music)") Green
    Say "    clip_a.mp4 ... clip_f.mp4               (each clip on its own)" Green
    Say "    MUSIC_CREDIT.md                         (credit line for the music, CC BY 4.0)" Green
    try { Invoke-Item -LiteralPath $OutDir } catch { }
} finally {
    Allow-Sleep
}
