# -*- coding: utf-8 -*-
# 生成论文4张插图（fig1-fig4）
import math
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "5_论文初稿", "figures")
os.makedirs(OUT, exist_ok=True)

DEG = math.pi / 180.0


# fig1 交会定位示意
def fig1():
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    S1 = (0.0, 0.0)
    S2 = (2.4, 3.2)
    G = (5.0, 1.6)
    L = 7.5

    def ray(P, ang, color, lw=1.6):
        ax.add_patch(FancyArrowPatch(P, (P[0] + L * math.cos(ang * DEG),
                                         P[1] + L * math.sin(ang * DEG)),
                                     arrowstyle="-|>", mutation_scale=12,
                                     color=color, lw=lw))

    a1 = math.degrees(math.atan2(G[1] - S1[1], G[0] - S1[0]))
    a2 = math.degrees(math.atan2(G[1] - S2[1], G[0] - S2[0]))
    # 误差带边界（±1°）
    for s in (+1, -1):
        ray(S1, a1 + s, "#bbbbbb", 1.0)
        ray(S2, a2 + s, "#bbbbbb", 1.0)
    # 真实示向度方向线
    ray(S1, a1, "#1f77b4")
    ray(S2, a2, "#d62728")

    def line_hit(P, ang):
        r = ang * DEG
        dx, dy = G[0] - P[0], G[1] - P[1]
        return abs(dx * math.sin(r) - dy * math.cos(r))

    # 定位区域四边形：4条误差带边界线的两两交点（靠近G的交点）
    pts = []
    import itertools

    def inter(P1, a1_, P2, a2_):
        r1, r2 = a1_ * DEG, a2_ * DEG
        c1, s1_ = math.cos(r1), math.sin(r1)
        c2, s2_ = math.cos(r2), math.sin(r2)
        den = c1 * s2_ - s1_ * c2
        if abs(den) < 1e-12:
            return None
        t = ((P2[0] - P1[0]) * s2_ - (P2[1] - P1[1]) * c2) / den
        return (P1[0] + t * c1, P1[1] + t * s1_)

    lines = [(S1, a1 - 1), (S1, a1 + 1), (S2, a2 - 1), (S2, a2 + 1)]
    for (Pa, aa), (Pb, ab) in itertools.combinations(lines, 2):
        if Pa is Pb:
            continue
        p = inter(Pa, aa, Pb, ab)
        if p and math.hypot(p[0] - G[0], p[1] - G[1]) < 2.0:
            pts.append(p)
    if len(pts) >= 4:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        xs = [p[0] for p in pts] + [pts[0][0]]
        ys = [p[1] for p in pts] + [pts[0][1]]
        ax.fill(xs, ys, color="#ff9896", alpha=0.55, zorder=1)

    ax.plot(*G, "k*", ms=14, zorder=5, label="干扰源 G")
    ax.plot(*S1, "o", color="#1f77b4", ms=8, zorder=5)
    ax.plot(*S2, "s", color="#d62728", ms=8, zorder=5)
    ax.annotate("$S_1$", S1, textcoords="offset points", xytext=(-22, -4), fontsize=12)
    ax.annotate("$S_2$", S2, textcoords="offset points", xytext=(-26, 2), fontsize=12)
    ax.annotate("定位区域", (G[0] - 0.4, G[1] + 0.55), fontsize=10)
    ax.annotate("示向度线 $\\theta_1$", (2.1, 0.62), fontsize=10, color="#1f77b4")
    ax.annotate("示向度线 $\\theta_2$", (2.5, 2.3), fontsize=10, color="#d62728",
                rotation=-24)
    ax.annotate("±1°误差带", (1.05, 1.9), fontsize=9, color="#777777")

    ax.set_xlim(-0.8, 7.6)
    ax.set_ylim(-0.8, 5.4)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("两点示向度交会定位与定位区域示意")
    ax.legend(loc="lower right", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_交会定位示意.png"), dpi=300)
    plt.close(fig)


# fig2 问题3扫描点集
def fig2():
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.add_patch(Circle((0, 0), 1800, fill=False, ls="--", color="#888888"))
    pts = [(0.0, 0.0)] + [(700 * math.cos(2 * math.pi * i / 6),
                           700 * math.sin(2 * math.pi * i / 6)) for i in range(6)] + \
          [(1400 * math.cos(2 * math.pi * i / 6),
            1400 * math.sin(2 * math.pi * i / 6)) for i in range(6)]
    # 每点覆盖圆 r=1200（介于1000-1500的示意值）
    for (x, y) in pts:
        ax.add_patch(Circle((x, y), 1200, fill=True, color="#aec7e8", alpha=0.14,
                            ec="none"))
    ax.plot([p[0] for p in pts[1:7]], [p[1] for p in pts[1:7]], "o", color="#1f77b4",
            ms=7, label="内圈 r=700（6点）")
    ax.plot([p[0] for p in pts[7:]], [p[1] for p in pts[7:]], "s", color="#d62728",
            ms=7, label="外圈 r=1400（6点）")
    ax.plot(0, 0, "*", color="#2ca02c", ms=15, label="原点预扫描")
    ax.annotate("目标区域 R=1800", (1290, 1330), fontsize=10, color="#555555")
    ax.annotate("阴影=各点覆盖示意\n（接收半径1200米）", (-620, 660), fontsize=9,
                color="#1f77b4")
    ax.set_xlim(-2100, 2100)
    ax.set_ylim(-2100, 2100)
    ax.set_aspect("equal")
    ax.set_xlabel("x（米）")
    ax.set_ylabel("y（米）")
    ax.set_title("问题3三阶段策略的扫描点集与覆盖示意")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_问题3扫描点集.png"), dpi=300)
    plt.close(fig)


# fig3 边界月牙几何
def fig3():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    G = (1740.0, 0.0)          # 朝外定向干扰源（距原点1740米，方向朝外+角度）
    phi = 10.0                  # 定向方向稍微偏一点，示意更直观
    r_recv = 1500.0
    ax.add_patch(Circle((0, 0), 1800, fill=False, ls="--", color="#888888",
                        label="目标区域边界 R=1800"))
    ax.add_patch(Circle((0, 0), 1700, fill=False, ls=":", color="#aaaaaa",
                        label="旧方案边界圈 r=1700"))
    # 可见区域 = 接收圆 ∩ 覆盖角扇形（以G为心的扇形±90°）
    import matplotlib.patches as mpatches
    from matplotlib.path import Path as MPath
    import numpy as np
    # 扇形（朝外±90°）
    wedge = mpatches.Wedge(G, r_recv, phi - 90, phi + 90, fill=True,
                           color="#98df8a", alpha=0.25)
    ax.add_patch(wedge)
    # 目标区域内可见弧
    th = np.linspace(0, 2 * np.pi, 720)
    for r, color, name in ((1700, "#ff7f0e", "r=1700圈上可见弧"),
                           (1800, "#1f77b4", "r=1800圈上可见弧")):
        vis = []
        for t in th:
            x, y = r * math.cos(t), r * math.sin(t)
            if (x - G[0]) * math.cos(phi * DEG) + (y - G[1]) * math.sin(phi * DEG) >= 0 \
               and math.hypot(x - G[0], y - G[1]) <= r_recv:
                vis.append((x, y))
        if vis:
            ax.plot([p[0] for p in vis], [p[1] for p in vis], color=color, lw=4,
                    label=name)
    ax.plot(*G, "k*", ms=13, zorder=5)
    ax.annotate("朝外定向干扰源\n（距原点1740米）", G, textcoords="offset points",
                xytext=(10, 18), fontsize=10)
    ax.annotate("边界月牙盲区：\n只有贴边的检测点能看见它", (1180, 980), fontsize=10,
                color="#333333")
    ax.set_xlim(-400, 3200)
    ax.set_ylim(-1700, 1700)
    ax.set_aspect("equal")
    ax.set_xlabel("x（米）")
    ax.set_ylabel("y（米）")
    ax.set_title("边界月牙盲区几何：r=1700 与 r=1800 边界圈对比")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_边界月牙几何.png"), dpi=300)
    plt.close(fig)


# fig4 漏检率对比（表6数据）
def fig4():
    bins = ["[1600,1700)", "[1700,1750)", "[1750,1780)", "[1780,1790)", "[1790,1800)"]
    old = [19.5, 100.0, 100.0, 100.0, 100.0]
    new = [0.0, 0.0, 0.0, 0.0, 20.0]
    x = range(len(bins))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    b1 = ax.bar([i - w / 2 for i in x], old, w, label="优化前（r=1700边界圈12点）",
                color="#ff7f0e")
    b2 = ax.bar([i + w / 2 for i in x], new, w, label="优化后（r=1800边界圈36点）",
                color="#1f77b4")
    for b in list(b1) + list(b2):
        h = b.get_height()
        ax.annotate(f"{h:.0f}%" if h in (0.0, 100.0) else f"{h:.1f}%",
                    (b.get_x() + b.get_width() / 2, h), ha="center",
                    va="bottom" if h < 90 else "bottom", fontsize=8.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(bins, fontsize=9)
    ax.set_ylim(0, 115)
    ax.set_ylabel("漏检率（%）")
    ax.set_xlabel("朝外定向干扰源距原点距离（米）")
    ax.set_title("朝外定向干扰源按距离分桶漏检率对比（蒙特卡洛，接收半径1500米）")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_漏检率对比.png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("图片已生成至", OUT)
    for f in sorted(os.listdir(OUT)):
        print(" -", f)
