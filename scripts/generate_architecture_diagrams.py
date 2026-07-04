#!/usr/bin/env python3
"""Generate H2Track architecture diagrams (Chinese) as JPG images using pygraphviz.

生成3张中文架构图:
  1. system_architecture.jpg — 8包分层系统架构
  2. node_communication.jpg — ROS节点通信与数据流
  3. algorithm_pipeline.jpg — 行为树+状态机+算法融合管线

用法:
    python3 scripts/generate_architecture_diagrams.py [--output-dir OUTPUT_DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pygraphviz as pgv

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "diagrams"


def _setup_graph(
    title: str,
    rankdir: str = "TB",
    dpi: int = 150,
    ratio: str = "compress",
) -> pgv.AGraph:
    """创建带统一样式的有向图"""
    g = pgv.AGraph(
        name=title,
        directed=True,
        strict=False,
        rankdir=rankdir,
        dpi=str(dpi),
        ratio=ratio,
        fontname="Noto Sans CJK SC",
        fontsize="16",
        label=title,
        labelloc="t",
        labeljust="c",
        pad="0.5",
        nodesep="0.4",
        ranksep="0.7",
        bgcolor="white",
        margin="0.3",
    )
    g.node_attr.update(
        fontname="Noto Sans CJK SC",
        fontsize="11",
        shape="box",
        style="filled,rounded",
        fillcolor="#E8F0FE",
        color="#1A73E8",
        penwidth="1.5",
    )
    g.edge_attr.update(
        fontname="Noto Sans CJK SC",
        fontsize="9",
        color="#5F6368",
        arrowsize="0.8",
    )
    return g


# ---------------------------------------------------------------------------
# 图1: 系统包架构图（中文）
# ---------------------------------------------------------------------------

def _build_system_architecture() -> pgv.AGraph:
    g = _setup_graph(
        "H2Track 系统架构 — 8包分层结构",
        rankdir="TB",
    )

    # 消息接口层（底部）
    g.add_node(
        "interfaces",
        label="h2track_interfaces\n自定义 ROS 2 消息",
        fillcolor="#D2E3FC",
        color="#1A73E8",
    )

    # 核心算法包层
    g.add_node(
        "tracking",
        label=(
            "h2track_tracking\n"
            "行为树 · 追踪算法 · 粒子滤波\n"
            "任务状态机 · 多算法融合"
        ),
        fillcolor="#E8F0FE",
    )
    g.add_node(
        "gas_sim",
        label=(
            "h2track_gas_sim\n"
            "气体仿真 · GADEN 适配器\n"
            "MOX 传感器模型 · 风速模型"
        ),
        fillcolor="#E8F0FE",
    )
    g.add_node(
        "web",
        label=(
            "h2track_web\n"
            "FastAPI Web控制台\n"
            "WebSocket 实时流 · 热力图可视化"
        ),
        fillcolor="#E8F0FE",
    )
    g.add_node(
        "utils",
        label=(
            "h2track_utils\n"
            "Nav2 生命周期管理 · 演示自检\n"
            "回归测试 · 地图保存 · Pose2D"
        ),
        fillcolor="#E8F0FE",
    )

    # 集成启动层
    g.add_node(
        "bringup",
        label=(
            "h2track_bringup\n"
            "启动文件 · 场景配置\n"
            "Gazebo世界 · RViz配置 · Nav2参数"
        ),
        fillcolor="#CEEAD6",
        color="#34A853",
    )

    # 描述与元包层
    g.add_node(
        "description",
        label="h2track_description\nURDF/Xacro机器人描述",
        fillcolor="#FCE8E6",
        color="#EA4335",
    )
    g.add_node(
        "sim",
        label="h2track_sim\n(元包)",
        fillcolor="#FCE8E6",
        color="#EA4335",
    )

    # 依赖边
    g.add_edge("interfaces", "tracking", label="依赖")
    g.add_edge("interfaces", "gas_sim", label="依赖")
    g.add_edge("interfaces", "web", label="依赖")
    g.add_edge("utils", "tracking", label="依赖")
    g.add_edge("tracking", "bringup", label="运行时依赖")
    g.add_edge("gas_sim", "bringup", label="运行时依赖")
    g.add_edge("description", "bringup", label="运行时依赖")
    g.add_edge("description", "sim", label="依赖")
    g.add_edge("bringup", "sim", label="依赖")

    # 子图分组
    g.add_subgraph(
        ["interfaces"],
        rank="source",
        name="cluster_msg",
        label="消息接口层",
        style="dashed",
        color="#1A73E8",
        fontname="Noto Sans CJK SC",
        fontsize="12",
    )
    g.add_subgraph(
        ["tracking", "gas_sim", "web", "utils"],
        rank="same",
        name="cluster_core",
        label="核心算法与工具包",
        style="dashed",
        color="#34A853",
        fontname="Noto Sans CJK SC",
        fontsize="12",
    )
    g.add_subgraph(
        ["description", "sim"],
        rank="same",
        name="cluster_desc",
        label="描述与元包层",
        style="dashed",
        color="#EA4335",
        fontname="Noto Sans CJK SC",
        fontsize="12",
    )

    return g


# ---------------------------------------------------------------------------
# 图2: ROS节点通信图（中文）
# ---------------------------------------------------------------------------

def _build_node_communication() -> pgv.AGraph:
    g = _setup_graph(
        "H2Track ROS节点通信 — 话题与数据流",
        rankdir="LR",
    )
    g.node_attr.update(fontsize="9")

    # 外部系统节点
    ext_style = {"fillcolor": "#F1F3F4", "color": "#9AA0A6", "shape": "box", "style": "filled,rounded"}
    g.add_node("gazebo", label="Gazebo 仿真\n(物理引擎 + 差速驱动)", **ext_style)
    g.add_node("gaden", label="GADEN CFD\n(气体扩散仿真)", **ext_style)
    g.add_node("nav2", label="Nav2 导航栈\n(AMCL · Planner · Controller)", **ext_style)
    g.add_node("rviz", label="RViz2\n(可视化)", **ext_style)

    # ROS节点
    gas_style = {"fillcolor": "#E8F0FE", "color": "#1A73E8", "shape": "ellipse", "style": "filled"}
    track_style = {"fillcolor": "#CEEAD6", "color": "#34A853", "shape": "ellipse", "style": "filled"}
    pf_style = {"fillcolor": "#FCE8E6", "color": "#EA4335", "shape": "ellipse", "style": "filled"}
    web_style = {"fillcolor": "#FFF3CD", "color": "#F9AB00", "shape": "ellipse", "style": "filled"}

    g.add_node("gas_field", label="gas_field_node\n(简化气体仿真)", **gas_style)
    g.add_node("gaden_adapter", label="gaden_adapter_node\n(GADEN适配)", **gas_style)
    g.add_node("anemometer", label="anemometer_adapter_node\n(风速适配)", **gas_style)
    g.add_node("bt_runner", label="bt_node_runner\n(行为树主编排)", **track_style)
    g.add_node("pf_node", label="particle_filter_node\n(粒子滤波源定位)", **pf_style)
    g.add_node("ground_truth", label="ground_truth_sampler\n(真值评估)", **pf_style)
    g.add_node("web_server", label="demo_web_server\n(FastAPI + WebSocket)", **web_style)
    g.add_node("nav2_gate", label="nav2_startup_gate\n(Nav2就绪检测)", fillcolor="#E8F0FE", color="#1A73E8", shape="ellipse", style="filled")

    # 话题节点
    topic_style = {"shape": "note", "fillcolor": "#FFFFFF", "color": "#5F6368", "fontsize": "8", "style": "filled"}
    g.add_node("topic_gas", label="/gas_concentration\n气体浓度 (5Hz)", **topic_style)
    g.add_node("topic_pose", label="/amcl_pose\n机器人位姿", **topic_style)
    g.add_node("topic_source", label="/estimated_source\n源位姿估计 (2Hz)", **topic_style)
    g.add_node("topic_wind", label="/estimated_wind\n风速估计 (10Hz)", **topic_style)
    g.add_node("topic_cloud", label="/particle_cloud\n粒子云可视化 (2Hz)", **topic_style)
    g.add_node("topic_odom", label="/odom\n里程计 (50Hz)", **topic_style)
    g.add_node("topic_mode", label="/robot_mode\n机器人任务模式", **topic_style)
    g.add_node("topic_found", label="/source_found\n源发现信号", **topic_style)
    g.add_node("action_nav", label="/navigate_to_pose\nNav2目标动作", shape="component", fillcolor="#FFF3CD", color="#F9AB00", style="filled", fontsize="8")

    # 数据流边
    g.add_edge("gazebo", "topic_odom", label="发布")
    g.add_edge("gazebo", "nav2", label="/scan /odom")
    g.add_edge("nav2", "topic_pose", label="发布")
    g.add_edge("gas_field", "topic_gas", label="发布")
    g.add_edge("gaden", "gaden_adapter", label="GasSensor")
    g.add_edge("gaden", "anemometer", label="风速数据")
    g.add_edge("gaden_adapter", "topic_gas", label="发布")
    g.add_edge("anemometer", "topic_wind", label="发布")
    g.add_edge("topic_gas", "bt_runner", label="订阅")
    g.add_edge("topic_gas", "pf_node", label="订阅")
    g.add_edge("topic_pose", "bt_runner", label="订阅")
    g.add_edge("topic_source", "bt_runner", label="订阅")
    g.add_edge("topic_wind", "bt_runner", label="订阅")
    g.add_edge("topic_wind", "pf_node", label="订阅")
    g.add_edge("topic_odom", "pf_node", label="订阅")
    g.add_edge("pf_node", "topic_source", label="发布")
    g.add_edge("pf_node", "topic_cloud", label="发布")
    g.add_edge("bt_runner", "topic_mode", label="发布")
    g.add_edge("bt_runner", "topic_found", label="发布")
    g.add_edge("bt_runner", "action_nav", label="发送目标")
    g.add_edge("action_nav", "nav2", label="执行动作")
    g.add_edge("nav2_gate", "nav2", label="生命周期检测")
    g.add_edge("nav2_gate", "bt_runner", label="就绪信号")

    # Web服务器订阅
    g.add_edge("topic_mode", "web_server", label="订阅")
    g.add_edge("topic_gas", "web_server", label="订阅")
    g.add_edge("topic_found", "web_server", label="订阅")
    g.add_edge("topic_odom", "web_server", label="订阅")
    g.add_edge("topic_cloud", "web_server", label="订阅")
    g.add_edge("topic_source", "web_server", label="订阅")
    g.add_edge("topic_pose", "web_server", label="订阅")

    # RViz订阅
    g.add_edge("topic_cloud", "rviz", label="订阅")
    g.add_edge("topic_source", "rviz", label="订阅")

    # Ground truth
    g.add_edge("gaden", "ground_truth", label="/odor_value\n(气体位置真值查询)")

    return g


# ---------------------------------------------------------------------------
# 图3: 算法管线图（中文）
# ---------------------------------------------------------------------------

def _build_algorithm_pipeline() -> pgv.AGraph:
    g = _setup_graph(
        "H2Track 算法管线 — 行为树 + 状态机 + 多算法融合",
        rankdir="TB",
    )
    g.node_attr.update(fontsize="9")

    # 行为树节点
    g.add_node(
        "bt_root",
        label="MissionRoot\n(Selector 选择器)",
        fillcolor="#1A73E8",
        color="#1A73E8",
        fontcolor="white",
        fontsize="12",
        shape="box",
        style="filled",
    )
    g.add_node(
        "bt_source",
        label="SourceFound\n检测源发现状态",
        fillcolor="#34A853",
        color="#34A853",
        fontcolor="white",
        shape="box",
        style="filled,rounded",
    )
    g.add_node(
        "bt_seek",
        label="SeekTrack\n成本防护 → 追踪融合 → Nav2客户端",
        fillcolor="#FBBC04",
        color="#FBBC04",
        shape="box",
        style="filled,rounded",
    )
    g.add_node(
        "bt_patrol",
        label="Patrol\n成本防护 → Nav2客户端\n(处理 SEEK_CONFIRM)",
        fillcolor="#EA4335",
        color="#EA4335",
        fontcolor="white",
        shape="box",
        style="filled,rounded",
    )

    g.add_edge("bt_root", "bt_source", label="优先级最高")
    g.add_edge("bt_root", "bt_seek", label="优先级第二")
    g.add_edge("bt_root", "bt_patrol", label="优先级最低")

    # 状态机节点
    sm_style = {"shape": "ellipse", "style": "filled"}
    g.add_node("sm_patrol", label="PATROL\n巡航巡逻", fillcolor="#EA4335", fontcolor="white", **sm_style)
    g.add_node("sm_confirm", label="SEEK_CONFIRM\n检测确认", fillcolor="#FBBC04", **sm_style)
    g.add_node("sm_track", label="SEEK_TRACK\n追踪寻源", fillcolor="#34A853", fontcolor="white", **sm_style)
    g.add_node("sm_found", label="SOURCE_FOUND\n源已找到", fillcolor="#1A73E8", fontcolor="white", **sm_style)

    g.add_edge("sm_patrol", "sm_confirm", label="浓度 > 检测阈值")
    g.add_edge("sm_confirm", "sm_track", label="持续高浓度\n确认检测")
    g.add_edge("sm_track", "sm_found", label="浓度 > 源阈值\n+ 半径范围内")
    g.add_edge("sm_confirm", "sm_patrol", label="浓度 < 退出阈值")
    g.add_edge("sm_track", "sm_patrol", label="羽流丢失\n超时")
    g.add_edge("sm_found", "sm_patrol", label="重新检测")

    # 算法管线
    alg_style = {"shape": "box", "style": "filled,rounded", "fontsize": "9"}
    g.add_node("sensor", label="气体传感器\n/gas_concentration", fillcolor="#E8F0FE", **alg_style)
    g.add_node("wind_est", label="风速估计器\n(梯度法 / GADEN真值)", fillcolor="#E8F0FE", **alg_style)
    g.add_node("surge_cast", label="Surge-Cast 追踪器\n逆风前进 + 横向搜索", fillcolor="#CEEAD6", **alg_style)
    g.add_node("particle_filter", label="粒子滤波\n500粒子 + 高斯羽流模型\n预测-更新-重采样", fillcolor="#FCE8E6", **alg_style)
    g.add_node("fusion", label="多算法融合\n加权平均 / 切换 / 级联\nSurge-Cast 70% + PF 30%", fillcolor="#FFF3CD", **alg_style)
    g.add_node("costmap", label="Costmap 安全防护\n障碍物检测", fillcolor="#E8F0FE", **alg_style)
    g.add_node("nav2_client", label="Nav2客户端\nNavigateToPose 动作", fillcolor="#D2E3FC", **alg_style)

    g.add_edge("sensor", "wind_est", label="浓度梯度")
    g.add_edge("sensor", "surge_cast", label="羽流检测")
    g.add_edge("sensor", "particle_filter", label="权重更新")
    g.add_edge("wind_est", "surge_cast", label="风向矢量")
    g.add_edge("surge_cast", "fusion", label="目标 + 置信度")
    g.add_edge("particle_filter", "fusion", label="估计 + 协方差")
    g.add_edge("fusion", "costmap", label="目标位姿")
    g.add_edge("costmap", "nav2_client", label="安全目标")
    g.add_edge("nav2_client", "surge_cast", label="导航结果", style="dashed", color="#9AA0A6")
    g.add_edge("nav2_client", "particle_filter", label="新位姿", style="dashed", color="#9AA0A6")

    # 状态机与算法的关联
    g.add_edge("sm_track", "surge_cast", label="激活追踪", style="dotted", color="#34A853", penwidth="2")
    g.add_edge("bt_seek", "surge_cast", label="执行行为", style="dotted", color="#FBBC04", penwidth="2")

    return g


# ---------------------------------------------------------------------------
# 渲染辅助
# ---------------------------------------------------------------------------

def _render(g: pgv.AGraph, out_path: Path) -> None:
    """布局并渲染图形为JPG"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.layout(prog="dot")
    g.draw(out_path, format="jpg")
    size_kb = out_path.stat().st_size / 1024
    print(f"  ✓ {out_path.name} ({size_kb:.0f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成H2Track中文架构图")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"输出目录 (默认: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    out_dir: Path = args.output_dir
    print(f"生成中文架构图 → {out_dir}/")
    print()

    diagrams = [
        ("system_architecture.jpg", _build_system_architecture),
        ("node_communication.jpg", _build_node_communication),
        ("algorithm_pipeline.jpg", _build_algorithm_pipeline),
    ]

    for filename, builder in diagrams:
        print(f"  构建: {filename}")
        g = builder()
        _render(g, out_dir / filename)

    print()
    print(f"完成！{len(diagrams)} 张中文架构图已生成至 {out_dir}/")


if __name__ == "__main__":
    main()
