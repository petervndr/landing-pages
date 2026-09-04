---
name: client-funnel-pages
description: Builds host-agnostic client landing pages (VSL, opt-in, booking, confirmation, legal, 404) from a signed brand kit and brief into standalone HTML plus one shared stylesheet. Use when building or editing funnel pages for a client. Does not deploy — after funnel-qc SHIP, use deploy-ghl. Not for QC (funnel-qc), live funnel audits (funnel-audit), GHL paste, or VSL script writing.
---

## Shared copy rules

Before drafting, read from the repo root (one library — do not keep local copies):

- `copywriting/voice-principles.md`
- `copywriting/banned-phrases.md`
- `copywriting/banned-patterns.md`
- `copywriting/proof-discipline.md`
- `copywriting/copywriting-playbook.md`

Email sequences also read `copywriting/value-dense-emails.md`. Ad body copy also reads `copywriting/haynes-dr-framework.md`.


# Client Funnel Pages

Resolve all relative scripts, assets, examples, and references from the directory containing this `SKILL.md`. Run bundled commands with that directory as the working directory.

Turns the house funnel template into a fully rebranded page set for any client.
One brand brief in → standalone HTML out (host-agnostic). Deploy is a separate skill.

- **VSL page** — dark hero card (headline + Wistia video + CTA), logo trust strip, Typeform application section.
- **Opt-in / lead-magnet page** — dark hero with an on-brand opt-in form, "loved by" trust band, "what's inside" + lead-magnet mockup, founder bio. The form is branded HTML with a placeholder submit; the deploy skill wires the real destination.
- **Book-a-call page** — headline + Calendly embed.
- **Call confirmation page** — post-booking thank-you page: an urgency video so they don't no-show, a text reminder to confirm, "do these 3 things" next-step cards (each with a calendar / text-message / video-thumbnail visual), and a "watch this before we talk" block (optional YouTube video + resource links). noindex.
- **Privacy Policy** + **Terms & Conditions** — boilerplate legal pages, branded to the client's entity and jurisdiction.
- **404 page** — a branded page-not-found: centered "404", a short message, and a Back-to-Home button. noindex.

Every page shares one stylesheet. Preview as complete HTML in `standalone/`.
Do not paste to GHL from this skill — that is `deploy-ghl`.

## How it works

The pages are templates with `{{TOKENS}}` for everything that changes between
clients — accent color, logo, headline, video/form ids, legal entity, address,
socials. A Python build script reads a per-client **brand brief**, fills the
tokens, and writes standalone preview files (and a `ghl/` section split that only
`deploy-ghl` may use). The script **fails loudly**: if the brief is missing a field, has a bad color, or a
template token goes unfilled, it stops and tells you exactly what's wrong rather
than shipping a half-built page.

## Output contract — non-negotiable, every build

Meet all of these or the build isn't deliverable. They exist because each was a repeated
correction:

- **Full paste-ready files, never snippets or diffs.** When a deploy skill hands Peter code, give the complete file to delete-and-replace wholesale — never "add this line."
- **Canonical output is `standalone/`.** Complete HTML pages + one shared stylesheet. `ghl/` is an implementation byproduct for `deploy-ghl` only — do not present it as the build deliverable or paste it yourself.
- **One shared stylesheet is the single source of truth.** All pages consume it; never
  fork per-page CSS. Tokens are namespaced `--cf-*` (see `references/verification-gate.md`).
- **Canonical output location.** Client funnels live under
  `01 Landing Pages/<Client>/<funnel>/` (brief + `standalone/`, one `media/` per
  client). The full path is
  `/Users/petervndr/Library/CloudStorage/GoogleDrive-peter@socialclubstudios.com/Shared drives/03 Pod 1 | Social Club Studios/01 Landing Pages`
  — the build script refuses to write anywhere else unless explicitly overridden. Don't
  scatter files; tell Peter exactly where the code is.
- **This skill does not deploy.** After `funnel-qc` SHIP, stop. Deploy is `deploy-ghl` only.
- **Scope discipline.** Change only the page and viewport named. Don't apply a VSL edit to
  the opt-in, a mobile edit to desktop, or add sections/sticky bars nobody asked for.
