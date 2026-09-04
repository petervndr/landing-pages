# Above-the-fold gate — measure the hero, don't eyeball it

On 2026-07-27 a full funnel-qc pass on the Scalability VSL B variant returned a detailed
FIX FIRST packet — render, brand-lock, links, embeds, GHL-readiness, content fidelity, a
conversion score — and never noticed that the primary CTA sat **below the fold on mobile**.
Peter found it by looking at his phone. Measured afterward at a real iPhone 14 Safari
viewport (390x664), B's CTA was cut by 9px and the A page *that was live* was cut by 58px.

That is the most expensive class of miss available to this skill. Everything else in the
packet is about a page being wrong; this is about the page being *invisible where it
counts*. A visitor who has to scroll to find the button is a visitor who converts worse,
and no other check in the run catches it — screenshots at "375px" say nothing about
height, and a desktop render says nothing at all.

## Why this needs measuring rather than looking

Two reasons the eye fails here:

1. **A screenshot of a tall page doesn't show you the fold.** Full-page captures stitch
   the whole scroll height together, so the CTA looks perfectly placed. You need
   `getBoundingClientRect().bottom` compared against `innerHeight` — an actual number, in
   px, per element.

2. **Screen height is not viewport height.** This is the specific mistake that hid the
   Scalability bug. An iPhone 14 is 844pt tall; Safari's chrome eats ~180 of it, leaving
   ~664 to the page. Test at 1440x900 and everything passes. Test at the heights below and
   it doesn't.

## The viewport matrix

The full 8-device matrix — same one the render step uses. These are **viewport**
(`innerHeight`) values in CSS px, already net of browser chrome and OS display scaling —
do not add anything back.

| # | Device | Viewport | Notes |
|---|--------|----------|-------|
| 1 | iPhone SE | 375x553 | Safari — the tightest realistic case |
| 2 | Standard iPhone (14/15/16) | 390x664 | Safari; 844pt screen minus ~180 chrome |
| 3 | iPhone Pro Max | 430x752 | Safari |
| 4 | iPad mini (portrait) | 744x1026 | Safari |
| 5 | iPad Air (portrait) | 820x1073 | Safari |
| 6 | 1080p laptop | 1536x734 | 1920x1080 at typical 125% scaling, minus chrome |
| 7 | 1440p laptop | 1707x830 | 2560x1440 at typical 150% scaling, minus chrome |
| 8 | 4K desktop | 1920x970 | 3840x2160 at typical 200% scaling, minus chrome |

Set the viewport, load the page **fresh**, then measure. A page resized after load can
keep stale layout, and a viewport set to zero width means nothing laid out at all — the
snippet refuses to measure in that case rather than reporting a meaningless pass.

## Which pages this applies to

Any page whose job is to get a click in the hero: **VSL, opt-in / lead-magnet, and
book-a-call**. Confirmation, legal, and 404 pages have no fold-critical CTA — note them as
N/A rather than measuring them.

**Booking pages measure differently.** A book-a-call page has no hero CTA button — the
calendar/application embed IS the CTA. `fold_check.js` handles this automatically: when
no CTA button matches, it falls back to the embed and passes only if the embed visibly
*starts* at least 80px above the fold (a tall calendar's bottom is never above the fold,
so bottom-measurement would always fail; top-visibility is the meaningful check).

## Running it

Serve `standalone/` over http as in the main render step, then per page per viewport paste
`scripts/fold_check.js` into whichever browser tool evaluates JS on the page
(`javascript_tool`, `evaluate_script`, `browser_evaluate`). It returns:

```json
{ "viewport": "390x664", "url": "/vsl-page.html", "gate": "FAIL — blocking (FAIL (cut by 58px))",
  "rows": [ { "element": "primary CTA", "severity": "BLOCKING", "status": "FAIL (cut by 58px)",
              "bottom": 722, "fold": 664, "selector": "cf-cta" } ] }
```

Read the script's comments before adapting it — the three things it handles deliberately
are the three ways this measurement silently lies:

