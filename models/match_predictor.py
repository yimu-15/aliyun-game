"""泊松单场预测器 — 基于独立泊松分布的胜/平/负概率预测"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

import numpy as np

from config.settings import prediction
from models.team_rating import TeamRating


@dataclass
class MatchPrediction:
    """单场预测结果"""
    home_team_id: str
    away_team_id: str
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    expected_goals_home: float
    expected_goals_away: float
    most_likely_score: str = "0-0"
    score_distribution: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "prob_home_win": round(self.prob_home_win, 4),
            "prob_draw": round(self.prob_draw, 4),
            "prob_away_win": round(self.prob_away_win, 4),
            "expected_goals_home": round(self.expected_goals_home, 2),
            "expected_goals_away": round(self.expected_goals_away, 2),
            "most_likely_score": self.most_likely_score,
        }


def _poisson_pmf(k: int, lam: float) -> float:
    """泊松概率质量函数 P(X=k) = λ^k * e^(-λ) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _compute_win_draw_loss(lam_home: float, lam_away: float) -> Tuple[float, float, float]:
    """从两个独立泊松分布计算胜/平/负概率"""
    k_max = prediction.POISSON_K_MAX
    p_home, p_draw, p_away = 0.0, 0.0, 0.0

    for i in range(k_max + 1):
        p_i = _poisson_pmf(i, lam_home)
        for j in range(k_max + 1):
            p_j = _poisson_pmf(j, lam_away)
            p = p_i * p_j
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p

    total = p_home + p_draw + p_away
    if total > 0:
        p_home /= total
        p_draw /= total
        p_away /= total

    return p_home, p_draw, p_away


def _calc_lambda(team: TeamRating, opponent: TeamRating,
                 is_home: bool, is_host: bool) -> float:
    """计算期望进球 λ"""
    attack = 0.5 + team.attack_score / 50.0
    defense_opp = 1.5 - opponent.defense_score / 50.0

    lam = prediction.LEAGUE_AVG_GOALS * attack * defense_opp

    if is_host and is_home:
        lam *= prediction.HOME_ADVANTAGE

    return lam


def predict_match(home: TeamRating, away: TeamRating,
                  is_home_host: bool = False,
                  away_is_host: bool = False) -> MatchPrediction:
    """
    ★ 预测单场比赛 ★

    Args:
        home: 主队评分
        away: 客队评分
        is_home_host: 主队是东道主
        away_is_host: 客队是东道主

    Returns:
        MatchPrediction 包含胜/平/负概率和期望进球
    """
    lam_h = _calc_lambda(home, away, True, is_home_host)
    lam_a = _calc_lambda(away, home, False, away_is_host)

    p_h, p_d, p_a = _compute_win_draw_loss(lam_h, lam_a)

    # 最可能比分
    best_score = "0-0"
    best_p = 0.0
    for i in range(prediction.POISSON_K_MAX + 1):
        for j in range(prediction.POISSON_K_MAX + 1):
            prob = _poisson_pmf(i, lam_h) * _poisson_pmf(j, lam_a)
            if prob > best_p:
                best_p = prob
                best_score = f"{i}-{j}"

    return MatchPrediction(
        home_team_id=home.team_id,
        away_team_id=away.team_id,
        prob_home_win=round(p_h, 4),
        prob_draw=round(p_d, 4),
        prob_away_win=round(p_a, 4),
        expected_goals_home=round(lam_h, 2),
        expected_goals_away=round(lam_a, 2),
        most_likely_score=best_score,
    )


def simulate_score(lam_home: float, lam_away: float,
                   rng: np.random.RandomState) -> Tuple[int, int]:
    """从泊松分布采样一场比赛的比分"""
    s_h = min(rng.poisson(lam_home), prediction.POISSON_K_MAX)
    s_a = min(rng.poisson(lam_away), prediction.POISSON_K_MAX)
    return s_h, s_a
