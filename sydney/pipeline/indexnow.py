"""IndexNow: list the pages that changed since the live site, for the deploy job to submit once they are live.

  python indexnow.py LIVE_SITEMAP_URL NEW_SITEMAP_PATH OUT_JSON

Compares the sitemap about to be published with the one live now. A page is submitted when it is new, gone, or its
<lastmod> moved; Sydney pages move once a day (the day's call), pages outside Sydney when their prices do, so the
five runs a day submit each page at most once a day. Writes OUT_JSON (the POST body for api.indexnow.org) only when
something changed. Never fails the build: any problem prints a warning and writes nothing. Standard library only.
The key is seo_pages.INDEXNOW_KEY, served at /{key}.txt (docs/SEO.md).
"""
import json, os, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_pages import INDEXNOW_KEY, SITE

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
LIMIT = 10_000                                     # IndexNow's most URLs in one request


def parse(xml_bytes):
    """{loc: lastmod} from a sitemap."""
    root = ET.fromstring(xml_bytes)
    return {u.findtext("s:loc", "", NS).strip(): u.findtext("s:lastmod", "", NS).strip() for u in root.findall("s:url", NS)}


def changed(old, new, site=SITE):
    """New, moved and removed addresses on this site, new and moved first (sitemap order), capped at LIMIT."""
    host = urllib.parse.urlsplit(site).netloc
    urls = [u for u, lm in new.items() if old.get(u) != lm] + [u for u in old if u not in new]
    return [u for u in urls if urllib.parse.urlsplit(u).netloc == host][:LIMIT]


def body(urls, site=SITE):
    host = urllib.parse.urlsplit(site).netloc
    return {"host": host, "key": INDEXNOW_KEY, "keyLocation": f"{site.rstrip('/')}/{INDEXNOW_KEY}.txt", "urlList": urls}


def main(live_url, new_path, out):
    try:
        with open(new_path, "rb") as fh: new = parse(fh.read())
    except Exception as e:
        print(f"::warning::indexnow: no new sitemap ({type(e).__name__}); nothing submitted"); return
    try:
        req = urllib.request.Request(live_url, headers={"User-Agent": "bowser-indexnow"})
        with urllib.request.urlopen(req, timeout=30) as r: old = parse(r.read())
    except Exception as e:
        # The first deploy, or the live site unreachable: submit nothing rather than every page; the next run catches up
        print(f"::warning::indexnow: live sitemap unreadable ({type(e).__name__}); nothing submitted"); return
    urls = changed(old, new)
    print(f"indexnow: {len(urls)} of {len(new)} pages changed since the live sitemap")
    if urls:
        with open(out, "w", encoding="utf-8") as fh: json.dump(body(urls), fh)


if __name__ == "__main__":
    if len(sys.argv) != 4: sys.exit(__doc__)
    main(*sys.argv[1:])
