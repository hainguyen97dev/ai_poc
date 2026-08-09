# Current Architecture of the Target System

This directory describes the **system being analyzed**, not the architecture
of the AI agent or this repository. ADA loads these documents before every
analysis so all use cases start from the same target-system baseline.

The documents currently contain an **assumed example architecture** for a
payment monolith. They are not verified production facts. Replace them with
approved architecture documents for the real target system before using an
analysis for an engineering decision.

## Conventions

- Mark every unverified statement with `[ASSUMPTION]`.
- Describe the current state only. Put proposed changes in a Change Request or
  ADR input, not in these files.
- Keep secrets, credentials, customer data, and production exports out.
- Prefer small focused Markdown files with stable names.
- Update the module map when a service boundary or dependency changes.
- Files named `README.md` are guidance and are not injected into prompts.

When verified artifacts become available, replace assumptions with facts and
record the artifact name, version, owner, and last-reviewed date.

ADA loads `.md`, `.txt`, `.json`, `.yaml`, and `.yml` files recursively in
filename order. Set `CURRENT_ARCHITECTURE_DIR` to override this directory.
