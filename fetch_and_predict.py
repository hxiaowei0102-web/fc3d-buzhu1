# -*- coding: utf-8 -*-
"""云端数据抓取 v2 —— 强化版, 多重数据源+重试+回退
输出: data.csv (issue,hundreds,tens,ones) + predict.json
"""
import csv, json, os, urllib.request, re, time, sys
from datetime import datetime, timezone

DATA_CSV = "data.csv"
PREDICT_JSON = "predict.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA_GOOGLE = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

def retry_urlopen(url, headers=None, timeout=15, tries=3):
    """带重试的urlopen"""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout)
        except Exception as e:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))

# ====== 数据源 ======

def fetch_cwl(count=10):
    """官方API - 支持多UA重试"""
    url = f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d&issueCount={count}"
    for ua in [UA, UA_GOOGLE]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Referer": "https://www.cwl.gov.cn/",
                "Accept": "application/json, text/plain, */*"
            })
            data = json.loads(urllib.request.urlopen(req, timeout=20).read())
            if data.get("result"):
                return [(r["code"], *[int(x) for x in r["red"].split(",")]) for r in data["result"]]
        except:
            continue
    raise Exception("cwl.gov.cn: 所有UA均失败")

def fetch_huiniao(count=20):
    """灰鸟API——免费"""
    url = f"https://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit={count}"
    data = json.loads(retry_urlopen(url, {"User-Agent": UA}, timeout=20).read())
    if data.get("code") != 1:
        raise Exception(f"huiniao code={data.get('code')}")
    return [(r["code"], r["one"], r["two"], r["three"]) for r in data["data"]["data"]["list"]]

def fetch_zhcw():
    """中彩网 - 网页抓取"""
    url = "https://www.zhcw.com/kjxx/3d/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        results = []
        for m in re.finditer(r"(\d{7})期.*?开奖号码.*?(\d)\D+(\d)\D+(\d)", html.replace('\n',''), re.DOTALL):
            results.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
        if results:
            return results
    except:
        pass
    raise Exception("zhcw.com 解析失败")

def fetch_500com():
    """500.com - JSON API (CDN, 可能被墙但值得尝试)"""
    # 500.com has a JSONP API
    urls = [
        "https://datachart.500.com/3d/history/newinc/history.php?start=2026195&end=2026200&limit=5",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.500.com/"})
            html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
            # Parse tab-delimited data
            results = []
            for line in html.split("\n"):
                parts = line.strip().split("\t")
                if len(parts) >= 5 and parts[0].isdigit() and len(parts[0]) == 7:
                    results.append((parts[0], int(parts[1]), int(parts[2]), int(parts[3])))
            if results:
                return results
        except:
            continue
    raise Exception("500.com 失败")


# ====== 抓取+交叉校验 ======
def fetch_with_fallback():
    sources = {
        "cwl.gov.cn": fetch_cwl,
        "huiniao.top": fetch_huiniao,
        "zhcw.com": fetch_zhcw,
        "500.com": fetch_500com,
    }
    results_by_source = {}
    for name, fn in sources.items():
        try:
            rows = fn() if "cwl" not in name else fn(10)
            if rows:
                results_by_source[name] = rows
                print(f"  ✓ {name}: {len(rows)}期, 最新{rows[0][0]}:{rows[0][1]}{rows[0][2]}{rows[0][3]}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    if not results_by_source:
        print("CRITICAL: ALL SOURCES FAILED")
        sys.exit(1)

    # 交叉校验最新一期
    from collections import Counter
    latest = {k: v[0] for k, v in results_by_source.items()}
    sig = Counter(latest.values())
    best, count = sig.most_common(1)[0]
    print(f"  → {count}/{len(results_by_source)}源一致: {best[0]}:{best[1]}{best[2]}{best[3]}")
    
    if count < 2:
        print(f"  ⚠ 仅{count}源可用, 无法交叉校验. 使用可用源数据.")

    # 合并所有源的去重数据
    all_rows = {}
    for rows in results_by_source.values():
        for r in rows:
            all_rows[r[0]] = r
    return sorted(all_rows.values(), key=lambda x: x[0])

# ====== 不组一预测(同core_v99) ======
def compute_prediction(draws):
    N = len(draws)
    cnts = []
    for t in range(N):
        row = [0]*10
        for d in [draws[t][1], draws[t][2], draws[t][3]]:
            row[d] += 1
        cnts.append(row)
    dsets = [{draws[t][1], draws[t][2], draws[t][3]} for t in range(N)]

    pf50 = [None]*N; gap_list = [None]*N; dgap_list = [None]*N
    for t in range(N):
        pf = [0]*10; g = [0]*10; dg = [0]*10
        for d in range(10):
            for k in range(1, t+1):
                if d in dsets[t-k]: g[d] = k; break
            else: g[d] = t
            for k in range(1, t+1):
                if cnts[t-k][d] >= 2: dg[d] = k; break
            else: dg[d] = t
            i0 = max(0, t-50)
            pf[d] = sum(1 for i in range(i0, t) if d in dsets[i])
        pf50[t] = pf; gap_list[t] = g; dgap_list[t] = dg

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
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ====== 主程序 ======
if __name__ == "__main__":
    print(f"=== FC3D Cloud Update v2 === {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    run_num = os.environ.get('GITHUB_RUN_NUMBER', 'local')
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    print(f"Run #{run_num}  Attempt {attempt}\n")

    # 加载已有数据
    existing = {}
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["issue"]] = (int(row["hundreds"]), int(row["tens"]), int(row["ones"]))
    print(f"Existing: {len(existing)} periods")

    print("\nFetching new data from multiple sources...")
    new_data = fetch_with_fallback()

    for r in new_data:
        existing[r[0]] = (r[1], r[2], r[3])

    all_sorted = sorted([(iss, h, t, o) for iss, (h, t, o) in existing.items()], key=lambda x: x[0])

    old_issues = set()
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                old_issues.add(row["issue"])
    new_added = [r for r in all_sorted if r[0] not in old_issues]

    with open(DATA_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue", "hundreds", "tens", "ones"])
        for r in all_sorted:
            w.writerow(r)
    print(f"\nTotal: {len(all_sorted)} periods, New: {len(new_added)}")
    for r in new_added:
        print(f"  + {r[0]}: {r[1]}{r[2]}{r[3]}")

    print("\nComputing prediction...")
    pred = compute_prediction(all_sorted)
    with open(PREDICT_JSON, "w", encoding="utf-8") as f:
        json.dump(pred, f, ensure_ascii=False, indent=2)
    print(f"Prediction: {pred['pred']} for {pred['next_issue']}")
    print(f"Last draw: {pred['last_issue']} = {pred['last_draw']}")
    print(f"Data: {pred['total']} periods total")
    print("\nDone.")
