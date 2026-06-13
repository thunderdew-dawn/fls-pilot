# Open Questions

- Measure exact dB mapping for `mixer.setEqGain`.
- Measure exact Hz mapping for `mixer.setEqFrequency`.
- Measure Bandwidth/Q behavior.
- Document FL Studio version, API version, and platform.
- Check if behavior is identical on macOS and Windows.
- Check if `getEqBandCount()` always returns `3` or if it's version-dependent.
- **Cross-Process Changelog Sync:** The `fls-pilot` MCP server loads `changelog.jsonl` into memory only at startup. If multiple server instances run simultaneously (e.g. IDE MCP vs explicit terminal server, or parallel test scripts), their in-memory undo histories will diverge and external file writes won't be seen. How can we ensure safe rollback and changelog synchronization across multiple processes?
