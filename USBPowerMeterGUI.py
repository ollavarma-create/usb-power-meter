"""
USBPowerMeterGUI.py – BLE USB-tehomittari graafisella käyttöliittymällä
Laite: J7-C / UC96 BLE (tai yhteensopiva)
Vaatimukset: pip install bleak matplotlib
"""

import asyncio
import threading
import time
import os
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt

from bleak import BleakClient, BleakScanner

# ── Vakiot ────────────────────────────────────────────────────────────────────
SERVICE_UUID     = "0000ffe0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
MAX_POINTS       = 300   # Graafissa näkyvien pisteiden maksimi
CSV_FILE         = "usb_meter_data.csv"

# ── Globaali tila ─────────────────────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.connected    = False
        self.recording    = False
        self.device_mac   = ""
        self.ble_loop     = None   # asyncio-silmukka BLE-säikeessä
        self.ble_thread   = None
        self.ble_client   = None
        self.start_time   = None
        self.csv_file     = None

        # Reaaliaikadata (thread-safe deque)
        self.times    = deque(maxlen=MAX_POINTS)
        self.voltages = deque(maxlen=MAX_POINTS)
        self.currents = deque(maxlen=MAX_POINTS)
        self.powers   = deque(maxlen=MAX_POINTS)
        self.mahs     = deque(maxlen=MAX_POINTS)
        self.whs      = deque(maxlen=MAX_POINTS)
        self.temps    = deque(maxlen=MAX_POINTS)

        # Kaikki data CSV-vientiä varten (rajoittamaton)
        self.all_times    = []
        self.all_voltages = []
        self.all_currents = []
        self.all_powers   = []
        self.all_mahs     = []
        self.all_whs      = []
        self.all_temps    = []

        # Viimeisin arvo näyttöä varten
        self.last = {
            "voltage": 0.0, "current": 0.0, "power": 0.0,
            "mah": 0, "wh": 0.0, "temp": 0
        }
        self.packet_count = 0
        self.found_devices = {}   # {nimi: mac}

state = AppState()


# ── BLE-parsinta ──────────────────────────────────────────────────────────────
def parse_packet(data: bytearray) -> dict | None:
    if len(data) != 36 or data[0] != 0xFF or data[1] != 0x55:
        return None
    return {
        "voltage": int.from_bytes(data[4:7],  "big") / 100.0,
        "current": int.from_bytes(data[7:10], "big") / 100.0,
        "mah":     int.from_bytes(data[10:13],"big"),
        "wh":      int.from_bytes(data[13:16],"big") / 100.0,
        "temp":    int.from_bytes(data[21:23],"big"),
    }


# ── BLE-säie (asyncio) ────────────────────────────────────────────────────────
def notification_handler(sender, data: bytearray):
    parsed = parse_packet(data)
    if parsed is None:
        return

    v  = parsed["voltage"]
    a  = parsed["current"]
    w  = v * a
    now = time.time() - state.start_time

    state.times.append(now)
    state.voltages.append(v)
    state.currents.append(a)
    state.powers.append(w)
    state.mahs.append(parsed["mah"])
    state.whs.append(parsed["wh"])
    state.temps.append(parsed["temp"])

    # Kaikki data talteen CSV-vientiä varten
    state.all_times.append(now)
    state.all_voltages.append(v)
    state.all_currents.append(a)
    state.all_powers.append(w)
    state.all_mahs.append(parsed["mah"])
    state.all_whs.append(parsed["wh"])
    state.all_temps.append(parsed["temp"])

    state.last.update({
        "voltage": v, "current": a, "power": w,
        "mah": parsed["mah"], "wh": parsed["wh"], "temp": parsed["temp"]
    })
    state.packet_count += 1

    if state.recording and state.csv_file:
        ts = time.strftime("%H:%M:%S")
        state.csv_file.write(
            f"{time.time():.3f},{v:.3f},{a:.3f},{w:.2f},"
            f"{parsed['mah']},{parsed['wh']:.3f},{parsed['temp']}\n"
        )
        state.csv_file.flush()


async def ble_scan():
    """Skannaa BLE-laitteet ja palauttaa listan."""
    devices = await BleakScanner.discover(timeout=5.0)
    return devices


