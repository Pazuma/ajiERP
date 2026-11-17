"""Build a self-contained, printable HTML handbook from the adjacent manuals."""

from html import escape
from pathlib import Path
import base64
import re


ROOT = Path(__file__).resolve().parent
SOURCES = [ROOT / "README.md", *sorted(ROOT.glob("[0-9][0-9]-*.md"))]


def slug(text):
    return re.sub(r"[^\w\-]", "", text.lower().replace(" ", "-"))


def target(href):
    name, _, fragment = href.partition("#")
    path = ROOT / name
    if path in SOURCES:
        anchor = path.stem
        if fragment:
            anchor += "--" + fragment
        return "#" + anchor
    return href


def inline(text):
    # Escape source text before inserting the small supported Markdown subset.
    text = escape(text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: '<a href="' + escape(target(m[2]), quote=True) + '">' + m[1] + "</a>",
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def render(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    output = []
    headings = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            output.append('<pre class="flow">' + escape("\n".join(block)) + "</pre>")
        elif match := re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line):
            asset = (ROOT / match[2]).resolve()
            asset.relative_to(ROOT)
            encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
            output.append('<figure><img src="data:image/png;base64,' + encoded + '" alt="' + escape(match[1], quote=True) + '"><figcaption>' + escape(match[1]) + '</figcaption></figure>')
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            output.append('<div class="table-wrap"><table>')
            for row_index, row in enumerate(rows):
                tag = "th" if row_index == 0 else "td"
                if row_index == 0:
                    output.append("<thead>")
                elif row_index == 1:
                    output.append("<tbody>")
                output.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in row) + "</tr>")
                if row_index == 0:
                    output.append("</thead>")
            if len(rows) > 1:
                output.append("</tbody>")
            output.append("</table></div>")
            continue
        elif match := re.match(r"^(#{1,6}) (.+)$", line):
            level, title = len(match[1]), match[2]
            anchor = path.stem if level == 1 else path.stem + "--" + slug(title)
            occurrence = headings.get(anchor, 0)
            headings[anchor] = occurrence + 1
            if occurrence:
                anchor += f"-{occurrence}"
            output.append(f'<h{level} id="{escape(anchor)}">{inline(title)}</h{level}>')
        elif line.startswith("> "):
            block = []
            while index < len(lines) and lines[index].startswith("> "):
                block.append(inline(lines[index][2:].rstrip()))
                index += 1
            output.append("<blockquote>" + "<br>".join(block) + "</blockquote>")
            continue
        elif re.match(r"^(?:- |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            pattern = r"^\d+\. " if ordered else r"^- "
            tag = "ol" if ordered else "ul"
            output.append(f"<{tag}>")
            while index < len(lines) and re.match(pattern, lines[index]):
                output.append("<li>" + inline(re.sub(pattern, "", lines[index])) + "</li>")
                index += 1
            output.append(f"</{tag}>")
            continue
        else:
            output.append("<p>" + inline(line) + "</p>")
        index += 1
    return "\n".join(output)


def main():
    navigation = "".join(
        f'<a href="#{escape(path.stem)}">{escape(path.read_text(encoding="utf-8").splitlines()[0][2:])}</a>'
        for path in SOURCES
    )
    chapters = "\n".join(f'<article>{render(path)}</article>' for path in SOURCES)
    html = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aki_erp 非技术人员使用手册｜合订版</title>
<style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:#233245;background:#f3f6fa;font:16px/1.85 "Microsoft YaHei","PingFang SC",sans-serif}
nav{position:fixed;inset:0 auto 0 0;width:260px;padding:28px 20px;background:#153c57;color:white;overflow:auto}nav strong{display:block;margin-bottom:22px;font-size:20px}nav a{display:block;color:#e3f2ff;text-decoration:none;padding:10px 0;line-height:1.6}
main{margin-left:260px;padding:32px;max-width:1460px}article{background:white;padding:36px 42px;margin-bottom:28px;border-radius:8px}h1{font-size:29px;color:#153c57;border-bottom:3px solid #288c97;padding-bottom:15px}h2{font-size:23px;color:#17556b;margin-top:36px}h3{font-size:19px;margin-top:28px}h1,h2,h3{scroll-margin-top:20px}
a{color:#116d89}p{margin:12px 0}li{margin:8px 0}.table-wrap{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.7}th,td{border:1px solid #d7e1e8;padding:11px 13px;text-align:left;vertical-align:top}th{background:#eaf3f7;color:#153c57}tr:nth-child(even){background:#fafcfd}thead{display:table-header-group}
blockquote,.flow{background:#f0f6f9;border-left:4px solid #288c97;padding:16px 20px;margin:20px 0}.flow{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.8 "Microsoft YaHei",sans-serif}code{background:#edf2f6;padding:1px 4px}footer{text-align:center;color:#65788a;padding:20px}
figure{margin:24px 0;break-inside:avoid}figure img{display:block;width:100%;height:auto;border:1px solid #d7e1e8;border-radius:6px}figcaption{font-size:14px;color:#65788a;text-align:center;margin-top:8px}
@media(max-width:850px){nav{position:static;width:auto}main{margin:0;padding:12px}article{padding:20px}h1{font-size:25px}}
@media print{@page{size:A4;margin:16mm 12mm}body{background:white;font-size:10.5pt;line-height:1.65}nav{display:none}main{margin:0;padding:0;max-width:none}article{padding:0;margin:0;border-radius:0;break-before:page}article:first-child{break-before:auto}h1{font-size:20pt}h2{font-size:15pt}h3{font-size:12pt}h1,h2,h3{break-after:avoid}table{font-size:9pt}th,td{padding:6px}tr{break-inside:avoid}.table-wrap{overflow:visible}a{color:inherit;text-decoration:none}.flow,blockquote{break-inside:avoid}footer{display:none}}
</style></head><body><nav><strong>aki_erp 使用手册</strong>'''
    html += navigation + '</nav><main>' + chapters
    html += '<footer>版本 1.2 · 2026-11-05 · 浏览器打印可另存为 PDF</footer></main></body></html>'
    output = ROOT / "aki_erp非技术人员使用手册-合订版.html"
    output.write_text(html, encoding="utf-8")
    print(f"Generated {output.name}: {len(SOURCES)} chapters")


if __name__ == "__main__":
    main()
