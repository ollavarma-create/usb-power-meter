import asyncio
import time
import os
from collections import deque
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from bleak import BleakClient, BleakScanner

# Konfiguraatio
DEVICE_MAC = "12:C0:36:1D:C4:B0"
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

CSV_FILE = "usb_meter_data.csv"

# Data-rakenteet (deque rajoittaa muistinkäyttöä, mutta käytämme nyt myös CSV:tä)
times = deque()
voltages = deque()
currents = deque()
powers = deque()
mahs = deque()
whs = deque()
temps = deque()

# Notification handler – kerää dataa
async def notification_handler(sender, data: bytearray):
    if len(data) != 36 or data[0] != 0xFF or data[1] != 0x55:
        print("Virheellinen paketti:", data.hex())
        return

    # Parsinta
    voltage = int.from_bytes(data[4:7], "big") / 100.0
    current = int.from_bytes(data[7:10], "big") / 100.0
    power = voltage * current
    mah = int.from_bytes(data[10:13], "big")
    wh = int.from_bytes(data[13:16], "big") / 100.0
    temp = int.from_bytes(data[21:23], "big")

    now = time.time()
    times.append(now)
    voltages.append(voltage)
    currents.append(current)
    powers.append(power)
    mahs.append(mah)
    whs.append(wh)
    temps.append(temp)

    # Tulosta konsoliin
    print(
        f"{time.strftime('%H:%M:%S')} | {voltage:.3f} V | {current:.3f} A | "
        f"{power:.2f} W | {mah} mAh | {wh:.3f} Wh | {temp} °C"
    )

    # Tallenna CSV:hen (append)
    with open(CSV_FILE, 'a', newline='') as f:
        f.write(f"{now},{voltage:.3f},{current:.3f},{power:.2f},{mah},{wh:.3f},{temp}\n")


# BLE-yhteys ja loop
async def main():
    print("Etsitään laitetta...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        print(f"Löydetty: {d.name or 'Ei nimeä'} ({d.address})")

    print(f"Yritetään yhdistää {DEVICE_MAC}...")
    async with BleakClient(DEVICE_MAC) as client:
        if not client.is_connected:
            print("Yhteys epäonnistui.")
            return

        print("Yhdistetty! Aktivoidaan notifikaatiot...")
        await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)

        # Start-komennot
        try:
            await client.write_gatt_char(NOTIFY_CHAR_UUID, bytearray([0xA5, 0x80]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(NOTIFY_CHAR_UUID, bytearray([0xA5, 0x01]))
        except Exception as e:
            print(f"Write epäonnistui (ei ehkä tarvita): {e}")

        print("Data virtaa... Paina Ctrl+C lopettaaksesi mittauksen.")

        try:
            await asyncio.sleep(3600)  # max 1 tunti
        except asyncio.CancelledError:
            pass
        finally:
            await client.stop_notify(NOTIFY_CHAR_UUID)


if __name__ == "__main__":
    # Poista vanha CSV ennen mittauksen alkua
    if os.path.exists(CSV_FILE):
        os.remove(CSV_FILE)
        print(f"Poistettu vanha tiedosto: {CSV_FILE}")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Lopetetaan (KeyboardInterrupt)...")
    except Exception as e:
        print(f"Virhe: {e}")
    finally:
        # Piirrä staattinen twin-axes-graafi
        try:
            # Lataa data – priorisoi CSV (koska deque voi tyhjentyä)
            if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
                df = pd.read_csv(CSV_FILE, header=None,
                                 names=['timestamp', 'voltage', 'current', 'power', 'mah', 'wh', 'temp'])
                df['time'] = df['timestamp'] - df['timestamp'].min()
                print(f"Data ladattu CSV:stä: {len(df)} pistettä")
            else:
                print("Ei dataa CSV:ssä – ei graafia.")
                df = pd.DataFrame()

            if not df.empty:
                fig, ax1 = plt.subplots(figsize=(12, 7))
                fig.suptitle("USB Tester Data – Vianetsintään optimoitu (Voltage + Current)", fontsize=16)

                # Vasen akseli: Voltage + Power (Power on usein lähempänä V:n skaalaa)
                ax1.plot(df['time'], df['voltage'], label='Voltage (V)', color='blue', linewidth=2)
                ax1.plot(df['time'], df['power'], label='Power (W)', color='red', linewidth=2, linestyle='--')
                ax1.set_xlabel('Time (s)')
                ax1.set_ylabel('Voltage (V) / Power (W)', color='black')
                ax1.tick_params(axis='y', labelcolor='black')
                ax1.grid(True, alpha=0.4)
                ax1.legend(loc='upper left')

                # Oikea akseli: Current (tärkein vianetsinnässä)
                ax2 = ax1.twinx()
                ax2.plot(df['time'], df['current'], label='Current (A)', color='green', linewidth=2.5)
                ax2.set_ylabel('Current (A)', color='green')
                ax2.tick_params(axis='y', labelcolor='green')
                ax2.legend(loc='upper right')

                fig.tight_layout()
                fig.savefig("usb_meter_vianetsinta.png", dpi=200, bbox_inches='tight')
                print("Graafi tallennettu: usb_meter_vianetsinta.png")

                plt.show()  # Ikkuna auki analysointia varten

        except Exception as e:
            print(f"Graafin piirto epäonnistui: {e}")

        print(f"Data tallennettu: {CSV_FILE}")