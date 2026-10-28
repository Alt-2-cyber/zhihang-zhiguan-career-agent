# 职航智管本地 AI 运行时与多模型 Agent 设计

## 1. 目标

在现有 React、FastAPI、PostgreSQL 架构上交付一套由项目自行编排的 Agent 运行时：智谱免费模型作为主模型，DeepSeek 作为备用模型，本地规则 Agent 作为最终兜底；BGE-M3、PaddleOCR、FunASR 和 MeloTTS 通过 Docker 独立服务提供本地能力。

交付必须满足以下目标：

- 保留现有学生与辅导员业务接口和人工确认机制。
- 让画像、计划、岗位匹配、简历优化、模拟面试和周复盘使用真实大模型推理。
- 所有 PDF 简历强制使用 PaddleOCR 识别，再由 BGE-M3 向量化。
- 使用 PostgreSQL + pgvector 保存岗位、简历和知识片段向量。
- 支持浏览器录音、FunASR 转写、用户修正、Agent 评分和 MeloTTS 播放追问。
- 适配 RTX 3050 6GB 显存，不让多个本地模型争抢 GPU。
- 在线模型或本地模型异常时保持业务可解释地降级，不伪装模型来源。

## 2. 非目标

本阶段不实现以下内容：

- 本地部署大语言模型。
- 实时双向流式语音通话。
- 声纹克隆、GPT-SoVITS 训练或数字人。
- Kubernetes、Kafka 或独立向量数据库。
- 让浏览器直接访问模型服务。
- 自动将未经用户确认的 AI 结果写入正式画像、计划或简历版本。

## 3. 运行环境约束

目标机器为 Windows、WSL2、Docker Desktop 和 NVIDIA Runtime，GPU 为 RTX 3050 6GB。Windows 图形进程会占用部分显存，因此不能假设容器可使用完整 6GB。

现有业务后端继续使用 Python 3.13。本地 AI 服务使用独立 Python 3.10 或 3.11 镜像，隔离 PyTorch、PaddlePaddle、FunASR 和 MeloTTS 的版本约束。

默认资源分配：

| 服务 | 默认设备 | 说明 |
| --- | --- | --- |
| BGE-M3 | CPU | 查询量低，稳定优先，允许通过环境变量切换 CUDA |
| PaddleOCR | CPU | 所有 PDF 异步识别，避免占用语音显存 |
| FunASR | CUDA | 非流式单任务推理，语音服务内串行执行 |
| MeloTTS | CPU | 与 FunASR 共用语音服务但不并行执行 |
| 智谱、DeepSeek | 远程 API | 本机不加载大语言模型权重 |

## 4. 总体架构

```text
Browser
  |
Nginx / React
  |
FastAPI
  |-- Agent Orchestrator
  |     |-- Zhipu glm-4-flash
  |     |-- DeepSeek deepseek-v4-flash
  |     `-- LocalAgentGateway
  |-- PostgreSQL-backed AI task queue
  `-- AI Worker
          |-- Embedding service: BGE-M3 / CPU
          |-- OCR service: PaddleOCR / CPU
          `-- Speech service
                 |-- FunASR / CUDA
                 `-- MeloTTS / CPU
  |
PostgreSQL 17 + pgvector
```

服务边界：

- `backend` 负责认证、RBAC、Agent 编排、业务事务和任务状态。
- `worker` 使用与后端相同的业务代码，但作为独立进程领取异步 AI 任务。
- `embedding` 只接受文本并返回归一化的 1024 维向量。
- `ocr` 只接受内部文件请求并返回按页组织的文本、置信度和诊断信息。
- `speech` 串行执行音频转写和语音合成，防止同一容器内并行占用资源。
- 模型服务只加入 Compose 内部网络，不映射宿主机端口。
- 前端只访问 `/api`，不持有任何模型密钥。

## 5. 自研 Agent 与故障转移

新增通用 OpenAI 兼容模型客户端和故障转移网关。Agent 的路由、提示词、业务工具、上下文选择、结构化契约和确认流程均由项目后端维护，模型 API 只承担推理。

默认顺序：

1. 智谱 `glm-4-flash`。
2. DeepSeek `deepseek-v4-flash`。
3. 现有 `LocalAgentGateway`。

每个专业能力继续实现现有 `AgentGateway` 契约：

- `analyze_profile`
- `build_plan`
- `match_job`
- `optimize_resume`
- `start_interview`
- `evaluate_answer`
- `build_weekly_review`

