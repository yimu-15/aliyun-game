"""球队评分引擎单元测试"""

import pytest
from models.team_rating import TeamSnapshot, rate_team, TeamRating


def test_rate_team_champion():
    """测试: 世界杯冠军应有较高评分"""
    snap = TeamSnapshot(
        "BRA", world_cup_titles=5, world_cup_runner_ups=2,
        world_cup_semi_finals=3, world_cup_appearances=22,
        fifa_rank=5, elo_rating=2100,
        goals_for_per_match=1.8, goals_against_per_match=0.7,
        avg_starter_rating=84, avg_bench_rating=78,
        win_rate_last_10=0.80, streak_wins=4,
    )
    rating = rate_team(snap)
    assert rating.overall > 70
    assert rating.historical > 40
    assert 0 <= rating.overall <= 100


def test_rate_team_weak():
    """测试: 弱队应有较低评分"""
    snap = TeamSnapshot(
        "WEAK", fifa_rank=200,
        goals_for_per_match=0.3, goals_against_per_match=2.5,
        avg_starter_rating=55, avg_bench_rating=50,
        win_rate_last_10=0.05,
    )
    rating = rate_team(snap)
    assert rating.overall < 30


def test_all_scores_in_range():
    """测试: 所有分项在 0-50 范围内"""
    snap = TeamSnapshot("TST")
    rating = rate_team(snap)
    for attr in ["historical", "strength", "attack_defense",
                  "player_quality", "recent_form"]:
        val = getattr(rating, attr)
        assert 0 <= val <= 50, f"{attr}={val} out of range"
