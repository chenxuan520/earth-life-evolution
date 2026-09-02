#!/usr/bin/env python3
"""把 notes/manuscript.json 渲染成静态 HTML 书。

生成:
  index.html            封面 + 主线地图 + 20 篇目录
  chapter-00..61.html   前言 / 60 章 / 全书总结
  glossary.html         附录: 术语索引 + 物种索引 + 完整参考文献
  assets/book.js        重写开头 CHAPTERS/书名/存储键数据块
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK_TITLE = "地球生命演化史"
BOOK_SUBTITLE = "从岩石证据到生命网络的四十亿年"

M = json.loads((ROOT / "notes" / "manuscript.json").read_text(encoding="utf-8"))
PARTS = M["parts"]                       # 20 篇
CHAPTERS = M["chapters"]                 # 60 章
REF_BY_ID = {r["id"]: r["text"] for r in M["references"]}
PART_OF = {c["num"]: c["part"] for c in CHAPTERS}
PART_NUM = {p["title"]: p["num"] for p in PARTS}
MAIN_LINES = [
    ("主线一 · 微观起点", "生命最早怎样在岩石里留下可信痕迹?",
     "理解化石证据的分级, 以及微生物席如何统治地球前 20 亿年。", [1, 2]),
    ("主线二 · 复杂生命的黎明", "氧气、真核细胞和多细胞身体是怎样拼出来的?",
     "看到能量革命、内共生和雪球地球怎样为复杂生命开门。", [3, 4]),
    ("主线三 · 海洋大繁荣与登陆", "海洋多样性为何跃升, 生命又怎样爬上陆地?",
     "理解大辐射、大灭绝, 以及植物与节肢动物的先锋登陆。", [5, 6]),
    ("主线四 · 鱼与四足动物", "颌和四肢分别改变了什么?",
     "回到鱼类王朝与浅水旁支, 看四足身体怎样镶嵌拼成。", [7]),
    ("主线五 · 羊膜动物与合弓王朝", "摆脱水之前, 陆地上发生过哪些实验?",
     "认识煤沼、巨虫、羊膜卵与被恐龙掩盖的合弓类世界。", [8, 9, 10]),
    ("主线六 · 恐龙王朝与终结", "中生代生态系统怎样运转, 又为何崩塌?",
     "从三叠纪重启读到 K-Pg 撞击后的幸存者名单。", [11, 12, 13, 14]),
    ("主线七 · 哺乳动物与现代世界", "恐龙退场后, 谁重写陆地与海洋?",
     "跟随鲸、马、象与草原化, 一直走到冰河时代的巨兽。", [15, 16, 17, 18, 19]),
    ("主线八 · 回望四十亿年", "生命树为什么没有顶端?",
     "用人族 shrubbery 与趋同演化收束全书, 带走整株生命树。", [20]),
]



def esc(t):
    return html.escape(str(t), quote=False)


def chapter_file(n):
    return f"chapter-{n:02d}.html"


def toc_card(num_label, title, desc, href):
    return (f'<a class="toc-card reveal" href="{href}">'
            f'<span class="toc-card__num">{esc(num_label)}</span>'
            f'<span class="toc-card__title">{esc(title)}</span>'
            f'<span class="toc-card__desc">{esc(desc)}</span></a>')


# ---------------------------------------------------------------- 页面骨架
def page(title, description, body, body_attr="", extra_js=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{esc(title)} | {BOOK_TITLE}</title>
    <meta name="description" content="{esc(description)}" />
    <link rel="icon" href="assets/favicon.svg" />
    <link rel="stylesheet" href="assets/book.css" />
  </head>
  <body{body_attr}>
{body}
    <script src="assets/book.js"></script>
  </body>
</html>
"""


# ---------------------------------------------------------------- 正文渲染
def render_blocks(blocks, chnum=None):
    """章节 blocks -> HTML。图注/图、物种条目、段落。"""
    out = []
    open_species = 0
    for b in blocks:
        t = b["type"]
        if t == "h2":
            while open_species:
                out.append("</div>")
                open_species -= 1
            out.append(f"<h2>{esc(b['text'])}</h2>")
        elif t == "h3":
            if not open_species:
                out.append('<div class="species-grid">')
                open_species += 1
            out.append(f'<div class="species-card"><h3>{esc(b["text"])}</h3>')
        elif t == "p":
            txt = b["text"]
            if open_species:
                out.append(f"<p>{esc(txt)}</p>")
            else:
                out.append(f"<p>{esc(txt)}</p>")
        elif t == "figure":
            cap = esc(b["caption"])
            out.append(
                f'<div class="figure reveal"><img class="figure__img" '
                f'src="{b["src"]}" alt="{cap}" loading="lazy" />'
                f'<p class="figure__cap">{cap}</p></div>')
    while open_species:
        out.append("</div>")
        open_species -= 1
    return "\n".join(out)


