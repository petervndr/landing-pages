# GoHighLevel Paste Guide

How to take a built funnel (the `ghl/` folder the script produces) live in GHL.
Each page is built from the SAME shared CSS plus a few section files. Repeat the
steps below once per page.

## The one rule that trips people up
These pages are built to occupy the **whole** GHL page — the CSS has a global
reset and sets the page background. Build each one as a **blank page** with no
other GHL elements, nav, or sections. If the client needs GHL's nav/footer on the
page, say so and the templates can be scoped under a wrapper instead.

## Per page

### 1. Custom CSS (paste once, page-wide)
`ghl/styles.css` → **Page/Funnel Settings → Custom CSS**.
The CSS is identical on every page in the funnel, so paste the same block on each.
If the field rejects raw CSS, wrap it in `<style> … </style>`.

### 2. Page font
Set the page font to the brand's font (e.g. **Poppins**) in GHL's design settings.
GHL serves Google Fonts natively — there is **no font code to paste**.

### 3. Sections (one Custom HTML / Code element each, top to bottom)
Drop a 1-column row, add a **Custom HTML / Code** element, paste one file. Repeat.

| Page | Sections, in order (optional ones only exist when the brief has them) |
|------|--------------------|
| **vsl** | `01-header` → `02-hero` → `03-booking` (if not linking out) → `04-testimonials` (opt.) |
| **opt-in** | `01-header` → `02-hero` → `03-compare` (opt.) → `04-whats-inside` (opt.) → `05-founder` (opt.) |
| **book-a-call** | `01-header` → `02-content` |
| **confirmation** | `01-header` → `02-hero` → `03-steps` → `04-resources` (opt.) → `05-faqs` (opt.) → `05b-testimonials` (opt.) |
| **results** | `01-header` → `02-content` |
| **privacy / terms** | `01-header` → `02-content` |
| **404** | `01-header` → `02-content` |

Then add the footer (last-numbered `…-footer`) as the final element.

### 4. Head & footer tracking code
Wistia lives in the hero (or video section) as an **iframe**. Do **not** paste
`player.js` or `embed/{id}.js` into tracking. See `wistia-in-ghl.md`.

- **VSL:** `00-head-code.html` (Wistia preconnect only, plus fonts note) → **Settings → Tracking Code → Head**.
  `06-footer-scripts.html` (deferred Typeform/calendar + scroll-reveal + logo marquee) →
  **Settings → Tracking Code → Body/Footer**.
- **confirmation:** `00-head-code.html` (Wistia preconnect if the page has Wistia iframes) → Head; `07-footer-scripts.html`
  (scroll-reveal) → Body/Footer.
- **results:** `00-head-code.html` (Wistia preconnect when testimonials use Wistia) → Head;
  `04-footer-scripts.html` (scroll-reveal) → Body/Footer.
- **book-a-call:** the Calendly loader is already inside `02-content.html`, so there's
  nothing extra to paste. `00-head-code.html` is just a reminder note.
- **privacy / terms:** no tracking code; `00-head-code.html` is just a note.

## Opt-in page — the hidden-form bridge
The opt-in hero's form is on-brand HTML. On submit, JS fills a **hidden, native GHL
form** on the page and fires it — so GHL captures the lead with full attribution
(Hyros, click data, automations). Proven working with GHL's inline forms (which
render as a `<div>`, not an iframe — so the bridge reaches the fields directly).

1. Build a GHL form with **First Name, Email, Phone, + your Revenue field**. Drop it
   in its own row, give the **row** the custom class **`optin-hidden`** (NO leading
   dot), and turn the row's **visibility OFF**.
2. Paste `07-footer-scripts.html` into **Tracking Code → Body/Footer**.
3. Inspect the hidden Revenue field, copy its input `name`, and set
   `optin.form.ghl_qualifier_field` in the brief (re-build) so the bridge fills it.
4. **Test:** submit the visible form → check the GHL form's Submissions. A
   `Hidden GHL form not found` console error almost always means a dot crept into the
   class — remove it and refresh (GHL forms load async).

Full setup, the `CONFIG` block, the visible↔GHL field map, and troubleshooting:
**`optin-form-bridge.md`**.

## Want fewer elements?
The sections are split for clarity, not necessity. You can merge any adjacent
sections into a single Custom HTML element (e.g. header + hero together), or paste
an entire page as one block. The CSS doesn't care how the HTML is chunked.

## Gotchas
- **Typeform UTM passthrough** (VSL): the form forwards `utm_*` + `gclid`/`fbclid`
  from the page URL, but the matching **Hidden Fields must exist inside the
  Typeform itself** (Settings → Hidden Fields) or the values are silently dropped.
- **Calendly looks white on a `file://` preview** — that's a cross-origin preview
  artifact. On a real GHL domain it renders transparent on the page background.
- **`.bgCover`**: GHL paints its own section background layer. The CSS already
  forces it to the page color (`.bgCover{background-color:var(--page)!important}`),
  which is what keeps the page from looking striped.

## ⚠ CSS variables must stay namespaced (`--cf-*`)

GoHighLevel injects its **own** `:root` custom properties — confirmed `--black: #000` (≈9×), and likely other generic single-word names (`--dark`, `--font`, `--card`, `--page`, `--radius`…). These **override** any identically-named variable you paste in your Custom CSS, even though your less-common tokens survive. The visible symptom is a dark hero/section rendering pure black (GHL's `--black`) instead of your brand dark, which also sinks subtle grid/texture overlays into invisibility.

This template namespaces **every** variable as `--cf-*` so GHL can't clobber it. If you add a new token, keep the prefix — never introduce a bare `--black`/`--card`/`--page`/`--font`. (Diagnosed on the SYAF site, 2026-06-27.)
