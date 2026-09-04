# Landing Pages plugin

If you were asked to **install this repository**, do that first. Do not build pages during install.

1. Confirm the host workspace path (the user's project — not this clone).
2. From this repo root, run:

```bash
./scripts/install.sh --project /path/to/host-workspace
```

Add `--claude` for Claude Code (also links `.claude/skills/`). Add `--cursor-local` for a Cursor user plugin.

3. Confirm these folders exist and resolve:

- `<host>/.agents/skills/client-funnel-pages/SKILL.md`
- `<host>/.agents/skills/funnel-qc/SKILL.md`
- `<host>/.agents/skills/deploy-ghl/SKILL.md`

4. Stop and tell the user install is done.

---

# Landing Page Pipeline

This plugin builds, checks, and pastes client landing pages into GoHighLevel. Do not hand-roll HTML or paste into GHL outside these skills. The only deploy path is GHL.

## Pipeline

`client-funnel-pages` → `funnel-qc` → `deploy-ghl`

Read each skill from `skills/<name>/SKILL.md` in this plugin. Resolve scripts, templates, and references from that skill directory.

| Skill | Use when |
| --- | --- |
| `client-funnel-pages` | Building or editing funnel pages. Output is host-agnostic `standalone/` HTML plus one shared stylesheet. |
| `funnel-qc` | Verifying a built funnel. Fresh context. Report only. Do not fix or deploy. |
| `deploy-ghl` | Pasting a SHIP'd funnel into GoHighLevel. |

## Rules

- Copy facts come from the client vault or brief. Styling comes from the signed `_brand/brand.jsonc` kit and existing built pages.
- Before drafting copy, read `copywriting/` at the **host workspace** root when those files exist (`voice-principles.md`, `banned-phrases.md`, `banned-patterns.md`, `proof-discipline.md`, `copywriting-playbook.md`). If they are missing, ask for voice rules. Do not invent proof.
- Page output lives under `LANDING_PAGES_ROOT` when set, otherwise the host's landing-pages folder (see `WORKSPACE.md`).
- This plugin does not write VSL scripts.

Host paths and tools: `WORKSPACE.md`.
