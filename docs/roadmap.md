# Roadmap

## 当前仓库真实状态

这个仓库现在是一个单机、本地、轻量 MVP，已经实现：

- 本地文档接入与对象存储复制
- 文本和 fixture 解析
- PDF 解析接口与降级路径
- SQLite 持久化文档、解析结果、chunks
- 搜索和 grounded QA 占位实现
- 样例 crawler skeleton
- 财务标准化与规则型评分

## 与大数据方案的差距

以下能力仍未实现：

- 真实交易所/监管站点 crawler
- OCR 版面理解、表格恢复、多语言阅读顺序恢复
- 统一事实表、币种换算、行业映射
- 向量检索与高质量 RAG
- 多任务调度、监控、重试、审计
- Kafka / Spark / Flink / MinIO / Iceberg / ClickHouse 等基础设施

## 下一步建议

### Phase 1

- 接入真实 `pypdf` 或 PaddleOCR PDF 文本抽取
- 扩展文本解析规则与表格字段抽取
- 增加文档列表、chunk 浏览、解析状态接口

### Phase 2

- 把 CN/HK/US crawler skeleton 替换成真实数据源适配器
- 为 HTML 和 PDF 增加市场特定规则
- 引入更可靠的 chunk ranking

### Phase 3

- 加入向量索引或 SQLite FTS
- 接入真实问答模型
- 增加跨报告、跨公司检索与比较

### Phase 4

- 评估是否需要事件驱动和分布式计算
- 在有真实吞吐需求时再接入重型基础设施
