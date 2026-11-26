"""IndexNow: list the pages that changed since the live site, for the deploy job to submit once they are live.

  python indexnow.py LIVE_SITEMAP_URL NEW_SITEMAP_PATH OUT_JSON

Compares the sitemap about to be published with the one live now. Either may be a sitemap index (seo_pages.py writes
one per page group): its child sitemaps are read from the live site, or from beside the new file. A page is submitted when it is new, gone, or its
<lastmod> moved; Sydney pages move once a day (the day's call), pages outside Sydney when their prices do, so the
five runs a day submit each page at most once a day. Writes OUT_JSON (the POST body for api.indexnow.org) only when
something changed. Never fails the build: any problem prints a warning and writes nothing. Standard library only.
The key is seo_pages.INDEXNOW_KEY, served at /{key}.txt (docs/SEO.md).
"""
import json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_pages import INDEXNOW_KEY, SITE

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
LIMIT = 10_000                                     # IndexNow's most URLs in one request


def parse(xml_bytes):
    """{loc: lastmod} from a sitemap."""
    root = ET.fromstring(xml_bytes)
    return {u.findtext("s:loc", "", NS).strip(): u.findtext("s:lastmod", "", NS).strip() for u in root.findall("s:url", NS)}


def read(src):
    if re.match(r"https?://", src):
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "bowser-indexnow"}), timeout=30) as r: return r.read()
    with open(src, "rb") as fh: return fh.read()


def load(src):
    """{loc: lastmod} from a sitemap or a sitemap index (URL or local path). A local index's children are the files
    of the same name beside it; a live one's are fetched. Any child that can't be read raises: better nothing than half."""
    data = read(src)
    root = ET.fromstring(data)
    if not root.tag.endswith("sitemapindex"): return parse(data)
    out = {}
    for loc in (s.findtext("s:loc", "", NS).strip() for s in root.findall("s:sitemap", NS)):
        child = loc if re.match(r"https?://", src) else os.path.join(os.path.dirname(src), os.path.basename(urllib.parse.urlsplit(loc).path))
        out.update(parse(read(child)))
    return out


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
        new = load(new_path)
    except Exception as e:
        print(f"::warning::indexnow: no new sitemap ({type(e).__name__}); nothing submitted"); return
    try:
        old = load(live_url)
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
