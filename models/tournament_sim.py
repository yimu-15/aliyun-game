"""赛程推演 + 蒙特卡洛模拟 — 从小组赛到冠军的完整推演"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

import numpy as np

from config.settings import prediction
from models.team_rating import TeamRating
from models.match_predictor import predict_match, simulate_score


@dataclass
class ChampionshipResult:
    """冠军预测聚合结果"""
    team_id: str
    champion_prob: float
    confidence_95_low: float
    confidence_95_high: float
    final_prob: float = 0.0
    semi_prob: float = 0.0
    quarter_prob: float = 0.0
    round_16_prob: float = 0.0
    most_likely_path: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "champion_prob": round(self.champion_prob, 4),
            "confidence_95": [round(self.confidence_95_low, 4),
                            round(self.confidence_95_high, 4)],
            "final_prob": round(self.final_prob, 4),
            "semi_prob": round(self.semi_prob, 4),
            "quarter_prob": round(self.quarter_prob, 4),
            "round_16_prob": round(self.round_16_prob, 4),
            "most_likely_path": self.most_likely_path,
        }


def _simulate_group(teams: List[TeamRating], host_ids: List[str],
                    rng: np.random.RandomState) -> List[str]:
    """模拟一个小组赛 → 返回前 2 名出线队 ID"""
    standings: Dict[str, dict] = {
        t.team_id: {"pts": 0, "gf": 0, "ga": 0}
        for t in teams
    }

    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            h, a = teams[i], teams[j]
            pred = predict_match(h, a, h.team_id in host_ids)
            s_h, s_a = simulate_score(pred.expected_goals_home,
                                      pred.expected_goals_away, rng)
            # 更新主队
            standings[h.team_id]["gf"] += s_h
            standings[h.team_id]["ga"] += s_a
            if s_h > s_a:
                standings[h.team_id]["pts"] += 3
            elif s_h == s_a:
                standings[h.team_id]["pts"] += 1
            # 更新客队
            standings[a.team_id]["gf"] += s_a
            standings[a.team_id]["ga"] += s_h
            if s_a > s_h:
                standings[a.team_id]["pts"] += 3
            elif s_a == s_h:
                standings[a.team_id]["pts"] += 1

    # 排序: pts → gd → gf
    sorted_teams = sorted(
        standings.items(),
        key=lambda x: (x[1]["pts"],
                       x[1]["gf"] - x[1]["ga"],
                       x[1]["gf"]),
        reverse=True,
    )
    return [t[0] for t in sorted_teams[:2]]


def _simulate_knockout(team_a: TeamRating, team_b: TeamRating,
                       rng: np.random.RandomState) -> str:
    """模拟一场淘汰赛 → 返回胜者 ID (三阶段: 90分钟 → 加时 → 点球)"""
    pred = predict_match(team_a, team_b)

    # Stage 1: 90 分钟
    roll = rng.random()
    if roll < pred.prob_home_win:
        return team_a.team_id
    elif roll < pred.prob_home_win + pred.prob_away_win:
        return team_b.team_id

    # Stage 2: 加时赛
    la = pred.expected_goals_home * prediction.EXTRA_TIME_LAMBDA_FACTOR
    lb = pred.expected_goals_away * prediction.EXTRA_TIME_LAMBDA_FACTOR
    s_a, s_b = simulate_score(la, lb, rng)
    if s_a > s_b:
        return team_a.team_id
    elif s_b > s_a:
        return team_b.team_id

    # Stage 3: 点球
    p_win = prediction.PENALTY_STRONG_TEAM_RATE if team_a.overall >= team_b.overall \
            else 1 - prediction.PENALTY_STRONG_TEAM_RATE
    return team_a.team_id if rng.random() < p_win else team_b.team_id


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson 二项分布置信区间"""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z ** 2 / total
    center = (p + z ** 2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * total)) / total) / denom
    return max(0, center - margin), min(1, center + margin)


def run_monte_carlo(
    all_teams: Dict[str, TeamRating],
    groups: Dict[str, List[str]],
    bracket_order: List[List[Tuple[int, int]]],
    host_ids: List[str],
    n_sim: Optional[int] = None,
) -> List[ChampionshipResult]:
    """
    ★ 蒙特卡洛冠军预测 ★

    Args:
        all_teams: {team_id: TeamRating} 所有球队评分
        groups: {group_id: [team_id, team_id, team_id]} 分组
        bracket_order: 淘汰赛对阵顺序，如 [[(0,1), (2,3)], [(4,5), (6,7)], ...]
        host_ids: 东道主球队 ID 列表
        n_sim: 模拟次数 (默认从 config 读取)

    Returns:
        按夺冠概率降序排列的结果列表
    """
    n_sim = n_sim or prediction.MONTE_CARLO_SIMULATIONS
    rng_base = np.random.RandomState(prediction.RANDOM_SEED)

    champion_count: Dict[str, int] = defaultdict(int)
    round_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for sim_idx in range(n_sim):
        sim_rng = np.random.RandomState(prediction.RANDOM_SEED + sim_idx * 997)

        # ── 小组赛 ──
        qualifiers: List[str] = []
        for group_id, team_ids in groups.items():
            group_teams = [all_teams[tid] for tid in team_ids]
            qualified = _simulate_group(group_teams, host_ids, sim_rng)
            qualifiers.extend(qualified)

        # ── 淘汰赛 ──
        current = qualifiers[:]
        stage_names = ["round_32", "round_16", "quarter", "semi", "final"]
        stage_idx = 0

        for round_matches in bracket_order:
            stage_name = stage_names[stage_idx] if stage_idx < len(stage_names) else f"s{stage_idx}"
            for tid in current:
                round_counts[tid][stage_name] += 1

            winners = []
            for (idx_a, idx_b) in round_matches:
                if idx_a < len(current) and idx_b < len(current):
                    ta = all_teams[current[idx_a]]
                    tb = all_teams[current[idx_b]]
                    w = _simulate_knockout(ta, tb, sim_rng)
                    winners.append(w)
            current = winners
            stage_idx += 1

        # 记录冠军
        if current:
            champion_count[current[0]] += 1

    # ── 聚合 ──
    results = []
    for tid, rating in all_teams.items():
        count = champion_count.get(tid, 0)
        prob = count / n_sim
        ci_low, ci_high = _wilson_ci(count, n_sim)

        results.append(ChampionshipResult(
            team_id=tid,
            champion_prob=prob,
            confidence_95_low=ci_low,
            confidence_95_high=ci_high,
            final_prob=round_counts[tid].get("final", 0) / n_sim,
            semi_prob=round_counts[tid].get("semi", 0) / n_sim,
            quarter_prob=round_counts[tid].get("quarter", 0) / n_sim,
            round_16_prob=round_counts[tid].get("round_16", 0) / n_sim,
        ))

    results.sort(key=lambda r: r.champion_prob, reverse=True)
    return results
