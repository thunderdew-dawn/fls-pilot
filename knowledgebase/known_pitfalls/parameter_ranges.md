# Pitfall: Parameter Ranges & Units

Many FL Studio setters expect normalized values from `0.0` to `1.0`.
UI values, dB, Hz, percentages, MIDI-CC, and normalized values **must not be mixed.**

**Incorrect Example:**
```python
mixer.setEqGain(5, 0, -14)
```

**Correct Example (Public MCP domain tool with calibrated knowledge):**
```python
fl_effect(action="set_eq_band", params={"track": 5, "band": 0, "gain": 0.2502})
```

**Correct Example (API with calibrated knowledge):**
```python
mixer.setEqGain(5, 0, 0.2502)
```
