"""
预测模型模块

核心模型:
- team_rating:  五维度球队评分引擎
- group_stage:  泊松单场预测 + 小组赛模拟
- knockout:     淘汰赛三阶段模拟
- champion:     蒙特卡洛冠军预测
- output:       结构化输出
"""
from .team_rating import TeamRating, rate_team
from .group_stage import MatchPrediction, predict_match
from .knockout import simulate_knockout_match, calc_advance_probability
from .champion import ChampionResult, run_monte_carlo