async def ble_connect(mac: str):
    state.ble_client = BleakClient(mac)
    await state.ble_client.connect()
    if not state.ble_client.is_connected:
        raise ConnectionError("Yhteys epäonnistui")

    await state.ble_client.start_notify(NOTIFY_CHAR_UUID, notification_handler)

    # Käynnistyskomennot (ei pakollisia kaikilla laitteilla)
    try:
        await state.ble_client.write_gatt_char(NOTIFY_CHAR_UUID, bytearray([0xA5, 0x80]))
        await asyncio.sleep(0.3)
        await state.ble_client.write_gatt_char(NOTIFY_CHAR_UUID, bytearray([0xA5, 0x01]))
    except Exception:
        pass

    state.connected = True
    state.start_time = time.time()

    # Pidä yhteys auki kunnes katkaistaan
    while state.connected:
        await asyncio.sleep(0.5)

    await state.ble_client.stop_notify(NOTIFY_CHAR_UUID)
    await state.ble_client.disconnect()


def run_ble_loop(coro):
    """Ajaa asyncio-koodin erillisessä säikeessä."""
    loop = asyncio.new_event_loop()
    state.ble_loop = loop
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()
        state.ble_loop = None


# ── Pääikkuna ─────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("USB Power Meter")
        self.configure(bg="#0d1117")
        self.resizable(True, True)
        self.geometry("1000x720")
        self._build_ui()
        self._start_animation()

    # ── UI-rakenne ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.configure(bg="#0d1117")

        # Yläpalkki
        top = tk.Frame(self, bg="#0d1117", pady=8)
        top.pack(fill="x", padx=16)

        tk.Label(top, text="⚡ USB Power Meter", font=("Courier New", 18, "bold"),
                 bg="#0d1117", fg="#58a6ff").pack(side="left")

        # Status-indikaattori
        self.status_dot = tk.Label(top, text="●", font=("Courier New", 18),
                                   bg="#0d1117", fg="#30363d")
        self.status_dot.pack(side="right", padx=4)
        self.status_label = tk.Label(top, text="Ei yhteyttä",
                                     font=("Courier New", 11), bg="#0d1117", fg="#8b949e")
        self.status_label.pack(side="right", padx=4)

        # Laitevalinta + napit
        ctrl = tk.Frame(self, bg="#161b22", pady=6, padx=12)
        ctrl.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(ctrl, text="Laite:", font=("Courier New", 10),
                 bg="#161b22", fg="#8b949e").pack(side="left")

        self.device_var = tk.StringVar(value="Ei laitteita")
        self.device_combo = ttk.Combobox(ctrl, textvariable=self.device_var,
                                          width=36, font=("Courier New", 10),
                                          state="readonly")
        self.device_combo.pack(side="left", padx=8)

        self._btn(ctrl, "🔍 Etsi", self._scan,   "#238636").pack(side="left", padx=4)
        self.btn_connect = self._btn(ctrl, "🔗 Yhdistä", self._connect, "#1f6feb")
        self.btn_connect.pack(side="left", padx=4)
        self._btn(ctrl, "🖼 Tallenna kuva", self._save_graph, "#6e40c9").pack(side="left", padx=4)
        self._btn(ctrl, "💾 Vie CSV", self._export_csv, "#3d444d").pack(side="left", padx=4)
        self._btn(ctrl, "✖ Katkaise", self._disconnect, "#b62324").pack(side="left", padx=4)



        # Mittarinäytöt
        gauges = tk.Frame(self, bg="#0d1117")
        gauges.pack(fill="x", padx=16, pady=(0, 8))

        self.gauge_vars = {}
        specs = [
            ("voltage", "JÄNNITE",  "V",   "#58a6ff"),
            ("current", "VIRTA",    "A",   "#3fb950"),
            ("power",   "TEHO",     "W",   "#f78166"),
            ("mah",     "KAPASIT.", "mAh", "#d2a8ff"),
            ("wh",      "ENERGIA",  "Wh",  "#ffa657"),
            ("temp",    "LÄMPÖ",    "°C",  "#79c0ff"),
        ]
        for key, label, unit, color in specs:
            f = tk.Frame(gauges, bg="#161b22", padx=12, pady=8,
                         relief="flat", bd=0)
            f.pack(side="left", expand=True, fill="both", padx=4)

            tk.Label(f, text=label, font=("Courier New", 8, "bold"),
                     bg="#161b22", fg="#484f58").pack()

            var = tk.StringVar(value="0.000")
            self.gauge_vars[key] = var
            tk.Label(f, textvariable=var, font=("Courier New", 22, "bold"),
                     bg="#161b22", fg=color).pack()

            tk.Label(f, text=unit, font=("Courier New", 9),
                     bg="#161b22", fg="#484f58").pack()

        # Graafi
        self.fig = Figure(figsize=(10, 3.8), facecolor="#0d1117")
        self.ax1 = self.fig.add_subplot(111)
        self.ax2 = self.ax1.twinx()
        self._style_axes()

        self.line_v, = self.ax1.plot([], [], color="#58a6ff", lw=1.5, label="Jännite (V)")
        self.line_w, = self.ax1.plot([], [], color="#f78166", lw=1.2,
                                      linestyle="--", label="Teho (W)")
        self.line_a, = self.ax2.plot([], [], color="#3fb950", lw=2.0, label="Virta (A)")

        lines = [self.line_v, self.line_w, self.line_a]
        labels = [l.get_label() for l in lines]
        self.ax1.legend(lines, labels, loc="upper left",
                        facecolor="#161b22", edgecolor="#30363d",
                        labelcolor="white", fontsize=8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Alatila
        bot = tk.Frame(self, bg="#0d1117")
        bot.pack(fill="x", padx=16, pady=(0, 8))
        self.rec_label = tk.Label(bot, text="", font=("Courier New", 9),
                                  bg="#0d1117", fg="#3fb950")
        self.rec_label.pack(side="left")
        self.pkt_label = tk.Label(bot, text="PKT: 0 | CSV: 0",
                                  font=("Courier New", 9), bg="#0d1117", fg="#8b949e")
        self.pkt_label.pack(side="left", padx=16)
        tk.Label(bot, text=f"MAC: {state.device_mac or '—'}",
                 font=("Courier New", 9), bg="#0d1117", fg="#484f58").pack(side="right")

    def _btn(self, parent, text, cmd, color):
        return tk.Button(parent, text=text, command=cmd,
                         font=("Courier New", 9, "bold"),
                         bg=color, fg="white", relief="flat",
                         padx=10, pady=4, cursor="hand2",
                         activebackground=color, activeforeground="white")

    def _style_axes(self):
        for ax in [self.ax1, self.ax2]:
            ax.set_facecolor("#0d1117")
            ax.tick_params(colors="#484f58", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#30363d")
        self.ax1.set_xlabel("Aika (s)", color="#484f58", fontsize=8)
        self.ax1.set_ylabel("V / W", color="#484f58", fontsize=8)
        self.ax2.set_ylabel("A", color="#3fb950", fontsize=8)
        self.ax2.tick_params(axis="y", labelcolor="#3fb950")
        self.fig.tight_layout(pad=1.5)

    # ── Animaatio ─────────────────────────────────────────────────────────────
    def _start_animation(self):
        self.anim = FuncAnimation(self.fig, self._update_plot,
                                  interval=500, blit=False, cache_frame_data=False)

    def _update_plot(self, frame):
        if not state.times:
            return

        t = list(state.times)
        v = list(state.voltages)
        a = list(state.currents)
        w = list(state.powers)

        self.line_v.set_data(t, v)
        self.line_w.set_data(t, w)
        self.line_a.set_data(t, a)

        self.ax1.relim(); self.ax1.autoscale_view()
        self.ax2.relim(); self.ax2.autoscale_view()

        # Päivitä mittarit
        last = state.last
        self.gauge_vars["voltage"].set(f"{last['voltage']:.3f}")
        self.gauge_vars["current"].set(f"{last['current']:.3f}")
        self.gauge_vars["power"].set(f"{last['power']:.2f}")
        self.gauge_vars["mah"].set(str(last["mah"]))
        self.gauge_vars["wh"].set(f"{last['wh']:.3f}")
        self.gauge_vars["temp"].set(str(last["temp"]))

        self.pkt_label.config(text=f"PKT: {state.packet_count} | CSV: {len(state.all_times)}")

        if state.recording:
            self.rec_label.config(
                text=f"⏺ Tallennetaan → {CSV_FILE}  ({state.packet_count} pistettä)")

    # ── Napit ─────────────────────────────────────────────────────────────────
    def _scan(self):
        self.status_label.config(text="Skannataan...", fg="#f0b429")
        self.status_dot.config(fg="#f0b429")
        self.update()

        def do_scan():
            loop = asyncio.new_event_loop()
            devices = loop.run_until_complete(ble_scan())
            loop.close()

            state.found_devices = {}
            for d in devices:
                name = d.name or "Nimetön"
                state.found_devices[f"{name} ({d.address})"] = d.address

            self.device_combo["values"] = list(state.found_devices.keys())
            if state.found_devices:
                self.device_combo.current(0)
                self.status_label.config(
                    text=f"{len(state.found_devices)} laite(tta) löydetty", fg="#3fb950")
                self.status_dot.config(fg="#3fb950")
            else:
                self.status_label.config(text="Ei laitteita löydetty", fg="#f78166")
                self.status_dot.config(fg="#f78166")

        threading.Thread(target=do_scan, daemon=True).start()

    def _connect(self):
        selected = self.device_var.get()
        if selected not in state.found_devices:
            messagebox.showwarning("Laite", "Valitse laite ensin (Etsi)")
            return

        mac = state.found_devices[selected]
        state.device_mac = mac

        self.status_label.config(text=f"Yhdistetään {mac}...", fg="#f0b429")
        self.status_dot.config(fg="#f0b429")

        def do_connect():
            try:
                run_ble_loop(ble_connect(mac))
            except Exception as e:
                self.status_label.config(text=f"Virhe: {e}", fg="#f78166")
                self.status_dot.config(fg="#f78166")
                state.connected = False

        state.ble_thread = threading.Thread(target=do_connect, daemon=True)
        state.ble_thread.start()

        # Tarkista yhteys 500 ms välein
        self._wait_for_connect()

    def _wait_for_connect(self):
        if state.connected:
            self.status_label.config(
                text=f"Yhdistetty: {state.device_mac}", fg="#3fb950")
            self.status_dot.config(fg="#3fb950")
        elif state.ble_thread and state.ble_thread.is_alive():
            self.after(500, self._wait_for_connect)

    def _disconnect(self):
        state.connected = False
        if state.recording:
            state.recording = False
            if state.csv_file:
                state.csv_file.close()
                state.csv_file = None
        self.status_label.config(text="Katkaistu", fg="#8b949e")
        self.status_dot.config(fg="#30363d")

    def _save_graph(self):
        """Tallenna nykyinen graafi PNG-tiedostoon."""
        if not state.times:
            messagebox.showinfo("Ei dataa", "Ei mittausdataa tallennettavaksi")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-kuva", "*.png"), ("Kaikki", "*.*")],
            initialfile="usb_meter_graafi.png",
            title="Tallenna graafi"
        )
        if not path:
            return
        self.fig.savefig(path, dpi=200, bbox_inches="tight",
                         facecolor=self.fig.get_facecolor())
        messagebox.showinfo("Tallennettu", f"Graafi tallennettu:\n{path}")

    def _export_csv(self):
        """Vie kaikki kerätty data CSV:hen (ei vain graafin viimeiset 300 pistettä)."""
        if not state.all_times:
            messagebox.showinfo("Ei dataa", "Ei mittausdataa vietäväksi")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="usb_meter_export.csv",
            title="Vie CSV"
        )
        if not path:
            return
        with open(path, "w") as f:
            f.write("aika_s,jannite_V,virta_A,teho_W,mah,wh,temp_C\n")
            for i in range(len(state.all_times)):
                f.write(
                    f"{state.all_times[i]:.3f},"
                    f"{state.all_voltages[i]:.3f},"
                    f"{state.all_currents[i]:.3f},"
                    f"{state.all_powers[i]:.2f},"
                    f"{state.all_mahs[i]},"
                    f"{state.all_whs[i]:.3f},"
                    f"{state.all_temps[i]}\n"
                )
        messagebox.showinfo("Viety", f"{len(state.all_times)} pistettä tallennettu:\n{path}")

    def on_close(self):
        state.connected = False
        if state.recording:
            self._stop_record()
        self.destroy()


# ── Käynnistys ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()