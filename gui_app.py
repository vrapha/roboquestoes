import sys
import os
import time

# =============================================================================
# DEBUG: DETECT RECURSIVE LAUNCH
# =============================================================================
if __name__ == "__main__":
    with open("process_log.txt", "a") as f:
        f.write(f"{time.ctime()} - PID {os.getpid()} - ARGV: {sys.argv}\n")

import sys




import io
import csv
import threading
import traceback
import subprocess
import multiprocessing
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from playwright.sync_api import sync_playwright


if sys.platform.startswith("win"):
    multiprocessing.freeze_support()


def app_root() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return app_root()


APP_ROOT = app_root()
ROOT = project_root()

try:
    os.chdir(ROOT)
except Exception:
    pass

DEBUG_DIR = ROOT / "debug"
INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"


def ensure_dirs() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


ensure_dirs()


def _setup_crash_log() -> Path:
    log_path = DEBUG_DIR / "crash.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def excepthook(exc_type, exc_value, exc_tb):
        import traceback as _tb
        error_text = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n\n=== CRASH {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(error_text)
        try:
            messagebox.showerror("Erro Fatal", f"Erro:\n\n{exc_value}\n\nVeja: {log_path}")
        except Exception:
            print(error_text)

    sys.excepthook = excepthook
    return log_path


CRASH_LOG_PATH = _setup_crash_log()


def find_scripts_dir() -> Path:
    candidates = [
        ROOT / "scripts",
        ROOT / "_internal" / "scripts",
        APP_ROOT / "scripts",
        APP_ROOT / "_internal" / "scripts",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return ROOT / "scripts"


SCRIPTS_DIR = find_scripts_dir()


def get_playwright_browser_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", ".")) / "RoboQuestoes" / "ms-playwright"


def ensure_playwright_browsers() -> None:
    browser_dir = get_playwright_browser_dir()
    browser_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_dir)

    # Check for both chromium and firefox
    has_chromium = any(browser_dir.glob("chromium-*"))
    has_firefox = any(browser_dir.glob("firefox-*"))

    if has_chromium and has_firefox:
        print(f"[DEBUG] Browsers já existem em: {browser_dir}")
        return

    print(f"[DEBUG] Browsers não encontrados em {browser_dir}. Instalando...")
    log_file = DEBUG_DIR / "playwright_install.log"
    
    if getattr(sys, "frozen", False):
        import contextlib
        from playwright.__main__ import main as playwright_main

        with log_file.open("w", encoding="utf-8") as f:
            f.write("=== Instalando Browsers (In-Process Frozen) ===\n")
            
            old_argv = sys.argv
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            # Install both chromium and firefox
            sys.argv = ["playwright", "install", "chromium", "firefox"]
            sys.stdout = f
            sys.stderr = f
            
            # Intercepta sys.exit para não fechar o app se o install der exit(0) ou (1)
            try:
                # Patch sys.exit to avoid killing the GUI app
                def safe_exit(code=0):
                    if code != 0:
                        raise RuntimeError(f"Playwright install failed with code {code}")
                
                original_exit = sys.exit
                sys.exit = safe_exit
                
                print("Iniciando playwright install chromium firefox...")
                playwright_main()
                print("Finalizado install.")
                
            except Exception as e:
                print(f"Erro durante install: {e}")
                f.write(f"\nERRO FATAL: {e}\n")
                # Se falhar, talvez queiramos subir erro ou tentar continuar
            finally:
                # Restaura tudo
                sys.argv = old_argv
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                sys.exit = original_exit

    else:
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW

        with log_file.open("w", encoding="utf-8") as f:
            f.write("=== Instalando Browsers (Subprocess) ===\n")
            f.flush()
            p = subprocess.Popen(
                [sys.executable, "-m", "playwright", "install", "chromium", "firefox"],
                stdout=f,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            rc = p.wait()

    if any(browser_dir.glob("chromium-*")) and any(browser_dir.glob("firefox-*")):
        print("[DEBUG] Browsers instalados com sucesso.")
        return
    
    # raise RuntimeError(f"Falha ao instalar Browsers. Veja detalhes em: {log_file}")


def _add_dll_dir(path: Path) -> None:
    if not path.exists():
        return
    try:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(path))
    except Exception:
        pass
    os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")


def setup_runtime_env() -> None:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(APP_ROOT))
    if SCRIPTS_DIR.exists():
        sys.path.insert(0, str(SCRIPTS_DIR))
        if SCRIPTS_DIR.parent.exists():
            sys.path.insert(0, str(SCRIPTS_DIR.parent))

    _add_dll_dir(APP_ROOT)
    _add_dll_dir(ROOT / "_internal")
    for libs_name in ("numpy.libs", "pandas.libs"):
        _add_dll_dir(APP_ROOT / libs_name)
        _add_dll_dir((ROOT / "_internal") / libs_name)

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(get_playwright_browser_dir())


setup_runtime_env()


# Importa os scripts
try:
    from scripts import robo_pdf_para_codigos as extractor
    from scripts import post_codes_to_sheets as poster
except Exception:
    try:
        import robo_pdf_para_codigos as extractor
        import post_codes_to_sheets as poster
    except Exception as e:
        extractor = None
        poster = None
        print(f"⚠️ Aviso: {e}")


class _TkLogWriter(io.TextIOBase):
    def __init__(self, push: Callable[[str], None]):
        super().__init__()
        self._push = push

    def write(self, s: str) -> int:
        if not s:
            return 0
        self._push(s)
        return len(s)

    def flush(self) -> None:
        return


