#!/usr/bin/env python3
"""
sync_css.py — CSS safety for the client-funnel-pages system.

The #1 historical pain was CSS: shared styles edited in one place breaking OTHER pages,
copies drifting out of sync, and a stylesheet outgrowing GoHighLevel's 12,000-char
custom-VALUE limit. This skill already avoids the multi-copy trap (ONE styles.css is the
single source, inlined identically into every standalone page and written once to
ghl/styles.css). This tool guards the rest:

  check <funnel-dir>   Confirm every built page carries the IDENTICAL shared stylesheet
                       (single-source), and report its size against GHL's 12k custom-value
                       budget. Exits non-zero if a page's CSS diverges. Run after any CSS
                       change + rebuild, before handoff.

  chunk <css|funnel>   Split the stylesheet into <=12,000-char pieces at rule boundaries
                       (keeping @media blocks whole) for the GHL custom-VALUES deploy route
                       (paste chunk 1..N into custom values, concatenate at the reference).
                       Default deploy pastes the whole file into the page-wide Custom CSS
                       box, which has no 12k limit — use chunk only for the values route.

  diff <old.css> <new.css>
                       Selector-level diff of EFFECTIVE (cascaded) declarations between two
                       stylesheets — the blast radius of a styles.css edit. Save a baseline
                       (cp the old ghl/styles.css) before editing, then diff to see exactly
                       which selectors changed across the whole system.

The brace-aware CSS parser is adapted from the SYAF _design-system split-css.py / reconcile.py.
"""
import os
import re
import sys

GHL_CUSTOM_VALUE_LIMIT = 12000   # hard cap per GHL custom value
CHUNK_MAX = 11800                # safe target (leaves room for a concat separator)


def die(title, lines):
    print("\n  ✗ " + title + "\n", file=sys.stderr)
    for ln in lines:
        print("      " + ln, file=sys.stderr)
    print("", file=sys.stderr)
    sys.exit(1)


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


# ── Brace-aware top-level rule splitter (keeps @media / @keyframes blocks intact) ──
def top_level_units(css):
    """Yield each top-level rule / at-block as one string, in source order."""
    css = strip_comments(css)
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        head = css[i:j]
        if head.strip().startswith("@") and not head.strip().startswith("@import"):
            # nested at-block: balance braces
            depth, k = 1, j + 1
            while k < n and depth > 0:
                depth += (css[k] == "{") - (css[k] == "}")
                k += 1
            yield css[i:k].strip()
            i = k
        else:
            k = css.find("}", j)
            if k < 0:
                break
            yield css[i:k + 1].strip()
            i = k + 1


# ── reconcile-style parser: (media, selector) -> effective declarations ──
def _norm(v):
    v = v.strip().lower()
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"\s*([:,])\s*", r"\1", v)
    return v


def _parse_decls(body):
    d = {}
    for part in body.split(";"):
        if ":" in part:
            k, _, val = part.partition(":")
            k = k.strip().lower()
            if k:
                d[k] = _norm(val)
    return d


def parse_effective(css):
    css = strip_comments(css)
    eff = {}
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        head = css[i:j].strip()
        if head.startswith("@media"):
            depth, k = 1, j + 1
            while k < n and depth > 0:
                depth += (css[k] == "{") - (css[k] == "}")
                k += 1
            inner = css[j + 1:k - 1]
            m = 0
            while True:
                jj = inner.find("{", m)
                if jj < 0:
                    break
                sels = inner[m:jj].strip()
                kk = inner.find("}", jj)
                decls = _parse_decls(inner[jj + 1:kk])
                for s in sels.split(","):
                    s = s.strip()
                    if s:
                        eff.setdefault((_norm(head), s), {}).update(decls)
                m = kk + 1
            i = k
        elif head.startswith("@"):
            depth, k = 1, j + 1
            while k < n and depth > 0:
                depth += (css[k] == "{") - (css[k] == "}")
                k += 1
            i = k
        else:
            k = css.find("}", j)
            if k < 0:
                break
            decls = _parse_decls(css[j + 1:k])
            for s in head.split(","):
                s = s.strip()
                if s:
                    eff.setdefault((None, s), {}).update(decls)
            i = k + 1
    return eff


def _norm_ws(s):
    return re.sub(r"\s+", " ", strip_comments(s)).strip()


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _resolve_css(arg):
    """Accept a .css file OR a funnel dir (uses its ghl/styles.css)."""
    if os.path.isdir(arg):
        p = os.path.join(arg, "ghl", "styles.css")
        if not os.path.isfile(p):
            p2 = os.path.join(arg, "styles.css")
            p = p2 if os.path.isfile(p2) else p
        if not os.path.isfile(p):
            die("no stylesheet found", ["Looked for ghl/styles.css under: " + arg])
        return p
    if not os.path.isfile(arg):
        die("file not found", [arg])
    return arg


def pack_chunks(css):
    """Greedily pack top-level rules into <=CHUNK_MAX-char chunks (keeping @media whole)."""
    chunks, cur = [], ""
    for u in top_level_units(css):
        add = (u if not cur else "\n" + u)
        if cur and len(cur) + len(add) > CHUNK_MAX:
            chunks.append(cur)
            cur = u
        else:
            cur += add
    if cur:
        chunks.append(cur)
    return chunks