- **Mobile Typeform applications use a 560px canvas.** At widths up to 767px, keep the
  full application shell, generated Typeform element, and iframe at `height` and
  `min-height: 560px`; remove clipping, masks, transforms, and decorative overlays.
  Desktop keeps its responsive height. Do not apply this to a short opt-in Typeform.
- **Fidelity & verification** are their own gates — see `references/content-fidelity.md`
  and `references/verification-gate.md`, wired into the workflow below.

## Workflow

This runs as a **gated pipeline**: you do everything autonomously except **one human
checkpoint** after `funnel-qc` (which host). Brand sign-off already happened at
onboarding inside `style-creator`. Deploy is never this skill.

### 0. Brand kit + prior art — establish the sources of truth
The most repeated correction in this skill's history is some form of *"we already have
this, why didn't you look."* Check three things, in order:

**a) The brand kit: `<Client>/_brand/brand.jsonc`** (under the canonical path above),
produced and signed off by the `style-creator` skill at onboarding. This skill does
**no brand extraction of its own** — the kit is the only styling source.

- **Kit exists** → it supplies the brief's brand fields verbatim (colors, fonts, logos
  + aspect ratios, theme, entity, socials, legal URLs). Carry its sign-off through:
  set `"brand_lock_confirmed": true` in the brief when the kit's flag is true.
- **No kit** → **stop and run the `style-creator` skill first**, end to end, including
  its brand-lock sign-off from Peter. Then come back here and proceed with the kit it
  produced. Don't inline a quick scrape "just for this build" — one-off extractions
  are exactly how the wrong-color/wrong-logo class of rework kept happening.

**b) The client's existing funnels in `01 Landing Pages/<Client>/`.** If any exist,
this build is **brownfield**:

- Existing funnels supply the **structural patterns** — reuse the closest sibling's
  header/footer layout, logo placement, and section styles for net-new pages rather
  than re-deriving from the house template. A `website/` or `_design-system/` folder
  outranks the house template too.
- The **brand values** still come from the kit. If an existing funnel's styles disagree
  with the kit (an old accent hex, a different font), **flag the conflict to Peter
  before building** — it usually means the kit is newer than the funnel (rebuild wins)
  or the funnel carries an approved exception (the kit needs updating). Don't silently
  pick either.
- Set `"prior_art_checked": true` in the brief after you've actually read the existing
  funnels — the build script fails without it when prior funnels exist.

**c) The registered client's knowledge folder in the shared vault.**
Resolve the client with AGENTS.md lookup (CLIENT-INDEX.md, then the client folder). Never guess a folder path. Do not run `client-profile-sync`. This is where positioning,
voice, proof numbers, offer language, and testimonial sources live by the time a funnel
gets built. All messaging on the pages draws from it — headlines, founder bio, proof
points, CTA language. If the file is missing or thin, tell Peter what's missing and ask;
don't invent copy facts.

**Trust order when sources disagree:** brand kit (styling) → existing built pages
(structure) → vault notes (messaging) → anything cached in another skill's reference
files. (A stale reference file shipping the wrong brand color is a real, recurring bug.)

### 1. Build the funnel brief
Copy the template into the client's canonical funnel folder (brownfield: start from the
client's existing brief instead):

```bash
cp "assets/brand-brief.template.jsonc" "<01 Landing Pages>/<Client>/<funnel>/brief.jsonc"
```

Fill every REQUIRED field:

- **Brand fields** — verbatim from `_brand/brand.jsonc`. No re-derivation, no
  "improvements"; if a kit value looks wrong, that's a step-0 conflict to flag, not a
  thing to quietly fix in the brief.
- **Copy facts** — from the client's vault knowledge file: positioning, proof numbers,
  founder bio, brand vocabulary.
- **Embed ids** (Wistia, Typeform, Calendly) — **ask the user**; the kit and vault
  can't know these and a wrong id is worse than asking. For A/B variants, give each
  page its **own** Wistia/Typeform id and `page=<slug>` — never reuse the source page's.
- **Pages** — decide what to build via the `pages` array; drop any the client
  doesn't need.

