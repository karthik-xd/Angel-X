import asyncio
import socket
import threading
import winreg
import ctypes
import atexit
import signal
import sys
import tkinter as tk
from tkinter import ttk, messagebox

PROXY_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
SPLIT_DELAY = 0.02  # 20ms delay between fragments

INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def set_system_proxy(enable: bool, host: str = PROXY_HOST, port: int = DEFAULT_PORT):
    """Enables or disables system-wide Windows proxy via Registry and WinINet."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
            if enable:
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"{host}:{port}")
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
    except Exception as e:
        print(f"Error modifying system proxy: {e}")


# Always ensure system proxy is cleared on exit
atexit.register(lambda: set_system_proxy(False))


class DPIBypassProxy:
    def __init__(self, host=PROXY_HOST, port=DEFAULT_PORT, on_activity=None):
        self.host = host
        self.port = port
        self.on_activity = on_activity
        self.server = None
        self.loop = None
        self.running = False
        self.active_conns = 0
        self.total_conns = 0

    async def pipe(self, r, w):
        try:
            while True:
                data = await r.read(65536)
                if not data:
                    break
                w.write(data)
                await w.drain()
        except Exception:
            pass
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def handle_client(self, cr, cw):
        self.active_conns += 1
        self.total_conns += 1
        if self.on_activity:
            self.on_activity(self.active_conns, self.total_conns)

        remote_writer = None
        try:
            req_line = await cr.readuntil(b"\r\n\r\n")
            lines = req_line.split(b"\r\n")
            if not lines or not lines[0]:
                cw.close()
                return

            parts = lines[0].decode(errors="ignore").split()
            if len(parts) < 2:
                cw.close()
                return

            method, target = parts[0], parts[1]

            if method == "CONNECT":
                # HTTPS connection tunneling
                if ":" in target:
                    host, port = target.rsplit(":", 1)
                    port = int(port)
                else:
                    host = target
                    port = 443

                rr, rw = await asyncio.open_connection(host, port)
                remote_writer = rw
                rw.get_extra_info("socket").setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                cw.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await cw.drain()

                # Read TLS ClientHello
                first_packet = await cr.read(65536)
                if first_packet:
                    # Fragment first packet: 1 byte first, delay, then rest
                    # Campus DPI fails to reassemble and cannot read SNI domain
                    rw.write(first_packet[:1])
                    await rw.drain()
                    await asyncio.sleep(SPLIT_DELAY)
                    rw.write(first_packet[1:])
                    await rw.drain()

                await asyncio.gather(self.pipe(cr, rw), self.pipe(rr, cw))
            else:
                # Plain HTTP proxying
                cw.close()
        except Exception:
            pass
        finally:
            try:
                cw.close()
            except Exception:
                pass
            if remote_writer:
                try:
                    remote_writer.close()
                except Exception:
                    pass
            self.active_conns = max(0, self.active_conns - 1)
            if self.on_activity:
                self.on_activity(self.active_conns, self.total_conns)

    async def _run(self):
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        self.running = True
        async with self.server:
            await self.server.serve_forever()

    def start(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run())
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False

    def stop(self):
        if self.loop and self.server:
            self.loop.call_soon_threadsafe(self.server.close)
            for task in asyncio.all_tasks(self.loop):
                self.loop.call_soon_threadsafe(task.cancel)


class AppUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Campus DPI Bypass")
        self.root.geometry("400x340")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.proxy = None
        self.thread = None
        self.auto_proxy_var = tk.BooleanVar(value=True)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Header Title
        title_label = tk.Label(
            self.root,
            text="CAMPUS DPI BYPASS",
            font=("Segoe UI", 16, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e"
        )
        title_label.pack(pady=(20, 5))

        subtitle = tk.Label(
            self.root,
            text="Splits TLS SNI packets. Hides domains from campus filter.",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#1e1e2e"
        )
        subtitle.pack(pady=(0, 15))

        # Status badge frame
        self.status_frame = tk.Frame(self.root, bg="#313244", padx=15, pady=8)
        self.status_frame.pack(fill="x", padx=30, pady=5)

        self.status_dot = tk.Label(self.status_frame, text="●", font=("Segoe UI", 14), fg="#f38ba8", bg="#313244")
        self.status_dot.pack(side="left", padx=(5, 8))

        self.status_text = tk.Label(
            self.status_frame,
            text="STATUS: STOPPED",
            font=("Segoe UI", 11, "bold"),
            fg="#f38ba8",
            bg="#313244"
        )
        self.status_text.pack(side="left")

        # Stats frame
        self.stats_label = tk.Label(
            self.root,
            text="Active Connections: 0 | Total Bypassed: 0",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#1e1e2e"
        )
        self.stats_label.pack(pady=10)

        # Main Action Button
        self.toggle_btn = tk.Button(
            self.root,
            text="START BYPASS",
            font=("Segoe UI", 12, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            activeforeground="#11111b",
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2",
            command=self.toggle_proxy
        )
        self.toggle_btn.pack(pady=10)

        # Checkbox for Windows system proxy
        chk = tk.Checkbutton(
            self.root,
            text="Auto-apply to Windows System Proxy (Browser & Apps)",
            variable=self.auto_proxy_var,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4"
        )
        chk.pack(pady=(5, 5))

        footer = tk.Label(
            self.root,
            text=f"Listening on {PROXY_HOST}:{DEFAULT_PORT}",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#1e1e2e"
        )
        footer.pack(side="bottom", pady=10)

    def update_stats(self, active, total):
        self.root.after(0, lambda: self.stats_label.config(
            text=f"Active Connections: {active} | Total Bypassed: {total}"
        ))

    def toggle_proxy(self):
        if self.proxy and self.proxy.running:
            self.stop()
        else:
            self.start()

    def start(self):
        self.proxy = DPIBypassProxy(
            host=PROXY_HOST,
            port=DEFAULT_PORT,
            on_activity=self.update_stats
        )
        self.thread = threading.Thread(target=self.proxy.start, daemon=True)
        self.thread.start()

        if self.auto_proxy_var.get():
            set_system_proxy(True, PROXY_HOST, DEFAULT_PORT)

        self.status_dot.config(fg="#a6e3a1")
        self.status_text.config(text="STATUS: RUNNING (PROTECTED)", fg="#a6e3a1")
        self.toggle_btn.config(text="STOP BYPASS", bg="#f38ba8")

    def stop(self):
        if self.proxy:
            self.proxy.stop()
        set_system_proxy(False)

        self.status_dot.config(fg="#f38ba8")
        self.status_text.config(text="STATUS: STOPPED", fg="#f38ba8")
        self.toggle_btn.config(text="START BYPASS", bg="#89b4fa")

    def on_close(self):
        self.stop()
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = AppUI(root)
    root.mainloop()
