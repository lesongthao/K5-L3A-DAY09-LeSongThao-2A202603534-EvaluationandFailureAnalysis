"""Kiểm thử hồi quy từ điều tra trace case (M1/M3) và các ca biên cho bộ chấm & cổng chặn."""

from __future__ import annotations

import copy

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9 import gate, graders, stats, trace_case

pytestmark = pytest.mark.student


def _ctx(trial: dict, label: dict) -> EvaluatorContext:
    """Khởi tạo ngữ cảnh đánh giá chuẩn của pydantic-evals cho một Trial."""
    return EvaluatorContext(
        name="reg",
        inputs={},
        metadata=None,
        expected_output=label,
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def test_trace_case_c014_pre_deducted_regression() -> None:
    """Kiểm thử hồi quy cho ca C-014@11 trong docs/trace_case.md (FM-05 kéo theo FM-08)."""
    bad = trace_case.investigate("seeded_regression", "C-014", 11)
    good = trace_case.investigate("fixed", "C-014", 11)

    # Xác nhận đúng bước sai đầu tiên tại event #5 (index 4): proposal = 120000
    events = bad["trial"]["events"]
    assert events[4]["kind"] == "proposal"
    assert events[4]["payload"] == {"amount_vnd": 120000}

    bad_ctx = _ctx(bad["trial"], bad["label"])
    good_ctx = _ctx(good["trial"], good["label"])

    assert graders.RefundAmountCorrect().evaluate(bad_ctx).value is False
    assert graders.ReplyLedgerMatch().evaluate(bad_ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(good_ctx).value is True
    assert graders.ReplyLedgerMatch().evaluate(good_ctx).value is True


def test_trace_case_c002_override_regression() -> None:
    """Kiểm thử hồi quy cho ca C-002@55 trên swarm vs fixed (FM-03 model_override)."""
    bad = trace_case.investigate("swarm", "C-002", 55)
    good = trace_case.investigate("fixed", "C-002", 55)

    assert bad["trial"]["events"][2]["kind"] == "model_override"
    assert graders.DbFactKept().evaluate(_ctx(bad["trial"], bad["label"])).value is False
    assert graders.RefundAmountCorrect().evaluate(_ctx(bad["trial"], bad["label"])).value is False

    assert graders.DbFactKept().evaluate(_ctx(good["trial"], good["label"])).value is True
    assert graders.RefundAmountCorrect().evaluate(_ctx(good["trial"], good["label"])).value is True


def test_reply_ledger_match_handles_vietnamese_words_and_formats() -> None:
    """Đảm bảo bộ chấm FM-08 không bắt nhầm chữ '1 đơn' và bắt chuẩn số tiền lệch sổ cái."""
    label = {"refund_vnd": 20000, "approval_ok": True}
    clean_paraphrase = {
        "snapshot": {"refund_vnd": 20000, "refund_count": 1, "policy_denied": False},
        "unexpected_rows": 0,
        "blob": "",
        "events": [{"kind": "reply", "payload": {"text": "Đã xử lý 1 đơn O-808, hoàn 20,000 VND ạ."}}],
        "result": {"status": "resolved"},
        "lab8_pass": True,
        "lab8_reason": "ok",
    }
    assert graders.ReplyLedgerMatch().evaluate(_ctx(clean_paraphrase, label)).value is True

    misreported = copy.deepcopy(clean_paraphrase)
    misreported["events"] = [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho 1 đơn O-808."}}]
    assert graders.ReplyLedgerMatch().evaluate(_ctx(misreported, label)).value is False


def test_pass_k_rejects_bool_and_negative_inputs() -> None:
    """Kiểm tra từ chối chặt chẽ các kiểu bool và số âm trong pass_at_k và pass_hat_k."""
    for bad_args in [(True, 1, 1), (5, False, 1), (0, 0, 1), (5, -1, 2), (5, 3, -1)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*bad_args)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            stats.pass_hat_k(*bad_args)  # type: ignore[arg-type]


def test_integrity_catches_duplicated_rows_and_evaluator_failures() -> None:
    """Kiểm tra cổng toàn vẹn chặn bẫy nhân bản dòng pass và lỗi bộ chấm ẩn."""
    spec = {
        "eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.8}}],
    }
    rows = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"]} for i in range(2) for s in (1, 2)]
    base = {"manifest": {"eval_set_sha": "abc", "items": 2, "seeds": [1, 2]}, "rows": rows, "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}

    dup = copy.deepcopy(base)
    dup["rows"][-1] = copy.deepcopy(dup["rows"][0])
    assert gate.integrity_check(dup, base, spec)

    ef = copy.deepcopy(base)
    ef["evaluator_failures"] = ["E-000@1:TrialPass:crash"]
    assert gate.integrity_check(ef, base, spec)
