# 04 技术说明：知页 LOCALFOLIO

**流程。** TXT/MD 分块（500 字符、重叠 60）→ 浏览器 Worker embedding → seekdb-js 1.4.0 upsert → refresh_index → seekdb 数据库内 ngram 全文 + cosine HNSW + RRF → 原文及出处。文档与查询都在浏览器计算；服务端明确关闭自动 embedding。内容哈希保证重复导入幂等，集合指纹隔离会话与精度，写入后统一刷新再检索。

**模型与体积。** multilingual-e5-small 固定 revision `761b726dd34fb83930e26aab4e9ac3899aa1fa78`；384 维、mean pooling、归一化、E5 前缀。FP32 ONNX 470,268,533 字节，INT8 ONNX 118,308,185 字节：权重压缩 **3.975 倍**，减小 **74.84%**；公共 tokenizer/config 另计。哈希与逐文件大小在原始报告 manifest。

**真实环境。** 2026-10-28，Windows / Edge 156 无头独立会话；Ryzen 9 7945HX（32 线程），15.69 GiB RAM，RTX 4060 Laptop；WSL2 Ubuntu 24.04、seekdb 1.4.0.0。Transformers.js 3.8.1，WASM 单线程；Node 22.20.0。数据库文件位于 WSL 原生文件系统，源码、模型及安装包在 E 盘。

**方法与最终结果。** 生产构建、本机服务，12 份公开人工示例、6 条标签查询；每配置 3 次全语料向量化、3 轮查询，以中位数计时。每个实验配置使用独立数据库集合，同模型、语料和标签。

| 配置 | 实际后端 | 分块/秒 | 查询端到端 ms | Recall@5 | nDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| FP32 / batch 1 | WASM | 16.67 | 75.75 | 0.8333 | 0.7891 |
| INT8 / batch 1 | WASM | 18.63 | 68.25 | 0.8333 | 0.7962 |
| INT8 / batch 8 | WASM | 17.47 | 68.20 | 0.8333 | 0.7962 |
| INT8 / Auto WebGPU / batch 8 | **降级 WASM** | 24.47 | 66.55 | 0.8333 | 0.7962 |

**优化取舍。** 同 batch 1 的 INT8 比 FP32 吞吐提高约 **11.8%**、查询中位数下降约 **9.9%**，该示例集质量未下降。batch 8 没有稳定收益，交互默认 batch 1。自动模式先检测 GPU，按三个固定公开句子与同精度 WASM 比较；余弦低于 0.99 或执行失败时降级。本机未校验的 GPU 实验曾降低 nDCG 至 0.5509，故不采用，也不宣称 GPU 加速；自动模式的最终吞吐差异含预热和执行顺序影响。

**口径与限制。** 模型初始化、文档向量化、写入、刷新、查询向量化、数据库检索均保留原始计时；新浏览器上下文初始化与热查询分开记录。操作系统可能已缓存权重，不将会话初始化冒充首次网络下载。表中端到端含 Worker / 本地 API 往返，不含 UI；交互另记双动画帧的查询到绘制近似值。12 文档 / 6 查询属于小样例复现，不能推断大规模质量。固定句子的数值检查也不保证全部输入质量。

**验证与复现。** 基础测试 4/4、生产构建、真实 DB 链路、Edge 全流程和 390px 布局检查通过；测试会话没有外网 HTTP 请求。详见 README；`npm test`、`npm run build`、`npm run test:db`、`npm run test:browser -- --benchmark`。最终原始数据：`results/benchmark.json`、`results/verification.json`；初始问题数据：`results/initial-webgpu-unchecked.json`。官方安装包 [seekdb 1.4.0](https://mirrors.oceanbase.com/oceanbase/community/stable/ubuntu/jammy/amd64/seekdb_1.4.0-100000212026082616ubuntu22.04_amd64.deb) SHA-256：`8b2b15ecb0d7d681105776895c2a029f8064c3476150242635515f3a355abee3`。
