#!/usr/bin/env python3
"""Generate assets/demo.svg — the animated README hero.

The animation is generated rather than hand-drawn so the timeline stays
readable and the SVG stays reproducible: edit SCENES, re-run, commit the diff.

    python3 assets/build_demo.py

Standard library only, like everything else here.
"""

import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.svg")

W, H = 880, 516
LOOP = 11.5  # seconds per cycle
FADE = 0.3   # seconds of cross-fade at each edge

SANS = "ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

# Vertical slots. The ticker and the answer share slot A on purpose: the ticker
# is deleted before the answer is sent, so the answer takes its place.
SLOT_MSG1 = 84
SLOT_A = 142
SLOT_PERM = 260
SLOT_YES = 382
SLOT_DONE = 438


def esc(text):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def bubble(x, y, w, h, side):
    """Rounded chat bubble with the one squared-off corner Telegram uses."""
    r = 14
    cls = "user" if side == "user" else "bot"
    if side == "user":
        d = (
            "M{x} {y1} A{r} {r} 0 0 1 {xr} {y} L{x2r} {y} A{r} {r} 0 0 1 {x2} {y1} "
            "L{x2} {y2} L{xr} {y2} A{r} {r} 0 0 1 {x} {y2r} Z"
        ).format(
            x=x, y=y, r=r, xr=x + r, x2=x + w, x2r=x + w - r,
            y1=y + r, y2=y + h, y2r=y + h - r,
        )
    else:
        d = (
            "M{x} {y2} L{x} {y1} A{r} {r} 0 0 1 {xr} {y} L{x2r} {y} "
            "A{r} {r} 0 0 1 {x2} {y1} L{x2} {y2r} A{r} {r} 0 0 1 {x2r} {y2} Z"
        ).format(
            x=x, y=y, r=r, xr=x + r, x2=x + w, x2r=x + w - r,
            y1=y + r, y2=y + h, y2r=y + h - r,
        )
    return '<path class="bub %s" d="%s"/>' % (cls, d)


def text(x, y, content, cls="t", anchor="start"):
    return '<text class="%s" x="%d" y="%d" text-anchor="%s">%s</text>' % (
        cls, x, y, anchor, esc(content)
    )


def smil(start, end):
    """SMIL opacity track for one scene.

    The timeline is SMIL rather than CSS keyframes for one reason: graceful
    degradation. Scenes that live to the end of the loop carry opacity="1" as a
    static attribute, which any renderer that ignores animation — a social
    preview, a feed reader, an image converter — uses as-is, so the fallback is
    the finished conversation rather than a blank rectangle. A CSS version needs
    opacity:0 defaults to work at all, and degrades to an empty frame.

    (GitHub itself serves the SVG unmodified and runs either kind of animation;
    an earlier note here claimed it strips @keyframes, which was wrong.)
    """
    norm = lambda t: max(0.0, min(1.0, t / LOOP))
    points = [(0.0, 0)]
    if start > 0:
        points.append((norm(start), 0))
    points.append((norm(start + FADE), 1))
    if end >= LOOP:
        points.append((1.0, 1))
    else:
        points.extend([(norm(end - FADE), 1), (norm(end), 0), (1.0, 0)])

    # keyTimes must be non-decreasing and span exactly 0..1.
    times, values, last = [], [], -1.0
    for t, v in points:
        t = max(t, last + 1e-4) if t <= last else t
        last = t
        times.append(min(t, 1.0))
        values.append(v)
    times[-1] = 1.0
    return (
        '<animate attributeName="opacity" dur="%ss" repeatCount="indefinite" '
        'calcMode="linear" keyTimes="%s" values="%s"/>'
    ) % (
        LOOP,
        ";".join("%.4f" % t for t in times),
        ";".join(str(v) for v in values),
    )


def group(gid, start, end, body):
    base = 1 if end >= LOOP else 0
    node = '<g id="%s" opacity="%d">%s%s</g>' % (
        gid, base, smil(start, end), "".join(body)
    )
    return node, (gid, start, end)


# --------------------------------------------------------------------------
# Scenes: (id, appears_at, disappears_at, svg body)
# --------------------------------------------------------------------------

SCENES = []


def scene(gid, start, end, body):
    node, timing = group(gid, start, end, body)
    SCENES.append((node, timing))


# 1. The user asks for something, from the phone.
scene("ask", 0.4, LOOP, [
    bubble(556, SLOT_MSG1, 296, 46, "user"),
    text(836, SLOT_MSG1 + 29, "fix the failing tests", "t u", "end"),
])

