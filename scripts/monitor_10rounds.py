#!/usr/bin/env python3
"""10-round simulation monitor — tracks robot state, detects issues, reports results."""

import subprocess, time, json, sys, os
from pathlib import Path
from collections import defaultdict

LOG_FILE = Path("/tmp/h2track_10rounds_monitor.jsonl")
RESULTS_FILE = Path("/tmp/h2track_10rounds_report.json")

def ros2_topic(topic, once=True):
    """Read a ROS2 topic value."""
    cmd = ["timeout", "3", "ros2", "topic", "echo", topic]
    if once:
        cmd.append("--once")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                               env={**os.environ, "PYTHONUNBUFFERED": "1"})
        return result.stdout.strip()
    except:
        return ""

def parse_odom(output):
    """Parse odometry to get x,y position."""
    x = y = None
    for line in output.split("\n"):
        line = line.strip()
        if "x:" in line and "position:" not in prev_line(output, line):
            try:
                x = float(line.split(":")[-1].strip())
            except: pass
        if "y:" in line and "position:" not in prev_line(output, line):
            try:
                y = float(line.split(":")[-1].strip())
            except: pass
    # Actually, parse more carefully
    lines = output.split("\n")
    in_position = False
    for line in lines:
        if "position:" in line:
            in_position = True
            continue
        if in_position:
            if "x:" in line and x is None:
                try: x = float(line.split(":")[-1].strip())
                except: pass
            elif "y:" in line and y is None:
                try: y = float(line.split(":")[-1].strip())
                except: pass
            elif "z:" in line:
                break
    return x, y

def prev_line(output, current):
    lines = output.split("\n")
    for i, l in enumerate(lines):
        if l.strip() == current.strip() and i > 0:
            return lines[i-1].strip()
    return ""

def get_robot_state():
    """Get current robot state snapshot."""
    mode_out = ros2_topic("/robot_mode")
    conc_out = ros2_topic("/gas_concentration")
    odom_out = ros2_topic("/odom")
    mode = mode_out.split("data:")[-1].strip() if mode_out else "UNKNOWN"
    conc = conc_out.split("data:")[-1].strip() if conc_out else "0"
    x, y = parse_odom(odom_out) if odom_out else (None, None)
    return {"mode": mode, "conc": float(conc) if conc else 0, "x": x, "y": y}

def round_summary(round_num, samples):
    """Summarize a round from samples."""
    if not samples:
        return {"round": round_num, "success": False, "error": "no data"}

    modes = [s["mode"] for s in samples]
    concs = [s["conc"] for s in samples]
    xs = [s["x"] for s in samples if s["x"] is not None]
    ys = [s["y"] for s in samples if s["y"] is not None]

    source_found = "SOURCE_FOUND" in modes
    seek_tracked = "SEEK_TRACK" in modes
    max_conc = max(concs) if concs else 0

    # Detect stuck: less than 0.3m movement over last 10 samples
    stuck_count = 0
    if len(xs) >= 10:
        recent_xs = xs[-10:]
        recent_ys = ys[-10:]
        movement = ((recent_xs[-1] - recent_xs[0])**2 + (recent_ys[-1] - recent_ys[0])**2)**0.5
        if movement < 0.3:
            stuck_count = 1

    # Detect wall collision: rapid costmap clearing indicates obstacle issues
    # (we count mode-switching as indicator of recovery attempts)
    mode_changes = sum(1 for i in range(1, len(modes)) if modes[i] != modes[i-1])

    # Moving distance
    total_dist = 0
    if len(xs) >= 2:
        for i in range(1, len(xs)):
            total_dist += ((xs[i]-xs[i-1])**2 + (ys[i]-ys[i-1])**2)**0.5

    return {
        "round": round_num,
        "success": source_found,
        "seek_tracked": seek_tracked,
        "max_conc": max_conc,
        "modes_seen": list(set(modes)),
        "mode_changes": mode_changes,
        "samples": len(samples),
        "total_dist_m": round(total_dist, 2),
        "stuck_detected": stuck_count > 0,
    }

