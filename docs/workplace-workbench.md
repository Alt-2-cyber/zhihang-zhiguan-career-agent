# 入职后职场训练工作台

## 设计边界

“模拟面试”只处理入职前的求职准备：岗位上下文、AI 动态出题、语音回答、追问和面试量表评分。

“职场训练”只处理入职后的工作适应：从工作简报读取任务，到形成真实交付物、提交评审、复盘改进。它不再渲染数字人面试官，也不把工作交付物伪装成面试回答。

## 入职后闭环

1. 场景通过 `work_context_json` 保存岗位、阶段、目标、协作对象、交付物、截止时间、验收标准、约束和推荐工作流。
2. 学生启动场景后，后端创建 `SimulationSession`，所有权校验沿用学生资源隔离规则。
3. 学生选择交付类型，可手写、保存草案，或调用 `generate_workplace_deliverable` Agent 生成基于简报的草案。
4. 草案写入 `WorkplaceDeliverable`。同一交付类型提交后再次编辑会创建新 revision，不覆盖历史版本。
5. 提交时后端按 `workplace-v1` 量表生成目标理解、行动可执行、风险意识、协作对齐、交付质量和证据质量，并将评审结果写入数据库。
6. 至少提交一份交付物后才能完成会话；完成时生成只基于已提交交付物的复盘报告。

## API

| API | 作用 |
| --- | --- |
| `GET /api/workplace/scenarios?phase=post_hire` | 只返回入职后场景 |
| `GET /api/workplace/sessions?phase=post_hire` | 只返回入职后会话 |
| `GET /api/workplace/sessions/{id}/brief` | 返回真实工作简报 |
| `GET /api/workplace/sessions/{id}/deliverables` | 返回交付物版本和评审历史 |
| `POST /api/workplace/sessions/{id}/deliverables` | 保存草案 |
| `POST /api/workplace/sessions/{id}/deliverables/submit` | 提交并生成结构化评审 |
| `POST /api/workplace/sessions/{id}/workplace-assist` | 调用主 Agent 生成工作交付草案并保存为草案 |
| `POST /api/workplace/sessions/{id}/controls` | 暂停、恢复和完成工作复盘 |

高风险的外部投递、删除和批量修改不在职场训练中自动执行。AI 只能生成工作草案，学生仍需核对事实并主动提交。

## 数据与故障转移

结构化 Agent 走智谱、DeepSeek、配置的本地规则三级链路；在线模型输出必须通过 `WorkplaceDeliverableGeneration` 契约校验。在线模型不可用时，本地规则只使用场景中已保存的工作简报字段，不会编造企业、日期、指标或完成状态。

