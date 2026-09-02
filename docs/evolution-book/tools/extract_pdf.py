#!/usr/bin/env python3
"""把《地球生命演化史》PDF 抽取成结构化 manuscript.json + 图片资源。

输出:
  notes/manuscript.json   全书结构(篇 / 章 / 小节 / 段落 / 图 / 物种 / 来源)
  assets/plates/chapter-XX.jpg   每章开篇彩图整页渲染
  assets/figures/fig-X-Y.png     正文内嵌示意图区域截图
"""

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path.home() / "temp" / "地球生命演化史_正式版_全章彩图版.pdf"
OUT_JSON = ROOT / "notes" / "manuscript.json"
PLATE_DIR = ROOT / "assets" / "plates"
FIG_DIR = ROOT / "assets" / "figures"

# 字号分层(见 notes/字体分析):
SIZE_PART_TITLE = 24.0    # 篇扉页大标题(28)/前沿标题(23)
SIZE_H2 = 12.5            # 章内小节标题(13)/前沿小节(14)
SIZE_H3 = 10.4            # 物种条目标题(10.5)
SIZE_INTRO = 11.0         # 章首导读框正文(11.1)
SIZE_BODY = 8.5           # 正文 9.1 / 物种描述 8.9
SIZE_CAPTION = 7.9        # 图注 7.8
# 页眉(7.7)/页脚(8.0)按 y 坐标过滤。
HEADER_Y = 40.0
FOOTER_Y = 790.0
# 段落判断: 同段行间 y 间隙约 2-3.5pt, 跨段约 9.2pt, 小节间 21pt+
PARA_GAP = 6.5

CAPTION_RE = re.compile(r"^图\s*(\d+)-(\d+)\u3000?\s*")
SOURCE_MARK_RE = re.compile(r"^\[R(\d+)\]")


def page_lines(page):
    """把一页的正文抽成行列表: (y0, x0, y1, max_size, text), 去掉页眉页脚。"""
    out = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            text = "".join(s["text"] for s in l["spans"]).strip()
            if not text:
                continue
            size = max(round(s["size"], 1) for s in l["spans"] if s["text"].strip())
            x0, y0, x1, y1 = l["bbox"]
            if y1 < HEADER_Y or y0 > FOOTER_Y:
                continue
            out.append({"y0": y0, "x0": x0, "y1": y1, "size": size, "text": text})
    out.sort(key=lambda r: (round(r["y0"], 1), r["x0"]))
    return out


class BlockBuilder:
    """把行流组装成内容块: heading / para / figure_caption / h3。"""

    def __init__(self):
        self.blocks = []
        self._para = None      # 正在累积的段落
        self._para_y1 = None

    def _flush(self):
        if self._para is not None:
            self.blocks.append({"type": "p", "text": self._para})
            self._para = None
            self._para_y1 = None

    def feed_heading(self, text, level):
        self._flush()
        self.blocks.append({"type": f"h{level}", "text": text})

    def feed_caption(self, text, fig_no, page_idx, clip):
        self._flush()
        self.blocks.append({
            "type": "figure",
            "caption": text,
            "fig": fig_no,
            "page": page_idx + 1,
            "clip": [round(v, 1) for v in clip],
        })

    def feed_line(self, size, text, join_prev=False):
        if self._para is not None and (join_prev or not self._para.rstrip().endswith(
                tuple("。!?;:;!?\"”')))]】"))):
            self._para += text
        else:
            self._flush()
            self._para = text

    def feed_break(self):
        self._flush()

    def done(self):
        self._flush()
        return self.blocks


