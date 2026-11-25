"""二游抽卡概率的精确计算（动态规划，不是蒙特卡洛）。

只用 Python 标准库。运行 `python 抽卡计算_Claude.py` 打印文档里所有【计算】表格；加 `--charts img` 同时生成配图（需要 matplotlib）。

模型分两层：
1. 稀有度层：距上次出最高稀有度已经抽了 k 抽时，第 k 抽出最高稀有度的概率 p(k)。
   由基础概率、软保底分段、硬保底决定。
2. UP 层：出了最高稀有度之后，是不是 UP、下一次有没有保证。用一个小状态机表示。
另外支持「井」（抽满 S 次换一个 UP）。
默认从保底计数 0、无大保底的状态开始，所有抽数都在同一个池子里。
"""
from collections import defaultdict
import math
import sys


# ---------- 稀有度层 ----------

def pity_curve(base, hard, segments=()):
    """返回 p[0..hard]，p[k] 是距上次出货第 k 抽的出货概率（p[0] 不用）。

    segments: [(start, inc, end), ...]。从第 start 抽起每抽比上一抽多 inc，
    到第 end 抽为止（end=None 表示一直加）。hard 抽必出（hard=None 表示没有硬保底，
    此时数组长度取 1 万抽，最后一格也不强制为 1）。
    """
    n = hard if hard else 10000
    p = [0.0] * (n + 1)
    for k in range(1, n + 1):
        v = base
        for start, inc, end in segments:
            if k >= start:
                last = k if end is None else min(k, end)
                v += inc * (last - start + 1)
        p[k] = min(v, 1.0)
    if hard:
        p[hard] = 1.0
    return p


def top_distribution(p):
    """出一次最高稀有度需要的抽数 N 的分布：dist[k] = P(N = k)。"""
    dist = [0.0] * len(p)
    survive = 1.0
    for k in range(1, len(p)):
        dist[k] = survive * p[k]
        survive *= 1 - p[k]
        if survive < 1e-15:
            break
    return dist


def stats(dist, extra_mass_at_end=0.0):
    """分布的期望、标准差和分位数。dist[n] = P(恰好第 n 抽达成)。"""
    total = sum(dist)
    mean = sum(n * q for n, q in enumerate(dist))
    var = sum(n * n * q for n, q in enumerate(dist)) - mean * mean
    out = {"mean": mean, "sd": math.sqrt(max(var, 0.0)), "mass": total}
    cdf = 0.0
    marks = [0.1, 0.5, 0.9, 0.99]
    i = 0
    for n, q in enumerate(dist):
        cdf += q
        while i < len(marks) and cdf >= marks[i] - 1e-12:
            out[f"p{int(marks[i] * 100)}"] = n
            i += 1
    out["max"] = max((n for n, q in enumerate(dist) if q > 1e-12), default=0)
    return out


def comprehensive_rate(p):
    """综合概率 = 1 / E[N]，长期平均每抽出最高稀有度的比例。"""
    d = top_distribution(p)
    return 1 / sum(k * q for k, q in enumerate(d))


# ---------- UP 层 ----------
# 状态机：state -> [(概率, 是否是目标 UP, 下一个状态), ...]

def chain_guarantee(q):
    """q 概率是目标 UP；没中则下一次必定是目标（原神角色池式 50/50 + 大保底）。"""
    return {"free": [(q, True, "free"), (1 - q, False, "guar")],
            "guar": [(1.0, True, "free")]}


def chain_plain(q):
    """每次出最高稀有度都独立地有 q 概率是目标，没有大保底。"""
    return {"free": [(q, True, "free"), (1 - q, False, "free")]}


def chain_always():
    return {"free": [(1.0, True, "free")]}


