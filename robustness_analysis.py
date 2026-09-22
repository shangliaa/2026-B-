# -*- coding: utf-8 -*-
# 离线蒙特卡洛鲁棒性检验（问题3/4），结果用于论文6.x/7.x节
import math
import random

REGION_R = 1800.0
DEG = math.pi / 180.0


def ring_p(r, n):
    return [(r * math.cos(2 * math.pi * i / n),
             r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# 扫描点集（与 robot_dog.py 一致）
P3_SET = [(0.0, 0.0)] + ring_p(700, 6) + ring_p(1400, 6)
P4_SET = [(0.0, 0.0)] + ring_p(500, 8) + ring_p(1000, 8) + ring_p(1500, 18) + ring_p(1800, 36)
# 优化前的P4点集（用于对比：r=1700×12替代r=1800×36）
P4_SET_OLD = [(0.0, 0.0)] + ring_p(500, 8) + ring_p(1000, 8) + ring_p(1500, 18) + ring_p(1700, 12)


def rand_in_disk(r=REGION_R):
    a = random.random() * 2 * math.pi
    rr = math.sqrt(random.random()) * r
    return (rr * math.cos(a), rr * math.sin(a))


def is_seen_omni(jx, jy, r_recv, S):
    r2 = r_recv * r_recv
    for (px, py) in S:
        dx, dy = px - jx, py - jy
        if dx * dx + dy * dy <= r2:
            return True
    return False


def is_seen_dir(jx, jy, ux, uy, r_recv, S):
    r2 = r_recv * r_recv
    for (px, py) in S:
        dx, dy = px - jx, py - jy
        if dx * ux + dy * uy >= 0 and dx * dx + dy * dy <= r2:
            return True
    return False


def mc_omni(S, n, r_recv_fixed=None, tag=""):
    """全向干扰源漏检概率蒙特卡洛"""
    miss = 0
    for _ in range(n):
        jx, jy = rand_in_disk()
        rr = r_recv_fixed if r_recv_fixed else random.uniform(1000, 1500)
        if not is_seen_omni(jx, jy, rr, S):
            miss += 1
    print(f"[全向 {tag}] N={n} 漏检={miss} 漏检率={miss / n * 100:.3f}%")
    return miss / n


def mc_dir(S, n, outward_only=False, r_recv_fixed=None, tag=""):
    """定向干扰源漏检概率蒙特卡洛；outward_only=True 时只测最坏的朝外朝向"""
    miss = 0
    for _ in range(n):
        jx, jy = rand_in_disk()
        if outward_only:
            d = math.hypot(jx, jy)
            ux, uy = (jx / d, jy / d) if d > 1e-9 else (1.0, 0.0)
        else:
            a = random.random() * 2 * math.pi
            ux, uy = math.cos(a), math.sin(a)
        rr = r_recv_fixed if r_recv_fixed else random.uniform(1000, 1500)
        if not is_seen_dir(jx, jy, ux, uy, rr, S):
            miss += 1
    print(f"[定向 {tag}] N={n} 漏检={miss} 漏检率={miss / n * 100:.4f}%")
    return miss / n


def mc_dir_by_d(S, n, r_recv=1500):
    """朝外定向干扰源：按距原点距离d分桶统计漏检率（最坏r_recv=1500？不，用1500最宽松也漏）"""
    bins = [(0, 800), (800, 1200), (1200, 1500), (1500, 1600), (1600, 1700),
            (1700, 1750), (1750, 1780), (1780, 1790), (1790, 1800)]
    cnt = [0] * len(bins)
    miss = [0] * len(bins)
    for _ in range(n):
        jx, jy = rand_in_disk()
        d = math.hypot(jx, jy)
        ux = jx / d if d > 1e-9 else 1.0
        uy = jy / d if d > 1e-9 else 0.0
        seen = is_seen_dir(jx, jy, ux, uy, r_recv, S)
        for i, (lo, hi) in enumerate(bins):
            if lo <= d < hi:
                cnt[i] += 1
                if not seen:
                    miss[i] += 1
                break
    print(f"[朝外定向按距离分桶 r_recv={r_recv}]")
    for i, (lo, hi) in enumerate(bins):
        if cnt[i]:
            print(f"  d∈[{lo:4d},{hi:4d}): 样本={cnt[i]:6d} 漏检率={miss[i] / cnt[i] * 100:6.3f}%")
        else:
            print(f"  d∈[{lo:4d},{hi:4d}): 样本=0")


def coverage_radius(S):
    """数值求区域内任意点到最近扫描点的最大距离（覆盖半径），用极坐标网格"""
    worst = 0.0
    worst_pos = None
    for r in [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200,
              1300, 1400, 1500, 1600, 1700, 1800]:
        n = max(8, int(2 * math.pi * r / 50)) if r > 0 else 1
        for i in range(n):
            th = 2 * math.pi * i / n
            x, y = r * math.cos(th), r * math.sin(th)
            dmin = min(math.hypot(x - px, y - py) for (px, py) in S)
            if dmin > worst:
                worst, worst_pos = dmin, (x, y)
    print(f"  覆盖半径(最大空洞到最近扫描点距离) = {worst:.1f}m，位置{tuple(round(v) for v in worst_pos)}")
    return worst


def mc_triang_error(S, n=20000):
    """
    交会定位误差：对每个被看见(>=2个接触点)的干扰源，
    取交会角最大的点对，按1°/点测向误差估计1σ位置误差：
    σ ≈ (σ_θ·√((d1²+d2²)/2)) / |sin γ|，γ为两点相对干扰源张角。
    统计中位数、95分位与“网格清除(25m)预计失败率”。
    """
    errs = []
    for _ in range(n):
        jx, jy = rand_in_disk()
        a = random.random() * 2 * math.pi
        ux, uy = math.cos(a), math.sin(a)
        rr = random.uniform(1000, 1500)
        vis = [(px, py) for (px, py) in S
               if (px - jx) * ux + (py - jy) * uy >= 0
               and math.hypot(px - jx, py - jy) <= rr]
        if len(vis) < 2:
            continue  # 单点接触走射线步进兜底
        best = 0.0
        bp = None
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                v1x, v1y = vis[i][0] - jx, vis[i][1] - jy
                v2x, v2y = vis[j][0] - jx, vis[j][1] - jy
                d1 = math.hypot(v1x, v1y)
                d2 = math.hypot(v2x, v2y)
                if d1 < 1e-9 or d2 < 1e-9:
                    continue
                s = abs(v1x * v2y - v1y * v2x) / (d1 * d2)  # |sin γ|
                if s > best:
                    best = s
                    bp = (d1, d2)
        if bp is None or best < 1e-9:
            continue
        d1, d2 = bp
        sig = (1.0 * DEG) * math.sqrt((d1 * d1 + d2 * d2) / 2) / best
        errs.append(sig)
    if errs:
        errs.sort()
        med = errs[len(errs) // 2]
        p95 = errs[int(len(errs) * 0.95)]
        fail = sum(1 for e in errs if e > 20) / len(errs)
        print(f"[交会定位误差] 样本={len(errs)} 中位1σ={med:.1f}m 95分位={p95:.1f}m "
              f"预计网格清除失败率(σ>20m)={fail * 100:.2f}%")
    else:
        print("[交会定位误差] 无样本")


def mc_ray_guarantee(S, n=20000):
    """射线步进兜底保证率：存在接触点且 |P-J|<=1100m（此时1°侧向误差<19.2m<20m清除半径）"""
    ok = 0
    seen_any = 0
    for _ in range(n):
        jx, jy = rand_in_disk()
        a = random.random() * 2 * math.pi
        ux, uy = math.cos(a), math.sin(a)
        rr = random.uniform(1000, 1500)
        found = None
        for (px, py) in S:
            if (px - jx) * ux + (py - jy) * uy >= 0 and math.hypot(px - jx, py - jy) <= rr:
                if found is None or math.hypot(px - jx, py - jy) < found:
                    found = math.hypot(px - jx, py - jy)
        if found is not None:
            seen_any += 1
            if found <= 1100:
                ok += 1
    if seen_any:
        print(f"[射线步进兜底] 被看见样本={seen_any}，其中最近接触<=1100m保证可清的比例={ok / seen_any * 100:.2f}%")
    else:
        print("[射线步进兜底] 无样本")


if __name__ == "__main__":
    random.seed(20260911)
    print("=" * 62)
    print("问题3/问题4 策略鲁棒性蒙特卡洛检验（区域半径1800m）")
    print("=" * 62)

    print("\n--- 1. 全向干扰源覆盖（P3扫描点集：原点+r700×6+r1400×6） ---")
    mc_omni(P3_SET, 50000, tag="r_recv~U[1000,1500]")
    mc_omni(P3_SET, 50000, r_recv_fixed=1000, tag="最坏r_recv=1000")
    coverage_radius(P3_SET)

    print("\n--- 2. 全向干扰源覆盖（P4扫描点集：原点+500×8+1000×8+1500×18+1800×36） ---")
    mc_omni(P4_SET, 50000, tag="r_recv~U[1000,1500]")
    mc_omni(P4_SET, 50000, r_recv_fixed=1000, tag="最坏r_recv=1000")
    coverage_radius(P4_SET)

    print("\n--- 3. 定向干扰源覆盖（P4点集，朝向随机） ---")
    mc_dir(P4_SET, 50000, tag="随机朝向")
    mc_dir(P4_SET, 50000, outward_only=True, tag="最坏朝外朝向")
    mc_dir(P4_SET, 50000, outward_only=True, r_recv_fixed=1000, tag="朝外且r_recv=1000")

    print("\n--- 4. 朝外定向干扰源分桶漏检率（P4点集 vs 优化前r=1700×12） ---")
    print("[优化前]")
    mc_dir_by_d(P4_SET_OLD, 60000)
    print("[优化后]")
    mc_dir_by_d(P4_SET, 60000)

    print("\n--- 5. 交会定位与射线兜底 ---")
    mc_triang_error(P4_SET)
    mc_ray_guarantee(P4_SET)
    print("\n分析完成。")