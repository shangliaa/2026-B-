# 机器狗程序：通过 HTTP+JSON 与官方模拟器通信
import json
import time
import math
import urllib.request
import urllib.error
from datetime import datetime

# 配置
BASE_URL = "http://127.0.0.1:2026"
# 参赛队号：不写死在代码中，优先取命令行第二个参数（python robot_dog.py [test|p4] <队号>），
# 其次取环境变量 ROBOT_ID，均未提供时使用占位符
import os
import sys
ROBOT_ID = (sys.argv[2] if len(sys.argv) > 2 else "") or os.environ.get("ROBOT_ID", "YOUR_TEAM_NO")
TIMEOUT = 10
LOG_FILE = "robot_log.txt"  # 自行记录的指令日志

# 全局状态
_req_counter = 0
_cur_pos = (0.0, 0.0)
_cur_channel = 1
_virtual_time = 0.0
_real_start_time = None


def _next_request_id(prefix):
    global _req_counter
    _req_counter += 1
    return f"{prefix}-{_req_counter}"


def _post(path, payload, retry=3):
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(retry):
        try:
            req = urllib.request.Request(
                BASE_URL + path,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                _log(f"{path} -> {result}")
                return result
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            _log(f"{path} 网络错误(第{attempt+1}次): {e}")
            time.sleep(1)
    raise RuntimeError(f"请求失败: {path}, 最后错误: {last_err}")


def _log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# 4条指令封装
def enter():
    global _real_start_time, _cur_pos, _cur_channel, _virtual_time
    payload = {
        "arena_id": "default",
        "robot_id": ROBOT_ID,
        "request_id": _next_request_id("enter"),
    }
    resp = _post("/enter", payload)
    if resp.get("accepted") is True:
        _real_start_time = time.time()
        _cur_pos = (0.0, 0.0)
        _cur_channel = 1
        _virtual_time = 0.0
        _log(f"进入成功，剩余现实时间: {resp.get('remaining_real_duration_s')}s")
    return resp


def measure(x, y, channel):
    global _cur_pos, _cur_channel, _virtual_time
    payload = {
        "arena_id": "default",
        "robot_id": ROBOT_ID,
        "request_id": _next_request_id("measure"),
        "position": {"x": x, "y": y},
        "channel": channel,
    }
    resp = _post("/measure", payload)
    if resp.get("accepted") is True:
        _cur_pos = (x, y)
        _cur_channel = channel
        _virtual_time = resp.get("virtual_time_s", _virtual_time)
        _log(f"检测 ({x},{y}) ch={channel}: {resp.get('measure_result')} "
             f"svd={resp.get('svd_deg')} vt={_virtual_time}")
    return resp


def clear(x, y, channel):
    global _cur_pos, _virtual_time
    payload = {
        "arena_id": "default",
        "robot_id": ROBOT_ID,
        "request_id": _next_request_id("clear"),
        "position": {"x": x, "y": y},
        "channel": channel,
    }
    resp = _post("/clear", payload)
    if resp.get("accepted") is True:
        _cur_pos = (x, y)
        _virtual_time = resp.get("virtual_time_s", _virtual_time)
        _log(f"清除 ({x},{y}) ch={channel}: {resp.get('clear_result')} vt={_virtual_time}")
    return resp


def exit_sim():
    payload = {
        "arena_id": "default",
        "robot_id": ROBOT_ID,
        "request_id": _next_request_id("exit"),
    }
    resp = _post("/exit", payload)
    _log(f"退出: {resp}")
    return resp


# 搜索策略（问题3：全向干扰源）
def simple_search_omnidirectional():
    """
    优化策略 v3：
    1. 原点预扫描全频道 → 区分有信号/无信号频道
    2. 有信号频道直接两点交会定位清除（省去螺旋扫描）
    3. 无信号频道才螺旋搜索
    4. 清除网格改为十字形5点（减少失败尝试）
    """
    enter_resp = enter()
    if enter_resp.get("accepted") is not True:
        _log("进入失败，退出")
        return

    remaining = enter_resp.get("remaining_real_duration_s", 1200)
    deadline = time.time() + remaining - 30

    cleared = 0
    cleared_channels = set()

    # 阶段1：原点预扫描全部20频道
    _log("=== 阶段1：原点全频道预扫描 ===")
    active_channels = {}  # ch -> svd_deg
    silent_channels = []
    for ch in range(1, 21):
        if time.time() > deadline:
            break
        resp = measure(0, 0, ch)
        if resp.get("accepted") is not True:
            continue
        result = resp.get("measure_result")
        if result == "direction":
            active_channels[ch] = resp["svd_deg"]
        elif result == "near":
            # 原点就在干扰源5米内，直接清除
            cresp = clear(0, 0, ch)
            if cresp.get("clear_result") == "success":
                cleared += 1
                cleared_channels.add(ch)
                _log(f"==== 原点近距离清除 ch={ch} 累计={cleared} ====")
        else:
            silent_channels.append(ch)

    _log(f"预扫描完成：有信号 {len(active_channels)} 个，无信号 {len(silent_channels)} 个，已清除 {cleared} 个")

    # 阶段2：对有信号频道直接交会定位清除
    _log("=== 阶段2：有信号频道直接定位清除 ===")
    for ch, svd in list(active_channels.items()):
        if ch in cleared_channels:
            continue
        if time.time() > deadline:
            break
        if _locate_and_clear(0, 0, svd, ch):
            cleared += 1
            cleared_channels.add(ch)
            _log(f"==== 清除成功 ch={ch} 累计={cleared} ====")

    # 阶段3：对未清除频道螺旋搜索
    # 包括：原点无信号的频道 + 阶段2定位失败的有信号频道
    _log("=== 阶段3：未清除频道螺旋搜索 ===")
    failed_active = [ch for ch in active_channels if ch not in cleared_channels]
    remaining_channels = (silent_channels + failed_active)
    remaining_channels = [ch for ch in remaining_channels if ch not in cleared_channels]
    if remaining_channels:
        # 两阶段搜索：先扫r=700内圈，全部清除则结束；否则扫r=1400外圈
        ring_dets = {}  # ch -> [(x, y, svd)] 同一频道在多个搜索点的检测记录
        for r in [700, 1400]:
            todo = [ch for ch in remaining_channels if ch not in cleared_channels]
            if not todo:
                break
            _log(f"--- 搜索半径 r={r}，待搜频道 {len(todo)} 个 ---")
            ring_points = [(r * math.cos(2 * math.pi * i / 6),
                            r * math.sin(2 * math.pi * i / 6)) for i in range(6)]
            for (sx, sy) in ring_points:
                if time.time() > deadline:
                    _log("时间不足，提前退出")
                    break
                todo = [ch for ch in remaining_channels if ch not in cleared_channels]
                if not todo:
                    break
                for ch in todo:
                    if time.time() > deadline:
                        break
                    resp = measure(sx, sy, ch)
                    if resp.get("accepted") is not True:
                        continue
                    result = resp.get("measure_result")
                    if result == "direction":
                        svd = resp["svd_deg"]
                        dets = ring_dets.setdefault(ch, [])
                        dets.append((sx, sy, svd))
                        # 优先用两个已测检测点直接交会（无需额外移动）
                        if _try_pair_clear(ch, dets):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 双点交会清除成功 ch={ch} 累计={cleared} ====")
                        elif _locate_and_clear(sx, sy, svd, ch):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 清除成功 ch={ch} 累计={cleared} ====")
                    elif result == "near":
                        cresp = clear(sx, sy, ch)
                        if cresp.get("clear_result") == "success":
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 近距离清除成功 ch={ch} 累计={cleared} ====")

    _log(f"搜索结束，共清除 {cleared} 个干扰源，虚拟时间 {_virtual_time}s")
    exit_sim()
    _log(f"程序运行时间: {time.time() - _real_start_time:.1f}s")


def _locate_and_clear(sx, sy, svd, ch):
    """
    从(sx,sy)测得示向度svd后，做两点交会定位并清除。
    第二点在垂直于示向度方向移动，距离依次尝试800/400/200米，各尝试两个方向，
    避免干扰源靠近区域边缘时大偏移超出有效接收半径。
    全部失败后在检测点周围做9点网格清除兜底。
    成功返回True。
    """
    rad = math.radians(svd)
    for dist in [800, 400, 200]:
        for sign in [1, -1]:
            perp_rad = rad + sign * math.pi / 2
            x2 = sx + dist * math.cos(perp_rad)
            y2 = sy + dist * math.sin(perp_rad)
            resp2 = measure(x2, y2, ch)
            if resp2.get("measure_result") == "direction":
                svd2 = resp2["svd_deg"]
                est = _triangulate(sx, sy, svd, x2, y2, svd2)
                if est:
                    cx, cy = est
                    if _grid_clear(cx, cy, ch):
                        return True
            elif resp2.get("measure_result") == "near":
                cresp = clear(x2, y2, ch)
                if cresp.get("clear_result") == "success":
                    return True
    # 兜底：在检测点周围直接网格清除
    if _grid_clear(sx, sy, ch):
        return True
    return False


def _try_pair_clear(ch, dets):
    """
    兜底策略：同一频道已积累多个检测点(dets=[(x,y,svd),...])时，
    选取与最新检测点间距足够大且交会角足够好的历史检测点，
    直接用两点示向度交会并网格清除，无需额外移动。
    成功返回True。
    """
    cx0, cy0, svd0 = dets[-1]
    candidates = []
    for (px, py, psvd) in dets[:-1]:
        if math.hypot(cx0 - px, cy0 - py) < 300:
            continue
        # 交会角检查：|sin(θ2-θ1)|过小说明两示向度线近乎平行，估计不可靠
        s = abs(math.sin(math.radians(svd0 - psvd)))
        if s < 0.2:
            continue
        candidates.append((s, px, py, psvd))
    # 优先用交会角最大的历史检测点，几何质量最好
    candidates.sort(key=lambda t: -t[0])
    for s, px, py, psvd in candidates:
        est = _triangulate(px, py, psvd, cx0, cy0, svd0)
        if est is not None and _grid_clear(est[0], est[1], ch):
            return True
    return False


def _grid_clear(cx, cy, ch, radius=25):
    """在(cx,cy)周围9点尝试清除（中心+8方向，半径25米），成功返回True。"""
    offsets = [(0, 0)]
    for ang in range(0, 360, 45):
        r = math.radians(ang)
        offsets.append((radius * math.cos(r), radius * math.sin(r)))
    for (dx, dy) in offsets:
        cresp = clear(cx + dx, cy + dy, ch)
        if cresp.get("clear_result") == "success":
            return True
    return False


def _ray_clear(sx, sy, svd, ch, max_dist=1500, step=35):
    """
    沿示向度方向射线步进清除（边界月牙单点接触兜底）。
    从检测点沿svd方向每step米尝试一次清除，最多前进max_dist米。
    适用于朝外定向干扰源只在边界圈上单点可见、无法两点交会的情形。
    成功返回True。
    """
    rad = math.radians(svd)
    t = step
    while t <= max_dist:
        x = sx + t * math.cos(rad)
        y = sy + t * math.sin(rad)
        if math.hypot(x, y) > 1800:
            break
        cresp = clear(x, y, ch)
        if cresp.get("clear_result") == "success":
            return True
        t += step
    return False


def _spiral_points(r_max=1800, step=800):
    """生成螺旋扫描点列表。"""
    points = [(0, 0)]
    r = step
    while r <= r_max:
        n = max(6, int(2 * math.pi * r / step))
        for i in range(n):
            theta = 2 * math.pi * i / n
            points.append((r * math.cos(theta), r * math.sin(theta)))
        r += step
    return points


def _triangulate(x1, y1, a1, x2, y2, a2):
    """两点示向度交会定位。a1,a2为示向度(度)。"""
    r1 = math.radians(a1)
    r2 = math.radians(a2)
    # 直线1: (x1,y1) + t*(cos r1, sin r1)
    # 直线2: (x2,y2) + s*(cos r2, sin r2)
    dx, dy = x2 - x1, y2 - y1
    c1, s1 = math.cos(r1), math.sin(r1)
    c2, s2 = math.cos(r2), math.sin(r2)
    denom = c1 * s2 - s1 * c2
    if abs(denom) < 1e-9:
        return None
    t = (dx * s2 - dy * c2) / denom
    return (x1 + t * c1, y1 + t * s1)


# 仅测试连接（不执行搜索）
def test_connection_only():
    resp = enter()
    if resp.get("accepted") is not True:
        print("连接失败，请检查模拟器是否已开始测试、接口是否就绪")
        return
    print("连接成功！剩余现实时间:", resp.get("remaining_real_duration_s"), "秒")
    measure(0, 0, 1)
    exit_sim()
    print("连通性测试完成")


# 问题4：含定向干扰源的搜索策略
def problem4_search():
    """
    问题4策略 v2：全向+定向干扰源混合场景
    1. 原点预扫描全频道
    2. 有信号频道：多方向第二点交会定位（±90°, ±45°）
    3. 未清除频道：三圈密集搜索（r=500/1000/1500）
    4. 持续无信号频道：边界圈r=1800（36点加密）专项搜索；
       边界月牙接触点不足两点交会时，沿示向度射线步进清除兜底
    """
    enter_resp = enter()
    if enter_resp.get("accepted") is not True:
        _log("进入失败，退出")
        return

    remaining = enter_resp.get("remaining_real_duration_s", 1200)
    deadline = time.time() + remaining - 30

    cleared = 0
    cleared_channels = set()

    # 阶段1：原点全频道预扫描
    _log("=== 阶段1：原点全频道预扫描 ===")
    active_channels = {}  # ch -> svd_deg
    silent_channels = []
    for ch in range(1, 21):
        if time.time() > deadline:
            break
        resp = measure(0, 0, ch)
        if resp.get("accepted") is not True:
            continue
        result = resp.get("measure_result")
        if result == "direction":
            active_channels[ch] = resp["svd_deg"]
        elif result == "near":
            cresp = clear(0, 0, ch)
            if cresp.get("clear_result") == "success":
                cleared += 1
                cleared_channels.add(ch)
                _log(f"==== 原点近距离清除 ch={ch} 累计={cleared} ====")
        else:
            silent_channels.append(ch)

    _log(f"预扫描：有信号 {len(active_channels)} 个，无信号 {len(silent_channels)} 个，已清除 {cleared} 个")

    # 阶段2：有信号频道多方向交会定位清除
    _log("=== 阶段2：有信号频道多方向定位清除 ===")
    for ch, svd in list(active_channels.items()):
        if ch in cleared_channels:
            continue
        if time.time() > deadline:
            break
        if _locate_and_clear_multi(0, 0, svd, ch):
            cleared += 1
            cleared_channels.add(ch)
            _log(f"==== 清除成功 ch={ch} 累计={cleared} ====")

    # 阶段3：未清除频道两阶段环形搜索
    _log("=== 阶段3：未清除频道两阶段环形搜索 ===")
    failed_active = [ch for ch in active_channels if ch not in cleared_channels]
    remaining_channels = [ch for ch in (silent_channels + failed_active)
                          if ch not in cleared_channels]

    ring_dets = {}  # ch -> [(x, y, svd)] 同一频道在多个搜索点的检测记录
    skip_phase4 = False
    if remaining_channels:
        # 三阶段搜索：r=500内圈 → r=1000中圈 → r=1500外圈
        # 每圈点数足够覆盖定向干扰源的180°覆盖角
        search_rings = [
            (500, 8),    # 内圈8点
            (1000, 8),   # 中圈8点
            (1500, 18),  # 外圈18点（加密，覆盖切向定向干扰源）
        ]
        for r, n in search_rings:
            todo = [ch for ch in remaining_channels if ch not in cleared_channels]
            if not todo:
                break
            _log(f"--- 搜索半径 r={r}，{n}个点，待搜 {len(todo)} 频道 ---")
            points = [(r * math.cos(2 * math.pi * i / n),
                       r * math.sin(2 * math.pi * i / n)) for i in range(n)]
            for (sx, sy) in points:
                if time.time() > deadline:
                    _log("时间不足，提前退出")
                    break
                todo = [ch for ch in remaining_channels if ch not in cleared_channels]
                if not todo:
                    break
                for ch in todo:
                    if time.time() > deadline:
                        break
                    resp = measure(sx, sy, ch)
                    if resp.get("accepted") is not True:
                        continue
                    result = resp.get("measure_result")
                    if result == "direction":
                        svd = resp["svd_deg"]
                        dets = ring_dets.setdefault(ch, [])
                        dets.append((sx, sy, svd))
                        if _try_pair_clear(ch, dets):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 双点交会清除成功 ch={ch} 累计={cleared} ====")
                        elif _locate_and_clear_multi(sx, sy, svd, ch):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 清除成功 ch={ch} 累计={cleared} ====")
                    elif result == "near":
                        cresp = clear(sx, sy, ch)
                        if cresp.get("clear_result") == "success":
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 近距离清除成功 ch={ch} 累计={cleared} ====")

    # 阶段4：定向干扰源专项搜索（针对持续无信号的频道）
    _log("=== 阶段4：定向干扰源专项搜索 ===")
    still_missing = [ch for ch in range(1, 21) if ch not in cleared_channels]
    if still_missing and not skip_phase4:
        _log(f"仍有 {len(still_missing)} 个频道未清除，进行定向专项搜索")
        # 拆分策略：已见频道（历史检测到过信号）补中圈角度；
        # 未见频道（全程no_signal）走区域边界圈r=1800（36点加密）。
        # 朝外定向干扰源的可见弧仅在边界圈上，且弧宽随其距原点距离增大而收窄，
        # r=1700圈对距原点>约1650m的朝外干扰源可能整圈不可见，故必须在r=1800上加密扫描。
        seen = [ch for ch in still_missing if ch in ring_dets]
        unseen = [ch for ch in still_missing if ch not in ring_dets]
        _log(f"已见未清除 {len(seen)} 个，未见 {len(unseen)} 个")
        phase4_plan = []
        if seen:
            phase4_plan.append(("已见频道补充定位", list(seen), (1000, 12), False))
        if unseen:
            phase4_plan.append(("未见频道边界圈", list(unseen), (1800, 36), True))
        for phase_name, chs, (r, n), skip_offsets in phase4_plan:
            _log(f"--- {phase_name}：r={r}，{n}个点 ---")
            points = [(r * math.cos(2 * math.pi * i / n),
                       r * math.sin(2 * math.pi * i / n)) for i in range(n)]
            for (sx, sy) in points:
                if time.time() > deadline:
                    break
                todo = [ch for ch in chs if ch not in cleared_channels]
                if not todo:
                    break
                for ch in todo:
                    resp = measure(sx, sy, ch)
                    if resp.get("accepted") is not True:
                        continue
                    result = resp.get("measure_result")
                    if result == "direction":
                        svd = resp["svd_deg"]
                        dets = ring_dets.setdefault(ch, [])
                        dets.append((sx, sy, svd))
                        if _try_pair_clear(ch, dets):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 双点交会清除成功 ch={ch} 累计={cleared} ====")
                        elif not skip_offsets and _locate_and_clear_multi(sx, sy, svd, ch):
                            # 边界月牙频道跳过偏移定位：偏移方向沿切线离开边界后
                            # 朝外干扰源立即不可见，偏移无效，交由射线步进兜底
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 定向专项清除成功 ch={ch} 累计={cleared} ====")
                    elif result == "near":
                        cresp = clear(sx, sy, ch)
                        if cresp.get("clear_result") == "success":
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 近距离清除成功 ch={ch} 累计={cleared} ====")

        # 阶段4二轮加密：首轮边界圈后仍无任何接触的未见频道
        # 等效间隔由10°加密到5°：任何可见弧>=5°的朝外干扰源保证被至少一个点捕获，
        # 只剩距原点约1798m以上、几乎贴边界的极窄月牙仍有一定漏检概率（面积占比<0.2%）
        still_unseen = [ch for ch in unseen if ch not in cleared_channels and ch not in ring_dets]
        if still_unseen:
            _log(f"--- 未见频道边界圈二轮加密(错位5°)：{len(still_unseen)} 个频道 ---")
            pts2 = [(1800 * math.cos(2 * math.pi * (i + 0.5) / 36),
                     1800 * math.sin(2 * math.pi * (i + 0.5) / 36)) for i in range(36)]
            for (sx, sy) in pts2:
                if time.time() > deadline:
                    break
                todo = [ch for ch in still_unseen if ch not in cleared_channels]
                if not todo:
                    break
                for ch in todo:
                    resp = measure(sx, sy, ch)
                    if resp.get("accepted") is not True:
                        continue
                    result = resp.get("measure_result")
                    if result == "direction":
                        svd = resp["svd_deg"]
                        dets = ring_dets.setdefault(ch, [])
                        dets.append((sx, sy, svd))
                        if _try_pair_clear(ch, dets):
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 双点交会清除成功 ch={ch} 累计={cleared} ====")
                    elif result == "near":
                        cresp = clear(sx, sy, ch)
                        if cresp.get("clear_result") == "success":
                            cleared += 1
                            cleared_channels.add(ch)
                            _log(f"==== 近距离清除成功 ch={ch} 累计={cleared} ====")

        # 阶段4兜底：对仍有边界接触但未清除的频道做射线步进清除
        # 月牙在边界圈上可能只见1-2个点，双点交会条件不足时，
        # 从接触点沿示向度射线每35m步进清除，最多1500m（有效接收半径上限）
        leftovers = [ch for ch in range(1, 21) if ch not in cleared_channels]
        for ch in leftovers:
            dets = ring_dets.get(ch, [])
            if not dets:
                continue
            for (px, py, psvd) in reversed(dets):
                if time.time() > deadline:
                    break
                if _ray_clear(px, py, psvd, ch):
                    cleared += 1
                    cleared_channels.add(ch)
                    _log(f"==== 射线步进清除成功 ch={ch} 累计={cleared} ====")
                    break

    _log(f"搜索结束，共清除 {cleared} 个干扰源，虚拟时间 {_virtual_time}s")
    exit_sim()
    _log(f"程序运行时间: {time.time() - _real_start_time:.1f}s")


def _locate_and_clear_multi(sx, sy, svd, ch):
    """
    多方向第二检测点交会定位清除（适配定向干扰源）。
    距离依次尝试800/400米，每个距离尝试+90°、-90°、+45°、-45°四个方向，
    避免边缘干扰源因偏移超出发射/接收范围而漏检。
    找到信号(direction)：做交会定位+网格清除；清除失败则继续尝试。
    全部失败后在检测点周围网格清除兜底。
    """
    rad = math.radians(svd)
    for dist in [800, 400]:
        for d in [math.pi / 2, -math.pi / 2, math.pi / 4, -math.pi / 4]:
            perp_rad = rad + d
            x2 = sx + dist * math.cos(perp_rad)
            y2 = sy + dist * math.sin(perp_rad)
            resp2 = measure(x2, y2, ch)
            if resp2.get("measure_result") == "direction":
                svd2 = resp2["svd_deg"]
                est = _triangulate(sx, sy, svd, x2, y2, svd2)
                if est:
                    cx, cy = est
                    if _grid_clear(cx, cy, ch):
                        return True
            elif resp2.get("measure_result") == "near":
                cresp = clear(x2, y2, ch)
                if cresp.get("clear_result") == "success":
                    return True
    # 兜底：在检测点周围直接网格清除
    if _grid_clear(sx, sy, ch):
        return True
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_connection_only()
        elif sys.argv[1] == "p4":
            problem4_search()
        else:
            simple_search_omnidirectional()
    else:
        simple_search_omnidirectional()