def chunk(arg):
    css_path = _resolve_css(arg)
    css = _read(css_path)
    oversized = [u for u in top_level_units(css) if len(u) > CHUNK_MAX]
    if oversized:
        die("a single CSS rule exceeds the chunk size", [
            "%d rule(s) are individually larger than %d chars and can't be split cleanly."
            % (len(oversized), CHUNK_MAX),
            "First offender starts: " + oversized[0][:80].replace("\n", " "),
        ])
    chunks = pack_chunks(css)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(css_path)), "css-chunks")
    os.makedirs(out_dir, exist_ok=True)
    for idx, c in enumerate(chunks, 1):
        with open(os.path.join(out_dir, "styles_%d.txt" % idx), "w", encoding="utf-8") as f:
            f.write(c)
    print("\n  Stylesheet: %s chars" % f"{len(css):,}")
    print("  Split into %d custom-value chunk(s) (<=%d each), written to:" % (len(chunks), CHUNK_MAX))
    print("    " + out_dir)
    for idx, c in enumerate(chunks, 1):
        print("      styles_%d.txt : %s chars" % (idx, f"{len(c):,}"))
    print("\n  Paste each into a GHL custom value and concatenate them at the reference.\n")


def check(funnel_dir):
    if not os.path.isdir(funnel_dir):
        die("not a funnel directory", [funnel_dir])
    shared_path = os.path.join(funnel_dir, "ghl", "styles.css")
    if not os.path.isfile(shared_path):
        die("ghl/styles.css not found", ["Build the funnel first; expected: " + shared_path])
    shared = _read(shared_path)
    shared_norm = _norm_ws(shared)

    standalone = os.path.join(funnel_dir, "standalone")
    pages = sorted(f for f in os.listdir(standalone) if f.endswith(".html")) \
        if os.path.isdir(standalone) else []
    diverged, checked = [], 0
    for p in pages:
        html = _read(os.path.join(standalone, p))
        m = re.search(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I)
        if not m:
            continue
        checked += 1
        if _norm_ws(m.group(1)) != shared_norm:
            diverged.append(p)

    size = len(shared)
    values = len(pack_chunks(shared))
    print("\n  Shared stylesheet : %s chars" % f"{size:,}")
    print("  Pages checked     : %d (inlined <style> compared to ghl/styles.css)" % checked)
    print("  Single-source     : %s" % ("✓ all pages identical" if not diverged else "✗ DIVERGENCE"))
    print("  GHL deploy        : fits the page-wide Custom CSS box as one block.")
    if size > GHL_CUSTOM_VALUE_LIMIT:
        print("  Custom-values route: needs %d chunks (<=12k each) — run `chunk` for that route." % values)
    if diverged:
        die("some pages have CSS that differs from the shared stylesheet", [
            "These standalone pages don't match ghl/styles.css:",
            "  " + ", ".join(diverged),
            "Every page must consume the ONE shared stylesheet — rebuild from the brief.",
        ])
    print("")


def diff(old_path, new_path):
    old = parse_effective(_read(_resolve_css(old_path)))
    new = parse_effective(_read(_resolve_css(new_path)))
    old_keys, new_keys = set(old), set(new)
    added = new_keys - old_keys
    removed = old_keys - new_keys
    changed = []
    for key in old_keys & new_keys:
        od, nd = old[key], new[key]
        props = set(od) | set(nd)
        d = {p: (od.get(p, "∅"), nd.get(p, "∅")) for p in props if od.get(p) != nd.get(p)}
        if d:
            changed.append((key, d))

    def label(k):
        media, sel = k
        return ("[%s] " % media if media else "") + sel

    print("\n  CSS diff — blast radius of the change\n")
    print("  Selectors added   : %d" % len(added))
    for k in sorted(added, key=label)[:40]:
        print("      + " + label(k))
    print("  Selectors removed : %d" % len(removed))
    for k in sorted(removed, key=label)[:40]:
        print("      - " + label(k))
    print("  Selectors changed : %d" % len(changed))
    for k, d in sorted(changed, key=lambda x: label(x[0]))[:60]:
        print("      ~ " + label(k))
        for p, (ov, nv) in d.items():
            print("          %s:  %s  ->  %s" % (p, ov, nv))
    if not (added or removed or changed):
        print("  (identical)")
    print("")


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("check", "chunk", "diff"):
        print(__doc__)
        sys.exit(0 if args[:1] in (["-h"], ["--help"], []) else 2)
    mode = args[0]
    if mode == "check":
        if len(args) != 2:
            die("usage", ["sync_css.py check <funnel-dir>"])
        check(args[1])
    elif mode == "chunk":
        if len(args) != 2:
            die("usage", ["sync_css.py chunk <styles.css | funnel-dir>"])
        chunk(args[1])
    elif mode == "diff":
        if len(args) != 3:
            die("usage", ["sync_css.py diff <old.css|funnel> <new.css|funnel>"])
        diff(args[1], args[2])


if __name__ == "__main__":
    main()
