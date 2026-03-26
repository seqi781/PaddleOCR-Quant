# PaddleOCR-Quant

一个面向公司财报分析的本地 MVP，目标是把“财报采集 → 文档解析 → 财务标准化 → 因子评分 → 查询服务”先在单机环境跑通。

这个版本**优先覆盖 A 股年报 MVP**，同时预留了港股、美股扩展路径。它不是完整的大数据生产系统，而是一个可运行、可演示、可继续扩展的仓库骨架。

## 这个 MVP 已经实现了什么

- FastAPI 查询服务
- Typer CLI
- SQLite 本地结构化存储
- 本地文件对象存储抽象
- Mock PaddleOCR 解析适配器（基于 fixtures）
- 财务字段标准化映射（中英文别名 → 标准码）
- 基础因子评分（质量、成长、现金流、风险、估值、综合分）
- 三个样例公司数据：贵州茅台、腾讯、Apple
- 基础测试：normalizer、scoring、API smoke

## 项目结构

```text
src/paddleocr_quant/
  api.py             FastAPI 服务
  cli.py             命令行入口
  db.py              数据库初始化
  models.py          数据模型
  parser.py          文档解析接口与 mock PaddleOCR 适配器
  normalizer.py      财务字段标准化
  scoring.py         因子评分
  repository.py      数据访问
  service.py         编排层
  storage.py         本地对象存储
  settings.py        配置
fixtures/
  seed_documents.json
  parsed/
  financials/
docs/architecture.md
tests/
```

## 快速开始

### 1. 安装依赖

```bash
cd projects/PaddleOCR-Quant
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

### 2. 初始化样例数据

```bash
paddleocr-quant seed
```

### 3. 启动 API

```bash
uvicorn paddleocr_quant.api:app --reload
```

### 4. 调用接口

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

写入样例数据：

```bash
curl -X POST http://127.0.0.1:8000/seed
```

解析样例文档：

```bash
curl -X POST http://127.0.0.1:8000/documents/600519.SH_2025_AR/parse
```

获取公司评分：

```bash
curl http://127.0.0.1:8000/companies/KWEICHOW_MOUTAI/score/2025
```

公司对比：

```bash
curl "http://127.0.0.1:8000/compare?metric=composite&report_period=2025"
```

## MVP 设计说明

### 1. 文档接入
先用 `seed_documents.json` 模拟多市场披露文档元数据，字段参考方案中的 `filing_document`。

### 2. 文档解析
当前没有直接调用真实 PaddleOCR，而是用 `MockPaddleOCRParser` 读取 `fixtures/parsed/*.json`。这样可以先把接口、数据结构和后续链路跑通。

### 3. 财务标准化
`normalizer.py` 把“营业收入 / Revenue / Net sales”等别名映射到统一标准项，例如 `REVENUE`、`OCF_NET`、`NP_PARENT`。

### 4. 因子评分
`scoring.py` 目前实现的是轻量规则版：
- 质量分：毛利率、ROE、现金流覆盖利润
- 成长分：收入增长、规模
- 现金流分：经营现金流、自由现金流
- 风险分：资产负债率、亏损惩罚
- 估值分：用简化代理分代替真实估值引擎

### 5. 为什么没有直接上 Kafka / Spark / Flink
因为这个仓库现在是 **本地 MVP**。重型组件更适合在生产化阶段接入。当前重点是先把：
- 数据模型
- 接口边界
- 解析与标准化协议
- 评分与查询流程

先稳定下来。

## 运行测试

```bash
pytest -q
```

## 已知限制

- OCR 是 mock，不是真实 PDF/扫描件解析
- 评分逻辑是规则化 MVP，不是生产级量化模型
- 还没有行情、估值、行业基准、币种换算服务
- 还没有全文检索 / 向量检索在线能力
- 还没有任务调度、消息总线、批流一体处理

## 后续路线图

### Phase 1：A 股 MVP 强化
- 接入真实公告抓取
- 接入 PaddleOCR / PP-StructureV3
- 解析三大报表与审计意见页
- 增加更多财务标准科目

### Phase 2：港股复杂 PDF
- 支持中英混合附注解析
- 阅读顺序恢复
- 文本 chunk 检索与问答

### Phase 3：美股与跨市场标准化
- 接入 SEC EDGAR
- 增加 HTML / XBRL 优先解析
- 做币种统一与跨市场对比

### Phase 4：生产化扩展
- Kafka / Pulsar 事件驱动
- MinIO / Iceberg 数据湖
- Spark / Flink 批流处理
- ClickHouse 指标分析
- Elasticsearch / pgvector / Milvus 检索层
- OpenClaw Skills 编排抓取、解析、评分、问答

## 和原始方案的关系

这份代码不是把方案里的所有基础设施一次性做完，而是把最关键的骨架先落地：

- `FilingDocument` 对应文档元数据
- `MockPaddleOCRParser` 对应文档理解接口
- `FinancialFact` 对应标准财务事实表
- `score_company()` 对应因子评分引擎
- FastAPI / CLI 对应服务层与自动化入口

它适合作为下一步继续接入真实 OCR、抓取器和量化规则的起点。
