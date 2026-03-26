# PaddleOCR-Quant

面向财报处理的本地轻量 MVP。当前版本已经把“本地文件接入 -> 文档策略检测 -> 解析/OCR 降级 -> 标准化 -> 简单检索/问答 -> 评分 -> API/CLI”串起来，保持单机可运行，不依赖 Kafka、Spark、Flink、MinIO。

## 当前已实现

- FastAPI 服务与 Typer CLI
- SQLite 本地存储
- 本地对象存储目录，用于保存原始文件和解析结果
- 本地文件接入：支持 `pdf`、`txt`、`md`、`html`
- 文件哈希计算、扩展名识别、对象存储复制
- 文档检测与解析策略选择
  - `mock-paddleocr`：继续支持现有 OCR fixtures
  - `text-heuristic`：解析 `txt/md/html`
  - `pdf-document`：先检测 PDF 文本是否可抽取，再走 text 或 OCR 路径
- OCR 适配层
  - `PaddleOCRAdapter`：仅在环境中已安装 PaddleOCR 时调用真实 OCR
  - 若 PaddleOCR 或 PDF 转图工具不可用，返回结构化 warning 和 page-level placeholder，不崩溃
- PDF rasterization service
  - 可选使用 `pdf2image`
  - 显式记录 `pdf2image` / Poppler 缺失 warning
  - 在 parse/page 结果中保留 rasterization metadata
- 可复用财务字段抽取模块
  - 支持 revenue、net profit、operating cash flow、free cash flow、gross margin、ROE、debt ratio、revenue growth
  - 支持轻量倍数/单位：`%`、`亿`、`万`、`million`、`billion`、`RMB`、`USD`
  - 返回 `canonical_code`、`source_text`、页码和解析元数据
- 文本 chunk 持久化与 SQLite 检索占位索引
- 关键词搜索与 grounded QA 模板回答
- CN/HK/US 样例 crawler skeleton
- 财务字段标准化与规则型评分
- 覆盖 inspect / parse / OCR fallback / extraction / search / QA 的测试

## OCR 状态说明

这个仓库现在已经接入“真实 OCR 的调用边界”，但不声称当前环境已经具备完整 OCR 能力：

- 如果安装了 PaddleOCR，`pdf-document` 的 OCR 路径会尝试调用它
- 如果 PDF 可抽取文本，默认优先走文本抽取路径，不强制 OCR
- 如果 PDF 不可抽取文本，会路由到 OCR adapter
- 如果 PaddleOCR、`pypdf`、`pdf2image` 或 Poppler 不可用，接口仍会返回可解析的 warning、page-level 占位结果、rasterization metadata 和降级文本

字段抽取细节见 [docs/extraction.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/extraction.md)。

Windows + NVIDIA 推荐环境、CUDA 说明、可选依赖建议见 [docs/ocr.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/ocr.md)。

## 没有实现的内容

这个仓库仍然不是原始“大数据生产方案”的完整实现，下面这些仍未落地：

- 真实生产级抓取器和调度系统
- 生产级 PaddleOCR / PP-Structure 文档理解链路
- 分布式消息队列、流处理、数据湖
- 向量检索、RAG 编排、LLM 推理服务
- XBRL、表格恢复、复杂多页版面分析
- 行情、估值、行业基准、币种统一服务
- 生产级字段抽取质量与复杂表格理解

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

检查文档推荐策略：

```bash
paddleocr-quant inspect doc-xxxxxxxxxxxx
```

显式走 OCR 路径：

```bash
paddleocr-quant parse-ocr doc-xxxxxxxxxxxx
```

直接从本地文件抽取字段：

