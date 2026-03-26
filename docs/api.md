# API

## Health

`GET /health`

返回服务状态和当前环境。

## Ingest Document

`POST /documents`

支持两种输入模式：

- fixture 模式：传 `source_fixture`
- 本地文件模式：传 `source_path`

本地文件模式示例：

```json
{
  "company_code": "AAPL",
  "company_name": "Apple",
  "market": "US",
  "fiscal_year": 2025,
  "report_type": "annual_report",
  "language": "en-US",
  "source_path": "/absolute/path/to/report.md",
  "source_fixture": null
}
```

返回字段包括：

- `document_id`
- `source_type`
- `file_hash`
- `stored_path`
- `detected_extension`
- `mime_type`

## Parse Document

`POST /documents/{document_id}/parse`

解析器选择逻辑：

- fixture 文档 -> `mock-paddleocr`
- `.txt` / `.md` / `.html` -> `text-heuristic`
- `.pdf` -> `pdf-fallback`

返回字段包括：

- `parser_name`
- `extracted_text`
- `extracted_fields`
- `chunks`
- `warnings`

## Search

`GET /documents/{document_id}/search?q=revenue&limit=5`

行为：

- 在 SQLite 中读取持久化 chunks
- 使用简单关键词匹配打分
- 返回命中 chunk 与 `score`

## QA

`POST /documents/{document_id}/qa`

请求：

```json
{
  "question": "What does the report say about revenue?",
  "top_k": 3
}
```

行为：

- 从问题中提取轻量查询词
- 召回 top chunks
- 返回 grounded 模板回答
- 附带 citations

说明：这不是 LLM 驱动的自由问答，而是本地 MVP 的可解释占位实现。

## Sample Filings

`GET /filings/sample?market=US&ticker=AAPL`

返回 CN / HK / US 的样例 crawler 输出，当前为 stub/fixture 级别接口。

## Scoring

`POST /scores/company`

```json
{
  "company_code": "AAPL",
  "fiscal_year": 2023
}
```

`POST /scores/compare`

```json
{
  "company_codes": ["600519.SH", "0700.HK", "AAPL"],
  "fiscal_year": 2023
}
```