> **⚠ Files must be hosted media links — never local paths.** Every image, video, logo,
> or favicon on a page must be an `https://` URL. If the user hands you a **file** (a
> headshot, MP4, GIF, cover image), do **not** wire a local path — tell them: **"upload
> this to GoHighLevel's media library and send me the media link,"** then use that URL.
> A local path renders on your machine and breaks for everyone else. (GHL serves uploads
> from `assets.cdn.filesafe.space/...`.)

`assets/brand-brief.example.jsonc` is a complete filled-in reference (SYAF) — read
it when you're unsure what a field should look like.

There is **no standing brand sign-off gate here** — that happened once at onboarding.
The only reasons to stop and ask before building: a step-0 conflict between the kit and
existing funnels, a missing/thin vault file, or embed ids nobody has given you.

### 2. Run the build
```bash
python3 "scripts/build_funnel.py" "<...>/01 Landing Pages/<Client>/<funnel>/brief.jsonc" \
    --out "<...>/01 Landing Pages/<Client>/<funnel>"

# Deploying only SOME pages (e.g. adding/updating one page in an existing funnel)?
# Build just that batch — other pages' output is left untouched:
python3 "scripts/build_funnel.py" <brief> --out <funnel> --pages vsl,confirmation
```

Output lands in the client's canonical funnel folder with `standalone/` (the deliverable)
and a **per-batch README**. `ghl/` may still be written for `deploy-ghl` — do not hand it
to Peter from this skill. The script **fails loudly** — on a missing field, a framework-default color,
an implausible logo aspect, a missing tracking param, oversized CSS, an unnamespaced
token, leaked placeholder/banned copy, an output path outside `01 Landing Pages`
(override: `--allow-out-anywhere`, only for throwaway experiments), or existing client
funnels you haven't acknowledged (`prior_art_checked` — see step 0). Read the error, fix
the brief, and re-run.

### 3. Dev preview — over http, not `file://`
While you iterate, serve the pages over http; **don't open them as `file://`.** YouTube,
Wistia, Typeform and Calendly embeds need a real web origin — on `file://` they throw
configuration errors (YouTube shows "Error 153") and a white box, which looks broken but
isn't.

```bash
cd "<funnel>/standalone" && python3 -m http.server 8000
# then open http://localhost:8000/<page>.html
```

`scripts/audit_links.py <funnel>` is cheap — run it during the dev loop whenever you
touch links or embeds. And keep `references/verification-gate.md` in mind while you
work: fresh render, both viewports, never argue with a render bug Peter reports before
inspecting the live element.

### 4. Independent QC — dispatch the `funnel-qc` skill as a SUBAGENT
When you believe the build is done, you do not get to certify it. **Dispatch the
`funnel-qc` skill in a fresh subagent context** and hand it: the funnel directory, the
brand-lock values, which pages/viewports you touched, and any reference Peter gave you.
It re-renders everything fresh across its full 8-device matrix (three iPhones, two
iPads, 1080p/1440p laptops, 4K desktop), diffs the brand-lock, runs the link &
embed audit, scans content fidelity, scores conversion via
`funnel-audit`, and returns a **QA packet** with a SHIP / FIX FIRST verdict. It does
**not** check GHL paste structure — that belongs to `deploy-ghl`.

Why a subagent: every "it's done" that later broke in GHL came from the builder grading
its own work with a stale mental model. A verifier with no context except the artifacts
finds what you've gone blind to — and late in a long build session, your context is
exactly when the gates historically got skipped.

Fix what the packet flags (or note why not), then **re-dispatch funnel-qc** until the
verdict is SHIP. Any CSS fix means the QC round re-checks **every** page, not just the
one you fixed — shared-CSS edits break pages nobody touched.

### 5. 🚦 GATE B — present the QA packet, then deploy-ghl
Present funnel-qc's **QA packet** (screenshots, brand-lock diff, audit results,
funnel-audit score + which fixes you applied, and anything NOT VERIFIED). The
only deploy path is GoHighLevel. When they say deploy, dispatch `deploy-ghl`.

Do not paste into GHL from this skill.

The opt-in page ships a branded HTML form with a placeholder submit.
`deploy-ghl` wires the hidden GHL form bridge. Do not embed a webhook in the
built page.

## Template fixes flow UP, not sideways

