# FL Studio MCP Knowledgebase

Zweck dieser Knowledgebase ist die Dokumentation von maschinenlesbarem Wissen und menschlichen Erkenntnissen zur FL Studio API. Sie soll verhindern, dass LLMs wiederholt dieselben Fehler bei der API-Nutzung machen.

## Ordnerrollen
- `fl_api/`: Dokumentation einzelner FL Studio API-Module, Grenzen und Kalibrierungsverfahren.
- `conversions/`: JSON/YAML-Mappings für Wertebereiche (z.B. UI-dB zu normalisierten Floats).
- `recipes/`: Wiederverwendbare Workflows und Templates, die nicht im Code verankert sein sollten.
- `known_pitfalls/`: Wiederkehrende Fehler und bekannte Probleme.
- `agent_notes/`: Laufende Notizen, Lernprotokolle (`learning_log.md`) und offene Fragen.

## Pflegepflicht
Agenten **müssen** dieses Repository vor Änderungen konsultieren und neues Wissen dokumentieren (siehe `AGENTS.md`).

## Confidence-Level
- `hypothesis`
- `user_reported`
- `docs_confirmed`
- `measured_once`
- `measured_repeated`
- `implementation_verified`
- `cross_platform_verified`
- `deprecated_or_rejected`

Markdown reicht für reine Erklärungen. **Sobald ein Mapping Tool-Entscheidungen beeinflusst, muss zusätzlich JSON/YAML aktualisiert werden.**

Wichtige Referenzen:
- [AGENTS.md](../AGENTS.md)
- [MCP_TOOL_POLICY.md](./MCP_TOOL_POLICY.md)
- [Learning Log](./agent_notes/learning_log.md)
