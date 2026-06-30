"""
小组赛预测模块 — 基于独立泊松分布的胜平负概率计算

核心公式:
  λ_home = LEAGUE_AVG × attack_strength(A) × defense_strength(B)
  λ_away = LEAGUE_AVG × attack_strength(B) × defense_strength(A)

从 λ 推导: P(胜), P(平), P(负), 期望进球, 最可能比分
"""

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

LEAGUE_AVG_GOALS = 1.32
POISSON_K_MAX = 10       # 进球截断上限
HOME_ADVANTAGE = 1.15    # 东道主加成


@dataclass
class MatchPrediction:
    """单场预测结果"""
    home_id: str
    away_id: str
    p_home_win: float     # P(主胜)
    p_draw: float         # P(平)
    p_away_win: float     # P(客胜)
    lam_home: float       # 期望进球 (主)
    lam_away: float       # 期望进球 (客)
    best_score: str = ""  # 最可能比分 "2-1"


# =============================================================================
# 泊松工具
# =============================================================================

def _poisson_pmf(k: int, lam: float) -> float:
    """P(X=k) = λ^k * e^(-λ) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _win_draw_loss_probs(lam_h: float, lam_a: float) -> Tuple[float, float, float]:
    """从两个独立泊松分布计算 P(胜), P(平), P(负)"""
    p_h, p_d, p_a = 0.0, 0.0, 0.0
    for i in range(POISSON_K_MAX + 1):
        pi = _poisson_pmf(i, lam_h)
        for j in range(POISSON_K_MAX + 1):
            pj = _poisson_pmf(j, lam_a)
            prob = pi * pj
            if i > j:
                p_h += prob
            elif i == j:
                p_d += prob
            else:
                p_a += prob
    total = p_h + p_d + p_a
    return (p_h / total, p_d / total, p_a / total) if total > 0 else (0.33, 0.34, 0.33)


# =============================================================================
# 公共 API
# =============================================================================

def calc_lambda(team_atk: float, team_def: float,
                opp_atk: float, opp_def: float,
                is_home: bool, is_host: bool) -> float:
    """
    计算一支球队的期望进球 λ。

    Args:
        team_atk: 攻击力系数 [0.5, 1.5]
        team_def: 防守力系数 [0.5, 1.5]  (本函数不使用, 用于对称调用)
        opp_atk:  对手攻击力系数
        opp_def:  对手防守力系数
        is_home:  是否主场
        is_host:  是否东道主

    Returns:
        期望进球 λ
    """
    lam = LEAGUE_AVG_GOALS * team_atk * opp_def
    if is_home and is_host:
        lam *= HOME_ADVANTAGE
    return lam


def predict_match(team_a, team_b,
                  is_a_home: bool = True,
                  is_a_host: bool = False,
                  is_b_host: bool = False) -> MatchPrediction:
    """
    预测一场比赛的胜平负概率。

    Args:
        team_a: TeamRating 对象 (主队)
        team_b: TeamRating 对象 (客队)
        is_a_home: team_a 是否主场
        is_a_host: team_a 是否东道主
        is_b_host: team_b 是否东道主

    Returns:
        MatchPrediction

    Example:
        >>> from models.team_rating import rate_team
        >>> bra = rate_team({"team_id":"BRA","wc_titles":5,"fifa_rank":5,
        ...                  "elo_rating":2100,"goals_for_20":1.8,"goals_against_20":0.7,
        ...                  "win_rate_10":0.8})
        >>> arg = rate_team({"team_id":"ARG","wc_titles":3,"fifa_rank":1,
        ...                  "elo_rating":2135,"goals_for_20":1.6,"goals_against_20":0.5,
        ...                  "win_rate_10":0.9})
        >>> p = predict_match(bra, arg)
        >>> print(f"BRA vs ARG: {p.p_home_win:.1%} / {p.p_draw:.1%} / {p.p_away_win:.1%}")
    """
    # 期望进球
    lam_a = calc_lambda(
        team_a.attack_factor, team_a.defense_factor,
        team_b.attack_factor, team_b.defense_factor,
        is_home=is_a_home, is_host=is_a_host,
    )
    lam_b = calc_lambda(
        team_b.attack_factor, team_b.defense_factor,
        team_a.attack_factor, team_a.defense_factor,
        is_home=not is_a_home, is_host=is_b_host,
    )

    p_h, p_d, p_a = _win_draw_loss_probs(lam_a, lam_b)

    # 最可能比分
    best, best_prob = "0-0", 0.0
    for i in range(POISSON_K_MAX + 1):
        for j in range(POISSON_K_MAX + 1):
            prob = _poisson_pmf(i, lam_a) * _poisson_pmf(j, lam_b)
            if prob > best_prob:
                best_prob, best = prob, f"{i}-{j}"

    return MatchPrediction(
        home_id=team_a.team_id, away_id=team_b.team_id,
        p_home_win=round(p_h, 4), p_draw=round(p_d, 4), p_away_win=round(p_a, 4),
        lam_home=round(lam_a, 2), lam_away=round(lam_b, 2), best_score=best,
    )


def simulate_score(lam_a: float, lam_b: float, rng: np.random.RandomState) -> Tuple[int, int]:
    """从泊松分布采样比分"""
    return (min(rng.poisson(lam_a), POISSON_K_MAX),
            min(rng.poisson(lam_b), POISSON_K_MAX))


def simulate_group(teams: list, group_name: str,
                   host_ids: List[str],
                   rng: np.random.RandomState) -> dict:
    """
    模拟一个小组的完整赛程。

    Args:
        teams: TeamRating 列表 (2-4 支球队)
        group_name: 组名
        host_ids: 东道主 ID 列表
        rng: 随机数生成器

    Returns:
        {"group": 组名, "standings": [{team_id, pts, gf, ga, gd}], "qualified": [前2名ID]}
    """
    standings = {t.team_id: {"team_id": t.team_id, "pts": 0, "gf": 0, "ga": 0}
                 for t in teams}

    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            a, b = teams[i], teams[j]
            is_a_host = a.team_id in host_ids
            is_b_host = b.team_id in host_ids
            pred = predict_match(a, b, is_a_host=is_a_host, is_b_host=is_b_host)
            s_a, s_b = simulate_score(pred.lam_home, pred.lam_away, rng)

            # 更新 A
            standings[a.team_id]["gf"] += s_a
            standings[a.team_id]["ga"] += s_b
            if s_a > s_b:
                standings[a.team_id]["pts"] += 3
            elif s_a == s_b:
                standings[a.team_id]["pts"] += 1

            # 更新 B
            standings[b.team_id]["gf"] += s_b
            standings[b.team_id]["ga"] += s_a
            if s_b > s_a:
                standings[b.team_id]["pts"] += 3
            elif s_b == s_a:
                standings[b.team_id]["pts"] += 1

    # 计算净胜球并排序
    for s in standings.values():
        s["gd"] = s["gf"] - s["ga"]

    sorted_teams = sorted(standings.values(),
                          key=lambda x: (x["pts"], x["gd"], x["gf"]),
                          reverse=True)
    for rank, s in enumerate(sorted_teams, 1):
        s["rank"] = rank

    return {
        "group": group_name,
        "standings": sorted_teams,
        "qualified": [s["team_id"] for s in sorted_teams[:2]],
    }


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("小组赛预测模块测试")
    print("=" * 50)

    from models.team_rating import rate_team

    # 构建测试球队
    snaps = [
        {"team_id": "BRA", "team_name": "巴西", "wc_titles": 5, "fifa_rank": 5,
         "elo_rating": 2100, "goals_for_20": 1.8, "goals_against_20": 0.7, "win_rate_10": 0.8},
        {"team_id": "ARG", "team_name": "阿根廷", "wc_titles": 3, "fifa_rank": 1,
         "elo_rating": 2135, "goals_for_20": 1.6, "goals_against_20": 0.5, "win_rate_10": 0.9},
        {"team_id": "SUI", "team_name": "瑞士", "wc_titles": 0, "fifa_rank": 22,
         "elo_rating": 1720, "goals_for_20": 1.1, "goals_against_20": 1.0, "win_rate_10": 0.5},
        {"team_id": "CMR", "team_name": "喀麦隆", "wc_titles": 0, "fifa_rank": 36,
         "elo_rating": 1440, "goals_for_20": 0.8, "goals_against_20": 1.4, "win_rate_10": 0.3},
    ]
    teams = [rate_team(s) for s in snaps]

    # 单场预测
    p = predict_match(teams[0], teams[1])
    print(f"\n[1] BRA vs ARG 单场预测:")
    print(f"  P(胜)={p.p_home_win:.1%}  P(平)={p.p_draw:.1%}  P(负)={p.p_away_win:.1%}")
    print(f"  xG: {p.lam_home} - {p.lam_away}  |  最可能比分: {p.best_score}")

    # 小组模拟
    rng = np.random.RandomState(42)
    result = simulate_group(teams, "A组", [], rng)
    print(f"\n[2] A组 模拟结果:")
    for s in result["standings"]:
        print(f"  {s['team_id']}: {s['pts']}pts  GF{s['gf']} GA{s['ga']} GD{s['gd']}  #{s['rank']}")
    print(f"  出线: {result['qualified']}")
