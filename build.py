from __future__ import annotations

import gzip
import html
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "docs" / "blog" / "posts"
OUT_DIR = ROOT / "site"
SITE_URL = "https://devhiker.xyz"
SITE_TITLE = "Pingzhi HU"
SITE_DESCRIPTION = "一个 Java 程序员的个人博客"


@dataclass
class Post:
    title: str
    date: date
    slug: str
    categories: list[str]
    source_path: Path
    body: str
    excerpt: str
    html: str = ""

    @property
    def url(self) -> str:
        return f"/blog/{self.slug}/"


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text

    _, raw_meta, body = text.split("---", 2)
    meta: dict[str, object] = {}
    current_key: str | None = None

    for line in raw_meta.strip().splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            meta.setdefault(current_key, [])
            assert isinstance(meta[current_key], list)
            meta[current_key].append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if not value:
            meta[key] = []
        elif value.startswith("[") and value.endswith("]"):
            meta[key] = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        elif value.lower() in {"true", "false"}:
            meta[key] = value.lower() == "true"
        else:
            meta[key] = value.strip("\"'")

    return meta, body.lstrip()


def plain_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`|~-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def excerpt_from(body: str) -> str:
    marker = "<!-- more -->"
    if marker in body:
        return plain_text(body.split(marker, 1)[0])
    return plain_text(body)[:220]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "", value)
    return value or quote(value)


def category_links(categories: list[str]) -> str:
    return " ".join(
        f'<a href="/category/{quote(slugify(category))}/">{html.escape(category)}</a>'
        for category in categories
    )


def post_meta(post: Post) -> str:
    cats = category_links(post.categories)
    date_text = post.date.isoformat()
    return f'<time datetime="{date_text}">{date_text}</time>{" \u00b7 " + cats if cats else ""}'


def inline_markup(text: str, link_map: dict[str, str]) -> str:
    placeholders: list[str] = []

    def stash(value: str) -> str:
        placeholders.append(value)
        return f"\u0000{len(placeholders) - 1}\u0000"

    text = html.escape(text, quote=False)

    text = re.sub(
        r"`([^`]+)`",
        lambda m: stash(f"<code>{m.group(1)}</code>"),
        text,
    )

    def image_repl(match: re.Match[str]) -> str:
        alt = html.escape(match.group(1), quote=True)
        src = rewrite_link(match.group(2), link_map)
        return stash(f'<img src="{html.escape(src, quote=True)}" alt="{alt}">')

    def link_repl(match: re.Match[str]) -> str:
        label = match.group(1)
        href = rewrite_link(match.group(2), link_map)
        return stash(f'<a href="{html.escape(href, quote=True)}">{label}</a>')

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_repl, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

    for index, value in enumerate(placeholders):
        text = text.replace(f"\u0000{index}\u0000", value)
    return text


def rewrite_link(href: str, link_map: dict[str, str]) -> str:
    if href.startswith(("http://", "https://", "mailto:", "#", "/")):
        return href
    filename = href.split("#", 1)[0].split("/")[-1]
    anchor = "#" + href.split("#", 1)[1] if "#" in href else ""
    if filename in link_map:
        return link_map[filename] + anchor
    return href


def render_markdown(markdown: str, link_map: dict[str, str], title: str) -> str:
    markdown = markdown.replace("<!-- more -->", "")
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{inline_markup(' '.join(paragraph), link_map)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                out.append(
                    f'<pre><code class="language-{html.escape(code_lang)}">'
                    + html.escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                in_code = False
                code_lang = ""
                code_lines = []
            else:
                flush_paragraph()
                close_list()
                in_code = True
                code_lang = stripped[3:].strip()
            index += 1
            continue

        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        if stripped == "<!-- more -->":
            index += 1
            continue

        if re.match(r"^\|.*\|$", stripped) and index + 1 < len(lines) and re.match(
            r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", lines[index + 1].strip()
        ):
            flush_paragraph()
            close_list()
            headers = [cell.strip() for cell in stripped.strip("|").split("|")]
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and re.match(r"^\|.*\|$", lines[index].strip()):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            out.append("<table><thead><tr>")
            out.extend(f"<th>{inline_markup(cell, link_map)}</th>" for cell in headers)
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                out.extend(f"<td>{inline_markup(cell, link_map)}</td>" for cell in row)
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            close_list()
            out.append("<hr>")
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1 and plain_text(text) == title:
                index += 1
                continue
            out.append(f"<h{level}>{inline_markup(text, link_map)}</h{level}>")
            index += 1
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            close_list()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith("> "):
                quote_lines.append(lines[index].strip()[2:])
                index += 1
            out.append(f"<blockquote><p>{inline_markup(' '.join(quote_lines), link_map)}</p></blockquote>")
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if bullet or ordered:
            flush_paragraph()
            wanted = "ul" if bullet else "ol"
            if list_type != wanted:
                close_list()
                out.append(f"<{wanted}>")
                list_type = wanted
            item = bullet.group(1) if bullet else ordered.group(1)
            out.append(f"<li>{inline_markup(item, link_map)}</li>")
            index += 1
            continue

        close_list()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    return "\n".join(out)


def read_posts() -> list[Post]:
    posts: list[Post] = []
    for path in POSTS_DIR.glob("*.md"):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        if meta.get("draft") is True:
            continue
        raw_date = str(meta.get("date", "1970-01-01"))
        post_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        categories = meta.get("categories", [])
        posts.append(
            Post(
                title=str(meta.get("title", path.stem)),
                date=post_date,
                slug=str(meta.get("slug", path.stem)),
                categories=[str(category) for category in categories] if isinstance(categories, list) else [],
                source_path=path,
                body=body,
                excerpt=excerpt_from(body),
            )
        )
    posts.sort(key=lambda post: post.date, reverse=True)
    return posts


def page(title: str, body: str, description: str = SITE_DESCRIPTION, path: str = "/", page_class: str = "") -> str:
    full_title = SITE_TITLE if title == SITE_TITLE else f"{title} - {SITE_TITLE}"
    main_class = "page" if not page_class else f"page {page_class}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(description, quote=True)}">
  <title>{html.escape(full_title)}</title>
  <link rel="canonical" href="{SITE_URL}{path}">
  <link rel="alternate" type="application/rss+xml" title="{SITE_TITLE}" href="/rss.xml">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <main class="{main_class}">
    <header class="site-header">
      <h1><a href="/">{html.escape(SITE_TITLE)}</a></h1>
      <nav class="site-nav" aria-label="Primary navigation">
        <a href="/archive/">Archive</a>
        <a href="/rss.xml">RSS</a>
        <a href="mailto:kangyinghuu@gmail.com">Email</a>
      </nav>
    </header>
{body}
    <footer class="site-footer">
      <a href="/">Home</a>
      <a href="/archive/">Archive</a>
      <a href="/rss.xml">RSS</a>
    </footer>
  </main>
</body>
</html>
"""


def post_summary(post: Post) -> str:
    return f"""<article class="post-summary">
  <h2><a href="{post.url}">{html.escape(post.title)}</a></h2>
  <div class="meta">{post_meta(post)}</div>
  <p>{html.escape(post.excerpt)}</p>
</article>"""


def post_full(post: Post) -> str:
    return f"""<article class="post-summary post-summary--full">
  <h2><a href="{post.url}">{html.escape(post.title)}</a></h2>
  <div class="meta">{post_meta(post)}</div>
  <div class="post-body">
{post.html}
  </div>
</article>"""


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="\n")


def render_home(posts: list[Post]) -> str:
    intro = """<section class="intro">
  <p>这里记录技术学习、踩坑、读书和独立开发的一些想法。</p>
</section>"""
    recent_posts = posts[:5]
    return page(SITE_TITLE, intro + "\n" + "\n".join(post_full(post) for post in recent_posts), SITE_DESCRIPTION, "/", "home-page")


def render_post(post: Post) -> str:
    body = f"""<article class="post">
  <header class="post-header">
    <h1>{html.escape(post.title)}</h1>
    <div class="meta">{post_meta(post)}</div>
  </header>
  <div class="post-body">
{post.html}
  </div>
</article>"""
    return page(post.title, body, post.excerpt, post.url)


def render_archive(posts: list[Post]) -> str:
    grouped: dict[str, list[Post]] = {}
    for post in posts:
        month = post.date.strftime("%Y-%m")
        grouped.setdefault(month, []).append(post)

    months = sorted(grouped, reverse=True)
    nav_items = []
    content_items = []
    for index, month in enumerate(months):
        month_posts = grouped[month]
        month_id = f"archive-{month}"
        active_class = " active" if index == 0 else ""
        nav_items.append(
            f'<a class="archive-month-link{active_class}" href="#{month_id}" data-target="{month_id}">'
            f'<span>{month}</span><span class="archive-count">{len(month_posts)}</span></a>'
        )
        list_items = "\n".join(
            f'<li><time datetime="{post.date.isoformat()}">{post.date.isoformat()}</time>'
            f'<a href="{post.url}">{html.escape(post.title)}</a></li>'
            for post in month_posts
        )
        content_items.append(f"""<section class="archive-month-group" id="{month_id}">
  <h2>{month}</h2>
  <ol class="archive-list">
{list_items}
  </ol>
</section>""")

    nav_html = "\n      ".join(nav_items)
    content_html = "\n".join(content_items)
    archive_script = """<script>
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('.archive-month-link'));
  var groups = Array.prototype.slice.call(document.querySelectorAll('.archive-month-group'));
  if (!links.length || !groups.length || !('IntersectionObserver' in window)) return;

  function setActive(id) {
    links.forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('data-target') === id);
    });
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) setActive(entry.target.id);
    });
  }, { rootMargin: '-25% 0px -60% 0px', threshold: 0 });

  groups.forEach(function (group) { observer.observe(group); });
}());
</script>"""

    body = f"""<section class="archive archive-linked">
  <h1>Archive</h1>
  <div class="archive-layout">
    <nav class="archive-months" aria-label="Archive months">
      {nav_html}
    </nav>
    <div class="archive-groups">
{content_html}
    </div>
  </div>
