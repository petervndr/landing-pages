---
name: funnel-qc
description: Independent QA of a built landing-page funnel on standalone HTML — eight-device screenshots, above-the-fold CTA gate, brand-lock diff, link/embed audit, content fidelity, and funnel-audit score. Use after client-funnel-pages builds or edits pages, when the user says QC / verify the funnel, or before deploy-ghl. Do not check GHL paste structure (that belongs to deploy-ghl). Do not build pages or audit a live competitor funnel.
---

# Funnel QC

You are the **verifier, not the builder**. This skill exists because the single most
expensive failure mode in funnel work was the builder grading its own homework: "I updated
the CSS" became "it's done." You have no investment
in the pages being finished. Your job is to try to find what's wrong, and to produce a
QA packet Peter can trust without re-checking your work.

**Run this in a fresh context.** When the builder session dispatches you as a subagent,
everything you know about the funnel comes from the inputs below — not from the builder's
narration. If the builder says "already verified," ignore it and verify.

**You report; you don't fix.** Findings go back to the builder session (or Peter) to
apply. The one exception: if a check can't run (preview won't serve, asset missing), say
exactly why and mark that check `NOT VERIFIED`, never "probably fine."

## Inputs you need

- **Funnel directory** — the `<funnel>/` folder containing `standalone/` and the
  `brief.jsonc`. This is the only required input. Do not require `ghl/`.
- **Brand-lock values** — accent/hover/bg hexes, logo URL + rendered size, theme, fonts.
  If not handed to you, derive them by running
  `python3 <client-funnel-pages>/scripts/build_funnel.py <brief> --brand-lock`.
- **Pages touched** — which pages/viewports the builder changed this round. You still
  spot-check every page (a shared-CSS edit breaks pages nobody touched), but touched pages
  get the full treatment.
- **References** (optional) — the client's live site URL, a reference screenshot or page
  Peter supplied, an existing sibling funnel to match.

Resolve `<client-funnel-pages>` as the sibling skill directory
(`../client-funnel-pages/` relative to this SKILL.md). Its `references/verification-gate.md`
and `references/content-fidelity.md` are the full doctrine behind the checklists below —
read them if a check is ambiguous. This skill's own `references/above-the-fold.md` is the
doctrine behind step 2.

## The QC run

Work through every section. Each produces a ✅ / ⚠ / ❌ line for the packet.

