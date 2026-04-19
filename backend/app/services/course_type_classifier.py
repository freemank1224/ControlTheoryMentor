"""Course type classification and strategy resolution helpers."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.tutor import CourseType, CourseTypeDecision, CourseTypeStrategy

CONTEXT_HINT_KEYS = (
    "courseType",
    "course_type",
    "course_type_hint",
    "intent",
    "taskType",
    "task_type",
)

KNOWLEDGE_HINT_VALUES = {
    "knowledge_learning",
    "knowledge",
    "learn",
    "learning",
    "explain",
    "concept",
}

PROBLEM_HINT_VALUES = {
    "problem_solving",
    "problem",
    "solve",
    "solving",
    "exercise",
    "quiz",
}

KNOWLEDGE_KEYWORDS = {
    "what",
    "why",
    "explain",
    "definition",
    "concept",
    "difference",
    "overview",
    "intuition",
    "understand",
    "原理",
    "解释",
    "是什么",
    "区别",
    "概念",
    "理解",
}

PROBLEM_KEYWORDS = {
    "solve",
    "calculate",
    "compute",
    "derive",
    "design",
    "tune",
    "prove",
    "find",
    "determine",
    "given",
    "equation",
    "numerical",
    "求",
    "计算",
    "推导",
    "求解",
    "设计",
    "已知",
    "方程",
    "参数",
}


def _normalize_hint(raw_value: Any) -> CourseType | None:
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip().lower()
    if value in KNOWLEDGE_HINT_VALUES:
        return CourseType.KNOWLEDGE_LEARNING
    if value in PROBLEM_HINT_VALUES:
        return CourseType.PROBLEM_SOLVING
    return None


def _extract_context_hint(context: dict[str, Any] | None) -> CourseType | None:
    if not context:
        return None
    for key in CONTEXT_HINT_KEYS:
        if key in context:
            hint = _normalize_hint(context.get(key))
            if hint is not None:
                return hint
    return None


def _contains_numeric_problem_pattern(text: str) -> bool:
    # Math-like symbols and values strongly suggest problem-solving intent.
    return bool(re.search(r"(=|>=|<=|\b\d+(?:\.\d+)?\b|\bG\(s\)|\bH\(s\)|\bs\^?\d)", text, re.IGNORECASE))


def classify_course_type(question: str, context: dict[str, Any] | None = None) -> CourseTypeDecision:
    """Classify a learner request into knowledge-learning vs problem-solving."""

    context_hint = _extract_context_hint(context)
    if context_hint is not None:
        return CourseTypeDecision(
            decision=context_hint,
            confidence=0.98,
            signals=[f"context_hint:{context_hint.value}"],
            overridden=False,
        )

    text = question.lower()
    if context:
        text = f"{text} {' '.join(str(value) for value in context.values())}".lower()

    knowledge_score = sum(1 for keyword in KNOWLEDGE_KEYWORDS if keyword in text)
    problem_score = sum(1 for keyword in PROBLEM_KEYWORDS if keyword in text)

    has_numeric_pattern = _contains_numeric_problem_pattern(text)
    if has_numeric_pattern:
        problem_score += 2

    if problem_score > knowledge_score:
        delta = problem_score - knowledge_score
        confidence = min(0.95, 0.58 + 0.08 * delta + 0.02 * problem_score)
        signals = [f"keyword_problem:{problem_score}", f"keyword_knowledge:{knowledge_score}"]
        if has_numeric_pattern:
            signals.append("numeric_pattern")
        return CourseTypeDecision(
            decision=CourseType.PROBLEM_SOLVING,
            confidence=round(confidence, 2),
            signals=signals,
            overridden=False,
        )

    if knowledge_score > problem_score:
        delta = knowledge_score - problem_score
        confidence = min(0.95, 0.58 + 0.08 * delta + 0.02 * knowledge_score)
        return CourseTypeDecision(
            decision=CourseType.KNOWLEDGE_LEARNING,
            confidence=round(confidence, 2),
            signals=[f"keyword_knowledge:{knowledge_score}", f"keyword_problem:{problem_score}"],
            overridden=False,
        )

    if problem_score > 0 and knowledge_score > 0:
        # Ambiguous prompts with equations are treated as problem solving.
        if has_numeric_pattern:
            return CourseTypeDecision(
                decision=CourseType.PROBLEM_SOLVING,
                confidence=0.62,
                signals=["tie_breaker:numeric_pattern"],
                overridden=False,
            )
        return CourseTypeDecision(
            decision=CourseType.KNOWLEDGE_LEARNING,
            confidence=0.58,
            signals=["tie_breaker:default_knowledge"],
            overridden=False,
        )

    return CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.5,
        signals=["fallback_default:knowledge_learning"],
        overridden=False,
    )


def resolve_course_type(
    strategy: CourseTypeStrategy,
    auto_decision: CourseTypeDecision,
    course_type_override: CourseType | None,
) -> CourseTypeDecision:
    """Resolve final course type based on strategy and optional override."""

    base_signals = list(auto_decision.signals)

    if strategy == CourseTypeStrategy.MANUAL:
        if course_type_override is None:
            return CourseTypeDecision(
                decision=auto_decision.decision,
                confidence=auto_decision.confidence,
                signals=base_signals + ["strategy:manual_missing_override"],
                overridden=False,
            )
        return CourseTypeDecision(
            decision=course_type_override,
            confidence=1.0,
            signals=base_signals + ["strategy:manual_override"],
            overridden=course_type_override != auto_decision.decision,
        )

    if strategy == CourseTypeStrategy.OVERRIDE:
        if course_type_override is None:
            return CourseTypeDecision(
                decision=auto_decision.decision,
                confidence=auto_decision.confidence,
                signals=base_signals + ["strategy:override_missing_value"],
                overridden=False,
            )
        return CourseTypeDecision(
            decision=course_type_override,
            confidence=max(auto_decision.confidence, 0.9),
            signals=base_signals + ["strategy:override_applied"],
            overridden=course_type_override != auto_decision.decision,
        )

    if course_type_override is not None:
        return CourseTypeDecision(
            decision=course_type_override,
            confidence=max(auto_decision.confidence, 0.9),
            signals=base_signals + ["strategy:auto_legacy_override"],
            overridden=course_type_override != auto_decision.decision,
        )

    return CourseTypeDecision(
        decision=auto_decision.decision,
        confidence=auto_decision.confidence,
        signals=base_signals + ["strategy:auto"],
        overridden=False,
    )