def split_chapter(ch):
    """章首导读(第一个 h2 之前的段落) 与 正文小节。"""
    lead, body = [], []
    seen_h2 = False
    for b in ch["blocks"]:
        if b["type"] == "h2":
            seen_h2 = True
        (body if seen_h2 else lead).append(b)
    return lead, body


def render_chapter(num, title, subtitle, part_title, lead_blocks, body_blocks,
                   plate=None, plate_caption="", source_refs=(), body_attr_extra=""):
    pnum = PART_NUM[part_title]
    idx_in_part = len([c for c in CHAPTERS if c["part"] == part_title and c["num"] < num]) + 1
    part_size = len([c for c in CHAPTERS if c["part"] == part_title])
    part_brief = next((p["brief"] for p in PARTS if p["title"] == part_title), "")

    lead_html = ""
    for i, b in enumerate(lead_blocks):
        if b["type"] == "p":
            cls = ' class="lead"' if i == 0 else ""
            lead_html += f"<p{cls}>{esc(b['text'])}</p>\n"

    plate_html = ""
    if plate:
        plate_html = f"""
        <div class="figure figure--plate reveal">
          <img class="figure__img figure__img--plate" src="{plate}" alt="{esc(title)} · 本章科学复原配图" loading="lazy" />
          <p class="figure__cap">本章科学复原配图 <span class="muted">（用于呈现结构与生态关系, 不替代化石照片、测量数据与系统发育证据。）</span></p>
        </div>"""

    refs_html = ""
    if source_refs:
        items = []
        for rid in source_refs:
            txt = REF_BY_ID.get(rid)
            if not txt:
                continue
            items.append(f'<li id="src-r{rid}">'
                         f'<a class="xref" href="glossary.html#r-{rid}">[R{rid}]</a> {esc(txt)}</li>')
        if items:
            refs_html = ('<section class="chapter-sources reveal"><h2>本章精选来源</h2>'
                         '<ol class="source-list">' + "".join(items) + "</ol></section>")

    eyebrow = f"第{pnum:02d}篇 · {part_title} · 第 {num} 章"
    body_html = f"""    <main class="chapter">
      <div class="chapter__inner">
        <p class="chapter__eyebrow">{esc(eyebrow)}</p>
        <h1>{esc(title)}</h1>
        <p class="chapter__meta">{esc(subtitle)}</p>
        <section class="chapter-context chapter-context--main">
          <div class="chapter-context__meta">
            <span class="chapter-context__badge">第{pnum:02d}篇</span>
            <span>本篇第 {idx_in_part} / {part_size} 章</span>
          </div>
          <p><strong>本篇主题:</strong>{esc(part_title)}</p>
          <p class="chapter-context__outcome">{esc(part_brief)}</p>
        </section>
{plate_html}
{lead_html}
{render_blocks(body_blocks)}
{refs_html}
      </div>
    </main>"""
    desc = subtitle or part_brief
    return page(f"第 {num} 章 · {title}", desc, body_html,
                body_attr=f' data-chapter="{num}"{body_attr_extra}')


