#!/usr/bin/env python3
"""
build_funnel.py — render a client's landing-page funnel from a brand brief.

Reads a commented-JSON brand brief, validates it (failing LOUDLY and listing
every missing field at once), then renders the page templates into:

  <out>/<client>-funnel/
    standalone/   vsl-page.html, book-a-call.html, privacy.html, terms.html   (open these to preview)
    ghl/          styles.css + one folder per page of paste-ready section files
    README-<date>-<batch>.md   paste guide for THIS deploy batch (one new doc per deploy)

Zero third-party dependencies — Python 3.8+ stdlib only, so it runs anywhere.

Usage:
    python3 build_funnel.py "<...>/01 Landing Pages/<Client>/<funnel>/brief.jsonc" \
        --out "<...>/01 Landing Pages/<Client>/<funnel>"
    python3 build_funnel.py path/to/brief.jsonc --brand-lock          # Gate A print, no build
    python3 build_funnel.py path/to/brief.jsonc --out ... --pages vsl,confirmation  # partial deploy batch
    python3 build_funnel.py path/to/brief.jsonc --out /tmp/x --allow-out-anywhere   # experiments

--out must live inside the canonical '01 Landing Pages' drive folder (CANONICAL_LP_DIR
below) unless --allow-out-anywhere is passed. If the client already has funnels there,
the brief must carry "prior_art_checked": true (see SKILL.md Step 0).
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys

# ──────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(SCRIPT_DIR, "..", "assets", "templates")
COMP_DIR = os.path.join(TPL_DIR, "components")
SHELL_DIR = os.path.join(TPL_DIR, "shells")

# Canonical home for every client funnel. Builds outside it get lost ("where do
# landing page files belong?" was a repeated correction) — so the script refuses
# to write anywhere else unless --allow-out-anywhere is passed explicitly.
_DEFAULT_LP_DIR = (
    "/Users/petervndr/Library/CloudStorage/GoogleDrive-peter@socialclubstudios.com/"
    "Shared drives/03 Pod 1 | Social Club Studios/01 Landing Pages"
)
CANONICAL_LP_DIR = os.environ.get("LANDING_PAGES_ROOT") or _DEFAULT_LP_DIR

ALL_PAGES = ["vsl", "opt-in", "book-a-call", "confirmation", "results", "privacy", "terms", "404"]

TOKEN_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


# ──────────────────────────────────────────────────────────────────────────
# Fail-loud helper — every fatal problem routes through here
# ──────────────────────────────────────────────────────────────────────────
def die(title, lines):
    print("\n  ✗ BUILD FAILED — " + title + "\n", file=sys.stderr)
    for ln in lines:
        print("      " + ln, file=sys.stderr)
    print("", file=sys.stderr)
    sys.exit(1)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def esc(s):
    """HTML-escape for text content and double-quoted attributes. Leaves the
    apostrophe alone (legal inside double-quoted attrs) so headlines like
    "You're..." render cleanly. Not for CSS values or URLs used inside CSS."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def wistia_preconnect():
    return (
        '<link rel="preconnect" href="https://fast.wistia.net" crossorigin>\n'
        '<link rel="preconnect" href="https://fast.wistia.com" crossorigin>\n'
        '<link rel="dns-prefetch" href="https://fast.wistia.net">'
    )


def wistia_iframe(wid, title="Video", eager=True):
    """Native iframe. The Aurora web component fails on GHL first load (Vue hydration)."""
    loading = "eager" if eager else "lazy"
    prio = ' fetchpriority="high"' if eager else ""
    return (
        '<iframe src="https://fast.wistia.net/embed/iframe/%s?seo=false&amp;videoFoam=true" '
        'title="%s" allow="autoplay; fullscreen" allowtransparency="true" '
        'frameborder="0" scrolling="no" loading="%s"%s></iframe>'
        % (esc(wid), esc(title), loading, prio)
    )


