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
    """2. apihz API (带key鉴权, key从环境变量APIHZ_KEY读取, 避免硬编码泄露)"""
    import os
    K = os.environ.get("APIHZ_KEY", "")
    if not K:  # 无key时跳过(避免404噪音)
        raise Exception("无APIHZ_KEY")
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


# ====== 不组一 + 不组二 双路预测 (算法统一走 algo_core.py) ======
def compute_predictions(draws):
    from algo_core import predict_next, backtest
    N = len(draws)
    pred = predict_next(draws)
    back_n = min(100, N - 1)
    bt = backtest(draws, back_n)
    bt["rows"].reverse()  # 云端最新在前
    pred["total"] = N
    pred["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pred["backtest"] = {
        "periods": bt["summary"]["periods"],
        "acc1": bt["summary"]["acc1"], "acc2": bt["summary"]["acc2"],
        "hits1": bt["summary"]["hits1"], "hits2": bt["summary"]["hits2"],
        "rows": bt["rows"],
    }
    return pred


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
