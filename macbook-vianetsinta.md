# USB Digital Testerin (J7-c) käyttäminen MacBook Air -vianetsintään

Tässä artikkelissa kerron miten voit halvalla Aliexpress-mittarilla (kuvassa alla) mitata USB lataukseen liittyvät tiedot. Käytetty testeri löytyy hakusanalla USB Tester Type-C PD Digital Capacity Meter 8A Voltage Current Monitor Power Bank Charger Detector with QC3.0 Fast Charging. Tässä mallissa on Bluetooth-yhteys ja toimii kaksisuuntaisesti, eli input ja output liitännät voi käyttää päinvastoin.

Mittari maksaa toimituskuluineeen noin 14 euroa. Laitteen mukana tulevan ohjekirjan mukaan Play-kaupasta voisi ladata Androidille E-Test sovelluksen, mutta se on tarkoitettu todella vanhoille Androideille. Laite on toki sopiva latauskaapeleiden ja laitteiden kunnon mittaamiseen ilman sovellustakin. Näytössä on useampi mode, joissa myös trendikuvia.

--

Huomaa, että esimerkiksi Xiaomin Turbo-lataus ei perustu PD-lataukseen. Xiaomi käyttää usein USB-A → USB-C -kaapelia (punainen sisus) Turbo Chargelle, jossa on erikoinen eMarker / lisäpinni PD-viestintään (ei standardi USB-C → USB-C). Mikäli haluat käyttää alla olevaa Python-scriptiä epästandardiin lataukseen, katso raw hex-arvot ja sovita ne mittaukseesi. Mittarin VBUS-arvot näyttävät muuten väärin.

Esimerkki: jos mittari lähettää: **ff5501030002100000be0001d3000000fb00560056001f000010053c0c80000003200029**

Puretaan se osiin (offset 0–35):

- **0–1**: ff 55 → header (kiinteä)
- **2**: 01 → message type (raportti)
- **3**: 03 → device/subtype (USB-mittari)
- **4–6**: 00 02 10 → voltage 0x000210 = 528 → 5.28 V
- **7–9**: 00 00 be → current 0x0000be = 190 → 1.90 A
- **10–12**: 00 01 d3 → mAh 0x0001d3 = 467 mAh
- **13–15**: 00 00 00 → Wh 0x000000 = 0.00 Wh
- **16**: fb → tuntematon (ehkä flags tai mode)
- **17–18**: 00 56 → D+ 0x0056 = 86 → 0.86 V
- **19–20**: 00 56 → D- 0x0056 = 86 → 0.86 V
- **21–22**: 00 1f → temperature 0x001f = 31 °C
- **23–25**: 00 00 10 → tuntematon (ehkä aika / counter)
- **26–28**: 05 3c 0c → tuntematon (ehkä impedance/resistance tai runtime-osia)
- **29–31**: 80 00 00 → tuntematon (ehkä group / preset)
- **32–34**: 03 20 00 → tuntematon (ehkä lisästatus)
- **35**: 29 → **checksum** (yleensä XOR tai summa koko paketista ilman viimeistä byteä)


Mitä näistä muista byteista yleensä saadaan selville?

Yleisimmät lisäarvot, joita eri reverse engineering -projektit (atorch-console, J7-C-loggerit, sigrok, Arduino-forumit ym.) ovat löytäneet:

- **D+ / D- jännitteet** (offset ~17–20): USB-datapinnit, tärkeitä pikalatausprotokollien (QC, PD, Apple 2.4A) tunnistamiseen.
- **Lämpötila** (offset ~21–22): Sisäinen lämpötila (NTC-anturi testerissä).
- **Resistance / Load Impedance** (usein offset ~26–28 tai 29–31): Kuormituksen resistanssi (mΩ tai Ω).
- **Charging time / Runtime** (usein 3–4 tavua jossain kohdassa): Kuinka kauan virtaa on ollut päällä (sekunteina tai BCD-muodossa).
- **Group number** / preset: Mihin "muistipaikkaan" data tallentuu testerissä.
- **Checksum** (viimeinen tavu): Usein XOR kaikista edellisistä byteista tai simppeli summa mod 256.

---

## USB-C PD


USB-C **Power Delivery (PD)** -neuvottelu (tunnetaan myös nimellä **USB PD handshake** tai **power contract negotiation**) on se prosessi, jolla USB-C-laitteet (esim. laturi ja puhelin/MacBook) sopivat yhdessä, millä jännitteellä, virralla ja teholla virtaa siirretään turvallisesti ja tehokkaasti. Se tapahtuu **Configuration Channel** -linjojen (CC1 ja CC2) yli, jotka ovat USB-C-liittimen neljästä ylimääräisestä pinnistä kaksi. Näitä käytetään sekä roolien selvittämiseen että digitaaliseen viestintään.