```bash
paddleocr-quant extract-fields ./sample_report.pdf --market CN_A
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
- `GET /documents/{document_id}/inspect`
- `POST /documents/{document_id}/parse`
- `POST /documents/{document_id}/parse/ocr`
- `POST /documents/{document_id}/extract-fields`
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

## PDF / OCR 支持说明

PDF 路径现在会先做策略检测：

- 若环境中已有 `pypdf` 且文本可抽取，默认走 text extraction
- 若文本不可抽取，默认走 OCR adapter
- 若显式调用 OCR parse，则直接走 OCR adapter
- 若缺少 `pypdf`、PaddleOCR、`pdf2image` 或 Poppler，系统不会崩溃，而是返回 warning、rasterization metadata 和 placeholder page 结果

这使当前仓库在轻量环境下仍可运行，同时也为后续 Windows + NVIDIA + PaddleOCR 部署保留了真实接入点。

## 智能体部署说明

这一节是写给 **智能体 / 自动化脚本 / 运维代理** 的。目标不是讲概念，而是让智能体能够按顺序把项目完整部署起来，并在失败时知道该检查什么。

### 1. 部署目标

智能体需要完成以下结果：

1. 克隆仓库
2. 创建 Python 3.11+ 虚拟环境
3. 安装项目依赖
4. 启动 FastAPI 服务
5. 运行测试验证环境
6. 可选：安装 OCR 相关依赖，启用真实 PDF OCR 能力
7. 可选：在 Windows + NVIDIA 环境启用 PaddleOCR GPU 路径

### 2. 最小可运行部署（CPU / 轻量版）

适用于：
- macOS
- Linux
- 没有 GPU 的 Windows
- 只需要先跑通 API / CLI / 本地文本解析 / PDF 降级路径

智能体应按顺序执行：

```bash
git clone <YOUR_REPO_URL>
cd PaddleOCR-Quant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
pytest -q
uvicorn paddleocr_quant.api:app --host 0.0.0.0 --port 8000
```

如果是 Windows PowerShell：

```powershell
git clone <YOUR_REPO_URL>
cd PaddleOCR-Quant
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
pytest -q
uvicorn paddleocr_quant.api:app --host 0.0.0.0 --port 8000
```

### 3. 智能体部署成功判定

部署完成后，智能体至少要验证：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

然后再执行：

```bash
pytest -q
```

当前仓库通过标准应为全部测试通过。

### 4. 智能体推荐的部署流程

建议智能体按这个优先级处理：

#### Phase A：先跑通基础服务
1. 安装 Python 依赖
2. 跑测试
3. 启动 API
4. 调用 `/health`

#### Phase B：验证业务链路
1. 使用 CLI 或 API ingest 一个本地 `txt/md/html/pdf`
2. 调用 `/documents/{document_id}/inspect`
3. 调用 `/documents/{document_id}/parse`
4. 调用 `/documents/{document_id}/extract-fields`
5. 调用 `/documents/{document_id}/search`

#### Phase C：再启用真实 OCR
1. 安装 `pypdf`
2. 安装 `pdf2image`
3. 安装 Poppler
4. 安装 PaddleOCR / PaddlePaddle
5. 调用 `/documents/{document_id}/parse/ocr`

也就是说：**不要一上来就强依赖 GPU OCR**。先让项目可运行，再逐步打开 OCR 能力。

### 5. OCR 增强部署（CPU 或试验环境）

如果智能体要进一步启用更完整的 PDF 能力，可以追加安装：

```bash
pip install pypdf pdf2image paddleocr
```

还需要系统依赖：
- Poppler（需要 `pdftoppm` 在 PATH 中）

#### macOS
```bash
brew install poppler
```

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

#### Windows
- 安装 Poppler for Windows
- 将 `pdftoppm.exe` 所在目录加入 PATH

### 6. Windows + NVIDIA + PaddleOCR GPU 部署说明

如果智能体部署目标是 **Windows 独显机器**，建议按下面顺序执行：

1. 安装 NVIDIA 驱动
2. 安装与 PaddlePaddle 兼容的 CUDA
3. 创建 Python 3.11 虚拟环境
4. 安装 GPU 版 PaddlePaddle
5. 安装 PaddleOCR
6. 安装项目依赖
7. 安装 `pdf2image`
8. 安装 Poppler 并配置 PATH
9. 跑测试
10. 启动 API
11. 用真实 PDF 调用 `/parse/ocr`

注意：
- GPU 版 PaddlePaddle 安装命令会随 CUDA 版本变化
- 智能体**不要硬编码固定 CUDA 安装命令**，应该先读取 Paddle 官方兼容矩阵
- 如果 GPU 环境不确定，智能体应先完成 CPU 版部署，再升级 GPU

### 7. 智能体部署时的失败处理策略

#### 情况 A：`pip install -e .[dev]` 失败
检查：
- Python 是否 >= 3.11
- 虚拟环境是否激活
- pip 是否需要先升级

#### 情况 B：`uvicorn paddleocr_quant.api:app` 启动失败
检查：
- 当前目录是否是仓库根目录
- 是否已经执行 `pip install -e .[dev]`
- 是否存在端口冲突

#### 情况 C：PDF 只能走降级路径
检查：
- 是否安装 `pypdf`
- 是否安装 `pdf2image`
- 是否安装 Poppler
- `pdftoppm` 是否在 PATH 中

#### 情况 D：OCR 不工作
检查：
- 是否安装 `paddleocr`
- PaddleOCR 是否能正常 import
- 若是 GPU 环境：PaddlePaddle GPU / CUDA / cuDNN 是否匹配

### 8. 智能体可执行的部署验收脚本

智能体可按如下顺序做最小验收：

```bash
pytest -q
uvicorn paddleocr_quant.api:app --host 127.0.0.1 --port 8000 &
sleep 3
curl http://127.0.0.1:8000/health
```

如果要验收真实文档链路，可继续：

1. ingest 一个真实文件
2. inspect
3. parse
4. extract-fields
5. 如果 OCR 环境已就绪，再调用 parse/ocr

### 9. 给智能体的边界说明

智能体可以完成：
- 仓库拉取
- Python 环境创建
- 依赖安装
- 测试执行
- API 启动
- CPU 版部署
- OCR 依赖检查
- Poppler / PATH 检查
- 真实 PDF 样本验证

智能体**不应假设**以下内容已经存在：
- CUDA 一定已正确安装
- PaddleOCR 一定可直接 import
- Windows 上的 Poppler 一定已配置 PATH
- 任意 PDF 都能得到高质量字段抽取

也就是说，智能体要按“**先可运行，后增强**”的方式部署，而不是一开始就把整套 GPU OCR 当成必选前提。

## 相关文档

- API 说明：[docs/api.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/api.md)
- OCR 说明：[docs/ocr.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/ocr.md)
- 字段抽取说明：[docs/extraction.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/extraction.md)
- 路线图：[docs/roadmap.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/roadmap.md)
- 架构说明：[docs/architecture.md](/Users/seqi/.openclaw/workspace/projects/PaddleOCR-Quant/docs/architecture.md)
