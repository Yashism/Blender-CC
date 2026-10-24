"""Peak-season safety checklist: an A3 floor poster (prints up to A2) and an A4 supervisor shift
check, in the twin film's look (its night aisle and dent renders, Outfit and Inter, the RAMS orange).

    blender -b --factory-startup -P scripts/twin/build.py -- --res 2000x1125 --samples 16 \\
        --out renders/poster/stills --list 60,220        # the night aisle and the dent
    python3 scripts/poster/peak_season.py                # -> renders/poster/*.pdf + *.png previews

HTML printed to PDF by headless Chromium (Playwright), so the type stays vector at any size.
"""
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from twin import post as PO  # noqa: E402  (the film's grade)

OUT = os.path.join(ROOT, "renders", "poster")
STILLS = os.path.join(OUT, "stills")
FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO = os.path.join(ROOT, "assets", "logo")

ORANGE = "#F55314"
BG = "#0B0E13"
INK = "#111827"
GREY = "#4B5563"
LINE = "#E5E7EB"
RED, AMBER, GREEN = "#DC2626", "#F59E0B", "#16A34A"

RULES = [
    ("Report every rack hit.",
     "However small. Tell your supervisor before you move on. Reporting a hit is never the mistake; hiding it is."),
    ("Walk your aisle for damage.",
     "Dented or bent uprights, twisted beams, missing beam locks, loose floor anchors. Found one? Report it and keep "
     "loads off it."),
    ("Right load, right place.",
     "Check the load sign before you put away and never go over it. Sound pallets only, square on the beams, heavy "
     "ones low."),
    ("Keep aisles and fire kit clear.",
     "No overflow stock in aisles, exits, or in front of extinguishers, hydrants and panels. Keep the space under "
     "sprinklers clear."),
    ("Check your forklift first.",
     "Forks, tyres, brakes, horn, lights, seat belt and camera, before every shift. Any fault: tag it out and "
     "report it."),
    ("Slow down where it's busy.",
     "Site limit <span class='blank s'></span> km/h. Slow down and sound the horn at aisle ends, crossings and blind "
     "corners. Carry loads low."),
    ("Keep people and forklifts apart.",
     "Walk in marked walkways, wear hi-vis, and make eye contact with the driver before you cross."),
    ("Trained and authorised only.",
     "Only authorised drivers operate forklifts and MHE. New and temporary staff get an induction and a buddy "
     "first."),
    ("Tired drivers hit racks.",
     "Take your breaks. If you're too tired to drive safely, say so. On long shifts, rotate tasks."),
    ("No flames near stock.",
     "No diyas, candles, incense or crackers on site. Festive lights only where approved, never on racking."),
]

RAG = [
    ("red", "Red", "Serious", "Unload the bay now and keep people out. Don't use it until it's repaired."),
    ("amber", "Amber", "Moderate", "Don't add load. Once it's empty, keep it empty. Repair within 4 weeks."),
    ("green", "Green", "Minor", "Within limits. Record it and recheck it at the next inspection."),
]

SHIFT_CHECKS = [
    "Rack walk: uprights, beams, beam locks and floor anchors",
    "Load signs present and readable on every bay",
    "Pallets sound and square on the beams; nothing overhanging the aisle",
    "Aisles, exits, fire equipment and the space under sprinklers clear",
    "Forklift pre-use check done for every truck",
    "Horns, lights, beacons and cameras working",
    "Walkways marked and clear; hi-vis worn",
    "New and temporary staff inducted; every driver authorised",
    "Breaks planned; no one driving overtired",
    "Festive decorations: no flames, approved lights only, none on racking",
]