def parse_chapter_pages(doc, pages, expected_title, h3_titles=None):
    """pages: 0-based 页码列表(不含彩图页)。返回 dict。

    h3_titles: 本章物种条目标题(来自 PDF 书签), 只有命中这些标题的
    10.5pt 行才算 h3; 其余按正文段落处理(正文中存在同字号的强调行)。
    章末 "本章精选来源" 是两栏排版, 正文层提取会把两栏交错打乱,
    因此只登记该小节, 具体文献编号由 pdfminer 另行解析。
    """
    h3_titles = [t.strip() for t in (h3_titles or [])]

    def norm(s):
        return s.replace("\u3000", "").replace(" ", "")

    h3_norms = {norm(t): t for t in h3_titles}
    title = None
    title_buf = ""
    subtitle = None
    bb = BlockBuilder()
    in_sources = False

    expected_norm = norm(expected_title)
    for pidx in pages:
        lines = page_lines(doc[pidx])
        prev_y1 = None
        i = 0
        while i < len(lines):
            ln = lines[i]
            size, text = ln["size"], ln["text"]
            gap = (ln["y0"] - prev_y1) if prev_y1 is not None else None
            prev_y1 = ln["y1"]
            i += 1

            # 章标题(仅章首). 长标题会折行: 逐行拼接直到匹配 TOC 标题
            if size >= 20:
                if title is None:
                    title_buf += text
                    tn = norm(title_buf)
                    if expected_norm.startswith(tn) or tn.startswith(expected_norm):
                        if tn == expected_norm:
                            title = title_buf
                    else:
                        # 兜底: 行内已包含章号核心信息即可
                        m2 = re.match(r"^第(\d+)章", text)
                        if m2:
                            title = title_buf
                    continue
                continue
            # 章首副标题(年代)与 Part 编号(标题下方小字; 长标题会把它挤到更低位置)
            if re.fullmatch(r"Part\s*\d+", text) and not bb.blocks:
                continue
            if title is not None and subtitle is None and not bb.blocks \
                    and ln["y0"] < 200 and size <= 8.5:
                subtitle = text
                continue
            # 图注 -> 图块
            m = CAPTION_RE.match(text)
            if m and size <= SIZE_CAPTION + 0.3:
                fig_no = f"{m.group(1)}-{m.group(2)}"
                # 图区域: 本页该图注上方、上一文本块之下
                clip = (40.0, pending_top(lines, ln), page_width(doc[pidx]) - 40.0, ln["y0"] - 4)
                if clip[3] - clip[1] >= 40:  # 高度足够才算真有图
                    bb.feed_caption(text, fig_no, pidx, clip)
                else:
                    bb.feed_line(size, text)
                continue
            # 小节标题
            if size >= SIZE_H2:
                if "精选来源" in text:
                    in_sources = True
                    continue
                bb.feed_heading(text, 2)
                continue
            if in_sources:
                # 来源小节正文两栏交错, 丢弃, 由 pdfminer 解析
                continue
            if SIZE_H3 - 0.2 <= size < SIZE_H2:
                # 只认 TOC 里登记的物种名; 允许折行拼接
                cand = text
                hit = h3_norms.get(norm(cand))
                while hit is None and i < len(lines) and lines[i]["size"] >= SIZE_H3 - 0.2 \
                        and any(t.startswith(norm(cand)) and t != norm(cand) for t in h3_norms):
                    cand += lines[i]["text"]
                    prev_y1 = lines[i]["y1"]
                    i += 1
                    hit = h3_norms.get(norm(cand))
                if hit is not None:
                    bb.feed_heading(hit, 3)
                    continue
                # 非物种标题的同字号强调行, 按正文处理
            # 正文行: 依据行距/缩进判断是否新段落
            new_para = gap is None or gap > PARA_GAP
            bb.feed_line(size, text, join_prev=not new_para)
        # 页末不强制断段: 由下一页首行 join 规则处理
        bb.feed_break_if_sentence_end()

    blocks = bb.done()
    return {"title_raw": title, "subtitle": subtitle, "blocks": blocks}


def pending_top(lines, caption_line):
    """图注上方最近的文字行底部, 找不到就用页面上部"""
    tops = [l["y1"] for l in lines if l["y1"] < caption_line["y0"] - 30]
    return (max(tops) + 4) if tops else 60.0


def page_width(page):
    return page.rect.width


# BlockBuilder 补丁: 页末处理
def _feed_break_if_sentence_end(self):
    if self._para is not None and self._para.rstrip().endswith(tuple("。!?\"”')))]】")):
        self._flush()


BlockBuilder.feed_break_if_sentence_end = _feed_break_if_sentence_end


