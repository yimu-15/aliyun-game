"""
球队评分计算模块 — 五维度加权模型

每个维度 0-50 分, 加权后得到综合评分 0-100。

维度:
  1. 历史底蕴 (20%): 世界杯冠军/亚军/四强/参赛次数
  2. FIFA排名 (30%): FIFA + ELO 排名归一化
  3. 攻防效率 (20%): 近20场进球率/失球率
  4. 球员班底 (15%): 首发+替补平均评分 (FIFA游戏数据代理)
  5. 近期状态 (15%): 近10场胜率 + 动量修正
"""

from dataclasses import dataclass
from typing import List, Optional


# ── 权重配置 ──
WEIGHTS = {
    "historical": 0.20,
    "strength": 0.30,
    "attack_defense": 0.20,
    "player_quality": 0.15,
    "recent_form": 0.15,
}

LEAGUE_AVG_GOALS = 1.32   # 国际比赛场均进球
MAX_FIFA_RANK = 211       # FIFA 成员总数
POINTS_PER_TITLE = 10     # 每个世界杯冠军加分


@dataclass
class TeamRating:
    """球队综合评分"""
    team_id: str
    team_name: str = ""
    overall: float = 0.0
    historical: float = 0.0
    strength: float = 0.0
    attack_defense: float = 0.0
    player_quality: float = 0.0
    recent_form: float = 0.0
    confederation: str = ""
    fifa_rank: int = 100

    @property
    def attack_score(self) -> float:
        """攻击得分 (0-50)"""
        return self.attack_defense * 0.5

    @property
    def defense_score(self) -> float:
        """防守得分 (0-50)"""
        return self.attack_defense * 0.5

    @property
    def attack_factor(self) -> float:
        """攻击力系数 [0.5, 1.5] — 用于泊松 λ 计算"""
        return 0.5 + self.attack_score / 50.0

    @property
    def defense_factor(self) -> float:
        """防守力系数 [1.5, 0.5] — 对手 λ 的乘数"""
        return 1.5 - self.defense_score / 50.0


# =============================================================================
# 单项评分函数
# =============================================================================

def _score_historical(snap: dict) -> float:
    """历史底蕴 (0-50)"""
    score = 50.0
    score += min(snap.get("wc_titles", 0) * POINTS_PER_TITLE, 50)
    score += min(snap.get("wc_runner_ups", 0) * 6, 30)
    score += min(snap.get("wc_semi_finals", 0) * 3, 15)
    score += min(snap.get("wc_appearances", 0) * 1, 20)
    score += min(snap.get("continental_titles", 0) * 5, 25)
    return min(score * 50 / 190, 50)


def _score_strength(snap: dict) -> float:
    """FIFA排名 + ELO (0-50)"""
    rank = snap.get("fifa_rank", 100)
    fifa_s = 50 * (1 - (rank - 1) / MAX_FIFA_RANK)
    elo = snap.get("elo_rating")
    if elo is not None:
        elo_s = 50 * (elo - 500) / (2200 - 500)
        elo_s = max(0, min(50, elo_s))
        return fifa_s * 0.7 + elo_s * 0.3
    return fifa_s


def _score_attack_defense(snap: dict) -> float:
    """攻防效率 (0-50)"""
    gf = snap.get("goals_for_20", LEAGUE_AVG_GOALS)
    ga = snap.get("goals_against_20", LEAGUE_AVG_GOALS)
    atk = 25 * (gf / LEAGUE_AVG_GOALS)
    df = 25 * (2 - ga / LEAGUE_AVG_GOALS)
    return max(0, min(50, atk + df))


def _score_players(snap: dict) -> float:
    """球员班底 (0-50) — 使用 FIFA 游戏评分代理"""
    starter = snap.get("avg_starter_rating", 70.0)
    bench = snap.get("avg_bench_rating", 65.0)
    sq = starter * 0.60 + bench * 0.40
    return sq * 50 / 99


def _score_form(snap: dict) -> float:
    """近期状态 (0-50)"""
    base = snap.get("win_rate_10", 0.4) * 50
    if snap.get("streak_wins", 0) >= 3:
        base += 5
    if snap.get("unbeaten_run", 0) >= 5:
        base += 3
    if snap.get("streak_losses", 0) >= 3:
        base -= 5
    base += snap.get("strong_wins", 0) * 2
    return max(0, min(50, base))


# =============================================================================
# 主评分函数
# =============================================================================

def rate_team(snapshot: dict) -> TeamRating:
    """
    计算单支球队的综合评分。

    Args:
        snapshot: dict, 包含 team_id, wc_titles, fifa_rank, elo_rating,
                  goals_for_20, goals_against_20, win_rate_10 等字段

    Returns:
        TeamRating 对象

    Example:
        >>> snap = {"team_id": "BRA", "wc_titles": 5, "fifa_rank": 5, "elo_rating": 2100,
        ...         "goals_for_20": 1.8, "goals_against_20": 0.7, "win_rate_10": 0.8}
        >>> r = rate_team(snap)
        >>> print(f"Brazil overall: {r.overall:.1f}")
    """
    h = _score_historical(snapshot)
    s = _score_strength(snapshot)
    ad = _score_attack_defense(snapshot)
    pq = _score_players(snapshot)
    rf = _score_form(snapshot)

    overall = (
        h * WEIGHTS["historical"]
        + s * WEIGHTS["strength"]
        + ad * WEIGHTS["attack_defense"]
        + pq * WEIGHTS["player_quality"]
        + rf * WEIGHTS["recent_form"]
    )

    return TeamRating(
        team_id=snapshot.get("team_id", ""),
        team_name=snapshot.get("team_name", ""),
        overall=overall,
        historical=h,
        strength=s,
        attack_defense=ad,
        player_quality=pq,
        recent_form=rf,
        confederation=snapshot.get("confederation", ""),
        fifa_rank=snapshot.get("fifa_rank", 100),
    )


def rate_all_teams(snapshots: List[dict]) -> List[TeamRating]:
    """批量评分"""
    return [rate_team(s) for s in snapshots]


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("球队评分模块测试")
    print("=" * 50)

    test_snaps = [
        {"team_id": "BRA", "team_name": "巴西", "wc_titles": 5, "fifa_rank": 5,
         "elo_rating": 2100, "goals_for_20": 1.8, "goals_against_20": 0.7,
         "win_rate_10": 0.80, "streak_wins": 4, "avg_starter_rating": 84, "avg_bench_rating": 78},
        {"team_id": "ARG", "team_name": "阿根廷", "wc_titles": 3, "fifa_rank": 1,
         "elo_rating": 2135, "goals_for_20": 1.6, "goals_against_20": 0.5,
         "win_rate_10": 0.90, "streak_wins": 6, "avg_starter_rating": 85, "avg_bench_rating": 79},
        {"team_id": "JPN", "team_name": "日本", "wc_titles": 0, "fifa_rank": 17,
         "elo_rating": 1820, "goals_for_20": 1.4, "goals_against_20": 0.9,
         "win_rate_10": 0.75, "streak_wins": 5, "avg_starter_rating": 74, "avg_bench_rating": 70},
    ]

    for snap in test_snaps:
        r = rate_team(snap)
        print(f"\n{r.team_name} ({r.team_id})")
        print(f"  综合: {r.overall:.1f}  |  FIFA#{r.fifa_rank}")
        print(f"  历史: {r.historical:.1f}  |  FIFA排名: {r.strength:.1f}")
        print(f"  攻防: {r.attack_defense:.1f}  |  球员: {r.player_quality:.1f}  |  状态: {r.recent_form:.1f}")
