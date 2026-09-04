---
name: deploy-ghl
description: Pastes a QC'd client funnel into GoHighLevel as per-section Custom HTML plus one shared stylesheet. Use after funnel-qc SHIP when the user says deploy, paste into HighLevel, or the live URL is a go.* / GHL funnel. Applies the Wistia iframe embed (never the Aurora web component) because GHL Vue hydration drops player.js on first load. Do not build pages (client-funnel-pages).
---

# Deploy to GoHighLevel

Host-specific packaging and paste. Pages must already exist in `standalone/` and have a `funnel-qc` **SHIP** verdict. Do not rebuild copy or restyle here.

Resolve sibling `../client-funnel-pages/` for the build output and `scripts/`. Read `references/wistia-in-ghl.md` before any VSL paste. Read `references/ghl-paste-guide.md` and, for opt-in pages, `references/optin-form-bridge.md`.

## Inputs

- Funnel directory with `standalone/`, `ghl/`, `brief.jsonc`
- `funnel-qc` QA packet (SHIP)
- Peter's OK to paste into GHL

If `ghl/` is missing, run the existing build script so it writes the section split, then apply the transforms below. Do not hand Peter the raw builder `00-head-code.html` if it still contains Wistia `player.js`.

## Required transforms (every GHL paste)

These are not optional. Lucrum VSL Direct Booking (2026-08-13) shipped a blurred swatch that GTmetrix scored as a fast LCP while `player.js` never loaded on first visit.

1. **Wistia = iframe only.** Replace every `<wistia-player>` with the iframe in `references/wistia-in-ghl.md`. Never paste `player.js` or `embed/{id}.js` (`type="module"`) into GHL Tracking → Head. Head may preconnect to `fast.wistia.net` / `fast.wistia.com` only.
2. **No `.reveal` on `.video-shell`.** Opacity 0 on the hero video looks like a dead embed.
3. **Defer Typeform.** Do not load `embed.typeform.com/next/embed.js` on first paint. Use the IntersectionObserver snippet in `wistia-in-ghl.md` so the VSL iframe wins the network.
4. **Full files, never diffs.** Delete-and-replace wholesale in GHL.
5. **Per-section HTML + one shared `styles.css`.** Never one collapsed page block. CSS tokens stay `--cf-*`. No font `<link>` in paste sections.

## Workflow

1. Confirm `funnel-qc` SHIP on `standalone/`.
2. Apply the transforms to `ghl/` (Wistia iframe, Typeform defer, video-shell CSS).
3. Run GHL-readiness:
   - `python3 ../client-funnel-pages/scripts/audit_links.py <funnel> --ghl`
   - `python3 ../client-funnel-pages/scripts/sync_css.py check <funnel>`
   - If stylesheet > 12k and GHL Custom Values: `python3 ../client-funnel-pages/scripts/sync_css.py chunk <funnel>`
   - Opt-in: hidden native GHL form + bridge per `optin-form-bridge.md`
4. Present the paste README + transformed `ghl/` files. Wait for Peter's OK.
5. Paste per `ghl-paste-guide.md`. Then verify the **published** GHL URL in a private window, first load, no refresh — the player chrome must appear without a reload.

## After paste

If the Wistia player is a stuck blur or empty box until refresh, the web component leaked back in. Re-paste the iframe hero and strip head Wistia scripts. Do not "debug player.js."

## Not this skill

- Building or editing page copy/layout → `client-funnel-pages`
- Host-agnostic QC → `funnel-qc`
