"""Cổng chặn tích hợp liên tục (CI Gate): đối chiếu báo cáo đánh giá của PR với baseline nhánh chính.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

Mã thoát: exit 0 = cho phép gộp (merge), exit 1 = chặn (blocked).
- Nhóm chỉ số an toàn (safety): tối đa bằng 0, không được bù trừ trung bình.
- Nhóm chỉ số năng lực (capability): phải đạt sàn tối thiểu VÀ khoảng tin cậy ghép cặp 95% của
  hiệu (PR - baseline) không được nằm hoàn toàn dưới 0.
- Cơ chế bánh cóc một chiều (ratchet): trên cùng phiên bản eval set, ngưỡng chỉ được phép siết chặt hơn.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.integrity import verify_report_integrity


def integrity_check(
    pr: dict[str, Any],
    base: dict[str, Any],
    spec: dict[str, Any],
    base_spec: dict[str, Any] | None = None,
) -> list[str]:
    """Kiểm tra tính toàn vẹn chống gian lận đánh giá (M7 Expert) trước khi so sánh kết quả.

    Tham số:
        pr: Báo cáo đánh giá của nhánh PR.
        base: Báo cáo baseline của nhánh chính.
        spec: Đặc tả metric áp dụng cho lần kiểm tra.
        base_spec: Đặc tả metric gốc trên nhánh chính để kiểm tra ratchet (nếu có).

    Trả về:
        Danh sách các vi phạm toàn vẹn (danh sách rỗng nghĩa là báo cáo đáng tin cậy).
    """
    return verify_report_integrity(pr, base, spec, base_spec)


def slice_check(pr: dict[str, Any], base: dict[str, Any], spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Đánh giá ngưỡng tối thiểu và hồi quy ghép cặp trên từng lát cắt dữ liệu quan trọng (M5 Advanced).

    Tham số:
        pr: Báo cáo đánh giá của PR.
        base: Báo cáo baseline trên nhánh chính.
        spec: Đặc tả metric chứa danh sách slices.

    Trả về:
        Bộ (danh sách mã slice bị chặn dạng 'slice:<name>/<metric>', danh sách dòng báo cáo).
    """
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap") or {}
    for sl in spec.get("slices") or []:
        sname = sl["name"]
        mid = sl["metric"]
        sid = f"slice:{sname}/{mid}"
        a = per_item(pr, mid, slice_name=sname)
        b = per_item(base, mid, slice_name=sname)
        verdict, note = "ok", ""
        if not a:
            val_disp: float | None = None
            verdict = "missing"
        else:
            raw_val = sum(a.values()) / len(a)
            val_disp = round(raw_val, 4)
            if "min" in sl and raw_val + 1e-12 < float(sl["min"]):
                verdict = "fail"
            elif "max" in sl and raw_val - 1e-12 > float(sl["max"]):
                verdict = "fail"
            if sl.get("no_significant_drop") and b:
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        th_view = {k: sl[k] for k in ("min", "max", "no_significant_drop") if k in sl}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val_disp!s:<8} {json.dumps(th_view):<40} {note:<28} {label}")
    return blocked, lines


def check(
    pr: dict[str, Any],
    base: dict[str, Any],
    spec: dict[str, Any],
    base_spec: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """So sánh toàn diện báo cáo PR với baseline theo đặc tả metric và lát cắt.

    Tham số:
        pr: Báo cáo đánh giá của PR.
        base: Báo cáo baseline.
        spec: Đặc tả metric hiện hành.
        base_spec: Đặc tả metric trên nhánh chính (phục vụ kiểm tra ratchet).

    Trả về:
        Bộ (danh sách hạng mục chặn merge, danh sách các dòng tóm tắt kết quả).
    """
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap(
                [a[k] for k in keys],
                [b[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000),
                rng=bs.get("rng", 2027),
            )
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    """Điểm vào dòng lệnh cho cổng chặn CI Gate.

    Tham số:
        argv: Danh sách đối số dòng lệnh tùy chọn.

    Trả về:
        0 nếu cho phép merge, 1 nếu bị chặn.
    """
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
