#!/usr/bin/env python3
"""Simple Tkinter GUI to orchestrate the AI Influencer pipeline steps.

This interface exposes the most common parameters of the command line
scripts under ``scripts/`` so that less technical users can run the
pipeline without memorising every flag.  Each action still calls the
underlying Python module (or shell script) so it behaves exactly like
its CLI counterpart.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ai_influencer.scripts.openrouter_models import MODEL_PRESETS, resolve_model_alias

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


class PipelineGUI:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AI Influencer Pipeline")
        self.root.geometry("960x720")

        self.queue: "queue.Queue[str]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.process: subprocess.Popen[str] | None = None
        self.run_buttons: list[tk.Widget] = []

        self.api_key_var = tk.StringVar(value=os.getenv("OPENROUTER_API_KEY", ""))

        self._build_ui()
        self._log("Benvenuto! Configura i percorsi e lancia i passaggi desiderati.")

    # ------------------------------------------------------------------
    # UI helpers
    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        canvas = tk.Canvas(main, borderwidth=0)
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_api_section(scroll_frame)
        self._build_prepare_section(scroll_frame)
        self._build_text_section(scroll_frame)
        self._build_image_section(scroll_frame)
        self._build_qc_section(scroll_frame)
        self._build_augment_section(scroll_frame)
        self._build_console(main)

    def _build_api_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Credenziali OpenRouter", padding=12)
        frame.pack(fill="x", pady=6)

        ttk.Label(frame, text="OPENROUTER_API_KEY:").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.api_key_var, width=70, show="*")
        entry.grid(row=0, column=1, sticky="ew", padx=6)
        frame.columnconfigure(1, weight=1)
        ttk.Label(
            frame,
            text="La chiave viene usata solo per le chiamate API e non viene salvata.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_prepare_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="1) Preparazione dataset", padding=12)
        frame.pack(fill="x", pady=6)

        self.raw_dir_var = tk.StringVar(value=str(Path("data/input_raw")))
        self.cleaned_dir_var = tk.StringVar(value=str(Path("data/cleaned")))
        self.rembg_var = tk.BooleanVar(value=True)
        self.facecrop_var = tk.BooleanVar(value=True)

        self._add_path_row(frame, "Input", self.raw_dir_var, 0, is_dir=True)
        self._add_path_row(frame, "Output", self.cleaned_dir_var, 1, is_dir=True)

        ttk.Checkbutton(frame, text="Applica remove.bg", variable=self.rembg_var).grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Checkbutton(frame, text="Crop del volto", variable=self.facecrop_var).grid(
            row=2, column=1, sticky="w", pady=(6, 0)
        )

        btn = ttk.Button(frame, text="Esegui preparazione", command=self.run_prepare)
        btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
        self._register_button(btn)

    def _build_text_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="2) Storyboard & Script (OpenRouter Testo)", padding=12)
        frame.pack(fill="x", pady=6)

        self.prompt_bank_var = tk.StringVar(value=str(ROOT / "prompt_bank.yaml"))
        self.text_out_var = tk.StringVar(value=str(Path("data/text/storyboard.json")))
        self.text_model_var = tk.StringVar(value="meta-llama/llama-3.1-70b-instruct")

        self._add_path_row(frame, "Prompt bank", self.prompt_bank_var, 0, is_dir=False)
        self._add_path_row(frame, "Output JSON", self.text_out_var, 1, is_dir=False)

        ttk.Label(frame, text="Modello").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.text_model_var).grid(
            row=2, column=1, sticky="ew", pady=(6, 0)
        )

        btn = ttk.Button(frame, text="Genera storyboard", command=self.run_text)
        btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
        self._register_button(btn)

    def _build_image_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="3) Generazione immagini (OpenRouter)", padding=12)
        frame.pack(fill="x", pady=6)

        self.image_out_var = tk.StringVar(value=str(Path("data/synth_openrouter")))
        self.image_model_var = tk.StringVar(value="sdxl")
        self.image_size_var = tk.StringVar(value="1024x1024")
        self.image_per_scene_var = tk.IntVar(value=12)
        self.image_sleep_var = tk.DoubleVar(value=3.0)

        self._add_path_row(frame, "Prompt bank", self.prompt_bank_var, 0, is_dir=False)
        self._add_path_row(frame, "Output dir", self.image_out_var, 1, is_dir=True)

        ttk.Label(frame, text="Modello").grid(row=2, column=0, sticky="w", pady=(6, 0))
        model_values = [alias for alias in MODEL_PRESETS.keys()]
        ttk.Combobox(
            frame,
            textvariable=self.image_model_var,
            values=model_values,
            state="normal",
        ).grid(row=2, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(
            frame,
            text="Preset disponibili: " + ", ".join(
                f"{alias} → {model}" for alias, model in MODEL_PRESETS.items()
            ),
            wraplength=520,
            foreground="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(frame, text="Risoluzione").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.image_size_var).grid(
            row=4, column=1, sticky="ew", pady=(6, 0)
        )

        ttk.Label(frame, text="Img per scena").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.image_per_scene_var).grid(
            row=5, column=1, sticky="ew", pady=(6, 0)
        )

        ttk.Label(frame, text="Pausa tra richieste (s)").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.image_sleep_var).grid(
            row=6, column=1, sticky="ew", pady=(6, 0)
        )

        btn = ttk.Button(frame, text="Genera immagini", command=self.run_images)
        btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=8)
        self._register_button(btn)

    def _build_qc_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="4) Quality Check", padding=12)
        frame.pack(fill="x", pady=6)

        self.qc_ref_var = tk.StringVar(value=str(Path("data/cleaned")))
        self.qc_cand_var = tk.StringVar(value=str(Path("data/synth_openrouter")))
        self.qc_out_var = tk.StringVar(value=str(Path("data/qc_passed")))
        self.qc_minsim_var = tk.DoubleVar(value=0.34)
        self.qc_minblur_var = tk.DoubleVar(value=80.0)

        self._add_path_row(frame, "Riferimento", self.qc_ref_var, 0, is_dir=True)
        self._add_path_row(frame, "Candidati", self.qc_cand_var, 1, is_dir=True)
        self._add_path_row(frame, "Output", self.qc_out_var, 2, is_dir=True)

        ttk.Label(frame, text="Soglia similarità").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.qc_minsim_var).grid(
            row=3, column=1, sticky="ew", pady=(6, 0)
        )

        ttk.Label(frame, text="Soglia nitidezza").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.qc_minblur_var).grid(
            row=4, column=1, sticky="ew", pady=(6, 0)
        )

        btn = ttk.Button(frame, text="Esegui QC", command=self.run_qc)
        btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
        self._register_button(btn)

    def _build_augment_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="5) Augment & Caption", padding=12)
        frame.pack(fill="x", pady=6)

        self.aug_in_var = tk.StringVar(value=str(Path("data/qc_passed")))
        self.aug_out_var = tk.StringVar(value=str(Path("data/augment")))
        self.aug_cap_var = tk.StringVar(value=str(Path("data/captions")))
        self.aug_num_var = tk.IntVar(value=1)
        self.aug_meta_var = tk.StringVar(value=str(Path("data/synth_openrouter/manifest.json")))

        self._add_path_row(frame, "Input", self.aug_in_var, 0, is_dir=True)
        self._add_path_row(frame, "Output", self.aug_out_var, 1, is_dir=True)
        self._add_path_row(frame, "Captions", self.aug_cap_var, 2, is_dir=True)
        self._add_path_row(frame, "Metadata", self.aug_meta_var, 3, is_dir=False)

        ttk.Label(frame, text="Augment per immagine").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.aug_num_var).grid(
            row=4, column=1, sticky="ew", pady=(6, 0)
        )

        btn = ttk.Button(frame, text="Esegui augment", command=self.run_augment)
        btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
        self._register_button(btn)

    def _build_console(self, parent: ttk.Frame) -> None:
        console_frame = ttk.Frame(parent)
        console_frame.pack(fill="both", expand=True, pady=(12, 0))

        toolbar = ttk.Frame(console_frame)
        toolbar.pack(fill="x", pady=(0, 4))

        stop_btn = ttk.Button(toolbar, text="Interrompi", command=self.stop_process, state="disabled")
        stop_btn.pack(side="left")
        self.stop_button = stop_btn

        clear_btn = ttk.Button(toolbar, text="Pulisci log", command=lambda: self._set_console(""))
        clear_btn.pack(side="left", padx=(6, 0))

        text = tk.Text(console_frame, height=12, wrap="word", state="disabled", bg="#111", fg="#eee")
        text.pack(fill="both", expand=True)
        self.console = text

    def _add_path_row(
        self,
        frame: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        *,
        is_dir: bool,
    ) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(0, 4))
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=(0, 4))
        frame.columnconfigure(1, weight=1)

        def browse() -> None:
            if is_dir:
                path = filedialog.askdirectory(initialdir=variable.get() or ".")
            else:
                path = filedialog.askopenfilename(initialdir=ROOT, filetypes=[("Tutti i file", "*.*")])
            if path:
                variable.set(path)

        ttk.Button(frame, text="Sfoglia", command=browse).grid(row=row, column=2, padx=(6, 0), pady=(0, 4))

    def _register_button(self, button: tk.Widget) -> None:
        self.run_buttons.append(button)

    def _set_console(self, text: str) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.insert(tk.END, text)
        self.console.configure(state="disabled")

    def _log(self, message: str) -> None:
        if not message.endswith("\n"):
            message += "\n"
        self.console.configure(state="normal")
        self.console.insert(tk.END, message)
        self.console.see(tk.END)
        self.console.configure(state="disabled")

    # ------------------------------------------------------------------
    # Command execution
    def _run_command(self, label: str, args: list[str], *, extra_env: dict[str, str] | None = None) -> None:
        if self.worker is not None:
            messagebox.showwarning("In esecuzione", "Attendi che il processo corrente termini.")
            return

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        self._log(f"[{label}] Avvio comando: {' '.join(args)}")
        self._set_running(True)

        def worker() -> None:
            try:
                self.process = subprocess.Popen(
                    args,
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )
            except FileNotFoundError as exc:
                self.queue.put(f"Errore: {exc}\n")
                self.queue.put("__DONE__")
                return

            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.queue.put(line)
            ret = self.process.wait()
            self.queue.put(f"[{label}] Terminato con codice {ret}\n")
            self.queue.put("__DONE__")

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.root.after(100, self._poll_queue)

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg == "__DONE__":
                    self.worker = None
                    self.process = None
                    self._set_running(False)
                else:
                    self._log(msg.rstrip("\n"))
        except queue.Empty:
            pass

        if self.worker is not None:
            self.root.after(100, self._poll_queue)

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for btn in self.run_buttons:
            btn.configure(state=state)
        self.stop_button.configure(state="normal" if running else "disabled")

    def stop_process(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._log("Richiesta terminazione processo...")
        else:
            messagebox.showinfo("Nessun processo", "Non ci sono processi in esecuzione.")

    # ------------------------------------------------------------------
    # Actions for each step
    def run_prepare(self) -> None:
        inp = self.raw_dir_var.get().strip()
        out = self.cleaned_dir_var.get().strip()
        if not inp or not out:
            messagebox.showerror("Parametri mancanti", "Specifica cartelle input e output.")
            return
        args = [
            PYTHON,
            str(ROOT / "prepare_dataset.py"),
            "--in",
            inp,
            "--out",
            out,
        ]
        if self.rembg_var.get():
            args.append("--do_rembg")
        if self.facecrop_var.get():
            args.append("--do_facecrop")
        self._run_command("prepare_dataset", args)

    def run_text(self) -> None:
        prompt = self.prompt_bank_var.get().strip()
        out = self.text_out_var.get().strip()
        if not prompt or not out:
            messagebox.showerror("Parametri mancanti", "Specifica prompt bank e file di output.")
            return
        env = {"OPENROUTER_API_KEY": self.api_key_var.get().strip()}
        args = [
            PYTHON,
            str(ROOT / "openrouter_text.py"),
            "--prompt_bank",
            prompt,
            "--out",
            out,
            "--model",
            self.text_model_var.get().strip() or "meta-llama/llama-3.1-70b-instruct",
        ]
        self._run_command("openrouter_text", args, extra_env=env)

    def run_images(self) -> None:
        prompt = self.prompt_bank_var.get().strip()
        out = self.image_out_var.get().strip()
        if not prompt or not out:
            messagebox.showerror("Parametri mancanti", "Specifica prompt bank e cartella di output.")
            return
        env = {"OPENROUTER_API_KEY": self.api_key_var.get().strip()}
        args = [
            PYTHON,
            str(ROOT / "openrouter_images.py"),
            "--prompt_bank",
            prompt,
            "--out",
            out,
            "--model",
            resolve_model_alias(self.image_model_var.get().strip() or "sdxl"),
            "--size",
            self.image_size_var.get().strip() or "1024x1024",
            "--per_scene",
            str(max(1, self.image_per_scene_var.get())),
            "--sleep",
            str(max(0.0, self.image_sleep_var.get())),
        ]
        self._run_command("openrouter_images", args, extra_env=env)

    def run_qc(self) -> None:
        ref = self.qc_ref_var.get().strip()
        cand = self.qc_cand_var.get().strip()
        out = self.qc_out_var.get().strip()
        if not ref or not cand or not out:
            messagebox.showerror("Parametri mancanti", "Completa i percorsi richiesti.")
            return
        args = [
            PYTHON,
            str(ROOT / "qc_face_sim.py"),
            "--ref",
            ref,
            "--cand",
            cand,
            "--out",
            out,
            "--minsim",
            str(self.qc_minsim_var.get()),
            "--minblur",
            str(self.qc_minblur_var.get()),
        ]
        self._run_command("qc_face_sim", args)

    def run_augment(self) -> None:
        inp = self.aug_in_var.get().strip()
        out = self.aug_out_var.get().strip()
        cap = self.aug_cap_var.get().strip()
        meta = self.aug_meta_var.get().strip()
        if not inp or not out or not cap:
            messagebox.showerror("Parametri mancanti", "Specifica input, output e cartella captions.")
            return
        args = [
            PYTHON,
            str(ROOT / "augment_and_caption.py"),
            "--in",
            inp,
            "--out",
            out,
            "--captions",
            cap,
            "--num_aug",
            str(max(0, self.aug_num_var.get())),
        ]
        if meta:
            args.extend(["--meta", meta])
        self._run_command("augment_and_caption", args)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    PipelineGUI().run()


if __name__ == "__main__":
    main()
