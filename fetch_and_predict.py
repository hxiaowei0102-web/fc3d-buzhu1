# -*- coding: utf-8 -*-
"""云端数据抓取 —— GitHub Actions专用, 纯标准库, 多重数据源
输出: data.csv (issue,hundreds,tens,ones) + predict.json
"""
import csv, json, os, urllib.request, re, time, sys
from datetime import datetime

DATA_CSV = "data.csv"
PREDICT_JSON = "predict.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ====== 数据源(按顺序尝试) ======

def fetch_cwl(count=10):
    """官方API"""
    url = f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d&issueCount={count}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.cwl.gov.cn/"})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return [(r["code"], *[int(x) for x in r["red"].split(",")]) for r in data.get("result", [])]

def fetch_huiniao(count=20):
    """灰鸟API——免费, JSON"""
    url = f"https://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit={count}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if data.get("code") != 1:
        raise Exception(f"huiniao code={data.get('code')}")
    return [(r["code"], r["one"], r["two"], r["three"]) for r in data["data"]["data"]["list"]]

def fetch_cjcp():
    """彩经网HTML"""
    url = "https://www.cjcp.cn/kaijiang/3d/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
    html_one = html.replace('\n', ' ')
    results = []
    for m in re.finditer(r"(\d{7})期.*?(\d)\s+(\d)\s+(\d)", html_one):
        results.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    return results

def fetch_gdfc():
    """广东福彩"""
    url = "https://www.gdfc.org.cn/play_list_game_6.html"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
    results = []
    for m in re.finditer(r"2026(\d{3})\s+(\d)\s+(\d)\s+(\d)", html):
        results.append((f"2026{m.group(1)}", int(m.group(2)), int(m.group(3)), int(m.group(4))))
    return results


# ====== 抓取+交叉校验 ======
def fetch_with_fallback():
    sources = {
        "cwl.gov.cn": fetch_cwl,
        "huiniao.top": lambda: fetch_huiniao(15),
        "cjcp.cn": fetch_cjcp,
        "gdfc.org.cn": fetch_gdfc,
    }
    results_by_source = {}
    for name, fn in sources.items():
        try:
            rows = fn()
            if rows:
                results_by_source[name] = rows
                print(f"  ✓ {name}: {len(rows)}期, 最新{rows[0][0]}:{rows[0][1]}{rows[0][2]}{rows[0][3]}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    if not results_by_source:
        print("ALL SOURCES FAILED")
        sys.exit(1)

    # 交叉校验最新一期
    from collections import Counter
    latest = {k: v[0] for k, v in results_by_source.items()}
    sig = Counter(latest.values())
    best, count = sig.most_common(1)[0]
    print(f"  → {count}/{len(results_by_source)}源一致: {best[0]}:{best[1]}{best[2]}{best[3]}")

    # 合并所有源的去重数据
    all_rows = {}
    for rows in results_by_source.values():
        for r in rows:
            all_rows[r[0]] = r
    return sorted(all_rows.values(), key=lambda x: x[0])


# ====== 不组一预测(同core_v99, 纯标准库) ======
def compute_prediction(draws):
    """输入: list of (issue, h, t, o), 按issue升序"""
    N = len(draws)
    digit_sets = [{r[1], r[2], r[3]} for r in draws]
    cnts = [[draws[t].count(x+1) for x in range(10)] for t in range(N)]  # FIX
    cnts = []; 
    for t in range(N):
        row = [0]*10
        for d in [draws[t][1], draws[t][2], draws[t][3]]:
            row[d] += 1
        cnts.append(row)
    digit_sets2 = [{draws[t][1], draws[t][2], draws[t][3]} for t in range(N)]

    pf50 = [None]*N; gap_list = [None]*N; dgap_list = [None]*N
    for t in range(N):
        pf = [0]*10; g = [0]*10; dg = [0]*10
        for d in range(10):
            for k in range(1, t+1):
                if d in digit_sets2[t-k]: g[d] = k; break
            else: g[d] = t
            for k in range(1, t+1):
                if cnts[t-k][d] >= 2: dg[d] = k; break
            else: dg[d] = t
            i0 = max(0, t-50)
            pf[d] = sum(1 for i in range(i0, t) if d in digit_sets2[i])
        pf50[t] = pf; gap_list[t] = g; dgap_list[t] = dg

    t = N
    s = [0]*10
    for d in range(10):
        s[d] = pf50[N-1][d]/50 - 0.004*gap_list[N-1][d] - 0.0005*dgap_list[N-1][d]
        if dgap_list[N-1][d] > 100:
            s[d] += 999
    pred_digit = min(range(10), key=lambda d: s[d])

    last = draws[-1]
    year, num = last[0][:4], int(last[0][4:])
    next_issue = f"{year}{num+1:03d}"
    return {
        "next_issue": next_issue,
        "pred": f"{pred_digit}-{pred_digit}",
        "meaning": f"数字{pred_digit}不会重复出现(对子)",
        "last_issue": last[0],
        "last_draw": f"{last[1]}{last[2]}{last[3]}",
        "total": N,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
    }


# ====== 主程序 ======
if __name__ == "__main__":
    print(f"=== FC3D Cloud Update === {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Run #{os.environ.get('GITHUB_RUN_NUMBER', 'local')}\n")

    # 加载已有数据
    existing = {}
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["issue"]] = (int(row["hundreds"]), int(row["tens"]), int(row["ones"]))
    print(f"Existing: {len(existing)} periods")

    print("\nFetching new data from multiple sources...")
    new_data = fetch_with_fallback()

    # 合并: 新数据覆盖已有(以防数据修正)
    for r in new_data:
        existing[r[0]] = (r[1], r[2], r[3])

    # 转为排序列表
    all_sorted = sorted([(iss, h, t, o) for iss, (h, t, o) in existing.items()], key=lambda x: x[0])
    added = len(all_sorted) - (len(existing) - len(new_data) + len(new_data))
    # 简单统计
    new_count = sum(1 for r in new_data if r[0] not in {x[0] for x in all_sorted[:-len(new_data)]})
    # 直接统计新增
    old_issues = set()
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                old_issues.add(row["issue"])
    new_added = [r for r in all_sorted if r[0] not in old_issues]

    # 保存完整CSV
    with open(DATA_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue", "hundreds", "tens", "ones"])
        for r in all_sorted:
            w.writerow(r)
    print(f"\nTotal: {len(all_sorted)} periods, New: {len(new_added)}")
    if new_added:
        for r in new_added:
            print(f"  + {r[0]}: {r[1]}{r[2]}{r[3]}")

    # 算预测
    print("\nComputing prediction...")
    pred = compute_prediction(all_sorted)
    with open(PREDICT_JSON, "w", encoding="utf-8") as f:
        json.dump(pred, f, ensure_ascii=False, indent=2)
    print(f"Prediction: {pred['pred']} for {pred['next_issue']}")
    print(f"Last draw: {pred['last_issue']} = {pred['last_draw']}")
    print("\nDone.")
