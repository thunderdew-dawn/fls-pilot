# MCP Tool Policy

## Tool-Hierarchie
1. **High-Level Safe Tools verwenden** (z. B. `set_internal_mixer_eq_gain_db`).
2. **Kalibrierte Conversion Tools verwenden**, falls keine High-Level-Tools verfügbar sind.
3. **Raw FL Studio API nur als Last Resort** (z. B. `mixer.setEqGain`).
4. **Niemals normalisierte Werte raten!**

## Beispiele
**Verboten:**
```python
mixer.setEqGain(5, 0, -14)
```
*(Grund: `-14` ist ein dB-Wert, aber `mixer.setEqGain` erwartet einen normalisierten Float).*

**Erlaubt:**
```python
set_internal_mixer_eq_gain_db(track=5, band="low", db=-14)
```