在线模型请求使用非流式 Chat Completions 和 JSON 输出。系统提示词必须包含完整输出字段、证据约束、禁止虚构要求和用户确认要求。返回内容先经过对应 Pydantic 模型校验。

发生以下情况时切换提供方：

- 连接失败或读取超时。
- HTTP 429 或 5xx。
- 认证、余额、模型不可用等 API 错误。
- 返回内容缺字段、无法解析 JSON 或违反 Pydantic 契约。

超时、429 和 5xx 在当前提供方最多重试一次；认证或参数错误不重试。连续失败三次后该提供方熔断 60 秒。单次业务调用必须有总时间预算，超过预算直接进入下一提供方。

每次结果记录实际 `provider`、模型名、是否发生故障转移、耗时和脱敏后的错误分类。日志不记录提示词全文、简历正文或 API Key。

## 6. 外部模型隐私处理

发送到智谱或 DeepSeek 前，对文本执行确定性脱敏：

- 中国大陆手机号替换为 `[PHONE]`。
- 邮箱替换为 `[EMAIL]`。
- 身份证号替换为 `[ID_CARD]`。
- 能识别的住址、学号等字段在结构化输入阶段替换为对应占位符。

原始文件和未脱敏文本仅保存在本地受控存储中。模型输出不得恢复或猜测被脱敏的信息。

## 7. PostgreSQL 任务队列

不新增 Redis。新增 `ai_tasks` 表并使用 PostgreSQL 行锁实现持久任务队列。

核心字段：

- `id`
- `task_type`: `resume_ocr`、`document_embedding`、`speech_transcription`、`speech_synthesis`
- `owner_id`
- `status`: `queued`、`running`、`succeeded`、`failed`、`cancelled`
- `input_json`
- `result_json`
- `error_code`
- `attempt_count`
- `available_at`
- `lease_expires_at`
- `heartbeat_at`
- `created_at`、`updated_at`、`completed_at`

Worker 使用 `SELECT ... FOR UPDATE SKIP LOCKED` 领取任务。任务运行期间更新心跳；租约过期后允许重新领取。每项任务最多执行三次，使用递增等待。错误信息必须为可展示的错误码和脱敏摘要。

## 8. PDF OCR 与简历处理

所有 PDF 都强制进入异步 OCR，不再使用 PDF 内嵌文本作为正式解析结果。

流程：

1. 后端验证文件扩展名、MIME、大小和所有权，将文件写入受控目录。
2. `ResumeFile.parse_status` 设为 `queued`，创建 `resume_ocr` 任务并立即返回。
3. Worker 将文件交给 OCR 服务。
4. OCR 服务逐页渲染并调用 PaddleOCR，返回页码、文本、置信度和识别警告。
5. Worker 保存合并文本，更新状态为 `embedding`，再创建向量化任务。
6. 文本切片向 BGE-M3 编码并写入 pgvector。
7. 全部成功后状态变为 `parsed`；失败时保留可重试状态和错误码。

DOCX 继续使用 `python-docx` 解析，之后进入相同向量化流程。

OCR 默认使用 PaddleOCR PP-OCRv5 Mobile 中文模型和国内下载源。模型文件写入持久缓存卷，容器重启不重复下载。

## 9. BGE-M3 与 pgvector

PostgreSQL 镜像切换为兼容 PostgreSQL 17 的 pgvector 镜像。Alembic 迁移创建 `vector` 扩展并新增 `document_chunks` 表。

核心字段：

- `source_type`: `resume`、`job`、`policy`、`interview_question`
- `source_id`
- `owner_id`，公共数据允许为空
- `chunk_index`
- `content`
- `content_hash`
- `embedding vector(1024)`
- `metadata_json`
- 时间戳

BGE-M3 输出归一化稠密向量。检索使用余弦距离，并严格按数据所有权和班级权限过滤。

岗位匹配采用两阶段流程：

1. pgvector 召回相似岗位或相关证据片段。
2. Agent 根据画像、岗位原文和召回证据生成五维评分。

向量只是召回信号，不直接作为录用概率，也不替代现有五维业务契约。

## 10. 语音面试

语音面试采用点击录音、停止后上传的非流式流程。

