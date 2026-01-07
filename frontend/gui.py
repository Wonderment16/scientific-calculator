#!/usr/bin/env python3
"""
Calculator GUI (commented)

This is the same working GUI you approved — with inline comments added throughout so
you can show the code to someone learning programming.

Key features (already implemented):
- Dark-themed scientific + graphing calculator UI (Tkinter).
- Slide-in sidebar with "Scientific" and "Graphing".
- Trig and Stats dropdown overlays (non-blocking).
- Functions inserted with auto-closing parentheses, caret placed between ().
- History overlay, equal-sized keypad tiles, safe plotting via backend.evaluate_for_x.
- Embedded Matplotlib canvas with toolbar and basic floating controls (grid/zoom/fit/export).
- All UI interactions operate on the focused input (scientific entry or graph entry).

Adjust the backend import at the top if your CalculatorEngine is located elsewhere.
"""

import math
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Tuple, Optional

import numpy as np
import matplotlib
matplotlib.use("TkAgg")  # use TkAgg backend for embedding in Tkinter windows
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from pathlib import Path
import sys


# Import the calculator backend engine (safe evaluation, plotting helpers).
# Adjust the import path to where your backend engine actually lives.
try:
    from backend.engine import CalculatorEngine
except Exception:
    raise ImportError("Could not import CalculatorEngine. Ensure backend.engine exists and provides CalculatorEngine.")


# -------------------------
# Visual theme / constants
# -------------------------
WINDOW_WIDTH = 380
WINDOW_HEIGHT = 540

BG = "#0f1113"          # main app background
PANEL_BG = "#17181A"    # panels / container background
BTN_BG = "#2b2d30"      # button tile background
FG = "#E6EEF3"          # foreground text (light)
ACCENT = "#cfeeff"      # accent color for titles, etc.

TITLE_FONT = ("Segoe UI", 13, "bold")
DISPLAY_FONT = ("Consolas", 18)


# -------------------------
# Small helper class used for plotted traces
# -------------------------
class GraphTrace:
    def __init__(self, expr: str, xs: np.ndarray, ys: np.ndarray, color: Optional[str] = None):
        self.expr = expr
        self.xs = xs
        self.ys = ys
        self.color = color