# 2. Instant acknowledgement, then the same message edited in place.
TICKER = [
    (1.0, 2.5, ["⏳ Got it, working…"]),
    (2.5, 4.1, ["⏳ Working… · 1 step · 2s", "└ Bash: pytest tests/ -q"]),
    (4.1, 5.5, ["⏳ Working… · 4 steps · 21s", "└ Edit: src/conftest.py"]),
    (5.5, 6.7, ["⏳ Working… · 7 steps · 1m 12s", "└ Bash: pytest tests/ -q"]),
]
scene("tickbub", 1.0, 6.7, [bubble(28, SLOT_A, 470, 78, "bot")])
for i, (a, b, lines) in enumerate(TICKER):
    body = [text(52, SLOT_A + (46 if len(lines) == 1 else 32), lines[0], "t")]
    if len(lines) > 1:
        body.append(text(52, SLOT_A + 60, lines[1], "t mono dim"))
    scene("tick%d" % i, a, b, body)

# 3. The ticker is deleted; the finished answer takes its place.
scene("answer", 7.0, LOOP, [
    bubble(28, SLOT_A, 470, 104, "bot"),
    text(52, SLOT_A + 30, "🤖 demo · turn 3/40", "t dim small"),
    text(52, SLOT_A + 60, "Fixed — the fixture leaked a temp dir", "t"),
    text(52, SLOT_A + 84, "between runs. Suite is green.", "t"),
])

# 4. A tool call needs approval — answered from the phone.
scene("perm", 7.9, LOOP, [
    bubble(28, SLOT_PERM, 470, 108, "bot"),
    text(52, SLOT_PERM + 30, "🔐 Permission requested", "t"),
    text(52, SLOT_PERM + 58, "Bash", "t dim small"),
    text(52, SLOT_PERM + 82, "git push origin main", "t mono"),
])
scene("yes", 8.9, LOOP, [
    bubble(756, SLOT_YES, 96, 46, "user"),
    text(836, SLOT_YES + 29, "yes", "t u", "end"),
])
scene("done", 9.7, LOOP, [
    bubble(28, SLOT_DONE, 300, 52, "bot"),
    text(52, SLOT_DONE + 32, "✅ Pushed. 1 commit to main.", "t"),
])


def build():
    nodes = "".join(node for node, _ in SCENES)

    css = """
    .bg{fill:#ffffff}
    .hdr{fill:#f7f9fb}
    .line{stroke:#e6ebf0;stroke-width:1}
    .bub.bot{fill:#f1f3f5}
    .bub.user{fill:#3390ec}
    .t{fill:#0f1419;font-family:%(sans)s;font-size:17px}
    .t.u{fill:#ffffff}
    .t.dim{fill:#6b7c8c}
    .t.small{font-size:14px}
    .t.mono{font-family:%(mono)s;font-size:15px}
    .title{fill:#0f1419;font-family:%(sans)s;font-size:16px;font-weight:600}
    .sub{fill:#6b7c8c;font-family:%(sans)s;font-size:13px}
    .avatar{fill:#3390ec}
    .avatar-t{fill:#ffffff;font-family:%(sans)s;font-size:15px;font-weight:700}
    @media (prefers-color-scheme:dark){
      .bg{fill:#17212b}
      .hdr{fill:#1d2b3a}
      .line{stroke:#101a23}
      .bub.bot{fill:#182533}
      .bub.user{fill:#2b5278}
      .t{fill:#e9edf0}
      .t.dim{fill:#8fa3b5}
      .title{fill:#e9edf0}
      .sub{fill:#8fa3b5}
    }
    """ % {"sans": SANS, "mono": MONO}

    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="A Telegram chat: a request is sent, a single status message updates in place while tools run, it disappears, and the finished answer arrives — then a permission request is approved with yes.">
<style>{css}</style>
<rect class="bg" width="{w}" height="{h}" rx="18"/>
<path class="hdr" d="M0 18 A18 18 0 0 1 18 0 L{w2} 0 A18 18 0 0 1 {w} 18 L{w} 62 L0 62 Z"/>
<line class="line" x1="0" y1="62" x2="{w}" y2="62"/>
<circle class="avatar" cx="46" cy="31" r="17"/>
<text class="avatar-t" x="46" y="37" text-anchor="middle">af</text>
<text class="title" x="76" y="27">claude-afk</text>
<text class="sub" x="76" y="46">bot · your session, on your phone</text>
{nodes}
</svg>
""".format(w=W, h=H, w2=W - 18, css=css, nodes=nodes)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return svg


if __name__ == "__main__":
    out = build()
    print("wrote %s (%.1f KB, %d scenes, %.0fs loop)" % (
        OUT, len(out.encode()) / 1024.0, len(SCENES), LOOP))
