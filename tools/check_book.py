#!/usr/bin/env python3
"""静态检查: 链接、图片、章节结构与字数和 manuscript.json 对齐。"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "notes" / "manuscript.json").read_text(encoding="utf-8"))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.imgs = []
        self.ids = set()
        self.h1 = 0
        self._div_stack = []
        self.card_nesting = 0
        self.cards = 0
        self.cards_no_p = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        if tag == "img" and d.get("src"):
            self.imgs.append(d["src"])
        if d.get("id"):
            self.ids.add(d["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "div":
            is_card = "species-card" in (d.get("class") or "")
            if is_card:
                if "card" in self._div_stack:
                    self.card_nesting += 1
                self.cards += 1
                self._div_stack.append("card")
                self._card_p = 0
            else:
                self._div_stack.append("div")
        if tag == "p" and "card" in getattr(self, "_div_stack", []):
            self._card_p = getattr(self, "_card_p", 0) + 1

    def handle_endtag(self, tag):
        if tag == "div" and self._div_stack:
            top = self._div_stack.pop()
            if top == "card" and getattr(self, "_card_p", 0) == 0:
                self.cards_no_p += 1


def main():
    errors = []

    pages = [ROOT / "index.html", ROOT / "glossary.html"]
    pages += [ROOT / f"chapter-{i:02d}.html" for i in range(0, 62)]
    for p in pages:
        if not p.exists():
            errors.append(f"缺页面 {p.name}")

    id_cache = {}
    for p in pages:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        lp = Links()
        lp.feed(text)
        id_cache[p.name] = lp.ids
        if lp.h1 != 1:
            errors.append(f"{p.name}: h1 数量 = {lp.h1}")
        if lp.card_nesting:
            errors.append(f"{p.name}: 物种卡片嵌套 {lp.card_nesting} 处")
        if lp.cards_no_p:
            errors.append(f"{p.name}: {lp.cards_no_p} 张物种卡片无正文")
        for href in lp.hrefs:
            if href.startswith(("http", "mailto:", "#")):
                continue
            file, _, anchor = href.partition("#")
            target = (ROOT / file)
            if file and not target.exists():
                errors.append(f"{p.name}: 链接不存在 {href}")
            elif anchor and anchor not in id_cache.get(file, set()) and \
                    not (target.exists() and f'id="{anchor}"' in target.read_text(encoding="utf-8")):
                errors.append(f"{p.name}: 锚点不存在 {href}")
        for src in lp.imgs:
            if not (ROOT / src).exists():
                errors.append(f"{p.name}: 缺图片 {src}")

    # 章页字数与手稿一致性抽查: 每章 H1 标题与来源小节
    for ch in M["chapters"]:
        text = (ROOT / f"chapter-{ch['num']:02d}.html").read_text(encoding="utf-8")
        if ch["title"] not in text:
            errors.append(f"chapter-{ch['num']:02d}: 缺标题 {ch['title']}")
        plate = f"assets/plates/chapter-{ch['num']:02d}.jpg"
        if plate not in text:
            errors.append(f"chapter-{ch['num']:02d}: 缺彩图引用")
        body_chars = sum(len(b.get("text", "")) for b in ch["blocks"] if b["type"] in ("p", "h2", "h3"))
        plain = re.sub(r"<[^>]+>", "", text)
        got = sum(1 for _ in re.finditer(r"[一-鿿]", plain))
        if got < body_chars * 0.6:
            errors.append(f"chapter-{ch['num']:02d}: 正文汉字 {got} 远少于手稿 {body_chars}")
        for b in ch["blocks"]:
            if b["type"] == "figure" and b.get("src") and not (ROOT / b["src"]).exists():
                errors.append(f"chapter-{ch['num']:02d}: 缺内嵌图 {b['src']}")

    # book.js 数据块
    js = (ROOT / "assets" / "book.js").read_text(encoding="utf-8")
    files = re.findall(r"file: '(chapter-\d+\.html)'", js)
    if len(files) != 62:
        errors.append(f"book.js CHAPTERS 数量 {len(files)} != 62")
    for f in files:
        if not (ROOT / f).exists():
            errors.append(f"book.js 指向不存在文件 {f}")
    if "BAD" in js:
        errors.append("book.js 替换残留")

    # 统计
    total_chars = sum(len(b.get("text", "")) for ch in M["chapters"]
                      for b in ch["blocks"] if b["type"] in ("p", "h2", "h3"))
    n_fig = sum(1 for ch in M["chapters"] for b in ch["blocks"] if b["type"] == "figure")
    print(f"章节 60 · 正文字符 {total_chars} · 内嵌图 {n_fig} · 彩图 60 · "
          f"术语 {len(M['glossary'])} · 物种 {len(M['species_index'])} · 文献 {len(M['references'])}")

    if errors:
        print("检查发现 %d 个问题:" % len(errors))
        for e in errors[:50]:
            print("  -", e)
        sys.exit(1)
    print("全部检查通过")


if __name__ == "__main__":
    main()
