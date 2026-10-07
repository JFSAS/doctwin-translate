# DocTwin Translate

DocTwin Translate 是用于 Codex 等 AI 代理的 PDF 翻译技能，可生成保留版式的译文 PDF，以及左侧原文、右侧译文的双语 PDF。

它结合 AI 翻译记忆、术语表和 BabelDOC / PDFMathTranslate 排版引擎，支持公式、代码、表格和图表的修复，以及渲染后的页面检查。

## 安装

需要 Git、Python 和能够读取技能说明、运行脚本的 AI 代理。

将仓库安装到 Codex 技能目录：

```bash
git clone https://github.com/JFSAS/doctwin-translate.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/doctwin-translate"
```

在独立 Python 环境中准备依赖和排版引擎：

```bash
SKILL="${CODEX_HOME:-$HOME/.codex}/skills/doctwin-translate"
python3 -m venv "$SKILL/.venv"
"$SKILL/.venv/bin/python" -m pip install pymupdf
"$SKILL/.venv/bin/python" "$SKILL/scripts/bootstrap_upstreams.py" --install babeldoc
```

## 使用

安装后开启新对话，通过 `$doctwin-translate` 调用技能，并提供 PDF 路径、目标语言和需要处理的页码。例如：

```text
使用 $doctwin-translate 将 /path/to/document.pdf 的第 1–10 页翻译为简体中文，
保留公式、代码和表格，生成左侧原文、右侧译文的双语 PDF，不添加水印。
使用技能目录下 .venv/bin/python 运行脚本。
```

默认目标语言为简体中文；可以指定其他语言。代理会收集翻译单元、生成术语表与翻译记忆、构建 PDF，并检查页面渲染结果。

工作文件位于 `tmp/pdfs/<文档名>/`，最终文件位于 `output/pdf/`。完整流程和脚本参数见 [SKILL.md](SKILL.md)。
