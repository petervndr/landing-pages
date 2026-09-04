# Host workspace contract

This plugin is portable. The **host workspace** still has to supply client facts, brand kits, and voice rules. The plugin does not invent those.

## Required on the host

| Need | Where the skills look |
| --- | --- |
| Brand kit | `<Client>/_brand/brand.jsonc` under the landing-pages root |
| Client facts | The client's brief, vault notes, or files the user names. Do not guess paths. |
| Python 3 | `build_funnel.py`, `audit_links.py`, `sync_css.py`, and the QC preview server |

## Recommended

| Need | Where the skills look |
| --- | --- |
| Copy library | `<workspace>/copywriting/` — `voice-principles.md`, `banned-phrases.md`, `banned-patterns.md`, `proof-discipline.md`, `copywriting-playbook.md` |

If `copywriting/` is missing, ask for voice rules before drafting. Do not invent proof numbers or testimonials.

## Landing-pages root

Set `LANDING_PAGES_ROOT` to the folder that holds `<Client>/<funnel>/` output.

On the author's machine the default is the SCS shared drive `01 Landing Pages`. If that path does not exist, set `LANDING_PAGES_ROOT` or pass `--allow-out-anywhere` on `build_funnel.py` only for a throwaway experiment.

Do not scatter output.

## Not in this plugin

- VSL script writing
- Brand extraction
- Live competitor funnel audits
- Netlify (or any non-GHL) publish
