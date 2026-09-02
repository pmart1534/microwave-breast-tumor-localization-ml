"""
adjust_antennas_A3.py
=====================
Drag the 4 numbered antenna boxes onto their true physical positions on the
A3 phantom photo. The antennas are in the SAME spot for every setup, so this
saves ONE shared layout used by all three panels of paper_figure_A3.py.

Uses the px<->inch calibration you already traced (calibration.json, "empty"
key) so the boxes are placed in the same inch coordinate frame as the dots.

Output:
  ../antenna_positions_A3.json   ->  {"1": [x_in, y_in], ...}
  (paper_figure_A3.py reads this automatically; falls back to built-in
   Medium-Separated defaults if the file is absent.)

Keys (canvas focus):
  s = save        u = undo last drag       r = reset all to defaults
  z = toggle 2x zoom
Close the window to save & exit.
"""
import json, os
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(HERE, "phantom_photos")
CAL_JSON = os.path.join(HERE, "calibration.json")
OUT_JSON = os.path.abspath(os.path.join(HERE, os.pardir, "antenna_positions_A3.json"))
PHOTO = "A3.jpg"
CAL_KEY = "empty"

# Built-in defaults: Sam "Medium Separated" 4-port (ports 1,2 left / 3,4 right).
DEFAULTS = {1: [1.554, 4.237], 2: [1.539, 1.219],
            3: [4.423, 1.428], 4: [4.543, 4.147]}

CAL = json.load(open(CAL_JSON))


def fit_affine(px, inch):
    P = np.asarray(px, float); Q = np.asarray(inch, float)
    A = np.column_stack([P, np.ones(len(P))])
    Mx, *_ = np.linalg.lstsq(A, Q[:, 0], rcond=None)
    My, *_ = np.linalg.lstsq(A, Q[:, 1], rcond=None)
    return np.stack([Mx, My], axis=0)


def invert_affine(M):
    A = M[:, :2]; t = M[:, 2]
    Ainv = np.linalg.inv(A); tinv = -Ainv @ t
    return np.column_stack([Ainv, tinv])


def apply_affine(M, pts):
    P = np.asarray(pts, float)
    A = np.column_stack([P, np.ones(len(P))])
    return (M @ A.T).T


def get_px2in(key):
    cp = CAL[key]["calib_points"]
    return fit_affine([c["px"] for c in cp], [c["inch"] for c in cp])


class AntennaEditor:
    def __init__(self, master):
        self.master = master
        master.title("A3 antenna position editor")
        self.canvas = tk.Canvas(master, width=900, height=900, bg="black",
                                highlightthickness=0)
        self.canvas.pack(side="left")
        self.info = tk.Label(master, text="", width=40, justify="left",
                             anchor="nw", font=("Arial", 11))
        self.info.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        master.bind("s", self.save)
        master.bind("u", self.undo)
        master.bind("r", self.reset)
        master.bind("z", self.toggle_zoom)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.focus_set()
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.zoom = 1.0
        self.dragging = None
        self.history = []
        self.M_px2in = get_px2in(CAL_KEY)
        self.M_in2px = invert_affine(self.M_px2in)

        start = DEFAULTS.copy()
        if os.path.exists(OUT_JSON):
            saved = json.load(open(OUT_JSON))
            for p, xy in saved.items():
                start[int(p)] = list(xy)
        self.pos_in = {p: list(v) for p, v in start.items()}
        self.load_photo()

    def load_photo(self):
        img = Image.open(os.path.join(PHOTOS_DIR, PHOTO))
        W, H = img.size
        self.scale = min(900 / W, 900 / H) * self.zoom
        dw, dh = int(W * self.scale), int(H * self.scale)
        self.img_tk = ImageTk.PhotoImage(img.resize((dw, dh)))
        self.canvas.config(width=min(dw, 1200), height=min(dh, 900),
                           scrollregion=(0, 0, dw, dh))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.img_tk, anchor="nw")
        self.draw()
        self.update_info()

    def disp_of(self, port):
        px = apply_affine(self.M_in2px, [self.pos_in[port]])[0]
        return px[0] * self.scale, px[1] * self.scale

    def draw(self):
        self.canvas.delete("ant")
        w, h = 16, 30
        for p in sorted(self.pos_in):
            dx, dy = self.disp_of(p)
            self.canvas.create_rectangle(dx - w/2, dy - h/2, dx + w/2, dy + h/2,
                                         fill="#262626", outline="yellow",
                                         width=2, tags=("ant",))
            self.canvas.create_text(dx, dy, text=str(p), fill="white",
                                    font=("Arial", 11, "bold"), tags=("ant",))

    def update_info(self):
        lines = "\n".join(f"  antenna {p}: ({v[0]:.2f}, {v[1]:.2f}) in"
                          for p, v in sorted(self.pos_in.items()))
        self.info.config(text="Drag the numbered antenna boxes onto their\n"
                              "true physical positions on the photo.\n"
                              "(Same layout is used for all setups.)\n\n"
                              + lines +
                              "\n\nKeys:\n  s = save\n  u = undo\n"
                              "  r = reset to defaults\n  z = toggle 2x zoom\n"
                              "  close window = save & exit")

    def closest(self, x, y, max_d=18):
        best, bd = None, max_d * max_d
        for p in self.pos_in:
            dx, dy = self.disp_of(p)
            d = (dx - x) ** 2 + (dy - y) ** 2
            if d < bd:
                bd, best = d, p
        return best

    def on_press(self, ev):
        self.dragging = self.closest(ev.x, ev.y)
        if self.dragging is not None:
            self.history.append((self.dragging, list(self.pos_in[self.dragging])))

    def on_drag(self, ev):
        if self.dragging is None:
            return
        inch = apply_affine(self.M_px2in, [[ev.x / self.scale, ev.y / self.scale]])[0]
        self.pos_in[self.dragging] = [float(inch[0]), float(inch[1])]
        self.draw(); self.update_info()

    def on_release(self, _ev):
        self.dragging = None

    def undo(self, _ev):
        if self.history:
            p, xy = self.history.pop()
            self.pos_in[p] = xy
            self.draw(); self.update_info()

    def reset(self, _ev):
        self.history.append(("__all__", {p: list(v) for p, v in self.pos_in.items()}))
        self.pos_in = {p: list(v) for p, v in DEFAULTS.items()}
        self.draw(); self.update_info()

    def toggle_zoom(self, _ev):
        self.zoom = 2.0 if self.zoom == 1.0 else 1.0
        self.load_photo()

    def save(self, _ev=None):
        out = {str(p): [round(v[0], 3), round(v[1], 3)]
               for p, v in sorted(self.pos_in.items())}
        with open(OUT_JSON, "w") as f:
            json.dump(out, f, indent=2)
        self.info.config(text=f"SAVED {OUT_JSON}\n\n" + self.info.cget("text"))
        print(f"Saved {OUT_JSON}")

    def on_close(self):
        self.save()
        self.master.destroy()


root = tk.Tk()
app = AntennaEditor(root)
root.mainloop()
