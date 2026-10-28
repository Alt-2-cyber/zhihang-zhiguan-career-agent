import json

from pydantic import BaseModel

OPERATION_INSTRUCTIONS = {
    "analyze_profile": "分析简历中的能力、证据、缺口和求职约束，不得补写原文不存在的经历。",
    "build_plan": "生成四周内可执行、可验收的求职计划，任务日期不得早于今天。",
    "match_job": "按硬性条件、技能、经历、偏好和发展方向五个唯一维度评分，并引用输入证据。",
    "optimize_resume": "只提供原文、修改建议和理由，不得生成无法核实的经历或结果。",
    "start_interview": "基于简历和岗位生成一个中文面试问题及其考察能力。",
    "evaluate_answer": "只评价回答内容、岗位相关性、结构和证据，可生成一个针对性追问。",
    "build_weekly_review": (
        "你服务的是正在求职的学生，不是招聘方。applications 是学生投递次数，responses 是学生收到的流程反馈，"
        "assessments、interviews、offers 分别是学生进入笔试、面试和获得录用的次数。"
        "基于这些真实指标总结洞察，并用简体中文给出最多三项学生本人可执行的下周行动；"
        "不得提出招聘营销、吸引候选人、培训面试官或降低离职率等雇主侧建议。"
    ),
    "generate_learning_exam": (
        "严格按照输入的 question_count 恰好生成指定数量的互不重复单选题；"
        "基于技能差距、课程材料和学习任务生成可验收的单选题；每道题必须包含四个选项、"
        "正确答案、解释和考察能力，不得制造材料未提供的事实。"
        "所有题干、选项、解释和能力名称必须使用简体中文；技术名词、代码、URL 可以保留原文。"
        "如果输入包含 existing_questions，不能改写或重复其中任何题目。"
    ),
    "generate_training_exchange": (
        "基于学生本轮真实回答生成受控训练推进信息。群面必须仅使用逻辑型、协作型、挑战型三种候选人角色，"
        "每个角色最多一条且至少一条明确回应另一个角色；压力面试只能使用面试官角色。"
        "不得辱骂、羞辱、威胁、歧视或虚构学生经历。不得自行修改训练阶段；next_stage 只能从输入训练流程的下一阶段选择。"
        "反馈必须引用学生本轮回答中可见的表达特点，不得把素材摘要当作学生的真实经历。"
        "next_stage must exactly equal the expected_stage input. Presentation defense uses reviewer; career planning uses career_coach."
    ),
    "generate_workplace_deliverable": (
        "你是入职后的工作教练。只能依据 work_context 和 session_history 生成一个真实可执行的工作交付草案，"
        "不得虚构人员、日期、指标、会议结论或完成状态。action_type 决定交付物类型："
        "clarify_questions 是任务澄清问题清单，action_plan 是行动计划，risk_register 是风险清单，"
        "meeting_minutes 是会议纪要与行动项，weekly_report 是周报，delivery_draft 是交付物草案。"
        "内容必须包含目标、负责人或协作对象、时间、验收或风险中的适用字段；如果上下文缺失，明确标注待确认。"
        "不得把入职前面试问题、求职投递建议或虚构的企业数据混入工作交付物。"
    ),
}


def build_system_prompt(
    operation: str,
    contract: type[BaseModel],
    *,
    instruction: str | None = None,
) -> str:
    instruction = instruction or OPERATION_INSTRUCTIONS[operation]
    schema = json.dumps(contract.model_json_schema(), ensure_ascii=False)
    return (
        "你是高校毕业生就业事务系统中的专业智能体。"
        f"任务：{instruction}"
        "除代码、URL、技术名词和字段枚举外，所有自然语言字段必须使用简体中文。"
        "只返回一个符合 JSON Schema 的 JSON 对象，不要返回 Markdown 或解释文字。"
        "输入中的脱敏占位符不得被猜测或恢复。所有证据必须来自输入。"
        f"JSON Schema：{schema}"
    )