def chain_radiance(capture_by_losses, q=0.5):
    """原神 5.0 后角色池：小保底歪了时，按「连续歪的次数」有一定概率触发捕获明光。

    capture_by_losses[i]：已经连续歪了 i 次时，这次本该歪的结果被改成 UP 的概率。
    状态 (i, guar)：i = 连续歪次数（计数器），guar = 是否在大保底。
    这里的计数规则是社区推测，不是官方公布的，见文档说明。
    """
    m = len(capture_by_losses) - 1
    ch = {}
    for i in range(m + 1):
        cap = capture_by_losses[i]
        # 小保底：q 直接中；(1-q) 本该歪，其中 cap 被明光捕获
        # 中了（含捕获）计数器怎么变是社区推测：直接中 → 计数器减 1（不低于 0），被捕获 → 归零
        ch[(i, False)] = [
            (q, True, (max(i - 1, 0), False)),
            ((1 - q) * cap, True, (0, False)),
            ((1 - q) * (1 - cap), False, (min(i + 1, m), True)),
        ]
        ch[(i, True)] = [(1.0, True, (i, False))]
    return ch


# ---------- 合成：拿到 K 个目标 UP 要多少抽 ----------

def pulls_to_copies(p, chain, start, copies=1, spark=None, spark_mode="repeat",
                    max_pulls=20000, eps=1e-13):
    """返回 dist[n] = 恰好在第 n 抽凑齐 copies 个目标 UP 的概率。

    spark: 井的抽数 S。spark_mode:
      "repeat"       每抽满 S 次可换 1 个目标（蔚蓝档案、赛马娘、NIKKE 式）
      "once_if_none" 抽满 S 次还没拿到目标时直接给 1 个，只生效一次（FGO 330 式）
    """
    hard_len = len(p) - 1
    cur = {(0, start, 0): 1.0}
    dist = [0.0]
    for n in range(1, max_pulls + 1):
        nxt = defaultdict(float)
        for (pity, s, c), pr in cur.items():
            k = pity + 1
            ph = p[k] if k <= hard_len else p[hard_len]
            if ph < 1.0:
                nxt[(min(pity + 1, hard_len), s, c)] += pr * (1 - ph)
            if ph > 0.0:
                for q, feat, ns in chain[s]:
                    if q > 0:
                        nxt[(0, ns, c + (1 if feat else 0))] += pr * ph * q
        done = 0.0
        cur = {}
        for (pity, s, c), pr in nxt.items():
            cc = c
            if spark and spark_mode == "once_if_none" and n == spark and c == 0:
                cc = 1
            have = cc + (n // spark if spark and spark_mode == "repeat" else 0)
            if have >= copies:
                done += pr
            else:
                cur[(pity, s, cc)] = cur.get((pity, s, cc), 0.0) + pr
        dist.append(done)
        if sum(cur.values()) < eps:
            break
    return dist


def fmt_pct(x, d=2):
    return f"{x * 100:.{d}f}%"


# ---------- 各游戏模型（参数见文档第 4 节，软保底多为社区模型） ----------

def jump(base, start, val, hard):
    """从第 start 抽起单抽概率直接跳到 val（异环式）。"""
    p = pity_curve(base, hard)
    for k in range(start, hard):
        p[k] = val
    return p


def ba_charge():
    """蔚蓝档案 2026 新规则：PU 0.7%；第 100 抽必出 ★3 且 50% 为 PU；第 200 抽必得 PU；只有出 PU 才重置。"""
    p = [0.0] + [0.007] * 200
    p[100] = 0.5
    p[200] = 1.0
    return p


GI = pity_curve(0.006, 90, [(74, 0.06, None)])                       # 原神/星铁角色池（社区模型）
GW = pity_curve(0.007, 80, [(63, 0.07, 73), (74, 0.035, None)])      # 原神武器池（社区模型）
LC = pity_curve(0.008, 80, [(66, 0.07, None)])                       # 星铁光锥池（社区模型）
WW = pity_curve(0.008, 80, [(66, 0.04, 70), (71, 0.08, 75), (76, 0.10, 78)])  # 鸣潮（社区模型）
AK = pity_curve(0.02, 99, [(51, 0.02, None)])                        # 明日方舟（官方规则）
EF = pity_curve(0.008, 80, [(66, 0.05, None)])                       # 终末地（攻略说法）
LDS = pity_curve(0.01, 70, [(61, 0.10, None)])                       # 恋与深空（国际服官方说明）
R99 = pity_curve(0.015, 70, [(61, 0.025, None)])                     # 重返未来：1999
PGR = pity_curve(0.005, 60)                                          # 战双
NTE = jump(0.0099, 71, 0.195, 90)                                    # 异环（攻略说法）
P4 = pity_curve(0.051, 10, [(9, 0.51, None)])                        # 原神 4★（社区模型）

# 保底式：(名称, 曲线, UP 状态机, 井, 井模式, 公示综合概率, E[M], 最坏抽数, 单抽人民币)
GUARANTEE_STYLE = [
    ("原神·角色活动祈愿", GI, chain_guarantee(0.55), None, None, 0.016, 1.45, 180, 12.83),
    ("原神·神铸赋形（定轨）", GW, chain_guarantee(0.375), None, None, 0.0185, 1.625, 160, 12.83),
    ("星穹铁道·角色活动跃迁", GI, chain_guarantee(0.5), None, None, 0.016, 1.5, 180, 12.83),
    ("星穹铁道·光锥活动跃迁", LC, chain_guarantee(0.75), None, None, 0.0187, 1.25, 160, 12.83),
    ("绝区零·独家频段", GI, chain_guarantee(0.5), None, None, 0.016, 1.5, 180, None),
    ("绝区零·音擎频段", None, None, None, None, 0.02, 1.25, 160, None),
    ("鸣潮·角色活动唤取", WW, chain_guarantee(0.5), None, None, 0.018, 1.5, 160, 12.83),
    ("鸣潮·武器活动唤取", WW, chain_always(), None, None, 0.018, 1.0, 80, 12.83),
    ("明日方舟·限定寻访", AK, chain_plain(0.35), 300, "repeat", None, None, 300, 11.68),
    ("明日方舟：终末地·特许寻访", EF, chain_plain(0.5), 120, "once_if_none", None, None, 120, 12.34),
    ("恋与深空·单卡限定", LDS, chain_guarantee(0.5), None, None, 0.021, 1.5, 140, 15.0),
    ("重返未来：1999·限时征集", R99, chain_guarantee(0.5), None, None, 0.0236, 1.5, 140, None),
    ("战双帕弥什·主题角色研发", PGR, chain_always(), None, None, 0.019, 1.0, 60, None),
    ("异环·限定 UP 池", NTE, chain_always(), None, None, None, 1.0, 90, None),
]

# 井式：把「出 PU」直接当计数事件。(名称, 曲线, 井, 货币, 单抽价格)
SPARK_STYLE = [
    ("FGO·PU 召唤（单 PU，330 确定召唤可重复）", pity_curve(0.008, 330), None, "JPY", 178.6),
    ("赛马娘·PU 育成角色（200 Pt 兑换）", pity_curve(0.0075, None), 200, "JPY", 300),
    ("公主连结·PU 池（200 Pt 兑换）", pity_curve(0.007, None), 200, "JPY", 300),
    ("学园偶像大师·PU 偶像（200 Pt 兑换）", pity_curve(0.0075, None), 200, "JPY", 298.8),
    ("世界计划·PU ★4（300 枚贴纸兑换）", pity_curve(0.004, None), 300, "JPY", 285.7),
    ("蔚蓝档案·旧规则（200 点兑换）", pity_curve(0.007, None), 200, "JPY", 250),
    ("蔚蓝档案·新规则（100 / 200 两段保底）", ba_charge(), None, "JPY", 250),
    ("NIKKE·PU 招募（200 券兑换）", pity_curve(0.02, None), 200, "USD", 3.87),
    ("第七史诗·PU 召唤（121 抽必得）", pity_curve(0.01, 121), None, None, None),
    ("碧蓝航线·限时建造 UR（200 次兑换）", pity_curve(0.012, None), 200, None, None),
]


def table(header, rows):
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


def report():
    # 3.1 同期望三种形状
    en = 1 / comprehensive_rate(GI)
    lo, hi = 1e-4, 0.05
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if (1 - (1 - m) ** 90) / m > en else (lo, m)
    rows = []
    for name, p in [("纯概率（每抽 1.605%）", pity_curve(1 / en, None)),
                    (f"只有硬保底（每抽 {m * 100:.3f}%，90 抽必出）", pity_curve(m, 90)),
                    ("原神式（0.6% + 74 抽起软保底 + 90 抽必出）", GI)]:
        s = stats(top_distribution(p))
        rows.append((name, f"{s['mean']:.1f}", f"{s['sd']:.1f}", s["p10"], s["p50"], s["p90"], s["p99"]))
    print("3.1 同期望三种形状")
    table(("曲线", "期望", "标准差", "P10", "中位数", "P90", "P99"), rows)
    d = top_distribution(GI)
    print(f"原神式：第 74 抽之前出货的比例 {sum(d[:74]) * 100:.1f}%\n")

    print("3.2 软保底起点（基础 0.6%，每抽 +6%，90 抽必出）")
    rows = []
    for st in [60, 66, 70, 74, 78, 82, 86]:
        p = pity_curve(0.006, 90, [(st, 0.06, None)])
        s = stats(top_distribution(p))
        rows.append((st, fmt_pct(comprehensive_rate(p), 3), f"{s['mean']:.1f}", s["p50"], s["p90"]))
    table(("软保底起点", "综合概率", "期望", "中位数", "P90"), rows)
    rows = []
    for inc in [0.02, 0.04, 0.06, 0.10]:
        p = pity_curve(0.006, 90, [(74, inc, None)])
        s = stats(top_distribution(p))
        rows.append((f"+{inc * 100:.0f}%", fmt_pct(comprehensive_rate(p), 3), f"{s['mean']:.1f}", s["p90"]))
    table(("每抽增量（74 抽起）", "综合概率", "期望", "P90"), rows)

    print("3.3 UP 规则（稀有度层用原神式曲线）")
    rows = []
    for name, ch, worst in [("100% 是 UP", chain_always(), "90"),
                            ("75% + 大保底", chain_guarantee(0.75), "180"),
                            ("55% + 大保底（含捕获明光的近似）", chain_guarantee(0.55), "180"),
                            ("50% + 大保底", chain_guarantee(0.5), "180"),
                            ("50%，没有大保底", chain_plain(0.5), "无上限")]:
        s = stats(pulls_to_copies(GI, ch, "free", 1))
        rows.append((name, f"{s['mean']:.1f}", f"×{s['mean'] / en:.2f}", s["p50"], s["p90"], s["p99"], worst))
    table(("UP 规则", "期望", "倍率", "中位数", "P90", "P99", "最坏"), rows)

    print("3.4 井（没有出货保底，PU 单抽概率 u，S 抽可兑换）")
    rows = []
    for u, S in [(0.004, 300), (0.005, 200), (0.007, 200), (0.0075, 200), (0.012, 200), (0.02, 200)]:
        p = pity_curve(u, None)
        s0 = stats(pulls_to_copies(p, chain_always(), "free", 1))
        s = stats(pulls_to_copies(p, chain_always(), "free", 1, spark=S))
        rows.append((fmt_pct(u, 2), S, f"{s0['mean']:.1f}", s0["p90"], f"{s['mean']:.1f}", s["p50"],
                     fmt_pct((1 - u) ** (S - 1), 1)))
    table(("PU 概率", "井", "无井期望", "无井 P90", "有井期望", "有井中位数", "抽满井的人"), rows)

    print("3.5 多份（原神角色池，55% 近似）")
    rows = []
    for k in [1, 2, 3, 7]:
        s = stats(pulls_to_copies(GI, chain_guarantee(0.55), "free", k))
        rows.append((k, f"{s['mean']:.1f}", s["p10"], s["p50"], s["p90"], 180 * k, f"{s['p90'] / s['mean']:.2f}"))
    table(("份数", "期望", "P10", "中位数", "P90", "最坏", "P90 ÷ 期望"), rows)

    print("4★ 十连保底：")
    print(f"  只有第 10 抽必出：综合 {fmt_pct(comprehensive_rate(pity_curve(0.051, 10)))}")
    print(f"  第 9 抽升到 {P4[9] * 100:.1f}%：综合 {fmt_pct(comprehensive_rate(P4))}（公示 13.000%）\n")

    print("公示综合概率反查")
    rows = []
    for name, p, pub in [("原神·角色", GI, "1.600%"), ("原神·武器", GW, "1.850%"), ("星铁·光锥（66 抽起）", LC, "1.870%"),
                         ("星铁·光锥（63 抽起）", pity_curve(0.008, 80, [(63, 0.07, None)]), "1.870%"),
                         ("鸣潮", WW, "1.8%"), ("鸣潮（只有硬保底）", pity_curve(0.008, 80), "1.8%"),
                         ("明日方舟", AK, "不公布"), ("恋与深空", LDS, "2.1%"), ("重返未来：1999", R99, "2.36%"),
                         ("战双（只有硬保底）", PGR, "1.9%"), ("绝区零·音擎（只有硬保底）", pity_curve(0.01, 80), "2.0%"),
                         ("无限暖暖（只有硬保底 20）", pity_curve(0.015, 20), "6.06%"), ("异环", NTE, "约 1.87%（攻略）")]:
        rows.append((name, fmt_pct(comprehensive_rate(p), 3), pub))
    table(("模型", "算出的综合概率", "公示"), rows)

    print("5.1 保底式：拿到 1 个当期 UP")
    rows = []
    for name, p, ch, spark, mode, rate, em, worst, price in GUARANTEE_STYLE:
        s = stats(pulls_to_copies(p, ch, "free", 1, spark=spark, spark_mode=mode or "repeat")) if p else None
        mean_pub = em / rate if rate and em else None
        mean = mean_pub or (s and s["mean"])
        rows.append((name, f"{mean_pub:.1f}" if mean_pub else "—", f"{s['mean']:.1f}" if s else "—",
                     s["p50"] if s else "—", s["p90"] if s else "—", worst,
                     f"{mean * price:,.0f}" if price and mean else "—"))
    table(("池子", "期望（按公示综合概率）", "期望（按曲线）", "中位数", "P90", "最坏", "期望花费（元）"), rows)

    print("5.2 井式：拿到 1 个当期 PU")
    rows = []
    for name, p, spark, cur, price in SPARK_STYLE:
        d = pulls_to_copies(p, chain_always(), "free", 1, spark=spark)
        s = stats(d)
        worst = spark or len(p) - 1
        rows.append((name, f"{s['mean']:.1f}", s["p50"], s["p90"], worst, fmt_pct(sum(d[worst:]), 1),
                     f"{s['mean'] * price:,.0f} {cur}" if price else "—"))
    table(("池子", "期望", "中位数", "P90", "最坏", "抽满封顶的人", "期望花费"), rows)

    print("5.3 满配")
    rows = []
    for name, p, ch, k, spark, worst in [("原神 6 命（7 份）", GI, chain_guarantee(0.55), 7, None, 1260),
                                         ("鸣潮 6 链（7 份）", WW, chain_guarantee(0.5), 7, None, 1120),
                                         ("重返未来：1999（6 份）", R99, chain_guarantee(0.5), 6, None, 840),
                                         ("FGO 宝具 5（5 份）", pity_curve(0.008, 330), chain_always(), 5, None, 1650),
                                         ("NIKKE 3 份", pity_curve(0.02, None), chain_always(), 3, 200, 600)]:
        s = stats(pulls_to_copies(p, ch, "free", k, spark=spark))
        rows.append((name, f"{s['mean']:.1f}", s["p50"], s["p90"], worst))
    table(("目标", "期望", "中位数", "P90", "最坏"), rows)


# ---------- 配图（需要 matplotlib；不装也不影响上面的表） ----------

def charts(out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    surface, ink, ink2, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"],
        "axes.unicode_minus": False, "font.size": 11, "axes.edgecolor": grid, "axes.labelcolor": ink2,
        "xtick.color": ink2, "ytick.color": ink2, "figure.facecolor": surface, "axes.facecolor": surface})

    def style(ax, title, sub):
        ax.grid(True, color=grid, linewidth=1)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.set_title(title, loc="left", color=ink, fontsize=14, pad=26, fontweight="bold")
        ax.text(0, 1.02, sub, transform=ax.transAxes, color=ink2, fontsize=10)

    series = [("原神·角色池", GI), ("鸣潮·角色池", WW), ("明日方舟", AK), ("恋与深空", LDS)]
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    for (name, p), c in zip(series, colors):
        xs, ys = list(range(1, len(p))), [v * 100 for v in p[1:]]
        ax.plot(xs, ys, color=c, linewidth=2, drawstyle="steps-post", label=name)
        ax.plot([xs[-1]], [ys[-1]], "o", color=c, markersize=8, markeredgecolor=surface, markeredgewidth=2)
        ax.text(len(p) - 1, 104, f"{len(p) - 1}", color=ink, fontsize=10, ha="center", va="bottom")
    ax.text(101.5, 104, "← 硬保底抽数", color=ink2, fontsize=9, va="bottom")
    ax.set_xlim(0, 112)
    ax.set_ylim(0, 112)
    ax.set_yticks(range(0, 101, 20))
    ax.set_xlabel("距上次出最高稀有度的抽数")
    ax.set_ylabel("这一抽出最高稀有度的概率（%）")
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    style(ax, "每抽出货概率：前段平、后段陡", "基础概率只管前几十抽；软保底起点之后概率快速爬升，到硬保底为 100%")
    fig.tight_layout()
    fig.savefig(f"{out_dir}/fig1_pity_curves.png", facecolor=surface)

    series = [
        ("原神·角色池（保底 + 大保底）", pulls_to_copies(GI, chain_guarantee(0.55), "free", 1)),
        ("明日方舟·限定（线性软保底 + 300 井）", pulls_to_copies(AK, chain_plain(0.35), "free", 1, spark=300)),
        ("蔚蓝档案·新规则（100 / 200 两段保底）", pulls_to_copies(ba_charge(), chain_always(), "free", 1)),
        ("FGO（纯概率 0.8% + 330 确定）", pulls_to_copies(pity_curve(0.008, 330), chain_always(), "free", 1)),
        ("NIKKE（PU 2% + 200 井）", pulls_to_copies(pity_curve(0.02, None), chain_always(), "free", 1, spark=200)),
    ]
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=150)
    for (name, d), c in zip(series, colors):
        xs, ys, acc = [0], [0], 0.0
        for n in range(1, min(len(d), 331)):
            acc += d[n]
            xs.append(n)
            ys.append(acc * 100)
        ax.plot(xs, ys, color=c, linewidth=2, label=name)
    ax.axhline(90, color=ink2, linewidth=1)
    ax.text(3, 91, "90% 的玩家", color=ink2, fontsize=9, va="bottom")
    ax.set_xlim(0, 345)
    ax.set_ylim(0, 102)
    ax.set_xticks(range(0, 331, 30))
    ax.set_xlabel("累计抽数")
    ax.set_ylabel("已拿到当期 UP 的玩家比例（%）")
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    style(ax, "拿到 1 个当期 UP：五种封顶方式", "曲线到 100% 的位置就是最坏情况；曲线越早变陡，玩家之间的差距越小")
    fig.tight_layout()
    fig.savefig(f"{out_dir}/fig2_cdf_one_up.png", facecolor=surface)


if __name__ == "__main__":
    report()
    if "--charts" in sys.argv:
        charts(sys.argv[sys.argv.index("--charts") + 1] if len(sys.argv) > sys.argv.index("--charts") + 1 else ".")
