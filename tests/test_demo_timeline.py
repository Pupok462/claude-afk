#!/usr/bin/env python3
"""Check that assets/demo.svg tells the story it claims to tell.

Eyeballing an animation catches the obvious break and misses everything else —
notably that two ticker states must never be on screen at once, since they
occupy the same bubble. This evaluates the SMIL opacity tracks directly:

    python3 tests/test_demo_timeline.py
"""

import os
import sys
import xml.etree.ElementTree as ET

SVG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "demo.svg"
)
NS = "{http://www.w3.org/2000/svg}"

TICKERS = ["tick0", "tick1", "tick2", "tick3"]
FINAL = ["ask", "answer", "perm", "yes", "done"]

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition)))
    suffix = (" — " + detail) if detail and not condition else ""
    print("%s %s%s" % ("PASS" if condition else "FAIL", name, suffix))


def load():
    """Return {id: (static_opacity, duration, [(keyTime, value)])}."""
    root = ET.parse(SVG).getroot()
    scenes = {}
    for g in root.iter(NS + "g"):
        gid = g.get("id")
        if not gid:
            continue
        anim = g.find(NS + "animate")
        if anim is None:
            scenes[gid] = (float(g.get("opacity", 1)), None, [])
            continue
        times = [float(x) for x in anim.get("keyTimes").split(";")]
        values = [float(x) for x in anim.get("values").split(";")]
        dur = float(anim.get("dur").rstrip("s"))
        scenes[gid] = (float(g.get("opacity", 1)), dur, list(zip(times, values)))
    return scenes


def opacity_at(track, dur, t):
    """Linear interpolation of a SMIL opacity track at time t."""
    frac = (t % dur) / dur
    for i in range(len(track) - 1):
        (t0, v0), (t1, v1) = track[i], track[i + 1]
        if t0 <= frac <= t1:
            if t1 == t0:
                return v1
            return v0 + (v1 - v0) * (frac - t0) / (t1 - t0)
    return track[-1][1]


def visible_at(scenes, t, threshold=0.5):
    out = set()
    for gid, (_, dur, track) in scenes.items():
        if dur and opacity_at(track, dur, t) > threshold:
            out.add(gid)
    return out


def main():
    if not os.path.exists(SVG):
        print("FAIL: %s missing — run python3 assets/build_demo.py" % SVG)
        return 1

    scenes = load()
    check("every scene has an animation track",
          all(dur for _, dur, _ in scenes.values()), str(sorted(scenes)))

    durations = {dur for _, dur, _ in scenes.values()}
    check("all scenes share one loop duration", len(durations) == 1, str(durations))
    loop = durations.pop()

    for gid, (_, _, track) in scenes.items():
        times = [t for t, _ in track]
        check("%s: keyTimes span 0..1, non-decreasing" % gid,
              times == sorted(times) and times[0] == 0.0 and times[-1] == 1.0,
              str(times))

    # The ticker states share one bubble — two on screen at once would overlap.
    overlaps = []
    step = loop / 400.0
    t = 0.0
    while t < loop:
        lit = [g for g in TICKERS if g in visible_at(scenes, t, threshold=0.15)]
        if len(lit) > 1:
            overlaps.append((round(t, 2), lit))
        t += step
    check("ticker states never overlap", not overlaps, str(overlaps[:3]))

    # The ticker is deleted before the answer is sent; they share a slot too.
    clashes = []
    t = 0.0
    while t < loop:
        vis = visible_at(scenes, t, threshold=0.15)
        if "answer" in vis and (set(TICKERS) | {"tickbub"}) & vis:
            clashes.append(round(t, 2))
        t += step
    check("answer never overlaps the ticker", not clashes, str(clashes[:3]))

    # Story beats.
    mid_ticker = visible_at(scenes, 3.3)
    check("mid-run shows a ticker state and no answer",
          bool(set(TICKERS) & mid_ticker) and "answer" not in mid_ticker,
          str(sorted(mid_ticker)))

    late = visible_at(scenes, loop - 0.5)
    check("the loop ends on the finished conversation",
          set(FINAL) <= late and not (set(TICKERS) & late), str(sorted(late)))

    # Graceful degradation: a renderer that ignores SMIL uses the attribute.
    static = {gid for gid, (op, _, _) in scenes.items() if op == 1}
    check("static fallback shows exactly the finished conversation",
          static == set(FINAL), str(sorted(static)))

    failed = [n for n, ok in results if not ok]
    print("\n%d/%d passed" % (len(results) - len(failed), len(results)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
