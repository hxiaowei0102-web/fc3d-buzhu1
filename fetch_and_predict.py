# -*- coding: utf-8 -*-
"""云端数据抓取 v5 —— 参考百十个项目6源体系
输出: data.csv (issue,hundreds,tens,ones) + predict.json
"""
import csv, json, os, urllib.request, re, sys
from datetime import datetime, timezone
from collections import Counter
try:
    import requests as reqs
    HAS_REQS = True
except ImportError:
    HAS_REQS = False

DATA_CSV = "data.csv"
PREDICT_JSON = "predict.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def http_get(url, timeout=15):
    """requests 优先, urllib 回退 (同百十个)"""
    if HAS_REQS:
        try:
            r = reqs.get(url, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
        except: pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except: pass
    return None

# ====== 数据源 (参考老板清单: 灰鸟/17500/apihz/中彩) ======

def fetch_17500():
    """0. 17500.cn 官方级全量TXT (2002至今, 权威基准, 带全历史)"""
    url = "https://www.17500.cn/getData/3d.TXT"
    text = http_get(url, timeout=30)
    if not text: raise Exception("无响应")
    results = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0].isdigit() and len(parts[0]) == 7:
            try:
                results.append((parts[0], int(parts[2]), int(parts[3]), int(parts[4])))
            except: continue
    if not results: raise Exception("解析失败")
    results.sort(key=lambda x: int(x[0]))  # 期号升序
    return results

def fetch_huiniao(count=5):
    """1. 灰鸟API (HTTP, 非HTTPS!, 带next_code跨年安全)"""
    url = f"http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit={count}"
    text = http_get(url, timeout=20)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    if data.get("code") != 1: raise Exception(f"code={data.get('code')}")
    return [(r["code"], r["one"], r["two"], r["three"]) for r in data["data"]["data"]["list"]]

def fetch_apihz(count=5):
    """2. apihz API (带key鉴权)"""
    K = "5d6f8a9b2c1e4f7a3b8d9c0e1f2a3b4c"
    url = f"https://api.apihz.cn/api/kaijiang/fc3d/list.php?key={K}&num={count}"
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

def fetch_zhcw():
    """3. 中彩网 (福彩官方)"""
    url = "https://www.zhcw.com/kjxx/fc3d/"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    m = re.search(r'<em>(\d{7})</em>.*?<em>(\d{4}-\d{2}-\d{2})</em>.*?<i>(\d)</i>\s*<i>(\d)</i>\s*<i>(\d)</i>', text, re.DOTALL)
    if not m:
        m = re.search(r'(\d{7})期.*?(\d{4}-\d{2}-\d{2}).*?(\d)\s*(\d)\s*(\d)', text, re.DOTALL)
    if not m: raise Exception("解析失败")
    return [(m.group(1), int(m.group(3)), int(m.group(4)), int(m.group(5)))]

def fetch_8200(count=5):
    """4. 8200.cn API"""
    url = f"https://api.8200.cn/hall/fc3d/getFc3dLotteryList?pageNo=1&pageSize={count}"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    data = json.loads(text)
    if data.get("code") != 0: raise Exception(f"code={data.get('code')}")
    items = data.get("data", {}).get("list", [])
    if not items: raise Exception("无数据")
    results = []
    for item in items:
        nums = item.get("openCode", "").split(",")
        if len(nums) >= 3:
            results.append((item.get("periodNo", ""), int(nums[0]), int(nums[1]), int(nums[2])))
    return results

def fetch_55128():
    """5. 55128.cn HTML"""
    url = "https://www.55128.cn/kjh/fcsd-history-61.htm"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    m = re.search(r'<tr[^>]*>\s*<td[^>]*>(\d{7})</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>\s*(?:<span[^>]*>)\s*(\d)\s*(?:</span>)\s*(?:<span[^>]*>)\s*(\d)\s*(?:</span>)\s*(?:<span[^>]*>)\s*(\d)', text)
    if not m:
        m = re.search(r'(\d{7}).*?(\d{4}-\d{2}-\d{2}).*?(\d)\s+(\d)\s+(\d)', text, re.DOTALL)
    if not m: raise Exception("解析失败")
    return [(m.group(1), int(m.group(3)), int(m.group(4)), int(m.group(5)))]

