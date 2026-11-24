"""The link-preview image (Open Graph / X card), drawn each run with today's call (2026-11-24).

A shared checkbowser.app link showed a cut-off card on Instagram ("owser", "now, or wait?"): the old og.png was
1200x630 with everything set left, and Instagram, WhatsApp and some Messenger views crop the image to a square or
a 4:5 box from the centre. Here everything sits in the middle SAFE px (inside a centred 4:5 box of the 630 px height), so
the wide cards (Facebook, X, LinkedIn, iMessage, Slack, Discord) and the square crops all show the whole message.

    og/today.png   today's call: "Wait if you can", "Sydney U91 202.9c/L · Tue 24 Nov", checkbowser.app
    og.png         the same layout with no call (static/og.png, the search pages' image and the fallback)

Colours are the brand's (app/src/constants/theme.ts): ink canvas, amber for the call on an act day, warm white
otherwise. Fonts: Inter (SIL OFL, fonts/LICENSE.txt). Needs Pillow; export_api.py fails soft without it.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, SAFE = 1200, 630, 480   # 480: inside a centred 4:5 crop (504 px) as well as a square one (630)
INK, WHITE, MUTED, AMBER = (20, 22, 24), (244, 241, 234), (154, 149, 140), (255, 178, 46)
TONE = {"act": AMBER, "wait": WHITE, "calm": WHITE}


def _font(weight, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", f"Inter-{weight}.ttf"), size)


def _fit(draw, text, weight, size, width, floor=20):
    """The largest font from `size` down (to `floor`) that sets `text` within `width` px."""
    while size > floor and draw.textlength(text, font=_font(weight, size)) > width: size -= 2
    return _font(weight, max(size, floor))


def draw(head=None, line=None, tone="calm", when=None):
    """The 1200x630 PNG as an Image: the lockup, then (with a call) the headline and its line, then the address.
    Every element is centred and within the middle SAFE px."""
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(HERE, "static", "og-lockup.png")).convert("RGBA")
    lw = 280 if head else 400
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    items = [("img", logo, 0)]
    if head:
        items += [("txt", (head, _fit(d, head, "ExtraBold", 76, SAFE), TONE.get(tone, WHITE)), 52)]
        if line: items += [("txt", (line, _fit(d, line, "SemiBold", 36, SAFE), WHITE), 26)]
        if when: items += [("txt", (when, _fit(d, when, "SemiBold", 30, SAFE), MUTED), 14)]
    else:
        q = "Fill up now, or wait?"
        items += [("txt", (q, _fit(d, q, "ExtraBold", 64, SAFE), WHITE), 48)]
    url = "checkbowser.app"
    items += [("txt", (url, _font("SemiBold", 30), AMBER), 52)]

    def height(it):
        kind, v, _ = it
        if kind == "img": return v.height
        t, f, _c = v; a, b = f.getbbox(t)[1], f.getbbox(t)[3]
        return b - a
    total = sum(height(it) + gap for it in items for gap in [it[2]])
    y = (H - total) // 2
    for kind, v, gap in items:
        y += gap
        if kind == "img":
            im.paste(v, ((W - v.width) // 2, y), v); y += v.height
        else:
            t, f, c = v; top, bottom = f.getbbox(t)[1], f.getbbox(t)[3]
            d.text(((W - d.textlength(t, font=f)) / 2, y - top), t, font=f, fill=c); y += bottom - top
    return im


def today(forecast, day_label):
    """(head, line, tone, when) for today's U91 call (or the first fuel's) from forecast.json, or None without one."""
    live = {r["fuel"]: r for r in forecast.get("live") or []}
    r = live.get("U91") or next(iter(live.values()), None)
    v = (r or {}).get("verdict") or {}
    if not r or not v.get("head") or not isinstance(r.get("now"), (int, float)): return None
    short = {"DL": "Diesel"}.get(r["fuel"], r["fuel"])
    tone = {"up": "act", "down": "wait"}.get(v.get("cls"), "calm")   # toneOf() in app/src/lib/outlook.ts
    return v["head"], f"Sydney {short} median {r['now']:.1f}c/L", tone, day_label


def write(out_dir, forecast, day_label):
    """Writes og/today.png under out_dir; returns its path relative to out_dir, or None when there is no call today."""
    t = today(forecast, day_label)
    if not t: return None
    os.makedirs(os.path.join(out_dir, "og"), exist_ok=True)
    draw(*t).save(os.path.join(out_dir, "og", "today.png"), optimize=True)
    return "og/today.png"


if __name__ == "__main__":   # python og_image.py: redraw static/og.png (the no-call image)
    draw().save(os.path.join(HERE, "static", "og.png"), optimize=True)