- **Hidden CTA twins.** These templates ship a desktop `.hero-copy .cta-block` *and* a
  separate `.cta-mobile`, one `display:none` per breakpoint. A hidden element measures
  `bottom: 0` — i.e. a confident, wrong PASS. The script only measures elements that are
  actually rendered, and reports which one it measured in `selector` so you can confirm.
- **`.reveal` / `.io` elements.** They start at `opacity:0` behind an IntersectionObserver
  that never fires for below-fold content, so they can measure at the wrong height. The
  script forces them visible first.
- **A dead viewport.** `innerWidth` of 0 means no layout happened; it errors instead of
  passing.

If a client's hero uses class names outside the script's selector lists, widen the lists —
but keep the CTA list mobile-variant-first, and never let a missing CTA read as a pass. The
script fails the gate on an `ABSENT` CTA for exactly that reason: it means the selectors are
wrong for this client, which is a thing a human needs to look at.

## Severity, and what actually blocks

| Element | Severity |
|---------|----------|
| Primary CTA | **Blocking** — fails the gate at *any* tested viewport |
| Headline | High — report it, doesn't block on its own |
| Video / form | High — report it, doesn't block on its own |
| Logo, trust/social-proof strip | Cosmetic — note the px, move on |

One viewport failing is a failure. "It's fine on seven of eight" is how a live page ends
up cut by 58px on the phone most of its traffic arrives on.

## Check the A / parent page too

A fold failure on a B variant is almost never B's fault — the hero is inherited, so the
parent page has the same geometry and has usually been live longer. On Scalability, B was
cut by 9px and the A page nobody had asked about was cut by 58px. **When the gate fails on
a variant, measure the A/parent page at the same viewports and report both.** The one
that's live is the more urgent finding, even though it's not the page you were asked to QC.

## The fix recipe (for the packet's recommendation, not for you to apply)

You report; the builder applies. But the packet is more useful when it names the shape of
the fix, and the pattern that worked on Scalability generalizes well:

```css
/* 1. Width-scoped trims — recover px on all phones. Scope to the variant's own class so
      the sibling/parent page is untouched. */
@media (max-width:600px){
  .hero-wrap.vsl-b .hero-card{padding-top:22px}
  .hero-wrap.vsl-b .overline{font-size:.72rem;letter-spacing:.1em}
  .hero-wrap.vsl-b .hero-copy h1{font-size:1.8rem;margin-top:16px}
  .hero-wrap.vsl-b .sub{font-size:1rem;margin-top:13px}
  .hero-wrap.vsl-b .hero-media{margin-top:16px}
  .hero-wrap.vsl-b .cta-mobile{margin-top:16px}
}
/* 2. HEIGHT-scoped block — the part people forget. Short viewports (SE class) need more
      than trims, and roomier phones shouldn't pay for it. Drop the overline (a qualifier,
      not the offer — first thing to go) and shrink the headline. */
@media (max-width:600px) and (max-height:620px){
  .hero-wrap.vsl-b .hero-card{padding-top:16px}
  .hero-wrap.vsl-b .overline{display:none}
  .hero-wrap.vsl-b .hero-copy h1{font-size:1.6rem;margin-top:0}
  .hero-wrap.vsl-b .sub{font-size:.95rem;margin-top:10px}
  .hero-wrap.vsl-b .hero-media{margin-top:12px}
  .hero-wrap.vsl-b .cta-mobile{margin-top:12px}
}
```

Two things make this pattern work rather than just move the problem: pairing `max-width`
with `max-height` so the trim only applies where vertical space is genuinely tight, and
scoping every rule to a class that exists on one page's hero only, so a variant fix can't
regress its parent. The live version is in
`01 Landing Pages/Scalability/vsl-funnel/ghl/vsl-b/_b-sections.css`.

A fold fix is a CSS change, which means the next QC round re-measures **every** page at
**every** viewport — a hero trim scoped one selector too wide is exactly the kind of edit
that fixes B and breaks the opt-in.
