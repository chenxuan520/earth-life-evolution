# 地球生命演化史 · 在线书

把同名 PDF 文稿《地球生命演化史(正式版·全章彩图版)》结构化整理成静态在线书,
组织方式参考同目录另一本书《从金融零基础到量化研究者》(finance-to-quant)。

## 目录结构

```
docs/evolution-book/
  index.html            封面 + 八条主线地图 + 20 篇目录
  chapter-00.html       前言(阅读方法与证据标签)
  chapter-01..60.html   60 个正文章
  chapter-61.html       全书总结(20 次创新 / 50 物种表 / 10 洗牌 / 时间轴)
  glossary.html         附录: 术语索引 54 · 物种索引 299 · 完整参考文献 113
  assets/
    book.css book.js favicon.svg   从 finance-book 复用并少量追加
    plates/chapter-XX.jpg          每章开篇科学复原彩图(共 60 张)
    figures/fig-X_Y.png            正文内嵌概念示意图(共 25 张)
  notes/
    manuscript.json     结构化手稿(抽取结果)
    source_pdf_text.txt PDF 全文纯文本备份
  tools/
    extract_pdf.py      PDF -> manuscript.json + 图片
    build_book.py       manuscript.json -> 全部 HTML + 重写 book.js 数据块
    check_book.py       静态检查(链接/图片/标题/字数核对)
```

## 重新构建

```bash
PY=$HOME/.opencode-venv/pdfenv/bin/python   # 任一 >=3.10 且装了 pymupdf + pdfminer.six 的解释器
cd docs/evolution-book
$PY tools/extract_pdf.py     # 约 3-5 分钟(pdfminer 逐页解析较慢)
$PY tools/build_book.py
$PY tools/check_book.py
```

本地预览: `python3 -m http.server 8137 --bind 127.0.0.1`, 打开 `http://127.0.0.1:8137/`。

## 数据要点

- 正文章节骨架完全来自 PDF 书签和字号层级: 每章统一为
  进入这个时代 / 生态系统如何运转 / 关键演化创新 / 生命群像(物种条目) /
  因果链 / 时代横截面 / 科学家为什么这样判断 / 过去的图景与今天的证据 /
  跨尺度观察 / 通向下一个时代 / 本章精选来源。
- 章末"本章精选来源"是两栏排版, 正文层提取会错乱;
  改由 pdfminer 只取 [RN] 编号, 再回链到完整参考文献映射。
- 术语索引、物种索引、完整参考文献用 pdfminer 按栏(x0≈306 分界)重排行序。
- 原来 PDF 的参考条目正文字体中部分拉丁字形对 PyMuPDF 不可见, 必须用 pdfminer 兜底;
  [R16] 一条在源文件里以碎片化文本框排版, 行序人工校正过(extract_pdf.py 内有注释)。
