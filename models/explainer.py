"""因子归因可解释性引擎 — 单项特征消融法"""

from dataclasses import dataclass
from typing import List

from models.team_rating import TeamRating
from models.match_predictor import predict_match


@dataclass
class FactorExplanation:
    """单个因子的解释"""
    factor_id: str
    display_name: str
    value_team_a: float
    value_team_b: float
    impact: float
    direction: str              # "team_a_advantage" / "team_b_advantage"

    def to_dict(self) -> dict:
        return {
            "factor": self.display_name,
            "team_a_value": round(self.value_team_a, 1),
            "team_b_value": round(self.value_team_b, 1),
            "impact": round(self.impact, 4),
            "direction": self.direction,
        }


_FACTOR_NAMES = {
    "historical":      "历史底蕴",
    "strength":        "FIFA 排名",
    "attack_defense":  "攻防效率",
    "player_quality":  "球员班底",
    "recent_form":     "近期状态",
    "home_advantage":  "东道主优势",
}

# 中立值 (50 分制的中值)
_NEUTRAL = {k: 25.0 for k in _FACTOR_NAMES if k != "home_advantage"}


def _get_factor_value(rating: TeamRating, factor_id: str) -> float:
    return getattr(rating, factor_id, 25.0)


def _make_neutral_rating(rating: TeamRating, factor_id: str) -> TeamRating:
    """将某个评分维度置为中立值"""
    neutral_val = _NEUTRAL.get(factor_id, 25.0)
    return TeamRating(
        team_id=rating.team_id,
        overall=rating.overall,
        historical=neutral_val if factor_id == "historical" else rating.historical,
        strength=neutral_val if factor_id == "strength" else rating.strength,
        attack_defense=neutral_val if factor_id == "attack_defense" else rating.attack_defense,
        player_quality=neutral_val if factor_id == "player_quality" else rating.player_quality,
        recent_form=neutral_val if factor_id == "recent_form" else rating.recent_form,
    )


def explain_match(
    team_a: TeamRating,
    team_b: TeamRating,
    is_a_host: bool = False,
) -> dict:
    """
    ★ 比赛预测可解释性分析 ★

    方法: 单项特征消融 (Single Feature Ablation)
      1. 计算基准预测
      2. 逐因子置为中立项重新预测
      3. 计算概率变化 → 贡献度

    Args:
        team_a, team_b: 两队评分
        is_a_host: team_a 是否为东道主

    Returns:
        包含预测结果和 Top-5 解释因子的字典
    """
    base = predict_match(team_a, team_b, is_a_host)
    base_p = base.prob_home_win

    factors: List[FactorExplanation] = []

    # 逐因子消融
    for factor_id in ["historical", "strength", "attack_defense",
                       "player_quality", "recent_form"]:
        a_n = _make_neutral_rating(team_a, factor_id)
        b_n = _make_neutral_rating(team_b, factor_id)
        ablated = predict_match(a_n, b_n, is_a_host)
        impact = abs(base_p - ablated.prob_home_win)

        direction = "team_a_advantage" if base_p > ablated.prob_home_win \
                    else "team_b_advantage"

        factors.append(FactorExplanation(
            factor_id=factor_id,
            display_name=_FACTOR_NAMES[factor_id],
            value_team_a=_get_factor_value(team_a, factor_id),
            value_team_b=_get_factor_value(team_b, factor_id),
            impact=impact,
            direction=direction,
        ))

    # 东道主优势 (单独处理)
    if is_a_host:
        no_host = predict_match(team_a, team_b, False)
        impact = abs(base_p - no_host.prob_home_win)
        factors.insert(0, FactorExplanation(
            factor_id="home_advantage",
            display_name="东道主优势",
            value_team_a=1.0,
            value_team_b=0.0,
            impact=impact,
            direction="team_a_advantage",
        ))

    factors.sort(key=lambda f: f.impact, reverse=True)

    return {
        "match": f"{team_a.team_id} vs {team_b.team_id}",
        "prediction": {
            f"{team_a.team_id}_win": base.prob_home_win,
            "draw": base.prob_draw,
            f"{team_b.team_id}_win": base.prob_away_win,
        },
        "expected_goals": {
            team_a.team_id: base.expected_goals_home,
            team_b.team_id: base.expected_goals_away,
        },
        "top_factors": [f.to_dict() for f in factors[:5]],
    }