1. 浏览器通过 `MediaRecorder` 录制 `WebM/Opus`。
2. 后端验证文件类型、时长、大小和会话所有权，创建转写任务。
3. Speech 服务使用 FFmpeg 转换为 16kHz 单声道 WAV。
4. FunASR 默认使用 ModelScope 的 `paraformer-zh` 中文非流式模型完成转写。
5. 前端显示转写文本，学生可以编辑识别错误。
6. 只有学生确认后的文字才进入 `evaluate_answer`。
7. Agent 返回追问后创建 TTS 任务。
8. MeloTTS 生成中文音频，前端提供播放、暂停和重播。

Speech 服务内部使用进程级互斥锁，ASR 和 TTS 不并行。FunASR 使用 CUDA，MeloTTS 默认使用 CPU。设备选择可配置，但 6GB 配置不允许两个任务同时使用 GPU。

原始录音和生成语音使用随机存储名。下载接口校验用户和面试会话所有权。原始录音默认七天过期，由定时清理任务删除；转写文本和面试评分按业务记录保留。

## 11. API 设计

新增或调整以下接口：

- `GET /api/ai/tasks/{task_id}`：查询本人任务状态。
- `POST /api/ai/tasks/{task_id}/retry`：重试本人可重试的失败任务。
- `GET /api/system/capabilities`：返回各能力是否可用、当前降级状态和模型来源，不返回密钥。
- `GET /api/jobs/recommended`：基于已确认画像的向量召回结果。
- `POST /api/interviews/{session_id}/transcriptions`：上传录音并创建 ASR 任务。
- `POST /api/interviews/{session_id}/answers`：继续接收用户确认后的文字答案。
- `GET /api/media/{artifact_id}`：鉴权后读取录音或 TTS 音频。

现有简历上传接口保持路径不变，但 PDF 上传后的 `parse_status` 为异步状态，并在响应中返回 `task_id`。前端继续轮询简历列表或任务接口。

## 12. 前端交互

简历页面显示以下稳定状态：

- 排队中
- OCR 识别中
- 向量化中
- 已完成
- 失败，可重试

模拟面试页面增加：

- 录音、停止和重新录制按钮。
- 录音时长与麦克风权限错误。
- 转写进度。
- 可编辑的转写确认区。
- 提交文字答案按钮。
- 追问音频的播放、暂停和重播控制。
- 当前回答实际使用的模型来源。

文本输入始终保留，麦克风不可用或 ASR 失败时不阻断面试。

## 13. 健康检查与可观测性

每个模型服务提供 `/health/live` 和 `/health/ready`：

- `live` 只检查进程。
- `ready` 检查模型权重是否可用、依赖是否加载和设备是否满足配置。

后端能力接口聚合数据库、任务 Worker、Embedding、OCR、Speech、智谱和 DeepSeek 状态。外部模型只做低频、无敏感数据的可用性探测，避免消耗免费额度。

记录以下指标：

- 任务排队时长和执行时长。
- OCR 页数与平均置信度。
- 向量编码与检索耗时。
- ASR 音频时长和实时率。
- TTS 字符数和生成耗时。
- 模型提供方成功、重试、故障转移和本地降级次数。

## 14. Docker 与配置

Compose 新增 `worker`、`embedding`、`ocr` 和 `speech` 服务，并增加模型缓存卷。只有 `speech` 申请 NVIDIA GPU。

配置项使用以下命名，不在仓库保存真实值：

```text
AGENT_PROVIDER=failover
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_API_KEY=
ZHIPU_MODEL=glm-4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-flash
AGENT_TIMEOUT_SECONDS=60

EMBEDDING_SERVICE_URL=http://embedding:8101
OCR_SERVICE_URL=http://ocr:8102
SPEECH_SERVICE_URL=http://speech:8103
MODEL_CACHE_DIR=/models
MODELSCOPE_CACHE=/models/modelscope
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
OCR_MODEL_VERSION=PP-OCRv5
OCR_LANG=ch
ASR_MODEL=paraformer-zh
ASR_DEVICE=cuda
TTS_LANGUAGE=ZH
TTS_DEVICE=cpu
AUDIO_RETENTION_DAYS=7
```

本机 `.env` 保存用户提供的密钥且已被 `.gitignore` 排除。启动脚本只检查变量是否存在，不打印变量值。

## 15. 数据库迁移与兼容性

迁移必须在现有数据卷上执行，不允许删除卷或重新初始化数据库。步骤为：

