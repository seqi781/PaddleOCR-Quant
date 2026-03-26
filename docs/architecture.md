# 架构说明：本地 MVP 如何映射到大数据版方案

## 1. 当前仓库的定位

这个仓库实现的是一个**本地可运行 MVP**，目标不是一次性落地完整的大数据平台，而是先确定以下边界：

- 文档元数据模型
- 文档解析接口
- 财务标准化协议
- 因子评分接口
- API / CLI 服务入口

当前实现适合：
- 快速验证方案可行性
- 作为真实 PaddleOCR 接入前的骨架
- 作为未来微服务拆分的原型

## 2. 当前实现与大数据目标的映射

| 大数据方案层 | 目标技术 | 当前 MVP 对应实现 | 说明 |
|---|---|---|---|
| 采集与下载层 | Scrapy / Playwright / Airflow | fixtures + ingest API | 先用静态样例模拟文档接入 |
| 消息总线 | Kafka / Pulsar | 未实现 | 未来用于 `document_ingested` 等事件 |
| 原始数据湖 | MinIO / S3 / Iceberg | LocalObjectStorage | 当前仅做本地文件抽象 |
| OCR 解析层 | PaddleOCR GPU 集群 | MockPaddleOCRParser | 未来替换为真实 OCR 服务 |
| 元数据管理 | PostgreSQL | SQLite(SQLModel) | MVP 使用本地单文件数据库 |
| 标准化计算层 | Spark / Flink / Python ETL | service.py + normalizer.py + scoring.py | 当前为单机同步执行 |
| 指标分析层 | ClickHouse | API 内存排序 | 未来替换为分析型数据库 |
| 检索层 | Elasticsearch / Milvus / pgvector | TextChunk 占位模型 | 为未来向量检索预留 |
| 智能体层 | FastAPI + OpenClaw | FastAPI + CLI | 后续可被 OpenClaw Skill 调用 |

## 3. 为什么先做这种结构

因为真正的大数据系统要长期演进，如果没有清晰协议，后面越做越乱。MVP 先把最容易稳定的部分定下来：

1. **文档对象长什么样**
2. **解析结果怎么输出**
3. **财务字段怎么标准化**
4. **评分层拿什么输入、给什么输出**
5. **外部系统如何调用服务**

一旦这些边界稳定：
- 真实 OCR 可以替换 mock 解析器
- 本地 SQLite 可以升级到 PostgreSQL / ClickHouse
- 同步 API 可以升级成 Kafka 驱动异步流水线
- 本地 chunk 占位可以升级成向量数据库检索

## 4. 下一步推荐演进顺序

### 4.1 第一阶段：真实文档解析接入
- 对接 PaddleOCR / PP-StructureV3
- 新增 PDF 可提取性判断
- 区分文本型 PDF 与扫描型 PDF
- 输出页面级结构、表格、Markdown

### 4.2 第二阶段：采集模块接入
- A 股：巨潮资讯 / 上交所
- 港股：HKEXnews
- 美股：SEC EDGAR
- 文档下载后发出 `document_ingested` 事件

### 4.3 第三阶段：存储与分析升级
- 原始文件进 MinIO / S3
- 结构化事实入 PostgreSQL / ClickHouse
- 历史批量回刷用 Spark
- 增量更新和订阅提醒用 Flink

### 4.4 第四阶段：问答与智能编排
- OpenClaw Skills：抓取财报、解析财报、评估公司、筛选股票
- 向量检索：附注问答、风险段落定位
- 规则触发：新年报入库后自动重算评分

## 5. OpenClaw 在未来架构中的角色

OpenClaw 不应该替代底层数据库或计算引擎，而应该作为：

- **流程编排层**：协调采集、解析、入库、评分
- **研究问答层**：把自然语言问题转成 API / SQL / 检索动作
- **自动化触发层**：新文件入库后自动跑解析和提醒

在这个 MVP 中，FastAPI 已经提供了适合被 OpenClaw Skill 调用的服务边界。

## 6. 总结

当前代码完成的不是“大数据全栈”，而是一个可靠的起点：

- 能跑
- 能测
- 能解释
- 能继续长大

这比直接堆一堆重型基础设施更适合作为项目第一版。