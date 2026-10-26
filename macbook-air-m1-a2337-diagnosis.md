# MacBook Air M1 (A2337) — Won't Charge or Boot. What Now?

My son's five-year-old MacBook Air M1 had broken down, and I decided to try repairing it as a learning exercise. Repairing an old device also saves natural resources. Forums do warn that MacBooks are designed to last 4–5 years and cannot be repaired — but let's see about that.

## Initial Situation

The MacBook will not start or charge. No component appears to be getting warm. The MacBook uses Torx screws (sizes T4 and T5) and butterfly-shaped Pentalobe screws (1.2 mm). In the photo below, the Pentalobe screws are the shiny ones above the port connectors (small bracket pieces holding the connector in place — like the flat flex cable for the USB port on the left). [Opening guide on iFixit](https://www.ifixit.com/Guide/MacBook+Air+13-Inch+Late+2020+Logic+Board+Replacement/142562).

The logic board is type **820-02016**, and schematics and OpenBoardViewer images are [available at repair.wiki](https://repair.wiki/w/MacBook_Air_A2337).

### Voltages Measured on the Logic Board

**LOGIC BOARD DETACHED (NO CONNECTORS EXCEPT USB BOARD):**

- PPBUS_AON: 11.96V (C5804)
- PP3V8_AON_VDDMAIN: 3.79V (C5895)
- PP5V_S2: 5.18V (CP717)
- PP3V3_S2_UPC: 3.29V (CF751)
- PP3V3_UPC0_LDO: 3.27V (RF242)
- PP3V3_UPC1_LDO: 3.29V (CF508)
- PP1V5_UPC0_LDO_CORE: 1.59V (CF405)
- PP1V5_UPC1_LDO_CORE: 1.585V (CF505)
- PP1V8_AON: 1.801V (CR851)

**LOGIC BOARD IN PLACE AND ALL CONNECTORS:**

- PP1V8_S2: 1.796V (JR850)
- PP1V25_S2: 1.223V (JF202 PIN 12)

## Firmware Restore Attempt

A MacBook can sometimes get stuck in a boot loop due to corrupt firmware. Restoring it with Apple Configurator 2 on another Mac did not succeed — the software gave little indication of why. Firmware restoration is also possible on Linux using [idevicerestore](https://github.com/libimobiledevice/idevicerestore), where the log gives more detail about what is going wrong. The restore finds the logic board (in DFU mode) but cannot start the restore process:

```
Command: idevicerestore -e UniversalMac_26.2_25C56_Restore.ipsw
Found device in DFU mode
ECID: 7055480287406366
Identified device as j313ap, MacBookAir10,1
Device Product Version: N/A
Device Product Build: N/A
Extracting BuildManifest from IPSW
IPSW Product Version: 26.2
IPSW Product Build: 25C56 Major: 25
Device supports Image4: true
Variant: Customer Erase Install (IPSW)
This restore will erase all device data.
Performing macOS restore
##################################[ WARNING ]#################################
# You are about to perform an *ERASE* restore. ALL DATA on the target device #
# will be IRREVERSIBLY DESTROYED. If you want to update your device without  #
# erasing the user data, cancel now and restart without -e or --erase        #
# command line switch.                                                        #
# Type YES and press ENTER to continue, or hit CTRL+C to cancel.             #
##############################################################################
> YES
Checking IPSW for required components...
All required components found in IPSW
Getting ApNonce in DFU mode... 7e a0 3f 15 bd 03 bd 5b 79 cd c6 21 7b 76 39 d7 fa f4 e8 88 a3 ac 0a 19 12 c6 b7 d3 be cb 61 56
Trying to fetch new SHSH blob
Getting SepNonce in dfu mode... b2 86 47 9d fc b7 b7 96 ab 7f 80 9f a7 a3 60 eb 2a e3 ec 75
Received SHSH blobs
...
Extracting iBSS.j313.RELEASE.im4p (Firmware/dfu/iBSS.j313.RELEASE.im4p)...
Personalizing IMG4 component iBSS...
Sending iBSS (770863 bytes)...
Uploading [==================================================] 100.0%
Device did not reconnect in DFU or recovery mode. Possibly invalid iBSS. Reset device and try again.
Unable to place device into recovery mode from DFU mode
```

## While Measuring Logic Board Voltages…

During voltage measurements I noticed that diode D5270 was missing from the board. According to the schematics it is more closely related to battery charging, but since it should clearly be present, I ordered a replacement to be safe.

![Missing diode](samples/puuttuva_diodi.jpg)

Diode in OpenBoardViewer:

![OpenBoardViewer](samples/Openboardviewer.jpg)

The diode is 0.3 × 0.6 mm — a 0201 surface-mount component. On [Mouser Electronics](https://www.mouser.com/) the Zener diode X3-DFN06 (X3-DFN0603-2) costs €0.103; it is worth ordering several at once, because 0201 components have a habit of launching off tweezers and joining the dust on the floor.

The diode is so small it is barely visible to the naked eye. A microscope or good magnifying glass is essential.

![Microscope and logic board](samples/mikroskooppi.jpg)

I also ordered the J7-C USB power meter with Bluetooth. It turned out that cheap USB Bluetooth dongles may not support the older Bluetooth modes used by the meter, so I also had to get an ASUS USB-BT500 dongle for the Linux PC. The laptop's built-in Bluetooth supported the old modes, but I prefer not to code on a small screen.

I wrote an application for the USB meter that finds the UC96_BLE device via Bluetooth and logs the measured voltage, current, and power to a CSV file and plots it with matplotlib. When the MacBook tries to boot, voltage stays at 5V with occasional current spikes of around 0.18 A. 20 V never appears. The code is available on [Codeberg](https://codeberg.org/hiltsu/USB-Power-Meter).

Initially it seemed the fault might be in the SSD/NAND chips (a commonly reported failure on forums), but multimeter readings of the NAND AWAKE lines appeared to be at typical levels:

- PP0V88_AWAKE_NAND: 216.0 Ω (FLN001)
- PP1V25_AWAKE_NAND: 215.5 Ω (CN03A)
- PP2V5_AWAKE_NAND: 588 kΩ (RN522, varies)

The conclusion is that PD (Power Delivery) negotiation with the charger is failing. The MacBook Air apparently cannot request the required 20V from the power supply. Various cables and chargers have been tried — the fault is not in those.

## Soldering the Diode Back

Soldering the diode requires a good microscope, suitable solder paste, a hot air station, and nerves of steel. Start by cleaning the pads, then apply solder paste. The choice of paste matters.

Surrounding components can be protected with Kapton tape, but it will not survive long at hot air temperatures above 300°C.

Sn63Pb37 solder paste is suitable for soldering 0201 components. It contains Sn63Pb37 eutectic alloy with IPX3 flux, particle size Type 3 (25–45 µm). Its melting point is low (~183°C), resulting in less thermal stress on the component and board compared to lead-free alternatives.

The paste holds the diode in place, but positioning it correctly is nerve-racking — tweezers with tips larger than 1 mm tend to send the diode flying into the dust. Also remember: the diode's marked end is the cathode and must face toward FET Q5270.

I used a hot air station set to 340–350°C with the lowest possible airflow. I pre-heated the board to ~150–200°C first, then heated the diode for about a minute. The problem is that even with the smallest nozzle the airflow inevitably heats nearby components. Fortunately this diode is at the board edge — though I did melt the microscope stand plastic slightly when some air escaped sideways, which is why you can see a can opener (metal) shielding the stand in the photo.

After soldering, check the work with a multimeter — look for short circuits and verify the diode contacts are sound.

![Soldered diode](samples/juotos.jpg)

## Situation After Replacing the Diode

After soldering the diode, the situation changed.

The MacBook now negotiated 20V correctly with the power supply. However, current consumption remains low — not even the battery is being charged.

![20 volts negotiated correctly](samples/20v.jpg)

The restore now progresses further but still fails. The DFU mode has also changed:

```
sudo idevicerestore UniversalMac_26.2_25C56_Restore.ipsw
idevicerestore 1.0.0-268-g74e3bd9 (libirecovery 1.3.1, libtatsu 1.0.5-3-g60a39f3)
Found device in DFU mode
ECID: 7055480287406366
Identified device as j313ap, MacBookAir10,1
Device Product Version: N/A
Device Product Build: N/A
Extracting BuildManifest from IPSW
IPSW Product Version: 26.2
IPSW Product Build: 25C56 Major: 25
Device supports Image4: true
Variant: Customer Upgrade Install (IPSW)
This restore will update the device without erasing user data.
Performing macOS restore
Checking IPSW for required components...
All required components found in IPSW
Getting ApNonce in DFU mode... 52 d9 34 47 c0 b9 16 df 7d b1 8c 24 56 8a 9c e7 6a 57 ed a5 89 10 d5 26 0b 84 60 6b 61 d5 24 a0
...
Extracting iBSS.j313.RELEASE.im4p (Firmware/dfu/iBSS.j313.RELEASE.im4p)...
Personalizing IMG4 component iBSS...
Sending iBSS (770863 bytes)...
Uploading [==================================================] 100.0%
...
Personalizing IMG4 component Ap,LocalPolicy...
Sending Ap,LocalPolicy (3041 bytes)...
Uploading [==================================================] 100.0%
INFO: executing command: lpolrestore
Extracting t8103ciofw.im4p (Firmware/t8103ciofw.im4p)...
Personalizing IMG4 component Ap,RestoreCIO...
Sending Ap,RestoreCIO (179054 bytes)...
Uploading [                                                  ]   0.0% Unable to send Ap,RestoreCIO component: Unable to upload data to device
Unable to send Ap,RestoreCIO to device.
Unable to send component 'Ap,RestoreCIO' to device.
...
Unable to send iBoot stage 1 components to device
Unable to place device into recovery mode from DFU mode
```

According to the log, the following components fail to upload:

- **RestoreCIO** (I/O firmware)
- **RestoreTMU** (thermal / timing / power domain)
- **RestoreANS** (Apple Neural/ANS subsystem)
- **RestoreDCP** (Display Co-Processor)

What is working:

- SoC (M1 / T8103) is alive
- Secure Enclave is alive
- DFU USB communication works at least up to iBSS level

Voltage sometimes drops back to 5V, and pressing Control-Option-Shift + Power brings it back to 20V — though not always. This key combination resets the SMC equivalent in Apple Silicon and forces the USB-C PD controller to reinitialise.

The behaviour is not consistent: sometimes voltage rises to 20V and stays there, but then idevicerestore drops it back to 5V at the moment it should be transitioning out of DFU mode.

Comparing against the restore log:

- iBSS → OK (very low current draw)
- Next stage → RestoreCIO / RestoreTMU / RestoreANS
- As soon as clocks, fabric, and I/O additional power rails should come up, power is absent, USB transfer dies, and PD falls back / stalls to 5V.

The fault most likely lies in one of the following:

- USB-C / PD / CD3217B2 controller (classic symptom: 20V without load)
- PMIC or its power rail → SoC blocks power draw
- Short or leakage on a SoC power domain
- ESD or mechanical damage in the I/O area

## Next Steps

The CD3217B2 controller chips can in principle be [replaced at home](https://youtu.be/7HCq6pQzZ8g?si=F2d4epomjaKyzqB3) (YouTube video), but my motivation to continue is limited — the fault could still be elsewhere. The positives from this exercise were:

- My diagnostic skills improved further
- I learned surface-mount soldering and how to work with sub-millimetre components
- I wrote a working Python script that can log battery charging on phones and other devices
- I found that I stayed calm even when things got difficult

If anyone needs the device for parts, the screen, case, keyboard, speaker, and battery can all be salvaged. Recycling components reduces environmental impact — if you want to find something positive in this project.

Thank you for reading!

---

## License

MIT License

Copyright (c) 2025 Jari Hiltunen (Codeberg: [hiltsu](https://codeberg.org/hiltsu))

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