def parse_flat_pages(doc, pages):
    """通用解析: 前言/总结等无物种条目的页面。标题 23 -> 忽略, h2=14, 正文逐段。"""
    bb = BlockBuilder()
    title = None
    close_puncts = tuple("。!?\"”')))]】；;")
    for pidx in pages:
        lines = page_lines(doc[pidx])
        prev_y1 = None
        for ln in lines:
            size, text = ln["size"], ln["text"]
            gap = (ln["y0"] - prev_y1) if prev_y1 is not None else None
            prev_y1 = ln["y1"]
            if size >= 20:
                if title is None:
                    title = text
                continue
            if size >= SIZE_H2:
                bb.feed_heading(text, 2)
                continue
            new_para = gap is None or gap > PARA_GAP or (
                bb._para is not None and bb._para.rstrip().endswith(close_puncts))
            bb.feed_line(size, text, join_prev=not new_para)
        bb.feed_break_if_sentence_end()
    return {"title_raw": title, "blocks": bb.done()}


def pdfminer_pages(pages_idx):
    """pdfminer 逐页全文(0-based 页码 -> 文本)。仅用于找章末来源编号。"""
    from pdfminer.high_level import extract_text
    return {p: extract_text(str(PDF_PATH), page_numbers=[p]) for p in pages_idx}


def pdfminer_column_lines(pages_idx, col_split=306.0):
    """按栏提取文本行: 返回按 (页, 左栏|右栏, y) 排序的文本行列表。
    附录索引是两栏排版; 直接 extract_text 会在条目折行时把两栏粘连。"""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer
    out = []
    for p in pages_idx:
        for layout in extract_pages(str(PDF_PATH), page_numbers=[p]):
            boxes = []
            def walk(o):
                if isinstance(o, LTTextContainer):
                    boxes.append(o)
                elif hasattr(o, "__iter__"):
                    for c in o:
                        walk(c)
            walk(layout)
            def key(b):
                col = 0 if b.x0 < col_split else 1
                return (col, -round(b.y1, 1))
            for b in sorted(boxes, key=key):
                for line in b.get_text().splitlines():
                    t = re.sub(r"\s{2,}", " ", line).strip()
                    if t:
                        out.append(t)
    return out


SOURCE_MARK_RE2 = re.compile(r"^\[R(\d+)\]")


def parse_ref_map(pm_texts, start, end):
    """完整参考文献页 -> {R号: 引用文本}。pdfminer 按栏序输出。"""
    text = "\n".join(pm_texts.get(p, "") for p in range(start - 1, end))
    lines = []
    for raw in text.splitlines():
        t = raw.strip()
        if not t or t in ("完整参考文献", "地球生命演化史", "附录与索引"):
            continue
        if re.fullmatch(r"\d{3}", t):      # 页码
            continue
        if re.fullmatch(r"\d+\.", t):      # 列表序号(与 [RN] 重复)
            continue
        lines.append(t)
    text = "\n".join(lines)
    ref_map = {}
    for part in re.split(r"(?=\[R\d+\])", text):
        m = SOURCE_MARK_RE2.match(part.strip())
        if not m:
            continue
        body = part.strip()
        body = re.sub(r"-\s*\n\s*", "-", body)     # 连字符断词复原
        body = re.sub(r"\s*\n\s*", " ", body)
        body = re.sub(r"\s{2,}", " ", body).strip()
        ref_map[int(m.group(1))] = body[m.end():].strip()

    # R16 在源 PDF 里以碎片化文本框排版, 两种提取器的行序都会打乱; 人工校正这一句。
    ref_map[16] = ("Butterfield, N. J. Bangiomorpha pubescens n. gen., n. sp.: implications "
                   "for the evolution of sex, multicellularity, and the Mesoproterozoic/"
                   "Neoproterozoic radiation of eukaryotes. Paleobiology 26, 386-404 (2000).")
    return ref_map


