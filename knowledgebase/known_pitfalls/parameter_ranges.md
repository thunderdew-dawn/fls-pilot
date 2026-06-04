# Pitfall: Parameter Ranges & Units

Viele FL-Studio-Setter erwarten normalisierte Werte von `0.0` bis `1.0`.
UI-Werte, dB, Hz, Prozent, MIDI-CC und normalisierte Werte **dürfen nicht vermischt werden.**

**Beispiel falsch:**
```python
mixer.setEqGain(5, 0, -14)
```

**Beispiel richtig (High-Level-Wrapper):**
```python
set_internal_mixer_eq_gain_db(track=5, band=0, db=-14)
```

**Beispiel richtig (API mit kalibrierter Kenntnis):**
```python
mixer.setEqGain(5, 0, 0.2502)
```
