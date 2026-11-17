"""Các hàm thống kê cho Lab 9 (M2 hiệu chuẩn giám khảo, M4 paired bootstrap, M6 pass@k & pass^k).

Nguyên tắc cốt lõi:
- Giám khảo AI (LLM Judge) là một bộ phân loại nhị phân — phải đo lường bằng ma trận nhầm lẫn,
  Precision, Recall, Cohen's Kappa và hiệu chỉnh tỷ lệ lỗi bằng Rogan-Gladen.
- Điểm trung bình cao hơn chưa có ý nghĩa cho tới khi khoảng tin cậy ghép cặp (paired CI) loại trừ 0.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy import stats as sp_stats

POS = "FAIL"  # Nhiệm vụ của giám khảo là tìm lỗi nên FAIL là lớp dương tính (positive class)


def _normalize_labels(human: Sequence[str], judge: Sequence[str]) -> tuple[list[str], list[str]]:
    """Chuẩn hóa và kiểm tra tính hợp lệ của hai chuỗi nhãn PASS/FAIL.

    Tham số:
        human: Danh sách nhãn chuẩn do con người gán.
        judge: Danh sách nhãn dự đoán do giám khảo AI gán.

    Trả về:
        Bộ hai danh sách nhãn đã viết hoa và cắt khoảng trắng thừa.
    """
    if len(human) != len(judge):
        raise ValueError(f"Độ dài nhãn không khớp: human={len(human)}, judge={len(judge)}.")
    if not human:
        raise ValueError("Danh sách nhãn không được rỗng.")
    h_norm = [str(x).strip().upper() for x in human]
    j_norm = [str(x).strip().upper() for x in judge]
    return h_norm, j_norm


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """Tính ma trận nhầm lẫn (tp/fp/fn/tn) với FAIL là lớp dương tính.

    Tham số:
        human: Danh sách nhãn chuẩn của người.
        judge: Danh sách nhãn của giám khảo.

    Trả về:
        Từ điển chứa số lượng tp, fp, fn, tn.
    """
    h_norm, j_norm = _normalize_labels(human, judge)
    tp = fp = fn = tn = 0
    for h_val, j_val in zip(h_norm, j_norm):
        h_pos = h_val == POS
        j_pos = j_val == POS
        if h_pos and j_pos:
            tp += 1
        elif not h_pos and j_pos:
            fp += 1
        elif h_pos and not j_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Tính độ chuẩn xác (Precision) và độ phủ (Recall) trên lớp FAIL.

    Tham số:
        human: Danh sách nhãn chuẩn của người.
        judge: Danh sách nhãn của giám khảo.

    Trả về:
        Bộ (precision, recall); trả về 0.0 nếu mẫu số tương ứng bằng 0.
    """
    cm = confusion(human, judge)
    prec_denom = cm["tp"] + cm["fp"]
    rec_denom = cm["tp"] + cm["fn"]
    precision = cm["tp"] / prec_denom if prec_denom > 0 else 0.0
    recall = cm["tp"] / rec_denom if rec_denom > 0 else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """Tính hệ số đồng thuận Cohen's Kappa: (p_o - p_e) / (1 - p_e).

    Ném ValueError khi p_e == 1 (giám khảo hằng số không mang tín hiệu phân loại).

    Tham số:
        human: Danh sách nhãn chuẩn của người.
        judge: Danh sách nhãn của giám khảo.

    Trả về:
        Giá trị Cohen's Kappa kiểu float.
    """
    cm = confusion(human, judge)
    total = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    p_o = (cm["tp"] + cm["tn"]) / total
    p_human_pos = (cm["tp"] + cm["fn"]) / total
    p_judge_pos = (cm["tp"] + cm["fp"]) / total
    p_e = p_human_pos * p_judge_pos + (1.0 - p_human_pos) * (1.0 - p_judge_pos)
    if math.isclose(p_e, 1.0, abs_tol=1e-12):
        raise ValueError("Cohen's kappa không xác định khi p_e == 1 (nhãn không có phương sai).")
    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Hiệu chỉnh tỷ lệ lỗi quan sát được theo độ nhạy và độ đặc hiệu của giám khảo; cắt về [0, 1].

    Tham số:
        observed_rate: Tỷ lệ FAIL quan sát được từ giám khảo.
        sensitivity: Độ nhạy (Recall = TP / (TP + FN)).
        specificity: Độ đặc hiệu (TN / (TN + FP)).

    Trả về:
        Tỷ lệ lỗi ước lượng đã hiệu chỉnh nằm trong đoạn [0.0, 1.0].
    """
    denom = sensitivity + specificity - 1.0
    if math.isclose(denom, 0.0, abs_tol=1e-12):
        raise ValueError("Rogan-Gladen không xác định khi sensitivity + specificity == 1.")
    corrected = (observed_rate + specificity - 1.0) / denom
    return float(min(1.0, max(0.0, corrected)))


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 1000,
    rng: int = 2027,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Tính khoảng tin cậy ghép cặp (paired bootstrap percentile CI) cho hiệu trung bình mean(a) - mean(b).

    Tham số:
        a: Điểm trung bình theo seed của từng item ở phiên bản A (PR).
        b: Điểm trung bình theo seed của từng item ở phiên bản B (baseline), cùng thứ tự.
        n_resamples: Số lần lấy mẫu lặp bootstrap.
        rng: Hạt giống ngẫu nhiên cho bộ sinh numpy.random.default_rng.
        confidence: Mức độ tin cậy (mặc định 0.95).

    Trả về:
        Bộ (mean_diff, ci_low, ci_high). Nếu a == b tại mọi phần tử thì trả về (0.0, 0.0, 0.0).
    """
    if len(a) != len(b):
        raise ValueError(f"Hai chuỗi ghép cặp phải cùng độ dài: {len(a)} != {len(b)}.")
    if not a:
        raise ValueError("Không thể chạy paired bootstrap trên chuỗi rỗng.")
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if np.array_equal(arr_a, arr_b):
        return (0.0, 0.0, 0.0)

    def _mean_diff(x: np.ndarray, y: np.ndarray, axis: int = -1) -> np.ndarray:
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    res = sp_stats.bootstrap(
        (arr_a, arr_b),
        _mean_diff,
        n_resamples=n_resamples,
        paired=True,
        method="percentile",
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    diff = float(np.mean(arr_a - arr_b))
    return (diff, float(res.confidence_interval.low), float(res.confidence_interval.high))


def _validate_nck(n: int, c: int, k: int) -> None:
    """Kiểm tra chặt chẽ bộ tham số (n, c, k) cho ước lượng không chệch pass@k và pass^k.

    Tham số:
        n: Tổng số lần chạy thử nghiệm của một item (n >= 1).
        c: Số lần chạy đạt yêu cầu (0 <= c <= n).
        k: Kích thước mẫu con cần đánh giá (1 <= k <= n).
    """
    for name, val in (("n", n), ("c", c), ("k", k)):
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"Tham số {name}={val!r} phải là số nguyên.")
    if n < 1 or c < 0 or c > n or k < 1 or k > n:
        raise ValueError(f"Bộ tham số không hợp lệ: n={n}, c={c}, k={k}.")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Xác suất có ÍT NHẤT MỘT lần đạt trong k lần rút từ n lần chạy (với c lần đạt).

    Công thức ước lượng không chệch (Chen et al., 2021): 1 - C(n - c, k) / C(n, k).

    Tham số:
        n: Tổng số lần chạy của item.
        c: Số lần đạt trong n lần chạy.
        k: Số lần thử được rút.

    Trả về:
        Giá trị ước lượng pass@k trong đoạn [0.0, 1.0].
    """
    _validate_nck(n, c, k)
    return 1.0 - (math.comb(n - c, k) / math.comb(n, k))


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Chỉ số pass^k (tau-bench, Yao et al., 2024): xác suất CẢ k lần rút từ n lần chạy đều đạt.

    Công thức ước lượng không chệch: C(c, k) / C(n, k).

    Tham số:
        n: Tổng số lần chạy của item.
        c: Số lần đạt trong n lần chạy.
        k: Số lần thử cần đạt đồng thời.

    Trả về:
        Giá trị ước lượng pass^k trong đoạn [0.0, 1.0].
    """
    _validate_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)