### Vaihe vaiheelta – miten PD-neuvottelu menee käytännössä


1. **Liitäntä ja alustava roolien selvitys (Connection & Orientation Detection)**  

Kun kaapeli yhdistetään, laitteet mittaavat CC-linjojen jännitteitä (pull-up/down-resistorit).  Tämä selvittää:  

- Kumpi on **Source** (laturi, antaa virtaa) ja kumpi **Sink** (laite, ottaa virtaa).  
- Kaapelin suunta (USB-C on käännettävä, joten CC1/CC2 vaihtuivat).  


Aluksi virtaa annetaan **aina 5 V** (ja yleensä 0.9–3 A) – tämä on USB-C:n oletus "legacy"-tasolla, jotta vanhat laitteet toimivat ilman PD:ta.  Jos jommallakummalla puolella ei ole PD-kykyä → jäädään 5 V / max 15 W tasolle (ei neuvottelua).

2. **Source Capabilities -viesti (laturi kertoo mitä se osaa)**  

**Source** (laturi) lähettää **Source_Capabilities**-viestin (yleensä heti kun yhteys on varma). Viesti sisältää listan **Power Data Objects** (PDO):sta – eli tarjolla olevat jännite/virta-yhdistelmät.  

Esimerkki tyypillisestä laturista:  

- PDO1: 5 V @ 3 A (15 W) – pakollinen kaikille PD-latureille  
- PDO2: 9 V @ 3 A (27 W)  
- PDO3: 15 V @ 3 A (45 W)  
- PDO4: 20 V @ 5 A (100 W)  
- PPS (Programmable Power Supply) -alueet, esim. 3.3–21 V @ 5 A (erittäin tarkka säätö)  


Viesti lähetään **BMC-koodatulla** (Biphase Mark Coding) signaalilla CC-linjalla (~300 kbit/s).

3. **Sink Request -viesti (laite pyytää haluamaansa)**  

 **Sink** (esim. MacBook tai puhelin) lukee tarjolla olevat PDO:t.  Se valitsee itselleen sopivimman (yleensä maksimitehon, mutta laitteen rajoitusten mukaan).  

Esimerkki:  

- MacBook Air pyytää 20 V / 3 A (60 W) jos laturi tukee.  
- Puhelin pyytää 9 V / 3 A (27 W) jos tukee.  


Laite lähettää **Request**-viestin, jossa on **Request Data Object (RDO)**: haluttu PDO-indeksi + virran määrä.

4. **Source Accept / Reject + PS_Ready**  

Laturi vastaa:  

- **Accept** (jos ok) → sitten **PS_Ready** (Power Supply Ready) – kertoo että jännite on nyt muutettu pyydetyksi.  
- **Reject** (jos ei pysty, esim. ylikuormitus tai kaapeli ei tue) → jäädään edelliseen sopimukseen (yleensä 5 V).  


Kun PS_Ready saapuu → virransyöttö muuttuu pyydetyksi jännitteeksi/virraksi (esim. 5 V → 20 V muutamassa kymmenessä millisekunnissa).

5. **Power contract on voimassa**  

Nyt virtaa siirretään sovitulla tavalla. Laite voi myöhemmin pyytää muutosta (esim. jos akku lämpenee → alempi teho).  Jos yhteys katkeaa tai virhe → palataan oletus 5 V:hen (Hard Reset / Cable Reset). 
### Mitä testeri näkee näissä vaiheissa?


Aluksi aina 5 V (ennen neuvottelua). D+ / D- pinnit voivat olla mukana joissain vanhemmissa pikalatausprotokollissa (QC, Apple 2.4A), mutta **PD käyttää vain CC-linjoja** – D+/D- voivat olla 0–0.9 V (data pois päältä) tai korkeammat jos käytössä Apple/BC 1.2 -tuki.   Jos neuvottelu epäonnistuu → jää 5 V:iin, vaikka laturi tukee 100 W → virta jää pieneksi (esim. 0.5–1.5 A).
### Yhteenveto vianetsintään


Jos MacBook Air latautuu hitaasti:

- Tarkista virta (A): Jos alle 2–3 A vaikka laturi on 60–100 W → neuvottelu epäonnistui (väärä kaapeli, likainen portti, viallinen laturi tai kaapeli ei tue PD:tä kunnolla).  
- Tarkista jännite (V): Jos jää 5 V:hen → ei PD-sopimusta.  
- Teho (W) kertoo kokonaistilanteen, mutta vian syy löytyy yleensä V + A -yhdistelmästä.

![USB Power Meter MacBookissa](samples/20v.jpg)

---
