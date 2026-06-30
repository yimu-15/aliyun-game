"""
结果结构化输出模块 — 将预测结果格式化为前端可用的 JSON 结构

输出三级:
  Level 1: 冠军排行 — 夺冠概率排行榜
  Level 2: 赛程树   — 淘汰赛对阵 + 晋级概率
  Level 3: 单场详情 — 胜负因子归因
"""

import json
from datetime import datetime
from typing import List, Dict

from models.champion import ChampionResult
from models.group_stage import predict_match
from models.knockout import calc_advance_probability


def format_champion_rankings(results: List[ChampionResult],
                              model_version: str = "1.0.0-mvp") -> dict:
    """
    格式化夺冠排行榜 (Level 1 输出)。

    Returns:
        {
            "model_version": ...,
            "generated_at": ...,
            "num_simulations": ...,
            "rankings": [{team_id, team_name, champion_prob, ci_95, ratings}, ...]
        }
    """
    return {
        "model_version": model_version,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_teams": len(results),
        "rankings": [
            {
                "rank": i + 1,
                "team_id": r.team_id,
                "team_name": r.team_name,
                "champion_prob": round(r.champion_prob, 4),
                "champion_prob_pct": f"{r.champion_prob * 100:.2f}%",
                "ci_95": [round(r.ci_low, 4), round(r.ci_high, 4)],
                "advancement": {
                    "final": round(r.final_prob, 4),
                    "semi": round(r.semi_prob, 4),
                    "quarter": round(r.quarter_prob, 4),
                    "round_16": round(r.round_16_prob, 4),
                },
                "overall_rating": round(r.overall_rating, 1),
            }
            for i, r in enumerate(results)
        ],
    }


def format_bracket_tree(teams_map: dict, rankings: List[ChampionResult]) -> dict:
    """
    格式化赛程树 (Level 2 输出)。

    构建一个简化的淘汰赛对阵树,
    每个节点包含: 对阵双方、晋级概率、阶段。

    Args:
        teams_map: {team_id: TeamRating}
        rankings: 冠军排行列表

    Returns:
        赛程树 dict
    """
    if len(rankings) < 8:
        return {"error": "需要至少 8 支球队"}

    top8 = rankings[:8]
    top4 = rankings[:4]
    top2 = rankings[:2]

    def make_match(a: ChampionResult, b: ChampionResult, stage: str) -> dict:
        ta = teams_map.get(a.team_id)
        tb = teams_map.get(b.team_id)
        if ta and tb:
            prob_a = calc_advance_probability(ta, tb)
        else:
            prob_a = 0.5
        return {
            "stage": stage,
            "team_a": {"id": a.team_id, "name": a.team_name, "advance_prob": round(prob_a, 3)},
            "team_b": {"id": b.team_id, "name": b.team_name, "advance_prob": round(1 - prob_a, 3)},
        }

    return {
        "final": make_match(top2[0], top2[1], "final"),
        "semi_finals": [
            make_match(top4[0], top4[1], "semi"),
            make_match(top4[2], top4[3], "semi"),
        ],
        "quarter_finals": [
            make_match(top8[0], top8[1], "quarter"),
            make_match(top8[2], top8[3], "quarter"),
            make_match(top8[4], top8[5], "quarter"),
            make_match(top8[6], top8[7], "quarter"),
        ],
    }


def format_match_detail(team_a, team_b,
                         is_a_host: bool = False) -> dict:
    """
    格式化单场预测详情 (Level 3 输出)。

    包含: 胜平负概率、期望进球、最可能比分

    Args:
        team_a, team_b: TeamRating 对象
        is_a_host: team_a 是否东道主

    Returns:
        单场详情 dict
    """
    from models.group_stage import predict_match as pm

    pred = pm(team_a, team_b, is_a_host=is_a_host)

    # 攻防因子比较
    factors = {
        "fifa_rank": {
            "name": "FIFA排名",
            "value_a": team_a.strength,
            "value_b": team_b.strength,
            "advantage": "team_a" if team_a.strength > team_b.strength else "team_b",
        },
        "attack_defense": {
            "name": "攻防效率",
            "value_a": team_a.attack_defense,
            "value_b": team_b.attack_defense,
            "advantage": "team_a" if team_a.attack_defense > team_b.attack_defense else "team_b",
        },
        "recent_form": {
            "name": "近期状态",
            "value_a": team_a.recent_form,
            "value_b": team_b.recent_form,
            "advantage": "team_a" if team_a.recent_form > team_b.recent_form else "team_b",
        },
        "historical": {
            "name": "历史底蕴",
            "value_a": team_a.historical,
            "value_b": team_b.historical,
            "advantage": "team_a" if team_a.historical > team_b.historical else "team_b",
        },
    }

    return {
        "match": f"{team_a.team_id} vs {team_b.team_id}",
        "prediction": {
            f"{team_a.team_id}_win": pred.p_home_win,
            "draw": pred.p_draw,
            f"{team_b.team_id}_win": pred.p_away_win,
        },
        "expected_goals": {
            team_a.team_id: pred.lam_home,
            team_b.team_id: pred.lam_away,
        },
        "best_score": pred.best_score,
        "factors": factors,
    }


def save_json(data: dict, filepath: str):
    """保存结果为 JSON 文件"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {filepath}")


def print_champion_table(results: List[ChampionResult], top_n: int = 10):
    """终端友好的排行榜输出"""
    print(f"\n{'#' :<4} {'球队':<12} {'夺冠概率':<10} {'95% CI':<16} {'评分':<6}")
    print("-" * 52)
    for i, r in enumerate(results[:top_n], 1):
        name = r.team_name or r.team_id
        print(f"{i:<4} {name:<12} {r.champion_prob:<10.1%} "
              f"[{r.ci_low:.1%}, {r.ci_high:.1%}]  {r.overall_rating:<6.1f}")


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("输出模块测试")
    print("=" * 50)

    from models.team_rating import rate_team

    teams = [rate_team({"team_id": tid, "team_name": name, "wc_titles": t, "fifa_rank": r,
                        "elo_rating": 1800, "goals_for_20": 1.3, "goals_against_20": 1.0,
                        "win_rate_10": 0.5})
             for tid, name, t, r in [
                 ("ARG","阿根廷",3,1), ("BRA","巴西",5,5), ("FRA","法国",2,2), ("ENG","英格兰",1,4),
             ]]

    # 单场详情
    detail = format_match_detail(teams[0], teams[1])
    print(json.dumps(detail, ensure_ascii=False, indent=2))
