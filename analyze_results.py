# 汇总演练结果，核对机器人日志的清除数与虚拟时间
import json
import re
from pathlib import Path

LOG_DIR = Path(r"e:\2026数模\B题\CUMCM2026B\Jammers-simulator\JammersSimulatorData\behavior-logs")
ROBOT_LOG = Path(r"e:\2026数模\B题\robot_log.txt")


def parse_result_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        d = json.load(f)
    return {
        "case_code": d["case_code"],
        "jammer_count": d["jammer_count"],
        "omni": d["omnidirectional_jammer_count"],
        "dir": d["directional_jammer_count"],
        "mtime": filepath.stat().st_mtime,
    }


def parse_robot_log():
    """从robot_log提取每次测试的(清除数, 虚拟时间)"""
    if not ROBOT_LOG.exists():
        return []
    with open(ROBOT_LOG, "r", encoding="utf-8") as f:
        text = f.read()
    runs = []
    for m in re.finditer(r"搜索结束，共清除 (\d+) 个干扰源，虚拟时间 ([\d.]+)s", text):
        runs.append((int(m.group(1)), float(m.group(2))))
    return runs


def main():
    result_files = sorted(LOG_DIR.glob("practice-p3-*.result.json"),
                          key=lambda p: p.stat().st_mtime)
    robot_runs = parse_robot_log()

    # result.json前2个是历史测试，从第3个开始对应robot_log的记录
    # 找到第一个与robot_runs数量匹配的位置
    n_runs = len(robot_runs)
    results = [parse_result_json(f) for f in result_files]
    # 取最后n_runs个result.json
    results = results[-n_runs:] if n_runs <= len(results) else results

    print("=" * 85)
    print(f"{'#':>3} {'案例编码':<22} {'总数':>4} {'清除':>4} {'比例':>6} {'虚拟时间':>10} {'平均时间':>10}")
    print("-" * 85)

    total_jammers = 0
    total_cleared = 0
    times = []
    full_clear = 0

    for i, (info, (cleared, vt)) in enumerate(zip(results, robot_runs), 1):
        ratio = cleared / info["jammer_count"] * 100 if info["jammer_count"] > 0 else 0
        avg = vt / cleared if cleared > 0 else 0
        mark = " ✅" if cleared == info["jammer_count"] and cleared > 0 else ""
        print(f"{i:>3} {info['case_code']:<22} {info['jammer_count']:>4} {cleared:>4} "
              f"{ratio:>5.1f}% {vt:>10.1f} {avg:>10.1f}{mark}")

        total_jammers += info["jammer_count"]
        total_cleared += cleared
        if cleared > 0:
            times.append(avg)
        if cleared == info["jammer_count"] and cleared > 0:
            full_clear += 1

    print("-" * 85)
    overall_ratio = total_cleared / total_jammers * 100 if total_jammers > 0 else 0
    avg_time = sum(times) / len(times) if times else 0
    print(f"{'合计/平均':<26} {total_jammers:>4} {total_cleared:>4} "
          f"{overall_ratio:>5.1f}% {'':>10} {avg_time:>10.1f}")
    print("=" * 85)
    print(f"\n共 {len(results)} 次测试，其中 {full_clear} 次 100% 清除")
    print(f"总清除率: {overall_ratio:.1f}% ({total_cleared}/{total_jammers})")
    print(f"平均定位清除时间: {avg_time:.1f} 秒 ({avg_time/60:.1f} 分钟)")
    if times:
        print(f"最短平均时间: {min(times):.1f}s, 最长平均时间: {max(times):.1f}s")


if __name__ == "__main__":
    main()
