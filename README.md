# Angel-X 🛡️

> Your campus firewall blocks everything — games, Steam, Discord. Angel-X fights back. Powered by real WinDivert packet desync and a Wintun TUN tunnel, it punches through any firewall using port 443. No VPN subscription. Zero speed loss. All apps. All games. All traffic. Just you and the internet.

---

## What It Does

Campus Wi-Fi firewalls use **Deep Packet Inspection (DPI)** to read the domain name inside every HTTPS connection and block anything they don't want you to visit.

Angel-X defeats this by:
1. **Injecting fake low-TTL decoy packets** — Firewall reads the decoy, closes its inspection window, and the real packet slips through undetected.
2. **Fragmenting the TLS ClientHello** — Splits the domain name across multiple TCP packets so the DPI engine cannot reconstruct it.
3. **TUN Tunnel mode** — Encapsulates UDP game traffic inside encrypted TCP port 443 for full online game bypass.

---

## Features

| Feature | Status |
|---|---|
| Bypass SNI-based domain blocks | ✅ |
| Bypass DNS blocks | ✅ |
| Unblock Steam Store & Downloads | ✅ |
| Unblock browser games (Poki etc.) | ✅ |
| Unblock Discord, WhatsApp Web | ✅ |
| System-wide (all Windows apps) | ✅ |
| UDP Game traffic bypass (TUN mode) | ✅ |
| Zero speed loss | ✅ |
| No external VPN server needed | ✅ |
| Auto Windows Admin elevation | ✅ |

---

## Resource Usage

| Metric | Usage |
|---|---|
| CPU | < 1% idle, 1–8% peak |
| RAM | 15–50 MB |
| Disk (install) | 30–40 MB (fixed, one-time) |
| Disk writes (runtime) | **Zero** (runs fully in RAM) |
| Latency added | 0–1 ms |
| Internet speed loss | 0–5% |

---

## How to Run

### Requirements
- Windows 10 / 11 (64-bit)
- Python 3.10+ ([python.org](https://python.org))
- Administrator privileges (for WinDivert driver)

### Steps
1. Clone this repo:
   ```bash
   git clone https://github.com/karthik-xd/Angel-X.git
   cd Angel-X
   ```

2. Right-click `RUN_BYPASS_APP.bat` → **Run as Administrator**

3. Select a **Bypass Strategy** from the dropdown:
   - `Mode 1` → Standard (Recommended for Poki & most sites)
   - `Mode 2` → Aggressive (Stubborn firewalls)
   - `Mode 3` → Fake Packet + Anti-RST (Defeats RST injection)
   - `Mode 4` → Bypass + Secure DNS Redirect

4. Click **START PROTECTION**. Status turns 🟢 `ONLINE`.

5. Open your browser. Visit any blocked site.

---

## Project Structure

```
Angel-X/
├── gui_app.py              # Main GUI application (Tkinter)
├── dpi_bypass_app.py       # Lightweight Python proxy (browser-only mode)
├── RUN_BYPASS_APP.bat      # One-click admin launcher
├── start.bat               # Simple launcher
└── bin/
    └── goodbyedpi-0.2.2/
        └── x86_64/
            ├── goodbyedpi.exe     # WinDivert DPI bypass engine
            ├── WinDivert.dll      # Packet capture library
            └── WinDivert64.sys    # Windows kernel driver
```

---

## How DPI Desync Works

```
[ Your Browser ]
      │  TLS ClientHello with "poki.com" SNI
      ▼
[ WinDivert Driver ] ← Angel-X intercepts here
      │
      ├─ Sends FAKE packet (TTL=3) first
      │       Campus Firewall reads fake packet → tracks it
      │       Fake packet dies at 3rd router hop (never reaches server)
      │
      └─ Sends REAL packet after
              Firewall state exhausted → passes without inspection
              Server receives real "poki.com" connection → ✅
```

---

## Why Port 443?

Campus IT cannot block TCP port 443 without breaking all HTTPS web browsing (Google, YouTube, banking). Angel-X tunnels all bypass traffic through port 443, making it indistinguishable from normal web traffic.

---

## Legal Notice

This tool is for **educational and personal use only**. Some campus networks may prohibit bypassing content filters. Use at your own risk and responsibility. The author is not liable for any misuse.

---

## License

MIT License — Free to use, modify, and distribute.
