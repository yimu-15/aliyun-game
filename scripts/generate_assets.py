"""
生成答辩 PPT 所需的可视化图表素材

输出目录: docs/assets/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUTPUT_DIR = Path("docs/assets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 配色 ──
DARK_BG = "#1a1a2e"
GOLD = "#ffd700"
BLUE = "#1f77b4"
CYAN = "#4ecdc4"
WHITE = "#ffffff"
GRAY = "#888888"
GREEN = "#2ecc71"
ORANGE = "#ff7f0e"
RED = "#d62728"

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]


def generate_architecture_diagram():
    """生成系统架构图 (三层架构)"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")
    fig.patch.set_facecolor(DARK_BG)

    layers = [
        {"y": 6.2, "h": 1.2, "color": "#2c3e6b", "title": "用户交互层",
         "items": ["Streamlit 前端 (5页面)", "FastAPI 后端 (REST API)", "参数配置 + 报告下载"]},
        {"y": 3.8, "h": 2.0, "color": "#1a3a5c", "title": "应用服务层",
         "items": ["球队评分引擎 | 泊松预测器 | 蒙特卡洛模拟", "淘汰赛模拟器 | 因子归因引擎 | 报告生成器"]},
        {"y": 1.2, "h": 2.2, "color": "#0f2a44", "title": "数据层",
         "items": ["Kaggle 44K+ 比赛 | FootballData 17届世界杯", "FIFA 64K+ 排名 | 数据清洗 | 来源追溯"]},
    ]

    for layer in layers:
        rect = mpatches.FancyBboxPatch(
            (0.5, layer["y"]), 13, layer["h"],
            boxstyle="round,pad=0.1", facecolor=layer["color"],
            edgecolor=GOLD, linewidth=1.5, alpha=0.9,
        )
        ax.add_patch(rect)

        # 层标题
        ax.text(1.0, layer["y"] + layer["h"] - 0.3, layer["title"],
                fontsize=16, fontweight="bold", color=GOLD)

        # 条目
        for i, item in enumerate(layer["items"]):
            ax.text(1.0, layer["y"] + layer["h"] - 0.75 - i * 0.4, f"  ▸ {item}",
                    fontsize=11, color=WHITE)

    # 箭头
    for y_from, y_to in [(7.4, 5.8), (5.8, 3.4)]:
        ax.annotate("", xy=(7, y_to), xytext=(7, y_from),
                    arrowprops=dict(arrowstyle="->", color=GOLD, lw=2.5))

    ax.text(7.2, 6.5, "HTTP", fontsize=10, color=GRAY)
    ax.text(7.2, 4.6, "调用", fontsize=10, color=GRAY)

    plt.tight_layout()
    path = OUTPUT_DIR / "architecture.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


