# -*- coding: utf-8 -*-
"""零依赖两阶段单纯形法（最小化）。

仅覆盖本项目所需的线性规划规模（变量 < 40，约束 < 80）。
使用 Bland 规则避免循环，数值容差 1e-9。
"""

import math


class LPResult:
    def __init__(self, status, x=None, value=None, message=""):
        self.status = status          # optimal / infeasible / unbounded / error
        self.x = x or []
        self.value = value
        self.message = message

    def __repr__(self):
        return f"LPResult({self.status}, {self.value})"


def _pivot(T, obj, row, col, m, n):
    piv = T[row][col]
    if abs(piv) < 1e-12:
        raise ZeroDivisionError("pivot too small")
    inv = 1.0 / piv
    Tr = T[row]
    for j in range(n + 1):
        Tr[j] *= inv
    for i in range(m):
        if i == row:
            continue
        f = T[i][col]
        if abs(f) > 1e-12:
            Ti = T[i]
            for j in range(n + 1):
                Ti[j] -= f * Tr[j]
    f = obj[col]
    if abs(f) > 1e-12:
        for j in range(n + 1):
            obj[j] -= f * Tr[j]


def _simplex(T, basis, c, allowed, m, n, max_iter=5000):
    """T: m x (n+1)，basis 长度 m，c 长度 n。返回状态。"""
    obj = [0.0] * (n + 1)
    for j in range(n):
        obj[j] = c[j]
    for i, b in enumerate(basis):
        cb = c[b]
        if abs(cb) > 1e-15:
            row = T[i]
            for j in range(n + 1):
                obj[j] -= cb * row[j]

    for _ in range(max_iter):
        enter = -1
        for j in range(n):
            if not allowed[j]:
                continue
            if obj[j] < -1e-9:
                enter = j
                break
        if enter < 0:
            val = 0.0
            for i, b in enumerate(basis):
                if b < n:
                    val += c[b] * T[i][n]
            return "optimal", val

        leave = -1
        best_ratio = math.inf
        for i in range(m):
            a = T[i][enter]
            if a > 1e-9:
                ratio = T[i][n] / a
                if ratio < best_ratio - 1e-10 or (
                    abs(ratio - best_ratio) <= 1e-10 and (leave < 0 or basis[i] < basis[leave])
                ):
                    best_ratio = ratio
                    leave = i
        if leave < 0:
            return "unbounded", None
        _pivot(T, obj, leave, enter, m, n)
        basis[leave] = enter

    return "max_iter", None


