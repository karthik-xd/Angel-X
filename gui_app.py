import os
import sys
import ctypes
import subprocess
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

APP_TITLE = "Campus Shield - DPI Bypass"
LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "CampusShield")
SOURCE_BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "goodbyedpi-0.2.2", "x86_64")

PRESETS = {
    "Mode 1: Standard Bypass (Recommended for Poki & Games)": "-5",
    "Mode 2: Aggressive Bypass (For stubborn firewalls)": "-9",
    "Mode 3: Fake Packet + Anti-RST (Defeats RST injection)": "-p -r -s -f 2 -k 2 -n -e 2",
    "Mode 4: Bypass + Secure DNS Redirect (77.88.8.8:1253)": "-5 --dns-addr 77.88.8.8 --dns-port 1253"
}


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def setup_local_binaries():
    """Copies driver and executable to local AppData to prevent network share execution issues."""
    os.makedirs(LOCAL_DIR, exist_ok=True)
    required_files = ["goodbyedpi.exe", "WinDivert.dll", "WinDivert64.sys"]
    for f in required_files:
        src = os.path.join(SOURCE_BIN_DIR, f)
        dst = os.path.join(LOCAL_DIR, f)
        if os.path.exists(src) and (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)):
            shutil.copy2(src, dst)
    return os.path.join(LOCAL_DIR, "goodbyedpi.exe")


class DPIBypassApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("480x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#181825")

        self.process = None
        self.is_running = False
        self.exe_path = setup_local_binaries()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Header
        header = tk.Label(
            self.root,
            text="CAMPUS SHIELD",
            font=("Segoe UI", 18, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        )
        header.pack(pady=(18, 2))

        sub = tk.Label(
            self.root,
            text="Driver-level DPI Desync & SNI Unblocker",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        )
        sub.pack(pady=(0, 14))

        # Status Card
        self.status_card = tk.Frame(self.root, bg="#313244", padx=16, pady=10)
        self.status_card.pack(fill="x", padx=30, pady=5)

        self.status_dot = tk.Label(
            self.status_card,
            text="●",
            font=("Segoe UI", 16),
            fg="#f38ba8",
            bg="#313244"
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_text = tk.Label(
            self.status_card,
            text="OFFLINE (FIREWALL BLOCKING ACTIVE)",
            font=("Segoe UI", 10, "bold"),
            fg="#f38ba8",
            bg="#313244"
        )
        self.status_text.pack(side="left")

        # Preset Selector
        preset_frame = tk.Frame(self.root, bg="#181825")
        preset_frame.pack(fill="x", padx=30, pady=(15, 5))

        tk.Label(
            preset_frame,
            text="Bypass Strategy:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825"
        ).pack(anchor="w", pady=(0, 4))

        self.preset_var = tk.StringVar(value=list(PRESETS.keys())[0])
        self.combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(PRESETS.keys()),
            state="readonly",
            font=("Segoe UI", 9)
        )
        self.combo.pack(fill="x")

        # Main Action Button
        self.btn_toggle = tk.Button(
            self.root,
            text="START PROTECTION",
            font=("Segoe UI", 12, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            activeforeground="#11111b",
            relief="flat",
            padx=20,
            pady=12,
            cursor="hand2",
            command=self.toggle
        )
        self.btn_toggle.pack(pady=16)

        # Log output text box
        log_frame = tk.Frame(self.root, bg="#181825")
        log_frame.pack(fill="both", expand=True, padx=30, pady=(0, 15))

        self.log_box = tk.Text(
            log_frame,
            height=6,
            bg="#11111b",
            fg="#a6adc8",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=8
        )
        self.log_box.pack(fill="both", expand=True)
        self.log("Ready. WinDivert engine loaded.")
        if not is_admin():
            self.log("[WARN] App not running as Administrator. Admin required to load driver.")

    def log(self, message):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see("end")

    def toggle(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not is_admin():
            messagebox.showerror(
                "Administrator Rights Required",
                "WinDivert packet driver requires Administrator privileges to bypass hardware DPI.\n\nPlease run this app as Administrator."
            )
            return

        cmd_args = PRESETS.get(self.preset_var.get(), "-5")
        full_cmd = f'"{self.exe_path}" {cmd_args}'

        try:
            self.log(f"Starting driver with: {cmd_args}")
            # CREATE_NO_WINDOW flag
            self.process = subprocess.Popen(
                full_cmd,
                cwd=LOCAL_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=0x08000000
            )
            self.is_running = True

            self.status_dot.config(fg="#a6e3a1")
            self.status_text.config(text="ONLINE (PROTECTED - DPI BYPASS ACTIVE)", fg="#a6e3a1")
            self.btn_toggle.config(text="STOP PROTECTION", bg="#f38ba8")
            self.combo.config(state="disabled")

            threading.Thread(target=self._monitor_process, daemon=True).start()
            self.log("Driver loaded successfully. Fake packet injection active.")
        except Exception as e:
            self.log(f"Error launching: {e}")
            messagebox.showerror("Error", f"Failed to start bypass engine:\n{e}")

    def _monitor_process(self):
        while self.is_running and self.process:
            line = self.process.stdout.readline()
            if line:
                cleaned = line.strip()
                if cleaned:
                    self.root.after(0, self.log, cleaned)
            elif self.process.poll() is not None:
                break
        if self.is_running:
            self.root.after(0, self.stop)

    def stop(self):
        self.is_running = False
        if self.process:
            self.log("Stopping bypass engine...")
            try:
                subprocess.run(f"taskkill /F /IM goodbyedpi.exe", shell=True, capture_output=True)
                self.process.terminate()
            except Exception:
                pass
            self.process = None

        self.status_dot.config(fg="#f38ba8")
        self.status_text.config(text="OFFLINE (FIREWALL BLOCKING ACTIVE)", fg="#f38ba8")
        self.btn_toggle.config(text="START PROTECTION", bg="#89b4fa")
        self.combo.config(state="readonly")
        self.log("Stopped. Driver unloaded.")

    def on_close(self):
        self.stop()
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    if not is_admin():
        # Auto-request elevation on start
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            f'"{os.path.abspath(__file__)}"',
            None,
            1
        )
        sys.exit(0)

    root = tk.Tk()
    app = DPIBypassApp(root)
    root.mainloop()