def otf_to_ttf(src, dst):
    """CFF outlines -> TrueType (fontTools' otf2ttf): Chromium embeds CFF fonts as Type 3, which some
    print shops reject; TrueType goes in as a normal embedded font."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont, newTable
    f = TTFont(src)
    order = f.getGlyphOrder()
    gs = f.getGlyphSet()
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyphs[name] = pen.glyph()
    f["loca"] = newTable("loca")
    f["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder, glyf.glyphs = order, glyphs
    del f["CFF "]
    for t in ("VORG",):
        if t in f:
            del f[t]
    glyf.compile(f)
    hmtx = f["hmtx"]
    for name, g in glyf.glyphs.items():
        if hasattr(g, "xMin"):
            hmtx[name] = (hmtx[name][0], g.xMin)
    f["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for k in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
              "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, k, 1 if k == "maxZones" else 0)
    maxp.compile(f)
    post = f["post"]
    post.formatType, post.extraNames, post.mapping, post.glyphOrder = 2.0, [], {}, order
    f.sfntVersion = "\000\001\000\000"
    f.save(dst)


def font_faces():
    faces = [("Outfit", 700, "Outfit-Bold.ttf"), ("Outfit", 800, "Outfit-ExtraBold.ttf"),
             ("Inter", 400, "Inter-Regular.otf"), ("Inter", 500, "Inter-Medium.otf"),
             ("Inter", 600, "Inter-SemiBold.otf"), ("Inter", 700, "Inter-Bold.otf")]
    cache = os.path.join(OUT, "fonts")
    os.makedirs(cache, exist_ok=True)
    css = []
    for fam, w, f in faces:
        path = os.path.join(FONTS, f)
        if f.endswith(".otf"):
            ttf = os.path.join(cache, f[:-4] + ".ttf")
            if not os.path.exists(ttf):
                otf_to_ttf(path, ttf)
            path = ttf
        css.append(f"@font-face {{ font-family: '{fam}'; font-weight: {w}; src: url('file://{path}'); }}")
    return "\n".join(css)


def still(frame, name, crop=None, size=None):
    """A film still with the film's grade, as a print JPEG."""
    src = os.path.join(STILLS, f"f_{frame:04d}.png")
    if not os.path.exists(src):
        raise SystemExit(f"missing {src}: render the stills first (see the docstring)")
    im = Image.open(src).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    if size:
        im = im.resize(size, Image.LANCZOS)
    im = PO.grade(im)
    out = os.path.join(OUT, f"{name}.jpg")
    im.save(out, quality=92, subsampling=0)
    return out


def poster_html(hero, dent):
    rules = []
    for i, (head, body) in enumerate(RULES):
        rules.append(f"""
      <div class="rule">
        <div class="box"></div>
        <div class="num">{i + 1:02d}</div>
        <div class="txt"><h3>{head}</h3><p>{body}</p></div>
      </div>""")
    col_a, col_b = "".join(rules[:5]), "".join(rules[5:])
    rag = "".join(f"""
        <div class="rag-row">
          <div class="pill {k}">{label}</div>
          <div class="rag-txt"><b>{sev}.</b> {txt}</div>
        </div>""" for k, label, sev, txt in RAG)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{font_faces()}
