"""
淘汰赛晋级模拟模块 — 三阶段制胜模型

每场淘汰赛必须分出胜负:
  Stage 1 - 90分钟常规时间: 泊松模型预测 P(胜)/P(平)/P(负)
  Stage 2 - 30分钟加时赛:    λ × 0.33, 重新采样
  Stage 3 - 点球大战:        强队 55% 胜率

P(晋级) = P(90分钟胜) + P(90分钟平) × [P(加时胜) + P(加时平) × P(点球胜)]
"""

from typing import List

import numpy as np

from models.group_stage import predict_match, simulate_score

EXTRA_TIME_FACTOR = 0.33    # 加时赛进球率 (30min / 90min)
PENALTY_FAVORITE_RATE = 0.55  # 评分更高的队在点球中的胜率


def simulate_knockout_match(team_a, team_b,
                             is_a_host: bool = False,
                             is_b_host: bool = False,
                             rng: np.random.RandomState = None) -> str:
    """
    模拟一场淘汰赛, 返回胜者 team_id。

    三阶段制胜:
      1. 90分钟 → 如果分出胜负直接返回
      2. 加时赛 → λ × 0.33 重新采样
      3. 点球 → 强队 55% 胜率

    Args:
        team_a, team_b: TeamRating 对象
        is_a_host, is_b_host: 是否东道主
        rng: 随机数生成器

    Returns:
        胜者 team_id

    Example:
        >>> from models.team_rating import rate_team
        >>> bra = rate_team({"team_id":"BRA","wc_titles":5,"fifa_rank":5,
        ...                  "elo_rating":2100,"goals_for_20":1.8,"goals_against_20":0.7,"win_rate_10":0.8})
        >>> arg = rate_team({"team_id":"ARG","wc_titles":3,"fifa_rank":1,
        ...                  "elo_rating":2135,"goals_for_20":1.6,"goals_against_20":0.5,"win_rate_10":0.9})
        >>> rng = np.random.RandomState(42)
        >>> winner = simulate_knockout_match(bra, arg, rng=rng)
        >>> print(f"Winner: {winner}")
    """
    if rng is None:
        rng = np.random.RandomState()

    pred = predict_match(team_a, team_b, is_a_host=is_a_host, is_b_host=is_b_host)

    # Stage 1: 90分钟
    roll = rng.random()
    if roll < pred.p_home_win:
        return team_a.team_id
    elif roll < pred.p_home_win + pred.p_away_win:
        return team_b.team_id

    # Stage 2: 加时赛 (进球率降低)
    la = pred.lam_home * EXTRA_TIME_FACTOR
    lb = pred.lam_away * EXTRA_TIME_FACTOR
    s_a, s_b = simulate_score(la, lb, rng)
    if s_a > s_b:
        return team_a.team_id
    elif s_b > s_a:
        return team_b.team_id

    # Stage 3: 点球大战
    if team_a.overall >= team_b.overall:
        return team_a.team_id if rng.random() < PENALTY_FAVORITE_RATE else team_b.team_id
    else:
        return team_b.team_id if rng.random() < PENALTY_FAVORITE_RATE else team_a.team_id


def calc_advance_probability(team_a, team_b,
                              is_a_host: bool = False,
                              is_b_host: bool = False) -> float:
    """
    计算 team_a 淘汰 team_b 的晋级概率 (非采样, 精确概率)。

    公式:
      P(晋级) = P(90min胜) + P(90min平) × [P(加时胜) + P(加时平) × P(点球胜)]

    Args:
        team_a, team_b: TeamRating 对象

    Returns:
        team_a 的晋级概率 [0, 1]
    """
    from models.group_stage import _win_draw_loss_probs

    pred = predict_match(team_a, team_b, is_a_host=is_a_host, is_b_host=is_b_host)

    # 加时赛概率
    la_et = pred.lam_home * EXTRA_TIME_FACTOR
    lb_et = pred.lam_away * EXTRA_TIME_FACTOR
    p_et_win, p_et_draw, _ = _win_draw_loss_probs(la_et, lb_et)

    # 点球胜率
    p_pen = PENALTY_FAVORITE_RATE if team_a.overall >= team_b.overall else (1 - PENALTY_FAVORITE_RATE)

    advance = pred.p_home_win + pred.p_draw * (p_et_win + p_et_draw * p_pen)
    return advance


def simulate_knockout_round(matches: List[tuple],
                             host_ids: List[str],
                             rng: np.random.RandomState) -> List[str]:
    """
    模拟一轮淘汰赛的所有比赛。

    Args:
        matches: [(team_a, team_b), ...] 本轮对阵
        host_ids: 东道主 ID 列表
        rng: 随机数生成器

    Returns:
        晋级到下一轮的球队 ID 列表
    """
    winners = []
    for team_a, team_b in matches:
        is_a_host = team_a.team_id in host_ids
        is_b_host = team_b.team_id in host_ids
        winner = simulate_knockout_match(team_a, team_b, is_a_host, is_b_host, rng)
        winners.append(winner)
    return winners


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("淘汰赛模拟模块测试")
    print("=" * 50)

    from models.team_rating import rate_team

    bra = rate_team({"team_id": "BRA", "team_name": "巴西", "wc_titles": 5, "fifa_rank": 5,
                     "elo_rating": 2100, "goals_for_20": 1.8, "goals_against_20": 0.7, "win_rate_10": 0.8})
    arg = rate_team({"team_id": "ARG", "team_name": "阿根廷", "wc_titles": 3, "fifa_rank": 1,
                     "elo_rating": 2135, "goals_for_20": 1.6, "goals_against_20": 0.5, "win_rate_10": 0.9})

    # 精确晋级概率
    p_bra = calc_advance_probability(bra, arg)
    print(f"\n[1] BRA vs ARG 淘汰赛:")
    print(f"  BRA 晋级概率: {p_bra:.1%}")
    print(f"  ARG 晋级概率: {1-p_bra:.1%}")

    # 模拟 1000 次
    rng = np.random.RandomState(42)
    bra_wins = sum(
        simulate_knockout_match(bra, arg, rng=np.random.RandomState(42 + i)) == "BRA"
        for i in range(1000)
    )
    print(f"\n[2] 1000 次模拟:")
    print(f"  BRA 胜: {bra_wins} ({bra_wins/10:.1f}%)")
    print(f"  ARG 胜: {1000 - bra_wins} ({(1000 - bra_wins)/10:.1f}%)")
