# -*- coding: utf-8 -*-
"""algo_core.py —— 福彩3D不组预测 单一算法源（本地 + 云端共用）

不组一(同数字杀对子) 98.9% + 不组二(异数字) 95.7%
严格无前瞻：预测第 t 期只用 < t 的数据。

draws 格式: list of (issue, hundreds, tens, ones)，issue 为 7 位字符串。

这是【唯一算法源】。本地 core_v99.py 与云端 fetch_and_predict.py 都 import 本模块，
以后升级算法只改这一处，双端 pull/同步即可保持一致，不再双份维护。
字段名统一以云端为基准（回测行开奖号字段用 "draw"）。
"""
from collections import Counter

PAIRS = [(a, b) for a in range(10) for b in range(a + 1, 10)]
W, LAM, ALPHA = 100, 0.9, 0.1   # 不组二: 衰减窗口 / 衰减系数 / 个体冷度权重


def _digit_sets_and_counts(draws):
    dsets = [{h, t, o} for _, h, t, o in draws]
    cnts = [[[h, t, o].count(x) for x in range(10)] for _, h, t, o in draws]
    return dsets, cnts


def compute_features(draws):
    """计算 pf50/gap/dgap 三特征 (N×10)。严格无前瞻。"""
    N = len(draws)
    dsets, cnts = _digit_sets_and_counts(draws)
    pf50 = [[0] * 10 for _ in range(N)]
    gap = [[0] * 10 for _ in range(N)]
    dgap = [[0] * 10 for _ in range(N)]
    for t in range(N):
        for d in range(10):
            for k in range(1, t + 1):
                if d in dsets[t - k]:
                    gap[t][d] = k
                    break
            else:
                gap[t][d] = t
            for k in range(1, t + 1):
                if cnts[t - k][d] >= 2:
                    dgap[t][d] = k
                    break
            else:
                dgap[t][d] = t
            i0 = max(0, t - 50)
            pf50[t][d] = sum(1 for i in range(i0, t) if d in dsets[i])
    return pf50, gap, dgap, dsets, cnts


def predict1(pf50, gap, dgap, t):
    """不组一: 同数字两码杀对子，返回数字 d"""
    N = len(pf50)
    te = min(t, N - 1)
    scores = [pf50[te][d] / 50 - 0.004 * gap[te][d] - 0.0005 * dgap[te][d] for d in range(10)]
    for d in range(10):
        if dgap[te][d] > 100:
            scores[d] += 999
    return min(range(10), key=lambda d: scores[d])


def is_hit1(d, cnts, t):
    return cnts[t][d] < 2


def predict2(dsets, t):
    """不组二: 异数字两码，返回 (a, b) 且 a < b"""
    co = Counter()
    indiv = Counter()
    for i in range(max(0, t - W), t):
        wgt = LAM ** (t - 1 - i)
        s = dsets[i]
        for a in s:
            indiv[a] += wgt
            for b in s:
                if a < b:
                    co[(a, b)] += wgt
    if not co:
        return (0, 1)
    return min(PAIRS, key=lambda p: co.get(p, 0) + ALPHA * (indiv.get(p[0], 0) + indiv.get(p[1], 0)))


def is_hit2(pred, dsets, t):
    a, b = pred
    return not (a in dsets[t] and b in dsets[t])


def backtest(draws, n_periods=1000):
    """严格无前瞻回测。返回 {summary, rows}，字段以云端为基准。"""
    N = len(draws)
    pf50, gap, dgap, dsets, cnts = compute_features(draws)
    start = N - n_periods
    rows = []
    hits1 = hits2 = 0
    for t in range(start, N):
        d1 = predict1(pf50, gap, dgap, t)
        h1 = is_hit1(d1, cnts, t)
        hits1 += h1
        p2 = predict2(dsets, t)
        h2 = is_hit2(p2, dsets, t)
        hits2 += h2
        issue, hh, tt, oo = draws[t]
        rows.append({
            "issue": issue, "draw": f"{hh}{tt}{oo}",
            "pred1": f"{d1}-{d1}", "hit1": h1,
            "pred2": f"{p2[0]}-{p2[1]}", "hit2": h2,
        })
    cum1 = cum2 = 0
    for i, r in enumerate(rows):
        cum1 += r["hit1"]
        cum2 += r["hit2"]
        r["cum1"] = round(cum1 / (i + 1) * 100, 1)
        r["cum2"] = round(cum2 / (i + 1) * 100, 1)
    return {
        "summary": {
            "periods": n_periods,
            "acc1": round(hits1 / n_periods * 100, 1),
            "hits1": hits1, "misses1": n_periods - hits1,
            "acc2": round(hits2 / n_periods * 100, 1), "hits2": hits2,
        },
        "rows": rows,
    }


def predict_next(draws):
    """预测下一期。返回 dict，字段以云端为基准。"""
    N = len(draws)
    pf50, gap, dgap, dsets, cnts = compute_features(draws)
    d1 = predict1(pf50, gap, dgap, N)
    p2 = predict2(dsets, N)
    issue, hh, tt, oo = draws[-1]
    year, num = int(issue[:4]), int(issue[4:])
    if num >= 999:  # 跨年安全: 满999进下一年001
        year += 1
        num = 0
    return {
        "next_issue": f"{year}{num + 1:03d}",
        "pred1": f"{d1}-{d1}", "meaning1": f"数字{d1}不会重复出现(对子)",
        "pred2": f"{p2[0]}-{p2[1]}", "meaning2": f"数字{p2[0]}和{p2[1]}不同时出现",
        "last_issue": issue, "last_draw": f"{hh}{tt}{oo}",
    }


if __name__ == "__main__":
    import csv, json, sys
    sys.stdout.reconfigure(encoding="utf-8")
    with open(r"D:\福彩3D资料\fc3d-history.csv", encoding="utf-8") as f:
        draws = [(r["issue"], int(r["hundreds"]), int(r["tens"]), int(r["ones"]))
                 for r in csv.DictReader(f)]
    draws.sort(key=lambda d: d[0])
    bt = backtest(draws, 1000)
    s = bt["summary"]
    print(f"不组一(同数字): {s['acc1']}%  命中{s['hits1']}/失误{s['misses1']}")
    print(f"不组二(异数字): {s['acc2']}%  命中{s['hits2']}")
    print("下一期:", json.dumps(predict_next(draws), ensure_ascii=False))