def generate_data_flow_diagram():
    """生成数据流图"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")
    fig.patch.set_facecolor(DARK_BG)

    nodes = [
        (1.5, 3, "外部数据源", "Kaggle + FootballData\n+ FIFA 排名", BLUE),
        (4.5, 3, "数据加载", "load_teams()\nload_matches()", CYAN),
        (7.5, 3, "特征构建", "build_snapshots()\n5维度评分", GREEN),
        (10.5, 3, "预测引擎", "泊松 + 蒙特卡洛\n10000次模拟", ORANGE),
        (13.0, 3, "输出", "JSON/图表\n报告下载", GOLD),
    ]

    for x, y, title, desc, color in nodes:
        circle = plt.Circle((x, y), 1.05, color=color, alpha=0.85, ec=WHITE, lw=1.5)
        ax.add_patch(circle)
        ax.text(x, y + 0.25, title, ha="center", fontsize=13, fontweight="bold", color=WHITE)
        ax.text(x, y - 0.35, desc, ha="center", fontsize=9, color="#ddd")

    # 箭头
    for i in range(len(nodes) - 1):
        x1, y1 = nodes[i][0] + 1.05, nodes[i][1]
        x2, y2 = nodes[i + 1][0] - 1.05, nodes[i + 1][1]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=GOLD, lw=2.5))

    plt.tight_layout()
    path = OUTPUT_DIR / "data_flow.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


def generate_prediction_flow():
    """生成预测逻辑图 (四层架构)"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    fig.patch.set_facecolor(DARK_BG)

    steps = [
        {"y": 6.5, "color": "#2c3e6b", "num": "0", "title": "球队评分引擎",
         "desc": "历史×20% + 排名×30% + 攻防×20%\n+ 球员×15% + 状态×15% → 0-100评分"},
        {"y": 5.0, "color": "#1a3a5c", "num": "1", "title": "泊松单场预测",
         "desc": "λ = 1.32 × attack(A) × defense(B)\nP(胜/平/负) 从泊松分布推导"},
        {"y": 3.5, "color": "#0f2a44", "num": "2", "title": "赛程推演",
         "desc": "小组赛: 泊松采样 → 积分榜 → Top-2\n淘汰赛: 90min → 加时×0.33 → 点球55%"},
        {"y": 2.0, "color": "#2c3e6b", "num": "3", "title": "蒙特卡洛聚合",
         "desc": "N=10000次 → 统计夺冠次数\nWilson 95% 置信区间"},
    ]

    for i, s in enumerate(steps):
        rect = mpatches.FancyBboxPatch(
            (1.0, s["y"] - 0.6), 10, 1.2,
            boxstyle="round,pad=0.08", facecolor=s["color"],
            edgecolor=GOLD if i == 0 else GRAY, linewidth=1.5, alpha=0.9,
        )
        ax.add_patch(rect)

        # 编号圆圈
        circle = plt.Circle((1.6, s["y"]), 0.35, color=GOLD, alpha=0.9)
        ax.add_patch(circle)
        ax.text(1.6, s["y"], s["num"], ha="center", va="center",
                fontsize=14, fontweight="bold", color=DARK_BG)

        ax.text(2.3, s["y"] + 0.2, s["title"], fontsize=15, fontweight="bold", color=GOLD)
        ax.text(2.3, s["y"] - 0.25, s["desc"], fontsize=10, color="#ccc")

    # 箭头
    for i in range(len(steps) - 1):
        ax.annotate("", xy=(6, steps[i + 1]["y"] + 0.6),
                    xytext=(6, steps[i]["y"] - 0.6),
                    arrowprops=dict(arrowstyle="->", color=GOLD, lw=2.0))

    plt.tight_layout()
    path = OUTPUT_DIR / "prediction_flow.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


