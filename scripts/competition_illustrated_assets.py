"""Evidence-based diagrams and screenshot crops for the illustrated report."""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT=Path(r'D:\table\ai_jiuye')
OUT=PROJECT/'docs'/'deliverables'/'比赛提交材料_职航智管_图文增强版_20261026'
ASSETS=OUT/'assets'
EVIDENCE=OUT/'evidence'
TMP=PROJECT/'output'/'competition-illustrated-20261026'
for folder in [OUT,ASSETS,EVIDENCE,TMP]:folder.mkdir(parents=True,exist_ok=True)
MANIFEST={}
C={'ink':'#171B2B','muted':'#536071','purple':'#6043B5','edge':'#8F83AF','pale':'#F3F0FA','teal':'#157F79','tealpale':'#EAF6F2','amber':'#A66316','amberpale':'#FFF5E4','line':'#697589','gray':'#F2F4F7'}
FONT=r'C:\Windows\Fonts\msyh.ttc'
BOLD=r'C:\Windows\Fonts\msyhbd.ttc'


class Canvas:
    def __init__(self,name,title,note='',height=1000,source=None,planned=False):
        self.name=name;self.im=Image.new('RGB',(2400,height),'white');self.d=ImageDraw.Draw(self.im)
        self.h=height;self.source=source or [];self.planned=planned
        self.text((40,22,2320,80),title,size=53,bold=True)
        if note:self.text((40,height-77,2320,62),note,size=31,color=C['muted'])
        self.boxes={}

    def wrap(self,text,font,width):
        lines=[]
        for paragraph in text.split('\n'):
            current=''
            for char in paragraph:
                if current and font.getlength(current+char)>width:
                    lines.append(current);current=char
                else:current+=char
            lines.append(current)
        return lines

    def text(self,rect,text,size=42,bold=False,color=None,center=False):
        x,y,w,h=rect;face=ImageFont.truetype(BOLD if bold else FONT,size)
        lines=self.wrap(text,face,w)
        lineh=int(size*1.34)
        if len(lines)*lineh>h+8:raise ValueError(f'{self.name}: text overflow {text[:32]} {rect}')
        yy=y+(h-len(lines)*lineh)/2 if center else y
        for line in lines:
            xx=x+(w-face.getlength(line))/2 if center else x
            self.d.text((xx,yy),line,font=face,fill=color or C['ink']);yy+=lineh

    def box(self,key,rect,title,body='',tone='purple'):
        x,y,w,h=rect
        fill={'purple':C['pale'],'teal':C['tealpale'],'amber':C['amberpale'],'gray':C['gray']}[tone]
        edge=C['teal']if tone=='teal'else C['amber']if tone=='amber'else C['edge']
        self.d.rounded_rectangle((x,y,x+w,y+h),radius=15,fill=fill,outline=edge,width=3)
        if body:
            self.text((x+24,y+19,w-48,70),title,44,True)
            self.text((x+24,y+100,w-48,h-115),body,34,color=C['muted'])
        else:self.text((x+18,y+10,w-36,h-20),title,43,True,center=True)
        self.boxes[key]=rect
        return self

    def anchor(self,key,side):
        x,y,w,h=self.boxes[key]
        return {'r':(x+w,y+h/2),'l':(x,y+h/2),'t':(x+w/2,y),'b':(x+w/2,y+h)}[side]

    def arrow(self,a,b,sides=('r','l'),via=None,label=None,color=None,dashed=False):
        start=self.anchor(a,sides[0])if isinstance(a,str)else a
        end=self.anchor(b,sides[1])if isinstance(b,str)else b
        points=[start]+(via or [])+[end];color=color or C['line']
        for p,q in zip(points,points[1:]):
            if dashed:
                length=math.dist(p,q);segments=max(1,int(length/16))
                for i in range(segments):
                    if i%2==0:
                        t0=i/segments;t1=(i+1)/segments
                        self.d.line((p[0]+(q[0]-p[0])*t0,p[1]+(q[1]-p[1])*t0,p[0]+(q[0]-p[0])*t1,p[1]+(q[1]-p[1])*t1),fill=color,width=4)
            else:self.d.line([p,q],fill=color,width=4)
        dx,dy=end[0]-points[-2][0],end[1]-points[-2][1];angle=math.atan2(dy,dx)
        self.d.polygon([end,(end[0]-18*math.cos(angle-.45),end[1]-18*math.sin(angle-.45)),(end[0]-18*math.cos(angle+.45),end[1]-18*math.sin(angle+.45))],fill=color)
        if label:
            mx=(start[0]+end[0])/2;my=(start[1]+end[1])/2
            self.text((mx-210,my-66,420,50),label,31,center=True,color=color)
        return self

    def save(self):
        path=ASSETS/(self.name+'.png');self.im.save(path)
        MANIFEST[self.name]={'type':'planned_diagram'if self.planned else 'source_diagram','title':self.name,'source':self.source,'pixel_size':list(self.im.size)}
        return path