def parse_index_entries_from_lines(lines, drop_titles):
    """通用索引条目解析(物种/术语)。格式: 名称：第N章 · 页(；第N章 · 页)。名称可折行。"""
    entries, buf = [], ""
    incomplete = re.compile(r"：(?:第\d+章\s*·\s*\d+；)*第\d+章\s*·\s*$")  # 页码尚未接上
    refs_pat = re.compile(r"：((?:第\d+章\s*·\s*\d+(?:；)?)+)")
    continuation = re.compile(r"^(?:；)?第\d+章\s*·\s*(?:\d|$)")

    def split_ready(buf):
        """buffer 中每出现一组 '名称：引用列表' 就切出一条; 返回余下未完成的尾巴。
        引用组后面紧跟 ';第N章 ·' 说明本条引用还没折完, 必须等下一行。"""
        made = []
        while True:
            m = refs_pat.search(buf)
            if not m:
                break
            tail = buf[m.end():]
            if (m.group(1).endswith("；") and not tail.strip()) or continuation.match(tail):
                break
            name = buf[:m.start()].strip()
            refs = [{"chapter": int(c), "page": int(pg)}
                    for c, pg in re.findall(r"第(\d+)章\s*·\s*(\d+)", m.group(1))]
            made.append({"name": name, "refs": refs})
            buf = tail
        return made, buf

    for t in lines:
        if t in drop_titles or t.startswith(("页码链接", "术语后的页码")):
            continue
        if re.fullmatch(r"\d{1,3}", t):
            if incomplete.search(buf):
                buf += " " + t     # 索引页码折行
            # 否则是页脚页码, 丢弃
        else:
            buf += t
        made, buf = split_ready(buf)
        entries.extend(made)
    if buf.strip():
        buf = re.sub(r"：(?:第\d+章\s*·\s*\d+；)*第\d+章\s*·\s*$", "", buf).strip()
        entries.append({"name": buf, "refs": []})
    return entries