When a funnel-qc finding is classified `TEMPLATE` (the house template would reproduce it
for the next client), the fix belongs in this skill's
`assets/templates/` — applied to the client build *and* backported here in the same
session. A fix that stops at the client folder gets re-discovered and re-fixed on every
future build; the above-the-fold bug survived months of per-client patches exactly this
way. After any template or shared-CSS change, prove the template still passes centrally:

```bash
node scripts/template_qc.mjs   # builds the example brief, fold-gates every hero-CTA
                               # page across the 8-device matrix; non-zero exit = don't publish
```

## Editing the shared CSS safely

All pages share ONE stylesheet — that is what prevents the "edit here, break there" drift
that plagued earlier builds. When you change `assets/templates/styles.css` (or a client's
built CSS) and rebuild, use the CSS safety tool before shipping:

```bash
# 1. Blast radius — exactly which selectors a CSS edit changed:
cp <funnel>/standalone/styles.css /tmp/css-baseline.css 2>/dev/null || cp <funnel>/ghl/styles.css /tmp/css-baseline.css
python3 scripts/sync_css.py diff /tmp/css-baseline.css <funnel>/ghl/styles.css

# 2. Confirm every page still carries the identical shared sheet:
python3 scripts/sync_css.py check <funnel>
```

CSS chunking for GHL's 12k Custom Values limit is `deploy-ghl`, not this skill.

A CSS change means a fresh `funnel-qc` round over **every** page at every device size
in its matrix (Step 4) — not just the one you were working on. That is how a shared-CSS
edit that silently broke another page used to slip through.

## The brand brief at a glance

| Group | Fields |
|-------|--------|
| **Brand** | brand_name, legal_entity, accent (+ optional hover/bg/font), logo_url (+ optional logo_white_url for the dark mobile header), logo_aspect |
| **VSL** | callout, headline, subheadline, cta_text, form_heading, wistia_id, typeform_id, trust_logos[] |
| **Opt-in** | eyebrow, headline (+ optional highlight), subheadline, fineprint, lead_magnet_image, trust_logos[] (dark), form qualifier + options, what's-inside bullets, founder bio |
| **Book** | headline, calendly_url |
| **Confirmation** | headline (+ highlight), subheadline, reminder (text), hero video (youtube **or** wistia_id), steps[] (title/text + optional calendar/text/thumb visual); optional "before we talk" video (YouTube) + resources[] |
| **Legal** | website_url, support_email, governing_state, venue (+ optional arbitration body, dates) |
| **404** | page_title, meta_description, headline, cta_url (+ optional subline, cta_text) |
| **Footer** | address lines, privacy/terms URLs, socials (optional), disclaimer (optional) |

Anything marked optional has a sensible default (hover color auto-lightens the
accent; the earnings disclaimer auto-generates from the brand name; dates default
to today).

## ⚠️ Legal pages are templates, not legal advice
The Privacy Policy, Terms, and footer earnings disclaimer are solid boilerplate,
but they are **not a substitute for review by the client's counsel**. They assume
a US LLC with a specified governing state and AAA arbitration. Before any client
publishes, flag that a lawyer should review the legal pages against the client's
actual entity, jurisdiction, and data practices. Never represent the generated
legal text as vetted.

## Shipping to the team
Source of truth for this skill is the canonical `Skillmaster/agent-skills/client-funnel-pages/` directory. The old
`scs_claude/` role packs are **retired** — the team gets skills via the **plugins** in
`github.com/socialclubstudios/scs-plugins`. This one belongs in the **funnel-builder**
plugin. To publish:

1. Add `client-funnel-pages` to
   `/Users/petervndr/Peter OS Canonical/Skillmaster/dist-cowork/plugins/funnel-builder/skills.manifest`.
2. Republish that plugin from the canonical workspace and push:

```bash
"/Users/petervndr/Peter OS Canonical/Skillmaster/dist-cowork/publish-cowork.sh" funnel-builder
cd ~/claude/socialclubstudios/scs-plugins && git add -A && git commit -m "Add client-funnel-pages to funnel-builder" && git push
```

`publish-cowork.sh` rebuilds the whole plugin from the manifest and `rm -rf`s the
destination first, so confirm every skill in the manifest exists under `Skillmaster/agent-skills/`
before running.
