"""Unit tests for course type classification and strategy resolution."""

from app.schemas.tutor import CourseType, CourseTypeDecision, CourseTypeStrategy
from app.services.course_type_classifier import classify_course_type, resolve_course_type


def test_classify_uses_context_hint_for_knowledge_learning():
    decision = classify_course_type(
        question="Please solve this quickly",
        context={"courseType": "knowledge_learning"},
    )

    assert decision.decision == CourseType.KNOWLEDGE_LEARNING
    assert decision.confidence == 0.98
    assert decision.signals == ["context_hint:knowledge_learning"]


def test_classify_uses_context_hint_for_problem_solving_alias():
    decision = classify_course_type(
        question="What is feedback loop?",
        context={"intent": "solve"},
    )

    assert decision.decision == CourseType.PROBLEM_SOLVING
    assert decision.confidence == 0.98


def test_classify_prefers_problem_keywords_and_numeric_pattern():
    decision = classify_course_type(
        question="Given G(s)=1/(s+1), calculate the gain and derive the equation",
        context=None,
    )

    assert decision.decision == CourseType.PROBLEM_SOLVING
    assert decision.confidence >= 0.7
    assert "numeric_pattern" in decision.signals


def test_classify_prefers_knowledge_keywords():
    decision = classify_course_type(
        question="Explain what a PID controller is and why it works",
        context=None,
    )

    assert decision.decision == CourseType.KNOWLEDGE_LEARNING
    assert decision.confidence >= 0.6


def test_classify_tie_breaks_to_problem_when_numeric_pattern_exists():
    decision = classify_course_type(
        question="Explain why this concept solve for G(s)=k",
        context=None,
    )

    assert decision.decision == CourseType.PROBLEM_SOLVING
    assert decision.signals == ["tie_breaker:numeric_pattern"]


def test_classify_tie_breaks_to_knowledge_without_numeric_pattern():
    decision = classify_course_type(
        question="Explain and solve feedback in plain terms",
        context=None,
    )

    assert decision.decision == CourseType.KNOWLEDGE_LEARNING
    assert decision.signals == ["tie_breaker:default_knowledge"]


def test_classify_problem_branch_without_numeric_pattern_is_covered():
    decision = classify_course_type(
        question="Please solve and calculate the controller gain",
        context=None,
    )

    assert decision.decision == CourseType.PROBLEM_SOLVING
    assert "numeric_pattern" not in decision.signals


def test_classify_ignores_invalid_context_hint_and_uses_keyword_scoring():
    decision = classify_course_type(
        question="Explain the concept of PID",
        context={"courseType": ["invalid"], "task_type": "unknown"},
    )

    assert decision.decision == CourseType.KNOWLEDGE_LEARNING
    assert decision.confidence >= 0.58


def test_classify_falls_back_to_knowledge_when_no_signal_matches():
    decision = classify_course_type(
        question="PID",
        context={"note": "minimal"},
    )

    assert decision.decision == CourseType.KNOWLEDGE_LEARNING
    assert decision.confidence == 0.5
    assert decision.signals == ["fallback_default:knowledge_learning"]


def test_resolve_manual_strategy_requires_override_for_force_decision():
    auto = CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.73,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.MANUAL,
        auto_decision=auto,
        course_type_override=CourseType.PROBLEM_SOLVING,
    )

    assert final.decision == CourseType.PROBLEM_SOLVING
    assert final.confidence == 1.0
    assert final.overridden is True
    assert "strategy:manual_override" in final.signals


def test_resolve_manual_strategy_same_override_keeps_not_overridden_flag():
    auto = CourseTypeDecision(
        decision=CourseType.PROBLEM_SOLVING,
        confidence=0.82,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.MANUAL,
        auto_decision=auto,
        course_type_override=CourseType.PROBLEM_SOLVING,
    )

    assert final.decision == CourseType.PROBLEM_SOLVING
    assert final.overridden is False


def test_resolve_manual_without_override_falls_back_to_auto():
    auto = CourseTypeDecision(
        decision=CourseType.PROBLEM_SOLVING,
        confidence=0.81,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.MANUAL,
        auto_decision=auto,
        course_type_override=None,
    )

    assert final.decision == CourseType.PROBLEM_SOLVING
    assert final.overridden is False
    assert "strategy:manual_missing_override" in final.signals


def test_resolve_override_strategy_applies_override_when_present():
    auto = CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.66,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.OVERRIDE,
        auto_decision=auto,
        course_type_override=CourseType.PROBLEM_SOLVING,
    )

    assert final.decision == CourseType.PROBLEM_SOLVING
    assert final.confidence >= 0.9
    assert final.overridden is True
    assert "strategy:override_applied" in final.signals


def test_resolve_override_strategy_without_value_keeps_auto():
    auto = CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.64,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.OVERRIDE,
        auto_decision=auto,
        course_type_override=None,
    )

    assert final.decision == auto.decision
    assert final.overridden is False
    assert "strategy:override_missing_value" in final.signals


def test_resolve_auto_strategy_applies_legacy_override_if_present():
    auto = CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.55,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.AUTO,
        auto_decision=auto,
        course_type_override=CourseType.PROBLEM_SOLVING,
    )

    assert final.decision == CourseType.PROBLEM_SOLVING
    assert final.overridden is True
    assert "strategy:auto_legacy_override" in final.signals


def test_resolve_auto_strategy_without_override_returns_auto():
    auto = CourseTypeDecision(
        decision=CourseType.KNOWLEDGE_LEARNING,
        confidence=0.59,
        signals=["auto"],
    )

    final = resolve_course_type(
        strategy=CourseTypeStrategy.AUTO,
        auto_decision=auto,
        course_type_override=None,
    )

    assert final.decision == CourseType.KNOWLEDGE_LEARNING
    assert final.overridden is False
    assert "strategy:auto" in final.signals
