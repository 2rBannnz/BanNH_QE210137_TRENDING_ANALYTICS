"""Dựng PDF báo cáo từ Markdown trong reports/ (không cần cài thêm thư viện).

Markdown -> HTML bằng bộ chuyển đổi nhỏ bên dưới (đủ cho tiêu đề, đoạn, danh sách, bảng, code, ảnh,
trích dẫn, HTML thô) -> PDF bằng Microsoft Edge chạy ẩn (--print-to-pdf), khổ A4 theo reports/style.css.

Chạy từ thư mục gốc repo:
    python -m src.utils.build_reports                      # mọi reports/Report_*.md
    python -m src.utils.build_reports reports/Report_1_Proposal.md
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from src.utils.config import Config

REPORTS = Config.REPO_ROOT / "reports"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


# ---------------------------------------------------------------- inline
def inline(s: str) -> str:
    """Escape HTML rồi dựng lại các ký hiệu inline của Markdown."""
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = s.replace("&lt;br&gt;", "<br>")
    return s


def slug(s: str) -> str:
    s = re.sub(r"<.*?>", "", s)
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.U)
    return re.sub(r"[\s_]+", "-", s).strip("-")[:60] or "muc"


# ---------------------------------------------------------------- block
def md_to_html(md: str):
    """Trả về (thân HTML, mục lục HTML). Đánh số h2/h3 tự động."""
    lines = md.replace("\r\n", "\n").split("\n")
    out, toc = [], []
    i, n = 0, len(lines)
    so2 = so3 = 0
    para = []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(x.strip() for x in para)) + "</p>")
            para.clear()

    while i < n:
        line = lines[i]
        bare = line.strip()
        # -- khối rỗng
        if not bare:
            flush(); i += 1; continue
        # -- code fence
        if bare.startswith("```"):
            flush(); i += 1; buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf), quote=False) + "</code></pre>")
            continue
        # -- HTML thô: khối bắt đầu bằng '<' tới dòng trống
        if bare.startswith("<") and not bare.startswith("<br"):
            flush(); buf = []
            while i < n and lines[i].strip():
                buf.append(lines[i]); i += 1
            out.append("\n".join(buf)); continue
        # -- tiêu đề
        m = re.match(r"^(#{1,4})\s+(.*)$", bare)
        if m:
            flush()
            level, text = len(m.group(1)), m.group(2).strip()
            text_html = inline(text)
            if level == 2:
                so2 += 1; so3 = 0; num = f"{so2}."
                text_html = f"{num} {text_html}"
                toc.append((2, slug(text), text_html))
            elif level == 3:
                so3 += 1; num = f"{so2}.{so3}."
                text_html = f"{num} {text_html}"
                toc.append((3, slug(text), text_html))
            out.append(f'<h{level} id="{slug(text)}">{text_html}</h{level}>')
            i += 1; continue
        # -- hr
        if re.match(r"^-{3,}$", bare):
            flush(); out.append("<hr>"); i += 1; continue
        # -- bảng
        if bare.startswith("|") and i + 1 < n and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush()
            header = [c.strip() for c in bare.strip("|").split("|")]
            align = []
            for c in lines[i + 1].strip().strip("|").split("|"):
                c = c.strip()
                align.append("center" if c.startswith(":") and c.endswith(":") else "right" if c.endswith(":") else "left")
            i += 2; rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            def td(tag, cells):
                return "".join(f'<{tag} style="text-align:{align[k] if k < len(align) else "left"}">{inline(c)}</{tag}>'
                               for k, c in enumerate(cells))
            out.append("<table><thead><tr>" + td("th", header) + "</tr></thead><tbody>" +
                       "".join("<tr>" + td("td", r) + "</tr>" for r in rows) + "</tbody></table>")
            continue
        # -- trích dẫn
        if bare.startswith(">"):
            flush(); buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip()); i += 1
            paras, cur = [], []
            for b in buf + [""]:
                if b: cur.append(b)
                elif cur: paras.append("<p>" + inline(" ".join(cur)) + "</p>"); cur = []
            out.append("<blockquote>" + "".join(paras) + "</blockquote>"); continue
        # -- danh sách (2 cấp, thụt 2+ khoảng trắng)
        if re.match(r"^(\s*)([-*]|\d+\.)\s+", line):
            flush(); items = []
            while i < n and re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                items.append((len(m.group(1)), m.group(2), m.group(3))); i += 1
                # dòng nối tiếp của cùng item (thụt vào, không phải item mới)
                while i < n and lines[i].strip() and not re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]) \
                        and lines[i].startswith(" " * (len(m.group(1)) + 2)):
                    items[-1] = (items[-1][0], items[-1][1], items[-1][2] + " " + lines[i].strip()); i += 1
            html_list, stack = [], []   # stack: (indent, tag)
            for ind, mark, text in items:
                tag = "ol" if mark[0].isdigit() else "ul"
                while stack and ind < stack[-1][0]:
                    html_list.append(f"</li></{stack.pop()[1]}>")
                if not stack or ind > stack[-1][0]:
                    if stack: html_list[-1] = html_list[-1]  # đang mở li cha
                    html_list.append(f"<{tag}>"); stack.append((ind, tag))
                else:
                    html_list.append("</li>")
                html_list.append("<li>" + inline(text))
            while stack:
                html_list.append(f"</li></{stack.pop()[1]}>")
            out.append("".join(html_list)); continue
        # -- ảnh đứng riêng -> figure
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", bare)
        if m:
            flush()
            out.append(f'<figure><img src="{m.group(2)}" alt="{html.escape(m.group(1))}">'
                       f"<figcaption>{inline(m.group(1))}</figcaption></figure>")
            i += 1; continue
        # -- đoạn văn
        para.append(line); i += 1
    flush()

    toc_html = ['<nav id="TOC"><h2 style="border:none">Mục lục</h2><ul>']
    open3 = False
    for level, sid, text in toc:
        if level == 2:
            if open3: toc_html.append("</ul></li>"); open3 = False
            toc_html.append(f'<li><a href="#{sid}">{text}</a>')
        else:
            if not open3: toc_html.append("<ul>"); open3 = True
            toc_html.append(f'<li><a href="#{sid}">{text}</a></li>')
    if open3: toc_html.append("</ul></li>")
    toc_html.append("</li></ul></nav>")
    # sửa li của mục cấp 2 cuối chưa đóng
    body = "\n".join(out).replace("<li>", "<li>", 1)
    return body, "".join(toc_html).replace("<li><a", "</li><li><a").replace("<ul></li><li><a", "<ul><li><a", 1)


def dung_html(md_path: Path) -> Path:
    md = md_path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.*)$", md, flags=re.M)
    title = html.unescape(re.sub(r"[*`]", "", title.group(1))) if title else md_path.stem
    body, toc = md_to_html(md)
    # chèn mục lục ngay sau khối bìa (dấu <!-- TOC -->), nếu có
    body = body.replace("<!-- TOC -->", toc) if "<!-- TOC -->" in body else toc + body
    doc = (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
           f'<link rel="stylesheet" href="style.css"></head><body>{body}</body></html>')
    out = md_path.with_suffix(".html")
    out.write_text(doc, encoding="utf-8")
    return out


def in_pdf(html_path: Path) -> Path:
    pdf = html_path.with_suffix(".pdf")
    profile = Path(tempfile.gettempdir()) / "edge-pdf-profile"
    cmd = [str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
           "--no-pdf-header-footer", "--virtual-time-budget=8000", f"--print-to-pdf={pdf}", html_path.resolve().as_uri()]
    for _ in range(3):   # Edge headless thỉnh thoảng thoát mà chưa ghi file; thử lại là được
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        if pdf.exists():
            return pdf
    raise RuntimeError(f"Edge không tạo được {pdf}")


def main(args):
    files = [Path(a) for a in args] or sorted(REPORTS.glob("Report_*.md"))
    for md in files:
        h = dung_html(md)
        pdf = in_pdf(h)
        h.unlink()
        print(f"{pdf.relative_to(Config.REPO_ROOT)}  {pdf.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
