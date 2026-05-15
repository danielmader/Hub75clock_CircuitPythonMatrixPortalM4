# Code Review Memo fuer src/code.py

Stand: 2026-05-15

Gepruefte und ueberarbeitete Datei: `src/code.py`

## Status

Die frueheren Hauptprobleme aus dem Review sind inzwischen umgesetzt:

- Der Start ist jetzt offline-first und blockiert nicht mehr auf WLAN oder NTP.
- Bei Netzwerkausfall bleibt die Uhr sichtbar in Betrieb und versucht spaetere Reconnects und NTP-Resyncs weiter.
- Der SHT40-Pfad prueft jetzt beide CRC-Bytes.
- Die Anzeige hat nun eine kleine Statuslogik ueber 2x2-Pixelmarker in den oberen Ecken.

## Aktueller Ablauf der Uhrlogik

### 1. Bootphase

1. Konstanten, Retry-Timer und globale Statuswerte werden initialisiert.
2. WLAN-Zugangsdaten werden aus `settings.toml` gelesen.
3. ESP32-SPI-WLAN wird initialisiert.
4. Die Firmware geht danach sofort weiter, auch wenn noch kein WLAN steht.
5. Display, Startlogos, Sensor und Labels werden aufgebaut.
6. Der Hauptloop startet mit `asyncio.run(main())`.

Wichtige Folge:

- Die Uhr ist nach dem Boot sichtbar, auch wenn zu diesem Zeitpunkt weder WLAN noch NTP verfuegbar sind.

### 2. Laufzeitphase

1. `clocktick()` laeuft einmal pro Sekunde.
2. Zuerst wird `maintain_wifi_connection()` aufgerufen.
3. Wenn kein WLAN besteht und der Retry-Timer es erlaubt, wird ein kurzer Verbindungsversuch gestartet.
4. Danach entscheidet `sync_time_via_ntp()`, ob ein NTP-Sync faellig ist.
5. Ist ein Sync faellig und WLAN vorhanden, wird der NTP-Client bei Bedarf lazy initialisiert.
6. Direkt vor dem blockierenden NTP-Zugriff wird der linke Marker im Blinkzustand ins Display gerendert.
7. Bei erfolgreichem Sync werden RTC, `ts_clocktick` und `ts_lastntpsync` aktualisiert.
8. Bei Fehlschlag wird der naechste NTP-Versuch nach `NTP_RETRY_INTERVAL` geplant.
9. Anschliessend aktualisiert `update_display()` Uhrzeit, Sensorwert und Statusmarker.

## Statusmarker im Display

### Linke obere Ecke, 2x2 Pixel, amber

- Aus: RTC vorhanden und letzter NTP-Sync noch innerhalb von `NTP_INTERVAL`.
- Dauerhaft an: letzter erfolgreicher NTP-Sync ist ueberfaellig.
- Blinkend: Es gab noch nie einen erfolgreichen NTP-Sync.
- Blinkend: Ein NTP-Sync wird gerade ausgefuehrt.

### Rechte obere Ecke, 2x2 Pixel, rot

- Aus: WLAN verbunden.
- An: aktuell kein WLAN verbunden.

### Kombinationen

- Keine Marker: RTC ok, WLAN ok, letzter NTP-Sync noch gueltig.
- Nur links blinkend: Noch nie synchronisiert oder Sync laeuft gerade.
- Nur links dauerhaft: Letzter NTP-Sync ist ueberfaellig.
- Nur rechts: Kein WLAN, NTP ist aber noch nicht ueberfaellig oder es gab noch keinen separaten linken Zustand.
- Links und rechts gleichzeitig: Kein WLAN und letzter NTP-Sync ist ueberfaellig.

## Szenarioanalyse mit aktuellem Code

### 1. Uhr startet neu ohne Netzwerkzugang

1. Das Geraet bootet normal bis ins Display.
2. Die Uhr zeigt sofort die RTC-basierte Zeit an.
3. Rechts oben leuchtet der rote Marker fuer `No Net`.
4. Links oben blinkt amber, solange noch nie ein erfolgreicher NTP-Sync stattgefunden hat.
5. Das Geraet versucht spaeter immer wieder kurze WLAN-Reconnects.
6. Sobald WLAN spaeter verfuegbar wird, kann ein NTP-Sync nachgeholt werden.

Ergebnis:

- Die Uhr bleibt sichtbar und betriebsfaehig.
- Spaetere Synchronisationen werden nicht verhindert.

### 2. Uhr startet normal und Netzwerk funktioniert

1. Das Geraet bootet normal.
2. Der Hauptloop startet sofort.
3. WLAN wird verbunden.
4. Der erste NTP-Sync wird ausgefuehrt; waehrenddessen blinkt links oben der amber Marker.
5. Nach erfolgreichem Sync verschwinden beide Marker.
6. Spaetere Resyncs laufen nach `NTP_INTERVAL` erneut.

Ergebnis:

- Normalbetrieb ohne dauerhafte Marker.
- Sync-Vorgaenge sind kurz sichtbar, ohne die Uhr in einen Fehlerzustand zu bringen.

### 3. Uhr startet normal und mit Netzwerk, aber irgendwann setzt das Netzwerk fuer einen Tag aus

1. Die Uhr laeuft zunaechst normal.
2. Wenn WLAN spaeter ausfaellt, erscheint rechts oben der rote Marker.
3. Solange der letzte Sync noch innerhalb von `NTP_INTERVAL` liegt, bleibt links aus.
4. Wird der Sync ueberfaellig, erscheint links oben der amber Marker.
5. Die Uhr laeuft weiter ueber die RTC.
6. WLAN-Reconnects und spaetere NTP-Syncs werden weiter versucht.
7. Nach Rueckkehr des WLAN kann ein spaeterer NTP-Sync wieder erfolgreich werden.

Ergebnis:

- Kein Board-Reset allein wegen Netzverlust.
- Die Uhr bleibt sichtbar.
- Die Logik blockiert spaetere Resyncs nicht.

## CRC-Pruefung fuer SHT40

Der Sensorpfad prueft jetzt beide vom SHT40 gelieferten CRC-Bytes:

- Temperaturblock: Bytes 0 bis 2
- Feuchteblock: Bytes 3 bis 5

Bei CRC-Fehlern wird die Messung verworfen. Die Anzeige behaelt dadurch den letzten gueltigen Sensorwert statt moegliche Busfehler als Messwert darzustellen.

## Restrisiken

1. Die RTC-Guete haengt weiterhin davon ab, dass irgendwann mindestens ein erfolgreicher NTP-Sync stattgefunden hat.
2. Waehrend eines blockierenden NTP-Zugriffs ist die CPU kurz beschaeftigt; der Blinkmarker wird aber unmittelbar davor ins Display geschrieben und ist dadurch trotzdem sichtbar.
3. Der Code ist weiterhin stark skriptbasiert aufgebaut und nicht als saubere Zustandsmaschine oder in kleine testbare Initialisierungsfunktionen zerlegt.

## Sinnvolle weitere Tests

1. Boot ohne WLAN und spaetere Rueckkehr des WLAN.
2. Boot mit WLAN, aber NTP-Server nicht erreichbar.
3. Netzwerkausfall laenger als `NTP_INTERVAL`, danach Rueckkehr.
4. Absichtlicher Sensor-CRC-Fehler oder I2C-Stoerung.
5. Sichtpruefung der Blinkmarker auf realer Hardware.