# -------------------------
# Main application class
# -------------------------
class CalculatorGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("Calculator")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(350, 500)
        self.configure(bg=BG)

        # ---------- robust icon loading ----------
        # If this file is at frontend/gui.py and assets/ is at the project root,
        # parent.parent moves from frontend -> project root.
        if getattr(sys, "frozen", False):
            # Support PyInstaller one-file bundle
            base_dir = Path(sys._MEIPASS)
        else:
            base_dir = Path(__file__).resolve().parent.parent

        icon_path = base_dir / "assets" / "app_icon.png"

        if not icon_path.exists():
            # Either warn or raise so you can see the exact path that was looked for
            raise FileNotFoundError(f"Calculator icon not found at: {icon_path}")

        # Keep a reference to the PhotoImage so it isn't garbage-collected
        self.icon = tk.PhotoImage(file=str(icon_path))

        # Use positional args for iconphoto: (default, *images)
        self.iconphoto(True, self.icon)

        # Backend engine instance
        self.engine = CalculatorEngine()
        self.engine.set_mode("deg")  # default angle mode

        # Internal state
        self.sidebar_width = 220
        self.sidebar_visible = False
        self._sidebar_animating = False   # guard to prevent overlapping sidebar animations
        self.trig_dropdown: Optional[tk.Toplevel] = None   # overlay window for trig functions
        self.stats_dropdown: Optional[tk.Toplevel] = None  # overlay window for stats functions
        self.history_window: Optional[tk.Toplevel] = None  # history overlay
        self.is_rad = False   # angle mode flag
        self.history: List[Tuple[str, str]] = []  # list of (expression, result)
        self.mode = "scientific"  # current UI mode: "scientific" or "graphing"

        # Color cycle for plotting multiple traces
        self.color_cycle = iter(matplotlib.rcParams['axes.prop_cycle'].by_key()['color'])
        self.traces: List[GraphTrace] = []  # stored graph traces shown on the plot

        # Build UI sections
        self._build_header()        # top bar with hamburger/title/history
        self._build_sidebar()       # slide-in sidebar overlay
        self._build_main_frames()   # scientific and graphing frames
        self._switch_to_mode("scientific")  # show scientific first

        # Global handlers
        # Close dropdown overlays when clicking anywhere (fallback)
        self.bind_all("<Button-1>", self._global_click, add="+")
        # Backspace key handling (operate on the focused calculator entry)
        self.bind("<BackSpace>", self._on_backspace_key, add="+")

    # -------------------------
    # Header and hamburger icon
    # -------------------------
    def _build_header(self):
        """Top header with hamburger, title, and history button."""
        header = tk.Frame(self, bg=PANEL_BG, height=48)
        header.pack(fill="x", side="top")

        # Hamburger button: we bind on ButtonRelease for reliable event ordering.
        self.hamburger_btn = tk.Button(header, text="≡", bg=PANEL_BG, fg=FG, relief="flat")
        self.hamburger_btn.pack(side="left", padx=(8, 4), pady=6)
        # Use ButtonRelease so the click event doesn't get swallowed by other handlers
        self.hamburger_btn.bind("<ButtonRelease-1>", self._on_hamburger_click)

        # Title label (changes when mode switches)
        self.title_label = tk.Label(header, text="Scientific", bg=PANEL_BG, fg=FG, font=TITLE_FONT)
        self.title_label.pack(side="left", padx=(6, 0), pady=6)

        # Spacer to push the History button to the right
        tk.Frame(header, bg=PANEL_BG).pack(side="left", expand=True)

        # History overlay toggle
        self.history_btn = tk.Button(header, text="History", bg=PANEL_BG, fg=FG, relief="flat", command=self.toggle_history)
        self.history_btn.pack(side="right", padx=8, pady=6)

    def _on_hamburger_click(self, event):
        """Handler for the hamburger click — schedule toggle to avoid immediate global click interference."""
        # Delay by 1ms to allow event ordering to settle (prevents global click closing the sidebar immediately)
        self.after(1, self.toggle_sidebar)

    # -------------------------
    # Sidebar (slide-in overlay)
    # -------------------------
    def _build_sidebar(self):
        """Create the sidebar overlay but keep it off-screen initially."""
        self.sidebar = tk.Frame(self, bg="#111214", width=self.sidebar_width, height=self.winfo_height())
        self.sidebar.place(x=-self.sidebar_width, y=48)  # off-screen

        # Only two entries as requested
        tk.Label(self.sidebar, text="Calculator", bg="#111214", fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 8))

        tk.Button(self.sidebar, text="Scientific", bg=BTN_BG, fg=FG, relief="flat",
                  command=lambda: self._select_mode("scientific")).pack(fill="x", padx=12, pady=6)

        tk.Button(self.sidebar, text="Graphing", bg=BTN_BG, fg=FG, relief="flat",
                  command=lambda: self._select_mode("graphing")).pack(fill="x", padx=12, pady=6)

    def toggle_sidebar(self):
        """Toggle the sidebar open/closed; guarded to prevent overlapping animations."""
        if self._sidebar_animating:
            return
        if self.sidebar_visible:
            self.close_sidebar()
        else:
            self.open_sidebar()

    def open_sidebar(self):
        """Animated open of sidebar. Lifts it above other widgets and animates placement."""
        if self._sidebar_animating or self.sidebar_visible:
            return
        self._sidebar_animating = True
        self.sidebar.lift()
        start_x = -self.sidebar_width
        end_x = 0
        step = 20

        def anim(x=start_x):
            # Incrementally move the sidebar into place
            if x < end_x:
                x2 = x + step
                if x2 > end_x:
                    x2 = end_x
                self.sidebar.place(x=x2, y=48)
                if x2 < end_x:
                    self.after(8, lambda: anim(x2))
                else:
                    self._sidebar_animating = False
                    self.sidebar_visible = True
            else:
                # safety fallback
                self._sidebar_animating = False
                self.sidebar_visible = True

        anim(start_x)

    def close_sidebar(self):
        """Animated close of sidebar (slide out)."""
        # If already animating or not visible, try immediate hide to keep state consistent.
        if self._sidebar_animating or not self.sidebar_visible:
            if self._sidebar_animating:
                self._sidebar_animating = False
            return self.close_sidebar_immediate_if_needed()

        self._sidebar_animating = True
        start_x = 0
        end_x = -self.sidebar_width
        step = 20

        def anim(x=start_x):
            if x > end_x:
                x2 = x - step
                if x2 < end_x:
                    x2 = end_x
                self.sidebar.place(x=x2, y=48)
                if x2 > end_x:
                    self.after(8, lambda: anim(x2))
                else:
                    self._sidebar_animating = False
                    self.sidebar_visible = False
            else:
                self._sidebar_animating = False
                self.sidebar_visible = False

        anim(start_x)

    def close_sidebar_immediate_if_needed(self):
        """Hide the sidebar immediately and reset animation flags (used when switching modes)."""
        try:
            self.sidebar.place(x=-self.sidebar_width, y=48)
        except Exception:
            try:
                self.sidebar.place_forget()
            except Exception:
                pass
        self._sidebar_animating = False
        self.sidebar_visible = False

    # -------------------------
    # Mode selection (scientific <-> graphing)
    # -------------------------
    def _select_mode(self, mode: str):
        """
        Called when the user selects a mode from the sidebar.
        We hide the sidebar immediately so the main view becomes visible at once.
        """
        self.close_sidebar_immediate_if_needed()
        self._switch_to_mode(mode)

    # -------------------------
    # Main frames (scientific and graphing)
    # -------------------------
    def _build_main_frames(self):
        """Create container and both scientific and graphing views (we will pack/unpack to switch)."""
        self.main_container = tk.Frame(self, bg=PANEL_BG)
        self.main_container.pack(fill="both", expand=True, padx=8, pady=8)

        # Scientific UI frame
        self.scientific_frame = tk.Frame(self.main_container, bg=PANEL_BG)
        self._build_scientific_ui(self.scientific_frame)

        # Graphing UI frame
        self.graph_frame = tk.Frame(self.main_container, bg=PANEL_BG)
        self._build_graph_ui(self.graph_frame)

    def _switch_to_mode(self, mode: str):
        """Show only the requested mode's frame."""
        self.mode = mode
        self.title_label.config(text=mode.capitalize())
        if mode == "scientific":
            # hide graph frame, show scientific
            self.graph_frame.pack_forget()
            self.scientific_frame.pack(fill="both", expand=True)
        else:
            # hide scientific frame, show graph
            self.scientific_frame.pack_forget()
            self.graph_frame.pack(fill="both", expand=True)

    # -------------------------
    # Scientific UI build
    # -------------------------
    def _build_scientific_ui(self, parent):
        """
        Build the scientific UI: display, expression entry, dropdown toggles, keypad.
        Keypad buttons that insert functions use _insert_with_autoclose so they insert 'fn()'
        with caret placed between parentheses.
        """
        # Display area (result/error area)
        disp = tk.Frame(parent, bg=PANEL_BG)
        disp.pack(fill="x")
        self.display_var = tk.StringVar()
        tk.Label(disp, textvariable=self.display_var, bg=PANEL_BG, fg=FG,
                 anchor="e", font=DISPLAY_FONT).pack(fill="x", padx=6, pady=(6, 4))

        # Expression entry (user types here)
        self.expr_var = tk.StringVar()
        self.entry = tk.Entry(disp, textvariable=self.expr_var, bg=BG, fg=FG,
                              insertbackground=FG, relief="flat", font=("Consolas", 12))
        self.entry.pack(fill="x", padx=6, pady=(0, 6), ipady=6)
        self.entry.bind("<Return>", lambda e: self._evaluate())

        # Row with dropdown toggles and DEG indicator
        toggles = tk.Frame(parent, bg=PANEL_BG); toggles.pack(fill="x")
        self.trig_btn = tk.Button(toggles, text="Trigonometry ▾", bg=PANEL_BG, fg=FG, relief="flat", command=self._open_trig_dropdown)
        self.trig_btn.pack(side="left", padx=(0, 6), pady=6)
        self.stats_btn = tk.Button(toggles, text="Function ▾", bg=PANEL_BG, fg=FG, relief="flat", command=self._open_stats_dropdown)
        self.stats_btn.pack(side="left", padx=(0, 6), pady=6)
        tk.Frame(toggles, bg=PANEL_BG).pack(side="left", expand=True)
        self.mode_label = tk.Label(toggles, text="DEG", bg=PANEL_BG, fg=FG)
        self.mode_label.pack(side="right", padx=6)

        # Keypad grid of tiles (rows x columns). Buttons are uniform-sized by grid weight.
        tile_container = tk.Frame(parent, bg=PANEL_BG)
        tile_container.pack(fill="both", expand=True, pady=(6, 0))
        tiles = [
            ["π", "C", "(", ")", "⌫", "RAD"],
            ["7", "8", "9", "*", "/", "n!"],
            ["4", "5", "6", "-", "mod(", ","],
            ["1", "2", "3", "+", "ANS", ""],
            ["0", ".", "=", "Graph", "ln(", ""],
        ]
        # Create buttons and spacers; map label -> command with _map_button
        for r, row in enumerate(tiles):
            for c, label in enumerate(row):
                if not label:
                    spacer = tk.Frame(tile_container, bg=PANEL_BG)
                    spacer.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
                else:
                    btn = tk.Button(tile_container, text=label, bg=BTN_BG, fg=FG, relief="flat",
                                    command=self._map_button(label))
                    btn.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
                tile_container.grid_columnconfigure(c, weight=1)
            tile_container.grid_rowconfigure(r, weight=1)

    def _map_button(self, label: str):
        """
        Map a keypad label to the appropriate handler.
        For function-like labels that end with '(' we return a lambda that calls
        _insert_with_autoclose(token) — which inserts token + ')' and places the caret inside.
        """
        if label == "C":
            return self._clear_entry
        if label == "⌫":
            return self._backspace_button
        if label == "ANS":
            return self._insert_last_answer
        if label == "=":
            return self._evaluate
        if label == "Graph":
            # graph button switches mode to graphing view
            return lambda: self._switch_to_mode("graphing")
        if label == "π":
            return lambda: self._insert_text("pi")
        if label in ("ln(", "ln"):
            return lambda: self._insert_with_autoclose("ln(")
        if label == "n!":
            return lambda: self._insert_with_autoclose("factorial(")
        if label == "mod(":
            return lambda: self._insert_with_autoclose("mod(")
        if label in ("√", "sqrt"):
            return lambda: self._insert_with_autoclose("sqrt(")
        # default insertion for numbers/operators
        return lambda l=label: self._insert_text(l)

    # -------------------------
    # Graphing UI build
    # -------------------------
    def _build_graph_ui(self, parent):
        """
        Build the graphing UI:
        - Input for f(x)
        - Run / Add / Clear buttons
        - x-range and sample count input
        - Embedded Matplotlib canvas with toolbar
        - Floating buttons for Grid/Zoom/Fit/Export
        """
        # Top row: function input and action buttons
        top = tk.Frame(parent, bg=PANEL_BG); top.pack(fill="x", padx=6, pady=(6, 4))
        tk.Label(top, text="f(x) =", bg=PANEL_BG, fg=FG).grid(row=0, column=0, sticky="w")
        self.fx_var = tk.StringVar(value="sin(x)")
        self.fx_entry = tk.Entry(top, textvariable=self.fx_var, bg=BG, fg=FG, insertbackground=FG)
        self.fx_entry.grid(row=0, column=1, sticky="ew", padx=6)
        top.columnconfigure(1, weight=1)

        # Trig/Stats toggles for the graphing entry as well
        self.trig_btn_graph = tk.Button(top, text="Trig ▾", bg=PANEL_BG, fg=FG, relief="flat", command=self._open_trig_dropdown)
        self.trig_btn_graph.grid(row=0, column=2, padx=4)
        self.stats_btn_graph = tk.Button(top, text="Stats ▾", bg=PANEL_BG, fg=FG, relief="flat", command=self._open_stats_dropdown)
        self.stats_btn_graph.grid(row=0, column=3, padx=4)

        # Run / Add / Clear
        controls = tk.Frame(top, bg=PANEL_BG); controls.grid(row=0, column=4, sticky="e")
        self.run_btn = tk.Button(controls, text="▶ Run", bg=BTN_BG, fg=FG, command=self._run_plot); self.run_btn.pack(side="left", padx=4)
        self.add_btn = tk.Button(controls, text="+ Add", bg=BTN_BG, fg=FG, command=self._add_plot); self.add_btn.pack(side="left", padx=4)
        self.clear_btn = tk.Button(controls, text="Clear", bg=BTN_BG, fg=FG, command=self._clear_plot); self.clear_btn.pack(side="left", padx=4)

        # Range and samples row
        rng = tk.Frame(parent, bg=PANEL_BG); rng.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(rng, text="x-min", bg=PANEL_BG, fg=FG).pack(side="left")
        self.xmin_var = tk.StringVar(value="-10"); tk.Entry(rng, textvariable=self.xmin_var, width=8).pack(side="left", padx=(4, 12))
        tk.Label(rng, text="x-max", bg=PANEL_BG, fg=FG).pack(side="left")
        self.xmax_var = tk.StringVar(value="10"); tk.Entry(rng, textvariable=self.xmax_var, width=8).pack(side="left", padx=(4, 12))
        tk.Label(rng, text="samples", bg=PANEL_BG, fg=FG).pack(side="left")
        self.samples_var = tk.StringVar(value="400"); tk.Entry(rng, textvariable=self.samples_var, width=6).pack(side="left", padx=(4, 12))

        # Canvas area for Matplotlib (embedded)
        canvas_frame = tk.Frame(parent, bg=PANEL_BG); canvas_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.fig = Figure(figsize=(5, 3), dpi=100, facecolor=PANEL_BG)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#131416")
        for spine in self.ax.spines.values():
            spine.set_color("#44484C")

        # Actual Tk widget for matplotlib drawing
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Matplotlib toolbar (pan/zoom/save)
        self.toolbar = NavigationToolbar2Tk(self.canvas, canvas_frame)
        self.toolbar.update()
        self.toolbar.pack(fill="x")

        # Floating control bar on top-right of the canvas frame
        floatbar = tk.Frame(canvas_frame, bg=PANEL_BG)
        floatbar.place(relx=0.97, rely=0.02, anchor="ne")
        self.grid_on = False
        tk.Button(floatbar, text="Grid", bg=BTN_BG, fg=FG, command=self._toggle_grid).pack(side="top", pady=3, padx=3, fill="x")
        tk.Button(floatbar, text="+", bg=BTN_BG, fg=FG, command=lambda: self._zoom(0.8)).pack(side="top", pady=3, padx=3, fill="x")
        tk.Button(floatbar, text="-", bg=BTN_BG, fg=FG, command=lambda: self._zoom(1.25)).pack(side="top", pady=3, padx=3, fill="x")
        tk.Button(floatbar, text="Fit", bg=BTN_BG, fg=FG, command=self._autoscale_view).pack(side="top", pady=3, padx=3, fill="x")
        tk.Button(floatbar, text="Export", bg=BTN_BG, fg=FG, command=self._export_png).pack(side="top", pady=3, padx=3, fill="x")

    # -------------------------
    # Dropdown overlays (Trig & Stats) and insertion helper
    # -------------------------
    def _open_trig_dropdown(self):
        """
        Create a Toplevel overlay positioned under the appropriate Trig button.
        It inserts function names using _insert_with_autoclose so e.g. "sin(" becomes "sin()"
        with caret placed inside.
        """
        if self.stats_dropdown:
            self._close_stats_dropdown()
        if self.trig_dropdown:
            self._close_trig_dropdown()
            return

        top = tk.Toplevel(self)
        top.overrideredirect(True)  # remove window decorations (no titlebar)
        top.transient(self)
        self.trig_dropdown = top

        # Position the overlay under the appropriate Trig button (graph vs scientific)
        btn = self.trig_btn if self.mode == "scientific" else getattr(self, "trig_btn_graph", self.trig_btn)
        bx = btn.winfo_rootx()
        by = btn.winfo_rooty() + btn.winfo_height()
        top.geometry(f"+{bx}+{by}")

        # Ensure overlay is on top but non-blocking
        top.lift()
        top.attributes("-topmost", True)

        frm = tk.Frame(top, bg=PANEL_BG)
        frm.pack(fill="both", expand=True)

        # Trig function buttons (show short label, insert with autoclose)
        funcs = ["sin(", "cos(", "tan(", "sec(", "csc(", "cot("]
        for i, f in enumerate(funcs):
            b = tk.Button(frm, text=f[:-1], bg=BTN_BG, fg=FG, relief="flat",
                          command=lambda fn=f: self._insert_with_autoclose(fn))
            b.grid(row=0, column=i, padx=4, pady=6, sticky="nsew")
            frm.grid_columnconfigure(i, weight=1)

        # Close overlay when focus moves away
        top.bind("<FocusOut>", lambda e: self._close_trig_dropdown())

    def _close_trig_dropdown(self):
        """Destroy the trig overlay if present."""
        if self.trig_dropdown:
            try:
                self.trig_dropdown.destroy()
            except Exception:
                pass
            self.trig_dropdown = None

    def _open_stats_dropdown(self):
        """Open the stats/functions overlay (similar to trig overlay)."""
        if self.trig_dropdown:
            self._close_trig_dropdown()
        if self.stats_dropdown:
            self._close_stats_dropdown()
            return

        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top.transient(self)
        self.stats_dropdown = top

        # position under the stats toggle button
        btn = self.stats_btn if self.mode == "scientific" else getattr(self, "stats_btn_graph", self.stats_btn)
        bx = btn.winfo_rootx()
        by = btn.winfo_rooty() + btn.winfo_height()
        top.geometry(f"+{bx}+{by}")

        top.lift()
        top.attributes("-topmost", True)

        frm = tk.Frame(top, bg=PANEL_BG)
        frm.pack(fill="both", expand=True)

        # list of statistical / utility functions
        funcs = ["mean(", "median(", "mode(", "std(", "variance(", "min(", "max(", "abs(", "round(", "rand(", "choice("]
        cols = 6
        for i, f in enumerate(funcs):
            r = i // cols
            c = i % cols
            b = tk.Button(frm, text=f.rstrip("(").rstrip(")"), bg=BTN_BG, fg=FG, relief="flat",
                          command=lambda fn=f: self._insert_with_autoclose(fn))
            b.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            frm.grid_columnconfigure(c, weight=1)

        top.bind("<FocusOut>", lambda e: self._close_stats_dropdown())

    def _close_stats_dropdown(self):
        """Destroy the stats overlay if present."""
        if self.stats_dropdown:
            try:
                self.stats_dropdown.destroy()
            except Exception:
                pass
            self.stats_dropdown = None

    def _get_active_entry(self) -> tk.Entry:
        """
        Determine which Entry widget should receive input:
        - If focus is on one of our entries, we return it (lets keyboard-focused edits work).
        - Otherwise we return the default entry for the current mode:
            scientific -> self.entry, graphing -> self.fx_entry.
        This is used by insertion and backspace helpers so the UI acts on the focused control.
        """
        focused = self.focus_get()
        if isinstance(focused, tk.Entry):
            if focused in (getattr(self, "entry", None), getattr(self, "fx_entry", None)):
                return focused
        # fallback based on mode
        return getattr(self, "entry") if self.mode == "scientific" else getattr(self, "fx_entry")

    def _insert_with_autoclose(self, token: str):
        """
        Insert a function token into the active entry, auto-closing parentheses:
        - If token ends with '(' -> insert 'token)' and place caret between parentheses.
        - Else insert the token as-is and move caret to the end of the inserted token.
        After insertion we close any open overlays.
        """
        target = self._get_active_entry()
        idx = target.index(tk.INSERT)
        if token.endswith("("):
            insert_text = token + ")"
            target.insert(idx, insert_text)
            # place caret after the opening '(' so user can type the argument immediately
            target.icursor(idx + len(token))
        else:
            target.insert(idx, token)
            target.icursor(idx + len(token))
        target.focus_set()
        # close overlays for cleanliness
        self._close_trig_dropdown()
        self._close_stats_dropdown()

    # -------------------------
    # Global click fallback to close overlays (non-blocking)
    # -------------------------
    def _global_click(self, event):
        """
        Called for all mouse clicks; used as a safety fallback to close dropdowns if
        the user clicks outside them. We check whether the clicked widget is the
        dropdown toggle or a widget inside the dropdown; if not, close the dropdown.
        """
        w = event.widget
        if self.trig_dropdown:
            btn = self.trig_btn if self.mode == "scientific" else getattr(self, "trig_btn_graph", self.trig_btn)
            # keep dropdown open if click was on the toggle or inside dropdown
            if w is btn or self._is_child_of(w, self.trig_dropdown):
                pass
            else:
                self._close_trig_dropdown()
        if self.stats_dropdown:
            btn = self.stats_btn if self.mode == "scientific" else getattr(self, "stats_btn_graph", self.stats_btn)
            if w is btn or self._is_child_of(w, self.stats_dropdown):
                pass
            else:
                self._close_stats_dropdown()

    def _is_child_of(self, widget, topwin):
        """Walk up widget master chain to check if a widget is a descendant of topwin (a Toplevel)."""
        w = widget
        while w:
            if isinstance(w, tk.Toplevel) and w == topwin:
                return True
            w = getattr(w, "master", None)
        return False

    # -------------------------
    # Scientific input helpers
    # -------------------------
    def _insert_text(self, txt: str):
        """Insert text at the end of the active entry (numbers/operators)."""
        target = self._get_active_entry()
        target.insert(tk.END, txt)
        target.focus_set()

    def _insert_last_answer(self):
        """Insert the most recent history result into the active entry."""
        if self.history:
            tgt = self._get_active_entry()
            tgt.insert(tk.END, self.history[-1][1])
            tgt.focus_set()

    def _clear_entry(self):
        """Clear the scientific expression and display."""
        self.expr_var.set("")
        self.display_var.set("")

    def _backspace_button(self):
        """Backspace invoked by the keypad button (deletes character before caret)."""
        target = self._get_active_entry()
        cur = target.get()
        if cur:
            try:
                pos = target.index(tk.INSERT)
            except Exception:
                pos = len(cur)
            if pos > 0:
                target.delete(pos - 1, pos)
                target.focus_set()

    def _on_backspace_key(self, event):
        """
        Backspace keyboard key handling. We delete the character before the caret
        in the active entry and return "break" to stop default Tk behavior.
        """
        target = self._get_active_entry()
        cur = target.get()
        if cur:
            try:
                pos = target.index(tk.INSERT)
            except Exception:
                pos = len(cur)
            if pos > 0:
                target.delete(pos - 1, pos)
                return "break"

    def _toggle_sign(self):
        """Toggle leading sign of the active entry (insert/delete a leading '-')."""
        target = self._get_active_entry()
        cur = target.get()
        if not cur:
            return
        try:
            if cur.startswith("-"):
                target.delete(0)
            else:
                target.insert(0, "-")
            target.focus_set()
        except Exception:
            pass

    # -------------------------
    # Evaluate expression (scientific)
    # -------------------------
    def _evaluate(self):
        """
        Evaluate the expression in the main scientific entry using the backend engine.
        If parentheses are unbalanced, append the missing ')' characters before evaluation.
        The backend returns either a numeric result or an error string; we display it.
        """
        expr = self.expr_var.get().strip()
        if not expr:
            return
        # Auto-balance parentheses for convenience
        extra = expr.count("(") - expr.count(")")
        if extra > 0:
            expr = expr + (")" * extra)

        # Sync angle mode with backend
        self.engine.set_mode("rad" if self.is_rad else "deg")

        try:
            result = self.engine.calculate(expr)
        except Exception as e:
            result = f"Error: {e}"

        # Show result and add to history
        self.display_var.set(str(result))
        self.history.append((expr, str(result)))

    # -------------------------
    # Graphing actions (run/add/clear)
    # -------------------------
    def _run_plot(self):
        """Clear existing traces and plot current expression."""
        self.traces = []
        self._plot_expression(add=False)

    def _add_plot(self):
        """Add the current expression as an additional trace without clearing existing ones."""
        self._plot_expression(add=True)

    def _clear_plot(self):
        """Clear all traces and reset the plot area."""
        self.traces = []
        self.ax.clear()
        self.ax.set_facecolor("#131416")
        for spine in self.ax.spines.values():
            spine.set_color("#44484C")
        self.canvas.draw()

    def _plot_expression(self, add: bool):
        """
        Sample the expression safely using backend.evaluate_for_x and plot it.
        - add=False replaces existing traces
        - add=True overlays this trace onto existing ones
        """
        expr = self.fx_var.get().strip()
        if not expr:
            messagebox.showinfo("Plot", "Enter an expression in terms of x (example: sin(x))")
            return

        # Validate range
        try:
            xmin = float(self.xmin_var.get()); xmax = float(self.xmax_var.get())
            if xmin >= xmax:
                raise ValueError("x-min must be < x-max")
        except Exception as e:
            messagebox.showerror("Range error", f"Invalid x-range: {e}")
            return

        # Samples (number of x points)
        try:
            samples = int(self.samples_var.get())
            if samples < 10:
                samples = 10
        except Exception:
            samples = 400

        xs = np.linspace(xmin, xmax, samples)
        ys = []
        has_valid = False

        # Sync angle mode to backend
        self.engine.set_mode("rad" if self.is_rad else "deg")

        # Evaluate y for each x using backend.evaluate_for_x (safe)
        for xv in xs:
            try:
                v = self.engine.evaluate_for_x(expr, float(xv))
            except Exception:
                v = None
            if v is None:
                ys.append(float("nan"))
            else:
                try:
                    ys.append(float(v))
                    has_valid = True
                except Exception:
                    ys.append(float("nan"))

        if not has_valid:
            messagebox.showerror("Plot error", "No valid points to plot for this expression")
            return

        # Color selection for trace
        try:
            color = next(self.color_cycle)
        except StopIteration:
            self.color_cycle = iter(matplotlib.rcParams['axes.prop_cycle'].by_key()['color'])
            color = next(self.color_cycle)

        trace = GraphTrace(expr=expr, xs=xs, ys=np.array(ys), color=color)
        if not add:
            self.traces = [trace]
        else:
            self.traces.append(trace)

        # Draw traces
        self.ax.clear()
        self.ax.set_facecolor("#131416")
        for spine in self.ax.spines.values():
            spine.set_color("#44484C")
        for t in self.traces:
            self.ax.plot(t.xs, t.ys, label=t.expr, color=t.color)

        # Legend and autoscale
        if self.traces:
            self.ax.legend(loc="upper right", facecolor="#222", framealpha=0.9, fontsize="small")
        self._autoscale_view()
        self.canvas.draw()

    # -------------------------
    # Plot helpers (grid, zoom, autoscale, export)
    # -------------------------
    def _toggle_grid(self):
        """Toggle grid on the plot."""
        self.grid_on = not getattr(self, "grid_on", False)
        self.ax.grid(self.grid_on, color="#2A2D30")
        self.canvas.draw()

    def _zoom(self, factor: float):
        """Zoom the plot by a multiplicative factor around the current center."""
        x0, x1 = self.ax.get_xlim(); y0, y1 = self.ax.get_ylim()
        cx = 0.5 * (x0 + x1); cy = 0.5 * (y0 + y1)
        halfw = (x1 - x0) * 0.5 * factor; halfh = (y1 - y0) * 0.5 * factor
        self.ax.set_xlim(cx - halfw, cx + halfw); self.ax.set_ylim(cy - halfh, cy + halfh)
        self.canvas.draw()

    def _autoscale_view(self):
        """Autoscale view to show all valid (non-NaN) points of all traces."""
        if not getattr(self, "traces", None):
            self.canvas.draw()
            return
        xs_all = np.concatenate([t.xs for t in self.traces])
        ys_all = np.concatenate([t.ys for t in self.traces])
        ys_valid = ys_all[~np.isnan(ys_all)]
        if ys_valid.size == 0:
            self.canvas.draw()
            return
        xmin, xmax = xs_all.min(), xs_all.max()
        ymin, ymax = ys_valid.min(), ys_valid.max()
        if ymin == ymax:
            ymin -= 1; ymax += 1
        margin = (ymax - ymin) * 0.08
        self.ax.set_xlim(xmin, xmax); self.ax.set_ylim(ymin - margin, ymax + margin)
        self.canvas.draw()

    def _export_png(self):
        """Save the current figure to a PNG image via a file dialog."""
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png")],
                                            initialfile="plot.png")
        if not path:
            return
        try:
            self.fig.savefig(path, dpi=150, facecolor=self.fig.get_facecolor())
            messagebox.showinfo("Export", f"Saved plot to {path}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    # -------------------------
    # History overlay
    # -------------------------
    def toggle_history(self):
        """Open or close the history overlay window (bottom anchored)."""
        if self.history_window and tk.Toplevel.winfo_exists(self.history_window):
            self._close_history()
            return
        win = tk.Toplevel(self)
        win.title("History")
        win.geometry(f"{self.winfo_width()}x180+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() - 180}")
        win.transient(self)
        self.history_window = win

        frm = tk.Frame(win, bg="#0e0f10")
        frm.pack(fill="both", expand=True)
        lb = tk.Listbox(frm, bg="#0e0f10", fg=FG)
        lb.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        # fill listbox with recent history (limit 200)
        for expr, res in self.history[-200:]:
            lb.insert("end", f"{expr} = {res}")

        # double-click to insert expression back into the active entry
        lb.bind("<Double-Button-1>", lambda e: self._on_history_double(e, listbox=lb))

        scrollbar = tk.Scrollbar(frm, command=lb.yview)
        lb.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Close history if focus moves away
        win.bind("<FocusOut>", lambda e: self._close_history())

    def _close_history(self):
        """Close the history window if open."""
        if self.history_window:
            try:
                self.history_window.destroy()
            except Exception:
                pass
            self.history_window = None

    def _on_history_double(self, event, listbox):
        """Handler to re-use an expression from history (double-click)."""
        sel = listbox.curselection()
        if not sel:
            return
        item = listbox.get(sel[0])
        expr = item.split(" = ")[0]
        if self.mode == "scientific":
            self.expr_var.set(expr)
        else:
            self.fx_var.set(expr)
        self._close_history()

# -------------------------
# Run the application
# -------------------------
def main():
    # Create and run the GUI
    app = CalculatorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()