def minimize(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None,
             max_iter=5000):
    """min c^T x, s.t. A_ub x <= b_ub, A_eq x = b_eq, bounds。

    bounds: [(low, high) | None]，None 表示 [0, inf)。
    """
    A_ub = [list(map(float, r)) for r in (A_ub or [])]
    b_ub = [float(v) for v in (b_ub or [])]
    A_eq = [list(map(float, r)) for r in (A_eq or [])]
    b_eq = [float(v) for v in (b_eq or [])]
    c = [float(v) for v in c]
    n0 = len(c)

    bounds = bounds or [(0.0, None)] * n0
    lows, highs = [], []
    for i in range(n0):
        lo, hi = bounds[i] if bounds[i] else (0.0, None)
        lows.append(0.0 if lo is None else float(lo))
        highs.append(None if hi is None else float(hi))
        if highs[-1] is not None and highs[-1] < lows[-1] - 1e-12:
            return LPResult("infeasible", message="变量上下界冲突")

    # 变量平移：x = y + low
    shift = lows
    c2 = c[:]
    const_obj = sum(c[i] * shift[i] for i in range(n0))

    rows = []  # (type, coeffs, rhs)
    for r, b in zip(A_ub, b_ub):
        rr = [r[i] for i in range(n0)]
        rhs = b - sum(rr[i] * shift[i] for i in range(n0))
        rows.append(["<=", rr, rhs])
    for r, b in zip(A_eq, b_eq):
        rr = [r[i] for i in range(n0)]
        rhs = b - sum(rr[i] * shift[i] for i in range(n0))
        rows.append(["==", rr, rhs])
    for i in range(n0):
        if highs[i] is not None:
            rr = [0.0] * n0
            rr[i] = 1.0
            rows.append(["<=", rr, highs[i] - shift[i]])

    # 统一 b >= 0
    norm = []
    for typ, rr, rhs in rows:
        if rhs < -1e-12:
            rr = [-v for v in rr]
            rhs = -rhs
            typ = ">=" if typ == "<=" else ("<=" if typ == ">=" else "==")
        elif abs(rhs) <= 1e-12:
            rhs = 0.0
        norm.append((typ, rr, rhs))

    n_slack = sum(1 for t, _, _ in norm if t != "==")
    n_art = sum(1 for t, _, _ in norm if t in (">=", "=="))
    n = n0 + n_slack + n_art
    m = len(norm)

    if m == 0:
        x = [shift[i] for i in range(n0)]
        return LPResult("optimal", x, const_obj)

    T = []
    basis = []
    slack_i = 0
    art_i = 0
    art_start = n0 + n_slack
    for typ, rr, rhs in norm:
        row = [0.0] * (n + 1)
        for j in range(n0):
            row[j] = rr[j]
        if typ == "<=":
            row[n0 + slack_i] = 1.0
            basis.append(n0 + slack_i)
            slack_i += 1
        elif typ == ">=":
            row[n0 + slack_i] = -1.0
            slack_i += 1
            row[art_start + art_i] = 1.0
            basis.append(art_start + art_i)
            art_i += 1
        else:  # ==
            row[art_start + art_i] = 1.0
            basis.append(art_start + art_i)
            art_i += 1
        row[n] = rhs
        T.append(row)

    # ---- 第一阶段：最小化人工变量之和
    c1 = [0.0] * n
    for j in range(art_start, n):
        c1[j] = 1.0
    allowed1 = [True] * n
    status, val = _simplex(T, basis, c1, allowed1, m, n, max_iter)
    if status == "unbounded":
        return LPResult("error", message="第一阶段无界（模型错误）")
    if val is None or val > 1e-6:
        return LPResult("infeasible", message="约束不可行")

    # ---- 清除仍留在基中的人工变量（值为 0 时换出或删除冗余行）
    i = 0
    while i < m:
        if basis[i] >= art_start:
            if T[i][n] > 1e-7:
                return LPResult("infeasible", message="人工变量非零")
            pivot_col = -1
            for j in range(art_start):
                if abs(T[i][j]) > 1e-8 and j not in basis:
                    pivot_col = j
                    break
            if pivot_col < 0:
                del T[i]
                del basis[i]
                m -= 1
                continue
            dummy = [0.0] * (n + 1)
            _pivot(T, dummy, i, pivot_col, m, n)
            basis[i] = pivot_col
        i += 1

    # ---- 第二阶段：原始目标，人工变量禁止进入
    c2full = [0.0] * n
    for j in range(n0):
        c2full[j] = c2[j]
    allowed2 = [True] * n
    for j in range(art_start, n):
        allowed2[j] = False
    status, val2 = _simplex(T, basis, c2full, allowed2, m, n, max_iter)
    if status != "optimal":
        return LPResult(status, message="第二阶段未得到最优解")

    x = [0.0] * n0
    for i, b in enumerate(basis):
        if b < n0:
            x[b] = T[i][n]
    x = [0.0 if abs(v) < 1e-8 else max(0.0, v) for v in x]
    x = [x[i] + shift[i] for i in range(n0)]
    value = sum(c[i] * x[i] for i in range(n0))
    return LPResult("optimal", x, value)


def maximize(c, **kwargs):
    res = minimize([-v for v in c], **kwargs)
    if res.status == "optimal":
        res.value = -res.value
    return res