</section>
{archive_script}"""
    return page("Archive", body, SITE_DESCRIPTION, "/archive/", "archive-page")


def render_category(name: str, posts: list[Post], path: str) -> str:
    body = f'<section class="archive post-list"><h1>{html.escape(name)}</h1>\n'
    body += "\n".join(post_summary(post) for post in posts)
    body += "\n</section>"
    return page(name, body, SITE_DESCRIPTION, path)


def render_rss(posts: list[Post]) -> str:
    items = []
    for post in posts[:20]:
        dt = datetime.combine(post.date, datetime.min.time()).astimezone()
        items.append(f"""<item>
  <title>{html.escape(post.title)}</title>
  <link>{SITE_URL}{post.url}</link>
  <guid>{SITE_URL}{post.url}</guid>
  <pubDate>{format_datetime(dt)}</pubDate>
  <description>{html.escape(post.excerpt)}</description>
</item>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
<channel>
  <title>{SITE_TITLE}</title>
  <link>{SITE_URL}</link>
  <description>{SITE_DESCRIPTION}</description>
{''.join(items)}
</channel>
</rss>
"""


def render_sitemap(urls: list[str]) -> str:
    body = "\n".join(f"  <url><loc>{SITE_URL}{url}</loc></url>" for url in urls)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""


def main() -> None:
    posts = read_posts()
    link_map = {post.source_path.name: post.url for post in posts}
    for post in posts:
        post.html = render_markdown(post.body, link_map, post.title)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()
    write(OUT_DIR / "style.css", (ROOT / "src" / "style.css").read_text(encoding="utf-8"))
    write(OUT_DIR / ".nojekyll", "")
    if (ROOT / "docs" / "CNAME").exists():
        write(OUT_DIR / "CNAME", (ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip() + "\n")

    write(OUT_DIR / "index.html", render_home(posts))
    write(OUT_DIR / "blog" / "index.html", render_home(posts))
    write(OUT_DIR / "archive" / "index.html", render_archive(posts))

    urls = ["/", "/blog/", "/archive/"]
    years = sorted({post.date.year for post in posts}, reverse=True)
    for year in years:
        year_posts = [post for post in posts if post.date.year == year]
        write(OUT_DIR / "archive" / str(year) / "index.html", render_category(str(year), year_posts, f"/archive/{year}/"))
        urls.append(f"/archive/{year}/")

    categories = sorted({category for post in posts for category in post.categories})
    for category in categories:
        category_posts = [post for post in posts if category in post.categories]
        category_slug = slugify(category)
        write(OUT_DIR / "category" / category_slug / "index.html", render_category(category, category_posts, f"/category/{quote(category_slug)}/"))
        urls.append(f"/category/{quote(category_slug)}/")

    for post in posts:
        write(OUT_DIR / "blog" / post.slug / "index.html", render_post(post))
        urls.append(post.url)

    not_found = page("Not Found", '<article class="post"><h1>Not Found</h1><p><a href="/">Back home</a></p></article>')
    write(OUT_DIR / "404.html", not_found)
    write(OUT_DIR / "rss.xml", render_rss(posts))
    sitemap = render_sitemap(urls)
    write(OUT_DIR / "sitemap.xml", sitemap)
    write(OUT_DIR / "sitemap.xml.gz", gzip.compress(sitemap.encode("utf-8")))

    assets_src = ROOT / "docs" / "assets"
    assets_out = OUT_DIR / "assets"
    if assets_src.exists():
        if assets_out.exists():
            shutil.rmtree(assets_out)
        shutil.copytree(assets_src, assets_out)

    print(f"Built {len(posts)} posts into {OUT_DIR}")


if __name__ == "__main__":
    main()
