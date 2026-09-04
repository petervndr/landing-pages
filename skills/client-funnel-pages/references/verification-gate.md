# Verification gate — never claim "done" off a stale or local preview

This is the single most important discipline in the whole skill. More funnel time
was lost to *false "it's done"* than to any actual bug. The rule: **you do not get to
say a page is done, fixed, verified, or working until you have looked at a fresh render
of it, at both viewports, with your own eyes (a screenshot), and diffed it against the
reference.** Narration is not verification. "I updated the CSS" is not "it renders."

## The hard rules

1. **A fresh render, every time.** After any edit, reload the page (re-serve, or
   `window.location.reload()`) before looking. A preview you opened three edits ago is
   stale and will lie to you. If you can't confirm the render is current, say so — don't
   imply it's verified.

2. **Both viewports, always.** Screenshot **mobile (375px)** and **desktop (1280px)**
   for every page you touched. Most breakage in this skill's history was mobile-only:
   CTA cut off, full-bleed frames missing, logo header gone after a theme switch, review
   cards unbounded. Desktop looking right tells you nothing about mobile. (This is the
   builder's quick in-loop check — the independent `funnel-qc` pass re-renders at its
   full 8-device matrix, so don't be surprised when it fails a size you never looked at;
   check the tight ones early if the hero is dense.)

3. **Diff against the reference, not your memory.** Open the brand-lock (colors, logo
   size, theme) and the reference page/screenshot Peter gave you, side by side with your
   render. "Looks about right" is how the periwinkle, the gold accent, and the switched
   headshots all shipped. Compare the actual pixels.

4. **Never dismiss a reported bug before inspecting the live render.** If Peter says a
   section is broken, blank, the wrong color, or blurry — he is right until the live
   rendered DOM proves otherwise. Do **not** reply "it's too subtle," "that's a cached
   view," "it's by design," or anything that argues with what he sees. Inspect the
   computed styles / rendered element first, *then* respond. ("don't gaslight me" and
   "what the actual fuck" both came from arguing instead of looking.)

5. **Fail loud.** If a page can't be verified — preview won't load, an embed needs a real
   origin, you're missing an asset — state plainly **"NOT verified: <reason>."** Never let
   "done" stand in for "I think it's probably fine."

## Host preview ≠ your local preview

Your local standalone render is not GHL. GHL injects its own CSS and
hydrates custom HTML in Vue — that is why Wistia web components die on first load.
After `funnel-qc` SHIP, `deploy-ghl` owns host preflight
(`ghl-paste-guide.md`, `optin-form-bridge.md`, `wistia-in-ghl.md`).

`--cf-*` tokens still belong in the shared stylesheet here so GHL cannot clobber them
later. Font `<link>` tags stay in standalone preview only.

## Embed checklist (Typeform / Calendly / Wistia / YouTube)

Run this on every page that has an embed — these broke in almost every build:

- [ ] Embed is **constrained to section width**, not full-bleed across the page.
- [ ] Height is **not compressed** — full Typeform applications use the canonical 560px
      `height` + `min-height` mobile canvas through 767px, show all launch UI, and have no
      clipping overlay or inner scrollbar. Desktop remains responsive.
- [ ] **Per-variant ids are correct** — warm vs cold VSL use *different* Wistia/Typeform
      ids; confirm which is which (don't reuse the same id on both).
- [ ] **Tracking is wired** — Typeform carries the UTM passthrough attribute *and* the
      `page=<slug>` param; a duplicated page has its own `page=` slug, not the source's.
- [ ] **No stray params** — no leftover `primary_color` / theme params bleeding a wrong
      color (e.g. Calendly dates highlighted in the wrong blue).
- [ ] Preview is served over **http**, never `file://` (embeds throw config errors on a
      file origin and look broken when they aren't).

## Bottom line

Before you tell Peter a page is done, you must be able to say: *"Rendered fresh, checked
mobile + desktop, diffed against the brand-lock and the reference, embeds and tracking
verified."* If you can't say that truthfully, it isn't done yet.