# ---------------------------------------------------------------- index.html
def build_index():
    roadmap_cards = []
    for idx, (name, question, outcome, part_nums) in enumerate(MAIN_LINES, start=1):
        chs = [c for c in CHAPTERS if PART_NUM[c["part"]] in part_nums]
        rng = f"第{chs[0]['num']}–{chs[-1]['num']} 章" if chs else ""
        roadmap_cards.append(f"""
        <a class="roadmap-card" href="#line-{idx}">
          <span>{esc(name)} · {esc(rng)}</span>
          <strong>{esc(question)}</strong>
          <small>{esc(outcome)}</small>
        </a>""")

    toc_html_list = []
    for idx, (line_name, question, outcome, part_nums) in enumerate(MAIN_LINES, start=1):
        plist = [p for p in PARTS if p["num"] in part_nums]
        for k, p in enumerate(plist):
            head = ""
            if k == 0:
                head = (
                    f'<div class="toc-line" id="line-{idx}"><div class="toc-part-header">'
                    f'<span class="toc-part-badge">{esc(line_name)}</span>'
                    f'<h2 class="toc-line__question">{esc(question)}</h2>'
                    f'<p>{esc(outcome)}</p></div></div>')
            cards = [f"""
      <section class="toc-part-block toc-part-block--main" id="part-{p['num']}">
        <div class="toc-part-header">
          <span class="toc-part-badge">第{p['num']:02d}篇</span>
          <h2>{esc(p['title'])}</h2>
          <p class="toc-part-question">{esc(p['brief'])}</p>
        </div>
        <div class="toc-grid">"""]
            for c in [c for c in CHAPTERS if c["part"] == p["title"]]:
                cards[0] += "\n          " + toc_card(
                    f"第 {c['num']} 章", c["title"], c["subtitle"],
                    chapter_file(c["num"]))
            cards[0] += "\n        </div>\n      </section>"
            toc_html_list.append(head + "".join(cards))

    toc_html = "\n".join(toc_html_list)

    n_species = sum(1 for c in CHAPTERS for b in c["blocks"] if b["type"] == "h3")
    n_figs = sum(1 for c in CHAPTERS for b in c["blocks"] if b["type"] == "figure")

    body = f"""    <header class="cover">
      <div class="cover__inner">
        <p class="cover__eyebrow">{esc(BOOK_SUBTITLE)}</p>
        <h1>{BOOK_TITLE}</h1>
        <p class="cover__lead">
          沿着二十个时代, 从岩石里最早的微生物信号走到冰河时代与人类登场。
          每一章先把环境与能量条件摆回现场, 再看物种如何摄食、竞争、合作和繁殖,
          最后说清哪些结论是高可信、主流解释、合理推测还是争议较大。
        </p>
        <div class="cover__actions">
          <a class="button button--primary" data-continue href="chapter-00.html">开始阅读</a>
          <a class="button button--ghost" href="glossary.html">术语与索引</a>
        </div>
        <p class="muted">
          全书 60 章 · 20 篇 · {n_species} 个物种条目 · {n_figs} 张概念示意图 · 每章配一页科学复原彩图。
          内容由同主题 PDF 文稿结构化整理为在线书, 附 {len(M['glossary'])} 条术语索引、
          {len(M['species_index'])} 条物种索引与 {len(M['references'])} 条完整参考文献。
        </p>
      </div>
    </header>
    <main class="toc-section" id="toc">
      <section class="book-roadmap reveal" aria-labelledby="roadmap-title">
        <p class="book-roadmap__eyebrow">八条主线按时间顺序展开</p>
        <h2 id="roadmap-title">整本书只走一条时间轴</h2>
        <p>从最早的生命信号到生命树如何运行, 八条主线依次推进; 每条主线由若干"篇"(时代)组成, 篇内每章回答一个核心问题。</p>
        <div class="roadmap-grid">{''.join(roadmap_cards)}
        </div>
      </section>
      <div class="toc-heading">
        <p class="book-roadmap__eyebrow">共 60 章 + 前言与全书总结</p>
        <h2>全书目录</h2>
        <p>建议顺序阅读; 时间轴不可逆, 但每章都可以在术语表与物种索引里回看。</p>
      </div>
      <section class="toc-part-block toc-part-block--special">
        <div class="toc-grid">
          {toc_card("前言", "怎样阅读四十亿年生命史", "证据标签、图像与阅读方法。", "chapter-00.html")}
        </div>
      </section>
{toc_html}
      <section class="toc-part-block toc-part-block--appendix">
        <div class="toc-part-header">
          <span class="toc-part-badge">收束与工具</span>
          <h2>回望与随时可查的附录</h2>
          <p class="toc-part-question">读完全书后, 如何用一页页清单回看整株生命树?</p>
        </div>
        <div class="toc-grid">
          {toc_card("总结", "生命树如何运行", "20 次演化创新、50 种代表生命、10 次生态洗牌、完整时间轴。", "chapter-61.html")}
          {toc_card("附录", "术语 · 物种 · 参考文献", "54 条术语索引、299 条物种记录索引与 113 条完整参考文献。", "glossary.html")}
        </div>
      </section>

      <section class="about reveal">
        <h2>关于本书</h2>
        <p>
          这本书讲地球生命四十亿年的演化史: 它不是明星动物的名录, 而是一棵不断分叉、扩张、
          收缩并被灭绝修剪的树; 树上的生物又通过光合作用、掘穴、造礁、森林和迁徙持续改造自己的环境。
          全书持续区分四个证据层级——<strong>高可信</strong>(多件标本、多地点或多方法彼此一致)、
          <strong>主流解释</strong>、<strong>合理推测</strong>和<strong>争议较大</strong>, 读任何结论时都能知道想象走到哪里为止。
        </p>
        <p>
          本在线版由同名 PDF 文稿经结构化抽取自动整理: 每章保留"进入这个时代 → 生态系统如何运转 →
          关键演化创新 → 生命群像 → 因果链 → 证据与方法"的统一骨架, 并整页保留每章开篇的科学复原彩图。
        </p>
        <p class="about__meta">本页与章节内容由工具链自动生成; 目录结构与阅读框架参考同类型开源书的组织方式。</p>
      </section>
    </main>"""
    return page(BOOK_TITLE, BOOK_SUBTITLE, body, body_attr=" data-cover")