# ──────────────────────────────────────────────────────────────────────────
# Brief loading (JSON + full-line // comments)
# ──────────────────────────────────────────────────────────────────────────
def strip_jsonc(raw):
    """Remove // line comments and /* */ block comments, string-aware so that
    // inside a string value (e.g. https://...) is never touched."""
    out = []
    i, n = 0, len(raw)
    in_str = escape = False
    while i < n:
        c = raw[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and raw[i + 1] == "/":
            while i < n and raw[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and raw[i + 1] == "*":
            i += 2
            while i + 1 < n and not (raw[i] == "*" and raw[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def load_brief(path):
    if not os.path.isfile(path):
        die("brief not found", ["No file at: " + path])
    raw = read(path)
    try:
        return json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as e:
        die("brand brief is not valid JSON", [
            str(e),
            "Tip: comments must be on their own line and start with //",
            "Check for a trailing comma or a missing quote near the line above.",
        ])


def get(d, dotted, default=None):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


def book_entries(brief):
    """Normalize brief['book'] to a list of booking-page dicts.

    A single object → one page (slug defaults to 'book-a-call' for back-compat
    with existing single-page briefs). A list → one page per object, each of
    which MUST carry a unique slug (used for the output filename + GHL folder).
    Each entry: {slug?, page_title, meta_description, headline, calendly_url}."""
    raw = brief.get("book")
    if isinstance(raw, dict):
        e = dict(raw)
        e.setdefault("slug", "book-a-call")
        return [e]
    if isinstance(raw, list):
        return [dict(e) for e in raw if isinstance(e, dict)]
    return []


def render_book_sub(entry):
    """Optional subheadline under a booking-page headline."""
    sub = entry.get("subheadline")
    return ('<p class="cal-sub reveal">%s</p>' % esc(sub)) if sub else ""


def vsl_entries(brief):
    """Normalize brief['vsl'] to a list of VSL-page dicts.

    A single object → one page (slug defaults to 'vsl', filename 'vsl-page.html',
    for back-compat with existing single-VSL briefs). A list → one page per object,
    each of which MUST carry a unique slug. Each entry embeds EITHER a Typeform
    application (typeform_id), a GoHighLevel calendar (ghl_calendar_url), or links
    out to a booking page (cta_url)."""
    raw = brief.get("vsl")
    if isinstance(raw, dict):
        e = dict(raw)
        e.setdefault("slug", "vsl")
        return [e]
    if isinstance(raw, list):
        return [dict(e) for e in raw if isinstance(e, dict)]
    return []


def vsl_filename(slug):
    """Standalone filename for a VSL entry — 'vsl-page.html' for the default single
    page (back-compat), '<slug>.html' for named entries in a multi-VSL list."""
    return "vsl-page.html" if slug == "vsl" else slug + ".html"


def ghl_embed_loader(url):
    """The GHL form_embed.js loader for a calendar iframe, served from the SAME host as
    the calendar URL. GHL's own generated embed loads the script from the calendar's
    domain, so a white-label domain (e.g. link.<brand>.com) must load its own copy
    rather than the default link.msgsndr.com."""
    m = re.match(r'(https?://[^/]+)', (url or "").strip())
    base = m.group(1) if m else "https://link.msgsndr.com"
    return base + "/js/form_embed.js"


# ──────────────────────────────────────────────────────────────────────────
# Validation — collect ALL problems, then fail once with the full list
# ──────────────────────────────────────────────────────────────────────────
def validate(brief, pages):
    missing = []

    def need(dotted, hint=""):
        v = get(brief, dotted)
        if v is None or (isinstance(v, str) and v.strip() == "") or \
           (isinstance(v, list) and len(v) == 0):
            missing.append((dotted + ("  — " + hint if hint else "")))

    # Shared brand identity (every page uses these)
    for f, h in [
        ("brand_name", "short display name, e.g. Scale Your Accounting Firm"),
        ("legal_entity", "full legal name, e.g. Scale Your Accounting Firm, LLC"),
        ("accent", "primary brand hex, e.g. #6800fc"),
        ("logo_url", "wordmark shown on light backgrounds (header + footer)"),
        ("logo_aspect", 'logo width / height, e.g. "2476 / 149"'),
    ]:
        need(f, h)

    # Footer is on every page
    for f, h in [
        ("footer.address_line1", "e.g. 9111 Broadway STE E"),
        ("footer.address_line2", "e.g. Merrillville, IN 46410"),
        ("footer.privacy_url", "where the Privacy link points"),
        ("footer.terms_url", "where the Terms link points"),
    ]:
        need(f, h)

    if "vsl" in pages:
        # vsl is one object OR a list of VSL pages (each with its own booking embed).
        ventries = vsl_entries(brief)
        if not ventries:
            missing.append('vsl  — a VSL page object, or a list of them for multiple VSL pages')
        vmulti = len(ventries) > 1
        vseen = set()
        for idx, e in enumerate(ventries):
            where = ("vsl[%d]" % idx) if vmulti else "vsl"
            for f, h in [
                ("page_title", "browser tab title"),
                ("meta_description", "SEO/social description"),
                ("callout", "eyebrow above the headline"),
                ("headline", "the big H1"),
                ("subheadline", "supporting line under the headline"),
                ("cta_text", "button label"),
                ("wistia_id", "Wistia media id"),
            ]:
                v = e.get(f)
                if v is None or (isinstance(v, str) and not v.strip()):
                    missing.append("%s.%s  — %s" % (where, f, h))
            # trust_logos is OPTIONAL. The on-page booking section is required unless
            # the CTA links out (cta_url): a VSL page embeds a Typeform application
            # (typeform_id) OR a GoHighLevel calendar (ghl_calendar_url).
            if not e.get("cta_url"):
                tf = (e.get("typeform_id") or "").strip()
                cal = (e.get("ghl_calendar_url") or "").strip()
                if not tf and not cal:
                    missing.append("%s.typeform_id (or %s.ghl_calendar_url / %s.cta_url)  — a Typeform id, "
                                   "a GoHighLevel calendar embed URL, or a booking-page URL to link out to" % (where, where, where))
                if tf and not (e.get("form_heading") or "").strip():
                    missing.append("%s.form_heading  — heading above the Typeform" % where)
            if vmulti:
                slug = (e.get("slug") or "").strip()
                if not slug:
                    missing.append('%s.slug  — required when `vsl` is a list (becomes the page filename/URL)' % where)
                elif slug in vseen:
                    missing.append('%s.slug  — duplicate "%s"; each VSL page needs a unique slug' % (where, slug))
                else:
                    vseen.add(slug)

    if "opt-in" in pages:
        for f, h in [
            ("optin.page_title", "browser tab title"),
            ("optin.meta_description", "SEO/social description"),
            ("optin.eyebrow", "small line above the headline"),
            ("optin.headline", "the big H1"),
            ("optin.cta_text", "scroll-to-form button label"),
        ]:
            need(f, h)
        # optin.subheadline is OPTIONAL — omit it for a tighter above-the-fold.
        # Trust band is OPTIONAL — omit optin.trust_logos for a lean application
        # page (hero + form only). The native HTML form needs qualifier options;
        # a Typeform opt-in (optin.typeform_id) doesn't.
        if not get(brief, "optin.typeform_id"):
            for f, h in [
                ("optin.form.qualifier_label", 'dropdown label, e.g. "Revenue"'),
                ("optin.form.qualifier_options", "list of dropdown option strings"),
            ]:
                need(f, h)
        # "What's inside" is OPTIONAL — only validated when the block is present.
        if get(brief, "optin.whats_inside") is not None:
            for f, h in [
                ("optin.whats_inside.heading", '"What\'s inside" section heading'),
                ("optin.whats_inside.bullets", "list of {icon, lead, text} bullets"),
            ]:
                need(f, h)
        # The lead-magnet visual (cover image or looping MP4) is OPTIONAL. When
        # absent, the "what's inside" section collapses to a single centered column.
        # Founder bio is OPTIONAL — only validate it when the block is present.
        if get(brief, "optin.founder") is not None:
            for f, h in [
                ("optin.founder.heading", 'founder section heading, e.g. "Hey, I\'m Peter"'),
                ("optin.founder.photo", "founder photo URL"),
                ("optin.founder.bullets", "list of bullet strings"),
            ]:
                need(f, h)

    if "book-a-call" in pages:
        entries = book_entries(brief)
        if not entries:
            missing.append('book  — a booking page object, or a list of them for multiple booking pages')
        multi = len(entries) > 1
        seen_slugs = set()
        for idx, e in enumerate(entries):
            where = ("book[%d]" % idx) if multi else "book"
            for f, h in [
                ("page_title", "browser tab title"),
                ("meta_description", "SEO description"),
                ("headline", 'e.g. "Schedule Your Strategy Session"'),
            ]:
                v = e.get(f)
                if v is None or (isinstance(v, str) and not v.strip()):
                    missing.append("%s.%s  — %s" % (where, f, h))
            # A booking page embeds a Calendly widget (calendly_url), a Typeform
            # application (typeform_id), OR a GoHighLevel calendar (ghl_calendar_url)
            # — exactly one is required.
            if not (e.get("calendly_url") or "").strip() and not (e.get("typeform_id") or "").strip() \
               and not (e.get("ghl_calendar_url") or "").strip():
                missing.append("%s.calendly_url (or %s.typeform_id / %s.ghl_calendar_url)  — a full Calendly "
                               "inline data-url, a Typeform id, or a GoHighLevel calendar embed URL" % (where, where, where))
            if multi:
                slug = (e.get("slug") or "").strip()
                if not slug:
                    missing.append('%s.slug  — required when `book` is a list (becomes the page filename/URL)' % where)
                elif slug in seen_slugs:
                    missing.append('%s.slug  — duplicate "%s"; each booking page needs a unique slug' % (where, slug))
                else:
                    seen_slugs.add(slug)

    if "confirmation" in pages:
        for f, h in [
            ("confirmation.page_title", "browser tab title"),
            ("confirmation.meta_description", "SEO description"),
            ("confirmation.headline", "the urgency H1, e.g. \"Watch this before your call\""),
            ("confirmation.steps", "list of {title, text} next-step cards"),
        ]:
            need(f, h)
        # Hero video — either a YouTube embed or a Wistia media id (one is required).
        if not (get(brief, "confirmation.youtube") or get(brief, "confirmation.wistia_id")):
            missing.append('confirmation.youtube (or confirmation.wistia_id)  — '
                           'hero video: a YouTube URL/id, or a Wistia media id')

    if "results" in pages:
        for f, h in [
            ("results.page_title", "browser tab title"),
            ("results.meta_description", "SEO description"),
            ("results.headline", 'the H1, e.g. "Real Results From Real Firms"'),
            ("results.videos", "list of {youtube, name, title, quote} testimonial cards"),
        ]:
            need(f, h)

    if "404" in pages:
        for f, h in [
            ("404.page_title", "browser tab title"),
            ("404.meta_description", "SEO description"),
            ("404.headline", "the not-found message, e.g. \"We can't find that page.\""),
            ("404.cta_url", "where the Back-to-Home button points"),
        ]:
            need(f, h)

    if "privacy" in pages or "terms" in pages:
        for f, h in [
            ("legal.website_url", "bare domain, e.g. joinsyaf.com"),
            ("legal.support_email", "contact email in the policies"),
        ]:
            need(f, h)

    if "terms" in pages:
        for f, h in [
            ("legal.governing_state", "e.g. Indiana"),
            ("legal.venue", "court/arbitration seat, e.g. Lake County, Indiana"),
        ]:
            need(f, h)

    if missing:
        die("the brand brief is missing required fields", [
            "Fill these in, then re-run:", ""
        ] + ["• " + m for m in missing])

    # Light format checks
    accent = brief.get("accent", "")
    if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", accent.strip()):
        die("accent is not a valid hex color", [
            'Got: "%s"' % accent,
            'Use #rgb or #rrggbb, e.g. "#6800fc".',
        ])

    theme = (brief.get("theme") or "dark").strip().lower()
    if theme not in ("light", "dark"):
        die("theme must be \"light\" or \"dark\"", [
            'Got: "%s"' % brief.get("theme"),
            'Use "light" or "dark" (or omit for the default dark hero card).',
        ])

    # A brand color that matches a page-builder default is almost always a scrape mistake.
    if not brief.get("brand_lock_confirmed"):
        flagged = []
        for field in ("accent", "accent_bright", "page_bg", "card_bg"):
            nh = norm_hex(brief.get(field))
            if nh and nh in FRAMEWORK_DEFAULT_HEXES:
                flagged.append("%s = %s" % (field, nh))
        if flagged:
            die("a brand color looks like a page-builder default, not the real brand color", [
                "These match known Relume/Webflow/Tailwind boilerplate colors:", "",
            ] + ["  • " + f for f in flagged] + [
                "",
                "Re-scrape the client's REAL color — the one on the buttons / logo /",
                "headings you can see — not the first :root variable. If this genuinely",
                'IS the brand color, confirm the brand-lock and set "brand_lock_confirmed": true.',
            ])

    # logo_aspect drives the CSS aspect-ratio AND the rendered logo width — it must parse.
    ar = parse_aspect_ratio(brief.get("logo_aspect"))
    if ar is None:
        die("logo_aspect is not a valid ratio", [
            'Got: "%s"' % brief.get("logo_aspect"),
            'Use "width / height" in px, e.g. "2476 / 149".',
        ])
    elif ar > 40 or ar < 0.1:
        print("  ⚠ logo_aspect ratio %.1f:1 looks implausible — check width/height aren't "
              "swapped (a mis-set aspect renders the logo the wrong size)." % ar, file=sys.stderr)

    # A/B or multi-variant pages usually each carry their OWN embed id — a shared video/form
    # across variants is sometimes intended (same VSL, different copy) but was also a real
    # bug (the "same wistia on both pages" mistake), so warn and let the human decide.
    for key in ("vsl", "book"):
        entries = vsl_entries(brief) if key == "vsl" else book_entries(brief)
        if len(entries) > 1:
            for field in ("wistia_id", "typeform_id"):
                seen = {}
                for idx, e in enumerate(entries):
                    val = (e.get(field) or "").strip()
                    if not val:
                        continue
                    if val in seen:
                        print('  ⚠ %s[%d] and %s[%d] share the same %s "%s" — intended, or should '
                              "each variant have its own? (A/B pages usually differ)."
                              % (key, seen[val], key, idx, field, val), file=sys.stderr)
                    else:
                        seen[val] = idx

    # Warn on the template's placeholder Wistia id left un-swapped.
    for e in vsl_entries(brief) + book_entries(brief) + [brief.get("confirmation") or {}]:
        if isinstance(e, dict) and (e.get("wistia_id") or "").strip() == "lyz4xux7p5":
            print('  ⚠ wistia_id "lyz4xux7p5" is the TEMPLATE PLACEHOLDER — swap in the '
                  "real client video id before publishing.", file=sys.stderr)
            break

    bad_pages = [p for p in pages if p not in ALL_PAGES]
    if bad_pages:
        die("unknown page name(s) in `pages`", [
            "Unknown: " + ", ".join(bad_pages),
            "Valid: " + ", ".join(ALL_PAGES),
        ])


# ──────────────────────────────────────────────────────────────────────────
# Color helpers
# ──────────────────────────────────────────────────────────────────────────
def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def lighten(hex_color, amount=0.18):
    """Blend toward white by `amount` (0..1) — used to auto-derive the hover color."""
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex((r + (255 - r) * amount,
                       g + (255 - g) * amount,
                       b + (255 - b) * amount))


def norm_hex(h):
    """Normalize a hex string to lowercase #rrggbb (expanding #rgb) for comparison,
    or '' if it isn't a hex color."""
    h = (h or "").strip().lower().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h if len(h) == 6 and all(c in "0123456789abcdef" for c in h) else ""


# Framework / page-builder DEFAULT palette colors. Scrapers routinely lift these from a
# Relume / Webflow / Tailwind boilerplate :root instead of the brand's real color — the
# #6173e5 "periwinkle" and #37ca37 "green" were both shipped by mistake. A brief that
# lands on one of these almost certainly has the wrong color, so the build STOPS unless
# `brand_lock_confirmed: true` (set only after Peter signs off the brand-lock at Gate A).
FRAMEWORK_DEFAULT_HEXES = {
    "#6173e5",   # Relume/Webflow periwinkle (shipped on Sell Up by mistake)
    "#37ca37",   # sample green (correctly rejected on Alay)
    "#4353ff",   # Webflow default blue
    "#3b82f6", "#6366f1", "#4f46e5", "#8b5cf6",  # Tailwind blue-500 / indigo-500/600 / violet-500
    "#0ea5e9", "#10b981", "#ef4444",             # Tailwind sky-500 / emerald-500 / red-500
}


def parse_aspect_ratio(s):
    """'2476 / 149' or '16/9' -> width/height as a float, or None if unparseable."""
    try:
        a, b = str(s).replace(" ", "").split("/")
        a, b = float(a), float(b)
        return a / b if b else None
    except (ValueError, AttributeError):
        return None


# ──────────────────────────────────────────────────────────────────────────
# Token assembly
# ──────────────────────────────────────────────────────────────────────────
def build_tokens(brief, pages):
    accent = brief["accent"].strip()
    accent_bright = (brief.get("accent_bright") or lighten(accent)).strip()
    r, g, b = hex_to_rgb(accent)

    # Theme — "dark" (default) keeps the signature dark hero card; "light" flips the
    # hero / resource card surfaces to a clean white-on-light look. The dark values are
    # identical to the original hardcoded ones, so existing (dark) briefs render unchanged.
    theme = (brief.get("theme") or "dark").strip().lower()
    if theme == "light":
        card_default = "#ffffff"
        surf = {"BG_ELEV": "#f1f1f1", "INK": "#101010", "INK_SOFT": "#5c5c66",
                "HAIRLINE": "rgba(16,16,16,.12)",
                "CARD_SHADOW": "0 18px 50px -26px rgba(16,16,16,.22)",
                "VISUAL_BG": "#f3f3f6", "BUBBLE_BG": "#e9e9ef", "BUBBLE_INK": "#3a3a42"}
    else:
        card_default = "#121212"
        surf = {"BG_ELEV": "#1c1c1c", "INK": "#f4f4f6", "INK_SOFT": "#c4c4cc",
                "HAIRLINE": "rgba(245,245,247,.12)", "CARD_SHADOW": "none",
                "VISUAL_BG": "var(--cf-card)", "BUBBLE_BG": "#2c2c32", "BUBBLE_INK": "var(--cf-ink-soft)"}

    # Hero card vs flat. LIGHT mode defaults to a FLAT hero — the hero sits directly on the
    # plain page background with no inset white card (a white card on a light page reads as
    # redundant). DARK mode keeps the signature inset card. Override per client with
    # hero_card: true/false. When flat, the hero takes the page bg so it fully blends in.
    hc = brief.get("hero_card")
    hero_flat = (hc is False) or (hc is None and theme == "light")
    if hero_flat:
        surf["CARD_SHADOW"] = "none"
        hero_radius = "0"
        hero_bg = "var(--cf-page)"
    else:
        hero_radius = "var(--cf-radius)"
        hero_bg = "var(--cf-card)"

    # headline highlight (.hl) — dark: white text on an accent marker; light: solid accent text
    hl_grad = ("linear-gradient(rgba(%d,%d,%d,.5) 0%%, rgb(%d,%d,%d) 50%%, rgb(%d,%d,%d) 100%%)"
               % (r, g, b, r, g, b, r, g, b))
    if theme == "light":
        surf["HL_COLOR"], surf["HL_BG"] = accent, "none"
    else:
        surf["HL_COLOR"], surf["HL_BG"] = "#fff", hl_grad

    today = datetime.date.today()
    legal_date = get(brief, "legal.last_updated") or \
        "%s %d, %d" % (today.strftime("%B"), today.day, today.year)
    copyright_year = str(get(brief, "legal.copyright_year") or today.year)

    brand = brief["brand_name"].strip()
    entity = brief["legal_entity"].strip()
    font_family = (brief.get("font_family") or "Poppins").strip()
    # Optional separate headline/display font (e.g. an elegant serif over a sans body).
    # Empty → headings use the body font, so existing briefs are unaffected.
    headline_font = (brief.get("headline_font") or "").strip()
    # Header/footer logo width. Derive from the logo's real aspect so a square/badge logo
    # doesn't render at full wordmark width (the "logo way too big" bug that hit 5 of the
    # last 8 client builds). Target ~a 34px header logo HEIGHT; explicit logo_width /
    # footer_logo_width in the brief always win.
    _ar = parse_aspect_ratio(brief.get("logo_aspect")) or 6.0
    lw = brief.get("logo_width")
    logo_width = int(lw) if lw else max(110, min(round(34 * _ar), 460))  # mobile scales ~0.74
    flw = brief.get("footer_logo_width")
    footer_logo_width = int(flw) if flw else max(90, round(logo_width * 0.62))
    th = brief.get("trust_logo_height")
    if th:
        th = int(th)                      # trust-strip logo height (px, desktop cap)
        trust_h = "clamp(%dpx,%.2fvw,%dpx)" % (round(th * 0.77), th / 11.8, th)
        trust_maxw = "%dpx" % round(th / 26 * 175)
    else:
        trust_h, trust_maxw = "clamp(20px,2.2vw,26px)", "175px"   # default — identical to original

    line1 = get(brief, "footer.address_line1", "")
    line2 = get(brief, "footer.address_line2", "")
    map_url = get(brief, "footer.map_url")
    _addr_inner = "%s<br>%s" % (esc(line1), esc(line2))
    address_html = ('<a href="%s" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">%s</a>'
                    % (esc(map_url), _addr_inner)) if map_url else _addr_inner

    disclaimer = get(brief, "footer.disclaimer") or default_disclaimer(
        brand, entity, copyright_year)

    T = {
        # brand / CSS
        "PAGE_BG": (brief.get("page_bg") or "#f5f5f5").strip(),
        "CARD_BG": (brief.get("card_bg") or card_default).strip(),
        "ACCENT": accent,
        "ACCENT_BRIGHT": accent_bright,
        "ACCENT_RGB": "%d,%d,%d" % (r, g, b),
        "FONT_STACK": "'%s',system-ui,-apple-system,'Segoe UI',sans-serif" % font_family,
        "FONT_GF": font_family.replace(" ", "+"),
        # Headline font: falls back to the body font when no headline_font is set, so
        # headings render identically for briefs that don't opt in.
        "HEAD_FONT_STACK": ("'%s',Georgia,'Times New Roman',serif" % headline_font) if headline_font else "var(--cf-font)",
        # Extra Google-Fonts family param appended to the standalone <link> (empty when
        # headline == body). Raw (kept out of HTML-escaping) because it's a URL fragment.
        "HEAD_FONT_GF_PARAM": ("&family=%s:ital,wght@0,500;0,600;0,700;1,600" % headline_font.replace(" ", "+")) if headline_font else "",
        "LOGO_URL": brief["logo_url"].strip(),
        "LOGO_WHITE_URL": (get(brief, "logo_white_url") or brief["logo_url"]).strip(),
        "LOGO_ASPECT": str(brief["logo_aspect"]).strip(),
        "LOGO_W": "%dpx" % logo_width,
        "LOGO_W_M": "%dpx" % round(logo_width * 0.74),
        "FOOTER_LOGO_W": "%dpx" % footer_logo_width,
        "TRUST_H": trust_h,
        "TRUST_MAXW": trust_maxw,
        "HERO_RADIUS": hero_radius,
        "HERO_BG": hero_bg,
        "WISTIA_ID": get(brief, "vsl.wistia_id", "none"),
        # brand text
        "BRAND_NAME": brand,
        "BRAND_NAME_UPPER": brand.upper(),
        "LEGAL_ENTITY": entity,
        # legal
        "WEBSITE_URL": get(brief, "legal.website_url", ""),
        "SUPPORT_EMAIL": get(brief, "legal.support_email", ""),
        "GOVERNING_STATE": get(brief, "legal.governing_state", ""),
        "VENUE": get(brief, "legal.venue", ""),
        "ARBITRATION_BODY": get(brief, "legal.arbitration_body",
                                "American Arbitration Association (AAA)"),
        "LEGAL_DATE": legal_date,
        # footer
        "ADDRESS_INLINE": "%s, %s" % (line1, line2),
        "ADDRESS_HTML": address_html,
        "PRIVACY_URL": get(brief, "footer.privacy_url", ""),
        "TERMS_URL": get(brief, "footer.terms_url", ""),
        "PRIVACY_LABEL": get(brief, "footer.privacy_label") or "Privacy Policy",
        "TERMS_LABEL": get(brief, "footer.terms_label") or "Terms & Conditions",
        "DISCLAIMER": disclaimer,
        # vsl
        "VSL_CALLOUT": get(brief, "vsl.callout", ""),
        "VSL_HEADLINE": get(brief, "vsl.headline", ""),
        "VSL_SUBHEADLINE": get(brief, "vsl.subheadline", ""),
        "VSL_CTA_TEXT": get(brief, "vsl.cta_text", ""),
        "VSL_FORM_HEADING": get(brief, "vsl.form_heading", ""),
        "TYPEFORM_ID": get(brief, "vsl.typeform_id", ""),
        # VSL hero CTA target. Default is the on-page Typeform application section
        # (#book). Set vsl.cta_url in the brief to link out to a booking page instead
        # (e.g. a Calendly book-a-call page) — this also drops the on-page Typeform.
        "VSL_CTA_HREF": get(brief, "vsl.cta_url") or "#book",
        # book
        "BOOK_HEADLINE": get(brief, "book.headline", ""),
        "CALENDLY_URL": get(brief, "book.calendly_url", ""),
        # opt-in (scalar text — markers handle the HTML blocks in build())
        "OPTIN_EYEBROW": get(brief, "optin.eyebrow", ""),
        "OPTIN_SUBHEADLINE": get(brief, "optin.subheadline", ""),
        "OPTIN_CTA_TEXT": get(brief, "optin.cta_text", ""),
        "OPTIN_QUALIFIER_LABEL": get(brief, "optin.form.qualifier_label", ""),
        "OPTIN_SUBMIT_TEXT": get(brief, "optin.form.submit_text") or "Get Access",
        "OPTIN_CONSENT": get(brief, "optin.form.consent") or default_consent(entity),
        "OPTIN_SUCCESS_MESSAGE": get(brief, "optin.form.success_message")
            or "You're in! Check your inbox for your download.",
        "OPTIN_TRUST_HEADING": get(brief, "optin.trust_heading") or "Loved by firm owners at…",
        "OPTIN_WI_HEADING": get(brief, "optin.whats_inside.heading", ""),
        "OPTIN_WI_MOD": "" if (get(brief, "optin.lead_magnet_image") or get(brief, "optin.lead_magnet_video")) else " wi-nomedia",
        "OPTIN_TYPEFORM_ID": get(brief, "optin.typeform_id", ""),
        "OPTIN_FOUNDER_HEADING": get(brief, "optin.founder.heading", ""),
        # GHL custom-field name for the qualifier (hashed id, per form) — wired
        # into the hidden-form bridge CONFIG.
        "OPTIN_GHL_QUALIFIER": get(brief, "optin.form.ghl_qualifier_field", ""),
        # confirmation / thank-you page
        "CONFIRM_BADGE": get(brief, "confirmation.eyebrow") or "✓ Your Call Is Booked",
        "CONFIRM_CUE": get(brief, "confirmation.cue") or "\U0001f447 Watch this before your call",
        "CONFIRM_STEPS_EYEBROW": get(brief, "confirmation.steps_eyebrow") or "Your Next Steps",
        "CONFIRM_STEPS_HEADING": get(brief, "confirmation.steps_heading")
            or "Do these 3 things to get the most out of your call",
        "CONFIRM_RES_HEADING": get(brief, "confirmation.resources_heading")
            or "Get a head start before our call",
        "BWT_CLASS": " has-video" if get(brief, "confirmation.video") else "",
        # results (testimonials) page
        "RESULTS_EYEBROW": get(brief, "results.eyebrow") or "Client Results",
        "RESULTS_HEADLINE": get(brief, "results.headline", ""),
        # 404 page
        "NF_HEADLINE": get(brief, "404.headline", ""),
        "NF_SUBLINE": get(brief, "404.subline")
            or "The link may be broken, or the page may have moved.",
        "NF_CTA_TEXT": get(brief, "404.cta_text") or "Back to Home",
        "NF_CTA_URL": get(brief, "404.cta_url", "#"),
    }
    T.update(surf)  # theme-driven hero-card surface colors (raw CSS — not escaped)

    # Escape every human/text + HTML-attribute token. CSS values, ids, the
    # logo URL (used inside a CSS url()), and the pre-escaped address HTML are
    # left raw — entity-encoding those would break the CSS or double-escape.
    raw_keys = {"PAGE_BG", "CARD_BG", "ACCENT", "ACCENT_BRIGHT", "ACCENT_RGB",
                "FONT_STACK", "FONT_GF", "HEAD_FONT_STACK", "HEAD_FONT_GF_PARAM",
                "LOGO_URL", "LOGO_WHITE_URL", "LOGO_ASPECT",
                "LOGO_W", "LOGO_W_M", "FOOTER_LOGO_W", "TRUST_H", "TRUST_MAXW", "HERO_RADIUS", "HERO_BG",
                "VISUAL_BG", "BUBBLE_BG", "BUBBLE_INK", "HL_COLOR", "HL_BG",
                "WISTIA_ID", "VSL_CTA_HREF", "ADDRESS_HTML", "DISCLAIMER", "OPTIN_WI_MOD", "OPTIN_TYPEFORM_ID",
                "BG_ELEV", "INK", "INK_SOFT", "HAIRLINE", "CARD_SHADOW"}
    for k in list(T):
        if k not in raw_keys:
            T[k] = esc(T[k])
    return T


def default_disclaimer(brand, entity, year):
    return (
        "The results referenced on this website are not typical and are not a "
        "guarantee of your success. The instructors at %s are experienced "
        "business owners and operators, and your results will vary depending on "
        "your education, effort, application, experience, and background. We "
        "cannot guarantee that you will make money or that you will be successful "
        "if you apply the strategies we teach, whether specifically or generally. "
        "Consequently, your results may significantly vary from any examples "
        "referenced. We do not provide investment, tax, accounting, legal, or "
        "other professional advice; specific transactions and experiences are "
        "mentioned for informational purposes only. The content within this "
        "website is the property of %s. Any use of the images, content, or ideas "
        "expressed herein without the express written consent of %s is "
        "prohibited. Copyright © %s %s. All Rights Reserved."
        % (brand, entity, entity, year, entity)
    )


def default_consent(entity):
    return (
        "By submitting this form, you agree that %s may contact you by phone, "
        "text message, and email, including with automated technology, about "
        "its products and services, even if your number is on a Do Not Call list. "
        "Consent is not a condition of purchase, and message and data rates may "
        "apply. We do not sell your personal information. See our Privacy Policy "
        "and Terms of Service below." % entity
    )


# ──────────────────────────────────────────────────────────────────────────
# Social icons (only the platforms present in the brief are emitted, in order)
# ──────────────────────────────────────────────────────────────────────────
SOCIAL_SVG = {
    "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.6" cy="6.4" r="1.1" fill="currentColor" stroke="none"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58 2.78 2.78 0 0 0 1.95 1.96C4.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.96A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98" fill="currentColor" stroke="none"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>',
}
SOCIAL_LABEL = {"instagram": "Instagram", "youtube": "YouTube",
                "linkedin": "LinkedIn", "facebook": "Facebook"}
SOCIAL_ORDER = ["instagram", "youtube", "linkedin", "facebook"]


def render_socials(brief):
    social = get(brief, "footer.social", {}) or {}
    lines = []
    for key in SOCIAL_ORDER:
        url = social.get(key)
        if url:
            lines.append(
                '          <a href="%s" aria-label="%s" target="_blank" rel="noopener">%s</a>'
                % (esc(url), SOCIAL_LABEL[key], SOCIAL_SVG[key])
            )
    if not lines:
        return "          <!-- no social links provided -->"
    return "\n".join(lines)


def render_trust_logos(brief):
    logos = get(brief, "vsl.trust_logos", []) or []
    lines = []
    for item in logos:
        url = item.get("url", "") if isinstance(item, dict) else ""
        alt = item.get("alt", "") if isinstance(item, dict) else ""
        if not url:
            die("a trust logo is missing its `url`", [
                "Every entry in vsl.trust_logos needs a url and an alt.",
                "Offending entry: " + json.dumps(item),
            ])
        lines.append('          <img src="%s" alt="%s">' % (esc(url), esc(alt)))
    return "\n".join(lines)


# ── opt-in HTML-block renderers (markers in the templates) ──
def render_headline(brief):
    """Headline with an optional accent-highlighted phrase wrapped in <span class=hl>."""
    h = get(brief, "optin.headline", "")
    hl = get(brief, "optin.headline_highlight")
    if hl and hl in h:
        i = h.index(hl)
        return esc(h[:i]) + '<span class="hl">' + esc(hl) + "</span>" + esc(h[i + len(hl):])
    return esc(h)


def render_fineprint(brief):
    fp = get(brief, "optin.fineprint")
    return ('          <p class="fineprint reveal" style="--cf-d:.3s">%s</p>' % esc(fp)) if fp else ""


def render_optin_sub(brief):
    """Opt-in hero subheadline — omitted entirely when not provided."""
    s = get(brief, "optin.subheadline")
    return ('          <p class="sub reveal" style="--cf-d:.24s">%s</p>' % esc(s)) if s else ""


def render_optin_hero_trust(brief):
    """Compact trust cluster shown INSIDE the hero, directly under the CTA — a small
    label + the proof logos/badges. Replaces the old full-width trust band."""
    logos = get(brief, "optin.trust_logos", []) or []
    if not logos:
        return ""
    label = get(brief, "optin.trust_heading") or "Loved by firm owners at…"
    imgs = []
    for item in logos:
        url = item.get("url", "") if isinstance(item, dict) else ""
        alt = item.get("alt", "") if isinstance(item, dict) else ""
        if not url:
            die("an opt-in trust logo is missing its `url`", [
                "Every entry in optin.trust_logos needs a url and an alt.",
                "Offending entry: " + json.dumps(item),
            ])
        imgs.append('              <img src="%s" alt="%s">' % (esc(url), esc(alt)))
    return ('          <div class="optin-hero-trust reveal" style="--cf-d:.42s">\n'
            '            <span class="oht-label">%s</span>\n'
            '            <div class="oht-logos">\n%s\n            </div>\n'
            '          </div>' % (esc(label), "\n".join(imgs)))


def render_qualifier_options(brief):
    opts = get(brief, "optin.form.qualifier_options", []) or []
    return "\n".join('                  <option value="%s">%s</option>' % (esc(o), esc(o))
                     for o in opts)


def render_optin_trust(brief):
    logos = get(brief, "optin.trust_logos", []) or []
    lines = []
    for item in logos:
        url = item.get("url", "") if isinstance(item, dict) else ""
        alt = item.get("alt", "") if isinstance(item, dict) else ""
        if not url:
            die("an opt-in trust logo is missing its `url`", [
                "Every entry in optin.trust_logos needs a url and an alt.",
                "Offending entry: " + json.dumps(item),
            ])
        lines.append('        <img src="%s" alt="%s">' % (esc(url), esc(alt)))
    return "\n".join(lines)


def render_wi_intro(brief):
    intro = get(brief, "optin.whats_inside.intro")
    if not intro:
        return ""
    if isinstance(intro, str):
        intro = [intro]
    return "\n".join("          <p>%s</p>" % esc(p) for p in intro)


def render_wi_bullets(brief):
    bullets = get(brief, "optin.whats_inside.bullets", []) or []
    lines = []
    for b in bullets:
        icon = b.get("icon", "") if isinstance(b, dict) else ""
        lead = b.get("lead", "") if isinstance(b, dict) else ""
        text = b.get("text", "") if isinstance(b, dict) else str(b)
        lines.append('            <li><span class="wi-ico">%s</span><strong>%s:</strong> %s</li>'
                     % (esc(icon), esc(lead), esc(text)))
    return "\n".join(lines)


def _leadmagnet_visual(brief):
    """The lead-magnet visual — an <img>, or a looping muted <video> when
    optin.lead_magnet_video is set (a GIF-style autoplay loop, far lighter than a GIF).
    Optionally wrapped as a clickable play-button thumbnail (optin.lead_magnet_play)
    that scrolls to the opt-in form."""
    image = get(brief, "optin.lead_magnet_image")
    video = get(brief, "optin.lead_magnet_video")
    if not image and not video:
        return ""
    alt = get(brief, "optin.lead_magnet_alt") or get(brief, "optin.whats_inside.heading") or "Free resource"
    if video:
        poster = get(brief, "optin.lead_magnet_poster")
        poster_attr = ' poster="%s"' % esc(poster) if poster else ""
        media = ('<video class="lm-media" autoplay loop muted playsinline%s aria-label="%s">'
                 '<source src="%s" type="video/mp4"></video>'
                 % (poster_attr, esc(alt), esc(video)))
    else:
        media = '<img src="%s" alt="%s">' % (esc(image), esc(alt))
    if get(brief, "optin.lead_magnet_play"):
        return ('<a class="lm-video" href="#optin-form" aria-label="%s">%s'
                '<span class="vid-play"><svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M8 5v14l11-7z"/></svg></span></a>' % (esc(alt), media))
    return media


def render_wi_media(brief):
    """The 'what's inside' media column. Omitted entirely when there's no visual,
    so the section collapses to a single centered column (.wi-nomedia)."""
    v = _leadmagnet_visual(brief)
    return ('        <div class="wi-media">\n          %s\n        </div>' % v) if v else ""


def render_optin_hero_img(brief):
    """The lead-magnet mockup shown inside the hero on mobile only (omitted when absent)."""
    v = _leadmagnet_visual(brief)
    return ('          <div class="optin-hero-img reveal" style="--cf-d:.28s">%s</div>' % v) if v else ""


def render_founder_photo(brief):
    url = get(brief, "optin.founder.photo", "")
    alt = get(brief, "optin.founder.photo_alt") or "Founder"
    return '          <img src="%s" alt="%s">' % (esc(url), esc(alt))


def render_founder_intro(brief):
    intro = get(brief, "optin.founder.intro")
    return ("          <p>%s</p>" % esc(intro)) if intro else ""


def render_founder_bullets(brief):
    bullets = get(brief, "optin.founder.bullets", []) or []
    return "\n".join("            <li>%s</li>" % esc(b) for b in bullets)


def render_founder_closing(brief):
    c = get(brief, "optin.founder.closing")
    return ("          <p>%s</p>" % esc(c)) if c else ""


def render_redirect_js(brief):
    url = get(brief, "optin.form.success_redirect")
    return json.dumps(url) if url else "null"


def render_redirect_map(brief):
    """JSON map of {qualifier option value -> redirect URL} for per-qualifier routing
    (e.g. send each revenue tier to a different VSL page). Empty {} when unset."""
    m = get(brief, "optin.form.success_redirect_map")
    return json.dumps(m if isinstance(m, dict) else {})


# ── confirmation (thank-you) page renderers ──
def render_confirm_headline(brief):
    h = get(brief, "confirmation.headline", "")
    hl = get(brief, "confirmation.headline_highlight")
    if hl and hl in h:
        i = h.index(hl)
        return esc(h[:i]) + '<span class="hl">' + esc(hl) + "</span>" + esc(h[i + len(hl):])
    return esc(h)


def render_confirm_sub(brief):
    s = get(brief, "confirmation.subheadline")
    return ('        <p class="sub reveal" style="--cf-d:.16s">%s</p>' % esc(s)) if s else ""


def render_confirm_cue(brief):
    """The "👇 Watch this before your call" cue under the headline. Defaults when the
    field is absent; set confirmation.cue to "" to omit it entirely."""
    raw = get(brief, "confirmation.cue")   # None when absent → default; "" → omit
    text = "\U0001f447 Watch this before your call" if raw is None else raw
    return ('        <span class="confirm-cue reveal" style="--cf-d:.2s">%s</span>' % esc(text)) if text else ""


def render_confirm_steps_eyebrow(brief):
    """The steps-section eyebrow (default "Your Next Steps"). Set
    confirmation.steps_eyebrow to "" to omit it."""
    raw = get(brief, "confirmation.steps_eyebrow")
    text = "Your Next Steps" if raw is None else raw
    return ('        <span class="steps-eyebrow">%s</span>' % esc(text)) if text else ""


def render_confirm_reminder(brief):
    text = get(brief, "confirmation.reminder")
    if not text:
        return ""
    # bold any email / @handle so the confirm action stands out
    body = re.sub(r'([\w.+-]*@[\w.-]+\.\w{2,})', r'<strong>\1</strong>', esc(text))
    cta_text = get(brief, "confirmation.cta_text")
    cta = ""
    if cta_text:
        cta = '\n          <a class="cf-cta" href="%s">%s</a>' % (
            esc(get(brief, "confirmation.cta_url") or "#"), esc(cta_text))
    return ('        <div class="confirm-reminder reveal" style="--cf-d:.3s">\n'
            '          <p>%s</p>%s\n        </div>' % (body, cta))


def render_cal_mock(v):
    event = esc(v.get("event", "Your call"))
    try:
        hl = int(v.get("day", 10))
    except (TypeError, ValueError):
        hl = 10
    dows = "".join('<span class="dow">%s</span>' % d for d in ["M", "T", "W", "T", "F", "S", "S"])
    days = "".join('<span class="%s">%d</span>' % ("hl" if d == hl else "", d) for d in range(1, 15))
    return ('          <div class="step-visual"><div class="cal-mock">\n'
            '            <div class="cal-bar"><i class="r"></i><i class="y"></i><i class="g"></i><span>Calendar</span></div>\n'
            '            <div class="cal-title">%s</div>\n'
            '            <div class="cal-grid">%s%s</div>\n'
            '            <div class="cal-event">✓ Added to your calendar</div>\n'
            '          </div></div>' % (event, dows, days))


def render_txt_mock(v):
    sender = v.get("sender", "")
    initial = esc((sender[:1] or "•").upper())
    return ('          <div class="step-visual"><div class="txt-mock">\n'
            '            <div class="txt-avatar">%s</div>\n'
            '            <div class="txt-sender">%s</div>\n'
            '            <div class="txt-meta">Text Message · Today</div>\n'
            '            <div class="txt-bubble">%s</div>\n'
            '            <div class="txt-reply">%s</div>\n'
            '          </div></div>' % (initial, esc(sender), esc(v.get("message", "")),
                                        esc(v.get("reply", "YES"))))


def render_thumb_mock(v):
    cap = v.get("caption", "")
    capdiv = ('<span class="cap">%s</span>' % esc(cap)) if cap else ""
    play = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>'
    return ('          <div class="step-visual" style="padding:0">\n'
            '            <div class="step-thumb"><img src="%s" alt="" loading="lazy">'
            '<span class="ply">%s</span>%s</div>\n'
            '          </div>' % (esc(v.get("url", "")), play, capdiv))


def render_step_visual(v):
    if not isinstance(v, dict):
        return ""
    t = v.get("type")
    if t == "calendar":
        return render_cal_mock(v)
    if t == "text":
        return render_txt_mock(v)
    if t in ("thumb", "image", "video"):
        return render_thumb_mock(v)
    return ""


def render_confirm_steps(brief):
    steps = get(brief, "confirmation.steps", []) or []
    out = []
    for i, s in enumerate(steps, 1):
        d = s if isinstance(s, dict) else {}
        text = d.get("text", "") if isinstance(s, dict) else str(s)
        visual = render_step_visual(d.get("visual"))
        vis = (visual + "\n") if visual else ""
        inner = ('%s'
                 '          <span class="step-num">%d</span>\n'
                 '          <h3>%s</h3>\n'
                 '          <p>%s</p>\n' % (vis, i, esc(d.get("title", "")), esc(text)))
        href = d.get("href")
        if href:
            # a clickable step (e.g. scrolls to the video section)
            out.append('        <a class="step-card is-link" href="%s">\n%s        </a>' % (esc(href), inner))
        else:
            out.append('        <div class="step-card">\n%s        </div>' % inner)
    return "\n".join(out)


def extract_youtube_id(url):
    if not url:
        return ""
    m = re.search(r'(?:youtu\.be/|[?&]v=|/embed/|/shorts/)([\w-]{6,})', url)
    return m.group(1) if m else url.strip()


def render_confirm_video(brief):
    vid = extract_youtube_id(get(brief, "confirmation.video", ""))
    if not vid:
        return ""
    cap = get(brief, "confirmation.video_caption")
    caption = ('\n            <p class="bwt-caption">%s</p>' % esc(cap)) if cap else ""
    return ('          <div class="bwt-video">\n'
            '            <a class="yt-embed" href="https://www.youtube.com/watch?v=%s" target="_blank" rel="noopener" aria-label="Watch the video on YouTube">\n'
            '              <img src="https://img.youtube.com/vi/%s/hqdefault.jpg" alt="" loading="lazy">\n'
            '              <span class="yt-play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>\n'
            '            </a>%s\n'
            '          </div>' % (esc(vid), esc(vid), caption))


def render_confirm_hero_video(brief):
    """Confirmation hero video. Prefers a YouTube embed (`confirmation.youtube`,
    URL or id); falls back to the Wistia player (`confirmation.wistia_id`).
    Returns "" when neither is set so the wrapper isn't emitted.

    The YouTube iframe is sized with an INLINE 16:9 padding box rather than an
    external CSS class, so it fills correctly in GHL even when the shared
    styles.css hasn't been re-pasted — a bare iframe with no CSS otherwise
    collapses to the browser default 300×150."""
    yt = extract_youtube_id(get(brief, "confirmation.youtube", ""))
    if yt:
        shell = (
            '          <div class="video-shell" style="position:relative;padding-bottom:56.25%%;height:0">\n'
            '            <iframe src="https://www.youtube.com/embed/%s" title="Watch this before your call" loading="lazy"\n'
            '              style="position:absolute;top:0;left:0;width:100%%;height:100%%;border:0;display:block"\n'
            '              frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"\n'
            '              referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>\n'
            '          </div>' % esc(yt))
    else:
        wid = get(brief, "confirmation.wistia_id", "")
        if not wid:
            return ""
        shell = (
            '          <div class="video-shell">\n'
            '            %s\n'
            '          </div>' % wistia_iframe(wid, "Watch this before your call", eager=True))
    return ('        <div class="confirm-video reveal" style="--cf-d:.24s">\n'
            '%s\n'
            '        </div>' % shell)


def render_confirm_head(brief):
    """Preconnect only. Wistia is an iframe — never player.js / embed module."""
    hero_wistia = "" if get(brief, "confirmation.youtube") else (get(brief, "confirmation.wistia_id") or "").strip()
    faq_wistia = any(isinstance(f, dict) and (f.get("wistia_id") or "").strip()
                     for f in (get(brief, "confirmation.faqs.items", []) or []))
    testi_wistia = any(isinstance(t, dict) and (t.get("wistia") or t.get("wistia_id") or "").strip()
                       for t in (get(brief, "confirmation.testimonials.items", []) or []))
    if hero_wistia or faq_wistia or testi_wistia:
        return wistia_preconnect()
    return ""


def render_confirm_resources(brief):
    items = get(brief, "confirmation.resources", []) or []
    arrow = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>')
    rows = []
    for r in items:
        if not isinstance(r, dict):
            continue
        title = esc(r.get("title", ""))
        url = esc(r.get("url", "#") or "#")
        text = r.get("text", "")
        desc = ('\n              <p>%s</p>' % esc(text)) if text else ""
        # In-page anchors (#...) scroll within the page — don't open a new tab.
        tgt = '' if url.startswith('#') else ' target="_blank" rel="noopener"'
        rows.append(
            '          <a class="res-item" href="%s"%s>\n'
            '            <div class="res-text">\n'
            '              <h3>%s</h3>%s\n'
            '            </div>\n'
            '            <span class="res-arrow">%s</span>\n'
            '          </a>' % (url, tgt, title, desc, arrow))
    return "\n".join(rows)


def render_confirm_faqs(brief):
    """Optional FAQ-video grid. Each item: {title, wistia_id}. Iframe only — no player.js."""
    items = get(brief, "confirmation.faqs.items", []) or []
    cards = []
    for f in items:
        if not isinstance(f, dict):
            continue
        wid = (f.get("wistia_id") or "").strip()
        if not wid:
            continue
        cards.append(
            '        <article class="faq-card">\n'
            '          <div class="faq-video">%s</div>\n'
            '          <p class="faq-q">%s</p>\n'
            '        </article>' % (wistia_iframe(wid, f.get("title", "FAQ video"), eager=False),
                                    esc(f.get("title", ""))))
    if not cards:
        return ""
    heading = esc(get(brief, "confirmation.faqs.heading") or "Your questions, answered")
    sub = get(brief, "confirmation.faqs.subheading")
    sub_html = ('\n      <p class="faq-sub reveal">%s</p>' % esc(sub)) if sub else ""
    return ('  <!-- ═══ FAQ VIDEOS ═══ -->\n'
            '  <section class="faq-section io" id="faqs">\n'
            '    <div class="wrap">\n'
            '      <h2 class="faq-heading reveal">%s</h2>%s\n'
            '      <div class="faq-grid">\n%s\n      </div>\n'
            '    </div>\n'
            '  </section>' % (heading, sub_html, "\n".join(cards)))


def _testimonial_row(v):
    """One two-column testimonial row (.result-row), shared by the results page and
    the confirmation testimonial section — text on one side, video on the other
    (sides alternate per row via CSS :nth-child). Returns (row_html, wistia_id);
    wistia_id is '' for a YouTube/none embed so callers can emit per-Wistia loaders."""
    wistia = (v.get("wistia") or v.get("wistia_id") or "").strip()
    yt = "" if wistia else extract_youtube_id(v.get("youtube", ""))
    if not wistia and not yt:
        return ("", "")
    name = esc(v.get("name", ""))
    title = v.get("title", "")
    title_html = ' <span>— %s</span>' % esc(title) if title else ""
    quote = v.get("quote", "")
    quote_html = ('          <p class="result-quote">%s</p>\n' % esc(quote)) if quote else ""
    name_html = ('          <p class="result-name">%s%s</p>\n' % (name, title_html)) if (name or title) else ""
    # Optional short HEADLINE that leads the card — a bold summary line above everything.
    headline = v.get("headline", "")
    headline_html = ('          <p class="result-headline">%s</p>\n' % esc(headline)) if headline else ""
    # Optional documented result stat (a firm-attributed figure, NOT a spoken quote) —
    # an accent line; shrinks to a sub-line under the headline when one precedes it.
    result = v.get("result", "")
    result_html = ('          <p class="result-stat">%s</p>\n' % esc(result)) if result else ""
    if wistia:
        embed = wistia_iframe(wistia, name or "Testimonial", eager=False)
    else:
        embed = ('<iframe src="https://www.youtube.com/embed/%s" title="%s" loading="lazy" '
                 'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                 'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>' % (esc(yt), name))
    row = ('      <article class="result-row reveal">\n'
           '        <div class="result-video">%s</div>\n'
           '        <div class="result-text">\n'
           '%s%s'
           '          <span class="result-qmark" aria-hidden="true">“</span>\n'
           '%s%s'
           '        </div>\n'
           '      </article>' % (embed, headline_html, result_html, quote_html, name_html))
    return (row, wistia)


def _render_testimonial_section(items, heading, sub, section_id="testimonials"):
    """Two-column alternating testimonial rows. Wistia is an iframe — no player.js."""
    rows = []
    for v in (items or []):
        if not isinstance(v, dict):
            continue
        row, _wid = _testimonial_row(v)
        if not row:
            continue
        rows.append(row)
    if not rows:
        return ""
    heading = esc(heading or "Don't take our word for it")
    sub_html = ('\n      <p class="faq-sub reveal">%s</p>' % esc(sub)) if sub else ""
    return ('  <!-- ═══ CLIENT TESTIMONIALS ═══ -->\n'
            '  <section class="faq-section io" id="%s">\n'
            '    <div class="wrap">\n'
            '      <h2 class="faq-heading reveal">%s</h2>%s\n'
            '    </div>\n'
            '    <div class="results-rows">\n%s\n    </div>\n'
            '  </section>' % (esc(section_id), heading, sub_html, "\n".join(rows)))


def render_confirm_testimonials(brief):
    """Client-testimonial section on the confirmation page (see _render_testimonial_section)."""
    return _render_testimonial_section(
        get(brief, "confirmation.testimonials.items", []) or [],
        get(brief, "confirmation.testimonials.heading"),
        get(brief, "confirmation.testimonials.subheading"),
        "testimonials")


def render_vsl_testimonials(brief):
    """Optional client-testimonial section on the VSL page — same two-column
    video rows as the confirmation page, rendered below the Typeform application."""
    return _render_testimonial_section(
        get(brief, "vsl.testimonials.items", []) or [],
        get(brief, "vsl.testimonials.heading"),
        get(brief, "vsl.testimonials.subheading"),
        "testimonials")


# ── results (testimonials) page renderers ──
def render_results_sub(brief):
    s = get(brief, "results.subheadline")
    return ('      <p class="results-sub reveal" style="--cf-d:.22s">%s</p>' % esc(s)) if s else ""


def render_results_videos(brief):
    """Alternating two-column testimonial rows for the results page — text ↔ video
    (see _testimonial_row, shared with the confirmation testimonial section)."""
    out = []
    for v in get(brief, "results.videos", []) or []:
        if not isinstance(v, dict):
            continue
        row, _ = _testimonial_row(v)
        if row:
            out.append(row)
    return "\n".join(out)


def render_results_head(brief):
    """Wistia preconnect for the results page — iframe embeds, no player.js."""
    ids = [(v.get("wistia") or v.get("wistia_id") or "").strip()
           for v in (get(brief, "results.videos", []) or []) if isinstance(v, dict)]
    ids = [i for i in ids if i]
    if not ids:
        return ""
    return wistia_preconnect()


def render_results_reviews(brief):
    # A drop-in reviews widget (e.g. Elfsight Google Reviews) takes precedence over
    # hand-authored review cards — render the raw embed inside the reviews section.
    embed = get(brief, "results.reviews_embed")
    if embed:
        heading = esc(get(brief, "results.reviews_heading") or "What our clients say")
        return ('  <section class="results-reviews">\n'
                '    <h2 class="reveal">%s</h2>\n'
                '    <div class="reviews-embed reveal">\n%s\n    </div>\n'
                '  </section>' % (heading, embed))
    reviews = get(brief, "results.reviews", []) or []
    if not reviews:
        return ""
    heading = esc(get(brief, "results.reviews_heading") or "What our clients say")
    cards = []
    for rv in reviews:
        if not isinstance(rv, dict):
            continue
        # Stars are OPTIONAL — only rendered when the brief gives an explicit rating.
        # Logo/quote testimonials that never came from a star-rating platform omit
        # "stars" so we don't fabricate a rating that wasn't given.
        stars_html = ""
        if "stars" in rv:
            try:
                n = max(0, min(5, int(rv.get("stars", 5))))
            except (TypeError, ValueError):
                n = 5
            stars_html = ('<span class="stars" aria-label="%d out of 5">%s%s</span>\n          '
                          % (n, "★" * n, "☆" * (5 - n)))
        detail = rv.get("detail", "")
        detail_html = '<span class="review-detail">%s</span>' % esc(detail) if detail else ""
        platform = rv.get("platform", "")
        platform_html = ('\n          <span class="platform-badge">%s</span>' % esc(platform)) if platform else ""
        # Optional circular headshot beside the byline.
        avatar = rv.get("avatar", "")
        avatar_html = ('<img class="review-avatar" src="%s" alt="%s" loading="lazy">\n            '
                       % (esc(avatar), esc(rv.get("name", "")))) if avatar else ""
        cards.append(
            '        <article class="review-card reveal">\n'
            '          %s<p class="review-quote">%s</p>\n'
            '          <div class="review-by">\n'
            '            %s<div class="review-byline">\n'
            '              <span class="review-name">%s</span>%s\n'
            '            </div>\n'
            '          </div>%s\n'
            '        </article>' % (stars_html, esc(rv.get("quote", "")), avatar_html,
                                    esc(rv.get("name", "")), detail_html, platform_html))
    # Center the grid when there are only 1–2 reviews so they don't leave a gaping
    # blank column in the 3-up desktop layout.
    grid_class = "review-grid"
    if len(cards) in (1, 2):
        grid_class += " review-grid--%d" % len(cards)
    return ('  <section class="results-reviews">\n'
            '    <h2 class="reveal">%s</h2>\n'
            '    <div class="%s">\n%s\n    </div>\n'
            '  </section>' % (heading, grid_class, "\n".join(cards)))


def render_results_cta(brief):
    # Prefer an embedded Typeform application at the bottom of the page (loader bundled
    # in-section, like the VSL). Fall back to a CTA button (cta_text + cta_url) for
    # clients who'd rather link out to a booking page.
    tf = get(brief, "results.typeform_id")
    if tf:
        heading = esc(get(brief, "results.form_heading") or get(brief, "results.cta_text") or "Apply now")
        # NB: plain "book" (no "io") — the results page doesn't run the .io reveal
        # observer, and .io starts at opacity:0, which would leave this invisible.
        return ('  <!-- ═══ TYPEFORM APPLICATION — bottom of results ═══ -->\n'
                '  <section class="book book--typeform" id="apply">\n'
                '    <div class="wrap">\n'
                '      <div class="book-head">\n'
                '        <h2>%s</h2>\n'
                '      </div>\n'
                '      <div class="form-shell typeform-shell">\n'
                '        <div data-tf-live="%s" data-tf-transitive-search-params="utm_source,utm_medium,utm_campaign,utm_term,utm_content,gclid,fbclid"></div>\n'
                '      </div>\n'
                '    </div>\n'
                '    <script src="https://embed.typeform.com/next/embed.js" async></script>\n'
                '  </section>' % (heading, esc(tf)))
    text = get(brief, "results.cta_text")
    if not text:
        return ""
    url = get(brief, "results.cta_url") or "#"
    arrow = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>')
    return ('  <section class="results-cta">\n'
            '    <a class="cf-cta" href="%s">%s %s</a>\n'
            '  </section>' % (esc(url), esc(text), arrow))


# ──────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────
def apply_tokens(text, tokens):
    for k, v in tokens.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def check_unfilled(text, label):
    leftovers = sorted(set(TOKEN_RE.findall(text)))
    if leftovers:
        die("unfilled placeholders in " + label, [
            "These tokens had no value in the brief (or a template/brief typo):",
            "", "  " + "  ".join(leftovers),
            "", "Add them to the brief, or check the spelling.",
        ])


def css_hardening_lint(css):
    """Guard the shared stylesheet against a GHL token-collision regression. GHL injects
    its own :root vars — notably --black:#000 — that clobber identically named pasted
    tokens, so every brand token must be namespaced --cf-*. Comments are stripped first
    (the header comment names the bad tokens on purpose). A bare `var(--black)` / `--black:`
    is the exact bug that flattened the SYAF hero, so it hard-stops; the rest warn."""
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def used(tok):
        return (re.search(r"var\(\s*--" + tok + r"(?![\w-])", stripped) or
                re.search(r"(?:^|[;{]\s*)--" + tok + r"(?![\w-])\s*:", stripped, re.M))

    if used("black"):
        die("shared CSS uses a bare --black token (GHL collision risk)", [
            "GHL injects its own --black:#000 that overrides identically-named pasted vars.",
            "Namespace it --cf-black (or reuse an existing --cf-* token).",
        ])
    warned = [t for t in ("card", "page", "font", "accent", "ink") if used(t)]
    if warned:
        print("  ⚠ shared CSS has bare, un-namespaced token(s): "
              + ", ".join("--" + t for t in warned)
              + " — namespace them --cf-* so GHL can't clobber them.", file=sys.stderr)


def check_content(page_html, label, brief):
    """Content-fidelity lint on rendered page COPY. Strips <style>/<script> so only visible
    HTML is scanned. Hard-stops on unambiguous template/build leftovers; warns loudly on
    voice/brand issues that need a human eye (verbatim testimonials are a valid exception,
    so those don't hard-fail — they surface at the QA gate instead)."""
    body = re.sub(r"<(style|script)\b.*?</\1>", " ", page_html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", body)
    low = text.lower()

    leaks = [p for p in ("lorem ipsum", "replace_me", "calendar_id") if p in low]
    if leaks:
        die("placeholder/template text leaked onto " + label, [
            "Found in visible copy: " + ", ".join('"%s"' % p for p in leaks),
            "Replace it with the client's real copy before shipping.",
        ])

    warns = []
    if "—" in text:
        warns.append("em dash present (—) — voice rule is NO em dashes; sweep them")
    for leak in ("hey i'm john", "i'm john", "profit first", "placeholder", "todo:"):
        if leak in low:
            warns.append('possible template/placeholder leftover: "%s"' % leak)
    bn = (str(brief.get("brand_name", "")) + " " + str(brief.get("legal_entity", ""))).lower()
    if ("scale your accounting" in bn or "syaf" in bn) and re.search(r"\bcoaching\b", low):
        warns.append('"coaching" on a SYAF page — use "advisory" (verbatim testimonials excepted)')
    if warns:
        print("  ⚠ content check — %s:" % label, file=sys.stderr)
        for w in warns:
            print("      • " + w, file=sys.stderr)


def comp(name, tokens, markers=None):
    """Render one component template, fill any markers, verify nothing is left."""
    text = apply_tokens(read(os.path.join(COMP_DIR, name)), tokens)
    for marker, value in (markers or {}).items():
        text = text.replace(marker, value)
    check_unfilled(text, name)
    return text


def font_note(font_family, headline_font=""):
    note = ("<!-- Set the page font to %s in GHL's design settings (GHL loads Google "
            "Fonts natively). -->" % font_family)
    headline_font = (headline_font or "").strip()
    if headline_font and headline_font != font_family:
        # GHL design settings only sets ONE (body) font, so load the headline font
        # explicitly here — otherwise headings fall back to the body font in GHL.
        link = ('<!-- Headline font "%s" (GHL only sets the body font, so load this one here) -->\n'
                '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                '<link href="https://fonts.googleapis.com/css2?family=%s:ital,wght@0,500;0,600;0,700;1,600&display=swap" rel="stylesheet">'
                % (headline_font, headline_font.replace(" ", "+")))
        return link + "\n" + note
    return note


# ──────────────────────────────────────────────────────────────────────────
# Page assembly
# ──────────────────────────────────────────────────────────────────────────
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def render_extra_legal_links(brief):
    """Optional extra footer legal links (e.g. an APS Disclosure page) appended
    after Privacy/Terms. Each item: { label, url }. Empty when not provided."""
    out = []
    for lk in get(brief, "footer.legal_links", []) or []:
        if isinstance(lk, dict) and lk.get("url") and lk.get("label"):
            out.append('          <a href="%s" target="_blank" rel="noopener">%s</a>'
                       % (esc(lk["url"]), esc(lk["label"])))
    return "\n".join(out)


def render_qualifier2(brief):
    """Optional second qualifier dropdown on the native opt-in form."""
    label = get(brief, "optin.form.qualifier2_label")
    opts = get(brief, "optin.form.qualifier2_options") or []
    if not label or not opts:
        return ""
    options = "\n".join('                  <option value="%s">%s</option>' % (esc(o), esc(o)) for o in opts)
    return ('              <div class="optin-field">\n'
            '                <label for="of-qual2">%s <span class="req">*</span></label>\n'
            '                <select id="of-qual2" name="qualifier2" required>\n'
            '                  <option value="" disabled selected>Select one…</option>\n'
            '%s\n'
            '                </select>\n'
            '              </div>' % (esc(label), options))


def render_compare_cards(brief):
    """We-vs-them comparison cards: each item is {cpa, us}."""
    out = []
    brand = brief.get("brand_name", "")
    for it in get(brief, "optin.compare.items", []) or []:
        if not isinstance(it, dict):
            continue
        out.append(
            '        <article class="cmp-card reveal">\n'
            '          <div class="cmp-side cmp-cpa"><span class="cmp-label">Your CPA</span><p>%s</p></div>\n'
            '          <div class="cmp-side cmp-us"><span class="cmp-label">%s</span><p>%s</p></div>\n'
            '        </article>' % (esc(it.get("cpa", "")), esc(brand), esc(it.get("us", ""))))
    return "\n".join(out)


def page_outputs(brief, pages):
    """(standalone filename, ghl folder) pairs a page list writes — used to clear
    exactly this batch's outputs on a partial (--pages) deploy."""
    outs = []
    for p in pages:
        if p == "vsl":
            for e in vsl_entries(brief):
                slug = (e.get("slug") or "vsl").strip()
                outs.append((vsl_filename(slug), slug))
        elif p == "book-a-call":
            for e in book_entries(brief):
                slug = (e.get("slug") or "book-a-call").strip()
                outs.append((slug + ".html", slug))
        elif p == "opt-in":
            outs.append(("opt-in.html", "opt-in"))
        else:  # confirmation, results, privacy, terms, 404
            outs.append((p + ".html", p))
    return outs


def build(brief, out_root, deploy_pages=None):
    if deploy_pages:
        bad = [p for p in deploy_pages if p not in ALL_PAGES]
        if bad:
            die("unknown page name(s) in --pages", [
                "Unknown: " + ", ".join(bad),
                "Valid: " + ", ".join(ALL_PAGES),
            ])
        pages = deploy_pages
    else:
        pages = brief.get("pages") or ALL_PAGES
    validate(brief, pages)
    T = build_tokens(brief, pages)
    font_family = (brief.get("font_family") or "Poppins").strip()
    headline_font_b = (brief.get("headline_font") or "").strip()

    # Shared, rendered-once pieces
    css = apply_tokens(read(os.path.join(TPL_DIR, "styles.css")), T)
    check_unfilled(css, "styles.css")
    css_hardening_lint(css)
    shell = read(os.path.join(SHELL_DIR, "standalone.html"))

    header_light = comp("header.html", T, {"<!--TOPBAR_MOD-->": ""})
    # Dark-hero pages (vsl / opt-in / confirmation) use a header that goes dark + white
    # logo on mobile so it merges into the hero. Light pages (book / legal) use header_light.
    # Only darken when a white logo is provided (else the logo would vanish on the dark bar).
    header_dark = (comp("header.html", T, {"<!--TOPBAR_MOD-->": " topbar--dark"})
                   if get(brief, "logo_white_url") else header_light)
    page_theme = (brief.get("theme") or "dark").strip().lower()
    # In LIGHT mode every page uses the light header: a dark mobile topbar renders the
    # WHITE logo, which is invisible on the now-white card. Dark mode keeps the dark
    # mobile header on the hero pages.
    header_html = header_light if page_theme == "light" else header_dark
    footer_html = comp("footer.html", T, {"<!--SOCIAL_LINKS-->": render_socials(brief),
                                          "<!--EXTRA_LEGAL_LINKS-->": render_extra_legal_links(brief)})

    client = brief.get("client_slug", "client").strip() or "client"
    out = os.path.join(out_root, client + "-funnel")
    ghl = os.path.join(out, "ghl")
    standalone = os.path.join(out, "standalone")

    if deploy_pages:
        # Partial deploy batch: remove only THIS batch's outputs so the other pages'
        # deliverables stay intact. The shared styles.css is still rewritten below —
        # if it changed, it must be re-pasted on EVERY page (the deploy README says so).
        for fname, dname in page_outputs(brief, pages):
            fp = os.path.join(standalone, fname)
            if os.path.isfile(fp):
                os.remove(fp)
            dp = os.path.join(ghl, dname)
            if os.path.isdir(dp):
                shutil.rmtree(dp)
    else:
        # Full build: standalone/ and ghl/ are 100% generated — wipe them before
        # regenerating so a renamed page or dropped slug can't leave a stale file
        # behind with old content.
        for d in (standalone, ghl):
            if os.path.isdir(d):
                shutil.rmtree(d)

    # CSS pasted once, page-wide, identical across every page
    write(os.path.join(ghl, "styles.css"), css)

    built = []

    def standalone_page(title, desc, head_extra, head_code, body, body_scripts=""):
        pt = dict(T)
        pt.update({
            "PAGE_TITLE": esc(title), "META_DESCRIPTION": esc(desc),
            "HEAD_META_EXTRA": head_extra, "HEAD_CODE": head_code,
            "STYLES": css, "BODY": body, "BODY_SCRIPTS": body_scripts,
        })
        page = apply_tokens(shell, pt)
        check_unfilled(page, title + " (standalone)")
        check_content(page, title, brief)
        return page

    # ── VSL (one or more pages, each with its own booking embed) ──
    if "vsl" in pages:
        for e in vsl_entries(brief):
            slug = (e.get("slug") or "vsl").strip()
            # build_tokens bakes the single-object vsl.* as globals (empty for a list) —
            # override the VSL tokens from THIS entry so every VSL page is self-contained.
            vt = dict(T)
            vt["VSL_CALLOUT"] = esc(e.get("callout", ""))
            vt["VSL_HEADLINE"] = esc(e.get("headline", ""))
            vt["VSL_SUBHEADLINE"] = esc(e.get("subheadline", ""))
            vt["VSL_CTA_TEXT"] = esc(e.get("cta_text", ""))
            vt["VSL_FORM_HEADING"] = esc(e.get("form_heading", ""))
            vt["TYPEFORM_ID"] = esc(e.get("typeform_id") or "")
            vt["WISTIA_ID"] = (e.get("wistia_id") or "").strip()      # raw (id in URL/attr)
            vt["VSL_CTA_HREF"] = (e.get("cta_url") or "#book")        # raw (href)

            # Logo trust strip — optional, per entry (omitted entirely when no logos).
            llines = ['          <img src="%s" alt="%s">' % (esc(it.get("url", "")), esc(it.get("alt", "")))
                      for it in (e.get("trust_logos") or []) if isinstance(it, dict) and it.get("url")]
            logo_strip = ("" if not llines else
                          '      <!-- ═══ LOGO TRUST STRIP — full width, beneath the two columns ═══ -->\n'
                          '      <div class="logo-strip reveal" style="--cf-d:.5s">\n'
                          '        <div class="logos">\n'
                          '%s\n'
                          '        </div>\n'
                          '      </div>' % "\n".join(llines))
            hero_html = comp("hero.html", vt, {"<!--LOGO_STRIP-->": logo_strip})

            # Booking section below the hero: cta_url → none (CTA links out); a GHL
            # calendar (ghl_calendar_url) → embedded calendar; else a Typeform application.
            ghl_cal = (e.get("ghl_calendar_url") or "").strip()
            if e.get("cta_url"):
                app_html, booking_loader, tf_preconnect = "", "", ""
            elif ghl_cal:
                app_html = (
                    '  <!-- ═══ GOHIGHLEVEL CALENDAR — VSL page ═══ -->\n'
                    '  <section class="book io" id="book">\n'
                    '    <div class="wrap">\n'
                    '      <div class="book-head">\n'
                    '        <h2>%s</h2>\n'
                    '      </div>\n'
                    '      <div class="form-shell">\n'
                    '        <div id="cal-widget" class="cal-ghl">\n'
                    '          <iframe src="%s" title="Schedule your call" scrolling="no" id="ghl-cal-embed"\n'
                    '                  style="width:100%%;border:none;overflow:hidden;min-height:780px;background:transparent"></iframe>\n'
                    '        </div>\n'
                    '      </div>\n'
                    '    </div>\n'
                    '  </section>' % (esc(e.get("form_heading", "")), esc(ghl_cal)))
                booking_loader = ('  <!-- GoHighLevel calendar loader (auto-resizes the iframe) -->\n'
                                  '  <script src="%s" async></script>' % ghl_embed_loader(ghl_cal))
                tf_preconnect = ""
            else:
                app_html = comp("application.html", vt)
                booking_loader = (
                    '  <!-- Typeform embed — UTM params (+ ad-click IDs) are forwarded from the page URL via\n'
                    '       data-tf-transitive-search-params on the form div. The matching Hidden Fields must\n'
                    '       also exist inside the Typeform (Settings -> Hidden Fields) or the values are dropped. -->\n'
                    '  <script src="https://embed.typeform.com/next/embed.js"></script>\n')
                tf_preconnect = ('<!-- Warm the Typeform connections so the application form starts loading sooner -->\n'
                                 '<link rel="preconnect" href="https://embed.typeform.com">\n'
                                 '<link rel="preconnect" href="https://form.typeform.com" crossorigin>')
            scripts_html = comp("footer-scripts.html", vt, {"<!--VSL_TYPEFORM_LOADER-->": booking_loader})
            head_vsl = comp("head-vsl.html", vt, {"<!--VSL_TYPEFORM_PRECONNECT-->": tf_preconnect})

            og_title = e.get("og_title") or e.get("page_title", "")
            og_desc = e.get("og_description") or e.get("meta_description", "")
            og = ('<!-- Open Graph -->\n'
                  '<meta property="og:title" content="%s">\n'
                  '<meta property="og:description" content="%s">\n'
                  '<meta property="og:type" content="website">' % (esc(og_title), esc(og_desc)))

            # Optional client-testimonial video section (per entry), below the booking section.
            te = e.get("testimonials") or {}
            vtesti = _render_testimonial_section(te.get("items") or [], te.get("heading"),
                                                 te.get("subheading"), "testimonials")

            body_parts = ([header_html, hero_html]
                          + ([app_html] if app_html else [])
                          + ([vtesti] if vtesti else [])
                          + [footer_html])
            page = standalone_page(e.get("page_title", ""), e.get("meta_description", ""),
                                   og, head_vsl, "\n".join(body_parts), scripts_html)
            write(os.path.join(standalone, vsl_filename(slug)), page)

            d = os.path.join(ghl, slug)
            write(os.path.join(d, "00-head-code.html"), head_vsl + "\n\n" + font_note(font_family, headline_font_b))
            write(os.path.join(d, "01-header.html"), header_html)
            write(os.path.join(d, "02-hero.html"), hero_html)
            if app_html:
                write(os.path.join(d, "03-booking.html"), app_html)
            if vtesti:
                write(os.path.join(d, "04-testimonials.html"), vtesti)
            write(os.path.join(d, "05-footer.html"), footer_html)
            write(os.path.join(d, "06-footer-scripts.html"), scripts_html)
        built.append("vsl")

    # ── Opt-in ──
    if "opt-in" in pages:
        optin_header = header_light if page_theme == "light" else header_html
        tf_id = get(brief, "optin.typeform_id")
        if tf_id:
            optin_form = comp("optin-typeform.html", T)
        else:
            optin_form = comp("optin-form.html", T, {
                "<!--OPTIN_QUALIFIER_OPTIONS-->": render_qualifier_options(brief),
                "<!--OPTIN_QUALIFIER2-->": render_qualifier2(brief),
            })
        oh = comp("optin-hero.html", T, {
            "<!--OPTIN_HEADLINE-->": render_headline(brief),
            "<!--OPTIN_SUB-->": render_optin_sub(brief),
            "<!--OPTIN_FINEPRINT-->": render_fineprint(brief),
            "<!--OPTIN_HERO_IMG-->": render_optin_hero_img(brief),
            "<!--OPTIN_HERO_TRUST-->": render_optin_hero_trust(brief),
            "<!--OPTIN_FORM-->": optin_form,
        })
        ocompare = (comp("optin-compare.html", T, {
            "<!--COMPARE_HEADING-->": esc(get(brief, "optin.compare.heading")
                                          or ("Your CPA vs. " + brief.get("brand_name", ""))),
            "<!--COMPARE_CARDS-->": render_compare_cards(brief),
        }) if get(brief, "optin.compare") else "")
        # Trust logos now live INSIDE the hero (under the CTA), so the standalone
        # trust band is retired.
        ot = ""
        owi = (comp("optin-whats-inside.html", T, {
            "<!--OPTIN_WI_INTRO-->": render_wi_intro(brief),
            "<!--OPTIN_WI_BULLETS-->": render_wi_bullets(brief),
            "<!--OPTIN_WI_MEDIA-->": render_wi_media(brief),
        }) if get(brief, "optin.whats_inside") else "")
        of = ""
        if get(brief, "optin.founder") is not None:
            of = comp("optin-founder.html", T, {
                "<!--OPTIN_FOUNDER_PHOTO-->": render_founder_photo(brief),
                "<!--OPTIN_FOUNDER_INTRO-->": render_founder_intro(brief),
                "<!--OPTIN_FOUNDER_BULLETS-->": render_founder_bullets(brief),
                "<!--OPTIN_FOUNDER_CLOSING-->": render_founder_closing(brief),
            })
        # Always include optin-scripts: the form bridge no-ops when there's no native
        # form (Typeform path), but the .io reveal observer + logo marquee must still run.
        oscripts = comp("optin-scripts.html", T, {
            "<!--OPTIN_REDIRECT-->": render_redirect_js(brief),
            "<!--OPTIN_REDIRECT_MAP-->": render_redirect_map(brief),
        })

        og_title = get(brief, "optin.og_title") or brief["optin"]["page_title"]
        og_desc = get(brief, "optin.og_description") or brief["optin"]["meta_description"]
        og = ('<!-- Open Graph -->\n'
              '<meta property="og:title" content="%s">\n'
              '<meta property="og:description" content="%s">\n'
              '<meta property="og:type" content="website">' % (esc(og_title), esc(og_desc)))
        body = "\n".join([optin_header, oh] + ([ocompare] if ocompare else []) + ([ot] if ot else []) + ([owi] if owi else []) + ([of] if of else []) + [footer_html])
        page = standalone_page(brief["optin"]["page_title"],
                               brief["optin"]["meta_description"],
                               og, "", body, oscripts)
        write(os.path.join(standalone, "opt-in.html"), page)

        d = os.path.join(ghl, "opt-in")
        write(os.path.join(d, "00-head-code.html"), font_note(font_family, headline_font_b))
        write(os.path.join(d, "01-header.html"), optin_header)
        write(os.path.join(d, "02-hero.html"), oh)
        if ocompare:
            write(os.path.join(d, "03-compare.html"), ocompare)
        if ot:
            write(os.path.join(d, "03-trust.html"), ot)
        if owi:
            write(os.path.join(d, "04-whats-inside.html"), owi)
        if of:
            write(os.path.join(d, "05-founder.html"), of)
        write(os.path.join(d, "06-footer.html"), footer_html)
        if oscripts:
            write(os.path.join(d, "07-footer-scripts.html"), oscripts)
        built.append("opt-in")

    # ── Book a call (one or more booking pages, each with its own Calendly) ──
    if "book-a-call" in pages:
        for e in book_entries(brief):
            bt = dict(T)
            bt["BOOK_HEADLINE"] = e.get("headline", "")
            # Booking pages embed EITHER a Typeform application OR a Calendly widget.
            # Both carry id="cal-widget" so the cover-card CTA (href="#cal-widget") scrolls
            # to the form/calendar on either page type.
            ghl_cal = (e.get("ghl_calendar_url") or "").strip()
            tf_id = (e.get("typeform_id") or "").strip()
            if ghl_cal:
                book_embed = (
                    '    <!-- GoHighLevel calendar embed -->\n'
                    '    <div id="cal-widget" class="cal-ghl">\n'
                    '      <iframe src="%s" title="Schedule your call" scrolling="no" id="ghl-cal-embed"\n'
                    '              style="width:100%%;border:none;overflow:hidden;min-height:780px;background:transparent"></iframe>\n'
                    '    </div>' % esc(ghl_cal))
                book_loader = ('  <!-- GoHighLevel calendar loader (auto-resizes the iframe to fit the booking widget) -->\n'
                               '  <script src="%s" async></script>' % ghl_embed_loader(ghl_cal))
            elif tf_id:
                book_embed = (
                    '    <!-- Typeform application -->\n'
                    '    <div id="cal-widget" class="cal-typeform typeform-shell">\n'
                    '      <div data-tf-live="%s" data-tf-transitive-search-params="utm_source,utm_medium,utm_campaign,utm_term,utm_content,gclid,fbclid" style="width:100%%;height:70vh;min-height:560px;"></div>\n'
                    '    </div>' % esc(tf_id))
                book_loader = ('  <!-- Typeform loader -->\n'
                               '  <script src="https://embed.typeform.com/next/embed.js" async></script>')
            else:
                book_embed = (
                    '    <div class="calendly-inline-widget" data-url="%s" style="min-width:320px;height:780px;"></div>'
                    % esc(e.get("calendly_url", "")))
                book_loader = ('  <script src="https://assets.calendly.com/assets/external/widget.js" async></script>')
            cal_html = comp("cal-content.html", bt, {
                "<!--BOOK_SUB-->": render_book_sub(e),
                "<!--BOOK_EMBED-->": book_embed,
                "<!--BOOK_LOADER-->": book_loader,
            })
            body = "\n".join([header_light, cal_html, footer_html])
            page = standalone_page(e["page_title"], e["meta_description"], "", "", body)
            slug = (e.get("slug") or "book-a-call").strip()
            write(os.path.join(standalone, slug + ".html"), page)

            d = os.path.join(ghl, slug)
            write(os.path.join(d, "00-head-code.html"), font_note(font_family, headline_font_b))
            write(os.path.join(d, "01-header.html"), header_light)
            write(os.path.join(d, "02-content.html"), cal_html)
            write(os.path.join(d, "03-footer.html"), footer_html)
        built.append("book-a-call")

    # ── Call confirmation (thank-you) ──
    if "confirmation" in pages:
        head_confirm = comp("head-confirm.html", T, {"<!--CONFIRM_HEAD-->": render_confirm_head(brief)})
        ch = comp("confirm-hero.html", T, {
            "<!--CONFIRM_HEADLINE-->": render_confirm_headline(brief),
            "<!--CONFIRM_SUB-->": render_confirm_sub(brief),
            "<!--CONFIRM_CUE-->": render_confirm_cue(brief),
            "<!--CONFIRM_HERO_VIDEO-->": render_confirm_hero_video(brief),
            "<!--CONFIRM_REMINDER-->": render_confirm_reminder(brief),
        })
        cs = comp("confirm-steps.html", T, {
            "<!--CONFIRM_STEPS-->": render_confirm_steps(brief),
            "<!--CONFIRM_STEPS_EYEBROW-->": render_confirm_steps_eyebrow(brief),
        })
        cscripts = comp("confirm-scripts.html", T)

        cresources = ""
        if get(brief, "confirmation.resources") or get(brief, "confirmation.video"):
            cresources = comp("confirm-resources.html", T, {
                "<!--CONFIRM_VIDEO-->": render_confirm_video(brief),
                "<!--CONFIRM_RESOURCES-->": render_confirm_resources(brief),
            })

        og_title = get(brief, "confirmation.og_title") or brief["confirmation"]["page_title"]
        og_desc = get(brief, "confirmation.og_description") or brief["confirmation"]["meta_description"]
        head_extra = ('<!-- Open Graph -->\n'
                      '<meta property="og:title" content="%s">\n'
                      '<meta property="og:description" content="%s">\n'
                      '<meta property="og:type" content="website">\n'
                      '<meta name="robots" content="noindex">' % (esc(og_title), esc(og_desc)))
        cfaqs = render_confirm_faqs(brief)   # optional FAQ-video grid, sits below the resources block
        ctesti = render_confirm_testimonials(brief)   # optional client-testimonial grid, below the FAQ grid

        parts = ([header_html, ch, cs]
                 + ([cresources] if cresources else [])
                 + ([cfaqs] if cfaqs else [])
                 + ([ctesti] if ctesti else [])
                 + [footer_html])
        page = standalone_page(brief["confirmation"]["page_title"],
                               brief["confirmation"]["meta_description"],
                               head_extra, head_confirm, "\n".join(parts), cscripts)
        write(os.path.join(standalone, "confirmation.html"), page)

        d = os.path.join(ghl, "confirmation")
        write(os.path.join(d, "00-head-code.html"), head_confirm + "\n\n" + font_note(font_family, headline_font_b))
        write(os.path.join(d, "01-header.html"), header_html)
        write(os.path.join(d, "02-hero.html"), ch)
        write(os.path.join(d, "03-steps.html"), cs)
        if cresources:
            write(os.path.join(d, "04-resources.html"), cresources)
        if cfaqs:
            write(os.path.join(d, "05-faqs.html"), cfaqs)
        if ctesti:
            write(os.path.join(d, "05b-testimonials.html"), ctesti)
        write(os.path.join(d, "06-footer.html"), footer_html)
        write(os.path.join(d, "07-footer-scripts.html"), cscripts)
        built.append("confirmation")

    # ── Results (testimonials) ──
    if "results" in pages:
        rc = comp("results-content.html", T, {
            "<!--RESULTS_SUB-->": render_results_sub(brief),
            "<!--RESULTS_VIDEOS-->": render_results_videos(brief),
            "<!--RESULTS_REVIEWS-->": render_results_reviews(brief),
            "<!--RESULTS_CTA-->": render_results_cta(brief),
        })
        rscripts = comp("results-scripts.html", T)
        rhead = render_results_head(brief)
        og_title = get(brief, "results.og_title") or brief["results"]["page_title"]
        og_desc = get(brief, "results.og_description") or brief["results"]["meta_description"]
        og = ('<!-- Open Graph -->\n'
              '<meta property="og:title" content="%s">\n'
              '<meta property="og:description" content="%s">\n'
              '<meta property="og:type" content="website">' % (esc(og_title), esc(og_desc)))
        body = "\n".join([header_light, rc, footer_html])
        page = standalone_page(brief["results"]["page_title"],
                               brief["results"]["meta_description"],
                               og, rhead, body, rscripts)
        write(os.path.join(standalone, "results.html"), page)

        d = os.path.join(ghl, "results")
        write(os.path.join(d, "00-head-code.html"),
              (rhead + "\n\n" + font_note(font_family, headline_font_b)) if rhead else font_note(font_family, headline_font_b))
        write(os.path.join(d, "01-header.html"), header_light)
        write(os.path.join(d, "02-content.html"), rc)
        write(os.path.join(d, "03-footer.html"), footer_html)
        write(os.path.join(d, "04-footer-scripts.html"), rscripts)
        built.append("results")

    # ── Legal pages ──
    noindex = '<meta name="robots" content="noindex">'
    for name, tpl, title in [
        ("privacy", "legal-privacy.html", "Privacy Policy"),
        ("terms", "legal-terms.html", "Terms & Conditions"),
    ]:
        if name in pages:
            legal_html = comp(tpl, T)
            body = "\n".join([header_light, legal_html, footer_html])
            page = standalone_page("%s | %s" % (title, brief["brand_name"]),
                                   "%s for %s." % (title, brief["legal_entity"]),
                                   noindex, "", body)
            write(os.path.join(standalone, name + ".html"), page)

            d = os.path.join(ghl, name)
            write(os.path.join(d, "00-head-code.html"), font_note(font_family, headline_font_b))
            write(os.path.join(d, "01-header.html"), header_light)
            write(os.path.join(d, "02-content.html"), legal_html)
            write(os.path.join(d, "03-footer.html"), footer_html)
            built.append(name)

    # ── 404 (page not found) ──
    if "404" in pages:
        nf = comp("notfound.html", T)
        body = "\n".join([header_html, nf, footer_html])
        page = standalone_page(brief["404"]["page_title"], brief["404"]["meta_description"],
                               '<meta name="robots" content="noindex">', "", body)
        write(os.path.join(standalone, "404.html"), page)

        d = os.path.join(ghl, "404")
        write(os.path.join(d, "00-head-code.html"), font_note(font_family, headline_font_b))
        write(os.path.join(d, "01-header.html"), header_html)
        write(os.path.join(d, "02-content.html"), nf)
        write(os.path.join(d, "03-footer.html"), footer_html)
        built.append("404")

    # One paste guide PER DEPLOY, scoped to exactly this batch of pages — a single-page
    # deploy gets a doc about that one page; a multi-page batch gets one doc covering
    # all of them. A legacy whole-funnel README.md from an older build is removed so a
    # stale guide can't be followed by mistake (only if this script generated it).
    date_iso = datetime.date.today().isoformat()
    batch = "+".join(built) if len(built) <= 3 else "%d-pages" % len(built)
    readme_name = "README-%s-%s.md" % (date_iso, batch)
    legacy = os.path.join(out, "README.md")
    if os.path.isfile(legacy) and "Generated by the `client-funnel-pages` skill" in read(legacy):
        os.remove(legacy)
    write(os.path.join(out, readme_name),
          client_readme(brief, built, font_family, date_iso, partial=bool(deploy_pages)))
    return out, built, readme_name


def client_readme(brief, built, font_family, date_iso, partial=False):
    rows = {
        "vsl": "- **vsl** — VSL landing page (hero + video + Typeform application)",
        "opt-in": "- **opt-in** — lead-magnet opt-in (hero form → hidden GHL form, trust band, what's-inside, founder bio)",
        "book-a-call": "- **book-a-call** — headline + booking embed",
        "confirmation": "- **confirmation** — call confirmation / thank-you (urgency video + next-step cards w/ visuals + 'before we talk' video & links) (noindex)",
        "results": "- **results** — testimonial video grid (click-to-play YouTube) + platform-review cards + CTA",
        "privacy": "- **privacy** — Privacy Policy (noindex)",
        "terms": "- **terms** — Terms & Conditions (noindex)",
        "404": "- **404** — branded page-not-found (centered message + Back-to-Home) (noindex)",
    }

    def _book_embed_label(e):
        if (e.get("ghl_calendar_url") or "").strip():
            return "GoHighLevel calendar embed", e.get("ghl_calendar_url", "")
        if (e.get("typeform_id") or "").strip():
            return "Typeform application", e.get("typeform_id", "")
        return "Calendly embed", e.get("calendly_url", "")

    _be = book_entries(brief)
    if len(_be) == 1:
        _lbl, _tgt = _book_embed_label(_be[0])
        rows["book-a-call"] = "- **book-a-call** — headline + %s" % _lbl
    elif len(_be) > 1:
        subs = "\n".join("    - `%s/` (standalone `%s.html`) → %s (%s)"
                         % (e.get("slug", "book-a-call"), e.get("slug", "book-a-call"),
                            _book_embed_label(e)[1], _book_embed_label(e)[0])
                         for e in _be)
        rows["book-a-call"] = ("- **book-a-call** — %d booking pages:\n%s" % (len(_be), subs))
    optin_setup = ""
    if "opt-in" in built:
        optin_setup = """
## Opt-in form
The built page ships branded HTML (First Name, Email, Phone, Revenue) with a
placeholder submit. `deploy-ghl` wires the hidden native GHL form.
Do not embed a webhook here.
"""
    scope_note = (
        "This doc covers ONLY the pages in this deploy batch — other pages in the funnel"
        "\nare untouched and keep their own deploy README."
        if partial else
        "This doc covers every page in this deploy batch."
    )
    return """# {brand} — Funnel Deploy — {date}

Generated by the `client-funnel-pages` skill.
**Pages in this deploy:** {built}
{scope_note}

## Preview vs deploy

**Preview:** open the matching file in `standalone/` over http (not `file://`).
**Deploy:** after `funnel-qc` SHIP, use `deploy-ghl`. Do not paste from this README.

- **GHL** → `deploy-ghl` (iframe Wistia only; never `player.js` in head tracking)

## Pages in this batch

{rows}
{optin_setup}
## ⚠️ Before you publish
- **Legal pages are boilerplate templates, not legal advice.** Have the client's
  counsel review the Privacy Policy, Terms, and footer earnings disclaimer against
  the client's actual entity, jurisdiction, and data practices before going live.
- **Typeform UTM passthrough:** the matching Hidden Fields (utm_source, etc.) must
  exist inside the Typeform itself, or the values are dropped.
""".format(
        brand=brief.get("brand_name", "Client"),
        date=date_iso,
        built=", ".join(built),
        scope_note=scope_note,
        font=font_family,
        rows="\n".join(rows[b] for b in built),
        optin_setup=optin_setup,
    )


# ──────────────────────────────────────────────────────────────────────────
def print_brand_lock(brief):
    """Print the resolved brand-lock (palette, logo dims, theme) for Gate A sign-off,
    without building. Surfaces a bad-scrape / default color immediately."""
    accent = (brief.get("accent") or "").strip()
    if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", accent):
        die("accent is not a valid hex color", ['Got: "%s"' % brief.get("accent")])
    if not brief.get("brand_lock_confirmed"):
        for field in ("accent", "accent_bright", "page_bg", "card_bg"):
            nh = norm_hex(brief.get(field))
            if nh and nh in FRAMEWORK_DEFAULT_HEXES:
                die("%s = %s looks like a page-builder default, not the brand color" % (field, nh), [
                    'Re-scrape the real color, or set "brand_lock_confirmed": true after sign-off.',
                ])
    ar = parse_aspect_ratio(brief.get("logo_aspect")) or 6.0
    hover = (brief.get("accent_bright") or (lighten(accent) if accent else "")).strip()
    lw = brief.get("logo_width")
    logo_w = int(lw) if lw else max(110, min(round(34 * ar), 460))
    print("\n  ══ BRAND LOCK — confirm before building ══\n")
    print("    Brand      : %s  (%s)" % (brief.get("brand_name", ""), brief.get("legal_entity", "")))
    print("    Theme      : %s" % (brief.get("theme") or "dark").strip().lower())
    print("    Accent     : %s   hover %s" % (accent, hover))
    print("    Page bg    : %s   card bg %s" % (brief.get("page_bg") or "#f5f5f5",
                                                brief.get("card_bg") or "#121212"))
    print("    Fonts      : body %s / headline %s" % (brief.get("font_family") or "Poppins",
                                                       brief.get("headline_font") or "(same)"))
    print("    Logo       : %s" % (brief.get("logo_url") or "(none)"))
    print("    Logo size  : aspect %s (%.1f:1) -> renders ~%dpx wide in the header"
          % (brief.get("logo_aspect", ""), ar, logo_w))
    print("\n    ↳ Confirm these are the client's REAL brand values before building.\n")


def _norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_client_dir(brand_name):
    """Locate the client's folder under CANONICAL_LP_DIR by normalized name
    (exact match first, then containment either way). None if no match / no dir."""
    if not os.path.isdir(CANONICAL_LP_DIR):
        return None
    target = _norm_name(brand_name)
    if not target:
        return None
    dirs = [d for d in sorted(os.listdir(CANONICAL_LP_DIR))
            if os.path.isdir(os.path.join(CANONICAL_LP_DIR, d))]
    for d in dirs:
        if _norm_name(d) == target:
            return os.path.join(CANONICAL_LP_DIR, d)
    for d in dirs:
        nd = _norm_name(d)
        if nd and (nd in target or target in nd):
            return os.path.join(CANONICAL_LP_DIR, d)
    return None


def check_prior_art(brief, brief_path):
    """If this client already has built funnels, refuse to build until the brief
    acknowledges them ("prior_art_checked": true). Existing pages are the styling
    source of truth — 'we already have this, why didn't you look' was the single
    most repeated correction in this skill's history."""
    if brief.get("prior_art_checked"):
        return
    client_dir = find_client_dir(brief.get("brand_name"))
    if not client_dir:
        return  # greenfield — nothing to inherit
    existing = []
    for entry in sorted(os.listdir(client_dir)):
        b = os.path.join(client_dir, entry, "brief.jsonc")
        if os.path.isfile(b) and os.path.abspath(b) != os.path.abspath(brief_path):
            existing.append(b)
    if existing:
        die("existing funnels found for this client — prior-art pass required", [
            "This client already has built funnels. Read them FIRST and inherit their",
            "styles (stylesheet, footer, logo variants, section patterns) instead of",
            "re-deriving from the house template:",
            "",
        ] + ["  • " + p for p in existing] + [
            "",
            'Then set "prior_art_checked": true in the brief and re-run.',
        ])


def main():
    ap = argparse.ArgumentParser(description="Render a client funnel from a brand brief.")
    ap.add_argument("brief", help="Path to the brand brief (.jsonc / .json)")
    ap.add_argument("--out", default=os.getcwd(),
                    help="Output directory (default: current directory; must be inside the "
                         "canonical '01 Landing Pages' drive folder)")
    ap.add_argument("--brand-lock", action="store_true",
                    help="Print the resolved brand-lock (palette, logo, theme) and exit — for Gate A sign-off.")
    ap.add_argument("--allow-out-anywhere", action="store_true",
                    help="Skip the canonical-location check on --out (throwaway experiments only).")
    ap.add_argument("--pages", default=None,
                    help="Comma-separated deploy batch (e.g. 'vsl,confirmation'). Only these "
                         "pages are rebuilt, other pages' output is left untouched, and the "
                         "deploy README covers only this batch. Omit to build the brief's full "
                         "page list.")
    args = ap.parse_args()

    brief = load_brief(args.brief)
    if args.brand_lock:
        print_brand_lock(brief)
        return

    out_abs = os.path.abspath(args.out)
    if not args.allow_out_anywhere and not (
            out_abs == CANONICAL_LP_DIR or out_abs.startswith(CANONICAL_LP_DIR + os.sep)):
        die("output path is outside the canonical landing-pages folder", [
            "Client funnels live under:",
            "  " + CANONICAL_LP_DIR,
            "Got --out:",
            "  " + out_abs,
            "Point --out at '<canonical>/<Client>/<funnel>' so the build lands where the",
            "team expects it, or pass --allow-out-anywhere for a throwaway experiment.",
        ])

    check_prior_art(brief, args.brief)
    deploy_pages = ([p.strip() for p in args.pages.split(",") if p.strip()]
                    if args.pages else None)
    out, built, readme_name = build(brief, out_abs, deploy_pages)

    label = "deploy batch" if deploy_pages else "funnel"
    print("\n  ✓ %s built — %d page(s): %s\n" % (label.capitalize(), len(built), ", ".join(built)))
    print("    " + out)
    print("      ├─ standalone/   (open these to preview)")
    print("      ├─ ghl/          (for deploy-ghl only; do not paste from the builder)")
    print("      └─ %s   (paste guide for THIS deploy + pre-publish checklist)\n" % readme_name)


if __name__ == "__main__":
    main()
