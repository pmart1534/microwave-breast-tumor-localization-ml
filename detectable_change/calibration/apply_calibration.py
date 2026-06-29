"""
apply_calibration.py  (v2)
==========================
Reads calibration.json and prints the resulting outlines in INCH
coordinates, ready to paste into brainstorm_variations.py.

Supports both the legacy 4-corner schema and the new flexible
"calib_points" schema (any N >= 3 grid intersections, each labelled with
its inch coordinate).

Bowl smoothing: pools every bowl click across all three photos, fits a
periodic cubic spline through them in polar coordinates around the
centroid, and samples 60 evenly-spaced points along the spline.  No
angle-binned medians -> no pointy corners.
"""
import json, os
import numpy as np
from scipy.interpolate import CubicSpline

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = json.load(open(os.path.join(HERE, "calibration.json")))

# Legacy 4-corner inch positions (used only if a photo has 'corners' instead
# of 'calib_points').
LEGACY_CORNERS_IN = np.array([(1, 1), (5, 1), (5, 5), (1, 5)], dtype=float)


def fit_affine(px, inch):
    """Solve for 2x3 affine M with  inch = M @ [px_x, px_y, 1]."""
    P = np.asarray(px, dtype=float)
    Q = np.asarray(inch, dtype=float)
    A = np.column_stack([P, np.ones(len(P))])
    Mx, *_ = np.linalg.lstsq(A, Q[:, 0], rcond=None)
    My, *_ = np.linalg.lstsq(A, Q[:, 1], rcond=None)
    return np.stack([Mx, My], axis=0)


def apply(M, pts):
    P = np.asarray(pts, dtype=float)
    A = np.column_stack([P, np.ones(len(P))])
    return (M @ A.T).T


def get_affine(data):
    if "calib_points" in data and data["calib_points"]:
        cp = data["calib_points"]
        px   = [c["px"]   for c in cp]
        inch = [c["inch"] for c in cp]
        return fit_affine(px, inch), inch, px
    if "corners" in data:
        return fit_affine(data["corners"], LEGACY_CORNERS_IN), \
               LEGACY_CORNERS_IN.tolist(), data["corners"]
    raise KeyError("no calib_points or corners in this photo")


def print_polygon(name, pts):
    print(f"\n{name} = [")
    pts = list(pts)
    for i in range(0, len(pts), 4):
        chunk = pts[i:i + 4]
        print("    " + ", ".join(f"({x:.2f}, {y:.2f})" for x, y in chunk) + ",")
    print("]")


def order_by_angle(pts):
    """Sort points counter-clockwise around their centroid."""
    pts = np.asarray(pts)
    c = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    return pts[np.argsort(ang)]


def spline_smooth_closed(pts, n_out=60):
    """Fit a periodic cubic spline through pts (closed polygon) in polar
    coords around centroid, sample n_out evenly spaced points.  Robust
    to non-circular shapes because we spline radius vs angle, then map
    back."""
    pts = np.asarray(pts, dtype=float)
    c = pts.mean(axis=0)
    dx = pts[:, 0] - c[0]; dy = pts[:, 1] - c[1]
    ang = np.arctan2(dy, dx)
    rad = np.hypot(dx, dy)
    order = np.argsort(ang)
    ang = ang[order]; rad = rad[order]
    # de-duplicate angles (rare but spline needs strictly increasing)
    keep = np.concatenate([[True], np.diff(ang) > 1e-6])
    ang = ang[keep]; rad = rad[keep]
    # extend periodically for the spline
    ang_ext = np.concatenate([ang - 2 * np.pi, ang, ang + 2 * np.pi])
    rad_ext = np.concatenate([rad, rad, rad])
    cs = CubicSpline(ang_ext, rad_ext)
    out_ang = np.linspace(-np.pi, np.pi, n_out, endpoint=False)
    out_rad = cs(out_ang)
    out_x = c[0] + out_rad * np.cos(out_ang)
    out_y = c[1] + out_rad * np.sin(out_ang)
    return list(zip(out_x, out_y))


bowl_pts_all = []
for kind, data in CAL.items():
    print(f"\n# === {kind} ===")
    M, inch_targets, px_clicks = get_affine(data)
    inch_fit = apply(M, px_clicks)
    err = np.linalg.norm(np.asarray(inch_fit) - np.asarray(inch_targets), axis=1)
    print(f"# {len(px_clicks)} calib points,  max fit error {err.max():.3f} in,  "
          f"mean {err.mean():.3f} in")

    if "bowl" in data:
        bowl_in = apply(M, data["bowl"])
        bowl_pts_all.append(bowl_in)

    if "glandular" in data:
        g = order_by_angle(apply(M, data["glandular"]))
        smoothed = spline_smooth_closed(g, n_out=40)
        print_polygon(f"{kind}_OUTLINE", smoothed)


print(f"\n# === BOWL: pooled from {sum(len(b) for b in bowl_pts_all)} clicks ===")
pooled = np.concatenate(bowl_pts_all, axis=0)

# Fit an axis-aligned ellipse (cx, cy, rx, ry) by least squares to the
# clicked perimeter:
#   ((x-cx)/rx)^2 + ((y-cy)/ry)^2 = 1
# Linearise as  A x^2 + B x + C y^2 + D y = 1   ->  4 unknowns, then
# recover cx = -B/(2A), cy = -D/(2C), rx = sqrt(1/A + B^2/(4A^2)), etc.
x = pooled[:, 0]; y = pooled[:, 1]
M = np.column_stack([x ** 2, x, y ** 2, y])
coef, *_ = np.linalg.lstsq(M, np.ones(len(x)), rcond=None)
A, B, C, D = coef
cx = -B / (2 * A); cy = -D / (2 * C)
rx2 = (1 + B ** 2 / (4 * A) + D ** 2 / (4 * C)) / A
ry2 = (1 + B ** 2 / (4 * A) + D ** 2 / (4 * C)) / C
rx = float(np.sqrt(rx2)); ry = float(np.sqrt(ry2))
# fit residual (should be small)
fit = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
print(f"# fit residual: mean |r^2 - 1| = {np.mean(np.abs(fit - 1)):.4f}")

print(f"BOWL_ELLIPSE_CENTER = ({cx:.3f}, {cy:.3f})")
print(f"BOWL_ELLIPSE_RX     = {rx:.3f}")
print(f"BOWL_ELLIPSE_RY     = {ry:.3f}")
