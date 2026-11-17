"""Kiểm tra tính toàn vẹn báo cáo đánh giá và cơ chế bánh cóc một chiều (Ratchet — M7 Expert).

Module này tách riêng các quy tắc chống gian lận báo cáo (anti-gaming) cho cổng CI Gate, đảm bảo
mọi báo cáo PR dính NaN/inf, rơi hoặc nhân bản dòng, tráo tập hạt giống, tráo nhãn lát cắt, sửa tay
số liệu tổng hợp hoặc nới lỏng ngưỡng đặc tả đều bị từ chối ngay lập tức.
"""

from __future__ import annotations

import math
from typing import Any

from lab9.eval import aggregate
from lab9.graders import GRADERS


def is_bad_number(val: Any) -> bool:
    """Kiểm tra giá trị số tổng hợp có bị thiếu, thuộc kiểu bool, hoặc là NaN/vô cực hay không.

    Tham số:
        val: Giá trị cần kiểm tra trong từ điển metrics.

    Trả về:
        True nếu giá trị không hợp lệ cho phép so sánh ngưỡng.
    """
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return True
    return math.isnan(val) or math.isinf(val)


def ratchet_problems(spec: dict[str, Any], base_spec: dict[str, Any]) -> list[str]:
    """Đối chiếu đặc tả PR với base_spec trên cùng phiên bản eval set theo quy tắc chỉ siết chặt.

    Tham số:
        spec: Đặc tả metric của nhánh PR.
        base_spec: Đặc tả metric gốc trên nhánh chính.

    Trả về:
        Danh sách các vi phạm nới lỏng ngưỡng hoặc hạ cấp cờ chặn.
    """
    problems: list[str] = []
    same_version = spec.get("eval_set_version") == base_spec.get("eval_set_version")
    same_file = bool(spec.get("eval_set")) and spec.get("eval_set") == base_spec.get("eval_set")
    if not (same_version or same_file):
        return problems
    if same_file and not same_version:
        problems.append("eval_set_version bumped without changing eval_set file")

    if base_spec.get("seeds") and spec.get("seeds") != base_spec.get("seeds"):
        problems.append("spec seeds differ from base_spec on the same eval set")

    spec_metrics = {m["id"]: m for m in spec.get("metrics") or []}
    for bm in base_spec.get("metrics") or []:
        mid = bm["id"]
        if mid not in spec_metrics:
            problems.append(f"metric {mid!r} removed from spec")
            continue
        sm = spec_metrics[mid]
        if bm.get("blocking") and not sm.get("blocking"):
            problems.append(f"metric {mid!r} downgraded from blocking to non-blocking")
        bth = bm.get("threshold") or {}
        sth = sm.get("threshold") or {}
        if "min" in bth and ("min" not in sth or float(sth["min"]) < float(bth["min"]) - 1e-12):
            problems.append(f"metric {mid!r} min threshold loosened ({sth.get('min')} < {bth['min']})")
        if "max" in bth and ("max" not in sth or float(sth["max"]) > float(bth["max"]) + 1e-12):
            problems.append(f"metric {mid!r} max threshold loosened ({sth.get('max')} > {bth['max']})")
        if "max_increase" in bth and (
            "max_increase" not in sth or float(sth["max_increase"]) > float(bth["max_increase"]) + 1e-12
        ):
            problems.append(f"metric {mid!r} max_increase loosened")
        if bth.get("no_significant_drop") and not sth.get("no_significant_drop"):
            problems.append(f"metric {mid!r} dropped no_significant_drop")

    spec_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for bs in base_spec.get("slices") or []:
        key = (bs["name"], bs["metric"])
        if key not in spec_slices:
            problems.append(f"slice {key[0]}/{key[1]} removed from spec")
            continue
        ss = spec_slices[key]
        if bs.get("blocking") and not ss.get("blocking"):
            problems.append(f"slice {key[0]}/{key[1]} downgraded to non-blocking")
        if "min" in bs and ("min" not in ss or float(ss["min"]) < float(bs["min"]) - 1e-12):
            problems.append(f"slice {key[0]}/{key[1]} min threshold loosened")
        if "max" in bs and ("max" not in ss or float(ss["max"]) > float(bs["max"]) + 1e-12):
            problems.append(f"slice {key[0]}/{key[1]} max threshold loosened")
        if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
            problems.append(f"slice {key[0]}/{key[1]} dropped no_significant_drop")
    return problems