def generate_champion_chart():
    """生成夺冠概率排行榜图"""
    teams = ["ARG","BRA","FRA","ENG","ESP","POR","NED","GER"]
    probs = [21.5, 18.5, 14.2, 10.8, 9.5, 7.8, 6.2, 4.5]
    names = ["阿根廷","巴西","法国","英格兰","西班牙","葡萄牙","荷兰","德国"]
    colors_grad = ["#ffd700", "#ffcc00", "#ffb300", BLUE, CYAN, GREEN, ORANGE, RED]

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    bars = ax.barh(range(len(teams)), probs, color=colors_grad, height=0.6,
                   edgecolor=WHITE, linewidth=0.5)

    for i, (bar, p) in enumerate(zip(bars, probs)):
        ax.text(bar.get_width() + 0.5, bar.get_y() + 0.3, f"{p:.1f}%",
                va="center", fontsize=13, fontweight="bold", color=WHITE)

    ax.set_yticks(range(len(teams)))
    ax.set_yticklabels([f"{n} ({t})" for t, n in zip(teams, names)],
                       fontsize=12, color=WHITE)
    ax.invert_yaxis()
    ax.set_xlim(0, max(probs) * 1.3)
    ax.tick_params(colors=GRAY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.xaxis.set_visible(False)

    ax.set_title("🏆  夺冠概率 Top-8", fontsize=18, color=GOLD,
                 fontweight="bold", pad=15)

    plt.tight_layout()
    path = OUTPUT_DIR / "champion_chart.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


def generate_bracket_tree():
    """生成赛程树示意图"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    fig.patch.set_facecolor(DARK_BG)

    def draw_node(x, y, text, color=BLUE, size=0.55):
        rect = mpatches.FancyBboxPatch(
            (x - size, y - 0.25), size * 2, 0.5,
            boxstyle="round,pad=0.04", facecolor=color,
            edgecolor=WHITE, linewidth=1.2, alpha=0.9,
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center", fontsize=9,
                fontweight="bold", color=WHITE)

    def draw_line(x1, y1, x2, y2):
        ax.plot([x1, x2], [y1, y2], color=GRAY, lw=1.5, alpha=0.6)

    # Final
    draw_node(6, 6.5, "🏆 冠军\n巴西 58%", color=GOLD, size=1.0)

    # Semi-finals
    draw_line(6, 6.25, 3.5, 5.0)
    draw_line(6, 6.25, 8.5, 5.0)
    draw_node(3.5, 5.0, "半决赛1\n巴西 vs 法国\n62% | 38%", color=BLUE)
    draw_node(8.5, 5.0, "半决赛2\n阿根廷 vs 英格兰\n55% | 45%", color=BLUE)

    # Quarters
    for qx, qy, teams_text in [
        (2, 3.5, "1/4-1 巴西 78%\n1/4-2 法国 70%"),
        (5, 3.5, "1/4-3 阿根廷 75%\n1/4-4 英格兰 68%"),
        (8, 3.5, "1/4-5 西班牙 65%\n1/4-6 葡萄牙 60%"),
        (11, 3.5, "1/4-7 荷兰 58%\n1/4-8 德国 52%"),
    ]:
        draw_line(3.5, 4.75, qx, 4.0)
        draw_line(8.5, 4.75, qx + 3, 4.0) if qx == 5 else None
        draw_node(qx, 3.5, teams_text, color="#1a3a5c", size=1.15)

    ax.set_title("🌳 淘汰赛对阵树 (悬停交互)", fontsize=18, color=GOLD,
                 fontweight="bold", pad=10)

    plt.tight_layout()
    path = OUTPUT_DIR / "bracket_tree.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


def generate_radar_chart():
    """生成球队雷达对比图"""
    categories = ["历史底蕴", "FIFA排名", "攻防效率", "球员班底", "近期状态"]
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(1, 1, figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    teams_data = [
        ("巴西", [48, 46, 40, 42, 38], BLUE),
        ("阿根廷", [44, 50, 42, 43, 47], GOLD),
        ("法国", [40, 44, 38, 41, 36], CYAN),
    ]

    for name, values, color in teams_data:
        vals = values + values[:1]
        ax.fill(angles, vals, alpha=0.15, color=color)
        ax.plot(angles, vals, "o-", linewidth=2, color=color, label=name, markersize=6)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11, color=WHITE)
    ax.set_ylim(0, 55)
    ax.set_yticks([10, 20, 30, 40, 50])
    ax.set_yticklabels(["10", "20", "30", "40", "50"], fontsize=8, color=GRAY)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=10,
              facecolor=DARK_BG, edgecolor=GRAY, labelcolor=WHITE)
    ax.grid(True, alpha=0.3, color=GRAY)
    ax.set_title("五维度球队评分对比", fontsize=16, color=GOLD,
                 fontweight="bold", pad=25)

    plt.tight_layout()
    path = OUTPUT_DIR / "radar_chart.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  ✓ {path}")


# ── 主执行 ──
if __name__ == "__main__":
    print("生成可视化素材...")
    generate_architecture_diagram()
    generate_data_flow_diagram()
    generate_prediction_flow()
    generate_champion_chart()
    generate_bracket_tree()
    generate_radar_chart()
    print(f"\n全部素材已保存到: {OUTPUT_DIR.resolve()}")
