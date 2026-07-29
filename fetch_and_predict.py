# -*- coding: utf-8 -*-
"""云端数据抓取 v3 —— 参考百十个项目6源体系, 强化版
输出: data.csv (issue,hundreds,tens,ones) + predict.json
"""
import csv, json, os, re, time, sys
from datetime import datetime, timezone
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

DATA_CSV = "data.csv"
PREDICT_JSON = "predict.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def http_get(url, timeout=15):
    """requests 优先, urllib 回退"""
    if HAS_REQUESTS:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
        except:
            pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except:
        pass
    return None

# ====== 7数据源(参考百十个项目) ======

def fetch_huiniao():
    """灰鸟API — 免费, JSON, 最稳定"""
    url = "https://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=5"
    text = http_get(url, timeout=20)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    if data.get("code") != 1: raise Exception(f"code={data.get('code')}")
    return [(r["code"], r["one"], r["two"], r["three"]) for r in data["data"]["data"]["list"]]

def fetch_cwl(count=10):
    """官方API — 可能被限, 作为补充"""
    url = f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d&issueCount={count}"
    text = http_get(url, timeout=20)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    if not data.get("result"): raise Exception("无数据")
    return [(r["code"], *[int(x) for x in r["red"].split(",")]) for r in data["result"]]

def fetch_apihz():
    """apihz.cn API — 免费, 稳定备用"""
    url = "https://api.apihz.cn/api/kaijiang/fc3d/list.php?key=5d6f8a9b2c1e4f7a3b8d9c0e1f2a3b4c&num=5"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    items = data.get("data", {}).get("data", [])
    if not items: raise Exception("无数据")
    results = []
    for item in items:
        nums = item.get("result", "").split(" ")
        if len(nums) >= 3:
            results.append((item["code"], int(nums[0]), int(nums[1]), int(nums[2])))
    return results

def fetch_8200():
    """8200.cn API"""
    url = "https://api.8200.cn/hall/fc3d/getFc3dLotteryList?pageNo=1&pageSize=5"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    items = data.get("data", {}).get("list", [])
    if not items: raise Exception("无数据")
    results = []
    for item in items:
        nums = item.get("openCode", "").split(",")
        if len(nums) >= 3:
            results.append((item.get("periodNo", ""), int(nums[0]), int(nums[1]), int(nums[2])))
    return results

def fetch_55128():
    """55128.cn 网页抓取"""
    url = "https://www.55128.cn/kjh/fcsd-history-61.htm"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    results = []
    for m in re.finditer(r'(\d{7})\s*</td>\s*<td[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>\s*<td[^>]*>.*?(\d).*?(\d).*?(\d).*?</td>', text, re.DOTALL):
        results.append((m.group(1), int(m.group(3)), int(m.group(4)), int(m.group(5))))
    if not results:
        # 备选模式
        for m in re.finditer(r'(\d{7}).*?(\d)\s+(\d)\s+(\d)', text, re.DOTALL):
            results.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if not results: raise Exception("解析失败")
    return results

def fetch_zhcw():
    """中彩网 zhcw.com"""
    url = "https://www.zhcw.com/kjxx/fc3d/"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    results = []
    for m in re.finditer(r'(\d{7})期.*?(\d)\s*(\d)\s*(\d)', text.replace('\n',' '), re.DOTALL):
        results.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if not results: raise Exception("解析失败")
    return results

def fetch_caijing():
    """彩经网 cjcp.com.cn"""
    url = "https://www.cjcp.com.cn/kaijiang/fc3d/"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    results = []
    for m in re.finditer(r'(\d{7})\s*期.*?(\d)\s+(\d)\s+(\d)', text, re.DOTALL):
        results.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if not results: raise Exception("解析失败")
    return results