@page {{ size: 297mm 420mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 297mm; height: 420mm; background: #fff; color: {INK};
  font-family: 'Inter', sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.hero {{ position: relative; height: 146mm; background: {BG} url('file://{hero}') center 58% / cover no-repeat; }}
.hero::after {{ content: ''; position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(11,14,19,.55) 0%, rgba(11,14,19,0) 28%, rgba(11,14,19,0) 45%,
                                      rgba(11,14,19,.92) 88%, {BG} 100%); }}
.hero > * {{ position: absolute; z-index: 1; }}
.logo {{ left: 16mm; top: 13mm; width: 44mm; }}
.chip {{ right: 16mm; top: 14.5mm; font: 600 3.6mm 'Inter'; letter-spacing: .5mm; color: #fff;
  border: .35mm solid rgba(255,255,255,.55); border-radius: 10mm; padding: 2.2mm 4.6mm; }}
.title {{ left: 16mm; right: 16mm; bottom: 12mm; color: #fff; }}
.title h1 {{ font: 700 21mm/0.98 'Outfit'; letter-spacing: -.3mm; }}
.title h1 em {{ font-style: normal; color: {ORANGE}; }}
.title p {{ margin-top: 4.5mm; font: 500 5mm/1.35 'Inter'; color: #D6DEE8; }}
.body {{ padding: 11mm 16mm 0; }}
.label {{ font: 700 3.5mm 'Inter'; letter-spacing: .7mm; color: {ORANGE}; text-transform: uppercase; }}
.label span {{ color: #9CA3AF; letter-spacing: .3mm; font-weight: 600; text-transform: none; margin-left: 2mm; }}
.rules {{ display: grid; grid-template-columns: 1fr 1fr; column-gap: 11mm; margin-top: 5mm; }}
.rule {{ display: grid; grid-template-columns: 8.5mm 13mm 1fr; align-items: start; padding: 4.1mm 0;
  border-top: .3mm solid {LINE}; min-height: 23.8mm; }}
.box {{ width: 6.2mm; height: 6.2mm; border: .55mm solid {INK}; border-radius: 1mm; margin-top: .9mm; }}
.num {{ font: 800 7.6mm/1 'Outfit'; color: {ORANGE}; letter-spacing: -.2mm; }}
.txt h3 {{ font: 700 5.4mm/1.15 'Outfit'; color: {INK}; }}
.txt p {{ margin-top: 1.3mm; font: 400 3.55mm/1.42 'Inter'; color: {GREY}; }}
.blank {{ display: inline-block; border-bottom: .3mm solid {INK}; width: 14mm; height: 3.6mm;
  vertical-align: -.6mm; }}
.dmg {{ display: grid; grid-template-columns: 74mm 1fr; column-gap: 9mm; margin-top: 6mm;
  background: #F6F7F9; border-radius: 3mm; padding: 6mm; }}
.dmg figure img {{ width: 74mm; height: 53mm; object-fit: cover; border-radius: 2mm; display: block; }}
.dmg figcaption {{ margin-top: 2.2mm; font: 500 3.2mm/1.35 'Inter'; color: {GREY}; }}
.dmg h2 {{ font: 700 6.2mm/1.15 'Outfit'; margin: 1.6mm 0 3.4mm; }}
.rag-row {{ display: grid; grid-template-columns: 19mm 1fr; column-gap: 4mm; align-items: center; padding: 2.5mm 0;
  border-top: .3mm solid #E3E6EA; }}
.rag-row:first-of-type {{ border-top: 0; }}
.pill {{ font: 700 3.5mm 'Inter'; color: #fff; text-align: center; border-radius: 6mm; padding: 1.6mm 0;
  letter-spacing: .3mm; text-transform: uppercase; }}
.pill.red {{ background: {RED}; }} .pill.amber {{ background: {AMBER}; color: #1F1300; }}
.pill.green {{ background: {GREEN}; }}
.rag-txt {{ font: 400 3.65mm/1.4 'Inter'; color: {INK}; }}
.rag-txt b {{ font-weight: 700; }}
.note {{ margin-top: 2.6mm; font: 400 2.9mm/1.35 'Inter'; color: #6B7280; }}
.fill {{ display: grid; grid-template-columns: 1.25fr 1fr 1fr; column-gap: 8mm; margin-top: 6.5mm; }}
.field {{ font: 600 3.3mm 'Inter'; color: {GREY}; letter-spacing: .2mm; }}
.field div {{ margin-top: 8.5mm; border-bottom: .4mm solid {INK}; }}
.foot {{ position: absolute; left: 16mm; right: 16mm; bottom: 9mm; display: flex; align-items: center;
  justify-content: space-between; border-top: .3mm solid {LINE}; padding-top: 4mm;
  font: 500 3.1mm 'Inter'; color: #6B7280; }}
.foot img {{ height: 6.2mm; margin-right: 3.5mm; vertical-align: middle; }}
.foot .l {{ display: flex; align-items: center; }}
</style></head><body>
<section class="hero">
  <img class="logo" src="file://{os.path.join(LOGO, 'rams_logo_white.png')}">
  <div class="chip">FESTIVE PEAK SEASON</div>
  <div class="title">
    <h1>Peak season.<br><em>Every hit counts.</em></h1>
    <p>Safety checklist for racks, forklifts and people. Read it before every shift.</p>
  </div>
</section>
<section class="body">
  <div class="label">Before every shift <span>tick each one</span></div>
  <div class="rules"><div>{col_a}</div><div>{col_b}</div></div>
  <div class="dmg">
    <figure>
      <img src="file://{dent}">
      <figcaption>A fork-tip hit at 2:14 a.m. Small dent, real risk: a damaged upright carries less load.</figcaption>
    </figure>
    <div>
      <div class="label">Found damage?</div>
      <h2>Rate it, then act.</h2>
      {rag}
      <p class="note">Traffic-light damage levels as in EN 15635. Your rack inspector sets the limits for your racking.</p>
    </div>
  </div>
  <div class="fill">
    <div class="field">Report rack hits to<div></div></div>
    <div class="field">Phone / WhatsApp<div></div></div>
    <div class="field">Fire assembly point<div></div></div>
  </div>
</section>
<footer class="foot">
  <div class="l"><img src="file://{os.path.join(LOGO, 'rams_logo_black.png')}">Rack safety by RAMS Digital · rams.digital</div>
  <div>Adapt it to your site's own safety rules.</div>
</footer>
</body></html>"""


def shift_html():
    rows = "".join(f"""
      <tr><td class="n">{i + 1}</td><td>{c}</td><td class="c"><span class="box"></span></td>
          <td class="c"><span class="box"></span></td><td></td></tr>""" for i, c in enumerate(SHIFT_CHECKS))
    log = "".join("""
      <tr><td></td><td></td><td></td><td class="rag"><span class="box r"></span><span class="box a"></span>
          <span class="box g"></span></td><td></td><td></td></tr>""" for _ in range(6))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{font_faces()}
@page {{ size: 210mm 297mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 210mm; height: 297mm; background: #fff; color: {INK}; font-family: 'Inter', sans-serif;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.top {{ background: {BG}; color: #fff; padding: 9mm 14mm 8mm; display: flex; align-items: flex-end;
  justify-content: space-between; }}
.top img {{ width: 30mm; }}
.top h1 {{ font: 700 8.6mm/1 'Outfit'; }}
.top h1 em {{ font-style: normal; color: {ORANGE}; }}
.top p {{ margin-top: 2mm; font: 500 3.3mm 'Inter'; color: #C9D2DD; text-align: right; }}
.wrap {{ padding: 7mm 14mm 0; }}
.fields {{ display: grid; grid-template-columns: 1fr 1fr 1.4fr 1.4fr; column-gap: 5mm; }}
.field {{ font: 600 2.9mm 'Inter'; color: {GREY}; letter-spacing: .2mm; }}
.field div {{ margin-top: 6.5mm; border-bottom: .3mm solid {INK}; }}
h2 {{ margin: 7mm 0 2.6mm; font: 700 4.6mm 'Outfit'; }}
h2 span {{ font: 500 3mm 'Inter'; color: #6B7280; margin-left: 2mm; }}
table {{ width: 100%; border-collapse: collapse; font-size: 3.2mm; }}
th {{ font: 700 2.6mm 'Inter'; letter-spacing: .3mm; text-transform: uppercase; color: #6B7280; text-align: left;
  vertical-align: bottom; padding: 1.6mm 2mm; border-bottom: .4mm solid {INK}; }}
td {{ padding: 0 2mm; height: 8.7mm; border-bottom: .25mm solid #D1D5DB; vertical-align: middle; line-height: 1.3; }}
td.n {{ font: 800 3.6mm 'Outfit'; color: {ORANGE}; width: 7mm; }}
td.c, th.c {{ text-align: center; width: 13mm; }}
.box {{ display: inline-block; width: 4.4mm; height: 4.4mm; border: .4mm solid {INK}; border-radius: .7mm;
  vertical-align: middle; }}
.box.r {{ border-color: {RED}; background: #FEE2E2; }} .box.a {{ border-color: {AMBER}; background: #FEF3C7; }}
.box.g {{ border-color: {GREEN}; background: #DCFCE7; }}
td.rag .box {{ margin-right: 1.4mm; }}
.log td {{ height: 10mm; }}
td.rag {{ white-space: nowrap; }}
.key {{ margin-top: 2.4mm; font: 400 2.75mm/1.45 'Inter'; color: #4B5563; }}
.key b {{ font-weight: 700; }}
.sign {{ display: grid; grid-template-columns: 1.3fr 0.6fr 1.3fr; column-gap: 6mm; margin-top: 5mm; }}
.foot {{ position: absolute; left: 14mm; right: 14mm; bottom: 8mm; display: flex; justify-content: space-between;
  align-items: center; border-top: .25mm solid {LINE}; padding-top: 3mm; font: 500 2.7mm 'Inter'; color: #6B7280; }}
.foot img {{ height: 4.4mm; margin-right: 2.6mm; vertical-align: middle; }}
</style></head><body>
<div class="top">
  <div><img src="file://{os.path.join(LOGO, 'rams_logo_white.png')}"></div>
  <div><h1>Peak-season <em>shift check</em></h1><p>Supervisor · one sheet per shift · keep with the shift log</p></div>
</div>
<div class="wrap">
  <div class="fields">
    <div class="field">Date<div></div></div>
    <div class="field">Shift<div></div></div>
    <div class="field">Zone / aisles<div></div></div>
    <div class="field">Supervisor<div></div></div>
  </div>
  <h2>Checks <span>tick OK or Issue; note what was done</span></h2>
  <table>
    <tr><th></th><th>Check</th><th class="c">OK</th><th class="c">Issue</th><th>Action / note</th></tr>
    {rows}
  </table>
  <h2>Rack hits and damage this shift <span>every one, however small</span></h2>
  <table class="log">
    <tr><th style="width:15mm">Time</th><th style="width:30mm">Aisle / bay / level</th><th>What happened</th>
        <th style="width:25mm">R / A / G</th><th style="width:34mm">Action taken</th><th style="width:24mm">Reported to</th></tr>
    {log}
  </table>
  <p class="key"><b>Red:</b> unload the bay now and keep people out. <b>Amber:</b> don't add load; once empty, keep it
    empty; repair within 4 weeks. <b>Green:</b> within limits; record and recheck at the next inspection.</p>
  <div class="sign">
    <div class="field">Supervisor signature<div></div></div>
    <div class="field">Time<div></div></div>
    <div class="field">Handed over to<div></div></div>
  </div>
</div>
<div class="foot">
  <div><img src="file://{os.path.join(LOGO, 'rams_logo_black.png')}">Rack safety by RAMS Digital · rams.digital</div>
  <div>Adapt it to your site's own safety rules.</div>
</div>
</body></html>"""


PRINT_JS = """
const { chromium } = require('playwright');
(async () => {
  const [html, pdf, w, h] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + html, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: pdf, width: w, height: h, printBackground: true, preferCSSPageSize: true,
                   margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await browser.close();
})();
"""


def print_pdf(html, name, w, h):
    hp = os.path.join(OUT, f"{name}.html")
    open(hp, "w").write(html)
    js = os.path.join(OUT, "_print.js")
    open(js, "w").write(PRINT_JS)
    pdf = os.path.join(OUT, f"{name}.pdf")
    subprocess.run(["node", js, hp, pdf, w, h], check=True)
    subprocess.run(["pdftoppm", "-png", "-r", "60", "-singlefile", pdf, os.path.join(OUT, f"{name}_preview")],
                   check=True)
    return pdf


def main():
    os.makedirs(OUT, exist_ok=True)
    hero = still(60, "hero_night_aisle")
    dent = still(220, "dent_closeup", crop=(0.24, 0.144, 0.80, 0.856))
    print(print_pdf(poster_html(hero, dent), "RAMS_peak_season_poster_A3", "297mm", "420mm"))
    print(print_pdf(shift_html(), "RAMS_peak_season_shift_check_A4", "210mm", "297mm"))


if __name__ == "__main__":
    main()
