"""
世界杯冠军预测 Agent — 主入口

端到端流水线:
  1. 加载数据
  2. 构建球队评分
  3. 蒙特卡洛冠军预测
  4. 结构化输出

用法:
    python main.py                  # 默认 8 队演示
    python main.py --teams 16       # 16 队
    python main.py --teams 32       # 32 队 (完整模拟)
    python main.py --sim 5000       # 自定义模拟次数
    python main.py --output json    # 输出 JSON 文件
"""

import argparse
import json
import sys
from pathlib import Path

# 确保根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve()))

from utils.data_loader import load_teams, load_matches, build_team_snapshots
from models.team_rating import rate_all_teams
from models.champion import run_monte_carlo
from models.output import (
    format_champion_rankings,
    format_bracket_tree,
    format_match_detail,
    print_champion_table,
    save_json,
)


def build_groups_and_bracket(team_ids: list) -> tuple:
    """
    根据球队数量自动构建分组和淘汰赛对阵。

    支持: 4, 8, 16, 32 队
    """
    n = len(team_ids)

    if n == 4:
        groups = {"A": team_ids[:2], "B": team_ids[2:4]}
        bracket = [[(0, 1), (2, 3)], [(0, 1)]]
    elif n == 8:
        groups = {
            "A": team_ids[0:4],
            "B": team_ids[4:8],
        }
        # 每组前2出线 = 4队 → 半决赛(2场) → 决赛
        bracket = [[(0, 1), (2, 3)], [(0, 1)]]
    elif n == 16:
        # 4 组 × 4 队, 每组前2出线 = 8 队
        groups = {chr(65 + i): team_ids[i * 4:(i + 1) * 4] for i in range(4)}
        bracket = [
            [(0, 1), (2, 3), (4, 5), (6, 7)],
            [(0, 1), (2, 3)],
            [(0, 1)],
        ]
    elif n >= 32:
        # 8 组 × 4 队, 每组前2出线 = 16 队
        groups = {chr(65 + i): team_ids[i * 4:(i + 1) * 4] for i in range(8)}
        bracket = [
            [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11), (12, 13), (14, 15)],
            [(0, 1), (2, 3), (4, 5), (6, 7)],
            [(0, 1), (2, 3)],
            [(0, 1)],
        ]
        team_ids = team_ids[:32]
    else:
        raise ValueError(f"不支持的球队数量: {n}, 请使用 4/8/16/32")

    return groups, bracket, team_ids


def main():
    parser = argparse.ArgumentParser(description="世界杯冠军预测 Agent")
    parser.add_argument("--teams", type=int, default=8,
                        choices=[4, 8, 16, 32], help="模拟球队数量")
    parser.add_argument("--sim", type=int, default=10000,
                        help="蒙特卡洛模拟次数")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSON 文件路径")
    parser.add_argument("--real-data", action="store_true",
                        help="尝试使用真实下载数据")
    args = parser.parse_args()

    print("=" * 60)
    print("  世界杯冠军预测 Agent")
    print(f"  球队: {args.teams}  |  模拟: {args.sim} 次  |  种子: {args.seed}")
    print("=" * 60)

    # ── Step 1: 加载数据 ──
    print("\n[1/4] 加载数据...")
    teams_df = load_teams(use_real_data=args.real_data)
    matches_df = load_matches(use_real_data=args.real_data)
    snapshots = build_team_snapshots(teams_df, matches_df)

    # 选择前 N 支球队
    snapshots = snapshots[:args.teams]
    print(f"  已加载 {len(snapshots)} 支球队")

    # ── Step 2: 球队评分 ──
    print("\n[2/4] 计算球队评分...")
    team_ratings = rate_all_teams(snapshots)
    team_map = {t.team_id: t for t in team_ratings}

    for t in sorted(team_ratings, key=lambda x: x.overall, reverse=True)[:5]:
        print(f"  {t.team_name or t.team_id}: {t.overall:.1f} 分")

    # ── Step 3: 冠军预测 ──
    print(f"\n[3/4] 蒙特卡洛模拟 ({args.sim} 次)...")
    team_ids = [t.team_id for t in team_ratings]
    groups, bracket, team_ids = build_groups_and_bracket(team_ids)
    host_ids = ["CAN", "MEX", "USA"]  # 2026 东道主

    results = run_monte_carlo(
        team_ratings, groups, bracket, host_ids,
        n_sim=args.sim, seed=args.seed,
    )

    # ── Step 4: 输出 ──
    print("\n[4/4] 结果:")

    # 终端输出
    print_champion_table(results, top_n=10)

    # JSON 输出
    output_data = format_champion_rankings(results)
    output_data["bracket"] = format_bracket_tree(team_map, results)

    # Top-2 单场详情
    if len(results) >= 2:
        a = team_map.get(results[0].team_id)
        b = team_map.get(results[1].team_id)
        if a and b:
            output_data["top_match_preview"] = format_match_detail(a, b)

    if args.output:
        save_json(output_data, args.output)
    else:
        # 默认保存
        save_json(output_data, "data/processed/champion_prediction.json")

    print("\n" + "=" * 60)
    print("  预测完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
