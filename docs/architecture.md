# 架构说明

## 定位

PaddleOCR-Quant 当前是一个单机、本地、轻量 MVP。目标不是一次性实现完整大数据平台，而是把下面这些稳定边界先落地：

- 文档接入与元数据
- 解析器接口与选择逻辑
- 财务字段标准化
- 本地检索与 grounded QA
- 因子评分
- API / CLI 服务边界

## 当前实现

### 接入层

- `POST /documents` 和 `paddleocr-quant ingest`
- 支持 `pdf`、`txt`、`md`、`html`
- 计算 SHA-256
- 复制原文件到本地对象存储

### 解析层

- `MockPaddleOCRParser`
  - 读取 `fixtures/mock_ocr/*.json`
- `TextDocumentParser`
  - 解析 `txt/md/html`
  - 提取纯文本与简单财务别名
- `PDFDocumentParser`
  - 先做 PDF 文本可抽取性检测
  - 可抽取时走文本路径
  - 不可抽取时走 OCR 路径
- `OCRAdapter`
  - 当前实现 `PaddleOCRAdapter`
  - 依赖缺失时返回结构化 warning 和 page placeholder
- `pdf.py`
  - 页面图像准备占位层
  - 不强制引入 Poppler 或重依赖

### 存储层

- SQLite
  - `documents`
  - `parsed_documents`
  - `document_chunks`
  - `company_metrics`
- 本地对象存储
  - 原始文件
  - 文档元数据 JSON
  - 解析结果 JSON

### 检索与问答层

- chunk 持久化到 SQLite
- 关键词匹配搜索
- 基于 top chunks 的 grounded QA 模板回答

### 市场源占位层

- `crawlers.py`
  - CN/HK/US source interface
  - 返回样例 filings stub 输出

## 与原始大数据方案的映射

| 目标层 | 生产化设想 | 当前本地实现 |
|---|---|---|
| 文档采集 | 交易所 crawler / 调度系统 | 本地文件 ingest + sample filing stubs |
| 原始存储 | S3 / MinIO / 数据湖 | 本地目录对象存储 |
| OCR / 解析 | PaddleOCR / PDF pipeline | mock parser + text parser + PDF strategy detection + optional PaddleOCR adapter |
| 元数据与事实 | PostgreSQL / OLAP | SQLite |
| 检索 | FTS / ES / 向量库 | SQLite chunk records + 关键词匹配 |
| 问答 | RAG + LLM | grounded response template |
| 编排 | 事件驱动 / 工作流 | 同步 API / CLI |

## 为什么先做这种形态

因为对本项目最重要的是先把协议跑通，而不是先堆重型基础设施。当前形态的价值在于：

- 可以在本地快速演示
- 可以稳定写测试
- 可以明确后续替换点
- 可以逐步升级成更真实的 parser / crawler / retrieval

## 明确未实现

下面这些仍然不在当前仓库里：

- Kafka / Spark / Flink / MinIO
- 真实生产级公告抓取
- 复杂版面分析、表格恢复、XBRL
- 向量索引与 LLM 驱动问答
- 任务调度、监控、重试、审计链路

这些内容属于未来扩展，而不是当前本地 MVP 的运行前提。