@dataclass
class RunState:
    pdf_path: Optional[str] = None
    target_cell: str = "E75"
    codes: list[str] | None = None


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_dirs()

        self.title("Robo Questões v3.4 (Firefox Login)")
        self.geometry("1000x700")
        self.minsize(900, 600)

        self.state_data = RunState()
        self._log_queue: Queue[str] = Queue()
        self._busy = False
        self._busy_lock = threading.Lock()

        self._build_ui()
        self.after(80, self._drain_log_queue)

    def _build_ui(self) -> None:
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            input_frame, text="Configurações",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))

        pdf_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        pdf_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(pdf_row, text="PDF:").pack(side="left")

        self.pdf_var = ctk.StringVar(value="(Nenhum)")
        self.pdf_entry = ctk.CTkEntry(pdf_row, textvariable=self.pdf_var, state="readonly", width=400)
        self.pdf_entry.pack(side="left", padx=10, fill="x", expand=True)

        self.btn_pick_pdf = ctk.CTkButton(pdf_row, text="Selecionar", command=self.on_pick_pdf, width=120)
        self.btn_pick_pdf.pack(side="right")

        cell_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        cell_row.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(cell_row, text="Célula:").pack(side="left")
        self.cell_var = ctk.StringVar(value="E75")
        ctk.CTkEntry(cell_row, textvariable=self.cell_var, width=100).pack(side="left", padx=10)

        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill="x", padx=20, pady=10)

        # Adicionar Checkbox para Headless
        self.var_show_browser = ctk.BooleanVar(value=True)
        self.chk_browser = ctk.CTkCheckBox(
            action_frame, text="Ver Navegador (Extração)", variable=self.var_show_browser,
            font=ctk.CTkFont(size=12)
        )
        self.chk_browser.pack(side="top", pady=5)

        btn_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_container.pack(pady=5)

        self.btn_extract = ctk.CTkButton(
            btn_container, text="▶ Iniciar", height=45, width=220,
            command=self.on_run_extract, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_extract.pack(side="left", padx=10)

        self.btn_send = ctk.CTkButton(
            btn_container, text="Enviar 📤", height=45, width=220, state="disabled",
            command=self.on_send, fg_color="green", hover_color="darkgreen",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_send.pack(side="left", padx=10)

        login_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        login_frame.pack(fill="x", padx=15, pady=(0, 10))

        login_label_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        login_label_frame.pack(anchor="center")

        ctk.CTkLabel(login_label_frame, text="Login:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 10))

        self.btn_reset = ctk.CTkButton(
            login_label_frame, text="🔓 Destravar", command=self.on_force_reset,
            width=100, height=20, fg_color="red", hover_color="darkred",
            font=ctk.CTkFont(size=10)
        )
        self.btn_reset.pack(side="left")

        auth_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        auth_frame.pack(pady=5)

        self.btn_login_site = ctk.CTkButton(auth_frame, text="Site", command=self.on_login_site, width=120, fg_color="gray", hover_color="gray30")
        self.btn_login_site.pack(side="left", padx=5)

        self.btn_login_google = ctk.CTkButton(auth_frame, text="Google", command=self.on_login_google, width=120, fg_color="gray", hover_color="gray30")
        self.btn_login_google.pack(side="left", padx=5)

        output_frame = ctk.CTkFrame(self, fg_color="transparent")
        output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        output_frame.grid_columnconfigure(0, weight=1, uniform="g")
        output_frame.grid_columnconfigure(1, weight=1, uniform="g")
        output_frame.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(output_frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(left, text="Códigos", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")
        self.codes_text = ctk.CTkTextbox(left, wrap="none", font=("Consolas", 12))
        self.codes_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.codes_text.configure(state="disabled")

        right = ctk.CTkFrame(output_frame)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(right, text="Console", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")
        self.log_text = ctk.CTkTextbox(right, wrap="word", font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        footer = ctk.CTkFrame(self, height=40, corner_radius=0)
        footer.pack(fill="x", side="bottom")

        self.status_var = ctk.StringVar(value="Pronto.")
        self.lbl_status = ctk.CTkLabel(footer, textvariable=self.status_var, anchor="w", padx=20)
        self.lbl_status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            footer, text="Outputs 📂", command=self.on_open_outputs, width=120, height=30,
            fg_color="transparent", border_width=1, border_color="gray"
        ).pack(side="right", padx=10, pady=5)

    def on_force_reset(self) -> None:
        with self._busy_lock:
            old_state = self._busy
            self._busy = False
        self._set_busy(False)
        self.status_var.set(f"🔓 Destravado (era: {old_state}).")
        print(f"\n🔓 Estado BUSY resetado: {old_state} -> False\n")

    def _push_log(self, s: str) -> None:
        self._log_queue.put(s)

    def _drain_log_queue(self) -> None:
        i = 0
        try:
            while i < 100:
                s = self._log_queue.get_nowait()
                self._append_log(s)
                i += 1
        except Empty:
            pass
        self.after(80, self._drain_log_queue)

    def _append_log(self, s: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", s)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_codes(self, codes: list[str]) -> None:
        self.codes_text.configure(state="normal")
        self.codes_text.delete("1.0", "end")
        self.codes_text.insert("end", "\n".join(codes))
        self.codes_text.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        with self._busy_lock:
            self._busy = busy

        print(f"[DEBUG] _set_busy({busy}) -> Dispatching UI update to main thread")
        # GARANTE que a atualização de widgets ocorra na Main Thread
        self.after(0, lambda: self._update_ui_state(busy))

    def _update_ui_state(self, busy: bool) -> None:
        try:
            print(f"[DEBUG] _update_ui_state(busy={busy}) running on Main Thread")
            state = "disabled" if busy else "normal"
            cursor = "watch" if busy else ""
            color = "yellow" if busy else ("white" if ctk.get_appearance_mode() == "Dark" else "black")

            self.btn_extract.configure(state=state)
            self.btn_login_site.configure(state=state)
            self.btn_login_google.configure(state=state)
            self.btn_pick_pdf.configure(state=state)

            if (not busy) and self.state_data.codes:
                self.btn_send.configure(state="normal")
            else:
                self.btn_send.configure(state="disabled")

            self.lbl_status.configure(text_color=color)
            self.configure(cursor=cursor)
            
            # Force update idle tasks to ensure UI refreshes immediately
            self.update_idletasks()
            print("[DEBUG] _update_ui_state completed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to update UI state: {e}")
            traceback.print_exc()
            messagebox.showerror("UI Error", f"Falha ao atualizar interface:\n{e}")

    def on_pick_pdf(self) -> None:
        print("[DEBUG] on_pick_pdf chamado")
        p = filedialog.askopenfilename(title="PDF", filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not p:
            print("[DEBUG] Nenhum PDF selecionado")
            return
        self.state_data.pdf_path = p
        self.pdf_var.set(p)
        self.status_var.set("PDF OK.")
        print(f"[DEBUG] PDF selecionado: {p}")

    def on_open_outputs(self) -> None:
        print("[DEBUG] on_open_outputs chamado")
        try:
            if sys.platform.startswith("win"):
                os.startfile(OUTPUTS_DIR)
            else:
                os.system(f'xdg-open "{OUTPUTS_DIR}"')
        except Exception:
            messagebox.showinfo("Outputs", f"{OUTPUTS_DIR}")

    def on_run_extract(self) -> None:
        print("[DEBUG] on_run_extract INICIADO")

        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.\nClique em 🔓 Destravar se travou")
                return

        if not self.state_data.pdf_path:
            messagebox.showwarning("PDF", "Selecione um PDF.")
            return

        state_path = DEBUG_DIR / "storage_state.json"
        print(f"[DEBUG] Verificando storage_state: {state_path}")
        print(f"[DEBUG] Existe: {state_path.exists()}")
        if state_path.exists():
            print(f"[DEBUG] Tamanho: {state_path.stat().st_size} bytes")

        if not state_path.exists() or state_path.stat().st_size < 50:
            messagebox.showerror(
                "Login Necessário",
                "❌ Faça LOGIN NO SITE primeiro!\n\n"
                "1. Clique em 'Site' (Login)\n"
                "2. Faça login no navegador\n"
                "3. Aguarde aparecer 'Sessão salva'\n"
                "4. Feche o navegador\n"
                "5. Tente novamente"
            )
            return

        cell = (self.cell_var.get() or "").strip().upper() or "E75"
        self.cell_var.set(cell)
        self.state_data.target_cell = cell

        self.status_var.set("Extraindo…")
        self._set_busy(True)

        self._set_codes([])
        self.state_data.codes = None
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        show_browser = self.var_show_browser.get()
        # Se 'Ver Navegador' = True -> headless = False
        headless_mode = not show_browser

        print(f"🚀 Iniciando extração (Mostrar Navegador: {show_browser})...\n")
        threading.Thread(target=self._worker_extract, args=(headless_mode,), daemon=True, name="ExtractThread").start()

    def _worker_extract(self, headless_mode: bool) -> None:
        print("[DEBUG] _worker_extract INICIADO")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            if not extractor:
                raise RuntimeError("Módulo extractor não carregado")

            ensure_playwright_browsers()
            print("=== EXTRAÇÃO ===\n")

            state_path = str((DEBUG_DIR / "storage_state.json").resolve())
            print(f"📍 Storage: {state_path}\n")

            if hasattr(extractor, "STORAGE_STATE"):
                extractor.STORAGE_STATE = state_path
                print("✅ STORAGE_STATE atualizado!\n")

            extractor.main(pdf_path=str(self.state_data.pdf_path), headless=headless_mode)

            path_csv = OUTPUTS_DIR / "codigos.csv"
            codes: list[str] = []
            if path_csv.exists():
                with path_csv.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0].strip() and row[0].strip().lower() != "codigo":
                            codes.append(row[0].strip())

            self.state_data.codes = codes
            self.after(0, lambda: self._set_codes(codes))
            self.after(0, lambda: self.status_var.set(f"✅ {len(codes)} códigos"))
            print(f"\n✅ Extração concluída! {len(codes)} códigos.\n")

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_send(self) -> None:
        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        if not self.state_data.codes:
            messagebox.showwarning("Códigos", "Extraia primeiro.")
            return

        # Fix: Read fresh value from UI, in case user changed it after extraction
        cell = (self.cell_var.get() or "").strip().upper() or "E75"
        self.state_data.target_cell = cell

        self._set_busy(True)
        self.status_var.set(f"Enviando para {cell}…")

        print("🚀 Iniciando envio...\n")
        threading.Thread(target=self._worker_send, args=(cell,), daemon=True).start()

    def _worker_send(self, cell: str) -> None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            if not poster:
                raise RuntimeError("Módulo poster não carregado")

            ensure_playwright_browsers()
            print("=== ENVIO ===\n")

            # Define path explicitly
            state_path = str(DEBUG_DIR / "storage_state_google.json")
            
            poster.main(
                target_cell=cell, 
                headless=False,
                storage_state_path=state_path
            )

            self.after(0, lambda: self.status_var.set("✅ Enviado"))
            self.after(0, lambda: messagebox.showinfo("OK", "Enviado!"))

        except Exception as e_err:
            traceback.print_exc()
            err_msg = str(e_err) # capture value for lambda
            self.after(0, lambda: self.status_var.set(f"Erro: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_login_site(self) -> None:
        print("[DEBUG] on_login_site chamado")

        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        self._set_busy(True)
        self.status_var.set("Login site (aguarde salvar)")

        print("🚀 Iniciando login site...\n")
        threading.Thread(target=self._worker_login_site, daemon=True).start()

    def _worker_login_site(self) -> None:
        print("[DEBUG] _worker_login_site INICIADO")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)
        
        # Helper logging function that is safe
        def safe_log(msg: str):
            # Try original stdout if available (console)
            if sys.__stdout__:
                try:
                    sys.__stdout__.write(msg + "\n")
                    sys.__stdout__.flush()
                except Exception:
                    pass
            # Always try to append to a debug file
            try:
                with open("login_debug.txt", "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception:
                pass

        safe_log("=== INICIANDO LOGIN WORKER ===")

        try:
            ensure_playwright_browsers()
            state_path = str(DEBUG_DIR / "storage_state.json")
            Path(state_path).parent.mkdir(parents=True, exist_ok=True)

            print("=== LOGIN SITE ===\n")
            print("✅ Faça login no navegador que vai abrir.")
            print("⛔ NÃO feche ainda — eu vou avisar quando a sessão estiver salva.\n")

            start_url = "https://manager.eumedicoresidente.com.br/admin/resources/Question"

            with sync_playwright() as p:
                # Launch with stealth args to avoid detection (same as google)
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled", 
                        "--start-maximized", 
                        "--no-sandbox",
                        "--disable-infobars"
                    ],
                    ignore_default_args=["--enable-automation"]
                )
                
                # Use a specific user agent
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                
                context_args = {
                    "user_agent": ua,
                    "viewport": None, # allow maximize
                    "no_viewport": True
                }

                if os.path.exists(state_path):
                    try:
                        context_args["storage_state"] = state_path
                        context = browser.new_context(**context_args)
                    except Exception:
                        del context_args["storage_state"]
                        context = browser.new_context(**context_args)
                else:
                    context = browser.new_context(**context_args)

                # Stealth script
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

                print("⚠️ Aguardando login... (Monitorando URL)")
                print("➡️ Faça login no site. Assim que detectar 'admin', eu salvo e aviso.")
                self._push_log("Aguardando login... (Monitorando URL)")

                time.sleep(1) # Espera navegador abrir

                saved_at_least_once = False
                
                print("⚠️ Aguardando confirmação manual do usuário...")
                safe_log("Aguardando confirmação manual...")
                
                # Reset flags
                self._login_confirmed = False
                self._login_abort = False
                
                # Delay to prevent accidental clicks
                time.sleep(4)

                # Show dialog on main thread
                def show_confirm():
                    ans = messagebox.askyesno(
                        "JÁ FEZ O LOGIN?", 
                        "1. Faça o login no navegador.\n2. SOMENTE DEPOIS de ver o Painel, clique em 'Sim' aqui.\n\nJá concluiu o login?"
                    )
                    if ans:
                        self._login_confirmed = True
                    else:
                        self._login_abort = True
                        
                self.after(0, show_confirm)
                
                # Wait for user action
                while not self._login_confirmed and not self._login_abort:
                    time.sleep(1)
                    if not browser.is_connected():
                        safe_log("Navegador fechado antes da confirmação.")
                        self._login_abort = True
                        break
                        
                if self._login_abort:
                     safe_log("Login cancelado ou navegador fechado.")
                     self.after(0, lambda: self.status_var.set("Login cancelado."))
                     return

                # If confirmed, save immediately
                if self._login_confirmed:
                    print("⏳ Salvando sessão...")
                    try:
                        context.storage_state(path=state_path)
                        safe_log("✅ SESSÃO SALVA COM SUCESSO!")
                        print("✅ SESSÃO SALVA!")
                        
                        self.after(0, lambda: self.status_var.set("✅ Login OK!"))
                        self.after(0, lambda: messagebox.showinfo("Sucesso", "Login salvo! O navegador será fechado."))
                    except Exception as e_save:
                        err_msg_save = str(e_save)
                        print(f"Erro ao salvar storage_state: {err_msg_save}")
                        safe_log(f"Erro ao salvar: {err_msg_save}")
                        self.after(0, lambda: messagebox.showwarning("Aviso", f"Erro ao salvar sessão: {err_msg_save}\n\nO navegador foi fechado?"))

            self.after(0, lambda: self.status_var.set("✅ Login OK (sessão salva)"))
            self.after(0, lambda: messagebox.showinfo("Login", "Sessão salva! Agora pode executar a extração."))

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro login: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro Login", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_login_google(self) -> None:
        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        self._set_busy(True)
        self.status_var.set("Login Google (feche ao terminar)")

        print("🚀 Iniciando login Google...\n")
        threading.Thread(target=self._worker_login_google, daemon=True).start()

    def _worker_login_google(self) -> None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            ensure_playwright_browsers()
            state_path = str(DEBUG_DIR / "storage_state_google.json")
            Path(state_path).parent.mkdir(parents=True, exist_ok=True)

            print("=== LOGIN GOOGLE (FIREFOX) ===\n")
            print("✅ Faça login e clique em 'Sim' na janela de confirmação.\n")

            with sync_playwright() as p:
                # Use Firefox to avoid Google Chromium Detection
                browser = p.firefox.launch(headless=False)
                
                context = browser.new_context(storage_state=state_path) if os.path.exists(state_path) else browser.new_context()
                page = context.new_page()
                page.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=60000)

                print("⚠️ Aguardando confirmação manual do usuário...")
                # Reset flags
                self._login_confirmed = False
                self._login_abort = False
                
                # Give user time to see the browser before checking
                time.sleep(4)

                # Show dialog on main thread
                def show_confirm():
                    ans = messagebox.askyesno(
                        "JÁ FEZ O LOGIN?", 
                        "1. Realize o login no navegador.\n2. SOMENTE DEPOIS de entrar na conta, clique em 'Sim' aqui.\n\nJá concluiu o login?"
                    )
                    if ans:
                        self._login_confirmed = True
                    else:
                        self._login_abort = True
                        
                self.after(0, show_confirm)
                
                # Wait for user action
                while not self._login_confirmed and not self._login_abort:
                    time.sleep(1)
                    if not browser.is_connected(): 
                         print("Navegador fechado antes da confirmação.")
                         self._login_abort = True
                         break
                        
                if self._login_abort:
                     print("Login cancelado ou navegador fechado.")
                     self.after(0, lambda: self.status_var.set("Login Google cancelado."))
                     try:
                        browser.close()
                     except Exception:
                        pass
                     return

                # If confirmed, save immediately
                if self._login_confirmed:
                    print("⏳ Salvando sessão...")
                    try:
                        # Save to JSON for compatibility
                        context.storage_state(path=state_path)
                        print(f"💾 Sessão salva: {state_path}\n")
                        self.after(0, lambda: self.status_var.set("✅ Login Google OK"))
                        self.after(0, lambda: messagebox.showinfo("Login", "Sessão Google salva!"))
                    except Exception as e_save:
                         err_msg_save = str(e_save)
                         print(f"Erro ao salvar storage_state: {err_msg_save}")
                         self.after(0, lambda: messagebox.showwarning("Aviso", f"Erro ao salvar sessão: {err_msg_save}\n\nO navegador foi fechado?"))
                    
                    try:
                        browser.close()
                    except Exception:
                        pass

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro login Google: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro Login Google", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))


def _add_dll_dir(path: Path) -> None:
    if not path.exists():
        return
    try:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(path))
    except Exception:
        pass
    os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")


def setup_runtime_env() -> None:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(APP_ROOT))
    if SCRIPTS_DIR.exists():
        sys.path.insert(0, str(SCRIPTS_DIR))
        if SCRIPTS_DIR.parent.exists():
            sys.path.insert(0, str(SCRIPTS_DIR.parent))

    _add_dll_dir(APP_ROOT)
    _add_dll_dir(ROOT / "_internal")
    for libs_name in ("numpy.libs", "pandas.libs"):
        _add_dll_dir(APP_ROOT / libs_name)
        _add_dll_dir((ROOT / "_internal") / libs_name)

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(get_playwright_browser_dir())


setup_runtime_env()


# Importa os scripts
try:
    from scripts import robo_pdf_para_codigos as extractor
    from scripts import post_codes_to_sheets as poster
except Exception:
    try:
        import robo_pdf_para_codigos as extractor
        import post_codes_to_sheets as poster
    except Exception as e:
        extractor = None
        poster = None
        print(f"⚠️ Aviso: {e}")


class _TkLogWriter(io.TextIOBase):
    def __init__(self, push: Callable[[str], None]):
        super().__init__()
        self._push = push

    def write(self, s: str) -> int:
        if not s:
            return 0
        self._push(s)
        return len(s)

    def flush(self) -> None:
        return


@dataclass
class RunState:
    pdf_path: Optional[str] = None
    target_cell: str = "E75"
    codes: list[str] | None = None


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_dirs()

        self.title("Robo Questões v3.3 (Debug)")
        self.geometry("1000x700")
        self.minsize(900, 600)

        self.state_data = RunState()
        self._log_queue: Queue[str] = Queue()
        self._busy = False
        self._busy_lock = threading.Lock()

        self._build_ui()
        self.after(80, self._drain_log_queue)

    def _build_ui(self) -> None:
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            input_frame, text="Configurações",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))

        pdf_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        pdf_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(pdf_row, text="PDF:").pack(side="left")

        self.pdf_var = ctk.StringVar(value="(Nenhum)")
        self.pdf_entry = ctk.CTkEntry(pdf_row, textvariable=self.pdf_var, state="readonly", width=400)
        self.pdf_entry.pack(side="left", padx=10, fill="x", expand=True)

        self.btn_pick_pdf = ctk.CTkButton(pdf_row, text="Selecionar", command=self.on_pick_pdf, width=120)
        self.btn_pick_pdf.pack(side="right")

        cell_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        cell_row.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(cell_row, text="Célula:").pack(side="left")
        self.cell_var = ctk.StringVar(value="E75")
        ctk.CTkEntry(cell_row, textvariable=self.cell_var, width=100).pack(side="left", padx=10)

        action_frame = ctk.CTkFrame(self)
        action_frame.pack(fill="x", padx=20, pady=10)

        # Adicionar Checkbox para Headless
        self.var_show_browser = ctk.BooleanVar(value=True)
        self.chk_browser = ctk.CTkCheckBox(
            action_frame, text="Ver Navegador (Extração)", variable=self.var_show_browser,
            font=ctk.CTkFont(size=12)
        )
        self.chk_browser.pack(side="top", pady=5)

        btn_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_container.pack(pady=5)

        self.btn_extract = ctk.CTkButton(
            btn_container, text="▶ Iniciar", height=45, width=220,
            command=self.on_run_extract, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_extract.pack(side="left", padx=10)

        self.btn_send = ctk.CTkButton(
            btn_container, text="Enviar 📤", height=45, width=220, state="disabled",
            command=self.on_send, fg_color="green", hover_color="darkgreen",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_send.pack(side="left", padx=10)

        login_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        login_frame.pack(fill="x", padx=15, pady=(0, 10))

        login_label_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        login_label_frame.pack(anchor="center")

        ctk.CTkLabel(login_label_frame, text="Login:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 10))

        self.btn_reset = ctk.CTkButton(
            login_label_frame, text="🔓 Destravar", command=self.on_force_reset,
            width=100, height=20, fg_color="red", hover_color="darkred",
            font=ctk.CTkFont(size=10)
        )
        self.btn_reset.pack(side="left")

        auth_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
        auth_frame.pack(pady=5)

        self.btn_login_site = ctk.CTkButton(auth_frame, text="Site", command=self.on_login_site, width=120, fg_color="gray", hover_color="gray30")
        self.btn_login_site.pack(side="left", padx=5)

        self.btn_login_google = ctk.CTkButton(auth_frame, text="Google", command=self.on_login_google, width=120, fg_color="gray", hover_color="gray30")
        self.btn_login_google.pack(side="left", padx=5)

        output_frame = ctk.CTkFrame(self, fg_color="transparent")
        output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        output_frame.grid_columnconfigure(0, weight=1, uniform="g")
        output_frame.grid_columnconfigure(1, weight=1, uniform="g")
        output_frame.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(output_frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(left, text="Códigos", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")
        self.codes_text = ctk.CTkTextbox(left, wrap="none", font=("Consolas", 12))
        self.codes_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.codes_text.configure(state="disabled")

        right = ctk.CTkFrame(output_frame)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(right, text="Console", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=5, anchor="w")
        self.log_text = ctk.CTkTextbox(right, wrap="word", font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        footer = ctk.CTkFrame(self, height=40, corner_radius=0)
        footer.pack(fill="x", side="bottom")

        self.status_var = ctk.StringVar(value="Pronto.")
        self.lbl_status = ctk.CTkLabel(footer, textvariable=self.status_var, anchor="w", padx=20)
        self.lbl_status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            footer, text="Outputs 📂", command=self.on_open_outputs, width=120, height=30,
            fg_color="transparent", border_width=1, border_color="gray"
        ).pack(side="right", padx=10, pady=5)

    def on_force_reset(self) -> None:
        with self._busy_lock:
            old_state = self._busy
            self._busy = False
        self._set_busy(False)
        self.status_var.set(f"🔓 Destravado (era: {old_state}).")
        print(f"\n🔓 Estado BUSY resetado: {old_state} -> False\n")

    def _push_log(self, s: str) -> None:
        self._log_queue.put(s)

    def _drain_log_queue(self) -> None:
        i = 0
        try:
            while i < 100:
                s = self._log_queue.get_nowait()
                self._append_log(s)
                i += 1
        except Empty:
            pass
        self.after(80, self._drain_log_queue)

    def _append_log(self, s: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", s)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_codes(self, codes: list[str]) -> None:
        self.codes_text.configure(state="normal")
        self.codes_text.delete("1.0", "end")
        self.codes_text.insert("end", "\n".join(codes))
        self.codes_text.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        with self._busy_lock:
            self._busy = busy

        print(f"[DEBUG] _set_busy({busy}) -> Dispatching UI update to main thread")
        # GARANTE que a atualização de widgets ocorra na Main Thread
        self.after(0, lambda: self._update_ui_state(busy))

    def _update_ui_state(self, busy: bool) -> None:
        try:
            print(f"[DEBUG] _update_ui_state(busy={busy}) running on Main Thread")
            state = "disabled" if busy else "normal"
            cursor = "watch" if busy else ""
            color = "yellow" if busy else ("white" if ctk.get_appearance_mode() == "Dark" else "black")

            self.btn_extract.configure(state=state)
            self.btn_login_site.configure(state=state)
            self.btn_login_google.configure(state=state)
            self.btn_pick_pdf.configure(state=state)

            if (not busy) and self.state_data.codes:
                self.btn_send.configure(state="normal")
            else:
                self.btn_send.configure(state="disabled")

            self.lbl_status.configure(text_color=color)
            self.configure(cursor=cursor)
            
            # Force update idle tasks to ensure UI refreshes immediately
            self.update_idletasks()
            print("[DEBUG] _update_ui_state completed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to update UI state: {e}")
            traceback.print_exc()
            messagebox.showerror("UI Error", f"Falha ao atualizar interface:\n{e}")

    def on_pick_pdf(self) -> None:
        print("[DEBUG] on_pick_pdf chamado")
        p = filedialog.askopenfilename(title="PDF", filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not p:
            print("[DEBUG] Nenhum PDF selecionado")
            return
        self.state_data.pdf_path = p
        self.pdf_var.set(p)
        self.status_var.set("PDF OK.")
        print(f"[DEBUG] PDF selecionado: {p}")

    def on_open_outputs(self) -> None:
        print("[DEBUG] on_open_outputs chamado")
        try:
            if sys.platform.startswith("win"):
                os.startfile(OUTPUTS_DIR)
            else:
                os.system(f'xdg-open "{OUTPUTS_DIR}"')
        except Exception:
            messagebox.showinfo("Outputs", f"{OUTPUTS_DIR}")

    def on_run_extract(self) -> None:
        print("[DEBUG] on_run_extract INICIADO")

        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.\nClique em 🔓 Destravar se travou")
                return

        if not self.state_data.pdf_path:
            messagebox.showwarning("PDF", "Selecione um PDF.")
            return

        state_path = DEBUG_DIR / "storage_state.json"
        print(f"[DEBUG] Verificando storage_state: {state_path}")
        print(f"[DEBUG] Existe: {state_path.exists()}")
        if state_path.exists():
            print(f"[DEBUG] Tamanho: {state_path.stat().st_size} bytes")

        if not state_path.exists() or state_path.stat().st_size < 50:
            messagebox.showerror(
                "Login Necessário",
                "❌ Faça LOGIN NO SITE primeiro!\n\n"
                "1. Clique em 'Site' (Login)\n"
                "2. Faça login no navegador\n"
                "3. Aguarde aparecer 'Sessão salva'\n"
                "4. Feche o navegador\n"
                "5. Tente novamente"
            )
            return

        cell = (self.cell_var.get() or "").strip().upper() or "E75"
        self.cell_var.set(cell)
        self.state_data.target_cell = cell

        self.status_var.set("Extraindo…")
        self._set_busy(True)

        self._set_codes([])
        self.state_data.codes = None
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        show_browser = self.var_show_browser.get()
        # Se 'Ver Navegador' = True -> headless = False
        headless_mode = not show_browser

        print(f"🚀 Iniciando extração (Mostrar Navegador: {show_browser})...\n")
        threading.Thread(target=self._worker_extract, args=(headless_mode,), daemon=True, name="ExtractThread").start()

    def _worker_extract(self, headless_mode: bool) -> None:
        print("[DEBUG] _worker_extract INICIADO")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            if not extractor:
                raise RuntimeError("Módulo extractor não carregado")

            ensure_playwright_browsers()
            print("=== EXTRAÇÃO ===\n")

            state_path = str((DEBUG_DIR / "storage_state.json").resolve())
            print(f"📍 Storage: {state_path}\n")

            if hasattr(extractor, "STORAGE_STATE"):
                extractor.STORAGE_STATE = state_path
                print("✅ STORAGE_STATE atualizado!\n")

            extractor.main(pdf_path=str(self.state_data.pdf_path), headless=headless_mode)

            path_csv = OUTPUTS_DIR / "codigos.csv"
            codes: list[str] = []
            if path_csv.exists():
                with path_csv.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0].strip() and row[0].strip().lower() != "codigo":
                            codes.append(row[0].strip())

            self.state_data.codes = codes
            self.after(0, lambda: self._set_codes(codes))
            self.after(0, lambda: self.status_var.set(f"✅ {len(codes)} códigos"))
            print(f"\n✅ Extração concluída! {len(codes)} códigos.\n")

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_send(self) -> None:
        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        if not self.state_data.codes:
            messagebox.showwarning("Códigos", "Extraia primeiro.")
            return

        # Fix: Read fresh value from UI, in case user changed it after extraction
        cell = (self.cell_var.get() or "").strip().upper() or "E75"
        self.state_data.target_cell = cell

        self._set_busy(True)
        self.status_var.set(f"Enviando para {cell}…")

        print("🚀 Iniciando envio...\n")
        threading.Thread(target=self._worker_send, args=(cell,), daemon=True).start()

    def _worker_send(self, cell: str) -> None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            if not poster:
                raise RuntimeError("Módulo poster não carregado")

            ensure_playwright_browsers()
            print("=== ENVIO ===\n")

            # Define path explicitly
            state_path = str(DEBUG_DIR / "storage_state_google.json")
            
            poster.main(
                target_cell=cell, 
                headless=False,
                storage_state_path=state_path
            )

            self.after(0, lambda: self.status_var.set("✅ Enviado"))
            self.after(0, lambda: messagebox.showinfo("OK", "Enviado!"))

        except Exception as e_err:
            traceback.print_exc()
            err_msg = str(e_err) # capture value for lambda
            self.after(0, lambda: self.status_var.set(f"Erro: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_login_site(self) -> None:
        print("[DEBUG] on_login_site chamado")

        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        self._set_busy(True)
        self.status_var.set("Login site (aguarde salvar)")

        print("🚀 Iniciando login site...\n")
        threading.Thread(target=self._worker_login_site, daemon=True).start()

    def _worker_login_site(self) -> None:
        print("[DEBUG] _worker_login_site INICIADO")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)
        
        # Helper logging function that is safe
        def safe_log(msg: str):
            # Try original stdout if available (console)
            if sys.__stdout__:
                try:
                    sys.__stdout__.write(msg + "\n")
                    sys.__stdout__.flush()
                except Exception:
                    pass
            # Always try to append to a debug file
            try:
                with open("login_debug.txt", "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception:
                pass

        safe_log("=== INICIANDO LOGIN WORKER ===")

        try:
            ensure_playwright_browsers()
            state_path = str(DEBUG_DIR / "storage_state.json")
            Path(state_path).parent.mkdir(parents=True, exist_ok=True)

            print("=== LOGIN SITE ===\n")
            print("✅ Faça login no navegador que vai abrir.")
            print("⛔ NÃO feche ainda — eu vou avisar quando a sessão estiver salva.\n")

            start_url = "https://manager.eumedicoresidente.com.br/admin/resources/Question"

            with sync_playwright() as p:
                # Launch with stealth args to avoid detection (same as google)
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled", 
                        "--start-maximized", 
                        "--no-sandbox",
                        "--disable-infobars"
                    ],
                    ignore_default_args=["--enable-automation"]
                )
                
                # Use a specific user agent
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                
                context_args = {
                    "user_agent": ua,
                    "viewport": None, # allow maximize
                    "no_viewport": True
                }

                if os.path.exists(state_path):
                    try:
                        context_args["storage_state"] = state_path
                        context = browser.new_context(**context_args)
                    except Exception:
                        del context_args["storage_state"]
                        context = browser.new_context(**context_args)
                else:
                    context = browser.new_context(**context_args)

                # Stealth script
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

                print("⚠️ Aguardando login... (Monitorando URL)")
                print("➡️ Faça login no site. Assim que detectar 'admin', eu salvo e aviso.")
                self._push_log("Aguardando login... (Monitorando URL)")

                time.sleep(1) # Espera navegador abrir

                saved_at_least_once = False
                
                print("⚠️ Aguardando confirmação manual do usuário...")
                safe_log("Aguardando confirmação manual...")
                
                # Reset flags
                self._login_confirmed = False
                self._login_abort = False
                
                # Delay to prevent accidental clicks
                time.sleep(4)

                # Show dialog on main thread
                def show_confirm():
                    ans = messagebox.askyesno(
                        "JÁ FEZ O LOGIN?", 
                        "1. Faça o login no navegador.\n2. SOMENTE DEPOIS de ver o Painel, clique em 'Sim' aqui.\n\nJá concluiu o login?"
                    )
                    if ans:
                        self._login_confirmed = True
                    else:
                        self._login_abort = True
                        
                self.after(0, show_confirm)
                
                # Wait for user action
                while not self._login_confirmed and not self._login_abort:
                    time.sleep(1)
                    if not browser.is_connected():
                        safe_log("Navegador fechado antes da confirmação.")
                        self._login_abort = True
                        break
                        
                if self._login_abort:
                     safe_log("Login cancelado ou navegador fechado.")
                     self.after(0, lambda: self.status_var.set("Login cancelado."))
                     return

                # If confirmed, save immediately
                if self._login_confirmed:
                    print("⏳ Salvando sessão...")
                    try:
                        context.storage_state(path=state_path)
                        safe_log("✅ SESSÃO SALVA COM SUCESSO!")
                        print("✅ SESSÃO SALVA!")
                        
                        self.after(0, lambda: self.status_var.set("✅ Login OK!"))
                        self.after(0, lambda: messagebox.showinfo("Sucesso", "Login salvo! O navegador será fechado."))
                    except Exception as e_save:
                        err_msg_save = str(e_save)
                        print(f"Erro ao salvar storage_state: {err_msg_save}")
                        safe_log(f"Erro ao salvar: {err_msg_save}")
                        self.after(0, lambda: messagebox.showwarning("Aviso", f"Erro ao salvar sessão: {err_msg_save}\n\nO navegador foi fechado?"))

            self.after(0, lambda: self.status_var.set("✅ Login OK (sessão salva)"))
            self.after(0, lambda: messagebox.showinfo("Login", "Sessão salva! Agora pode executar a extração."))

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro login: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro Login", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))

    def on_login_google(self) -> None:
        with self._busy_lock:
            if self._busy:
                messagebox.showwarning("Ocupado", "Operação em andamento.")
                return

        self._set_busy(True)
        self.status_var.set("Login Google (feche ao terminar)")

        print("🚀 Iniciando login Google...\n")
        threading.Thread(target=self._worker_login_google, daemon=True).start()

    def _worker_login_google(self) -> None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = _TkLogWriter(self._push_log)
        sys.stderr = _TkLogWriter(self._push_log)

        try:
            ensure_playwright_browsers()
            state_path = str(DEBUG_DIR / "storage_state_google.json")
            Path(state_path).parent.mkdir(parents=True, exist_ok=True)

            print("=== LOGIN GOOGLE ===\n")
            print("✅ Faça login e clique em 'Sim' na janela de confirmação.\n")

            # Create a persistent user data dir
            user_data_dir = DEBUG_DIR / "chrome_profile_google"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            with sync_playwright() as p:
                # Use SYSTEM CHROME to avoid detection loop
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    channel="chrome",  # <--- CRITICAL FIX: Use real Chrome
                    headless=False,
                    accept_downloads=True,
                    viewport=None,
                    args=[
                        "--disable-blink-features=AutomationControlled", 
                        "--start-maximized", 
                        "--no-sandbox",
                        "--disable-infobars"
                    ],
                    ignore_default_args=["--enable-automation"],
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                page = context.pages[0] if context.pages else context.new_page()
                
                # Stealth script
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=60000)

                print("⚠️ Aguardando confirmação manual do usuário...")
                # Reset flags
                self._login_confirmed = False
                self._login_abort = False
                
                # Give user time to see the browser before checking
                time.sleep(4)

                # Show dialog on main thread
                def show_confirm():
                    ans = messagebox.askyesno(
                        "JÁ FEZ O LOGIN?", 
                        "1. Realize o login no navegador.\n2. SOMENTE DEPOIS de entrar na conta, clique em 'Sim' aqui.\n\nJá concluiu o login?"
                    )
                    if ans:
                        self._login_confirmed = True
                    else:
                        self._login_abort = True
                        
                self.after(0, show_confirm)
                
                # Wait for user action
                while not self._login_confirmed and not self._login_abort:
                    time.sleep(1)
                    if not context.pages: 
                         print("Navegador fechado antes da confirmação.")
                         self._login_abort = True
                         break
                        
                if self._login_abort:
                     print("Login cancelado ou navegador fechado.")
                     self.after(0, lambda: self.status_var.set("Login Google cancelado."))
                     try:
                        context.close()
                     except Exception:
                        pass
                     return

                # If confirmed, save immediately
                if self._login_confirmed:
                    print("⏳ Salvando sessão...")
                    try:
                        # Save to JSON for compatibility
                        context.storage_state(path=state_path)
                        print(f"💾 Sessão salva: {state_path}\n")
                        self.after(0, lambda: self.status_var.set("✅ Login Google OK"))
                        self.after(0, lambda: messagebox.showinfo("Login", "Sessão Google salva!"))
                    except Exception as e_save:
                         err_msg_save = str(e_save)
                         print(f"Erro ao salvar storage_state: {err_msg_save}")
                         self.after(0, lambda: messagebox.showwarning("Aviso", f"Erro ao salvar sessão: {err_msg_save}\n\nO navegador foi fechado?"))
                    
                    try:
                        context.close()
                    except Exception:
                        pass

        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.after(0, lambda: self.status_var.set(f"Erro: {err_msg}"))
            self.after(0, lambda: messagebox.showerror("Erro", err_msg))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.after(0, lambda: self._set_busy(False))


def main() -> None:
    ensure_dirs()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()
    main()
