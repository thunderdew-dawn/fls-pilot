# Mixer EQ Kalibrierungs-Prozedur

Anleitung zur Ermittlung verlässlicher Mappings für `setEqGain` und `setEqFrequency`.

## Vorgehen
1. **Nur auf leerem Test-Mixer-Track testen.** Nicht während produktiver Sessions.
2. Vorher Projekt speichern.
3. Testwerte in kleinen Schritten (`0.0` bis `1.0`) setzen.
4. Nach jedem Setzen den Wert mit `getEqGain(track, band, mode=1)` oder `getEqFrequency(track, band, mode=1)` zurücklesen.
5. Ergebnisse in `mixer_eq_calibration.json` eintragen.
6. **Keine Annahmen über lineare Mappings treffen.**
7. FL-Studio-Version, API-Version und Plattform im JSON dokumentieren.

## JSON Beispiel-Fragment
```json
{
  "normalized": 0.2502,
  "db": -14.0,
  "confidence": "user_reported",
  "source": "user_reported"
}
```
