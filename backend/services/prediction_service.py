"""预测服务 — 封装模型调用逻辑"""

from typing import Dict, List, Optional

import numpy as np

from models.team_rating import TeamRating, rate_team
from models.group_stage import predict_match as predict_single
from models.knockout import calc_advance_probability
from models.champion import run_monte_carlo


class PredictionService:
    """预测服务 — 后端 API 与预测模型的桥梁。"""

    def __init__(self):
        self._teams: Optional[Dict[str, TeamRating]] = None
        self._champion_cache: Optional[List[dict]] = None

    def _load_teams(self) -> Dict[str, TeamRating]:
        """加载或创建球队评分 (MVP 使用内置示例数据)"""
        if self._teams is not None:
            return self._teams

        # 使用 dict 快照 (TeamSnapshot 类已移除)
        samples = [
            {"team_id":"BRA","team_name":"巴西","wc_titles":5,"fifa_rank":5,"elo_rating":2100,
             "goals_for_20":1.8,"goals_against_20":0.7,"avg_starter_rating":84,"avg_bench_rating":78,
             "win_rate_10":0.80,"streak_wins":4,"unbeaten_run":8,"strong_wins":3},
            {"team_id":"ARG","team_name":"阿根廷","wc_titles":3,"fifa_rank":1,"elo_rating":2135,
             "goals_for_20":1.6,"goals_against_20":0.5,"avg_starter_rating":85,"avg_bench_rating":79,
             "win_rate_10":0.90,"streak_wins":6,"unbeaten_run":12,"strong_wins":4},
            {"team_id":"FRA","team_name":"法国","wc_titles":2,"fifa_rank":2,"elo_rating":2080,
             "goals_for_20":1.7,"goals_against_20":0.8,"avg_starter_rating":83,"avg_bench_rating":77,
             "win_rate_10":0.75,"streak_wins":2,"unbeaten_run":5,"strong_wins":2},
            {"team_id":"ENG","team_name":"英格兰","wc_titles":1,"fifa_rank":4,"elo_rating":2020,
             "goals_for_20":1.5,"goals_against_20":0.6,"avg_starter_rating":82,"avg_bench_rating":78,
             "win_rate_10":0.70,"unbeaten_run":7,"strong_wins":2},
            {"team_id":"GER","team_name":"德国","wc_titles":4,"fifa_rank":16,"elo_rating":1960,
             "goals_for_20":1.6,"goals_against_20":0.9,"avg_starter_rating":81,"avg_bench_rating":75,
             "win_rate_10":0.60,"streak_losses":2,"strong_wins":1},
            {"team_id":"ESP","team_name":"西班牙","wc_titles":1,"fifa_rank":8,"elo_rating":2000,
             "goals_for_20":1.7,"goals_against_20":0.6,"avg_starter_rating":82,"avg_bench_rating":76,
             "win_rate_10":0.85,"streak_wins":5,"unbeaten_run":10,"strong_wins":3},
            {"team_id":"POR","team_name":"葡萄牙","wc_titles":0,"fifa_rank":6,"elo_rating":1980,
             "goals_for_20":1.8,"goals_against_20":0.7,"avg_starter_rating":81,"avg_bench_rating":74,
             "win_rate_10":0.80,"streak_wins":3,"unbeaten_run":6,"strong_wins":2},
            {"team_id":"NED","team_name":"荷兰","wc_titles":0,"fifa_rank":7,"elo_rating":1970,
             "goals_for_20":1.5,"goals_against_20":0.8,"avg_starter_rating":80,"avg_bench_rating":74,
             "win_rate_10":0.65,"strong_wins":1},
        ]
        self._teams = {s["team_id"]: rate_team(s) for s in samples}
        return self._teams

    def get_champion_rankings(self) -> List[dict]:
        """获取冠军概率排行榜"""
        if self._champion_cache:
            return self._champion_cache

        teams = self._load_teams()
        groups = {"A": ["BRA","POR","NED"], "B": ["ARG","ESP","ENG"], "C": ["FRA","GER","NED"]}
        bracket = [[(0,1),(2,3),(4,5)], [(0,1)], [(0,1)]]
        host_ids = []

        results = run_monte_carlo(list(teams.values()), groups, bracket, host_ids, n_sim=500, seed=42)
        self._champion_cache = [r.to_dict() for r in results]
        return self._champion_cache

    def get_bracket_tree(self) -> dict:
        """获取赛程树数据"""
        rankings = self.get_champion_rankings()
        return {
            "root": {
                "node_id": "FINAL", "stage": "final",
                "team_a": {"id": rankings[0]["team_id"], "advance_prob": 0.55},
                "team_b": {"id": rankings[1]["team_id"], "advance_prob": 0.45},
            }
        }

    def explain_match(self, team_a_id: str, team_b_id: str) -> dict:
        """单场比赛预测 + 解释"""
        teams = self._load_teams()
        a = teams.get(team_a_id)
        b = teams.get(team_b_id)
        if not a or not b:
            return {"error": f"球队不存在: {team_a_id} / {team_b_id}"}

        pred = predict_single(a, b)
        adv_a = calc_advance_probability(a, b)

        return {
            "match": f"{a.team_id} vs {b.team_id}",
            "prediction": {
                f"{a.team_id}_win": pred.p_home_win,
                "draw": pred.p_draw,
                f"{b.team_id}_win": pred.p_away_win,
            },
            "expected_goals": {a.team_id: pred.lam_home, b.team_id: pred.lam_away},
            "best_score": pred.best_score,
            "advance_prob_a": round(adv_a, 4),
            "factors": {
                "strength": {"name": "FIFA排名", "a": round(a.strength, 1), "b": round(b.strength, 1)},
                "attack_defense": {"name": "攻防效率", "a": round(a.attack_defense, 1), "b": round(b.attack_defense, 1)},
                "recent_form": {"name": "近期状态", "a": round(a.recent_form, 1), "b": round(b.recent_form, 1)},
                "historical": {"name": "历史底蕴", "a": round(a.historical, 1), "b": round(b.historical, 1)},
            },
        }