def fetch_caijing():
    """6. 彩经网 cjcp.com.cn"""
    url = "https://www.cjcp.com.cn/kaijiang/fc3d/"
    text = http_get(url, timeout=15)
    if not text: raise Exception("无响应")
    m = re.search(r'(\d{7})\s*期.*?(\d{4}-\d{2}-\d{2}).*?<span[^>]*?class="[^"]*?ball[^"]*?"[^>]*?>\s*(\d)\s*</span>\s*<span[^>]*?class="[^"]*?ball[^"]*?"[^>]*?>\s*(\d)\s*</span>\s*<span[^>]*?class="[^"]*?ball[^"]*?"[^>]*?>\s*(\d)', text, re.DOTALL)
    if not m:
        m = re.search(r'(\d{7}).*?(\d{4}-\d{2}-\d{2}).*?(\d)\D+(\d)\D+(\d)', text, re.DOTALL)
    if not m: raise Exception("解析失败")
    return [(m.group(1), int(m.group(3)), int(m.group(4)), int(m.group(5)))]

# ====== 抓取+交叉校验 ======
def fetch_with_fallback():
    sources = {
        "17500.cn(全量)": fetch_17500,
        "huiniao.top": fetch_huiniao,
        "apihz.cn": fetch_apihz,
        "zhcw.com": fetch_zhcw,
        "8200.cn": fetch_8200,
        "55128.cn": fetch_55128,
        "caijing.com": fetch_caijing,
    }
    results_by_source = {}
    for name, fn in sources.items():
        try:
            rows = fn()
            if rows:
                results_by_source[name] = rows
                rows.sort(key=lambda x: int(x[0]))  # 统一期号升序
                latest = rows[-1]  # 最新一期
                print(f"  + {name}: {len(rows)}条, 最新{latest[0]}:{latest[1]}{latest[2]}{latest[3]}")
        except Exception as e:
            print(f"  - {name}: {str(e)[:60]}")

    if not results_by_source:
        print("ALL SOURCES FAILED")
        sys.exit(1)

    from collections import Counter
    latest = {k: v[-1] for k, v in results_by_source.items()}
    best, count = Counter(latest.values()).most_common(1)[0]
    print(f"  -> {count}/{len(results_by_source)}源一致: {best[0]}:{best[1]}{best[2]}{best[3]}")
    if count < 2:
        print(f"  WARN: only {count} source(s) available")

    all_rows = {}
    for rows in results_by_source.values():
        for r in rows:
            all_rows[r[0]] = r
    return sorted(all_rows.values(), key=lambda x: int(x[0]))


# ====== 不组一 + 不组二 双路预测 ======
PAIRS = [(a, b) for a in range(10) for b in range(a + 1, 10)]