def verify_report_integrity(
    pr: dict[str, Any],
    base: dict[str, Any],
    spec: dict[str, Any],
    base_spec: dict[str, Any] | None = None,
) -> list[str]:
    """Kiểm tra toàn diện tính xác thực của báo cáo PR so với baseline và đặc tả metric.

    Tham số:
        pr: Báo cáo đánh giá của PR.
        base: Báo cáo baseline trên nhánh chính.
        spec: Đặc tả metric áp dụng cho lần kiểm tra.
        base_spec: Đặc tả metric gốc trên nhánh chính để kiểm tra ratchet (nếu có).

    Trả về:
        Danh sách lỗi toàn vẹn (rỗng nếu báo cáo hợp lệ hoàn toàn).
    """
    problems: list[str] = []
    if base_spec is not None:
        problems.extend(ratchet_problems(spec, base_spec))

    if pr.get("evaluator_failures"):
        problems.append(f"pr has {len(pr['evaluator_failures'])} evaluator failure(s)")

    pr_rows = pr.get("rows")
    base_rows = base.get("rows")
    zero_passes = isinstance(pr_rows, list) and not any(bool(r.get("pass_rate")) for r in pr_rows)
    pr_metrics = pr.get("metrics")
    if not isinstance(pr_metrics, dict) or not pr_metrics:
        problems.append("pr metrics missing or empty")
    else:
        for k, v in pr_metrics.items():
            if k == "cost_per_success" and v is None and zero_passes:
                continue
            if is_bad_number(v):
                problems.append(f"metric {k!r} has invalid/NaN/inf value: {v!r}")
        for m in spec.get("metrics") or []:
            mid = m["id"]
            if mid == "cost_per_success" and pr_metrics.get(mid) is None and zero_passes:
                continue
            if mid not in pr_metrics or is_bad_number(pr_metrics.get(mid)):
                problems.append(f"spec metric {mid!r} missing or invalid in pr metrics")

    manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    if not isinstance(pr_rows, list) or not isinstance(base_rows, list) or not pr_rows or not base_rows:
        problems.append("rows missing or empty")
        return problems

    want_n = int(manifest.get("items") or 0) * len(manifest.get("seeds") or [])
    if len(pr_rows) != want_n:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({want_n})")
    if manifest.get("items") != base_manifest.get("items") or list(manifest.get("seeds") or []) != list(
        base_manifest.get("seeds") or []
    ):
        problems.append("manifest items/seeds differ from baseline")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(set(pr_pairs)) != len(pr_pairs):
        problems.append("duplicate (item_id, seed) rows detected in PR report")
    if set(pr_pairs) != set(base_pairs):
        problems.append("PR (item_id, seed) set differs from baseline")

    base_slices = {(r.get("item_id"), r.get("seed")): sorted(r.get("slices") or []) for r in base_rows}
    for r in pr_rows:
        pair = (r.get("item_id"), r.get("seed"))
        if pair in base_slices and sorted(r.get("slices") or []) != base_slices[pair]:
            problems.append(f"slice tags altered on {pair[0]}@{pair[1]}")
            break

    row_mids = [m["id"] for m in spec.get("metrics") or [] if m["id"] in GRADERS or m["id"] in base_rows[0]]
    row_values_clean = True
    for r in pr_rows:
        for mid in row_mids:
            val = r.get(mid)
            if val is None or not isinstance(val, bool):
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has invalid {mid}={val!r}")
                row_values_clean = False
                break
        if not row_values_clean:
            break

    # Đối chiếu lại số liệu tổng hợp từ rows để phát hiện chỉnh sửa thủ công pr["metrics"]
    if row_values_clean and isinstance(pr_metrics, dict) and not problems:
        has_cost = all("cost" in r and isinstance(r["cost"], (int, float)) for r in pr_rows)
        rows_for_agg = pr_rows if has_cost else [{**r, "cost": 0.0} for r in pr_rows]
        recomputed = aggregate(rows_for_agg, row_mids, k_values=spec.get("pass_k", []))
        for mid in row_mids:
            if mid in pr_metrics and recomputed.get(mid) is not None:
                if abs(float(pr_metrics[mid]) - float(recomputed[mid])) > 1e-3:
                    problems.append(f"metric {mid!r}={pr_metrics[mid]} disagrees with rows ({recomputed[mid]})")
        for k_key in [k for k in recomputed if k.startswith(("pass_5", "pass_at_", "pass_hat_"))]:
            if k_key in pr_metrics and recomputed.get(k_key) is not None and "pass_rate" in row_mids:
                if abs(float(pr_metrics[k_key]) - float(recomputed[k_key])) > 1e-3:
                    problems.append(f"metric {k_key!r}={pr_metrics[k_key]} disagrees with rows ({recomputed[k_key]})")
        if has_cost and "cost_per_success" in pr_metrics and recomputed.get("cost_per_success") is not None:
            if abs(float(pr_metrics["cost_per_success"]) - float(recomputed["cost_per_success"])) > 1e-3:
                problems.append("metric 'cost_per_success' disagrees with rows")
    return problems