def parse_summary(doc, page_range, drop_titles):
    """全书总结页(两栏+表格混排)解析。

    50 物种表用 find_tables 直接拿单元格; 其余小节按行流分类:
      → 标题  -> 连续演化案例(四)
      解决:/打开: -> 演化创新(一)
      约X年前  -> 时间轴
      其余短行+描述行 -> 按所属区(三/五/六)
    """
    lines = pdfminer_column_lines(page_range)
    skip = set(drop_titles) | {"中文名 / 学名", "年代", "大小", "生态位",
                               "最值得记住的特点", "完整生命演化时间轴",
                               "功能", "独立出现的支系", "为什么相似、又为什么不同"}
    lines = [t for t in lines if t not in skip and not re.fullmatch(r"\d{3}", t)]
    # ---- 50 物种表 ----
    species_cards = []
    for p in page_range:
        for tab in doc[p].find_tables().tables:
            rows = tab.extract()
            if not rows or not rows[0] or "中文名" not in (rows[0][0] or "") \
                    and not any("中文名" in (c or "") for r in rows[:2] for c in r):
                continue
            for r in rows:
                raw = ["-" if c is None else c for c in r]
                # 单元格内折行: 连字符且不补空格; 中英文之间补空格
                cells = []
                for c in raw:
                    c = re.sub(r"-\s*\n\s*", "-", c)
                    c = re.sub(r"\s*\n\s*", "", c)
                    c = re.sub(r"(?<=[一-鿿])(?=[A-Za-z])", " ", c)   # 中文名 | 学名
                    c = re.sub(r"\s{2,}", " ", c).strip()
                    cells.append(c)
                if not cells or "中文名" in cells[0] or not cells[0]:
                    continue
                if len(cells) < 5:
                    continue
                if "第" in cells[0] and "章" in cells[0]:  # 上一节残片
                    continue
                species_cards.append({
                    "name": cells[0], "era": cells[1], "size": cells[2],
                    "niche": cells[3], "feature": cells[4],
                })

    # ---- 行流状态机 ----
    h2_pat = re.compile(r"^(一|二|三|四|五|六)、(.+)$")
    chap_ref = re.compile(r"^(.+?)\s+第([\d—–、,，\s]+)章$")
    era_pat = re.compile(r"^(约|至少约)[\d—–.,，KkPg\-－亿万千年前至今及\s]+(年前|至今|以前|及更早|以后)$")
    secs = {k: [] for k in ("intro", "一", "二", "三", "四", "五", "六", "时间轴")}
    order = []
    cur = "intro"
    i, n = 0, len(lines)
    _guard = 0

    def next_is_solve(j):
        return j < n and lines[j].startswith("解决：")

    while i < n:
        _guard += 1
        if _guard > n * 3 + 100:
            raise RuntimeError(f"parse_summary 卡住: i={i} cur={cur} t={lines[i][:50]!r}")
        t = lines[i]
        m = h2_pat.match(t)
        if m:
            cur = m.group(1)
            if cur not in order:
                order.append(cur)
            i += 1
            continue
        if cur == "二":
            # 表格区: 只有 'X 第N章' + 解决/打开 是上一节(一)翻栏后的延续
            m2 = chap_ref.match(t)
            if m2 and "→" not in t and next_is_solve(i + 1):
                pass  # 交给创新规则
            else:
                i += 1
                continue
        m2 = chap_ref.match(t)
        if m2 and "→" in t:
            j = i + 1
            desc = ""
            while j < n and not chap_ref.match(lines[j]) and not h2_pat.match(lines[j]) \
                    and not era_pat.match(lines[j]) and not desc.endswith(("。", "!", "?")):
                desc += lines[j]
                j += 1
            secs["四"].append({"name": m2.group(1), "chapter": m2.group(2), "desc": desc})
            if "四" not in order:
                order.append("四")
            i = j
            continue
        if m2 and next_is_solve(i + 1):
            # 创新条目源排版恒为: 标题行 + "解决:"行 + "打开:"行 (均单行)
            solve = open_ = ""
            j = i + 1
            if j < n and lines[j].startswith("解决："):
                solve = lines[j][3:]
                j += 1
            if j < n and lines[j].startswith("打开："):
                open_ = lines[j][3:]
                j += 1
            secs["一"].append({"name": m2.group(1), "chapter": m2.group(2),
                              "solve": solve, "open": open_})
            i = j
            continue
        if m2:
            j = i + 1
            desc = ""
            while j < n and not chap_ref.match(lines[j]) and not h2_pat.match(lines[j]) \
                    and not era_pat.match(lines[j]) and "→" not in lines[j] \
                    and not desc.endswith(("。", "!", "?")):
                desc += lines[j]
                j += 1
            secs["三"].append({"name": m2.group(1), "chapter": m2.group(2), "desc": desc})
            i = j
            continue
        if era_pat.match(t):
            j = i + 1
            desc = ""
            # 时间轴描述恒为单行; 多吞会把下方卡片标题卷进来
            if j < n and not era_pat.match(lines[j]) and not h2_pat.match(lines[j]) \
                    and not chap_ref.match(lines[j]):
                desc = lines[j]
                j += 1
            secs["时间轴"].append({"era": t, "desc": desc})
            if "时间轴" not in order:
                order.append("时间轴")
            i = j
            continue
        if cur == "五":
            # 趋同演化: 名称短行(不带句号) + 原因长句(带句号)
            shorts = [t]
            j = i + 1
            while j < n and len(lines[j]) <= 20 and not lines[j].endswith(("。", "!", "?")) \
                    and not h2_pat.match(lines[j]) and not chap_ref.match(lines[j]) \
                    and not era_pat.match(lines[j]):
                shorts.append(lines[j])
                j += 1
            desc = ""
            while j < n and not h2_pat.match(lines[j]) and not chap_ref.match(lines[j]) \
                    and not era_pat.match(lines[j]) and not desc.endswith(("。", "!", "?")):
                desc += lines[j]
                j += 1
            secs["五"].append({"cells": shorts, "desc": desc})
            i = j
            continue
        if cur in ("三", "六"):
            # 短标题 + 描述行(可折行): 吞到描述以句号收尾为止
            if len(t) <= 30 and i + 1 < n and len(lines[i + 1]) > 24:
                j = i + 1
                desc = ""
                while j < n and not h2_pat.match(lines[j]) and not chap_ref.match(lines[j]) \
                        and not era_pat.match(lines[j]):
                    line = lines[j]
                    if len(line) <= 30 and desc.endswith(("。", "!", "?", ";", ";")):
                        break  # 下一张卡片的标题
                    desc += line
                    j += 1
                    if desc.endswith(("。", "!", "?", "；", ";")):
                        break
                secs[cur].append({"name": t, "desc": desc})
                i = j
                continue
        if cur == "intro":
            secs["intro"].append(t)
        # 其他未识别行丢弃
        i += 1

    return {"species_cards": species_cards, "sections": secs, "order": order}


