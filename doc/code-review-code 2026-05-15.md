# Code Review Memo fuer src/code.py

Stand: 2026-05-15

Gepruefte Datei: `src/code.py`

## Kurzfazit

Die Uhrlogik ist fuer den Normalfall mit funktionierendem WLAN brauchbar, hat aber einen kritischen Architekturfehler beim Fehlerpfad: Netzwerk und NTP werden vor Display-Initialisierung und vor dem Hauptloop zwingend erfolgreich abgeschlossen. Dadurch ist die Uhr in Offline-Szenarien nicht degradiert betriebsfaehig, sondern kann komplett am Start haengen oder spaeter nach laengerem Netzwerkausfall in genau diesen haengenden Startzustand zurueckfallen.

## Findings

### 1. Kritisch: Kaltstart ohne Netzwerk blockiert die komplette Uhr dauerhaft

Fundstelle: `src/code.py:115-128`, `src/code.py:136-141`, `src/code.py:520`

Der Startpfad verbindet WLAN in einer aeusseren Endlosschleife:

- `while not esp.is_connected:` laeuft unbegrenzt.
- Nach jedem Timeout wird nur `esp.reset()` ausgefuehrt und derselbe Verbindungsversuch wiederholt.
- Display, Sensorinitialisierung und `asyncio.run(main())` werden erst danach erreicht.

Praktische Folge:

- Fall 1, "Uhr startet neu ohne Netzwerkzugang", ist aktuell nicht abgedeckt.
- Die Uhr zeigt in diesem Fall weder eine zwischengespeicherte Zeit noch einen Fehlerstatus an.
- Falls das WLAN-Passwort fehlt oder das Access Point nicht erreichbar ist, bleibt das Geraet im Bootpfad haengen.

Empfehlung:

- Display und Hauptloop vor die Netzwerkpflicht verschieben.
- WLAN/NTP als optionale Hintergrundfunktion behandeln.
- Einen Offline-Modus definieren: letzte RTC-Zeit anzeigen, Netzstatus kennzeichnen, spaeter periodisch reconnecten.

### 2. Kritisch: Laengerer Netzwerkausfall im Betrieb fuehrt spaetestens nach etwa einer Stunde zum Totalausfall

Fundstelle: `src/code.py:165-178`, `src/code.py:182-198`, `src/code.py:478-482`

Bei jedem fehlgeschlagenen NTP-Sync wird `consecutive_failures` erhoeht. Nach `MAX_CONSECUTIVE_FAILURES = 12` Fehlern wird das ESP-Modul hart resettet. Wenn die Reconnect-Phase danach scheitert, folgt `microcontroller.reset()`.

Mit `NTP_RETRY_INTERVAL = 300` Sekunden passiert das nach grob:

$$12 \times 300\,s = 3600\,s = 1\,h$$

Praktische Folge fuer Fall 3, "Netzwerk setzt fuer einen Tag aus":

- Zunaechst laeuft die Anzeige weiter mit RTC-Zeit.
- Nach etwa einer Stunde ohne erfolgreiche Reconnects erzwingt der Code aber einen kompletten Board-Reset.
- Nach diesem Reset landet das Geraet wieder im blockierenden Bootpfad aus Finding 1.
- Die Uhr ist damit nach laengerem Ausfall nicht mehr sichtbar in Betrieb, obwohl die RTC prinzipiell weiterlaufen koennte.

Empfehlung:

- Keinen Board-Reset nur wegen fehlendem Netzwerk erzwingen.
- Nach ESP-Reset in den Offline-Betrieb zurueckfallen statt `microcontroller.reset()` aufzurufen.
- Reconnect/NTP weiter mit Backoff versuchen, waehrend die Anzeige weiterlaeuft.

### 3. Hoch: Der erste NTP-Zugriff ist ungeschuetzt und verhindert robustes Degradieren schon beim Start

Fundstelle: `src/code.py:136-141`

Bereits beim Erzeugen der NTP/RTC-Basis werden `ntp.datetime` und `rtc.datetime = ntp.datetime` direkt auf Modulebene ausgefuehrt. Dieser Pfad ist nicht von `try/except` geschuetzt. Selbst wenn die WLAN-Verbindung formal steht, aber DNS, Routing oder der NTP-Server selbst stoeren, scheitert der Startpfad vor der Anzeige.

Praktische Folge:

- "WLAN verbunden" ist nicht gleich "Zeitserver erreichbar".
- Ein partieller Netzausfall beim Start verhindert den Uebergang in einen degradierbaren Laufzeitmodus.

Empfehlung:

- Initiales NTP-Sync in denselben fehlertoleranten Pfad verlegen wie spaetere Resyncs.
- RTC nur dann setzen, wenn der NTP-Lesezugriff erfolgreich war.

### 4. Mittel: Sensorwerte werden ohne CRC-Pruefung verwendet

Fundstelle: `src/code.py:328-344`

Der SHT40 liefert zu Temperatur und Feuchte CRC-Bytes mit. Der Code liest zwar alle 6 Bytes, ignoriert aber beide CRC-Bytes vollstaendig.

Praktische Folge:

- I2C-Stoerungen koennen unbemerkt als scheinbar gueltige Messwerte im Display landen.
- Genau in langen Laufzeiten auf einer LED-Matrix ist das vermeidbarer Datenmuell.

Empfehlung:

- Sensirion-CRC fuer beide Messwerte pruefen.
- Bei CRC-Fehler den letzten gueltigen Messwert behalten und den Fehler loggen.

### 5. Mittel: Das Modul mischt Bootlogik, Hardware-Setup und Dauerbetrieb in einem einzigen Top-Level-Skript

Fundstelle: `src/code.py:77-520`

Fast der gesamte relevante Kontrollfluss liegt auf Modulebene. Dadurch ist das Verhalten schwer isoliert testbar, und Ausfallpfade lassen sich kaum getrennt simulieren.

Praktische Folge:

- Keine saubere Zustandsmaschine fuer `booting`, `offline`, `online`, `degraded`, `recovering`.
- Kaum Moeglichkeit fuer gezielte Tests der drei geforderten Faelle.

Empfehlung:

- In klar getrennte Phasen aufteilen: `init_display()`, `init_sensor()`, `try_connect_wifi()`, `try_sync_time()`, `run_clock_loop()`.
- Den Laufzeitstatus explizit in Variablen oder einer kleinen Zustandsmaschine abbilden.

### 6. Niedrig: `ts_clocktick` wird gepflegt, aber nirgends fuer die Anzeige verwendet

Fundstelle: `src/code.py:59`, `src/code.py:147`, `src/code.py:161`

`ts_clocktick` wird initialisiert und bei erfolgreichem NTP-Sync neu gesetzt, danach aber nicht mehr genutzt. Die Anzeige basiert auf `rtc.datetime`.

Praktische Folge:

- Toter Zustand, der die Logik schwerer lesbar macht.
- Es bleibt unklar, ob einmal ein softwarebasierter Tick-Mechanismus geplant war.

Empfehlung:

- Entweder entfernen oder konsequent als einzige Zeitbasis verwenden.

## Ablauf der Uhrlogik im Ist-Zustand

### A. Gemeinsamer Startpfad

1. Konstanten und globale Statusvariablen werden initialisiert.
2. WLAN-Zugangsdaten werden aus `settings.toml` via `os.getenv()` gelesen.
3. ESP32-SPI-WLAN wird initialisiert.
4. Das Programm versucht unbegrenzt, sich mit dem WLAN zu verbinden.
5. Erst nach erfolgreicher WLAN-Verbindung werden Socket-Pool, NTP und RTC eingerichtet.
6. Erst danach werden Matrix-Display, Startlogos und Sensor eingerichtet.
7. Danach werden Labels erzeugt und `asyncio.run(main())` startet.
8. Im Hauptloop wird jede Sekunde `clocktick()` aufgerufen.
9. `clocktick()` prueft, ob ein NTP-Resync faellig ist, und aktualisiert danach die Anzeige.
10. `update_display()` liest periodisch den Sensor neu, berechnet CET/CEST und rendert Uhrzeit und Messwerte.

Wichtige Konsequenz:

- Alles vor Schritt 6 ist aktuell kritisch fuer das Ueberleben der Uhr. Wenn Schritt 4 oder 5 scheitert, gibt es keine Anzeige.

## Szenarioanalyse

### 1. Uhr startet neu ohne Netzwerkzugang

Ist-Ablauf:

1. Das Geraet bootet und liest SSID/Passwort.
2. `esp.connect_AP(...)` wird wiederholt versucht.
3. Nach `WIFI_CONNECT_TIMEOUT` wird das ESP resettet.
4. Danach beginnt derselbe Versuch erneut.
5. Display-Setup wird nie erreicht.
6. `main()` wird nie gestartet.

Ergebnis im Ist-Zustand:

- Keine Uhranzeige.
- Kein Offline-Fallback.
- Kein Sensorbetrieb.
- Kein begrenzter Retry mit spaeterem Uebergang in Normalbetrieb.

Was die Uhr in diesem Fall fachlich tun sollte:

1. Sofort Display initialisieren.
2. Wenn RTC noch eine sinnvolle Zeit hat, diese anzeigen.
3. Falls RTC ungueltig ist, einen klaren Status wie `--:--` oder `NO NET` anzeigen.
4. WLAN/NTP im Hintergrund retryen, ohne die Anzeige zu blockieren.

### 2. Uhr startet normal und Netzwerk funktioniert

Ist-Ablauf:

1. WLAN verbindet erfolgreich.
2. NTP liefert Zeit.
3. RTC wird auf UTC gesetzt.
4. Display zeigt Startlogos.
5. Sensor wird einmal initial gelesen.
6. Hauptloop startet.
7. Anzeige nutzt fuer die Uhrzeit `rtc.datetime` plus CET/CEST-Offset.
8. Alle 10 Sekunden werden Sensorwerte erneuert.
9. Alle 6 Stunden wird NTP erneut abgefragt.

Ergebnis im Ist-Zustand:

- Dieser Fall funktioniert weitgehend wie erwartet.
- Die Anzeige bleibt auch zwischen den NTP-Syncs stabil.

Restrisiken:

- Ein Fehler bei der initialen NTP-Abfrage beendet den robusten Startpfad trotzdem.
- Sensorwerte koennen bei Busfehlern ohne CRC unplausibel werden.

### 3. Uhr startet normal und mit Netzwerk, aber irgendwann setzt das Netzwerk fuer einen Tag aus

Ist-Ablauf:

1. Die Uhr laeuft zunaechst normal.
2. Netzwerk faellt spaeter aus, die RTC laeuft lokal weiter.
3. Solange kein NTP-Sync faellig ist, merkt die Anzeige davon kaum etwas.
4. Beim naechsten faelligen NTP-Sync erkennt `sync_time_via_ntp()` die Trennung und versucht `reconnect_wifi()`.
5. Bei Fehlschlag wird `ts_lastntpsync` so gesetzt, dass der naechste Versuch nach 5 Minuten erfolgt.
6. Nach 12 solchen Fehlschlaegen wird das ESP-Modul resettet.
7. Wenn auch danach innerhalb von 30 Sekunden kein Reconnect gelingt, folgt `microcontroller.reset()`.
8. Nach dem Board-Reset gilt wieder Szenario 1.

Ergebnis im Ist-Zustand:

- Kurzfristige Ausfaelle sind tolerierbar.
- Ein Tagesausfall ist nicht tolerierbar, weil die Uhr nach etwa einer Stunde in einen Reset-Zyklus kippt und danach am Boot haengen bleibt.

Was die Uhr in diesem Fall fachlich tun sollte:

1. Weiterhin RTC-Zeit anzeigen.
2. Sichtbar markieren, dass die Zeit seit letzter NTP-Synchronisation nur noch lokal laeuft.
3. Reconnect mit wachsendem Backoff versuchen.
4. Nach Netzrueckkehr sofort oder beim naechsten Retry NTP-Sync nachholen.
5. Niemals die Anzeige allein wegen Netzverlust abschalten.

## Empfohlene Soll-Architektur

### Minimal robust

1. Display immer zuerst initialisieren.
2. RTC und Anzeige unabhaengig vom Netzwerk starten.
3. WLAN-Verbindung asynchron und fehlertolerant behandeln.
4. NTP-Sync optional im Hintergrund ausfuehren.
5. Einen Status wie `ONLINE`, `RTC`, `NO NET`, `NTP ERR` intern fuehren.

### Praktische Zustandsfolge

1. `BOOT`
2. `DISPLAY_READY`
3. `RTC_ONLY`
4. `WIFI_CONNECTED`
5. `NTP_SYNCED`
6. `NETWORK_DEGRADED`
7. `RECOVERED`

Damit werden alle drei geforderten Faelle sauber modellierbar und testbar.

## Testfaelle, die aktuell fehlen

1. Boot ohne erreichbares WLAN.
2. Boot mit WLAN, aber ohne erreichbaren NTP-Server.
3. Laufzeitbetrieb mit RTC-Anzeige und spaeterem WLAN-Verlust fuer mehr als 1 Stunde.
4. Rueckkehr des WLAN nach mehreren fehlgeschlagenen Retries.
5. Sensor-Lesefehler und CRC-Fehler.

## Prioritaet fuer eine Nachbesserung

1. Bootpfad entkoppeln: Uhr muss ohne Netz sichtbar laufen koennen.
2. Board-Reset bei langem Netzausfall entfernen.
3. Initiales NTP-Sync robust machen.
4. Sensor-CRC nachziehen.
5. Top-Level-Skript in klar testbare Initialisierungs- und Laufzeitfunktionen zerlegen.