# ---------------------------------------------------------------- 前言/总结
def render_foreword():
    fw = M["foreword"]
    blocks = fw["blocks"]
    lead = [b for b in blocks if b["type"] == "p"][:1]
    body_html = render_blocks(blocks)
    inner = f"""    <main class="chapter">
      <div class="chapter__inner">
        <p class="chapter__eyebrow">前言</p>
        <h1>前言：怎样阅读四十亿年生命史</h1>
{body_html}
      </div>
    </main>"""
    return page("前言 · 怎样阅读四十亿年生命史", "阅读方法与证据标签。",
                inner, body_attr=' data-chapter="0"')


def card_list(items, cls):
    return f'<div class="{cls}">' + "".join(items) + "</div>"


def render_summary():
    sm = M["summary"]
    S = sm["sections"]

    intro = "".join(f"<p>{esc(t)}</p>" for t in S["intro"])

    inv = []
    for it in S["一"]:
        inv.append(f"""<div class="sum-card"><h3>{esc(it['name'])}
        <span class="sum-card__chap">第 {esc(it['chapter'])} 章</span></h3>
        <p><strong>解决:</strong>{esc(it['solve'])}</p>
        <p><strong>打开:</strong>{esc(it['open'])}</p></div>""")

    rows = []
    for c in sm["species_cards"]:
        rows.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in
                                     (c["name"], c["era"], c["size"], c["niche"], c["feature"])) + "</tr>")
    sp_table = ('<div class="table-wrap"><table class="sum-table"><thead><tr>'
                "<th>中文名 / 学名</th><th>年代</th><th>大小</th><th>生态位</th><th>最值得记住的特点</th>"
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    def chap_cards(items):
        return [f"""<div class="sum-card"><h3>{esc(it['name'])}
        <span class="sum-card__chap">第 {esc(it['chapter'])} 章</span></h3>
        <p>{esc(it['desc'])}</p></div>""" for it in items]

    conv = []
    for it in S["五"]:
        cells = " ｜ ".join(esc(x) for x in it["cells"])
        conv.append(f'<div class="sum-card"><h3>{cells}</h3><p>{esc(it["desc"])}</p></div>')

    extinct = [f'<div class="sum-card"><h3>{esc(it["name"])}</h3><p>{esc(it["desc"])}</p></div>'
               for it in S["六"]]

    tl_rows = "".join(f'<tr><td class="sum-timeline__era">{esc(x["era"])}</td>'
                      f'<td>{esc(x["desc"])}</td></tr>' for x in S["时间轴"])
    timeline = ('<div class="table-wrap"><table class="sum-table sum-table--timeline">'
                f"<tbody>{tl_rows}</tbody></table></div>")

    inner = f"""    <main class="chapter">
      <div class="chapter__inner">
        <p class="chapter__eyebrow">收束</p>
        <h1>全书总结：生命树如何运行</h1>
        {intro}
        <h2>一、地球生命史最重要的 20 次演化创新</h2>
        {card_list(inv, "sum-grid")}
        <h2>二、最值得认识的 50 种史前生命与代表记录</h2>
        {sp_table}
        <h2>三、10 次关键生态系统重新洗牌</h2>
        {card_list(chap_cards(S['三']), "sum-grid")}
        <h2>四、10 个连续演化案例</h2>
        {card_list(chap_cards(S['四']), "sum-grid")}
        <h2>五、10 个趋同演化案例</h2>
        {card_list(conv, "sum-grid")}
        <h2>六、10 个曾经极度成功但最终消失的支系</h2>
        {card_list(extinct, "sum-grid")}
        <h2>完整生命演化时间轴</h2>
        {timeline}
      </div>
    </main>"""
    return page("全书总结 · 生命树如何运行", "20 次创新、50 种生命、10 次洗牌与完整时间轴。",
                inner, body_attr=' data-chapter="61"')


# ---------------------------------------------------------------- glossary
def render_glossary():
    terms = []
    for g in M["glossary"]:
        links = "；".join(
            f'<a class="xref" href="{chapter_file(r["chapter"])}">第{r["chapter"]}章</a>'
            for r in g["refs"])
        terms.append(f'<li id="g-{esc(g["name"])}"><strong>{esc(g["name"])}</strong>'
                     f'<p>集中讨论: {links}</p></li>')

    species = []
    for s in M["species_index"]:
        ref_html = "；".join(
            f'<a class="xref" href="{chapter_file(r["chapter"])}">第{r["chapter"]}章</a>'
            for r in s["refs"]) or "正文多处出现"
        species.append(f'<li><strong>{esc(s["name"])}</strong><p>{ref_html}</p></li>')

    refs = []
    for r in M["references"]:
        refs.append(f'<li id="r-{r["id"]}">[R{r["id"]}] {esc(r["text"])}</li>')

    inner = f"""    <main class="chapter">
      <div class="chapter__inner">
        <p class="chapter__eyebrow">附录</p>
        <h1>术语 · 物种 · 参考文献</h1>
        <p class="lead">页码出自原 PDF 排版; 在线版直接改成章节链接, 点击术语后的"第N章"跳到最集中讨论的章节。</p>
        <section class="glossary-list reveal">
          <h2>术语索引({len(terms)} 条)</h2>
          <ul>{''.join(terms)}</ul>
        </section>
        <section class="glossary-list reveal">
          <h2>物种与代表记录索引({len(species)} 条)</h2>
          <ul>{''.join(species)}</ul>
        </section>
        <section class="references reveal">
          <h2>完整参考文献({len(refs)} 条)</h2>
          <ol class="source-list source-list--refs">{''.join(refs)}</ol>
        </section>
      </div>
    </main>"""
    return page("术语 · 物种 · 参考文献", "全书术语、物种索引与完整参考文献。",
                inner, body_attr=' data-extra="glossary"')


# ---------------------------------------------------------------- book.js 数据块
def rewrite_book_js():
    js_path = ROOT / "assets" / "book.js"
    js = js_path.read_text(encoding="utf-8")
    entries = []
    entries.append("    { num: 0, title: '前言: 怎样阅读四十亿年生命史', file: 'chapter-00.html', part: '前言' },")
    part_label = {}
    for p in PARTS:
        part_label[p["title"]] = f"第{p['num']:02d}篇 · {p['title']}"
    for c in CHAPTERS:
        entries.append(
            f"    {{ num: {c['num']}, title: '{c['title'].replace(chr(39), chr(92)+chr(39))}', "
            f"file: '{chapter_file(c['num'])}', part: '{part_label[c['part']]}' }},")
    entries.append("    { num: 61, title: '全书总结: 生命树如何运行', file: 'chapter-61.html', part: '收束' }")
    block = ("  var CHAPTERS = [\n" + "\n".join(entries) + "\n  ];\n"
             f'  var BOOK_TITLE = "{BOOK_TITLE}";\n'
             '  var STORAGE_LAST = "evolutionbook:last:v1";')
    pattern = re.compile(r"  var CHAPTERS = \[.*?var STORAGE_LAST\s*=\s*[^;]*;", re.S)
    if not pattern.search(js):
        raise SystemExit("book.js 数据块替换失败(未匹配)")
    out = pattern.sub(block, js, count=1)
    js_path.write_text(out, encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    idx = build_index()
    (ROOT / "index.html").write_text(idx, encoding="utf-8")

    for ch in CHAPTERS:
        lead, body = split_chapter(ch)
        plate = f"assets/plates/chapter-{ch['num']:02d}.jpg"
        html_txt = render_chapter(
            ch["num"], ch["title"], ch["subtitle"] or "", ch["part"],
            lead, body, plate=plate, plate_caption=ch.get("plate_caption", ""),
            source_refs=ch.get("source_refs", []))
        (ROOT / chapter_file(ch["num"])).write_text(html_txt, encoding="utf-8")

    (ROOT / "chapter-00.html").write_text(render_foreword(), encoding="utf-8")
    (ROOT / "chapter-61.html").write_text(render_summary(), encoding="utf-8")
    (ROOT / "glossary.html").write_text(render_glossary(), encoding="utf-8")
    # Pages 站点根跳转: GitHub Pages 以 docs/ 为站点根时, / -> evolution-book/
    (ROOT.parent / "index.html").write_text(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
        '<meta http-equiv="refresh" content="0; url=evolution-book/">'
        f'<title>{BOOK_TITLE}</title></head>'
        '<body><p>前往 <a href="evolution-book/">地球生命演化史在线书</a></p></body></html>\n',
        encoding="utf-8")
    rewrite_book_js()
    print("生成完成: index + 62 章页 + glossary")


if __name__ == "__main__":
    main()
