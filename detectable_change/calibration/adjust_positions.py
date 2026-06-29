"""
adjust_positions.py
===================
Drag-and-drop tool to nudge the recorded measurement positions to their
true physical locations on each phantom photo.  Useful when inserting
the glandular shifted the marble paths slightly off the default cell
sub-position grid.

Inputs:
  calibration.json   (pixel <-> inch maps from click_calibration.py)
  results/detectable_diff_*.npz  (default X,Y per label per setup)

Workflow per photo (Empty / F4 / F5):
  1. The photo opens with one small red marker per recorded position,
     placed at its DEFAULT physical X,Y (no shrink-to-centre applied).
  2. Drag any marker that's in the wrong place onto its true cell
     sub-position.  Markers you don't touch keep their default coord.
  3. Press 'n' to save and move to the next photo.

Output:
  position_adjustments.json   keyed by setup name -> {label: [X, Y]}.
  Only labels you actually moved are written (so you can rerun on a
  subset later without losing prior work).

Keys (canvas focus):
  n  = next photo (saves)
  u  = revert last drag
  r  = reset the marker under the cursor to its default position
  z  = zoom toggle (2x) to make tight positions easier to drag
"""
import json, os
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(HERE, "phantom_photos")
CAL_JSON = os.path.join(HERE, "calibration.json")
# Output: position adjustments json lives in the parent (detectable_change) folder
# so paper_figure.py can read it.
ADJ_JSON = os.path.abspath(os.path.join(HERE, os.pardir, "position_adjustments.json"))
# Input: detectable-change npz files also live in the parent folder.
RES_DIR  = os.path.abspath(os.path.join(HERE, os.pardir, "results"))

PHOTOS = [
    ("A2_Empty", "A2_Annotated.jpg",   "empty"),
    ("A2_F4",    "A2F4_Annotated.jpg", "F4"),
    ("A2_F5",    "A2F5_Annotated.jpg", "F5"),
]

# --- inch <-> pixel helpers -------------------------------------------
CAL = json.load(open(CAL_JSON))


def fit_affine(px, inch):
    P = np.asarray(px, dtype=float); Q = np.asarray(inch, dtype=float)
    A = np.column_stack([P, np.ones(len(P))])
    Mx, *_ = np.linalg.lstsq(A, Q[:, 0], rcond=None)
    My, *_ = np.linalg.lstsq(A, Q[:, 1], rcond=None)
    return np.stack([Mx, My], axis=0)   # 2x3


def get_pixel_to_inch(cal_key):
    data = CAL[cal_key]
    cp = data["calib_points"]
    px   = [c["px"]   for c in cp]
    inch = [c["inch"] for c in cp]
    return fit_affine(px, inch)


def invert_affine(M):
    """M is 2x3 px->inch.  Return 2x3 inch->px."""
    A = M[:, :2]; t = M[:, 2]
    Ainv = np.linalg.inv(A)
    tinv = -Ainv @ t
    return np.column_stack([Ainv, tinv])


def apply_affine(M, pts):
    P = np.asarray(pts, dtype=float)
    A = np.column_stack([P, np.ones(len(P))])
    return (M @ A.T).T


# --- load existing adjustments ---------------------------------------
if os.path.exists(ADJ_JSON):
    adjustments = json.load(open(ADJ_JSON))
else:
    adjustments = {}


