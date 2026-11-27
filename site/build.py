#!/usr/bin/env python3
"""把仓库里已经公开的 Markdown 生成成一页网站：index.html（仓库根目录）。

内容的唯一来源是 README.md、docs/design-outline.md、posts/*.md、CHANGELOG.md。
网站只是它们的另一种排版，改内容就改这些 Markdown，然后重新跑：

    python3 site/build.py

只用标准库。外观在 site/template.html 里，沿用 Jspace 的暗色编辑部风。
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/kairos1007/human-simulator"
BLOB = REPO_URL + "/blob/main/"


# ---------- 极简 Markdown ----------

def inline(text, base=""):
    """转义后处理 **粗体**、`代码`、[链接](地址)。相对链接改成 GitHub 上的地址。"""
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

    def link(m):
        label, href = m.group(1), m.group(2)
        if not re.match(r"^(https?:|mailto:|#)", href):
            href = BLOB + str((Path(base) / href)).replace("\\", "/")
            href = re.sub(r"[^/]+/\.\./", "", href)
        return f'<a href="{html.escape(href)}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)


def blocks(md):
    """按空行切块。"""
    out, cur = [], []
    for line in md.strip("\n").split("\n"):
        if line.strip():
            cur.append(line.rstrip())
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def table_rows(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    return [r for r in rows if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]


def render(md, base=""):
    """块级渲染：标题、列表、表格、段落（段内换行保留成 <br>）。"""
    parts = []
    for b in blocks(md):
        first = b[0]
        if first.startswith("#"):
            level = len(first) - len(first.lstrip("#"))
            parts.append(f"<h{level + 1}>{inline(first.lstrip('# '), base)}</h{level + 1}>")
        elif all(l.lstrip().startswith(("- ", "* ")) for l in b):
            items = "".join(f"<li>{inline(l.lstrip()[2:], base)}</li>" for l in b)
            parts.append(f"<ul>{items}</ul>")
        elif all(re.match(r"\s*\d+\.\s", l) for l in b):
            texts = [re.sub(r"^\s*\d+\.\s", "", l) for l in b]
            items = "".join(f"<li>{inline(t, base)}</li>" for t in texts)
            parts.append(f"<ol>{items}</ol>")
        elif first.startswith("|"):
            rows = table_rows(b)
            head = "".join(f"<th>{inline(c, base)}</th>" for c in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>" for r in rows[1:])
            parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
        else:
            parts.append("<p>" + "<br>".join(inline(l, base) for l in b) + "</p>")
    return "\n".join(parts)


def sections(md):
    """按二级标题切：{标题: 正文}，标题前的部分记在 '' 下。"""
    out, name, cur = {}, "", []
    for line in md.split("\n"):
        if line.startswith("## "):
            out[name] = "\n".join(cur)
            name, cur = line[3:].strip(), []
        else:
            cur.append(line)
    out[name] = "\n".join(cur)
    return out


def strip_md(s):
    return re.sub(r"\*\*|`", "", s)


# ---------- 各部分 ----------

def hero():
    readme = sections((ROOT / "README.md").read_text(encoding="utf-8"))
    bs = blocks(readme[""])
    title = bs[0][0].lstrip("# ").strip()
    tagline = " ".join(bs[1])
    intro = "\n\n".join("\n".join(b) for b in bs[2:])
    return title, tagline, render(intro), readme


def stages(readme):
    sec = readme.get("现在在哪一步", "")
    bs = blocks(sec)
    lead = render("\n\n".join("\n".join(b) for b in bs if not b[0].startswith("|")))
    rows = table_rows(next(b for b in bs if b[0].startswith("|")))[1:]
    items = []
    for i, (name, what) in enumerate(rows, 1):
        now = "←" in name
        name = strip_md(name.replace("← 现在", "").replace("←", "")).strip()
        num, _, label = name.partition("、")
        items.append(
            f'<li class="stage{" now" if now else ""}">'
            f'<span class="stage-num">{html.escape(num)}</span>'
            f'<div><h3>{html.escape(label or name)}{"<em>现在</em>" if now else ""}</h3>'
            f"<p>{inline(what)}</p></div></li>"
        )
    return lead, "\n".join(items)


def layers(readme):
    sec = readme.get("白皮书的层", "")
    rows = table_rows(next(b for b in blocks(sec) if b[0].startswith("|")))[1:]
    n = len(rows)
    out = []
    # README 从底色写起；页面从表面往下沉，所以倒过来排，越往下颜色越深
    for i, (name, what) in enumerate(reversed(rows)):
        depth = round(0.04 + 0.5 * i / max(n - 1, 1), 3)
        out.append(
            f'<li style="--depth:{depth}"><span class="layer-idx">{n - i:02d}</span>'
            f'<span class="layer-name">{html.escape(strip_md(name))}</span>'
            f'<span class="layer-what">{inline(what)}</span></li>'
        )
    return "\n".join(out)


def principles():
    outline = sections((ROOT / "docs/design-outline.md").read_text(encoding="utf-8"))
    items = []
    for line in outline.get("原则", "").split("\n"):
        m = re.match(r"\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)", line)
        if m:
            items.append(
                f'<li><span class="p-num">{int(m.group(1)):02d}</span>'
                f"<div><h3>{inline(m.group(2))}</h3><p>{inline(m.group(3), 'docs')}</p></div></li>"
            )
    return "\n".join(items)


def posts():
    out = []
    for f in sorted((ROOT / "posts").glob("*.md"), reverse=True):
        bs = blocks(f.read_text(encoding="utf-8"))
        title = bs[0][0].lstrip("# ").strip()
        date = " ".join(bs[1]) if len(bs) > 1 else ""
        body = "\n\n".join("\n".join(b) for b in bs[2:])
        rel = f.relative_to(ROOT).as_posix()
        first = blocks(body)[0] if body else []
        excerpt = inline(first[0]) if first else ""
        out.append(
            f'<article class="post"><details>'
            f'<summary><span class="post-date">{html.escape(date)}</span>'
            f"<h3>{inline(title)}</h3><p class=\"post-excerpt\">{excerpt}</p>"
            f'<span class="post-more">展开全文</span></summary>'
            f'<div class="post-body">{render(body, "posts")}'
            f'<p class="post-src"><a href="{BLOB}{rel}">在 GitHub 上看原文</a></p></div>'
            f"</details></article>"
        )
    return "\n".join(out)


def changelog():
    secs = sections((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    out = []
    for name, body in secs.items():
        if not name:
            continue
        out.append(f'<li><time>{html.escape(name)}</time>{render(body)}</li>')
    return "\n".join(out)


def main():
    title, tagline, intro, readme = hero()
    stage_lead, stage_items = stages(readme)
    page = (ROOT / "site/template.html").read_text(encoding="utf-8")
    zh, _, en = title.partition(" ")
    fills = {
        "TITLE": html.escape(title),
        "TITLE_ZH": html.escape(zh),
        "TITLE_EN": html.escape(en or title),
        "TAGLINE": inline(tagline),
        "INTRO": intro,
        "STAGE_LEAD": stage_lead,
        "STAGES": stage_items,
        "LAYERS": layers(readme),
        "PRINCIPLES": principles(),
        "POSTS": posts(),
        "CHANGELOG": changelog(),
        "REPO": REPO_URL,
        "WHITEPAPER": BLOB + "docs/whitepaper/README.md",
        "OUTLINE": BLOB + "docs/design-outline.md",
    }
    for k, v in fills.items():
        page = page.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        raise SystemExit(f"模板里还有没填的占位符：{left}")
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print("已生成 index.html")


if __name__ == "__main__":
    main()
