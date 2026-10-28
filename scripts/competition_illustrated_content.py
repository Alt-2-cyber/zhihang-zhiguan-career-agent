"""Preserve the detailed text and add evidence-led visual explanations."""
from copy import deepcopy

from competition_detailed_content import NAME, PAGES as PREVIOUS, p, h, t

REVISION='2026-10-26'

def fig(asset,caption,height=6.7):
    return {'kind':'figure','asset':asset,'caption':caption,'width':17.1,'height':height}

MAIN={
'overview':('d31_assurance','四类证据及其可支持的判断','先看有没有实现，再看是否验证，最后区分数据口径与后续计划；避免将配置数量和未来路线写成已证明的效果。'),
'background':('d02_problem','信息分散、泛化建议与执行中断的关系','图中的痛点是项目业务建模，不是用户问卷结果。系统通过事实、确认和状态连接这些步骤，而不是承诺未经测量的效率提升。'),
'roles':('d03_roles','角色入口与服务端资源归属','用户看到的导航只决定入口，后端才决定能读取哪名学生的资料；企业邀请不授予完整学生工作区权限。'),
'architecture':('d04_arch','前端、后端、Agent和数据的分层连接','读图顺序从浏览器向下：业务后端核验身份与状态，Agent通过注册工具获取事实；可选AI服务按模式启用。'),
'agent':('d05_sequence','综合问题回放中的专业步骤与只读工具','图示来自保存的local-rules回放：职业规划读取三类事实，投递Agent补充申请记录，最后汇总建议；不是在线大模型时延测试。'),
'tools':('d06_gates','工具候选从身份到契约的检查路径','每次调用都经过后端校验，任何失败都不能继续修改业务；具体校验由工具与业务处理器共同完成。'),
'conversation':('d08_async','消息接受、异步执行与SSE回传','HTTP接受、Worker完成、浏览器收到事件是不同节点。界面等待不代表任务失败，重新提交也不能绕过幂等检查。'),
'data':('d10_data','业务实体和证据关系','上排表示用户与业务事实，下排表示建议如何生成和执行；关系图是源码模型的概念说明，并非完整数据库ER图。'),
'profile':('d11_confirm','画像和计划的两次确认','先确认个人事实再确认行动安排，两类草稿都需要用户核验；任务完成仍必须有后续结果记录。'),
'jobs':('s04_match','岗位匹配界面与引用证据','同一画面把岗位要求、五维分与引用并列，适合核对建议依据；截图分数是预设演示值，不能据此宣称匹配准确率。'),
'interview':('d14_interview','默认面试结构及报告生成','6道核心题与2次追问构成默认上限，情景配置可以改变题量；报告用于训练反馈，不能直接推出录用判断。'),
'growth':('d16_delivery','从工作简报到有版本的交付物','交付草案与实际提交分开，评价基于提交内容；学生至少有一份交付结果后才完成复盘。'),
'applications':('d17_application','申请阶段的允许转换','已投递可直接进入面试，多个阶段均可关闭；关闭是终态。流程图根据ALLOWED_TRANSITIONS绘制，没有增加回退权限。'),
'counselor':('d19_intervention','学生反馈与辅导员验收的状态链','反馈提交和确认完成是两个动作；辅导员必须核对事实，不能因为学生填写了一句说明就自动验收。'),
'employment':('d20_followup','录用、入职与阶段回访','录用记录、入职信息和评价反馈分别保存；默认最小样本阈值只是当前配置，不能代替正式隐私评估。'),
'deployment':('d21_modes','全量本地配置与低资源服务器演示版','图左为满足条件后可启用的全量能力，图右为server-demo当前约束；图示不是一次新的模型服务实测。'),
'testing':('c06_tests','历史验证通过数与未通过项','日期为2026-10-20。后端、组件、API和规则用例的统计口径各异，不能合并解释为模型准确率。'),
'limitations':('d24_bug','文件已保存但解析失败的排查路径','HTTP 201表示文件记录创建，不等于解析成功；示例保留失败状态，文本补录作为替代输入。'),
'license':('d25_license','发布前许可与来源核对方案','图为尚待落实的发布检查，许可证需要实际权利主体确认；不把本地可见代码当成已完成开源。'),
'contribution':('d26_contribute','从Issue到发布的建议协作路径','流程是维护方案，不表示公开Issue、PR审查和CI已经运行。每个阶段应以可复现记录作为输入。'),
'roadmap':('d27_roadmap','按验收条件推进的长期路线','阶段之间以验收结果衔接，避免在没有团队承诺和样本支持时给出具体上线日期或用户规模。'),
'evaluation':('d28_evaluate','试点评估的样本、任务与复核流程','固定版本和授权后再采样，把失败计入分母；目标值、历史结果与实际试点成绩分别报告。'),
'demo':('d29_demo','现场演示的五个关键结果','演示应让评委看到输入、依据、操作和保存结果。遇到服务失败时说明现状，不用历史结果冒充现场输出。'),
'submission':('d30_submission','代码仓库、PDF与视频的提交对应','PDF已经整理，仓库和视频地址仍待填写；账号密码不写入公开PDF、视频或代码仓库。'),
}