def main():
    if not PDF_PATH.exists():
        sys.exit(f"PDF 不存在: {PDF_PATH}")
    doc = fitz.open(PDF_PATH)
    toc = doc.get_toc()

    # ---------- 目录解析 ----------
    parts, chapters, front = [], [], {}
    level1 = [(t, p) for l, t, p in toc if l == 1]
    chap_re = re.compile(r"^第(\d+)章\u3000(.+)$")
    for i, (t, p) in enumerate(level1):
        nxt = level1[i + 1][1] if i + 1 < len(level1) else doc.page_count + 1
        m = chap_re.match(t)
        if m:
            chapters.append({"num": int(m.group(1)), "title": m.group(2),
                             "start": p, "end": nxt - 1, "part": None})
        elif t in ("最早的生命世界", "氧气、真核细胞与复杂生命", "埃迪卡拉纪:陌生的复杂生命") \
                or (not m and t not in ("地球生命演化史", "目录") and p < 470 and p >= 7
                    and not t.startswith(("前言", "全书总结", "物种", "术语", "完整", "构建"))):
            parts.append({"title": t, "start": p, "end": nxt - 1})
        else:
            front[t] = {"start": p, "end": nxt - 1}

    # 章归入篇
    for ch in chapters:
        for part in parts:
            if part["start"] < ch["start"]:
                ch["part"] = part["title"]
    # 篇序号
    for i, part in enumerate(parts):
        part["num"] = i + 1

    # 篇扉页导语(12pt 那行, 可能折行)
    for part in parts:
        brief = ""
        for ln in page_lines(doc[part["start"] - 1]):
            if 11.5 <= ln["size"] <= 12.5:
                brief += ln["text"]   # 折行拼接
        part["brief"] = brief

    # ---------- pdfminer 文本(两栏/英文字体页用) ----------
    # 附录页 + 每章末页(来源小节可能在其中)
    appendix_titles = ("物种与代表记录索引", "术语索引", "完整参考文献")
    pm_needed = set()
    for t in appendix_titles:
        if t in front:
            pm_needed.update(range(front[t]["start"] - 1, front[t]["end"]))
    for ch in chapters:
        pm_needed.update(range(ch["end"] - 2, ch["end"]))  # 末两页,覆盖来源小节
    print(f"pdfminer 处理 {len(pm_needed)} 页 ...")
    pm_texts = pdfminer_pages(sorted(pm_needed))

    # ---------- 逐章解析 ----------
    PLATE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plate_problems = []

    def chapter_h3(ch):
        return [t for l, t, p in toc if l == 3 and ch["start"] <= p <= ch["end"]]

    for ch in chapters:
        start = ch["start"] - 1  # 0-based
        plate = start + 1
        ptxt = doc[plate].get_text()
        if "章节配图" not in ptxt:
            plate_problems.append(ch["num"])
            plate = None
        pages = list(range(start, ch["end"]))
        if plate is not None:
            pages.remove(plate)
            # 渲染彩图: 只截取配图插图的图片区域, 不带上下的页眉与图注文字
            ppage = doc[plate]
            rects = []
            for im in ppage.get_images(full=True):
                rects += ppage.get_image_rects(im[0])
            if rects:
                big = max(rects, key=lambda r: r.width * r.height)
                clip = fitz.Rect(big.x0 - 6, big.y0 - 6, big.x1 + 6, big.y1 + 6) \
                    & ppage.rect
            else:
                clip = ppage.rect
            pix = ppage.get_pixmap(dpi=150, clip=clip)
            pix.save(str(PLATE_DIR / f"chapter-{ch['num']:02d}.jpg"))
            # 取配图页正文说明
            expl = ""
            for ln in page_lines(doc[plate]):
                if 9.5 <= ln["size"] <= 11.5 and "说明" not in ln["text"][:3]:
                    expl += ln["text"]
            ch["plate_caption"] = expl.strip()
        data = parse_chapter_pages(doc, pages, f"第{ch['num']}章\u3000{ch['title']}",
                                   h3_titles=chapter_h3(ch))
        ch.update(data)
        # 章末来源: 用 pdfminer 文本找 "本章精选来源" 之后的 [RN] 编号
        src_ids = []
        ch_pages_txt = "\n".join(pm_texts.get(p, "") for p in range(start, ch["end"]))
        msrc = re.search(r"本章精选来源(.*)", ch_pages_txt, re.S)
        if msrc:
            seen = set()
            for rid in re.findall(r"\[R(\d+)\]", msrc.group(1)):
                rid = int(rid)
                if rid not in seen:
                    seen.add(rid)
                    src_ids.append(rid)
        ch["source_refs"] = sorted(src_ids)
        # 正文内嵌示意图: 按记录的 clip 区域整段渲染
        for b in ch["blocks"]:
            if b["type"] != "figure":
                continue
            fname = f"fig-{b['fig'].replace('-', '_')}.png"
            fpath = FIG_DIR / fname
            page = doc[b["page"] - 1]
            clip = fitz.Rect(b["clip"])
            # 防止 clip 与文字重叠: 已在解析时留边
            pix = page.get_pixmap(dpi=150, clip=clip)
            if pix.width < 40 or pix.height < 30:
                b["type"] = "caption_only"
                continue
            pix.save(str(fpath))
            b["src"] = f"assets/figures/{fname}"
        if not ch["title_raw"]:
            print(f"[warn] 第{ch['num']}章未定位到标题")

    # ---------- 前言 ----------
    fw_key = next((k for k in front if k.startswith("前言")), None)
    foreword = None
    if fw_key:
        fw = front[fw_key]
        foreword = parse_flat_pages(doc, list(range(fw["start"] - 1, fw["end"])))

    # ---------- 全书总结 ----------
    sm_key = next((k for k in front if k.startswith("全书总结")), None)
    summary = None
    if sm_key:
        sm = front[sm_key]
        summary = parse_summary(doc, range(sm["start"] - 1, sm["end"]),
                                ("附录与索引", "地球生命演化史", "全书总结:生命树如何运行",
                                 "全书总结：生命树如何运行"))

    # ---------- 术语索引 / 完整参考文献 / 物种索引(pdfminer) ----------
    glossary = []
    if "术语索引" in front:
        g = front["术语索引"]
        glossary = parse_index_entries_from_lines(
            pdfminer_column_lines(range(g["start"] - 1, g["end"])),
            ("术语索引", "地球生命演化史", "附录与索引"))

    references = []
    if "完整参考文献" in front:
        r = front["完整参考文献"]
        ref_map = parse_ref_map(pm_texts, r["start"], r["end"])
        references = [{"id": k, "text": ref_map[k]} for k in sorted(ref_map)]

    species = []
    if "物种与代表记录索引" in front:
        sp = front["物种与代表记录索引"]
        species = parse_index_entries_from_lines(
            pdfminer_column_lines(range(sp["start"] - 1, sp["end"])),
            ("物种与代表记录索引", "地球生命演化史", "附录与索引"))

    book = {
        "title": "地球生命演化史",
        "source_pdf": str(PDF_PATH),
        "parts": [{"num": p["num"], "title": p["title"], "brief": p["brief"]} for p in parts],
        "chapters": chapters,
        "foreword": foreword,
        "summary": summary,
        "glossary": glossary,
        "references": references,
        "species_index": species,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- 自检输出 ----------
    print(f"parts={len(parts)} chapters={len(chapters)} glossary={len(glossary)} "
          f"refs={len(references)} species={len(species)}")
    print("plate problems:", plate_problems or "无")
    n_fig = sum(1 for ch in chapters for b in ch["blocks"] if b["type"] == "figure")
    print("inline figures:", n_fig)
    no_blocks = [c["num"] for c in chapters if len(c["blocks"]) < 10]
    print("blocks<10 的章:", no_blocks or "无")


if __name__ == "__main__":
    main()