# ====== 抓取+交叉校验 ======
def fetch_with_fallback():
    sources = {
        "huiniao.top": fetch_huiniao,
        "cwl.gov.cn": lambda: fetch_cwl(10),
        "apihz.cn": fetch_apihz,
        "8200.cn": fetch_8200,
        "55128.cn": fetch_55128,
        "zhcw.com": fetch_zhcw,
        "caijing.com": fetch_caijing,
    }
    results_by_source = {}
    for name, fn in sources.items():
        try:
            rows = fn()
            if rows:
                results_by_source[name] = rows
                print(f"  ✓ {name}: {len(rows)}期, 最新{rows[0][0]}:{rows[0][1]}{rows[0][2]}{rows[0][3]}")
        except Exception as e:
            print(f"  ✗ {name}: {str(e)[:80]}")

    if not results_by_source:
        print("CRITICAL: ALL SOURCES FAILED")
        sys.exit(1)

    from collections import Counter
    latest = {k: v[0] for k, v in results_by_source.items()}
    sig = Counter(latest.values())
    best, count = sig.most_common(1)[0]
    print(f"  → {count}/{len(results_by_source)}源一致: {best[0]}:{best[1]}{best[2]}{best[3]}")
    if count < 2:
        print(f"  ⚠ 仅{count}源可用, 无法交叉校验")

    all_rows = {}
    for rows in results_by_source.values():
        for r in rows:
            all_rows[r[0]] = r
    return sorted(all_rows.values(), key=lambda x: x[0])


# ====== 不组一预测(同core_v99) ======
def compute_prediction(draws):
    N = len(draws)
    cnts = [[0]*10 for _ in range(N)]
    for t in range(N):
        for d in [draws[t][1], draws[t][2], draws[t][3]]:
            cnts[t][d] += 1
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

    # 当前预测
    s = [0]*10
    for d in range(10):
        s[d] = pf50[N-1][d]/50 - 0.004*gap_list[N-1][d] - 0.0005*dgap_list[N-1][d]
        if dgap_list[N-1][d] > 100: s[d] += 999
    pred_digit = min(range(10), key=lambda d: s[d])

    # 近100期回测
    back_n = min(100, N-1)
    bt_start = N - back_n
    bt_rows = []
    hits = 0
    cum_hits = 0
    for t in range(bt_start, N):
        sd = [0]*10
        for d in range(10):
            sd[d] = pf50[t][d]/50 - 0.004*gap_list[t][d] - 0.0005*dgap_list[t][d]
            if dgap_list[t][d] > 100: sd[d] += 999
        picked = min(range(10), key=lambda d: sd[d])
        actual_digits = [draws[t][1], draws[t][2], draws[t][3]]
        hit = cnts[t][picked] < 2
        if hit: hits += 1
        cum_hits += 1
        if draw_str := ''.join(str(x) for x in actual_digits):
            pass
        bt_rows.append({
            "issue": draws[t][0],
            "draw": f"{draws[t][1]}{draws[t][2]}{draws[t][3]}",
            "pred": f"{picked}-{picked}",
            "hit": hit,
            "cum": round(hits/(t-bt_start+1)*100, 1)
        })
    bt_rows.reverse()  # 近期在前

    last = draws[-1]
    year, num = last[0][:4], int(last[0][4:])
    return {
        "next_issue": f"{year}{num+1:03d}", "pred": f"{pred_digit}-{pred_digit}",
        "meaning": f"数字{pred_digit}不会重复出现(对子)",
        "last_issue": last[0], "last_draw": f"{last[1]}{last[2]}{last[3]}",
        "total": N, "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "backtest": {"periods": back_n, "acc": round(hits/back_n*100, 1), "hits": hits, "rows": bt_rows}
    }


if __name__ == "__main__":
    import urllib.request  # for fallback in http_get
    print(f"=== FC3D Cloud Update v3 === {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"requests: {'available' if HAS_REQUESTS else 'unavailable (urllib fallback)'}")
    run_num = os.environ.get('GITHUB_RUN_NUMBER', 'local')
    print(f"Run #{run_num}\n")

    existing = {}
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["issue"]] = (int(row["hundreds"]), int(row["tens"]), int(row["ones"]))
    print(f"Existing: {len(existing)} periods")

    print("\nFetching from 7 sources...")
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
        w = csv.writer(f); w.writerow(["issue", "hundreds", "tens", "ones"])
        for r in all_sorted: w.writerow(r)
    print(f"\nTotal: {len(all_sorted)} periods, New: {len(new_added)}")
    for r in new_added: print(f"  + {r[0]}: {r[1]}{r[2]}{r[3]}")

    print("\nComputing prediction...")
    pred = compute_prediction(all_sorted)
    with open(PREDICT_JSON, "w", encoding="utf-8") as f:
        json.dump(pred, f, ensure_ascii=False, indent=2)
    print(f"Prediction: {pred['pred']} for {pred['next_issue']}")
    print(f"Last draw: {pred['last_issue']} = {pred['last_draw']}")
    print(f"Data: {pred['total']} periods total")
    print("\nDone.")
