"""
冠军预测模块 — 蒙特卡洛模拟

流程:
  1. 小组赛: 每组模拟 → 前2名出线
  2. 淘汰赛: 逐轮模拟 → 胜者晋级
  3. 重复 N 次 → 统计夺冠次数 → 概率

输出: 夺冠概率排行榜 + 95% 置信区间 + 晋级各轮概率
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from models.group_stage import simulate_group, predict_match
from models.knockout import simulate_knockout_match


@dataclass
class ChampionResult:
    """一支球队的冠军预测聚合结果"""
    team_id: str
    team_name: str = ""
    champion_prob: float = 0.0       # 夺冠概率
    ci_low: float = 0.0              # 95% CI 下界
    ci_high: float = 0.0             # 95% CI 上界
    final_prob: float = 0.0          # 进决赛概率
    semi_prob: float = 0.0           # 进半决赛概率
    quarter_prob: float = 0.0        # 进8强概率
    round_16_prob: float = 0.0       # 进16强概率
    overall_rating: float = 0.0      # 综合评分

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "champion_prob": round(self.champion_prob, 4),
            "ci_95": [round(self.ci_low, 4), round(self.ci_high, 4)],
            "final_prob": round(self.final_prob, 4),
            "semi_prob": round(self.semi_prob, 4),
            "quarter_prob": round(self.quarter_prob, 4),
            "round_16_prob": round(self.round_16_prob, 4),
            "overall_rating": round(self.overall_rating, 1),
        }


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple:
    """Wilson 二项分布置信区间"""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z ** 2 / total
    center = (p + z ** 2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * total)) / total) / denom
    return max(0, center - margin), min(1, center + margin)


def run_monte_carlo(
    teams: list,                     # List[TeamRating]
    groups: Dict[str, List[str]],    # {组名: [team_id, ...]}
    bracket_order: List[List[tuple]], # 淘汰赛对阵模板
    host_ids: List[str],
    n_sim: int = 10000,
    seed: int = 42,
) -> List[ChampionResult]:
    """
    蒙特卡洛冠军预测。

    Args:
        teams: TeamRating 列表
        groups: 分组 {组名: [team_id, ...]}
        bracket_order: 淘汰赛每轮的对阵索引
            例如: [[(0,1),(2,3)], [(0,1)]] 表示第一轮用队伍0vs1,2vs3; 下一轮胜者对阵
        host_ids: 东道主 team_id 列表
        n_sim: 模拟次数
        seed: 随机种子

    Returns:
        按夺冠概率降序排列的 ChampionResult 列表

    Example:
        >>> from models.team_rating import rate_team
        >>> teams = [rate_team({"team_id": t, ...}) for t in ["BRA","ARG","FRA","ENG"]]
        >>> groups = {"A": ["BRA","ARG"], "B": ["FRA","ENG"]}
        >>> bracket = [[(0,1), (2,3)], [(0,1)]]
        >>> results = run_monte_carlo(teams, groups, bracket, [], n_sim=1000)
        >>> for r in results:
        ...     print(f"{r.team_id}: {r.champion_prob:.1%}")
    """
    team_map = {t.team_id: t for t in teams}
    team_names = {t.team_id: t.team_name for t in teams}

    # 计数器
    champion_count = defaultdict(int)
    round_counts = defaultdict(lambda: defaultdict(int))

    for sim_idx in range(n_sim):
        sim_rng = np.random.RandomState(seed + sim_idx * 997)

        # ── 小组赛 ──
        qualified = []
        for group_name, team_ids in groups.items():
            group_teams = [team_map[tid] for tid in team_ids if tid in team_map]
            if len(group_teams) < 2:
                continue
            result = simulate_group(group_teams, group_name, host_ids, sim_rng)
            qualified.extend(result["qualified"])

        if not qualified:
            continue

        for tid in qualified:
            round_counts[tid]["group"] += 1

        # ── 淘汰赛 ──
        current = qualified[:]
        stage_names = ["round_32", "round_16", "quarter", "semi", "final"]
        stage_idx = 0

        for round_matches in bracket_order:
            stage_name = stage_names[stage_idx] if stage_idx < len(stage_names) else f"stage_{stage_idx}"
            for tid in current:
                round_counts[tid][stage_name] += 1

            winners = []
            for (idx_a, idx_b) in round_matches:
                if idx_a < len(current) and idx_b < len(current):
                    ta = team_map.get(current[idx_a])
                    tb = team_map.get(current[idx_b])
                    if ta and tb:
                        is_a_host = ta.team_id in host_ids
                        is_b_host = tb.team_id in host_ids
                        w = simulate_knockout_match(ta, tb, is_a_host, is_b_host, sim_rng)
                        winners.append(w)
            current = winners
            stage_idx += 1

        # 记录冠军
        if current:
            champion_count[current[0]] += 1

    # ── 聚合结果 ──
    results = []
    for t in teams:
        count = champion_count.get(t.team_id, 0)
        prob = count / n_sim
        ci_low, ci_high = _wilson_ci(count, n_sim)

        results.append(ChampionResult(
            team_id=t.team_id,
            team_name=team_names.get(t.team_id, t.team_id),
            champion_prob=prob,
            ci_low=ci_low,
            ci_high=ci_high,
            final_prob=round_counts[t.team_id].get("final", 0) / n_sim,
            semi_prob=round_counts[t.team_id].get("semi", 0) / n_sim,
            quarter_prob=round_counts[t.team_id].get("quarter", 0) / n_sim,
            round_16_prob=round_counts[t.team_id].get("round_16", 0) / n_sim,
            overall_rating=t.overall,
        ))

    results.sort(key=lambda r: r.champion_prob, reverse=True)
    return results


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("冠军预测模块测试")
    print("=" * 50)

    from models.team_rating import rate_team

    # 构建 8 支球队
    snapshots = [
        {"team_id":"ARG","team_name":"阿根廷","wc_titles":3,"fifa_rank":1,
         "elo_rating":2135,"goals_for_20":1.6,"goals_against_20":0.5,"win_rate_10":0.9},
        {"team_id":"BRA","team_name":"巴西","wc_titles":5,"fifa_rank":5,
         "elo_rating":2100,"goals_for_20":1.8,"goals_against_20":0.7,"win_rate_10":0.8},
        {"team_id":"FRA","team_name":"法国","wc_titles":2,"fifa_rank":2,
         "elo_rating":2080,"goals_for_20":1.7,"goals_against_20":0.8,"win_rate_10":0.75},
        {"team_id":"ENG","team_name":"英格兰","wc_titles":1,"fifa_rank":4,
         "elo_rating":2020,"goals_for_20":1.5,"goals_against_20":0.6,"win_rate_10":0.7},
        {"team_id":"ESP","team_name":"西班牙","wc_titles":1,"fifa_rank":8,
         "elo_rating":2000,"goals_for_20":1.7,"goals_against_20":0.6,"win_rate_10":0.85},
        {"team_id":"GER","team_name":"德国","wc_titles":4,"fifa_rank":16,
         "elo_rating":1960,"goals_for_20":1.6,"goals_against_20":0.9,"win_rate_10":0.6},
        {"team_id":"POR","team_name":"葡萄牙","wc_titles":0,"fifa_rank":6,
         "elo_rating":1980,"goals_for_20":1.8,"goals_against_20":0.7,"win_rate_10":0.8},
        {"team_id":"NED","team_name":"荷兰","wc_titles":0,"fifa_rank":7,
         "elo_rating":1970,"goals_for_20":1.5,"goals_against_20":0.8,"win_rate_10":0.65},
    ]
    teams = [rate_team(s) for s in snapshots]

    # 8队分组 + 淘汰赛对阵
    groups = {
        "A": ["ARG", "GER", "NED"],
        "B": ["BRA", "ESP", "POR"],
        "C": ["FRA", "ENG", "NED"],  # NED 在两个组中会出现 (简化为测试)
    }
    bracket = [[(0, 1), (2, 3), (4, 5)], [(0, 1)], [(0, 1)]]

    results = run_monte_carlo(teams, groups, bracket, [], n_sim=2000, seed=42)

    print(f"\n{'排名':<4} {'球队':<10} {'夺冠概率':<10} {'95% CI':<16} {'评分':<6}")
    print("-" * 50)
    for i, r in enumerate(results, 1):
        print(f"{i:<4} {r.team_name:<10} {r.champion_prob:<10.1%} "
              f"[{r.ci_low:.1%}, {r.ci_high:.1%}]  {r.overall_rating:<6.1f}")