def compute_predictions(draws):
    N = len(draws)
    cnts = [[0]*10 for _ in range(N)]
    for t in range(N):
        for d in [draws[t][1], draws[t][2], draws[t][3]]:
            cnts[t][d] += 1
    dsets = [{draws[t][1], draws[t][2], draws[t][3]} for t in range(N)]

    pf50 = [None]*N; gap = [None]*N; dgap = [None]*N
    for t in range(N):
        pf = [0]*10; g = [0]*10; dg = [0]*10
        for d in range(10):
            for k in range(1, t+1):
                if d in dsets[t-k]: g[d] = k; break
            else: g[d] = t
            for k in range(1, t+1):
                if cnts[t-k][d] >= 2: dg[d] = k; break
            else: dg[d] = t
            i0 = max(0, t-50); pf[d] = sum(1 for i in range(i0, t) if d in dsets[i])
        pf50[t] = pf; gap[t] = g; dgap[t] = dg

    # 不组一
    s1 = [pf50[N-1][d]/50 - 0.004*gap[N-1][d] - 0.0005*dgap[N-1][d] for d in range(10)]
    for d in range(10):
        if dgap[N-1][d] > 100: s1[d] += 999
    d1 = min(range(10), key=lambda d: s1[d])

    # 不组二: 异数字
    W, LAM, ALPHA = 100, 0.9, 0.1
    co = Counter(); ind = Counter()
    for i in range(max(0, N-W), N):
        wgt = LAM ** (N-1-i)
        s = dsets[i]
        for a in s:
            ind[a] += wgt
            for b in s:
                if a < b: co[(a,b)] += wgt
    d2 = min(PAIRS, key=lambda p: co.get(p, 0) + ALPHA * (ind.get(p[0], 0) + ind.get(p[1], 0)))

    # 近100期回测
    back_n = min(100, N-1); bt_start = N - back_n; bt_rows = []
    hits1 = hits2 = 0
    for t in range(bt_start, N):
        sd = [pf50[t][d]/50 - 0.004*gap[t][d] - 0.0005*dgap[t][d] for d in range(10)]
        for d in range(10):
            if dgap[t][d] > 100: sd[d] += 999
        pick1 = min(range(10), key=lambda d: sd[d])
        h1 = cnts[t][pick1] < 2; hits1 += h1

        co2 = Counter(); ind2 = Counter()
        for i in range(max(0, t-W), t):
            wgt = LAM ** (t-1-i)
            s = dsets[i]
            for a in s:
                ind2[a] += wgt
                for b in s:
                    if a < b: co2[(a,b)] += wgt
        pick2 = min(PAIRS, key=lambda p: co2.get(p, 0) + ALPHA * (ind2.get(p[0], 0) + ind2.get(p[1], 0)))
        h2 = pick2[0] not in dsets[t] or pick2[1] not in dsets[t]; hits2 += h2

        bt_rows.append({
            "issue": draws[t][0], "draw": f"{draws[t][1]}{draws[t][2]}{draws[t][3]}",
            "pred1": f"{pick1}-{pick1}", "hit1": h1,
            "pred2": f"{pick2[0]}-{pick2[1]}", "hit2": h2,
            "cum1": round(hits1/(t-bt_start+1)*100,1), "cum2": round(hits2/(t-bt_start+1)*100,1)
        })
    bt_rows.reverse()

    last = draws[-1]
    year, num = last[0][:4], int(last[0][4:])
    return {
        "next_issue": f"{year}{num+1:03d}",
        "pred1": f"{d1}-{d1}", "meaning1": f"数字{d1}不会重复出现(对子)",
        "pred2": f"{d2[0]}-{d2[1]}", "meaning2": f"数字{d2[0]}和{d2[1]}不同时出现",
        "last_issue": last[0], "last_draw": f"{last[1]}{last[2]}{last[3]}",
        "total": N, "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "backtest": {"periods": back_n, "acc1": round(hits1/back_n*100,1), "acc2": round(hits2/back_n*100,1),
                     "hits1": hits1, "hits2": hits2, "rows": bt_rows}
    }


if __name__ == "__main__":
    print(f"=== FC3D Cloud v5 === {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"requests: {'OK' if HAS_REQS else 'NO'}\n")

    existing = {}
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["issue"]] = (int(row["hundreds"]), int(row["tens"]), int(row["ones"]))
    print(f"Existing: {len(existing)} periods")

    print("\nFetching (7-source fallback, 17500全量优先)...")
    new_data = fetch_with_fallback()
    for r in new_data: existing[r[0]] = (r[1], r[2], r[3])

    all_sorted = sorted([(iss, h, t, o) for iss, (h, t, o) in existing.items()], key=lambda x: x[0])
    old = set()
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f): old.add(row["issue"])
    added = [r for r in all_sorted if r[0] not in old]

    with open(DATA_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["issue", "hundreds", "tens", "ones"])
        for r in all_sorted: w.writerow(r)
    print(f"\nTotal: {len(all_sorted)}, New: {len(added)}")
    for r in added: print(f"  + {r[0]}: {r[1]}{r[2]}{r[3]}")

    print("\nPredicting...")
    pred = compute_predictions(all_sorted)
    with open(PREDICT_JSON, "w", encoding="utf-8") as f:
        json.dump(pred, f, ensure_ascii=False, indent=2)
    print(f"  不组一: {pred['pred1']} ({pred['meaning1']})")
    print(f"  不组二: {pred['pred2']} ({pred['meaning2']})")
    print(f"  Backtest {pred['backtest']['periods']}: {pred['backtest']['acc1']}% / {pred['backtest']['acc2']}%")
    print("Done.")
