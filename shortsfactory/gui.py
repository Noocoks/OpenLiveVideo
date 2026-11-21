from __future__ import annotations

import json
import logging
from importlib import resources
import math
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .config import (get_pixabay_key, load_settings, migrate_legacy_drafts,
                     save_pixabay_key, save_settings, user_data_dir, configure_logging)
from .models import Episode, suggest_title
from .pipeline import (prepare_episode, render_prepared, ProductionCancelled,
                       PreparedProduction)

# OLV visual identity: industrial / crimson.
BG = "#0d1117"
PANEL = "#121820"
PANEL_2 = "#19222b"
PANEL_3 = "#222d37"
BORDER = "#2b3742"
TEXT = "#edf0f2"
MUTED = "#9aa5af"
RED = "#790018"
RED_HOVER = "#a21d3b"
RED_LIGHT = "#d14a68"
GREEN = "#6dbb83"
VOICES = {
    "Álvaro · Español (España)": "es-ES-AlvaroNeural",
    "Elvira · Español (España)": "es-ES-ElviraNeural",
}
PLACEHOLDER_TITLE = "Mi nueva historia"


class ShortsFactoryApp:
    """Dark, keyboard-friendly desktop interface for the local Shorts workflow."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.project_dir = Path(__file__).resolve().parent.parent
        self.data_dir = user_data_dir()
        self.settings = load_settings()
        self.status = tk.StringVar(value="Listo para crear.")
        try:
            migrate_legacy_drafts(self.project_dir, self.data_dir)
        except OSError:
            self.status.set("No se pudieron importar algunos borradores antiguos.")
        self.title_var = tk.StringVar(value="")
        self.voice_label = tk.StringVar(value=self._voice_label(self.settings.get("voice", "es-ES-AlvaroNeural")))
        self.music_var = tk.StringVar(value=self.settings.get("music_path", ""))
        self.output_var = tk.StringVar(value=self.settings.get("output_dir", str(self.data_dir / "output" / "review")))
        self.last_output: Path | None = None
        self._autosave_job: str | None = None
        self._is_running = False
        self._cancel_event = threading.Event()
        self._prepared: PreparedProduction | None = None
        self._close_when_done = False
        self.logo_image = None
        self.logo_small = None

        root.title("OLV")
        root.geometry("920x720")
        root.minsize(640, 500)
        root.configure(bg=BG)
        self._load_brand_logo()
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._bind_autosave()
        self._restore_last_draft()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_brand_logo(self):
        """Load the bundled master emblem; use a native Tk fallback if SVG rendering fails."""
        image = None
        try:
            svg_resource = resources.files("shortsfactory").joinpath(
                "assets", "branding", "olv-master.svg")
            if svg_resource.is_file():
                import base64
                import cairosvg
                rendered = cairosvg.svg2png(
                    bytestring=svg_resource.read_bytes(), output_width=192, output_height=192)
                image = tk.PhotoImage(data=base64.b64encode(rendered).decode("ascii"))
        except Exception:
            image = None

        if image is None:
            # Dependency-free emergency mark: metallic ring and crimson play triangle.
            image = tk.PhotoImage(width=96, height=96)
            rows = []
            for y in range(96):
                row = []
                for x in range(96):
                    radius = math.hypot(x - 48, y - 48)
                    if 34 <= radius <= 42:
                        row.append("#a9a09c" if (x + y) % 7 else "#e8e0dc")
                    elif 13 <= x <= 69 and abs(y - 48) <= (x - 13) * 0.62:
                        row.append("#e51b2b")
                    else:
                        row.append("#0d1117")
                rows.append("{" + " ".join(row) + "}")
            for y, row in enumerate(rows):
                image.put(row, to=(0, y))
        self.logo_image = image
        try:
            self.root.iconphoto(True, self.logo_image)
        except tk.TclError:
            pass

    def _voice_label(self, voice_id: str):
        return next((label for label, value in VOICES.items() if value == voice_id),
                    "Álvaro · Español (España)")

    def _voice_id(self) -> str:
        return VOICES.get(self.voice_label.get(), "es-ES-AlvaroNeural")

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=("Segoe UI", 19, "bold"))
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Hero.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("Secondary.TButton", background=PANEL_2, foreground=TEXT, padding=(10, 8))
        style.map("Secondary.TButton", background=[("active", PANEL_3)])
        style.configure("TEntry", fieldbackground="#171d24", foreground=TEXT,
                        insertcolor=RED_LIGHT, bordercolor=BORDER, padding=9,
                        lightcolor=BORDER, darkcolor=BORDER)
        style.map("TEntry", bordercolor=[("focus", RED_LIGHT)])
        style.configure("TCombobox", fieldbackground="#171d24", foreground=TEXT,
                        background=PANEL_2, arrowcolor=TEXT, padding=8,
                        bordercolor=BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", "#171d24")],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL_2)])
        style.configure("Accent.TButton", background=RED, foreground="#ffffff",
                        padding=(22, 11), font=("Segoe UI", 10, "bold"),
                        borderwidth=0, relief="flat")
        style.map("Accent.TButton", background=[("active", RED_HOVER),
                  ("disabled", "#51242b")], foreground=[("disabled", "#a9a0a1")])
        style.configure("Quiet.TButton", background=PANEL_2, foreground=TEXT,
                        padding=(10, 8), borderwidth=0, relief="flat")
        style.map("Quiet.TButton", background=[("active", PANEL_3)],
                  foreground=[("active", "#ffffff")])
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL_2,
                        background=RED_LIGHT, bordercolor=PANEL_2,
                        lightcolor=RED_LIGHT, darkcolor=RED)
        style.configure("TSeparator", background=BORDER)

    def _build_menu(self):
        menu = tk.Menu(self.root, bg=PANEL, fg=TEXT, activebackground=RED,
                       activeforeground="#ffffff", tearoff=False, bd=0)

        file_menu = tk.Menu(menu, tearoff=False, bg=PANEL, fg=TEXT,
                            activebackground=RED, activeforeground="#ffffff")
        file_menu.add_command(label="Nueva historia", accelerator="Ctrl+N", command=self._new_story)
        file_menu.add_command(label="Abrir…", accelerator="Ctrl+O", command=self._open_story)
        file_menu.add_command(label="Guardar borrador", accelerator="Ctrl+S", command=self._save_draft)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_close)
        menu.add_cascade(label="Archivo", menu=file_menu)

        settings_menu = tk.Menu(menu, tearoff=False, bg=PANEL, fg=TEXT,
                                activebackground=RED, activeforeground="#ffffff")
        settings_menu.add_command(label="Clave de Pixabay…", command=self._set_api_key)
        settings_menu.add_command(label="Voz de narración…", command=self._set_voice)
        settings_menu.add_command(label="Música de fondo…", command=self._choose_music)
        settings_menu.add_command(label="Carpeta de salida…", command=self._choose_output)
        settings_menu.add_separator()
        settings_menu.add_command(label="Comprobar requisitos", command=self._check_requirements)
        menu.add_cascade(label="Ajustes", menu=settings_menu)

        help_menu = tk.Menu(menu, tearoff=False, bg=PANEL, fg=TEXT,
                            activebackground=RED, activeforeground="#ffffff")
        help_menu.add_command(label="Licencia AGPL-3.0-or-later", command=self._open_license)
        help_menu.add_command(label="Registros de diagnóstico", command=self._open_logs)
        help_menu.add_command(label="Acerca de OLV", command=self._about)
        menu.add_cascade(label="Ayuda", menu=help_menu)

        self.root.configure(menu=menu)
        self.root.bind("<Control-n>", lambda _e: self._new_story())
        self.root.bind("<Control-o>", lambda _e: self._open_story())
        self.root.bind("<Control-s>", lambda _e: self._save_draft())
        self.root.bind("<F5>", lambda _e: self._create())

    def _build_layout(self):
        # A single writing surface: the story is the main focus.
        self._layout_canvas = tk.Canvas(self.root, bg=BG, bd=0, highlightthickness=0)
        self._layout_canvas.pack(fill="both", expand=True)
        outer = ttk.Frame(self._layout_canvas, padding=(30, 20, 30, 20))
        self._layout_window = self._layout_canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>", lambda _event: self._layout_canvas.configure(
            scrollregion=self._layout_canvas.bbox("all")))
        self._layout_canvas.bind("<Configure>", lambda event: self._layout_canvas.itemconfigure(
            self._layout_window, width=event.width))
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_linux_mousewheel)
        self.root.bind_all("<Button-5>", self._on_linux_mousewheel)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 28))
        if self.logo_image is not None:
            self.logo_small = self.logo_image.subsample(3, 3)
            tk.Label(header, image=self.logo_small, bg=BG, bd=0).pack(side="left", padx=(0, 10))
        ttk.Label(header, text="OLV", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Tu imaginación en vida", style="Muted.TLabel").pack(
            side="left", padx=(12, 0), pady=(5, 0))
        ttk.Button(header, text="Abrir", style="Quiet.TButton",
                   command=self._open_story).pack(side="right")
        ttk.Button(header, text="Guardar", style="Quiet.TButton",
                   command=self._save_draft).pack(side="right", padx=(0, 8))

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Tu historia", style="Title.TLabel").pack(anchor="w", pady=(0, 12))

        title_row = ttk.Frame(content)
        title_row.pack(fill="x", pady=(0, 10))
        self.title_entry = ttk.Entry(title_row, textvariable=self.title_var)
        self.title_entry.pack(fill="x")

        editor_shell = tk.Frame(content, bg=BORDER, padx=1, pady=1)
        editor_shell.pack(fill="both", expand=True)
        self.script = tk.Text(editor_shell, wrap="word", undo=True, bg="#10151b", fg=TEXT,
                              insertbackground=RED_LIGHT, selectbackground="#6f1727",
                              relief="flat", padx=16, pady=14, font=("Segoe UI", 11),
                              highlightthickness=0, spacing1=3, spacing3=5, borderwidth=0)
        self.script.pack(fill="both", expand=True)
        self.script.insert("1.0", "")

        ttk.Label(content, text="Separa cada escena con una línea en blanco.",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 18))

        options = ttk.Frame(content)
        options.pack(fill="x", pady=(0, 14))
        voice_group = ttk.Frame(options)
        voice_group.pack(side="left", fill="x", expand=True)
        ttk.Label(voice_group, text="VOZ", style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        self.voice_box = ttk.Combobox(voice_group, textvariable=self.voice_label,
            values=list(VOICES.keys()), state="readonly", width=25)
        self.voice_box.pack(anchor="w", fill="x", padx=(0, 12))
        self.voice_box.bind("<<ComboboxSelected>>", lambda _e: self._persist_preferences())

        music_group = ttk.Frame(options)
        music_group.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Label(music_group, text="MÚSICA", style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        music_row = ttk.Frame(music_group)
        music_row.pack(fill="x")
        ttk.Label(music_row, textvariable=self._music_name_var(),
                  style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(music_row, text="Elegir", style="Quiet.TButton",
                   command=self._choose_music).pack(side="right")

        output_group = ttk.Frame(options)
        output_group.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(output_group, text="DESTINO", style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        output_row = ttk.Frame(output_group)
        output_row.pack(fill="x")
        ttk.Label(output_row, textvariable=self.output_var,
                  style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="Cambiar", style="Quiet.TButton",
                   command=self._choose_output).pack(side="right")

        ttk.Separator(content).pack(fill="x", pady=(2, 14))
        footer = ttk.Frame(content)
        footer.pack(fill="x")
        status_area = ttk.Frame(footer)
        status_area.pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(status_area, mode="indeterminate",
                                        style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 7))
        ttk.Label(status_area, textvariable=self.status, style="Muted.TLabel").pack(anchor="w")
        self.cancel_btn = ttk.Button(footer, text="Cancelar", style="Quiet.TButton",
                                     command=self._cancel_production, state="disabled")
        self.cancel_btn.pack(side="right", padx=(10, 0))
        self.create_btn = ttk.Button(footer, text="Crear Short", style="Accent.TButton",
                                     command=self._create)
        self.create_btn.pack(side="right", padx=(0, 8))

    def _on_mousewheel(self, event):
        if isinstance(event.widget, tk.Text):
            if event.delta:
                units = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
                event.widget.yview_scroll(units, "units")
            return "break"
        canvas = self._layout_canvas
        x, y = event.x_root, event.y_root
        inside = (canvas.winfo_rootx() <= x <= canvas.winfo_rootx() + canvas.winfo_width()
                  and canvas.winfo_rooty() <= y <= canvas.winfo_rooty() + canvas.winfo_height())
        if inside and event.delta:
            units = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
            canvas.yview_scroll(units, "units")

    def _on_linux_mousewheel(self, event):
        if isinstance(event.widget, tk.Text):
            event.widget.yview_scroll(-3 if event.num == 4 else 3, "units")
            return "break"
        canvas = self._layout_canvas
        x, y = event.x_root, event.y_root
        inside = (canvas.winfo_rootx() <= x <= canvas.winfo_rootx() + canvas.winfo_width()
                  and canvas.winfo_rooty() <= y <= canvas.winfo_rooty() + canvas.winfo_height())
        if inside:
            canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

    def _side_label(self, parent, text):
        ttk.Label(parent, text=text, style="PanelMuted.TLabel",
                  font=("Segoe UI", 8, "bold")).pack(anchor="w")

    def _music_name_var(self):
        self.music_name = tk.StringVar(value=Path(self.music_var.get()).name if self.music_var.get() else "Sin música seleccionada")
        return self.music_name

    def _bind_autosave(self):
        self.script.bind("<KeyRelease>", self._schedule_autosave)
        self.title_entry.bind("<KeyRelease>", self._schedule_autosave)

    def _schedule_autosave(self, _event=None):
        if self._autosave_job:
            self.root.after_cancel(self._autosave_job)
        self._autosave_job = self.root.after(1200, self._autosave)

    def _restore_last_draft(self):
        path = self.data_dir / "drafts" / "last_draft.json"
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.title_var.set(data.get("title", ""))
            self.script.delete("1.0", "end")
            self.script.insert("1.0", data.get("script", ""))
            self.voice_label.set(self._voice_label(data.get("voice", "es-ES-AlvaroNeural")))
            self.music_var.set(data.get("music_path", self.music_var.get()))
            self.output_var.set(data.get("output_dir", self.output_var.get()))
            self.music_name.set(Path(self.music_var.get()).name if self.music_var.get()
                                else "Sin música seleccionada")
            if data.get("script", "").strip():
                self.status.set("Último borrador restaurado automáticamente.")
        except (OSError, json.JSONDecodeError, AttributeError):
            self.status.set("No se pudo recuperar el último borrador.")

    def _draft_data(self):
        return {"title": self.title_var.get().strip(),
                "script": self.script.get("1.0", "end-1c").strip(),
                "voice": self._voice_id(), "music_path": self.music_var.get(),
                "output_dir": self.output_var.get()}

    def _autosave(self):
        self._autosave_job = None
        data = self._draft_data()
        if not data["script"]:
            return
        try:
            folder = self.data_dir / "drafts"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "last_draft.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set("Borrador guardado automáticamente.")
        except OSError:
            self.status.set("No se pudo guardar el borrador automáticamente.")

    def _save_draft(self):
        data = self._draft_data()
        if not data["script"]:
            messagebox.showinfo("Borrador vacío", "Escribe una historia antes de guardarla.")
            return
        drafts_dir = self.data_dir / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(parent=self.root, title="Guardar historia",
            initialdir=str(drafts_dir), initialfile="mi_historia.json",
            defaultextension=".json", filetypes=[("Historia OLV", "*.json"), ("Texto", "*.txt")])
        if not path:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() == ".txt":
            target.write_text(data["script"], encoding="utf-8")
        else:
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.set(f"Historia guardada: {target.name}")

    def _open_story(self):
        path = filedialog.askopenfilename(parent=self.root, title="Abrir historia",
            filetypes=[("Historias", "*.json *.txt"), ("Todos los archivos", "*.*")])
        if not path:
            return
        target = Path(path)
        try:
            if target.suffix.lower() == ".json":
                data = json.loads(target.read_text(encoding="utf-8"))
                self.title_var.set(data.get("title", ""))
                script = data.get("script", "")
                self.music_var.set(data.get("music_path", self.music_var.get()))
                self.output_var.set(data.get("output_dir", self.output_var.get()))
                self.voice_label.set(self._voice_label(data.get("voice", "es-ES-AlvaroNeural")))
            else:
                script = target.read_text(encoding="utf-8")
                self.title_var.set(target.stem.replace("_", " "))
            self.script.delete("1.0", "end")
            self.script.insert("1.0", script)
            self.status.set(f"Historia cargada: {target.name}")
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            messagebox.showerror("No se pudo abrir", str(exc))

    def _new_story(self):
        if self.script.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("Nueva historia", "¿Quieres empezar una historia nueva? El borrador actual se conserva."):
                return
        self.title_var.set("")
        self.script.delete("1.0", "end")
        self.status.set("Nueva historia lista.")

    def _set_api_key(self):
        current = get_pixabay_key()
        value = simpledialog.askstring("Pixabay · API Key",
            "Pega tu API Key. Se guardará en el almacén seguro de credenciales del sistema:",
            initialvalue=current, parent=self.root, show="*")
        if value is not None:
            try:
                save_pixabay_key(value)
                self.status.set("Clave de Pixabay guardada de forma segura.")
            except Exception as exc:
                messagebox.showerror("Almacén seguro no disponible", str(exc))

    def _set_voice(self):
        from tkinter import Toplevel
        win = Toplevel(self.root)
        win.title("Voz de narración")
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Selecciona la voz predeterminada:").pack(anchor="w", padx=18, pady=(18, 8))
        choice = tk.StringVar(value=self.voice_label.get())
        box = ttk.Combobox(win, textvariable=choice, values=list(VOICES.keys()), state="readonly", width=34)
        box.pack(padx=18, pady=6)
        def save():
            self.voice_label.set(choice.get())
            self._persist_preferences()
            win.destroy()
        ttk.Button(win, text="Guardar", style="Accent.TButton", command=save).pack(fill="x", padx=18, pady=18)

    def _choose_music(self):
        path = filedialog.askopenfilename(parent=self.root, title="Elegir música de fondo",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.ogg"), ("Todos", "*.*")])
        if path:
            self.music_var.set(path)
            self.music_name.set(Path(path).name)
            self._persist_preferences()

    def _choose_output(self):
        path = filedialog.askdirectory(parent=self.root, title="Carpeta donde guardar los Shorts")
        if path:
            self.output_var.set(path)
            self._persist_preferences()

    def _persist_preferences(self):
        settings = load_settings()
        settings.update({"voice": self._voice_id(), "music_path": self.music_var.get(),
                         "output_dir": self.output_var.get()})
        save_settings(settings)
        self.music_name.set(Path(self.music_var.get()).name if self.music_var.get() else "Sin música seleccionada")
        self.status.set("Preferencias guardadas.")

    def _set_busy(self, busy: bool):
        self.create_btn.configure(state="disabled" if busy else "normal")
        self.cancel_btn.configure(state="normal" if busy else "disabled")

    def _create(self):
        if self._is_running or self._prepared is not None:
            return
        script = self.script.get("1.0", "end-1c").strip()
        if not script:
            messagebox.showwarning("Falta la historia", "Pega o escribe una historia antes de crear el Short.")
            self.script.focus_set()
            return
        key = get_pixabay_key()
        if not key:
            messagebox.showinfo("Configuración inicial",
                "Configura la clave de Pixabay en Preferencias o define PIXABAY_API_KEY.")
            self._set_api_key()
            key = get_pixabay_key()
            if not key:
                return
        title = self.title_var.get().strip() or suggest_title(script)
        self.title_var.set(title)
        self._persist_preferences()
        output_dir = Path(self.output_var.get()).expanduser()
        if not output_dir.is_absolute():
            output_dir = self.data_dir / output_dir
        episode = Episode(title=title, script=script, voice=self._voice_id(),
            music_path=self.music_var.get() or None, output_dir=output_dir)
        self._cancel_event = threading.Event()
        self._is_running = True
        self._set_busy(True)
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=max(1, len(episode.scene_list()) * 2), value=0)
        self.status.set("Preparando clips y narración para revisar…")

        def report(message, current=0, total=1, stage="prepare"):
            self.root.after(0, lambda: self._production_progress(message, current, total, stage))

        def worker():
            try:
                prepared = prepare_episode(episode, key, self.project_dir, report,
                    data_dir=self.data_dir, cancel_event=self._cancel_event)
                self.root.after(0, lambda p=prepared: self._preparation_ready(p))
            except (ProductionCancelled, InterruptedError):
                self.root.after(0, self._production_cancelled)
            except Exception as exc:
                logging.getLogger(__name__).exception("Falló la preparación del Short.")
                self.root.after(0, lambda error=str(exc): self._failed(error))
        threading.Thread(target=worker, daemon=True, name="olv-prepare").start()

    def _production_progress(self, message: str, current: int, total: int, stage: str):
        if not self._is_running:
            return
        if stage in {"search", "voice"}:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=max(1, total * 2))
            self.progress["value"] = current * 2 + (1 if stage == "voice" else 0)
        elif stage == "render":
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        self.status.set(message)

    def _preparation_ready(self, prepared: PreparedProduction):
        self.progress.stop()
        self._is_running = False
        self._prepared = prepared
        self._set_busy(False)
        if self._close_when_done:
            self._prepared = None
            self._autosave()
            self.root.destroy()
            return
        self.status.set(f"{len(prepared.scenes)} escenas preparadas. Revisa los clips antes del montaje.")
        try:
            self._show_review(prepared)
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo abrir la revisión de escenas.")
            self._prepared = None
            messagebox.showerror("No se pudo abrir la revisión", str(exc))

    def _show_review(self, prepared: PreparedProduction):
        from tkinter import Toplevel
        win = Toplevel(self.root)
        win.title("Revisión de escenas · OLV")
        win.configure(bg=BG)
        win.transient(self.root)
        win.geometry("850x560")
        win.minsize(680, 440)
        win.grab_set()
        ttk.Label(win, text="REVISIÓN PREVIA AL MONTAJE", style="Hero.TLabel").pack(
            anchor="w", padx=20, pady=(18, 4))
        ttk.Label(win, text="Comprueba el orden y los clips antes de generar el MP4.",
                  style="Muted.TLabel").pack(anchor="w", padx=20, pady=(0, 14))
        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, style="Panel.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(left, text="ESCENAS", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        tree = ttk.Treeview(left, show="tree", selectmode="browse")
        tree.pack(fill="both", expand=True)
        for index, scene in enumerate(prepared.scenes):
            tree.insert("", "end", iid=str(index), text=f"{index+1:02d} · {scene.text[:34]}")
        if prepared.scenes:
            tree.selection_set("0")
        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="TEXTO Y FUENTE", style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        editor = tk.Text(right, wrap="word", bg="#10151b", fg=TEXT, insertbackground=RED_LIGHT,
                         relief="flat", padx=12, pady=10, height=8)
        editor.grid(row=1, column=0, sticky="nsew")
        source_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=source_var, style="PanelMuted.TLabel",
                  wraplength=430).grid(row=2, column=0, sticky="w", pady=(10, 8))
        selected = {"index": 0}

        def commit_editor():
            index = selected["index"]
            value = editor.get("1.0", "end-1c").strip()
            if value:
                prepared.scenes[index].text = value
                tree.item(str(index), text=f"{index+1:02d} · {value[:34]}")

        def select_scene(_event=None):
            selection = tree.selection()
            if not selection:
                return
            if 0 <= selected["index"] < len(prepared.scenes):
                commit_editor()
            index = int(selection[0])
            selected["index"] = index
            scene = prepared.scenes[index]
            editor.delete("1.0", "end")
            editor.insert("1.0", scene.text)
            source_var.set(f"Clip: {scene.video.name}\nFuente: {scene.source.get('creator', 'Pixabay')} · {scene.source.get('page_url', '')}")

        tree.bind("<<TreeviewSelect>>", select_scene)
        select_scene()
        controls = ttk.Frame(right, style="Panel.TFrame")
        controls.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        def move_scene(offset):
            commit_editor()
            index = selected["index"]
            target = index + offset
            if not 0 <= target < len(prepared.scenes):
                return
            prepared.scenes[index], prepared.scenes[target] = prepared.scenes[target], prepared.scenes[index]
            tree.delete(*tree.get_children())
            for pos, scene in enumerate(prepared.scenes):
                tree.insert("", "end", iid=str(pos), text=f"{pos+1:02d} · {scene.text[:34]}")
            selected["index"] = target
            tree.selection_set(str(target))
            scene = prepared.scenes[target]
            editor.delete("1.0", "end")
            editor.insert("1.0", scene.text)
            source_var.set(f"Clip: {scene.video.name}\nFuente: {scene.source.get('creator', 'Pixabay')} · {scene.source.get('page_url', '')}")

        ttk.Button(controls, text="↑ Subir", command=lambda: move_scene(-1)).pack(side="left")
        ttk.Button(controls, text="↓ Bajar", command=lambda: move_scene(1)).pack(side="left", padx=6)
        ttk.Button(controls, text="▶ Ver clip",
                   command=lambda: (commit_editor(), self._open_media(prepared.scenes[selected["index"]].video))).pack(side="left", padx=6)

        footer = ttk.Frame(win)
        footer.pack(fill="x", padx=20, pady=(0, 18))

        def cancel_review():
            self._prepared = None
            self.status.set("Revisión cancelada. No se ha renderizado ningún vídeo.")
            win.destroy()

        def render_now():
            commit_editor()
            win.destroy()
            self._render_prepared(prepared)

        ttk.Button(footer, text="Cancelar", style="Secondary.TButton",
                   command=cancel_review).pack(side="right")
        ttk.Button(footer, text="✓  GENERAR VÍDEO", style="Accent.TButton",
                   command=render_now).pack(side="right", padx=(0, 8))
        win.protocol("WM_DELETE_WINDOW", cancel_review)

    def _open_media(self, path: Path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("No se pudo abrir el clip", str(exc), parent=self.root)

    def _render_prepared(self, prepared: PreparedProduction):
        self._cancel_event = threading.Event()
        self._is_running = True
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.status.set("Montando el vídeo final…")

        def report(message, current=0, total=1, stage="render"):
            self.root.after(0, lambda: self._production_progress(message, current, total, stage))

        def worker():
            try:
                output = render_prepared(prepared, report, self._cancel_event)
                self.root.after(0, lambda p=output: self._finished(p))
            except (ProductionCancelled, InterruptedError):
                self.root.after(0, self._production_cancelled)
            except Exception as exc:
                logging.getLogger(__name__).exception("Falló el renderizado final.")
                self.root.after(0, lambda error=str(exc): self._failed(error))
        threading.Thread(target=worker, daemon=True, name="olv-render").start()

    def _cancel_production(self):
        if self._is_running:
            self._cancel_event.set()
            self.status.set("Solicitando cancelación…")
            self.cancel_btn.configure(state="disabled")
        elif self._prepared is not None:
            self._prepared = None
            self.status.set("Preparación descartada.")
            self._set_busy(False)

    def _production_cancelled(self):
        self.progress.stop()
        self._is_running = False
        self._prepared = None
        self._set_busy(False)
        self.status.set("Producción cancelada. Los temporales se conservan para diagnóstico.")
        if self._close_when_done:
            self._autosave()
            self.root.destroy()

    def _finished(self, output: Path):
        self.progress.stop()
        self._is_running = False
        self._set_busy(False)
        self._prepared = None
        self.last_output = output
        self.status.set(f"Short terminado: {output.name}")
        if self._close_when_done:
            self._autosave()
            self.root.destroy()
            return
        if messagebox.askyesno("Short terminado",
            f"El vídeo está listo para revisar:\\n\\n{output.resolve()}\\n\\n¿Quieres abrir la carpeta ahora?"):
            self._open_folder(output.parent)

    def _failed(self, error: str):
        self.progress.stop()
        self._is_running = False
        self._set_busy(False)
        self._prepared = None
        self.status.set("La producción se ha detenido. Revisa el mensaje.")
        if self._close_when_done:
            self._autosave()
            self.root.destroy()
            return
        messagebox.showerror("No se pudo crear el Short", error)

    def _open_output(self):
        folder = Path(self.output_var.get()).expanduser()
        if not folder.is_absolute():
            folder = self.data_dir / folder
        folder.mkdir(parents=True, exist_ok=True)
        self._open_folder(folder)

    def _open_folder(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc))

    def _open_logs(self):
        self._open_folder(self.data_dir / "logs")

    def _check_requirements(self):
        from .runtime import find_tool
        missing = [tool for tool in ("ffmpeg", "ffprobe") if not find_tool(tool)]
        if missing:
            messagebox.showwarning("Faltan requisitos",
                "No se encuentran: " + ", ".join(missing) + "\\nInstala FFmpeg y asegúrate de que está en PATH.")
        else:
            messagebox.showinfo("Requisitos correctos", "FFmpeg y FFprobe están disponibles.")

    def _open_license(self):
        import webbrowser
        webbrowser.open("https://www.gnu.org/licenses/agpl-3.0.html")

    def _about(self):
        messagebox.showinfo("Acerca de OLV",
            "OLV · Tu imaginación en vida.\n\n"
            "Software libre bajo GNU AGPL-3.0-or-later.\n"
            "Puedes usar, estudiar, modificar y redistribuir el programa respetando la licencia.\n"
            "Se distribuye sin garantía, en la medida permitida por la ley.\n"
            "La publicación de vídeos siempre es manual.")

    def _on_close(self):
        if self._is_running:
            if not messagebox.askyesno("Producción en curso",
                "La producción sigue en marcha. ¿Quieres cancelarla y cerrar OLV cuando termine de detenerse?"):
                return
            self._close_when_done = True
            self._cancel_event.set()
            self.cancel_btn.configure(state="disabled")
            self.status.set("Cerrando OLV cuando termine la cancelación segura…")
            return
        self._autosave()
        self.root.destroy()


def launch():
    configure_logging()
    logging.getLogger(__name__).info("Iniciando OLV.")
    root = tk.Tk()
    try:
        ShortsFactoryApp(root)
        root.mainloop()
    except Exception:
        logging.getLogger(__name__).exception("Error fatal al iniciar OLV.")
        raise
