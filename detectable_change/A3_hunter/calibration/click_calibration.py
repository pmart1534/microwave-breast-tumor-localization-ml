"""
click_calibration.py  (v3)
==========================
Calibration stage is now DRAG-AND-DROP:
  9 markers preplaced at the inner-4x4 grid intersections
  (1,1), (5,1), (5,5), (1,5)  +  main diagonal (2,2),(3,3),(4,4)
                              +  anti-diagonal (2,4),(4,2).
  Drag each marker to the corresponding yellow intersection in the
  photo.  Press 'n' to lock them in.

Bowl + glandular stages are unchanged: click points around the
outline, press 'n' when done.

Keys (canvas focus):
  n  = next stage
  u  = undo last click  (does nothing during drag stage)
"""
import json, os
import tkinter as tk
from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(HERE, "phantom_photos")
OUT_JSON = os.path.join(HERE, "calibration.json")

# Per-photo flags: (trace_bowl?, trace_glandular?)
PHOTOS = [
    ("empty", "A3.jpg",   True,  False),   # bowl ONLY here (same bowl for all)
    ("F4",    "A3F4.jpg", False, True),    # glandular insert outline
    ("F5",    "A3F5.jpg", False, True),    # glandular insert outline
]

# Inch positions of the 9 preplaced markers.
CALIB_INCHES = [
    (1, 1), (5, 1), (5, 5), (1, 5),   # corners
    (2, 2), (3, 3), (4, 4),           # main diagonal
    (2, 4), (4, 2),                   # anti-diagonal
]

STAGE_CALIB = ("calib_points",
               "DRAG each green marker onto the yellow grid intersection "
               "labelled with its inch coords.  Press 'n' when all 9 are placed.")
STAGE_BOWL  = ("bowl",
               "Click points around the BOWL outline (as many as you want). "
               "Press 'n' when done.")
STAGE_GLAND = ("glandular",
               "Click points around the GLANDULAR outline.  Press 'n' when done.")

results = {}


class ClickApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Phantom calibration clicker (v3)")

        self.canvas = tk.Canvas(master, width=900, height=900, bg="black",
                                highlightthickness=0)
        self.canvas.pack(side="left")

        right = tk.Frame(master)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.info = tk.Label(right, text="", wraplength=320,
                             font=("Arial", 11), justify="left", anchor="nw")
        self.info.pack(fill="both", expand=True)

        master.bind("n", self.next_stage)
        master.bind("u", self.undo)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.focus_set()

        self.photo_idx = 0
        self.stage_idx = 0
        self.clicks = []      # for bowl/glandular stages
        self.markers = []     # for calib stage:  list of dict
                              # {inch, px, oval_id, text_id}
        self.dragging = None  # index of marker being dragged
        self.scale = 1.0
        self.img_tk = None
        self.load_photo()

    # ---------------------------------------------------
    def load_photo(self):
        if self.photo_idx >= len(PHOTOS):
            self.finish(); return
        kind, fname, _, _ = PHOTOS[self.photo_idx]
        path = os.path.join(PHOTOS_DIR, fname)
        self.cur_img = Image.open(path)
        W, H = self.cur_img.size
        s = min(900 / W, 900 / H)
        self.scale = s
        self.disp_w = int(W * s); self.disp_h = int(H * s)
        disp = self.cur_img.resize((self.disp_w, self.disp_h))
        self.img_tk = ImageTk.PhotoImage(disp)
        self.canvas.config(width=self.disp_w, height=self.disp_h)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.img_tk, anchor="nw")
        kind, _, has_b, has_g = PHOTOS[self.photo_idx]
        self.stages = [STAGE_CALIB]
        if has_b: self.stages.append(STAGE_BOWL)
        if has_g: self.stages.append(STAGE_GLAND)
        self.stage_idx = 0
        self.clicks = []
        self.markers = []
        self.dragging = None
        results.setdefault(kind, {})
        self.start_stage()

    # ---------------------------------------------------
    def start_stage(self):
        stage = self.current_stage()
        # clear stage-specific drawings
        self.canvas.delete("stage")
        if stage == "calib_points":
            self.place_initial_markers()
        self.update_info()

    def current_stage(self):
        return self.stages[self.stage_idx][0]

    def update_info(self):
        kind, _, _, _ = PHOTOS[self.photo_idx]
        stage, msg = self.stages[self.stage_idx]
        if stage == "calib_points":
            progress = f"({len(self.markers)} markers placed)"
        else:
            progress = f"({len(self.clicks)} clicks)"
        self.info.config(text=f"Photo: {kind}\n\n"
                              f"Stage: {stage}\n\n{msg}\n\n{progress}\n\n"
                              "Keys:  n = next   u = undo last click")

    # ---------------------------------------------------
    def place_initial_markers(self):
        """Preplace the 9 calibration markers at a sensible first-guess
        position: assume inches (1,1)..(5,5) maps to roughly the central
        70% of the image bounds."""
        pad_frac = 0.15  # 15% padding on each side
        w = self.disp_w; h = self.disp_h
        def inch_to_display(ix, iy):
            # map inch (1..5) to display pixel within [pad*w, (1-pad)*w]
            fx = (ix - 1) / 4.0  # 0..1
            fy = (iy - 1) / 4.0
            dx = pad_frac * w + fx * (1 - 2 * pad_frac) * w
            dy = pad_frac * h + fy * (1 - 2 * pad_frac) * h
            return dx, dy
        for ix, iy in CALIB_INCHES:
            dx, dy = inch_to_display(ix, iy)
            self.add_marker(ix, iy, dx, dy)

    def add_marker(self, ix, iy, dx, dy):
        r = 9
        oval = self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r,
                                       outline="lime", fill="",
                                       width=2, tags=("stage", "marker"))
        # cross-hair so the exact centre is visible
        ch = 6
        self.canvas.create_line(dx - ch, dy, dx + ch, dy,
                                fill="lime", width=1, tags=("stage", "marker"))
        self.canvas.create_line(dx, dy - ch, dx, dy + ch,
                                fill="lime", width=1, tags=("stage", "marker"))
        text = self.canvas.create_text(dx + 14, dy - 10,
                                       text=f"({ix},{iy})",
                                       fill="lime", anchor="w",
                                       font=("Arial", 10, "bold"),
                                       tags=("stage", "marker"))
        self.markers.append({"inch": (ix, iy), "disp": [dx, dy],
                             "oval": oval, "text": text})

    def redraw_marker(self, m):
        dx, dy = m["disp"]; r = 9; ch = 6
        # delete and recreate (simpler than moving multiple items)
        self.canvas.delete(m["oval"])
        self.canvas.delete(m["text"])
        # also delete any leftover cross-hair items by tag refresh
        # (we'll just leave them; redrawing the whole stage on undo is fine)
        m["oval"] = self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r,
                                            outline="lime", fill="", width=2,
                                            tags=("stage", "marker"))
        self.canvas.create_line(dx - ch, dy, dx + ch, dy,
                                fill="lime", width=1, tags=("stage", "marker"))
        self.canvas.create_line(dx, dy - ch, dx, dy + ch,
                                fill="lime", width=1, tags=("stage", "marker"))
        m["text"] = self.canvas.create_text(dx + 14, dy - 10,
                                            text=f"({m['inch'][0]},{m['inch'][1]})",
                                            fill="lime", anchor="w",
                                            font=("Arial", 10, "bold"),
                                            tags=("stage", "marker"))

    # ---------------------------------------------------
    def on_press(self, ev):
        if self.current_stage() == "calib_points":
            # pick the closest marker if within grab radius
            best_i = None; best_d = 1e9
            for i, m in enumerate(self.markers):
                dx, dy = m["disp"]
                d = (dx - ev.x) ** 2 + (dy - ev.y) ** 2
                if d < best_d:
                    best_d = d; best_i = i
            if best_d <= 30 ** 2:
                self.dragging = best_i
            else:
                self.dragging = None
        else:
            # click stage - record the point
            px = ev.x / self.scale; py = ev.y / self.scale
            self.clicks.append([round(px, 1), round(py, 1)])
            r = 5
            self.canvas.create_oval(ev.x - r, ev.y - r, ev.x + r, ev.y + r,
                                    outline="red", width=2, tags=("stage",))
            self.canvas.create_text(ev.x + 10, ev.y - 10,
                                    text=str(len(self.clicks)),
                                    fill="red", font=("Arial", 10, "bold"),
                                    tags=("stage",))
            self.update_info()

    def on_drag(self, ev):
        if self.current_stage() != "calib_points" or self.dragging is None:
            return
        m = self.markers[self.dragging]
        m["disp"] = [ev.x, ev.y]
        # cheap: redraw the whole stage marker layer
        self.canvas.delete("marker")
        for mm in self.markers:
            self.redraw_marker(mm)

    def on_release(self, ev):
        self.dragging = None

    # ---------------------------------------------------
    def undo(self, ev):
        if self.current_stage() == "calib_points":
            return  # nothing to undo while dragging
        if not self.clicks:
            return
        self.clicks.pop()
        # redraw click stage from scratch
        self.canvas.delete("stage")
        for i, (px, py) in enumerate(self.clicks, 1):
            x = px * self.scale; y = py * self.scale; r = 5
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    outline="red", width=2, tags=("stage",))
            self.canvas.create_text(x + 10, y - 10, text=str(i),
                                    fill="red", font=("Arial", 10, "bold"),
                                    tags=("stage",))
        self.update_info()

    # ---------------------------------------------------
    def next_stage(self, ev):
        kind, _, _, _ = PHOTOS[self.photo_idx]
        stage = self.current_stage()
        if stage == "calib_points":
            # convert disp -> original pixel and save
            cps = []
            for m in self.markers:
                dx, dy = m["disp"]
                px = dx / self.scale; py = dy / self.scale
                cps.append({"inch": list(m["inch"]),
                            "px":   [round(px, 1), round(py, 1)]})
            results[kind][stage] = cps
        else:
            results[kind][stage] = list(self.clicks)
        self.clicks = []
        self.markers = []
        self.stage_idx += 1
        if self.stage_idx >= len(self.stages):
            self.photo_idx += 1
            self.load_photo()
        else:
            self.canvas.delete("stage")
            self.start_stage()

    # ---------------------------------------------------
    def finish(self):
        with open(OUT_JSON, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved {OUT_JSON}")
        self.master.destroy()


root = tk.Tk()
app = ClickApp(root)
root.mainloop()
