# Rendering on your PC (Windows)

This covers the one-off benchmark tonight. The same setup is reused later for the final episode render.

## One-time setup (about 10 minutes)

1. **Install Blender 4.5 LTS** from <https://www.blender.org/download/lts/4-5/>. The Windows installer is fine; so is the portable `.zip`. It can sit alongside any other Blender version you already have.
2. **Update the Intel graphics driver**, so Blender can use the Arc 140T graphics. Use the *Intel Driver & Support Assistant* (<https://www.intel.com/content/www/us/en/support/detect.html>), or install the latest *Intel Arc & Iris Xe Graphics* driver.
3. **Download the project**:
   1. While logged in to GitHub, open <https://github.com/yashism/blender-cc/archive/refs/heads/claude/trusting-lovelace-345i7f.zip>.
   2. Unzip it, for example to `C:\blender-cc`.
   
   If you use git instead: `git clone -b claude/trusting-lovelace-345i7f https://github.com/yashism/blender-cc.git C:\blender-cc`

## Run the benchmark (10–20 minutes, unattended)

1. Plug in the charger. Set **Windows Settings → System → Power → Power mode → Best performance**.
2. Open **PowerShell** and run the following. Adjust the first path if you unzipped somewhere else, and the Blender path if you used the portable zip.

```powershell
cd C:\blender-cc
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b --factory-startup -P scripts\benchmark.py
```

It builds a stand-in night-shift frame (FL-02 with Mittens, Bolt, Pickles, the roll cage, racks, lamps, haze and depth of field), then renders that frame at 1080p three times:

| Mode | What it tests |
| --- | --- |
| `eevee` | EEVEE on the Arc 140T graphics |
| `cycles_gpu` | Cycles on the Arc 140T graphics (oneAPI) |
| `cycles_cpu` | Cycles on the 16-core CPU |

At the end it prints a small table.

## Send back

- The text of `renders\benchmark\results.txt` (copy and paste it into the chat)
- Optionally, the three images `renders\benchmark\bench_*.png`, so the look of each mode can be compared

## If something goes wrong

- **`cycles_gpu` says "skipped (no GPU backend)":** update the Intel driver (step 2) and run again. The other two modes still give useful numbers.
- **One mode crashes:** re-run just the others, for example `... -P scripts\benchmark.py -- --modes eevee,cycles_cpu`.
- **It's taking forever:** each mode is a single frame, and the CPU mode is the slowest. Ten minutes or so for that one mode is normal.
