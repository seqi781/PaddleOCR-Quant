# OCR 集成说明

## 当前状态

这个仓库已经实现了“真实 OCR 集成层”，但当前实现仍然是轻量、可降级的本地版本：

- 已实现 `OCRAdapter` 抽象
- 已实现 `PaddleOCRAdapter`
- 已实现独立的 PDF rasterization service
- 如果环境里安装了 PaddleOCR，代码会尝试调用真实 OCR
- 如果 PaddleOCR 不存在，返回结构化 warning 和 page-level placeholder，不会因为缺依赖而崩溃
- PDF 现在会先做策略检测：优先文本抽取，其次 OCR

这里没有宣称“当前仓库在任意机器上已经完整跑通真实 OCR”。真实 OCR 仍依赖本机安装情况。

## 已实现的行为

### 1. 文档策略检测

对于 PDF：

- 若 `pypdf` 可用且能抽出文本，推荐策略为 `text`
- 若 `pypdf` 可用但抽不出文本，推荐策略为 `ocr`
- 若无法做文本检测，也会返回 warning，并偏向 OCR 路径

可通过：

- API: `GET /documents/{document_id}/inspect`
- CLI: `paddleocr-quant inspect <document_id>`

查看推荐策略。

### 2. OCR 显式调用

可通过：

- API: `POST /documents/{document_id}/parse/ocr`
- CLI: `paddleocr-quant parse-ocr <document_id>`

强制走 OCR 路径。

### 3. 页面图像准备层

当前增加了 PDF 页面 rasterization service，但保持轻量：

- 优先尝试可选依赖 `pdf2image`
- 依赖 Poppler 的 `pdftoppm`
- 如果当前机器无法把 PDF 渲染成图片，会返回明确 warning 和 page placeholder
- page 结果和 parse 结果里都会保留 rasterization metadata

这意味着当前代码已经为“真实 OCR 需要页面图片”的链路预留了位置，但不会把重依赖变成必选安装。

### 4. 页面级 OCR 结果

解析结果中新增了 `page_results`：

- `page_number`
- `status`
- `image_path`
- `extracted_text`
- `warnings`
- `metadata`

即使 OCR 没有真正执行，也会保留 page-level placeholder，方便后续切换到真正部署环境。

### 5. OCR 文本字段抽取

当 OCR 成功返回页面文本时，系统会直接对 OCR 文本做字段抽取：

- 复用统一的 financial extraction 模块
- 尽量把 `page` 页码写回字段结果
- 返回 `canonical_code`、`source_text` 和解析元数据

这依然是启发式抽取，不是生产级表格理解，但对真实财报中的关键字段已经比旧版内嵌正则更实用。

## Windows + NVIDIA 推荐环境

如果后续要把这个项目部署到 Windows + NVIDIA 机器，建议按下面思路准备。

### 建议目标

- Windows 11
- NVIDIA GPU
- 已正确安装匹配版本的 CUDA
- 使用 Python 3.11
- 单独的虚拟环境

### 建议安装方式

1. 先安装与 PaddlePaddle / PaddleOCR 兼容的 NVIDIA 驱动
2. 安装匹配版本的 CUDA
3. 安装 GPU 版本的 PaddlePaddle
4. 再安装 PaddleOCR

建议优先参考 PaddlePaddle 与 PaddleOCR 官方兼容矩阵，不要凭经验随意混装 CUDA、cuDNN、Paddle 版本。

## PaddleOCR / CUDA 注意事项

### 1. 版本匹配最重要

PaddleOCR 是否可用，关键不只是 `pip install paddleocr`，更在于：

- `paddlepaddle-gpu` 版本
- CUDA 版本
- cuDNN 版本
- Python 版本

这些需要相互兼容。

### 2. 当前仓库不强制这些依赖

本仓库故意没有把 PaddleOCR、PaddlePaddle、CUDA 相关包加入必选依赖，因为：

- 当前开发机不一定具备 GPU 环境
- CI / 本地测试需要保持轻量
- 文档策略检测、文本解析、mock parser 仍然应该在无 OCR 环境中可运行

### 3. 实际上线前建议补齐

如果要把 OCR 真的用于财报解析，后续建议继续补齐：

- 更稳定的 PDF 转图方案
- OCR 初始化参数配置
- 中英文 / 多语种模型切换
- 表格与版面结构恢复
- GPU/CPU 模式选择
- 批量页处理与失败重试

## 本地回退行为

当前环境里如果缺少依赖，行为如下：

- 缺少 `pypdf`
  - 无法判断 PDF 是否可抽取文本，会返回 warning
- 缺少 `pdf2image` 或 Poppler
  - 无法生成页面图片，会返回明确 warning、rasterization metadata 和 placeholder page
- 缺少 PaddleOCR
  - 无法执行真实 OCR，会返回 warning 和 `unavailable` 状态的 page result

无论哪种情况，API / CLI 都尽量返回结构化结果，而不是直接抛异常中断整个链路。

## 当前还没实现的部分

下面这些仍然没有完成：

- 真正稳定的 Windows GPU 部署脚本
- PaddleOCR 参数与模型配置管理
- PP-Structure、表格恢复、版面分析
- 复杂多页财报的高质量字段抽取
- OCR 结果清洗、去重、纠错、后处理

当前版本的定位是：先把“真实 OCR 的接入边界”和“轻量环境中的降级行为”做正确，而不是假装已经拥有完整生产能力。
