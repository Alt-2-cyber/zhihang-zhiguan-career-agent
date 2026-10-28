from pathlib import Path
import shutil
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Cm, Pt, RGBColor

from build_competition_docs import (
    ASSETS, PROJECT, OUTPUT, NAME, PURPLE, LIGHT_PURPLE, DARK, GRAY, ORANGE,
    add_header_footer, add_p, add_bullets, add_image, heading, table, page_break,
    prepare_assets,
)

DETAILED_DOCX = OUTPUT / "职航智管求职训练与职业成长服务系统_作品介绍_详细版.docx"
DETAILED_MD = OUTPUT / "职航智管求职训练与职业成长服务系统_作品介绍_详细版.md"


def build_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    add_header_footer(doc)
    for style_name in ["Normal", "Title", "Heading 1", "Heading 2", "List Bullet"]:
        if style_name not in doc.styles:
            doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
    doc.styles["Normal"].font.name = "等线"
    doc.styles["Normal"].font.size = Pt(10.5)

    add_p(doc, "职航智管", size=32, bold=True, color=PURPLE, before=55, after=4, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p(doc, "求职训练与职业成长服务系统", size=21, bold=True, color=DARK, after=12, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p(doc, "比赛项目介绍详细版", size=16, bold=True, color=GRAY, after=18, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p(doc, "技术创新 30%｜场景落地 30%｜开源治理 20%｜长期发展 20%", size=10.5, color=PURPLE, after=18, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_image(doc, ASSETS / "agent_assistant.png", width_cm=16.4, caption="图 1  就业助手与 Agent 执行过程（脱敏演示界面）")
    add_p(doc, "版本 V1.0  |  编制日期 2026-10-25", size=10, color=GRAY, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p(doc, "代码仓库：【提交前填写】  |  演示视频：【提交前填写】", size=10, color=ORANGE, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    page_break(doc)

    heading(doc, "一 执行摘要", 1)
    add_p(doc, "职航智管是一套面向高校毕业生和就业辅导人员的 Web 求职训练与职业成长服务系统。它把学生的求职事实、任务进展、岗位要求和训练反馈组织成连续上下文，让学生知道下一步要做什么，让辅导员知道风险依据在哪里，也让系统保留每次建议、确认和执行的过程记录。", size=11, after=8, line=1.25)
    table(doc, ["对象", "核心问题", "系统回答"], [
        ["学生", "目标不清、材料分散、计划难坚持、反馈不能沉淀", "画像、四周计划、岗位匹配、简历、面试、投递、学习和入职训练"],
        ["辅导员", "进展依赖人工收集，风险缺少解释，帮扶难闭环", "班级驾驶舱、风险事实、学生进展、帮扶任务、就业质量"],
        ["学校/项目管理", "缺少过程数据、权限边界和可复核记录", "审计日志、来源记录、版本化量表、任务与反馈留痕"],
    ], widths=[3.0, 7.0, 7.2], font_size=9.2)
    add_p(doc, "项目原则", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "事实先于建议：模型只能基于已授权的业务事实、来源片段或明确标注的建议开展分析。",
        "人保留决定权：学生确认画像、计划和简历建议；辅导员确认风险和帮扶结果；高风险动作需要二次确认。",
        "过程可追溯：会话、工具、输入输出、错误、时间、耗时和业务状态都能形成记录。",
        "边界可解释：演示数据、实测结果、配置数量和未验证能力在材料中分开标注。",
    ])
    page_break(doc)

    heading(doc, "二 比赛评审维度与证据映射", 1)
    add_p(doc, "比赛页面给出的评分结构是：技术创新 30%、场景落地 30%、开源治理 20%、长期发展 20%。本项目文档按照这四条主线组织，而不是单纯按页面功能罗列。", size=11, after=8, line=1.25)
    table(doc, ["维度", "评审问题", "项目证据", "文档页"], [
        ["技术创新 30%", "是否解决清晰问题，是否有可解释的技术设计？", "证据驱动、多 Agent 编排、工具契约、风险分层、持久会话", "第 4–7 页"],
        ["场景落地 30%", "是否能部署、运行、测试，需求是否真实？", "学生、辅导员、面试、职场训练、帮扶闭环和浏览器检查", "第 8–12 页"],
        ["开源治理 20%", "代码、依赖、文档和协作治理是否清楚？", "README、Compose、环境模板、迁移、测试、Issue/PR 计划", "第 14–16 页"],
        ["长期发展 20%", "团队是否有持续维护和运营计划？", "试点、运营、扩展路线，数据保留、监控和版本治理", "第 17–19 页"],
    ], widths=[3.0, 6.4, 7.2, 2.6], font_size=8.8)
    add_image(doc, ASSETS / "test_results.png", width_cm=16.0, caption="图 2  当前验证结果；通过项和未通过项均按日志如实记录")
    add_p(doc, "提交状态", size=12, bold=True, color=PURPLE, before=8, after=4)
    add_bullets(doc, [
        "作品介绍 PDF、可编辑 DOCX 和 Markdown 源文档已生成。",
        "代码仓库公开地址、演示视频公开链接和评审账号仍需项目方补填。",
        "当前工作区未配置公开 Git remote，材料没有把本地路径写成公开仓库。",
    ])
    page_break(doc)

    heading(doc, "三 产品边界与用户旅程", 1)
    add_image(doc, ASSETS / "architecture.png", width_cm=16.0, caption="图 3  从用户工作区到 Agent、业务服务和数据层的系统架构")
    table(doc, ["阶段", "学生端", "辅导员端", "系统沉淀"], [
        ["建档", "上传材料、填写目标、确认画像", "查看授权范围内的画像状态", "能力证据、约束和确认版本"],
        ["求职准备", "生成计划、匹配岗位、改简历", "查看学生任务进展", "任务、岗位要求、引用片段"],
        ["训练", "面试、学习、职场情景交付", "查看风险和帮扶反馈", "评分、草案、交付、复盘"],
        ["投递/入职", "更新申请、回访和评价", "查看班级质量和帮助结果", "阶段事件、回访、审计记录"],
    ], widths=[2.6, 5.0, 5.0, 5.0], font_size=8.9)
    add_p(doc, "不负责的事情", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "不自动代替学生向外部招聘平台投递。",
        "不把模型生成内容直接当成真实经历、录用结果或心理判断。",
        "不将摄像头表达稳定度用于录用、处分或心理诊断。",
        "不将演示库中的申请记录、评分和风险数当作真实就业统计。",
    ])
    page_break(doc)

    heading(doc, "四 技术创新一：证据驱动的多 Agent 协作", 1)
    add_image(doc, ASSETS / "agent_flow.png", width_cm=16.0, caption="图 4  Agent 运行流程：从问题到授权工具和业务状态")
    add_p(doc, "系统采用主 Agent 与专业 Agent 的分工。主 Agent 识别意图、拆解步骤、设置依赖关系；职业规划、岗位、简历、投递、面试、学习、职场和辅导员等专业 Agent 各自承担有限职责。专业 Agent 通过注册工具读取业务事实或形成动作提案，不能直接修改数据库。", size=10.8, after=7, line=1.2)
    table(doc, ["层次", "职责", "可审计结果"], [
        ["会话网关", "读取角色、会话、上下文资源和最近消息", "会话 ID、用户消息、上下文引用"],
        ["主 Agent", "识别意图、拆步骤、选择专业 Agent", "计划步骤、依赖关系、运行状态"],
        ["专业 Agent", "处理单一领域的证据和结论", "分析结论、引用、建议动作"],
        ["工具层", "按角色、资源、参数和风险执行", "工具版本、参数、结果、错误和耗时"],
        ["业务层", "保存事实和状态，执行事务边界", "申请事件、计划任务、审计日志"],
    ], widths=[3.0, 8.2, 6.4], font_size=8.8)
    add_p(doc, "本次回放证据", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "一条综合求职问题完成 2 个专业 Agent 步骤和 4 次只读工具调用。",
        "运行状态为 completed，工具状态均为 succeeded；刷新后用户消息数量保持一致。",
        "工具详情展示脱敏参数、返回值、引用、风险级别和耗时。",
    ])
    page_break(doc)

    heading(doc, "五 技术创新二：工具目录与风险控制", 1)
    add_image(doc, ASSETS / "tool_inventory.png", width_cm=15.0, caption="图 5  工具目录风险分层：只读 20、普通写 9、高风险拒绝入口 3")
    table(doc, ["校验点", "校验内容", "失败处理"], [
        ["身份", "当前角色是否允许该工具", "返回工具禁止，不继续执行"],
        ["资源归属", "学生、简历、申请或计划是否属于当前主体/授权范围", "返回资源不可用，不泄露其他对象"],
        ["参数契约", "输入是否符合 Pydantic schema", "返回参数无效，保留错误码"],
        ["风险等级", "只读、普通写、高风险动作是否需要确认", "生成动作提案、拒绝或要求二次确认"],
        ["输出契约", "工具返回是否符合结构化输出模型", "阻止不符合契约的结果进入回答"],
    ], widths=[3.0, 8.7, 5.9], font_size=8.8)
    add_p(doc, "核心设计决策", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "模型可以规划，但不能扩大工具权限。",
        "普通写操作也经过后端事务和审计；高风险动作不提供静默执行路径。",
        "错误记录保留真实失败原因，系统不会用成功文案覆盖失败状态。",
    ])
    page_break(doc)

    heading(doc, "六 技术创新三：多模态能力与工作后延伸", 1)
    add_image(doc, ASSETS / "interview.png", width_cm=8.0, caption="图 6  模拟面试场次报告")
    add_image(doc, ASSETS / "training.png", width_cm=8.0, caption="图 7  入职后职场工作台")
    table(doc, ["能力", "输入", "结构化输出", "边界"], [
        ["简历解析", "PDF/DOCX 文本", "解析状态、原文片段、画像草稿", "解析失败时提示手工录入"],
        ["面试训练", "岗位、简历、回答", "问题、追问、四维评分、场次报告", "评分仅作训练反馈"],
        ["语音/视觉", "授权音频或摄像头帧", "转写、朗读、表达稳定度参考", "原始视频不落库，不做录用判断"],
        ["职场训练", "工作简报、目标、验收标准", "交付草案、结构化评审、复盘", "AI 不能替学生提交外部工作结果"],
    ], widths=[3.0, 5.1, 5.4, 4.1], font_size=8.6)
    add_p(doc, "该设计把“求职前的表达训练”和“入职后的工作适应”分成两套流程，分别使用不同的数据模型、量表和操作边界。", size=10.5, color=GRAY, after=0)
    page_break(doc)

    heading(doc, "七 场景落地一：学生端完整链路", 1)
    add_image(doc, ASSETS / "student_dashboard_masked.png", width_cm=16.2, caption="图 8  学生工作台：目标、任务、投递漏斗和帮扶反馈")
    table(doc, ["用户动作", "系统处理", "验收标准"], [
        ["输入材料", "保存简历/文本，记录解析状态", "用户能看到成功、失败或手工录入提示"],
        ["确认画像", "展示能力、缺口、约束和证据", "未确认草稿不写入正式档案"],
        ["生成计划", "按目标岗位拆分四周任务", "每项任务有截止日期和验收标准"],
        ["岗位匹配", "五维比较，引用画像和岗位片段", "分数与证据同时展示"],
        ["面试复盘", "保存回答、评分、追问和报告", "单轮和场次结果区分口径"],
        ["每周复盘", "读取申请事件，生成优先行动", "建议回到真实任务和记录"],
    ], widths=[3.4, 8.1, 6.1], font_size=8.7)
    add_p(doc, "示例中的 3 条申请记录、4 项任务和匹配分来自人工构造演示库；该页面用于展示流程，不代表真实学生结果。", size=9.2, color=GRAY, after=0)
    page_break(doc)

    heading(doc, "八 场景落地二：辅导员端帮扶闭环", 1)
    add_image(doc, ASSETS / "counselor_dashboard.png", width_cm=16.2, caption="图 9  辅导员班级概览：风险事实与进展")
    table(doc, ["步骤", "辅导员看到什么", "决策边界"], [
        ["班级概览", "学生数、申请数、风险事件和分布", "数据必须有时间和样本口径"],
        ["查看事实", "无投递、任务逾期、缺少面试反馈等触发原因", "风险规则只提供线索"],
        ["布置任务", "任务标题、要求、截止时间和期望结果", "不自动处分或限制学生资源"],
        ["接收反馈", "学生反馈和相关证据", "可要求补充，不能直接把建议当事实"],
        ["确认完成", "验收状态和审计留痕", "完成由辅导员人工确认"],
    ], widths=[3.0, 8.4, 6.2], font_size=8.8)
    add_p(doc, "补充验证已完成学生反馈到辅导员验收的真实浏览器操作；移动端视口 390×844 也检查了无横向溢出。", size=9.2, color=GRAY, after=0)
    page_break(doc)

    heading(doc, "九 场景落地三：岗位情报、申请事件和复盘", 1)
    add_image(doc, ASSETS / "jobs.png", width_cm=16.2, caption="图 10  岗位匹配：五维结果、证据和补齐动作")
    add_image(doc, ASSETS / "funnel.png", width_cm=15.6, caption="图 11  申请阶段累计到达数据（人工构造演示数据）")
    add_p(doc, "岗位情报保留来源 URL、主机、类型、抓取时间和可信等级；岗位只用于检索、比较和分析，不自动向外部平台投递。申请阶段同时保存当前状态和变化事件，避免把“当前状态分布”误读为“累计到达漏斗”。", size=10.5, after=0, line=1.2)
    page_break(doc)

    heading(doc, "十 数据流、权限和隐私保护", 1)
    table(doc, ["数据对象", "来源", "使用者", "保护方式"], [
        ["个人画像/简历", "学生输入、上传文件、解析结果", "学生本人、授权辅导员、相关 Agent", "角色权限、资源归属、脱敏日志、确认后写入"],
        ["岗位信息", "演示岗位、公开来源适配器", "学生、辅导员、岗位 Agent", "来源 URL/时间、有效性提示、不得自动投递"],
        ["面试与训练", "回答、评分、交付物和复盘", "学生本人、授权辅导员", "版本化记录、量表版本、训练用途边界"],
        ["企业评价", "一次性邀请链接和匿名反馈", "授权管理人员", "匿名阈值、审核状态、权限隔离"],
        ["审计与运行", "Agent、工具、错误和耗时", "系统治理人员", "参数脱敏、访问控制、保留期限"],
    ], widths=[3.2, 6.3, 4.2, 3.9], font_size=8.5)
    add_image(doc, ASSETS / "risk_boundaries.png", width_cm=15.6, caption="图 12  风险规则阈值边界验证：15/15 通过")
    add_p(doc, "摄像头表达分析只保存统计结果，最多保留 20 条；关闭摄像头、拒绝权限或未检测到清晰人脸时不生成分数。该维度不用于心理诊断或录用判断。", size=9.5, color=GRAY, after=0)
    page_break(doc)

    heading(doc, "十一 工程架构与部署路径", 1)
    add_image(doc, ASSETS / "architecture.png", width_cm=16.0, caption="图 13  工程架构：React/Vite、FastAPI、数据库、Worker 和 AI 服务")
    table(doc, ["部署层", "组件", "失败时的用户可见行为"], [
        ["前端", "React 19、TypeScript、Vite、ECharts、Playwright", "页面显示加载、重试或服务不可用状态"],
        ["API", "FastAPI、JWT/RBAC、SQLAlchemy、Pydantic", "结构化错误码，不暴露内部堆栈"],
        ["数据", "SQLite 本地；PostgreSQL + pgvector 部署", "事务失败回滚，保留错误记录"],
        ["异步任务", "Redis、Worker、任务租约、重试和死信", "任务显示 queued/running/succeeded/failed"],
        ["AI 服务", "在线模型适配器、本地规则、OCR/Embedding/ASR/TTS/Emotion", "服务未就绪时明确提示，不伪造成功"],
    ], widths=[2.7, 8.4, 6.5], font_size=8.7)
    add_p(doc, "本地启动脚本、Docker Compose 和部署示例已经存在；公开评审环境仍需单独准备专用账号、密钥和服务地址。", size=9.4, color=GRAY, after=0)
    page_break(doc)

    heading(doc, "十二 测试、实测和已知限制", 1)
    add_image(doc, ASSETS / "test_results.png", width_cm=16.2, caption="图 14  自动化验证和浏览器回归结果")
    table(doc, ["验证项", "结果", "口径"], [
        ["后端自动化", "63/63 通过", "当前工作区测试集，不等于业务准确率"],
        ["前端组件", "25/25 通过", "10 个测试文件"],
        ["API 流程", "22/22 符合预期", "包含预期 401/403 权限拒绝用例"],
        ["风险规则边界", "15/15 通过", "5 条规则分别测试阈值前/阈值/阈值后"],
        ["补充浏览器检查", "14 项完成", "学生、辅导员、工具、反馈、移动端"],
        ["现有浏览器回归", "1/6 通过，5 项待处理", "多记录选择器、旧断言文案、移动端职场流程"],
    ], widths=[4.3, 4.2, 9.1], font_size=8.8)
    add_p(doc, "已知限制", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "当前工作区没有公开 Git remote，仓库链接需要在提交前补充。",
        "演示数据库是人工构造样本，不代表实际学生或全国就业统计。",
        "在线模型、OCR、向量、语音和视觉服务的可用性取决于部署环境。",
        "现有浏览器回归仍有 5 项待修订，材料中保留这些失败以便评委判断成熟度。",
    ])
    page_break(doc)

    heading(doc, "十三 开源治理与协作机制", 1)
    table(doc, ["治理主题", "当前基础", "发布前动作"], [
        ["代码可运行", "README、启动脚本、Docker Compose、迁移和种子", "在仓库首页放一条干净环境启动路径"],
        ["配置安全", ".env.example 与本地配置分离", "确认无密钥、数据库文件、上传文件和个人材料"],
        ["质量门禁", "pytest、Vitest、Playwright、前端构建", "接入 CI，保留失败日志和已知问题"],
        ["Issue/PR", "当前未提供公开仓库", "新增 bug、feature、security 模板与评审规则"],
        ["版本发布", "迁移、配置和提示词已进入源码", "打评审 tag，发布 CHANGELOG 和兼容说明"],
        ["贡献者文档", "模块化目录和技术说明", "补充架构决策、运行时依赖和代码所有权说明"],
    ], widths=[3.4, 7.0, 7.2], font_size=8.7)
    add_p(doc, "开源治理目标是让其他开发者能够复现、定位、修复和扩展系统，而不是只展示一张漂亮的界面截图。", size=10.8, bold=True, color=PURPLE, before=12, after=0, line=1.2)
    page_break(doc)

    heading(doc, "十四 长期发展与产品化路线", 1)
    table(doc, ["阶段", "重点工作", "验收指标示例"], [
        ["提交前", "公开仓库、评审链接、脱敏素材、专用账号", "评委可访问仓库/PDF/视频，能按 README 启动"],
        ["试点", "校准风险规则、量表、权限和人工复核", "形成授权数据字典、抽检记录、量表版本"],
        ["运营", "岗位来源监控、任务队列、告警、成本和保留期限", "来源新鲜度、失败率、任务延迟、模型成本可查询"],
        ["扩展", "多学校隔离、租户级权限、课程反馈和导出", "租户隔离、数据导出、审计追责可验证"],
    ], widths=[3.0, 8.2, 6.4], font_size=8.9)
    add_p(doc, "长期发展遵循三条约束：保留人的确认权、保留事实来源、保留可撤销和可审计路径。项目不以扩大无确认自动执行权限作为增长指标。", size=10.8, color=PURPLE, bold=True, before=12, after=8, line=1.2)
    add_image(doc, ASSETS / "funnel.png", width_cm=15.6, caption="图 15  演示申请阶段数据，仅用于说明过程分析，不代表真实就业转化")
    page_break(doc)

    heading(doc, "十五 演示脚本与提交清单", 1)
    table(doc, ["顺序", "演示动作", "评审要点"], [
        ["1", "登录，展示学生工作台", "目标、任务、投递和提醒是否聚合"],
        ["2", "打开就业画像和四周计划", "画像有证据，任务有截止日期和验收标准"],
        ["3", "岗位匹配并展开证据", "五维分数与引用片段同时出现"],
        ["4", "就业助手发送综合问题", "右侧显示专业 Agent、工具和风险级别"],
        ["5", "进入模拟面试和职场训练", "说明入职前后两个流程的边界"],
        ["6", "切换辅导员，查看风险并验收帮扶", "风险有触发事实，反馈可闭环"],
        ["7", "展示仓库/PDF/视频提交项", "链接和账号使用专用评审信息"],
    ], widths=[1.4, 8.0, 8.2], font_size=8.9)
    add_p(doc, "提交项", size=12, bold=True, color=PURPLE, before=10, after=4)
    add_bullets(doc, [
        "代码仓库 HTTPS 链接：【提交前填写】",
        "作品介绍 PDF：本详细版 PDF",
        "演示视频链接：【提交前填写】",
        "评审账号/密码：【提交前填写专用账号】/【提交前填写专用密码】",
        "最终脱敏检查：姓名、学校、指导教师、学号、手机号、邮箱、真实简历、账号密码。",
    ])
    page_break(doc)

    heading(doc, "附录 事实口径和证据索引", 1)
    table(doc, ["事实类型", "本材料采用的表述", "不能替代的结论"], [
        ["自动化测试", "后端 63/63、前端 25/25、API 22/22、规则边界 15/15", "不等于模型准确率、上线稳定性或业务成效"],
        ["演示数据", "24 名构造学生、6 个演示岗位、85 条申请、96 项任务、9 条风险", "不等于真实用户规模、真实投递或就业结果"],
        ["本地规则分数", "岗位匹配五维和面试报告作为流程演示", "不等于录用概率、心理结论或训练提升"],
        ["公开链接", "仓库和视频均标为待填写", "不把本地文件路径写成评审 URL"],
        ["已知缺口", "浏览器回归仍有 5 项待处理", "不将当前版本包装成所有流程已通过"],
    ], widths=[3.5, 8.1, 6.0], font_size=8.8)
    add_p(doc, "本详细版在原 15 页作品介绍基础上增加了数据流、API/工具边界、部署、治理、风险和演示说明；原版文件保持不变。", size=10.2, color=GRAY, before=12, after=0, line=1.2)
    return doc


def write_md():
    text = f"""# {NAME}｜比赛项目介绍详细版\n\n**评审维度：**技术创新 30%｜场景落地 30%｜开源治理 20%｜长期发展 20%  \n**版本：**V1.0  \n**编制日期：**2026-10-25\n\n## 一 项目定位\n\n职航智管把高校毕业生的就业画像、四周计划、岗位匹配、简历优化、模拟面试、投递管理、学习成长、入职训练和反馈回流组织成一个可追踪业务闭环。模型负责理解与提出建议，后端负责事实、权限、工具执行和审计。\n\n## 二 评审维度与证据\n\n| 维度 | 项目回应 | 证据 |\n|---|---|---|\n| 技术创新 30% | 证据驱动的多 Agent 协作、工具契约、风险分层、持久会话 | Agent 流程、工具目录、执行截图 |\n| 场景落地 30% | 学生、辅导员、面试、入职后工作训练 | 页面截图、浏览器检查、演示视频 |\n| 开源治理 20% | README、Compose、环境模板、迁移、测试、版本治理 | 代码仓库和部署文档 |\n| 长期发展 20% | 试点、运营、扩展路线，数据保留、监控和量表版本 | 路线图、风险表和已知限制 |\n\n## 三 技术创新\n\n### 3.1 Agent 编排\n\n主 Agent 负责意图识别和步骤规划；专业 Agent 负责职业规划、岗位、简历、投递、面试、学习、职场和辅导员领域。专业 Agent 不能直接修改数据库，只能从注册工具目录中读取授权事实或形成动作提案。\n\n### 3.2 工具治理\n\n每次工具调用都重新校验角色、资源归属、参数契约、风险等级和输出契约。当前源码盘点包含 20 个只读工具、9 个普通写工具和 3 个高风险拒绝入口。\n\n### 3.3 可追溯运行\n\n会话、消息、运行状态、Agent 步骤、工具参数、工具结果、错误、开始结束时间和耗时均可保存。刷新页面后消息从服务端恢复，不能通过重复渲染伪造成功。\n\n### 3.4 多模态和入职后训练\n\n简历支持 PDF/DOCX；面试支持回答、追问、评分和可选语音/摄像头服务；职场工作台独立处理入职后的任务澄清、行动计划、交付物和复盘。摄像头表达稳定度只作为训练参考，不作录用或心理判断。\n\n## 四 场景落地\n\n### 4.1 学生端\n\n学生从材料和目标岗位建立画像，确认能力证据后生成四周计划，进入岗位匹配和简历建议，再进行面试、投递、学习和每周复盘。每个建议都可以回到画像、岗位、申请、面试或任务事实。\n\n### 4.2 辅导员端\n\n辅导员查看班级概览、学生进展和风险事实，按照事实建立帮扶任务，学生提交反馈后由辅导员人工验收。风险规则提供线索，不自动排名、处分或限制资源。\n\n### 4.3 入职后工作训练\n\n工作台读取岗位、阶段、目标、协作对象、截止时间和验收标准，学生提交真实交付物，系统按量表评审并生成复盘。AI 只生成草案，学生核对后主动提交。\n\n## 五 数据和安全\n\n个人画像、简历和面试记录仅在授权范围使用；岗位保留来源 URL、时间和可信等级；工具输入输出做日志脱敏；高风险动作需要确认；摄像头原始帧不落库。\n\n## 六 工程交付\n\n前端使用 React/TypeScript/Vite，后端使用 FastAPI、SQLAlchemy、Alembic；本地演示使用 SQLite，部署支持 PostgreSQL；Worker/Redis 承载异步任务；README、Windows 启动脚本、Docker Compose、环境模板和测试脚本已在项目中。\n\n## 七 开源治理\n\n当前工作区没有公开 Git remote，仓库链接暂留：`【提交前填写仓库 HTTPS URL】`。发布前应移除密钥、数据库、上传文件和演示密码；建立 Issue、PR、安全问题模板；为评审版本打 tag；把后端测试、前端测试、构建和关键 E2E 接入 CI；发布 CHANGELOG 和已知限制。\n\n## 八 长期路线\n\n1. 提交前：公开仓库、评审链接、脱敏素材和专用账号。\n2. 试点：校准风险规则、面试量表、授权流程和人工复核样本。\n3. 运营：岗位来源监控、任务重试、死信、成本、告警和数据保留。\n4. 扩展：多学校隔离、租户权限、课程改进反馈和可解释导出。\n\n## 九 验证与限制\n\n后端 63/63、前端组件 25/25、API 22/22、风险规则边界 15/15；现有浏览器回归仍有 5 项待处理。演示库包含 24 名人工构造学生、6 个演示岗位、85 条申请记录、96 项计划任务、9 条风险事件，不代表实际就业统计。\n\n## 十 提交清单\n\n- 代码仓库：`【提交前填写】`\n- 作品介绍 PDF：当前详细版 PDF\n- 演示视频：`【提交前填写】`\n- 评审账号/密码：`【提交前填写专用账号】` / `【提交前填写专用密码】`\n- 脱敏复核：姓名、学校、教师、学号、联系方式、真实简历和账号密码。\n"""
    DETAILED_MD.write_text(text, encoding="utf-8")


def main():
    # Keep the public build command routed to the current, shared-source edition.
    from build_competition_detailed_v2 import main as build_current
    build_current()


if __name__ == "__main__":
    main()