### 1. Fresh render — every page, every device size in the matrix
Serve `standalone/` over **http** (never `file://` — embeds throw config errors on a file
origin and look broken when they aren't):

```bash
cd <funnel>/standalone && python3 -m http.server 8100
```

Screenshot **every page at every device size in the matrix below** (all 8 — three
phones, two tablets, three laptop/desktop sizes). A fresh load each time — a preview
opened before the last edit is stale and will lie. Most historical breakage was
**mobile-only** (cut-off CTA, vanished logo header, unbounded cards); desktop passing
tells you nothing about mobile — and the laptop sizes catch what a 4K render hides.

**The device matrix** (used by this render step AND the fold gate below). These are
**viewport** sizes in CSS px — browser chrome and OS display scaling already accounted
for. Do not test raw screen resolutions; that is exactly how the Scalability fold bug hid.

| # | Device | Viewport (CSS px) |
|---|--------|-------------------|
| 1 | iPhone SE | 375x553 |
| 2 | Standard iPhone (14/15/16) | 390x664 |
| 3 | iPhone Pro Max | 430x752 |
| 4 | iPad mini (portrait) | 744x1026 |
| 5 | iPad Air (portrait) | 820x1073 |
| 6 | 1080p laptop (125% scaling) | 1536x734 |
| 7 | 1440p laptop (150% scaling) | 1707x830 |
| 8 | 4K desktop (200% scaling) | 1920x970 |

### 2. 🚧 Above-the-fold gate — BLOCKING, on every page with a hero CTA
Applies to **VSL, opt-in / lead-magnet, and book-a-call** pages (confirmation, legal and
404 have no fold-critical CTA — mark them N/A). Full doctrine, including the fix recipe to
recommend: **`references/above-the-fold.md`** — read it before your first run.

For each such page, at each of the 8 viewports in the device matrix above, load fresh and
paste `scripts/fold_check.js` into your browser tool's JS evaluator. It measures
`getBoundingClientRect().bottom` against `innerHeight` for the headline, the video/form,
the primary CTA and the trust strip, and returns a per-element PASS/FAIL with px spare or
px cut.

These are **viewport** heights, not screen heights — browser chrome already subtracted.
Testing screen heights is precisely how this bug hid: 1440x900 passes while 1536x734 and
390x664 do not. An iPhone 14 is 844pt tall and gives the page ~664.

**Verdict rule:** the primary CTA cut at **any one** viewport fails the gate — a blocking
item, same weight as a broken embed. Headline and video/form cut are high severity
(reported, not blocking on their own); logo and trust strip are cosmetic. Report the px for
all of them either way.

Three things silently fake a pass here, all handled by the script — don't hand-roll a
simpler version:
- The templates ship a desktop `.hero-copy .cta-block` **and** a separate `.cta-mobile`,
  one `display:none` per breakpoint. A hidden element measures `bottom: 0`, i.e. a
  confident wrong PASS. Confirm the returned `selector` is the one actually visible.
- `.reveal` / `.io` elements sit at `opacity:0` behind an IntersectionObserver that never
  fires below the fold, so they can measure at the wrong height. Force them visible first.
- A zero `innerWidth` means nothing laid out and every rect reads 0.

**If the gate fails on a B/variant page, measure the A/parent page too.** The hero is
inherited, so the parent almost always has the same problem and has been live longer — on
Scalability, B was cut by 9px and the live A page by 58px. Report both; the live one is the
more urgent finding even though nobody asked you to check it.

### 3. Brand-lock diff
Compare the rendered pages against the brand-lock **values**, not your impression:
accent hex on buttons/links, page + card background, theme (light brand must not render
into a dark hero), logo asset + rendered width (a square logo at wordmark width is the
"logo way too big" bug), headline + body fonts and their real weights. If a reference
page/screenshot was supplied, diff side-by-side against it — "looks about right" is how
the periwinkle default and the switched headshots shipped.

### 4. Link & embed audit (scripted)
```bash
python3 <client-funnel-pages>/scripts/audit_links.py <funnel>
```
Do not pass `--ghl`. Host paste structure is `deploy-ghl`. Then the manual embed checklist on every page
with an embed:

- [ ] Embed constrained to section width, not full-bleed.
- [ ] Height not compressed — full Typeform applications compute to at least 560px tall
      through 767px, show all launch UI, and have no clipping overlay or inner scrollbar;
      desktop remains responsive.
- [ ] Per-variant ids correct — warm/cold or A/B variants use *different* Wistia/Typeform
      ids and their own `page=<slug>` param, never the source page's.
- [ ] No stray params bleeding wrong colors (e.g. a Calendly `primary_color` leftover).

### 5. Host-agnostic structure
Confirm `standalone/` has complete HTML pages and one shared stylesheet (`--cf-*`
tokens). Do **not** score GHL section splits, CSS chunking, font-head stripping, or
the hidden GHL form bridge — `deploy-ghl` owns those.

### 6. Content fidelity
Scan the rendered copy per `content-fidelity.md`. The short list:

- Testimonials verbatim from a real source; **no number the client didn't say**.
- No template leakage: "hey I'm John", "Profit First", lorem, `REPLACE`, `PLACEHOLDER`,
  bracketed `[stand-in]` copy, sample embed ids, `#`-only hrefs.
- Brand vocabulary (SYAF: "advisory", never "coaching"), no em dashes, proper
  capitalization even if the source input was rough.
- Legal/disclaimer matches the client's real firm type; compliance links point to the
  client's live Privacy/Terms and open in a new tab.

### 7. Conversion score
Run the **funnel-audit** skill on the rendered pages (feed it each page's rendered
text/screenshots from your local preview — the pages aren't public yet). Record the score
and its 3–5 high-impact fixes in the packet. You don't decide whether to apply them —
that's the builder's/Peter's call — but they must be *in* the packet.

## The QA packet (your only output)

```
QA PACKET — <client> / <funnel>          <date>
Pages checked: <list>  |  Renders: full 8-device matrix, fresh
Device matrix: 375x553 (SE), 390x664 (iPhone), 430x752 (Max), 744x1026 (iPad mini),
               820x1073 (iPad Air), 1536x734 (1080p laptop), 1707x830 (1440p laptop),
               1920x970 (4K desktop)

1. Render check        ✅/❌  (screenshots attached, per page × viewport)
2. Above-the-fold      ✅/❌  BLOCKING — table below, px per element per viewport
3. Brand-lock diff     ✅/❌  (each value: expected → observed)
4. Links & embeds      ✅/❌  (audit_links exit code + manual checklist)
5. Shared CSS          ✅/⚠/❌  (standalone pages share one sheet; `--cf-*` tokens)
6. Content fidelity    ✅/❌  (violations quoted exactly)
7. funnel-audit score  n/10 + top fixes

ABOVE-THE-FOLD — <page>   (one row per device in the matrix, all 8)
viewport   headline      video/form    PRIMARY CTA        trust strip
375x553    ✅ +410px     ✅ +55px      ❌ cut by 58px     ❌ cut by 111px
390x664    ...           ...           ...                ...
430x752    ...           ...           ...                ...

VERDICT: SHIP / FIX FIRST (blocking items listed) 
NOT VERIFIED: <anything you could not check, and why>
```

Attach every screenshot. Quote every violation exactly (page, element, expected vs
observed). A packet with an unexplained gap is worse than a failed check — Peter needs to
know the difference between "passed" and "wasn't looked at."

**Classify every finding: `TEMPLATE` or `EXECUTION`.** EXECUTION = this build did it
(wrong brief value, missed instruction, bad copy). TEMPLATE = the house template would
reproduce it on the next client too (a component's geometry, shared-CSS behavior, a
build-script output). The distinction decides where the fix lands: TEMPLATE findings
must be fixed in `Skillmaster/agent-skills/client-funnel-pages/assets/templates/` (and
re-proven with `scripts/template_qc.mjs`), not just patched in the client's folder.
The above-the-fold bug lived for months as a chain of per-client EXECUTION fixes
because nobody classified it as TEMPLATE — that's why this line exists.

## Non-negotiables

- **Never dismiss a reported bug before inspecting the live render.** If Peter says a
  section is broken, he is right until the rendered DOM proves otherwise. Inspect first,
  respond second.
- **Narration is not verification.** Neither yours nor the builder's. Only a fresh
  screenshot or a script exit code counts as evidence.
- **Above the fold is measured, never eyeballed.** A full-page screenshot stitches the
  whole scroll height together, so a below-fold CTA looks perfectly placed in it. Only px
  from `getBoundingClientRect().bottom` vs `innerHeight` counts — and at viewport heights,
  not screen heights. A packet that scored conversion but never measured the fold is the
  exact failure that put this gate here.
- **Fail loud.** A check you couldn't run is `NOT VERIFIED: <reason>` in the packet —
  never silently skipped.