def main():
    print("=" * 70)
    print("H2Track 10轮仿真测试监控")
    print("=" * 70)

    # Source env
    os.environ["DISPLAY"] = ":0"

    for round_num in range(1, 11):
        print(f"\n{'='*70}")
        print(f"🔄 第 {round_num}/10 轮测试开始")
        print(f"{'='*70}")

        # Launch simulation
        log_path = f"/tmp/h2track_round{round_num}.log"
        launch_cmd = (
            "source /opt/ros/humble/setup.bash && "
            "source /home/user/h2track-xian/install/setup.bash && "
            f"timeout 120 ros2 launch h2track_bringup demo.launch.py scene:=baseline use_gaden:=false 2>&1"
        )

        proc = subprocess.Popen(
            ["bash", "-c", launch_cmd],
            stdout=open(log_path, "w"), stderr=subprocess.STDOUT
        )

        print(f"  Launch PID: {proc.pid}")
        print(f"  等待系统启动 (30s)...")
        time.sleep(30)

        # Monitor for 80 seconds (sampling every 5s)
        samples = []
        print(f"  开始监控 (每5秒采样, 共16次)...")

        for i in range(16):
            state = get_robot_state()
            state["t"] = i * 5
            samples.append(state)
            pos_str = f"({state['x']:.1f},{state['y']:.1f})" if state['x'] else "(?,?)"
            print(f"    t={state['t']:3d}s 模式={state['mode']:<15s} 浓度={state['conc']:6.1f} 位置={pos_str}")
            time.sleep(5)

        # Kill simulation
        print(f"  终止第{round_num}轮...")
        proc.terminate()
        time.sleep(2)
        subprocess.run(["pkill", "-9", "-f", "ros2"], capture_output=True)
        subprocess.run(["pkill", "-9", "-f", "gz"], capture_output=True)
        time.sleep(2)

        # Summarize
        summary = round_summary(round_num, samples)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(summary) + "\n")

        found_str = "✅ SOURCE_FOUND" if summary["success"] else ("⚠️ SEEK_TRACK" if summary["seek_tracked"] else "❌ PATROL only")
        print(f"  结果: {found_str} | 最高浓度: {summary['max_conc']:.1f} | 移动距离: {summary['total_dist_m']:.1f}m | 卡住: {summary['stuck_detected']}")

    # Final report
    print(f"\n{'='*70}")
    print("📊 10轮测试汇总报告")
    print(f"{'='*70}")

    all_rounds = []
    with open(LOG_FILE) as f:
        for line in f:
            all_rounds.append(json.loads(line))

    source_found_count = sum(1 for r in all_rounds if r["success"])
    seek_count = sum(1 for r in all_rounds if r["seek_tracked"])
    stuck_count = sum(1 for r in all_rounds if r.get("stuck_detected"))
    avg_dist = sum(r.get("total_dist_m", 0) for r in all_rounds) / len(all_rounds) if all_rounds else 0
    avg_max_conc = sum(r["max_conc"] for r in all_rounds) / len(all_rounds) if all_rounds else 0

    print(f"  总轮数: {len(all_rounds)}")
    print(f"  SOURCE_FOUND: {source_found_count}/{len(all_rounds)} ({100*source_found_count/len(all_rounds):.0f}%)")
    print(f"  SEEK_TRACK: {seek_count}/{len(all_rounds)} ({100*seek_count/len(all_rounds):.0f}%)")
    print(f"  卡住次数: {stuck_count}/{len(all_rounds)}")
    print(f"  平均移动距离: {avg_dist:.1f}m")
    print(f"  平均最高浓度: {avg_max_conc:.1f} ppm")

    # Save report
    report = {
        "total_rounds": len(all_rounds),
        "source_found_rate": source_found_count / len(all_rounds),
        "seek_track_rate": seek_count / len(all_rounds),
        "stuck_rate": stuck_count / len(all_rounds),
        "avg_distance_m": avg_dist,
        "avg_max_conc": avg_max_conc,
        "rounds": all_rounds,
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  详细报告: {RESULTS_FILE}")

if __name__ == "__main__":
    main()