class AdjustApp:
    def __init__(self, master):
        self.master = master
        master.title("Position adjuster")

        self.canvas = tk.Canvas(master, width=900, height=900, bg="black",
                                highlightthickness=0)
        self.canvas.pack(side="left")
        right = tk.Frame(master)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.info = tk.Label(right, text="", wraplength=320,
                             font=("Arial", 11), justify="left", anchor="nw")
        self.info.pack(fill="both", expand=True)

        master.bind("n", self.next_photo)
        master.bind("u", self.undo)
        master.bind("r", self.reset_under_cursor)
        master.bind("z", self.toggle_zoom)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.focus_set()

        self.photo_idx = 0
        self.scale = 1.0
        self.zoom = 1.0
        self.dragging = None    # marker index
        self.markers = []       # list of dict
        self.history = []       # for undo
        self.cursor_x = self.cursor_y = 0
        self.load_photo()

    # ---------------------------------------------------
    def load_photo(self):
        if self.photo_idx >= len(PHOTOS):
            self.finish(); return
        setup, fname, cal_key = PHOTOS[self.photo_idx]
        path = os.path.join(PHOTOS_DIR, fname)
        img = Image.open(path)
        self.cur_img = img
        self.cal_key = cal_key
        self.setup = setup
        W, H = img.size
        self.full_w = W; self.full_h = H
        s = min(900 / W, 900 / H)
        self.scale = s * self.zoom
        self.disp_w = int(W * self.scale); self.disp_h = int(H * self.scale)
        disp = img.resize((self.disp_w, self.disp_h))
        self.img_tk = ImageTk.PhotoImage(disp)
        self.canvas.config(width=min(self.disp_w, 1200),
                           height=min(self.disp_h, 900),
                           scrollregion=(0, 0, self.disp_w, self.disp_h))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.img_tk, anchor="nw")

        # affines
        self.M_px2in = get_pixel_to_inch(cal_key)
        self.M_in2px = invert_affine(self.M_px2in)

        # load default measurement positions for this setup
        npz = np.load(os.path.join(RES_DIR, f"detectable_diff_{setup}.npz"),
                      allow_pickle=True)
        rows = npz["rows_S11"].tolist()
        adj_for_setup = adjustments.get(setup, {})
        self.markers = []
        for row in rows:
            label, x_in, y_in = row[0], row[1], row[2]
            default = (float(x_in), float(y_in))
            current = tuple(adj_for_setup.get(label, default))
            # convert inch -> display pixel
            px = apply_affine(self.M_in2px, [current])[0]
            dx, dy = px[0] * self.scale, px[1] * self.scale
            self.markers.append({
                "label": label, "default_in": default, "inch": current,
                "disp": [dx, dy], "moved": label in adj_for_setup,
            })
        self.history = []
        self.draw_markers()
        self.update_info()

    # ---------------------------------------------------
    def draw_markers(self):
        self.canvas.delete("marker")
        r = 4
        for m in self.markers:
            dx, dy = m["disp"]
            color = "orange" if m["moved"] else "red"
            self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r,
                                    outline=color, fill="",
                                    width=1.5, tags=("marker",))

    def update_info(self):
        setup, _, _ = PHOTOS[self.photo_idx]
        n_moved = sum(1 for m in self.markers if m["moved"])
        self.info.config(text=
            f"Photo: {setup}\n\n"
            f"{len(self.markers)} measurement positions plotted.\n"
            f"Red = at default coord.  Orange = moved.\n"
            f"({n_moved} moved so far)\n\n"
            "DRAG any marker to its true position.\n"
            "Untouched markers keep their default coord.\n\n"
            "Keys:\n"
            "  n = save & next photo\n"
            "  u = undo last drag\n"
            "  r = reset marker under cursor to default\n"
            "  z = toggle 2x zoom")

    # ---------------------------------------------------
    def closest_marker(self, x, y, max_d=15):
        best = None; best_d = max_d * max_d
        for i, m in enumerate(self.markers):
            dx, dy = m["disp"]
            d = (dx - x) ** 2 + (dy - y) ** 2
            if d < best_d:
                best_d = d; best = i
        return best

    def on_press(self, ev):
        self.dragging = self.closest_marker(ev.x, ev.y)
        if self.dragging is not None:
            m = self.markers[self.dragging]
            self.history.append((self.dragging, list(m["disp"]),
                                 tuple(m["inch"]), m["moved"]))

    def on_drag(self, ev):
        if self.dragging is None: return
        m = self.markers[self.dragging]
        m["disp"] = [ev.x, ev.y]
        # convert back to inch
        px_full = ev.x / self.scale
        py_full = ev.y / self.scale
        inch = apply_affine(self.M_px2in, [[px_full, py_full]])[0]
        m["inch"] = (float(inch[0]), float(inch[1]))
        m["moved"] = True
        self.draw_markers()

    def on_release(self, ev):
        self.dragging = None
        self.update_info()

    def on_hover(self, ev):
        self.cursor_x = ev.x; self.cursor_y = ev.y
        idx = self.closest_marker(ev.x, ev.y, max_d=12)
        if idx is not None:
            m = self.markers[idx]
            txt = (f"{m['label']}\n"
                   f"default ({m['default_in'][0]:.2f}, {m['default_in'][1]:.2f})\n"
                   f"current ({m['inch'][0]:.2f}, {m['inch'][1]:.2f})")
            self.canvas.delete("hover")
            self.canvas.create_rectangle(ev.x + 12, ev.y + 8,
                                          ev.x + 180, ev.y + 60,
                                          fill="white", outline="black",
                                          tags=("hover",))
            self.canvas.create_text(ev.x + 16, ev.y + 12, anchor="nw",
                                    text=txt, fill="black",
                                    font=("Arial", 9),
                                    tags=("hover",))
        else:
            self.canvas.delete("hover")

    # ---------------------------------------------------
    def undo(self, ev):
        if not self.history: return
        idx, disp, inch, moved = self.history.pop()
        m = self.markers[idx]
        m["disp"] = list(disp); m["inch"] = tuple(inch); m["moved"] = moved
        self.canvas.delete("hover")
        self.draw_markers()
        self.update_info()

    def reset_under_cursor(self, ev):
        idx = self.closest_marker(self.cursor_x, self.cursor_y, max_d=20)
        if idx is None: return
        m = self.markers[idx]
        self.history.append((idx, list(m["disp"]),
                             tuple(m["inch"]), m["moved"]))
        m["inch"] = m["default_in"]
        px = apply_affine(self.M_in2px, [m["default_in"]])[0]
        m["disp"] = [px[0] * self.scale, px[1] * self.scale]
        m["moved"] = False
        self.draw_markers()
        self.update_info()

    def toggle_zoom(self, ev):
        self.zoom = 2.0 if self.zoom == 1.0 else 1.0
        self.load_photo()

    # ---------------------------------------------------
    def next_photo(self, ev):
        setup, _, _ = PHOTOS[self.photo_idx]
        bucket = adjustments.setdefault(setup, {})
        for m in self.markers:
            if m["moved"]:
                bucket[m["label"]] = [round(m["inch"][0], 3),
                                       round(m["inch"][1], 3)]
        with open(ADJ_JSON, "w") as f:
            json.dump(adjustments, f, indent=2)
        self.photo_idx += 1
        self.load_photo()

    def finish(self):
        with open(ADJ_JSON, "w") as f:
            json.dump(adjustments, f, indent=2)
        print(f"Saved {ADJ_JSON}")
        self.master.destroy()


root = tk.Tk()
app = AdjustApp(root)
root.mainloop()
