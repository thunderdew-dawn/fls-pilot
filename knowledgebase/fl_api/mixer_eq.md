# Interner FL Studio Mixer EQ

Dokumentation der internen FL Studio Mixer EQ API.

## API Funktionen
```python
mixer.getEqBandCount()

mixer.getEqGain(track, band, mode=0)
mixer.setEqGain(track, band, value)

mixer.getEqFrequency(track, band, mode=0)
mixer.setEqFrequency(track, band, value)

mixer.getEqBandwidth(track, band)
mixer.setEqBandwidth(track, band, value)
```

## Bänder
- Band `0` = Low
- Band `1` = Mid
- Band `2` = High

## Wichtige Regeln
- Setter erwarten **normalisierte Float-Werte**, nicht dB oder Hz. (`docs_confirmed`)
- `getEqGain(..., mode=1)` kann dB liefern. (`user_reported`)
- `getEqFrequency(..., mode=1)` kann Hz liefern. (`user_reported`)
- `setEqGain(...)` akzeptiert KEINE dB. (`docs_confirmed`)
- `setEqFrequency(...)` akzeptiert KEINE Hz. (`docs_confirmed`)
