# Opt-in Form Bridge — hidden GHL form (PROVEN setup)

> **📦 Packaging standard:** when you assemble a full-funnel GHL deploy package, **inline this entire reference into the package `README.md`** — mechanics, field map, CONFIG block, and the full troubleshooting list — under a top callout telling the installer they can paste the whole project folder into Claude to debug. The installer (client / partner agency / VA) won't have this file on their machine, so a README that only links here is dead context. Self-contained = their Claude can actually fix the opt-in script.

The opt-in page shows an **on-brand HTML form**. On submit, bridge JS copies the
values into a **hidden, native GoHighLevel form** on the same page and fires it —
so GHL captures the lead with full attribution (Hyros, click data, ad tracking)
and your automations run, while the visitor only ever sees the pretty form.

This is confirmed working on GHL (sub-account `firmpillar.app`, SYAF Scaling
Blueprint opt-in). The notes below are the exact path that worked.

## How GHL actually renders its forms (the key fact)
A GHL **Form element dropped onto a funnel page renders INLINE** — a `<div>`
container with a class like `cform-XXXXXXXX`, and the fields live directly in the
page DOM (same-origin). There is **no `<form>` tag** — the inputs sit inside
`<div id="_builder-form">`. So the bridge:
- targets the **container** (`.optin-hidden` / `[class*="cform-"]`), not a `<form>`,
- sets each field's value with the native setter + `input`/`change` events (GHL forms are Vue-based), and
- clicks the container's `<button type="submit">`.

> If a GHL form ever renders as a cross-origin `<iframe>` instead (some embed
> modes), the DOM bridge can't reach its fields — use GHL's **inline embed** form
> code so the fields are same-origin. Do not use the iframe widget.

## The visible form ↔ hidden form field map
The visible opt-in form has: **First Name, Email, Phone, Revenue**. The hidden GHL
form must have matching fields. Standard GHL names line up automatically:

| Visible field | Hidden GHL field (input name) |
|---|---|
| First Name | `first_name` |
| Email | `email` |
| Phone | `phone` |
| Revenue (qualifier) | a **custom field** with a hashed name, e.g. `FcSLvOBaS607u5d61IIc` |

Only the qualifier/custom field is form-specific. Find its `name` by inspecting the
hidden form, then set it in the brief as **`optin.form.ghl_qualifier_field`** — the
build wires it into the bridge `CONFIG.map.qualifier`.

## Setup in GHL (do this once per client)
1. **Build the GHL form** (Forms → Builder) with **First Name, Email, Phone, and
   your Revenue field**. Make Revenue a single-line/text field so it accepts any
   value (or a dropdown whose options match the visible form's).
2. **Place it on the page** in its own 1-column row, and give that **row** the
   custom class **`optin-hidden`** — type it **without a leading dot**. (GHL stores
   exactly what you type; `.optin-hidden` becomes a literal class `.optin-hidden`
   that the selector won't match.)
3. **Hide the row** (visibility OFF). It stays in the DOM; the visitor never sees it.
4. **Find the Revenue field's name**: right-click it → Inspect → read the `name`
   on its `<input>`. Put that in the brief: `optin.form.ghl_qualifier_field`.
5. **Re-build** and paste the fresh `07-footer-scripts.html` into Tracking Code →
   Body/Footer, and `02-hero.html` into its section.

## The bridge CONFIG (top of `07-footer-scripts.html`)
```js
var CONFIG = {
  hiddenForm: '.optin-hidden, [class*="cform-"]',  // the GHL form CONTAINER
  map: {
    firstName: 'input[name="first_name"]',
    email:     'input[name="email"]',
    phone:     'input[name="phone"]',
    qualifier: 'input[name="<your-revenue-field>"]' // from optin.form.ghl_qualifier_field
  },
  successRedirect: null  // null = inline success message; or a thank-you URL
};
```
On submit the bridge fills these, waits ~150ms for GHL's model to update, then
clicks the hidden form's Submit button.

## Test
Submit the visible form → check **GHL → your form → Submissions** for the lead and
the browser **Console**. If it captures, you're done — leave the GHL form row hidden.

## Troubleshooting (the exact things that bit us)
- **`Hidden GHL form not found` in console** → the container selector didn't match.
  Most often the custom class was entered with a dot (`.optin-hidden`); remove it.
  Refresh once too — GHL forms load async.
- **Form fires but the lead is blank / missing Revenue** → the qualifier field name
  is wrong. Re-inspect the hidden form's Revenue `<input name>` and update
  `optin.form.ghl_qualifier_field`.
- **Name not captured** → the hidden form must have `first_name` (the visible form
  sends first name only).
- **Redirect cancels the submit** → if you set `successRedirect`, the bridge already
  delays the redirect ~700ms so the GHL request fires first; or use the GHL form's
  own post-submit redirect instead.