def flow(name,title,nodes,note,source,planned=False):
    c=Canvas(name,title,note,720,source,planned)
    count=len(nodes);gap=45;width=(2320-gap*(count-1))/count
    for i,item in enumerate(nodes):
        title_text,body=item if isinstance(item,tuple)else(item,'')
        c.box(str(i),(40+i*(width+gap),170,width,350),title_text,body,'amber'if planned else 'purple')
        if i:c.arrow(str(i-1),str(i))
    c.save()


def diagrams():
    flow('d01_journey','从材料到行动的业务闭环',[('个人事实','简历、偏好与证据'),('目标与计划','确认后形成任务'),('准备与训练','岗位、面试与学习'),('状态与反馈','投递、帮扶和回访'),('下一轮行动','依据结果继续复盘')],'过程记录提供上下文；演示数据不代表真实就业效果',['frontend/src/app/router.tsx','backend/app/reviews/router.py'])
    flow('d02_problem','三类需求如何连接到同一条工作流',[('信息分散','事实难整理'),('建议泛化','缺少个人依据'),('执行中断','任务与反馈脱节'),('闭环设计','证据、确认、状态')],'图示为项目需求建模，不代表已完成用户调研统计',['README.md','docs/workplace-workbench.md'])
    c=Canvas('d03_roles','角色可见页面与服务端数据边界','前端导航仅负责入口；服务端再次校验身份与资源归属',970,['frontend/src/app/router.tsx','backend/app/tools/authorization.py'])
    for i,(head,body)in enumerate([('学生本人','画像、计划、岗位、训练\n只处理本人就业记录'),('辅导员','班级概览、进展与帮扶\n限定授权学生范围'),('企业填写者','一次性邀请页面\n不进入学生工作区')]):
        c.box(str(i),(50+i*790,170,720,350),head,body)
    c.box('api',(380,660,1640,170),'后端统一检查：有效身份 → 角色 → 学生归属 → 资源权限',tone='teal')
    for i in range(3):c.arrow(str(i),'api',('b','t'),via=[(410+i*790,590),(1200,590)])
    c.save()
    c=Canvas('d04_arch','系统分层与核心连接','模型侧负责理解与建议；事实、状态、授权和事务在业务后端',1050,['backend/app/main.py','backend/app/tools/registry.py','docker-compose.server-demo.yml'])
    c.box('ui',(50,145,2300,130),'浏览器：学生工作区 / 辅导员工作区 / 受限企业邀请')
    c.box('api',(60,375,1030,210),'FastAPI业务层','JWT/RBAC、资源归属、状态与事务')
    c.box('agent',(1310,375,1030,210),'Agent网关与授权工具','步骤规划、契约、确认与审计')
    c.box('db',(60,735,1030,200),'业务数据库与事件','画像、任务、申请、消息、运行记录',tone='teal')
    c.box('ai',(1310,735,1030,200),'可选模型与本地AI服务','按部署模式启用，不就绪时明确提示',tone='gray')
    c.arrow('ui','api',('b','t'),via=[(1200,325),(575,325)])
    c.arrow('ui','agent',('b','t'),via=[(1200,325),(1825,325)])
    c.arrow('api','agent');c.arrow('api','db',('b','t'));c.arrow('agent','ai',('b','t'));c.save()
    c=Canvas('d05_sequence','一次综合求职问题的执行时序','历史local-rules回放：2个专业步骤、4次只读调用，不是在线模型性能测评',1170,['output/ppt-evidence-2026-10-20/chat_run.json'])
    lanes=['用户页面','主Agent','职业规划','投递Agent','工具 / 数据库'];xs=[190,690,1190,1690,2190]
    for i,label in enumerate(lanes):
        c.box('l'+str(i),(xs[i]-160,135,320,105),label,tone='gray')
        c.d.line((xs[i],255,xs[i],1040),fill='#CCD1DB',width=3)
    events=[(0,1,'综合问题：画像、计划、投递',320),(1,2,'读取职业准备依据',445),(2,4,'profile.get / plan.get / tasks.list',570),(1,3,'读取投递进展',695),(3,4,'applications.list',820),(1,0,'汇总三项行动与引用',970)]
    for a,b,label,y in events:
        c.arrow((xs[a],y),(xs[b],y),label=None)
        c.text((min(xs[a],xs[b])+25,y-67,abs(xs[b]-xs[a])-50,55),label,33,center=True)
    c.save()
    c=Canvas('d06_gates','候选工具调用如何通过授权检查','任一校验失败即中止；工具定义风险等级不能由模型参数降低',1070,['backend/app/tools/registry.py','backend/app/tools/authorization.py'])
    names=[('有效身份','用户仍有效、角色一致'),('资源归属','学生本人或授权范围'),('工具与领域','注册名称和专业职责'),('输入输出契约','结构和类型均需有效')]
    for i,(title,body)in enumerate(names):
        c.box(str(i),(40+i*590,180,520,270),title,body)
        if i:c.arrow(str(i-1),str(i))
    c.box('deny',(60,670,980,210),'拒绝 / 明确错误','401、403、422或工具错误；保留真实状态',tone='amber')
    c.box('ok',(1320,670,1020,210),'检查风险与确认方式','只读直接读取；普通写按模式确认；禁用高风险入口',tone='teal')
    c.arrow('0','deny',('b','t'),via=[(300,560),(550,560)],color=C['amber'])
    c.arrow('3','ok',('b','t'),via=[(2070,560),(1830,560)],color=C['teal']);c.save()
    c=Canvas('d07_actions','动作提案与实际业务执行分开','撤销仅适用于声明可逆且具有撤销处理器的工具，不是所有写入都可撤销',1050,['backend/app/chat/actions.py','backend/app/chat/schemas.py'])
    c.box('p',(60,170,520,180),'待确认 pending')
    c.box('run',(900,170,560,180),'执行 executing')
    c.box('ok',(1820,170,520,180),'成功 succeeded',tone='teal')
    c.box('reject',(60,670,520,190),'拒绝 / 过期\nrejected / expired',tone='gray')
    c.box('fail',(900,670,560,190),'执行失败 failed',tone='amber')
    c.box('undo',(1820,670,520,190),'可逆工具撤销\nundone',tone='gray')
    c.arrow('p','run',label='用户确认');c.arrow('run','ok',label='事务成功')
    c.arrow('p','reject',('b','t'),label='拒绝或过期');c.arrow('run','fail',('b','t'),label='异常留痕')
    c.arrow('ok','undo',('b','t'),label='再次校验权限');c.save()
    c=Canvas('d08_async','消息接受、任务处理与SSE回传','Idempotency-Key避免重复接受；事件序号用于按序继续读取',1050,['backend/app/chat/router.py','backend/app/ai/service.py'])
    for i,(title,body)in enumerate([('浏览器发送','消息 + 幂等键'),('API接受','保存消息、run与queued事件'),('Worker处理','领取任务、执行步骤')]):
        c.box(str(i),(60+i*800,175,680,260),title,body)
        if i:c.arrow(str(i-1),str(i))
    c.box('ev',(1200,665,1130,210),'持久事件 / 工具详情','sequence、状态、错误和结论')
    c.box('back',(60,665,850,210),'浏览器按游标显示','GET events?after=事件序号',tone='teal')
    c.arrow('2','ev',('b','t'),via=[(2000,550),(1765,550)])
    c.arrow('ev','back',('l','r'),label='SSE事件');c.save()
    c=Canvas('d09_tasks','异步任务生命周期与失败重试','图示来自任务实现；参数与重试次数以实际部署配置为准',1050,['backend/app/ai/service.py','backend/app/ai/worker.py'])
    c.box('q',(60,170,590,200),'queued 待处理')
    c.box('r',(905,170,590,200),'running 已领取')
    c.box('s',(1750,170,590,200),'succeeded 完成',tone='teal')
    c.arrow('q','r',label='获得租约');c.arrow('r','s',label='保存结果')
    c.box('retry',(300,680,800,190),'未达上限：延迟重新入队',tone='amber')
    c.box('dead',(1400,680,800,190),'达到上限：failed / dead letter',tone='amber')
    c.arrow('r','retry',('b','t'),via=[(1200,520),(700,520)])
    c.arrow('r','dead',('b','t'),via=[(1200,520),(1800,520)])
    c.arrow('retry','q',('l','b'),via=[(180,775),(180,490),(355,490)],dashed=True)
    c.save()
    c=Canvas('d10_data','业务实体与证据关系图','关系图为概念对应，字段和外键以源码模型为准',1010,['backend/app/chat/models.py','backend/app/applications/models.py','backend/app/students/models.py'])
    nodes=[('user',(60,170,680,205),'用户 / 授权主体','role、class、owner'),('profile',(860,170,680,205),'画像 / 简历 / 计划','版本、来源、确认状态'),('job',(1660,170,680,205),'岗位 / 申请 / 事件','来源URL、阶段、发生时间'),('chat',(60,650,680,205),'会话 / 消息','owner、request_key、context'),('run',(860,650,680,205),'运行 / 专业步骤','plan、status、dependencies'),('tool',(1660,650,680,205),'工具 / 提案 / 审计','risk、confirmation、result')]
    for key,rect,title,body in nodes:c.box(key,rect,title,body)
    c.arrow('user','profile');c.arrow('profile','job');c.arrow('chat','run');c.arrow('run','tool')
    c.arrow('user','chat',('b','t'),label='归属');c.arrow('profile','run',('b','t'),label='业务上下文');c.save()
    flow('d11_confirm','画像与计划的两个独立确认环节',[('输入材料','真实经历与偏好'),('画像草稿','核对原文与结论'),('确认画像','写入正式版本'),('计划草稿','生成周任务'),('确认计划','按验收要求执行')],'模型产生草稿，不自动确认经历或完成任务',['backend/app/students/router.py','backend/app/plans/router.py'])
    flow('d12_resume','简历上传、解析与版本路径',[('文件校验','PDF / DOCX与大小'),('保存记录','上传成功有文件'),('解析结果','成功或明确失败'),('建议草稿','原文、理由与修改'),('人工确认','保存对应版本')],'历史实际DOCX上传曾解析失败；失败时提供可读文本，不能伪造成功',['backend/app/resumes/router.py','backend/app/resumes/parser.py'])
    flow('d13_sources','岗位来源的采集与核验链',[('公开来源','URL与站点类型'),('适配采集','字段解析与错误'),('来源元数据','抓取时间与可信级别'),('岗位展示','新鲜度与有效性'),('用户核验','返回原页面确认')],'来源流程是实现设计；历史演示库公共岗位0，不代表已完成实时采集',['backend/app/intelligence/service.py'])
    flow('d14_interview','面试场次中的核心题、追问与报告',[('岗位与简历','建立场次背景'),('核心问题','默认6题'),('必要追问','默认最多2次'),('逐轮评价','四维评分与反馈'),('场次报告','平均分与改进项')],'题量以场次配置为准；本地演示分数不等于人工评分一致性',['backend/app/interviews/service.py','backend/app/interviews/router.py'])
    flow('d15_learning','学习任务与练习证据的对应关系',[('能力差距','证据不足先提示'),('课程与任务','明确验收要求'),('学习证据','提交说明或链接'),('测验作答','评分、答案与错题'),('继续练习','依据记录调整任务')],'数据不足时保留空状态，不生成虚构能力曲线',['backend/app/growth/service.py','frontend/src/features/student/LearningPage.tsx'])
    flow('d16_delivery','职场工作交付物的版本与复盘',[('工作简报','目标、约束与验收'),('保存草案','本人编辑或AI辅助'),('提交交付','保留revision'),('结构化评审','按量表反馈'),('完成复盘','至少已交付一份')],'AI只生成草案；学生核对后提交，历史版本不覆盖',['docs/workplace-workbench.md','backend/app/workplace/service.py'])
    # Use the current application's authoritative transition graph.
    old=PROJECT/'docs'/'deliverables'/'比赛提交材料_职航智管_20261025'/'assets_detailed'/'application_states.png'
    shutil.copy2(old,ASSETS/'d17_application.png');MANIFEST['d17_application']={'type':'source_diagram','source':['backend/app/applications/service.py'],'note':'saved/applied/assessment/interview/offered可到closed；applied可直达interview'}
    flow('d18_weekly','每周复盘先限定时间和事件口径',[('近7天事件','不是全部当前状态'),('阶段计数','投递、笔试、面试'),('数据洞察','说明发生了什么'),('优先行动','最多三项建议'),('下轮记录','实际操作后再复盘')],'零事件也是有效结果；建议不能冒充已发生的进展',['backend/app/reviews/router.py'])
    flow('d19_intervention','辅导员与学生的帮扶闭环',[('辅导员建任务','assigned'),('学生查看','理解任务要求'),('学生反馈','submitted'),('辅导员核验','检查结果与事实'),('确认完成','resolved')],'提交与验收是两个环节；当前接口没有独立截止日期字段',['backend/app/interventions/router.py'])
    flow('d20_followup','录用、入职与四个阶段回访',[('录用申请','不是已经入职'),('建立就业记录','日期与评价授权'),('7 / 30天','学生与企业反馈'),('90 / 180天','长期适应与成长'),('审核后汇总','默认最少3条样本')],'阶段时间为产品回访设计；没有新增真实企业或学生样本',['backend/app/employment/service.py'])
    c=Canvas('d21_modes','全量本地与低资源演示版的能力差异','左侧表示服务全部就绪后的配置能力；右侧表示server-demo约束',1090,['docker-compose.yml','docker-compose.server-demo.yml','docs/server-demo-deployment.md'])
    c.box('full',(60,155,1090,710),'全量本地配置','React + FastAPI + 业务数据库\n\nAgent：在线适配器或明确local演示\n\nOCR、BGE-M3、ASR/TTS、视觉\n需要资源与服务就绪\n\n摄像头还需用户明确授权')
    c.box('demo',(1250,155,1090,710),'低资源服务器演示','Nginx + API + PostgreSQL + Redis\n\n在线Agent：网络、额度有效才工作\n\n本地OCR、向量、语音、视觉未部署\n附件与相关任务均限制\n\n失败不伪装为在线成功',tone='teal')
    c.save()
    c=Canvas('d22_topology','服务器演示版的运行拓扑','没有部署本地模型容器；该图是配置拓扑，不是本次全链路联调结果',1030,['docker-compose.server-demo.yml'])
    c.box('browser',(60,150,520,180),'浏览器')
    c.box('nginx',(900,150,600,180),'Nginx入口')
    c.box('api',(1820,150,520,180),'FastAPI')
    c.box('model',(1820,670,520,180),'外部模型API',tone='gray')
    c.box('db',(60,670,520,180),'PostgreSQL',tone='teal')
    c.box('redis',(900,670,600,180),'Redis / 轻量Worker',tone='teal')
    c.arrow('browser','nginx');c.arrow('nginx','api');c.arrow('api','model',('b','t'))
    c.arrow('api','db',('b','t'),via=[(2080,490),(320,490)])
    c.arrow('api','redis',('b','t'),via=[(2080,555),(1200,555)]);c.save()
    flow('d23_privacy','业务数据从采集到保留的控制点',[('必要采集','真实个人材料最小化'),('限定读取','角色与资源归属'),('授权模型','必要事实与引用'),('记录与脱敏','工具、审计、错误'),('保留与清理','按类型配置期限')],'音频、用量、审计等期限以实际配置为准；不把“代码有清理函数”当作已运行证明',['backend/app/core/retention.py','backend/app/core/config.py'])
    flow('d24_bug','已知上传问题的真实结果与排查路径',[('收到文件','HTTP 201保存记录'),('存储引用','返回路径字符串'),('解析器输入','按Path使用suffix'),('异常被捕获','parse_status=failed'),('替代路径','用户补充可读文本')],'2026-10-22实际出现解析失败；本次只说明问题，没有修改业务源码',['backend/app/resumes/router.py','backend/app/resumes/parser.py','backend/app/resumes/storage.py'])
    flow('d25_license','开源发布前需要落实的许可检查',[('项目权属','确认可授权主体'),('代码依赖','版本与分发义务'),('模型与权重','分别核对使用条件'),('图片与改编','来源和必要声明'),('发布材料','实际LICENSE / NOTICE')],'这是发布前方案；当前没有公开remote与根级许可证，不自动代选许可证',['frontend/package.json','backend/pyproject.toml','frontend/public/ai-interviewer.source.txt'],planned=True)
    flow('d26_contribute','从问题到发布的建议协作流程',[('Issue','复现、环境、证据'),('实现方案','影响与回滚'),('Pull Request','变化与测试记录'),('维护者复核','权限、接口、文档'),('版本发布','tag、迁移与限制')],'建议流程尚待团队采用；不表示CI、公开Issue或维护角色已建立',['docs/competition-governance-proposal.md'],planned=True)
    flow('d27_roadmap','按验收条件推进的长期路线',[('提交准备','链接、许可与复测'),('授权试点','标准、样本与复核'),('稳定运营','告警、成本与恢复'),('多组织扩展','租户隔离与导出')],'不虚构日期、合作院校、试点人数或资金承诺',['docs/competition-governance-proposal.md'],planned=True)
    flow('d28_evaluate','试点评估的证据采集与复核',[('固定版本','样本范围与授权'),('实际任务','输入、操作与结果'),('人工复核','事实、引用与可用性'),('统计口径','失败计入分母'),('阶段结论','区分目标与结果')],'本图为后续验收设计，不是已完成的试点成绩',['scripts/competition_detailed_content.py evaluation'],planned=True)
    flow('d29_demo','现场演示用五个结果证明闭环',[('目标与画像','指出确认和原文'),('计划与匹配','任务标准与引用'),('助手执行','展开工具与风险'),('训练报告','说明评分口径'),('帮扶验收','学生反馈与完成')],'演示顺序是建议；在线服务失败时明确说明并展示带日期的历史记录',['scripts/competition_detailed_content.py demo'],planned=True)
    c=Canvas('d30_submission','三项必交材料及其需要证明的内容','截图未给出页数或时长上限；按组委会最终通知提交',910,['比赛提交要求截图'],True)
    for i,(title,body)in enumerate([('代码仓库链接','完整可运行源码\nREADME、环境与部署\n许可证、评审tag\n\nHTTPS URL 待填写'),('作品介绍PDF','背景、架构和创新\n场景、测试和风险\n治理与长期计划\n\n本图文增强版'),('演示视频链接','核心功能与使用流程\n说明数据和服务状态\n脱敏、访问权限\n\n公开视频URL待填写')]):c.box(str(i),(45+i*790,170,730,560),title,body,'amber'if i!=1 else 'teal')
    c.save()
    c=Canvas('d31_assurance','材料证据需要分别回答四个问题','历史测试不当作今日验证；只有当前检查不代表全套测试通过',810,['output/ppt-evidence-2026-10-20/data_summary.json','scripts/competition_detailed_content.py'])
    for i,(title,body)in enumerate([('有没有实现','从源码与配置定位\n不是看宣传文案'),('是否已验证','用例、日期、环境\n通过和失败都保留'),('数据是什么','演示或真实授权样本\n标注分母与时间'),('下一步做什么','未完成项和验收条件\n计划不写成成绩')]):c.box(str(i),(40+i*590,165,520,460),title,body)
    c.save()
    c=Canvas('d32_retention','按数据类型记录保留策略','以下为源码默认值；部署是否启用、是否适用仍需项目方确认',880,['backend/app/core/config.py','backend/app/core/retention.py'])
    vals=[('音频','7天','媒体清理'),('模型用量','90天','调用记录'),('已完成任务','30天','排除死信'),('审计记录','730天','按配置保留')]
    for i,(name,value,note)in enumerate(vals):
        c.box(str(i),(40+i*590,180,520,470),name,'\n'+value+'\n\n'+note,'teal'if i%2 else 'purple')
    c.save()


