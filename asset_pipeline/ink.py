"""Deterministic hand-drawn ink primitives that emit SVG markup.

Everything is seeded (random.Random(seed)) so re-running the art generator
yields byte-identical SVG. The look target is the Open Peeps linework the
character already uses: confident black outline, slightly imperfect
straight lines, flat fills, and engraved hatching for shade.
"""
import math
import random

INK = "#13121a"


def _f(v):
    return f"{v:.1f}"


class Ink:
    def __init__(self, x0, y0, w, h, seed=0):
        self.x0, self.y0, self.w, self.h = x0, y0, w, h
        self.rng = random.Random(seed)
        self.defs = []
        self.body = []
        self._n = 0

    # ---------------------------------------------------------------- geometry
    def _densify(self, pts, closed, step):
        out = []
        n = len(pts)
        pairs = n if closed else n - 1
        for i in range(pairs):
            a, b = pts[i], pts[(i + 1) % n]
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            k = max(1, int(length / step))
            for j in range(k):
                t = j / k
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, j == 0))
        if not closed:
            out.append((pts[-1][0], pts[-1][1], True))
        return out

    def _wobble(self, pts, closed, step, amp):
        dense = self._densify(pts, closed, step)
        res = []
        walk = 0.0
        for i, (x, y, corner) in enumerate(dense):
            j = (i + 1) % len(dense)
            nx, ny = dense[j][0] - dense[i - 1][0], dense[j][1] - dense[i - 1][1]
            ln = math.hypot(nx, ny) or 1.0
            nx, ny = -ny / ln, nx / ln
            walk = walk * 0.55 + self.rng.uniform(-1, 1) * 0.9
            off = amp * walk * (0.5 if corner else 1.0)
            res.append((x + nx * off, y + ny * off))
        return res

    @staticmethod
    def _catmull(pts, closed):
        n = len(pts)

        def P(i):
            return pts[i % n] if closed else pts[max(0, min(n - 1, i))]

        d = f"M{_f(pts[0][0])},{_f(pts[0][1])}"
        for i in range(n if closed else n - 1):
            p0, p1, p2, p3 = P(i - 1), P(i), P(i + 1), P(i + 2)
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += f" C{_f(c1[0])},{_f(c1[1])} {_f(c2[0])},{_f(c2[1])} {_f(p2[0])},{_f(p2[1])}"
        return d + (" Z" if closed else "")

    def _d(self, pts, closed, wobble, step, smooth):
        if wobble > 0:
            pts = self._wobble(pts, closed, step, wobble)
        elif smooth:
            pass
        if smooth:
            return self._catmull(pts, closed)
        d = "M" + " L".join(f"{_f(x)},{_f(y)}" for x, y in pts)
        return d + (" Z" if closed else "")

    # ------------------------------------------------------------------ shapes
    def path(self, pts, fill="none", stroke=INK, sw=5, closed=False, wobble=1.3,
             step=34, smooth=False, opacity=1.0, extra=""):
        d = self._d(pts, closed, wobble, step, smooth)
        op = f' opacity="{opacity}"' if opacity != 1.0 else ""
        st = (f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
              if stroke and sw > 0 else ' stroke="none"')
        self.body.append(f'<path d="{d}" fill="{fill}"{st}{op} {extra}/>')

    def poly(self, pts, fill="#fff", sw=5, wobble=1.3, step=34, smooth=False, **kw):
        self.path(pts, fill=fill, sw=sw, closed=True, wobble=wobble, step=step, smooth=smooth, **kw)

    def line(self, a, b, sw=5, wobble=1.0, **kw):
        self.path([a, b], sw=sw, closed=False, wobble=wobble, **kw)

    def rect(self, x, y, w, h, fill="#fff", sw=5, wobble=1.3, **kw):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], fill=fill, sw=sw, wobble=wobble, **kw)

    def rrect(self, x, y, w, h, r, fill="#fff", sw=5, wobble=1.0, **kw):
        pts = []
        for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0),
                           (x + r, y + h - r, 90), (x + r, y + r, 180)):
            for k in range(7):
                a = math.radians(a0 + k * 15)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, fill=fill, sw=sw, wobble=wobble, step=60, **kw)

    def ellipse(self, cx, cy, rx, ry, fill="#fff", sw=5, wobble=1.2, rot=0, n=44, **kw):
        pts = []
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for k in range(n):
            a = 2 * math.pi * k / n
            ex, ey = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + ex * cr - ey * sr, cy + ex * sr + ey * cr))
        self.poly(pts, fill=fill, sw=sw, wobble=wobble, step=80, smooth=True, **kw)

    def raw(self, frag):
        self.body.append(frag)

    # ---------------------------------------------------------------- clipping
    def clip_poly(self, pts):
        self._n += 1
        cid = f"c{self._n}"
        d = "M" + " L".join(f"{_f(x)},{_f(y)}" for x, y in pts) + " Z"
        self.defs.append(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return cid

    def hatch(self, poly_pts, angle=45, spacing=14, sw=2.4, opacity=0.75, jitter=1.6,
              gradient=None, skip=0.04, cid=None):
        """Parallel hatch strokes clipped to `poly_pts`. `gradient=(s0,s1)`
        varies spacing linearly across the perpendicular axis so shade can
        fade in (dense -> sparse), the way engraved shading does."""
        xs = [p[0] for p in poly_pts]
        ys = [p[1] for p in poly_pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        R = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 20
        ang = math.radians(angle)
        dx, dy = math.cos(ang), math.sin(ang)
        px, py = -dy, dx
        cid = cid or self.clip_poly(poly_pts)
        d = []
        pos = -R
        while pos < R:
            t = (pos + R) / (2 * R)
            sp = spacing if gradient is None else gradient[0] + (gradient[1] - gradient[0]) * t
            pos += sp * self.rng.uniform(0.85, 1.15)
            if self.rng.random() < skip:
                continue
            ax, ay = cx + px * pos, cy + py * pos
            l0 = -R + self.rng.uniform(0, R * 0.25)
            l1 = R - self.rng.uniform(0, R * 0.25)
            pts = []
            for k in range(4):
                s = l0 + (l1 - l0) * k / 3
                j = self.rng.uniform(-jitter, jitter)
                pts.append((ax + dx * s + px * j, ay + dy * s + py * j))
            d.append("M" + " L".join(f"{_f(x)},{_f(y)}" for x, y in pts))
        self.body.append(
            f'<g clip-path="url(#{cid})"><path d="{" ".join(d)}" fill="none" stroke="{INK}" '
            f'stroke-width="{sw}" stroke-linecap="round" opacity="{opacity}"/></g>')

    def crosshatch(self, poly_pts, angle=45, spacing=14, **kw):
        cid = self.clip_poly(poly_pts)
        self.hatch(poly_pts, angle, spacing, cid=cid, **kw)
        self.hatch(poly_pts, angle + 75, spacing * 1.15, cid=cid, **kw)

    # ------------------------------------------------------------------ output
    def svg(self):
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="{self.x0} {self.y0} {self.w} {self.h}">'
                f'<defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')