def spread(id,title,after,blocks,sources):
    return {'id':id,'title':title,'after':after,'kind':'visual_detail','blocks':blocks,'sources':sources}


DETAILS=[
spread('roles_detail','03 图解 从登录入口到学生工作台','roles',[
p('下面两幅是同一项目的真实浏览器界面。先用角色入口确认访问者，再进入其工作区；页面内容不能替代后端对资源归属的限制。截图为历史演示记录，不含评审凭据。'),
fig('s18_login','统一登录入口，填写账号密码后按角色进入工作区',height=6.6),
fig('s01_student','学生工作台局部：当前目标、近期任务与阶段记录',height=6.3),
p('输入：本人或专用演示账号。操作：登录后检查导航和目标信息，再进入具体业务。结果：工作台聚合当日待办。需要核对：界面“累计投递”当前实现可能包含收藏记录，因此正文仍按申请记录解释，不把页面标签直接当统计定义。')],['frontend/src/features/auth/LoginPage.tsx','frontend/src/features/student/StudentDashboard.tsx','output/copyright-20261022/capture.log']),
spread('tools_detail','06 图解 展开一次真实工具调用','tools',[
p('工具目录说明系统允许哪些动作，执行记录说明某次实际上做了什么。两类证据结合才能判断是否越权、是否失败，以及回答是否引用了有效业务事实。'),
fig('s19_tool_detail','profile.get原始详情与字段读法；右侧是说明文字，不是重绘界面',height=8.6),
fig('c08_tools','历史运行时目录分层：20只读、9普通写、3高风险拒绝入口',height=6.1),
p('检查顺序：先看工具名与版本，再看read风险、输入参数、脱敏返回、状态与时间。该记录中的student_id已经脱敏。目录有32个定义不等于本次验证了32个工具，更不等于3个高风险动作可以执行。')],['backend/app/tools/registry.py','output/ppt-evidence-2026-10-20/chat_run.json','output/ppt-evidence-2026-10-20/architecture_inventory.json']),
spread('async_detail','07 图解 动作状态与任务状态','conversation',[
p('一条对话可能同时出现动作提案和异步任务。提案描述用户是否允许修改，任务描述工作是否被领取并完成；两个状态机不能直接画成同一条“已经成功”的进度条。'),
fig('d07_actions','动作提案：待确认、执行、成功、拒绝、过期和可逆撤销',height=7.1),
fig('d09_tasks','异步任务：入队、领取、结果保存、延迟重试和死信',height=7.1),
p('执行失败应保留error_code与状态，重新入队还需遵守重试和租约规则。撤销是特定可逆工具的能力，不能承诺对所有业务修改一键恢复。图中流程依据实现整理，本次没有故意向生产环境注入故障。')],['backend/app/chat/actions.py','backend/app/ai/service.py','backend/app/ai/worker.py']),
spread('privacy_detail','08 图解 数据使用与保留策略','data',[
p('数据流不只有“送给模型”。材料先关联用户与资源范围，再按任务提供必要事实，输出通过确认或契约后保存。日志和审计还需要脱敏与保留期限，避免无限积累个人材料。'),
fig('d23_privacy','采集、限定读取、授权模型、脱敏记录与保留清理',height=5.4),
fig('d32_retention','源码默认保留期：音频7天、模型用量90天、完成任务30天、审计730天',height=6.3),
p('这些数值是当前Settings默认值，不是对学校或用户作出的法律保留承诺。任务清理只删除符合状态与时间条件的记录，并排除死信；具体调度是否启用以部署配置为准。实际试点还需明确数据用途、访问范围、删除及更正流程。')],['backend/app/core/config.py','backend/app/core/retention.py','backend/app/tools/authorization.py']),
spread('profile_detail','09 图解 画像证据与分周任务','profile',[
p('画像和计划放在相邻页面阅读，能够看到同一项能力缺口如何转成准备动作。示例目标为数据分析师；不是所有专业都应使用相同任务顺序，辅导员需要检查任务是否符合真实岗位。'),
fig('s02_profile','材料输入与已确认画像：能力证据、差距和求职约束',height=7.2),
fig('s03_plan','四周计划：周次、任务名、截止日期和验收要求',height=7.1),
p('看图要点：画像里的Python/SQL来自输入片段，项目结果需要补证据；计划安排完善简历、筛选岗位、面试和复盘。生成这些安排不等于学生已经完成。学生完成后仍需在对应业务模块保存结果。')],['backend/app/students/service.py','backend/app/plans/router.py','output/copyright-20261022/capture.log']),
spread('source_detail','10 图解 岗位来源与有效性核验','jobs',[
p('岗位分析只有在输入有效时才有意义。来源适配器应保留原URL、采集时间、类型与状态；前端展示分布和来源情况，用户仍需回到原招聘页面确认要求与时效。'),
fig('d13_sources','公开来源到岗位展示的采集与核验链',height=4.9),
fig('s05_sources','岗位情报页面：历史样本中演示岗位6，公共岗位和启用来源均为0',height=7.6),
p('这幅页面不能说明实时公开岗位采集已成功；它证明来源状态有地方展示。正式演示新增来源时，应同时展示刷新时间、成功或失败记录及字段缺失处理，不应把网页搜索描述为稳定商业招聘API。')],['backend/app/intelligence/service.py','frontend/src/features/student/JobIntelligencePage.tsx','output/ppt-evidence-2026-10-20/api_snapshot.json']),
spread('resume_detail','10 图解 上传记录与解析失败边界','jobs',[
p('材料保存和文本解析是两个环节。上传请求返回201后，前端仍需读取parse_status，决定能否把该材料用于后续分析。下面保留了真实失败记录，没有替换为“解析成功”。'),
fig('d12_resume','上传、解析、修改草稿与确认版本的关系',height=5.1),
fig('s06_resume','实际上传37KB演示DOCX后的列表状态：“需要手工录入”',height=3.6),
t(['检查项','应如何解释'],[['文件记录创建','文件存在，不代表得到可读文本'],['解析失败','前端显示状态；提供文本输入或重新提交'],['修改建议草稿','必须以实际输入原文为依据'],['确认版本','用户核实事实后才能保存']],[4.2,13]),
p('输入：一份不含个人身份信息的构造DOCX。操作：浏览器真实选择并上传。结果：文件保存，解析失败。代码线索为存储路径类型与解析器要求不一致；这项问题仍需修复后使用真实文件回归，文档不修改源码来掩盖它。')],['backend/app/resumes/router.py','backend/app/resumes/parser.py','backend/app/resumes/storage.py','output/copyright-20261022/screenshots/resume-uploaded.png']),
spread('interview_detail','11 图解 面试交互与场次报告','interview',[
p('同一场次会依次产生问题、回答、追问和评价。把面试台和最终报告并排理解，比单独展示一个雷达图更容易检查：用户回答了什么、哪一轮结束、最终分数依据是什么。'),
fig('s07_interview','真实数字人面试台局部，保留文字问题和未部署摄像头的提示',height=8.3),
fig('s08_report','已完成8轮的场次报告：四维均分和后续练习方向',height=5.8),
p('报告显示内容完整度76、岗位相关性78、表达结构75、证据质量76。此处是构造回答和本地规则评分，不能将数字人照片当作实时生成的视频，也不能将报告写成在线模型与人工评分一致性实验。')],['backend/app/interviews/service.py','frontend/src/features/student/DigitalHumanStage.tsx','output/ppt-evidence-2026-10-20/interview.json']),
spread('scores_detail','11 图解 两类评分的证据与口径','interview',[
p('岗位匹配比较个人画像与职位，面试报告比较该场回答与量表；即使两者都在0—100范围，分母、输入和用途也不同。图表保留历史原数据，不作跨模块“能力总分”。'),
fig('c03_match','五维匹配预设演示分数：82、86、72、78、80；综合80/100',height=6.9),
fig('c04_interview','单场8轮回答平均分：76、78、75、76',height=6.9),
p('适当用途：检查维度标签、引用和结果展示是否完整，选择下一轮训练重点。不能推出：80%录用率、模型准确率或“使用后提升若干分”。要评价效果，必须另有授权样本、人工标注、对照与时间范围。')],['backend/app/agents/local.py','output/ppt-evidence-2026-10-20/job_match.json','output/ppt-evidence-2026-10-20/interview.json']),
spread('growth_detail','12 图解 从学习任务到工作交付','growth',[
p('学习成长负责能力与练习记录，职场训练负责独立工作简报和交付。下面三图分别说明学习流、真实学习页面和工作场景，避免把做题结果直接当成工作绩效。'),
fig('d15_learning','学习任务记录形成后续练习依据',height=3.2),
fig('s09_learning','学习页面局部，数据不足时保留提示而不是生成虚构曲线',height=5.0),
fig('s10_workplace','工作任务简报局部：目标、交付物、约束和验收标准',height=5.2),
p('看图顺序：先确认能力证据是否充足，再检查任务要求，最后比较实际交付与标准。示例中的5个工作情景和2份交付记录属于构造样本；历史只验证过1条桌面交付链路，不能说全部情景已通过。')],['backend/app/growth/service.py','backend/app/workplace/service.py','docs/workplace-workbench.md']),
spread('weekly_detail','13 图解 从申请看板到本周行动','applications',[
p('看板显示当前记录所处阶段，复盘显示最近七天实际出现的事件。它们可以同时正确，却不应出现相同的总数。特别是历史申请已不在近七天窗口时，复盘为0也不等于记录丢失。'),
fig('s11_board','申请看板局部：收藏、已投递及后续阶段',height=4.9),
fig('d18_weekly','复盘先选时间窗口，再计算事件和建议',height=3.1),
fig('s12_weekly','真实复盘结果：近7天无事件，仍保留建议的性质',height=4.6),
p('输入：近七天的ApplicationEvent。输出：投递、回复、笔试、面试与录用等统计和不超过三项行动。建议不等于发生过的结果；已有全量累计数据不可以直接覆盖这个窗口的统计。')],['backend/app/applications/service.py','backend/app/reviews/router.py','output/copyright-20261022/capture.log']),
spread('help_detail','14 图解 查看风险、提交反馈与验收','counselor',[
p('从班级概览找到需要关注的对象后，辅导员应先核对事实。学生反馈和教师确认分开保存，演示时应看到状态从“待确认”到“已完成”的不同环节。'),
fig('s14_counselor','班级概览局部：24人、85条申请、9条风险事件（演示数据）',height=5.5),
fig('s15_feedback','学生提交后的真实反馈区域局部',height=2.9),
fig('s16_resolved','辅导员核验后的完成记录局部',height=3.4),
p('操作证据：历史浏览器完成了学生填写反馈和辅导员确认。业务价值在于任务有责任人、反馈有原文、验收有状态；不是以一条“已完成”推断班级帮扶成功率。真实样本还需注意一个学生多条风险时应按人去重。')],['backend/app/interventions/router.py','output/ppt-evidence-2026-10-20/browser-capture-agent-counselor.log']),
spread('quality_detail','15 图解 入职记录与反馈发布条件','employment',[
p('入职跟踪页面需要已录用申请作为来源，并由学生填写日期与企业评价授权。本示例尚未进入录用，因此实际页面没有就业记录，这种空状态也应如实展示。'),
fig('s17_employment','入职跟踪页面：无可用录用记录时不生成虚构就业结果',height=7.3),
t(['对象','输入与结果','发布边界'],[['就业记录','已录用申请、入职日期、授权','限本人和授权工作人员'],['学生反馈','真实任职体验与建议','不代表企业官方结论'],['企业邀请','一次性令牌对应一条记录','不暴露完整学生工作区'],['企业画像','审核通过样本，默认至少3条','不足样本时不展示明细']],[3.3,7.2,6.7]),
p('以上是实现与页面核对，没有新增真实企业、入职或长期回访数据。7、30、90、180天是功能设置的回访节点，不是本项目已经运行了180天的证据。')],['backend/app/employment/service.py','frontend/src/features/student/EmploymentFollowupPage.tsx']),
spread('deploy_detail','16 图解 服务器拓扑与性能证据范围','deployment',[
p('部署拓扑说明组件怎么连接，延迟图说明一次特定环境下怎样采样。两个图一起使用时，应保留“配置设计”和“历史本机实测”的区别，不把本机GET请求性能当成云端在线推理速度。'),
fig('d22_topology','server-demo配置拓扑：浏览器、Nginx、API、数据库、Redis与外部模型',height=6.7),
fig('c07_latency','历史本机5个接口各20次顺序GET的中位数与P95',height=6.4),
p('采样不含模型生成、OCR、向量、语音或视觉耗时，没有并发负载控制。2026-10-25站点检查仅首页与健康接口200，不能证明登录、数据库写入或所有Agent任务均可用；本次文档增强没有扩大这一验证范围。')],['docker-compose.server-demo.yml','docs/server-demo-deployment.md','output/ppt-evidence-2026-10-20/api_performance.json']),
spread('risk_detail','17 图解 风险样本与规则边界','testing',[
p('班级状态图说明构造样本如何展示；阈值图说明规则函数在边界处如何返回。二者分别是数据演示和确定性用例，不是对真实学生的预测评估。'),
fig('c05_risk_tasks','演示库：正常15、关注4、需干预5；任务已完成36、待完成60',height=6.9),
fig('c09_boundaries','5条规则的阈值前、阈值及阈值后，共15个用例',height=6.2),
p('构造样本每名风险学生仅一条事件，所以9条对应9人；真实数据不一定如此。连续面试未通过等事实还未全部接入定时扫描，函数边界用例通过不能自动证明班级后台扫描已持续完成。')],['backend/app/risks/rules.py','backend/app/core/scheduler.py','output/ppt-evidence-2026-10-20/risk_boundary_cases.json']),
spread('counts_detail','17 图解 两个阶段图为何不能混用','testing',[
p('同一85条构造申请可以产生两张都正确但含义不同的图。左图式累计到达表示“曾经走到哪里”，当前分布表示“现在停在哪里”。不能把两图的数字相减后宣称新增就业成效。'),
fig('c01_funnel','按申请ID去重的累计到达：85、68、50、33、16',height=6.6),
fig('c02_current','互斥的当前状态：17、18、17、17、16，合计85',height=6.6),
p('看图要求：核对是否为同一数据库、时间范围是否一致、记录是否按申请ID或学生去重、收藏是否计入总数。所有数字仅说明系统支持的过程统计，不能写作真实投递、录用或训练改善结果。')],['backend/app/applications/models.py','output/ppt-evidence-2026-10-20/data_summary.json'])
]


def build_pages():
    pages=[]
    for original in deepcopy(PREVIOUS):
        asset,caption,note=MAIN[original['id']]
        original['kind']='chapter'
        blocks=[];inserted=False
        for block in original['blocks']:
            if block['kind']=='figure':
                if not inserted:
                    blocks.extend([fig(asset,caption,height=7.4),p('看图要点：'+note)]);inserted=True
            else:blocks.append(block)
        if not inserted:
            # Insert after the first table, or after the first explanatory paragraph.
            slot=next((i+1 for i,b in enumerate(blocks)if b['kind']=='table'),1)
            blocks[slot:slot]=[fig(asset,caption,height=7.4),p('看图要点：'+note)]
        original['blocks']=blocks
        pages.append(original)
        pages.extend(deepcopy(x)for x in DETAILS if x['after']==original['id'])
    return pages


PAGES=build_pages()
assert len(PAGES)==40
used=[b['asset']for page in PAGES for b in page['blocks']if b['kind']=='figure']+['s13_agent','d01_journey']
assert len(used)==60
assert len(set(used))==60
