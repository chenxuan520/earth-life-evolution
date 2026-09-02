# Project Rules

- 本项目是《地球生命演化史》PDF 的在线书整理。内容唯一来源是 ~/temp 下的 PDF,
  正文一律由 `docs/evolution-book/tools/extract_pdf.py` 抽取生成, 不要手改生成的 HTML。
- 改内容 -> 改 extract_pdf.py, 重新抽取 + 构建 + check; 改排版 -> 改 build_book.py 或
  assets/book.css 末尾的 "evolution-book 新增组件" 段落(book.css 前半与 finance-book 保持一致)。
- 工具链 Python: 需要 ≥3.10 且装有 pymupdf、pdfminer.six。参考环境: /tmp/opencode/pdfenv
  (临时目录会被清, 丢失时用 `uv venv` + `uv pip install pymupdf pdfminer.six` 重建)。
- 任何改动完成后必须跑 `tools/check_book.py`, 并用本地 http.server + 浏览器实际打开
  index / 一个章节页 / chapter-61 / glossary 确认渲染。
- 已知刻意保留的取舍: 章节正文不自动内链术语; 原 PDF 页码在在线版中换成章节链接;
  物种索引有 1 条源文件缺页码的残缺引用(阿拉莫龙条目)按原样保留。