def screenshots():
    raw=PROJECT/'output'/'copyright-20261022'/'screenshots'
    shots=PROJECT/'docs'/'deliverables'/'职航智管_GPT图像PPT提示词包_20261020'/'截图'
    def crop(key,path,box=None,notes=None):
        with Image.open(path)as source:
            pic=source.convert('RGB')
            if box:pic=pic.crop(box)
            pic.save(ASSETS/(key+'.png'))
        MANIFEST[key]={'type':'screenshot','source':str(path.relative_to(PROJECT)),'crop':box,'historical_capture':'2026-10-22'if path.parent==raw else '2026-10-20','ui_values_changed':False,'note':notes}
    crop('s01_student',raw/'student.png',(45,75,1290,760))
    crop('s02_profile',raw/'profile.png',(45,70,1290,730))
    crop('s03_plan',raw/'plan.png',(45,70,1290,740))
    crop('s04_match',raw/'match.png',(45,75,1290,990))
    crop('s05_sources',shots/'05-job-intelligence.png',(80,70,1560,930))
    crop('s06_resume',raw/'resume-uploaded.png',(528,218,1269,373),notes='实际上传失败状态，保留“需要手工录入”')
    crop('s07_interview',shots/'07C-digital-human.png')
    crop('s08_report',shots/'07B-interview-summary.png')
    crop('s09_learning',raw/'learning.png',(45,70,1290,950))
    crop('s10_workplace',shots/'08-workplace.png',(80,155,1560,1035))
    crop('s11_board',raw/'applications.png',(45,70,1290,860))
    crop('s12_weekly',raw/'review-result.png',(45,70,1290,575),notes='近7天事件为0，不能按全量累计漏斗解释')
    crop('s13_agent',shots/'09-agent-assistant.png',(50,95,1630,1010))
    crop('s14_counselor',shots/'12-counselor-dashboard.png',(80,75,1560,1110))
    crop('s15_feedback',shots/'11-student-feedback.png',(90,690,1540,965))
    crop('s16_resolved',shots/'13A-confirmed-feedback.png')
    crop('s17_employment',raw/'employment.png',(45,70,1290,855))
    crop('s18_login',raw/'login.png',(110,175,1490,845))
    # The narrow screenshot is preserved as an excerpt, beside a legible
    # explanation. No new interface controls or numbers are invented.
    source=shots/'10-agent-tool-details.png'
    with Image.open(source)as im:
        panel=im.convert('RGB').crop((0,200,330,665))
        panel=panel.resize((900,1268),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(2400,1400),'white');canvas.paste(panel,(45,65))
    d=ImageDraw.Draw(canvas);face=ImageFont.truetype(FONT,46);sub=ImageFont.truetype(FONT,37)
    d.text((1030,75),'profile.get 实际工具记录局部',font=face,fill=C['ink'])
    lines=['工具：profile.get  ·  版本1','风险：read，只读取授权数据','输入参数：{}','返回：画像摘要与来源片段','student_id在返回展示中被脱敏','本图为历史local-rules回放','工具成功不代表在线模型评估通过']
    for i,line in enumerate(lines):d.text((1030,230+i*140),line,font=sub,fill=C['muted'])
    canvas.save(ASSETS/'s19_tool_detail.png')
    MANIFEST['s19_tool_detail']={'type':'annotated_screenshot','source':str(source.relative_to(PROJECT)),'crop':[0,200,330,665],'ui_values_changed':False,'note':'工具区域等比放大；右侧为图解文字，不是重绘产品界面'}