1. 备份 PostgreSQL。
2. 将数据库镜像切换为 pgvector 兼容镜像。
3. 启用 `vector` 扩展。
4. 创建任务、文档片段和媒体文件元数据表。
5. 为现有六个演示岗位创建向量化任务。
6. 保留现有用户、画像、计划、投递、风险和帮扶记录。

## 16. 测试策略

遵循测试驱动开发，每项行为先建立失败测试。

单元测试覆盖：

- 智谱成功路径。
- 智谱异常后 DeepSeek 接管。
- 两个在线模型异常后本地规则降级。
- Pydantic 输出校验失败触发故障转移。
- 手机、邮箱和身份证脱敏。
- 任务领取、租约、心跳、重试和过期恢复。
- PDF 强制 OCR，DOCX 不调用 OCR。
- 音频所有权和七天过期策略。

集成测试覆盖：

- pgvector 扩展、1024 维向量写入和余弦召回。
- OCR、Embedding 和 Speech 的 HTTP 契约。
- Worker 从排队到成功或失败的完整状态变化。
- 简历 OCR 后自动向量化。
- ASR 转写确认后提交面试评分。
- TTS 音频只能由会话本人读取。

浏览器测试覆盖：

- PDF 上传后的异步状态。
- 麦克风权限拒绝时仍可文字回答。
- 录音、停止、转写编辑、确认和提交。
- 追问音频播放控制。
- 智谱、DeepSeek 和本地降级来源标识。

实机验收覆盖：

- Docker NVIDIA Runtime 可见 RTX 3050。
- Speech 服务完成一段中文音频的转写和合成。
- 推理期间不发生 CUDA OOM。
- 模型缓存卷在容器重启后复用。
- 智谱真实请求成功，或明确识别免费模型不可用并切换 DeepSeek。
- DeepSeek 真实备用请求成功。
- 三个模型路径均不在日志中泄露密钥或简历正文。
- 原有后端、前端、E2E 和 Docker 健康检查全部通过。

## 17. 验收标准

满足以下条件才视为交付：

1. `docker compose up --build -d` 能启动数据库、后端、前端、Worker 和三个本地 AI 服务。
2. 所有服务达到预期健康状态；模型首次下载期间显示 `starting`。
3. PDF 简历完成强制 OCR 和向量化，任务状态可见且可重试。
4. 岗位推荐使用 pgvector 召回，五维匹配仍由结构化 Agent 输出。
5. 浏览器完成一次录音、转写编辑、文字确认、Agent 评分和追问播放。
6. 智谱、DeepSeek、本地规则三级路径均有自动化测试和实际来源标记。
7. RTX 3050 6GB 实测不发生显存不足。
8. 真实 API Key 仅存在本机 `.env`，Git 差异和 Docker 镜像历史中没有密钥。
9. 数据库迁移保留已有业务数据。
10. 自动化测试、静态检查、生产构建和浏览器测试全部通过。

## 18. 模拟面试摄像头情绪分析

模拟面试允许学生主动开启摄像头。浏览器端每 1 秒将当前视频画面缩放到最长边 640 像素并编码为 JPEG，调用后端 `POST /api/interviews/{session_id}/emotion/analyze`。请求使用单飞锁，上一帧未完成时不会并发堆积；后端校验会话归属、会话状态、媒体类型和 4 MB 大小上限，再将帧转发到独立的 `emotion` 服务。

情绪服务使用两阶段本地推理：YOLO 人脸模型负责定位人脸、返回归一化 `face_boxes` 标注框和统计人脸数量；`trpakov/vit-face-expression` 本地 ViT 模型在最大人脸裁剪图上分类表情。CUDA 可用时使用 GPU，否则自动切换 CPU。健康检查会在模型加载完成后返回 `ready=true`，模型首次启动从国内镜像下载并写入 `emotion_models` 卷。前端将每个标注框叠加到视频预览上，同时显示检测置信度。

每场面试最多保留 20 条观测统计，不保存原始视频帧。回答提交时，后端将当前样本聚合为表达稳定度：人脸出现率占 50%，主表情标签一致性占 30%，单帧表达置信度波动占 20%。没有清晰人脸时返回 `stability_score=null`，该维度从评分和报告中省略，不使用默认分数填充。

该指标是面试表达训练信号，不是心理状态诊断，也不参与录用决策。用户拒绝摄像头权限、关闭摄像头或情绪服务不可用时，文字回答、录音转写、AI 出题和原有回答评分继续可用。
