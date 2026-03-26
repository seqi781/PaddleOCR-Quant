# PaddleOCR-Quant

面向财报处理的本地轻量 MVP。当前版本已经把“本地文件接入 -> 解析 -> 标准化 -> 简单检索/问答 -> 评分 -> API/CLI”串起来，保持单机可运行，不依赖 Kafka、Spark、Flink、MinIO。

## 当前已实现

- FastAPI 服务与 Typer CLI
- SQLite 本地存储
- 本地对象存储目录，用于保存原始文件和解析结果
- 本地文件接入：支持 `pdf`、`txt`、`md`、`html`
- 文件哈希计算、扩展名识别、对象存储复制
- 解析器选择逻辑
  - `mock-paddleocr`：继续支持现有 OCR fixtures
  - `text-heuristic`：解析 `txt/md/html`
  - `pdf-fallback`：若未安装 PDF 库则优雅降级
- 文本 chunk 持久化与 SQLite 检索占位索引
- 关键词搜索与 grounded QA 模板回答
- CN/HK/US 样例 crawler skeleton
- 财务字段标准化与规则型评分
- 覆盖 ingest / parse / search / QA 的测试

## 没有实现的内容

这个仓库仍然不是原始“大数据生产方案”的完整实现，下面这些仍未落地：

- 真实生产级抓取器和调度系统
- 真正的 PaddleOCR / PP-Structure 文档理解链路
- 分布式消息队列、流处理、数据湖
- 向量检索、RAG 编排、LLM 推理服务
- XBRL、表格恢复、复杂多页版面分析
- 行情、估值、行业基准、币种统一服务

这些差距也在 [docs/roadmap.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/roadmap.md) 中明确写出。

## 目录概览

```text
src/paddleocr_quant/
  api.py
  bootstrap.py
  cli.py
  crawlers.py
  ingestion.py
  main.py
  models.py
  normalization.py
  parser.py
  retrieval.py
  scoring.py
  storage.py
fixtures/
  financials/
  mock_ocr/
docs/
  api.md
  architecture.md
  roadmap.md
tests/
```

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

启动 API：

```bash
uvicorn paddleocr_quant.api:app --reload
```

运行测试：

```bash
pytest -q
```

## CLI 示例

初始化内置评分样例数据：

```bash
paddleocr-quant seed
```

接入本地文本文件：

```bash
paddleocr-quant ingest ./sample_report.md AAPL Apple 2025 --market US --language en-US
```

解析文档：

```bash
paddleocr-quant parse doc-xxxxxxxxxxxx
```

搜索：

```bash
paddleocr-quant search doc-xxxxxxxxxxxx revenue
```

问答：

```bash
paddleocr-quant ask doc-xxxxxxxxxxxx "What does the report say about revenue?"
```

列出样例 filings：

```bash
paddleocr-quant sample-filings US AAPL
```

## API 概览

- `GET /health`
- `POST /documents`
- `POST /documents/{document_id}/parse`
- `GET /documents/{document_id}/search?q=...`
- `POST /documents/{document_id}/qa`
- `GET /filings/sample?market=US&ticker=AAPL`
- `POST /scores/company`
- `POST /scores/compare`

详细请求/响应示例见 [docs/api.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/api.md)。

## 本地文件接入行为

当 `POST /documents` 或 `paddleocr-quant ingest` 指向本地路径时，会执行：

1. 校验文件存在
2. 计算 SHA-256
3. 识别扩展名和 MIME
4. 复制到本地对象存储目录 `data/object_store/raw/`
5. 持久化文档元数据到 SQLite

解析后会把 chunk 和解析结果持久化到 SQLite 与对象存储。

## PDF 支持说明

PDF 路径已经支持接入和解析器选择，但当前默认不额外引入 PDF 依赖。如果环境中已经安装 `pypdf`，解析器会尝试抽取文本；否则会返回一个带 warning 的降级结果，保证链路可运行。

## 相关文档

- API 说明：[docs/api.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/api.md)
- 路线图：[docs/roadmap.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/roadmap.md)
- 架构说明：[docs/architecture.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/architecture.md)
