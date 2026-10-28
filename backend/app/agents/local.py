from datetime import date, timedelta

from app.agents.contracts import (
    CapabilityTag,
    CareerPlan,
    DimensionScore,
    Evidence,
    ExamOption,
    GeneratedExamQuestion,
    InterviewEvaluation,
    InterviewQuestion,
    JobMatch,
    LearningExamGeneration,
    MatchDimension,
    PlanTask,
    ProfileAnalysis,
    ResumeOptimization,
    ResumeSuggestion,
    TrainingExchange,
    TrainingRoleMessage,
    WeeklyMetrics,
    WeeklyReview,
    WorkplaceDeliverableGeneration,
)


class LocalAgentGateway:
    """Deterministic provider for development, tests, and offline demonstrations."""

    provider = "local-demo"

    def __init__(self, today: date | None = None) -> None:
        self.today = today or date.today()

    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis:
        skill = "Python / SQL" if "Python" in resume_text or "SQL" in resume_text else "项目实践"
        quote = self._quote(resume_text)
        constraints = [f"目标{key}：{value}" for key, value in sorted(preferences.items())]
        return ProfileAnalysis(
            provider=self.provider,
            summary="具备数据分析基础，建议以可量化项目成果强化岗位竞争力。",
            strengths=[
                CapabilityTag(
                    name=skill,
                    level="具备实践基础",
                    evidence=[Evidence(source="resume", quote=quote)],
                )
            ],
            gaps=["项目成果缺少业务指标或量化结果"],
            constraints=constraints,
        )

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan:
        role = target_role or "数据分析师"
        tasks = [
            PlanTask(
                title="完善目标岗位简历",
                week=1,
                due_date=self.today + timedelta(days=6),
                acceptance_criteria="完成一版针对目标岗位且不虚构经历的简历",
            ),
            PlanTask(
                title="筛选并投递匹配岗位",
                week=2,
                due_date=self.today + timedelta(days=13),
                acceptance_criteria="完成至少 5 个有匹配依据的岗位投递",
            ),
            PlanTask(
                title="完成模拟面试训练",
                week=3,
                due_date=self.today + timedelta(days=20),
                acceptance_criteria="完成一次模拟面试并根据反馈重答薄弱问题",
            ),
            PlanTask(
                title="复盘求职漏斗",
                week=4,
                due_date=self.today + timedelta(days=27),
                acceptance_criteria="根据投递结果确认下一周期最多三项改进动作",
            ),
        ]
        return CareerPlan(
            provider=self.provider,
            primary_role=role,
            backup_roles=["商业分析师", "运营分析师"],
            rationale=f"基于当前画像：{profile_summary[:120]}",
            tasks=tasks,
        )

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch:
        profile_quote = self._quote(profile_summary)
        job_quote = self._quote(job_description)
        scores = {
            MatchDimension.requirements: 82,
            MatchDimension.skills: 86,
            MatchDimension.experience: 72,
            MatchDimension.preferences: 78,
            MatchDimension.growth: 80,
        }
        dimensions = [
            DimensionScore(
                dimension=dimension,
                score=score,
                evidence=[
                    Evidence(
                        source="resume"
                        if dimension in {MatchDimension.skills, MatchDimension.experience}
                        else "job",
                        quote=profile_quote
                        if dimension in {MatchDimension.skills, MatchDimension.experience}
                        else job_quote,
                    )
                ],
            )
            for dimension, score in scores.items()
        ]
        overall = round(sum(scores.values()) / len(scores))
        return JobMatch(
            provider=self.provider,
            recommendation="apply" if overall >= 80 else "improve_then_apply",
            overall_score=overall,
            dimensions=dimensions,
            gaps=["建议补充数据可视化工具的成果证据"],
            actions=["针对岗位关键词调整项目描述", "投递前核对硬性条件"],
        )

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization:
        original = self._quote(resume_text)
        return ResumeOptimization(
            provider=self.provider,
            suggestions=[
                ResumeSuggestion(
                    original=original,
                    suggested=f"{original}；补充本人可核实的分析规模、职责和业务结果",
                    reason=f"目标岗位强调：{self._quote(job_description, 80)}",
                )
            ],
        )

    def start_interview(
        self,
        resume_text: str,
        job_description: str,
        interview_type: str = "standard",
    ) -> InterviewQuestion:
        del resume_text, job_description
        prompts = {
            "standard": ("请用 STAR 结构说明你在数据分析项目中解决的核心问题。", "项目分析与表达结构"),
            "stress": ("如果方案上线后一周核心指标持续下滑，你会如何处理？", "抗压决策与沟通"),
            "technical": ("请结合一个真实项目，解释你如何使用 Python 和 SQL 完成数据清洗、验证与分析。", "技术深度与证据"),
        }
        question, competency = prompts.get(interview_type, prompts["standard"])
        return InterviewQuestion(
            provider=self.provider,
            question_id="q1",
            question=question,
            competency=competency,
        )

    def evaluate_answer(
        self,
        question: str,
        answer: str,
        job_description: str,
        interview_type: str = "standard",
        question_id: str | None = None,
    ) -> InterviewEvaluation:
        del question, job_description
        has_numbers = any(character.isdigit() for character in answer)
        score = 82 if has_numbers else 70
        if len(answer.strip()) < 30:
            score = max(55, score - 10)
        if interview_type == "stress" and len(answer.strip()) >= 80:
            score = min(95, score + 4)
        return InterviewEvaluation(
            provider=self.provider,
            content_completeness=score,
            job_relevance=78,
            answer_structure=75,
            evidence_quality=score,
            feedback=["回答已覆盖主要行动", "建议补充可核实的量化结果"],
            follow_up=InterviewQuestion(
                provider=self.provider,
                question_id="q2",
                question=(
                    "这个判断如何验证？请说明你本人承担的具体工作、关键取舍和最终结果。"
                    if question_id in (None, "q1") and interview_type != "stress"
                    else "现在资源只剩一半、时间只剩两小时，你先做哪一步？请给出判断依据。"
                ),
                competency="证据充分度" if interview_type != "stress" else "压力下的优先级",
            )
            if question_id in (None, "q1")
            else None,
        )

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview:
        return WeeklyReview(
            provider=self.provider,
            metrics=metrics,
            insights=[
                f"本周完成 {metrics.applications} 次投递，获得 {metrics.interviews} 次面试。"
            ],
            actions=["复核低匹配岗位", "补充简历量化证据", "完成一次模拟面试"],
        )

    def generate_learning_exam(
        self,
        *,
        skill_name: str,
        context: dict[str, object],
        question_count: int,
    ) -> LearningExamGeneration:
        """Generate a deterministic, contract-valid offline exam."""
        del context
        count = max(1, min(question_count, 20))
        templates = [
            ("目标岗位要求和验收标准", "A", "先明确能力目标和验收标准，再安排学习。"),
            ("可核验的学习证据", "B", "截图、练习结果、复盘或可访问链接比一句完成说明更可验证。"),
            ("把能力差距转为行动", "B", "用一个小项目或练习补齐差距，并把过程和结果写进简历。"),
            ("记录学习结果", "B", "计划应在确认后执行，并持续记录进度和证据。"),
            ("判断能力提升", "A", "能支持简历、岗位匹配或面试表达的证据才说明能力提升。"),
            ("考试未通过后的处理", "B", "保留错题解释并安排补强任务，形成可追踪的闭环。"),
        ]
        questions: list[GeneratedExamQuestion] = []
        for index in range(count):
            topic, answer, explanation = templates[index % len(templates)]
            questions.append(
                GeneratedExamQuestion(
                    prompt=f"围绕 {skill_name}，{topic}时哪项做法最合理？",
                    options=[
                        ExamOption(key="A", text="先确认目标、场景和验收标准"),
                        ExamOption(key="B", text="只记录学习时长，不保留结果"),
                        ExamOption(key="C", text="直接复制网上答案作为成果"),
                        ExamOption(key="D", text="跳过练习，等待系统自动完成"),
                    ],
                    correct_answer=answer,
                    explanation=explanation,
                    competency=skill_name,
                )
            )
        return LearningExamGeneration(
            provider=self.provider,
            prompt_version="exam-v1-local",
            questions=questions,
        )

    def generate_training_exchange(
        self,
        *,
        mode: str,
        stage: str,
        prompt: str,
        student_response: str,
        stress_level: str,
        material_context: list[str],
        expected_stage: str = "scoring",
    ) -> TrainingExchange:
        del prompt, material_context
        response_hint = self._quote(student_response, 80)
        if mode == "group_interview":
            messages = [
                TrainingRoleMessage(
                    speaker="candidate_logic",
                    display_name="逻辑型候选人",
                    content=f"我认可你提到的‘{response_hint}’，建议先把问题拆成目标、约束和验证指标。",
                ),
                TrainingRoleMessage(
                    speaker="candidate_collaboration",
                    display_name="协作型候选人",
                    content="我补充一下执行分工：先确认责任人和交付时间，再把风险同步给相关同学。",
                    reply_to_speaker="candidate_logic",
                ),
                TrainingRoleMessage(
                    speaker="candidate_challenger",
                    display_name="挑战型候选人",
                    content="这个方案需要补充资源不足时的备选路径，否则共识难以真正落地。",
                    reply_to_speaker="candidate_collaboration",
                ),
            ]
        elif mode == "presentation_defense":
            messages = [
                TrainingRoleMessage(
                    speaker="reviewer",
                    display_name="\u7b54\u8fa9\u8bc4\u59d4",
                    content=(
                        f"\u4f60\u521a\u624d\u63d0\u5230\u201c{response_hint}\u201d\u3002"
                        "\u8bf7\u7528\u95ee\u9898\u3001\u65b9\u6848\u3001\u7ed3\u679c\u548c\u98ce\u9669\u56db\u6b65\u8865\u5145\u4e00\u6761\u53ef\u9a8c\u8bc1\u7684\u8bba\u636e\u3002"
                    ),
                )
            ]
        elif mode == "career_planning":
            messages = [
                TrainingRoleMessage(
                    speaker="career_coach",
                    display_name="\u804c\u4e1a\u89c4\u5212\u6559\u7ec3",
                    content=(
                        f"\u5df2\u8bb0\u5f55\u4f60\u7684\u5224\u65ad\uff1a\u201c{response_hint}\u201d\u3002"
                        "\u8bf7\u518d\u660e\u786e\u4e00\u9879\u672c\u5468\u53ef\u9a8c\u6536\u884c\u52a8\u3001\u4e00\u4e2a\u8bc1\u636e\u548c\u590d\u76d8\u65f6\u95f4\u3002"
                    ),
                )
            ]
        else:
            level_instruction = {
                "light": "请把关键动作再说具体一些。",
                "medium": "如果时间只剩一天，你会如何排序并说明依据？",
                "high": "请在 30 秒内说明最优先动作、风险和验证标准。",
            }.get(stress_level, "请说明你的判断依据。")
            messages = [
                TrainingRoleMessage(
                    speaker="interviewer",
                    display_name="面试官",
                    content=level_instruction,
                )
            ]
        return TrainingExchange(
            provider=self.provider,
            messages=messages,
            next_stage=expected_stage,
            feedback=["回答已纳入本轮量表评分，后续建议补充可验证的结果证据。"],
        )

    def generate_workplace_deliverable(
        self,
        *,
        action_type: str,
        work_context: dict[str, object],
        session_history: list[dict[str, object]],
        current_draft: str | None = None,
    ) -> WorkplaceDeliverableGeneration:
        """Create a grounded offline draft from the stored work brief.

        This is deliberately deterministic for local demonstrations. It never
        invents a stakeholder, deadline, metric, or delivery requirement that
        is absent from the scenario context.
        """
        del session_history
        objective = str(work_context.get("objective", "完成当前工作任务"))
        role = str(work_context.get("role", "当前岗位"))
        stage = str(work_context.get("stage", "当前工作阶段"))
        deadline = str(work_context.get("deadline", "待确认"))
        stakeholders = self._join_context(work_context.get("stakeholders"), "相关协作方")
        deliverables = self._join_context(work_context.get("deliverables"), "待交付成果")
        criteria = self._join_context(work_context.get("acceptance_criteria"), "验收标准")
        constraints = self._join_context(work_context.get("constraints"), "现有限制")
        labels = {
            "clarify_questions": "任务澄清问题清单",
            "action_plan": "行动计划",
            "risk_register": "风险清单",
            "meeting_minutes": "会议纪要与行动项",
            "weekly_report": "周报与进度汇报",
            "delivery_draft": "交付物草案",
        }
        title = labels.get(action_type, "工作交付草案")
        if action_type == "clarify_questions":
            content = (
                f"任务目标：{objective}\n\n"
                f"在开始执行前，向{stakeholders}确认：\n"
                f"1. 本次交付的优先级、范围和完成定义是什么？\n"
                f"2. 交付物是否明确为：{deliverables}？\n"
                f"3. 截止时间是否为 {deadline}，中间检查点如何安排？\n"
                f"4. 验收标准是否为：{criteria}？\n"
                f"5. 当前限制条件是：{constraints}，出现冲突时由谁决策？"
            )
        elif action_type == "action_plan":
            content = (
                f"目标：{objective}\n\n"
                "行动分解：\n"
                "1. 先确认范围、负责人、依赖和验收口径。\n"
                "2. 按交付物拆分最小可执行任务，给每项任务设置检查点。\n"
                f"3. 与{stakeholders}同步依赖，优先处理会阻塞交付的事项。\n"
                f"4. 在 {deadline} 前提交 {deliverables}，提交前逐项核对：{criteria}。\n"
                "5. 保留过程证据，记录偏差、决策和下一步。"
            )
        elif action_type == "risk_register":
            content = (
                f"任务：{objective}\n\n风险与应对：\n"
                "- 范围不清：先用问题清单确认优先级和完成定义。\n"
                "- 依赖延迟：为关键依赖设置提前提醒，并准备不依赖该项的替代路径。\n"
                f"- 验收争议：提前让{stakeholders}确认 {criteria}。\n"
                f"- 时间不足：以 {deadline} 为硬节点，每个检查点同步进度和剩余风险。\n"
                f"- 资源限制：当前约束为 {constraints}，超出范围时及时升级决策。"
            )
        elif action_type == "meeting_minutes":
            content = (
                f"会议主题：{objective}\n"
                f"参会对象：{stakeholders}\n\n"
                "已确认事项：\n- 明确目标、范围和验收口径后再开始执行。\n"
                f"行动项：\n- 负责人：我；事项：推进 {deliverables}；截止：{deadline}。\n"
                "待确认问题：\n- 依赖、优先级和异常升级路径。\n"
                f"验收依据：{criteria}"
            )
        elif action_type == "weekly_report":
            content = (
                f"本周目标：{objective}\n"
                "进展：已完成任务范围确认，并拆分了下一步行动。\n"
                f"当前交付：{deliverables}\n"
                f"协作进展：已识别{stakeholders}的依赖与待确认事项。\n"
                f"风险：{constraints}\n"
                f"下周计划：围绕 {criteria} 完成检查并在 {deadline} 前提交。"
            )
        else:
            content = (
                f"交付目标：{objective}\n\n"
                f"适用岗位：{role}；工作阶段：{stage}\n"
                f"交付内容：{deliverables}\n"
                f"验收标准：{criteria}\n"
                f"协作对象：{stakeholders}\n"
                f"截止时间：{deadline}\n"
                f"约束与风险：{constraints}\n\n"
                "提交前检查：目标是否覆盖、结果是否可验证、风险是否已同步。"
            )
        if current_draft and current_draft.strip():
            content += "\n\n基于当前草案的修订提示：保留已确认事实，补齐目标、负责人、时间和验收证据。"
        return WorkplaceDeliverableGeneration(
            provider=self.provider,
            action_type=action_type,
            title=title,
            content=content,
            rationale=["内容仅引用当前工作简报中的目标、协作对象、交付物、期限和验收标准。"],
        )

    @staticmethod
    def _join_context(value: object, fallback: str) -> str:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return "、".join(items) if items else fallback
        if isinstance(value, str) and value.strip():
            return value.strip()
        return fallback

    @staticmethod
    def _quote(text: str, length: int = 120) -> str:
        cleaned = " ".join(text.split())
        return cleaned[:length] or "用户尚未提供有效文本"