def charts():
    root=PROJECT/'output'/'ppt-evidence-2026-10-20'/'charts'
    for name,file in [('c01_funnel','C01-cumulative-funnel.png'),('c02_current','C02-current-stages.png'),('c03_match','C03-job-match.png'),('c04_interview','C04-interview-scores.png'),('c05_risk_tasks','C05-risk-and-tasks.png'),('c06_tests','C06-test-results.png'),('c07_latency','C07-local-api-latency.png'),('c08_tools','C08-tool-inventory.png'),('c09_boundaries','C09-risk-boundaries.png')]:
        shutil.copy2(root/file,ASSETS/(name+'.png'))
        svg=(root/file).with_suffix('.svg')
        if svg.exists():shutil.copy2(svg,ASSETS/(name+'.svg'))
        MANIFEST[name]={'type':'data_chart','source':str((root/file).relative_to(PROJECT)),'data_date':'2026-10-20','values_changed':False}


def main():
    diagrams();screenshots();charts()
    (EVIDENCE/'figures_manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'assets':len(MANIFEST),'diagrams':sum(v['type'].endswith('diagram')for v in MANIFEST.values()),'screenshots':sum('screenshot'in v['type']for v in MANIFEST.values()),'charts':sum(v['type']=='data_chart'for v in MANIFEST.values())},ensure_ascii=False))


if __name__=='__main__':main()
