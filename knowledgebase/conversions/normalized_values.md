# Normalisierte Werte vs. Reale Einheiten

Viele FL-Studio-Setter erwarten normalisierte Werte von `0.0` bis `1.0`.
- **dB, Hz, Prozent, MIDI-CC und normalisierte Floats** sind grundverschiedene Domänen.
- **Getter** können (je nach `mode`) reale Einheiten liefern, während **Setter** trotzdem normalisierte Werte verlangen.
- **Readback ist Pflicht**, wenn präzise Zielwerte ohne vollständiges Kalibrierungs-Mapping gesetzt werden sollen.
