#!/usr/bin/env python3
"""
audit_links.py — link & embed audit for a built client funnel.

For every standalone page in <funnel>/standalone/, it lists each linked element
and exactly where it points, categorized as:

  [same-page]  a #anchor on this page        — verifies the target id exists here
  [own-site]   an http(s) link to the client's own domain (a funnel/site page)
  [external]   any other http(s) link
  [embed]      Wistia / YouTube / Typeform / Calendly / <video> / <img>
  [LOCAL ⚠]    a non-hosted path (local file) — WILL break in GHL; must be a media link
  [contact]    mailto: / tel:

Then it liveness-checks every external URL + embed (HTTP status, or the platform's
media/oembed API) so a dead link — or a redirect to a domain that doesn't resolve —
is caught BEFORE launch. It also validates the ghl/ deliverable structure (one shared
styles.css + one folder of per-section files per page — never a collapsed single
block). Run it as the final step of every funnel build.

Usage:
    python3 audit_links.py "<...>/01 Landing Pages/<Client>/<funnel>"
"""
import argparse, html as _html, os, re, sys, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
_CACHE = {}


def check(url):
    """HTTP status (follows redirects) or an error label. Cached per URL."""
    if url in _CACHE:
        return _CACHE[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            res = r.status
    except urllib.error.HTTPError as e:
        res = e.code
    except Exception as e:
        res = "NO-RESOLVE (" + type(e).__name__ + ")"
    _CACHE[url] = res
    return res


def ok(status):
    return isinstance(status, int) and 200 <= status < 400


def base_domain(host):
    p = (host or "").split(".")
    return ".".join(p[-2:]) if len(p) >= 2 else host


def host_of(url):
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).lower() if m else ""


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def audit_page(path, funnel_base):
    h = open(path, encoding="utf-8").read()
    ids = set(re.findall(r'\sid="([^"]+)"', h))
    rows = []   # (category, label, target, status)

    # ── anchors ──
    for url, inner in re.findall(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', h, re.S | re.I):
        label = (strip_tags(inner) or "(no text)")[:40]
        if url.startswith("#"):
            present = url[1:] in ids
            rows.append(("same-page", label, url,
                         "target found" if present else "⚠ NO TARGET id on page"))
        elif url.startswith(("mailto:", "tel:")):
            rows.append(("contact", label, url, "—"))
        elif url.startswith("http"):
            cat = "own-site" if base_domain(host_of(url)) == funnel_base else "external"
            rows.append((cat, label, url, check(url)))
        else:
            rows.append(("LOCAL ⚠", label, url, "non-hosted path — fix before GHL"))

    # ── embeds ──
    for fid in dict.fromkeys(re.findall(r'data-tf-live="([^"]+)"', h)):
        rows.append(("embed", "Typeform form", fid,
                     check("https://form.typeform.com/to/" + fid)))
    for url in dict.fromkeys(re.findall(r'data-url="([^"]+)"', h)):
        rows.append(("embed", "Calendly", url, check(url)))
    # GoHighLevel calendar embeds (<iframe src=".../widget/booking/ID">) — matched by the
    # GHL-specific /widget/booking/ path so white-label domains (link.<brand>.com) are caught too.
    for url in dict.fromkeys(re.findall(
            r'<iframe[^>]*\ssrc="([^"]*/widget/booking/[^"]+)"', h)):
        if re.search(r'REPLACE|PLACEHOLDER|YOUR[_-]|XXXX|CALENDAR_ID|EXAMPLE', url, re.I):
            status = "⚠ PLACEHOLDER — paste the real GHL calendar embed URL"
        else:
            status = check(url)
        rows.append(("embed", "GHL calendar", url, status))
    for wid in dict.fromkeys(re.findall(r'<wistia-player[^>]*media-id="([^"]+)"', h)):
        rows.append(("embed", "Wistia video", wid,
                     check("https://fast.wistia.com/embed/medias/%s.json" % wid)))
    for wid in dict.fromkeys(re.findall(r'fast\.wistia\.net/embed/iframe/([a-z0-9]+)', h)):
        rows.append(("embed", "Wistia iframe", wid,
                     check("https://fast.wistia.com/embed/medias/%s.json" % wid)))
    yids = re.findall(r'youtube\.com/embed/([\w-]+)', h) + re.findall(r'youtu\.be/([\w-]+)', h)
    for yid in dict.fromkeys(yids):
        rows.append(("embed", "YouTube video", yid,
                     check("https://www.youtube.com/oembed?url=https://youtu.be/%s&format=json" % yid)))
    for src in dict.fromkeys(re.findall(r'<source[^>]*src="([^"]+)"', h) +
                             re.findall(r'<video[^>]*\ssrc="([^"]+)"', h)):
        rows.append(("embed", "video file", src,
                     check(src) if src.startswith("http") else "LOCAL ⚠ — upload + use media link"))
    for src in dict.fromkeys(re.findall(r'<img\b[^>]*\ssrc="([^"]+)"', h)):
        if src.startswith("data:"):
            continue
        rows.append(("embed", "image", src,
                     check(src) if src.startswith("http") else "LOCAL ⚠ — upload + use media link"))
    return rows


def check_ghl_structure(root):
    """Validate the ghl/ deliverable: one shared styles.css + one folder of
    per-section .html files per standalone page. A page collapsed into a single
    block (or missing entirely) breaks the GHL paste workflow — this is the
    'each section of the page should be its own html file' rule, enforced.
    Returns a list of problem strings (empty = clean)."""
    problems = []
    ghl = os.path.join(root, "ghl")
    standalone = os.path.join(root, "standalone")
    if not os.path.isdir(ghl):
        return ["ghl/: directory missing — nothing paste-ready was produced"]
    if not os.path.isfile(os.path.join(ghl, "styles.css")):
        problems.append("ghl/styles.css: missing — every page must share ONE stylesheet")

    loose = [f for f in os.listdir(ghl) if f.endswith(".html")]
    for f in loose:
        problems.append("ghl/%s: page-level .html at ghl/ root — split it into "
                        "per-section files in ghl/<page>/" % f)

    if os.path.isdir(standalone):
        for page in sorted(p for p in os.listdir(standalone) if p.endswith(".html")):
            stem = page[:-5]
            page_dir = os.path.join(ghl, stem)
            if not os.path.isdir(page_dir):
                problems.append("ghl/%s/: missing — no paste-ready sections for %s"
                                % (stem, page))
                continue
            sections = [f for f in os.listdir(page_dir) if f.endswith(".html")]
            if not sections:
                problems.append("ghl/%s/: no section .html files inside" % stem)
                continue
            for s in sections:
                body = open(os.path.join(page_dir, s), encoding="utf-8").read()
                n = len(re.findall(r"<section\b", body, re.I))
                if n >= 3:
                    problems.append("ghl/%s/%s: contains %d <section> blocks — looks "
                                    "like a collapsed page, split per section"
                                    % (stem, s, n))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("funnel", help="path to the <client>-funnel dir (or its standalone/ dir)")
    ap.add_argument("--ghl", action="store_true",
                    help="also validate ghl/ section split (deploy-ghl only)")
    args = ap.parse_args()

    root = args.funnel
    standalone = root if os.path.basename(root.rstrip("/")) == "standalone" \
        else os.path.join(root, "standalone")
    if not os.path.isdir(standalone):
        print("✗ no standalone/ dir at: " + standalone, file=sys.stderr)
        sys.exit(1)

    pages = sorted(p for p in os.listdir(standalone) if p.endswith(".html"))
    if not pages:
        print("✗ no .html pages in " + standalone, file=sys.stderr)
        sys.exit(1)

    # Infer the client's own domain from a privacy/terms/legal link (for own-site tagging).
    blob = "".join(open(os.path.join(standalone, p), encoding="utf-8").read() for p in pages)
    m = re.search(r'https?://([^/"]*?(?:legal|privacy|terms)[^/"]*|[^/"]+)/(?:legal|privacy|terms)', blob)
    funnel_base = base_domain(host_of(m.group(0))) if m else ""
    print("Auditing %d page(s) in %s" % (len(pages), standalone))
    print("Client domain (own-site tag): %s\n" % (funnel_base or "(could not infer)"))

    problems = []

    # ── GHL deliverable structure (only when --ghl; deploy-ghl owns this) ──
    if args.ghl and root != standalone:
        ghl_problems = check_ghl_structure(root)
        print("══ ghl/ structure ══")
        if ghl_problems:
            for gp in ghl_problems:
                print("  [ghl ⚠    ] %s" % gp)
            problems.extend("ghl structure: " + gp for gp in ghl_problems)
        else:
            print("  [ghl      ] per-section split + shared styles.css   (ok)")
        print()

    for p in pages:
        rows = audit_page(os.path.join(standalone, p), funnel_base)
        print("══ %s ══" % p)
        for cat, label, target, status in rows:
            flag = "" if (status in ("—", "target found") or ok(status)) else "   ‹‹ CHECK"
            print("  [%-9s] %-34s → %s   (%s)%s" % (cat, label, target, status, flag))
            if "⚠" in str(cat) or "⚠" in str(status) or (not ok(status) and status not in ("—", "target found")):
                problems.append("%s: %s → %s (%s)" % (p, label, target, status))
        print()

    print("═" * 60)
    if problems:
        print("⚠ %d ITEM(S) TO FIX:" % len(problems))
        for pr in problems:
            print("  • " + pr)
        sys.exit(1)
    print("✓ All links, anchors, and embeds resolve.")


if __name__ == "__main__":
    main()
