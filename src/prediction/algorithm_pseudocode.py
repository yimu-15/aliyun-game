"""
世界杯冠军预测 Agent — 简化版算法伪代码

本文件展示核心算法的清晰伪代码逻辑, 适合:
  - 答辩材料引用
  - 实现参考
  - 代码审查

注意: 这不是可执行的 Python 代码, 而是算法逻辑的精确描述。
     实际实现请参考同目录下的 team_rating.py / match_predictor.py 等文件。

=============================================================================

算法目录:
  1. Algorithm: TeamRating          — 球队综合评分计算
  2. Algorithm: PoissonMatchPredict — 泊松单场预测
  3. Algorithm: SimulateGroupStage  — 小组赛模拟
  4. Algorithm: SimulateKnockout    — 淘汰赛模拟
  5. Algorithm: MonteCarloChampion  — 蒙特卡洛冠军预测
  6. Algorithm: ExplainPrediction   — 因子归因可解释性
  7. 完整输出数据结构
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np


# =============================================================================
# 全局配置
# =============================================================================

RANDOM_SEED = 42
LEAGUE_AVG_GOALS = 1.32        # 国家队比赛场均进球
POISSON_K_MAX = 10             # 泊松分布截断
MONTE_CARLO_N = 10000          # 蒙特卡洛模拟次数

# 球队评分五维度权重
WEIGHTS = {
    "historical":      0.20,   # 历史底蕴
    "strength":        0.30,   # FIFA 排名 / 实力
    "attack_defense":  0.20,   # 攻防效率
    "player_quality":  0.15,   # 球员班底
    "recent_form":     0.15,   # 近期状态
}

# =============================================================================
# 1. Algorithm: TeamRating — 球队综合评分计算
# =============================================================================
#
# 输入: 球队的数据快照 (包含历史、排名、攻防、球员、状态)
# 输出: 0-100 的综合评分 + 5 维度分项分
#
# 时间复杂度: O(1) per team
# 可解释性: 每项评分都可追溯到具体数据

@dataclass
class TeamSnapshot:
    """一支球队在某时间点的数据快照"""
    team_id: str
    team_name: str

    # 历史战绩
    world_cup_titles: int = 0
    world_cup_runner_ups: int = 0
    world_cup_semi_finals: int = 0
    world_cup_appearances: int = 0
    continental_titles: int = 0

    # FIFA 排名
    fifa_rank: int = 100
    fifa_points: float = 0.0
    elo_rating: Optional[float] = None

    # 近 20 场攻防
    goals_for_per_match_20: float = 1.0
    goals_against_per_match_20: float = 1.0

    # 球员 (FIFA 游戏评分)
    avg_starter_rating: float = 70.0
    avg_bench_rating: float = 65.0

    # 近 10 场状态
    win_rate_last_10: float = 0.5
    streak_wins: int = 0       # 连胜场次
    streak_losses: int = 0     # 连败场次
    unbeaten_run: int = 0      # 不败场次
    strong_wins: int = 0       # 击败强队次数


@dataclass
class TeamRating:
    """球队综合评分"""
    team_id: str
    overall: float              # 0-100 综合评分
    historical: float           # 0-50 (乘以权重后贡献 overall)
    strength: float             # 0-50
    attack_defense: float       # 0-50
    player_quality: float       # 0-50
    recent_form: float          # 0-50

    @property
    def attack_score(self) -> float:
        """攻击力得分 (0-50, 来自 attack_defense 维度)"""
        return self.attack_defense * 0.5

    @property
    def defense_score(self) -> float:
        """防守力得分 (0-50, 来自 attack_defense 维度)"""
        return self.attack_defense * 0.5


def compute_historical_score(snapshot: TeamSnapshot) -> float:
    """
    计算历史底蕴得分 (0-50)

    加分规则:
      +10/次 世界杯冠军 (衰减前)
      +6/次  世界杯亚军
      +3/次  世界杯四强
      +1/次  世界杯参赛
      +5/次  洲际杯冠军
    1980 年前的成绩 × 0.5 衰减
    """
    score = 50.0  # 基础分

    score += min(snapshot.world_cup_titles * 10, 50)
    score += min(snapshot.world_cup_runner_ups * 6, 30)
    score += min(snapshot.world_cup_semi_finals * 3, 15)
    score += min(snapshot.world_cup_appearances * 1, 20)
    score += min(snapshot.continental_titles * 5, 25)

    # 归一化到 [0, 50] (理论最高分: 50 + 50 + 30 + 15 + 20 + 25 = 190)
    return min(score * 50 / 190, 50)


def compute_strength_score(snapshot: TeamSnapshot) -> float:
    """
    计算 FIFA 排名/实力得分 (0-50)

    FIFA 排名归一化: score = 50 × (1 - (rank - 1) / 210)
    排名第 1 → 50 分, 排名第 211 → 0 分
    如有 ELO, 与 FIFA 7:3 加权
    """
    fifa_score = 50 * (1 - (snapshot.fifa_rank - 1) / 210)

    if snapshot.elo_rating is not None:
        elo_score = 50 * (snapshot.elo_rating - 500) / (2200 - 500)
        elo_score = max(0, min(50, elo_score))
        return fifa_score * 0.7 + elo_score * 0.3

    return fifa_score


def compute_attack_defense_score(snapshot: TeamSnapshot) -> float:
    """
    计算攻防效率得分 (0-50)

    进攻分 = 25 × (场均进球 / 联赛平均进球)
    防守分 = 25 × (2 - 场均失球 / 联赛平均失球)
    总分 = 进攻分 + 防守分, 钳制到 [0, 50]
    """
    attack_part = 25 * (snapshot.goals_for_per_match_20 / LEAGUE_AVG_GOALS)
    defense_part = 25 * (2 - snapshot.goals_against_per_match_20 / LEAGUE_AVG_GOALS)
    return max(0, min(50, attack_part + defense_part))


def compute_player_quality_score(snapshot: TeamSnapshot) -> float:
    """
    计算球员班底得分 (0-50)

    首发 11 人平均评分 × 60% + 替补评分 × 40%
    归一化: score = avg × 50 / 99
    """
    sq_avg = (snapshot.avg_starter_rating * 0.60 +
              snapshot.avg_bench_rating * 0.40)
    return sq_avg * 50 / 99


def compute_recent_form_score(snapshot: TeamSnapshot) -> float:
    """
    计算近期状态得分 (0-50)

    基础分 = 胜率 × 50
    动量修正: 3 连胜 +5, 5 场不败 +3, 3 连败 -5
    强队胜利: +2/场
    """
    base = snapshot.win_rate_last_10 * 50

    # 动量修正
    if snapshot.streak_wins >= 3:
        base += 5
    if snapshot.unbeaten_run >= 5:
        base += 3
    if snapshot.streak_losses >= 3:
        base -= 5

    # 强队胜利修正
    base += snapshot.strong_wins * 2

    return max(0, min(50, base))


def rate_team(snapshot: TeamSnapshot) -> TeamRating:
    """
    ★ 核心算法: 计算一支球队的综合评分 ★

    流程:
      1. 分别计算 5 个维度的得分 (每个 0-50)
      2. 加权求和: overall = Σ(score_i × weight_i)
      3. 返回带分项评分的 TeamRating 对象
    """
    hist = compute_historical_score(snapshot)
    strength = compute_strength_score(snapshot)
    atk_def = compute_attack_defense_score(snapshot)
    players = compute_player_quality_score(snapshot)
    form = compute_recent_form_score(snapshot)

    overall = (
        hist     * WEIGHTS["historical"] +
        strength * WEIGHTS["strength"] +
        atk_def  * WEIGHTS["attack_defense"] +
        players  * WEIGHTS["player_quality"] +
        form     * WEIGHTS["recent_form"]
    )

    return TeamRating(
        team_id=snapshot.team_id,
        overall=overall,
        historical=hist,
        strength=strength,
        attack_defense=atk_def,
        player_quality=players,
        recent_form=form,
    )


# =============================================================================
# 2. Algorithm: PoissonMatchPredict — 泊松单场预测
# =============================================================================
#
# 输入: 主队评分 + 客队评分 + 是否东道主 + 历史交锋
# 输出: P(主胜) / P(平) / P(客胜) + 期望进球 + 比分概率分布
#
# 核心公式:
#   λ_home = league_avg × attack_strength(A) × defense_strength(B) × home_adv
#   λ_away = league_avg × attack_strength(B) × defense_strength(A)
#
#   其中 attack_strength 和 defense_strength 从球队评分的攻防维度映射:
#     attack_strength(team) = 0.5 + team.attack_score / 50.0    → [0.5, 1.5]
#     defense_strength(team) = 1.5 - team.defense_score / 50.0  → [1.5, 0.5]

@dataclass
class MatchPrediction:
    """单场预测结果"""
    home_team_id: str
    away_team_id: str
    prob_home_win: float       # P(主胜)
    prob_draw: float           # P(平)
    prob_away_win: float       # P(客胜)
    expected_goals_home: float # 期望进球 (主)
    expected_goals_away: float # 期望进球 (客)
    most_likely_score: str     # 最可能比分 "2-1"
    score_distribution: List[Dict]  # 比分概率分布


def _poisson_pmf(k: int, lam: float) -> float:
    """泊松分布概率质量函数: P(X=k) = λ^k × e^(-λ) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _calc_win_draw_loss_probs(lam_home: float, lam_away: float) -> Tuple[float, float, float]:
    """
    从两个独立的泊松分布计算胜/平/负概率

    计算方式:
      对 i=0..K_MAX, j=0..K_MAX:
        p = P(λ_home=i) × P(λ_away=j)
        if i > j: sum to prob_home_win
        if i = j: sum to prob_draw
        if i < j: sum to prob_away_win
    """
    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0

    for i in range(POISSON_K_MAX + 1):
        p_i = _poisson_pmf(i, lam_home)
        for j in range(POISSON_K_MAX + 1):
            p_j = _poisson_pmf(j, lam_away)
            p = p_i * p_j
            if i > j:
                prob_home += p
            elif i == j:
                prob_draw += p
            else:
                prob_away += p

    # 归一化 (补偿截断损失)
    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total

    return prob_home, prob_draw, prob_away


def _compute_lambda(team_rating: TeamRating, opponent_rating: TeamRating,
                    is_home: bool, is_host: bool) -> float:
    """
    计算一支球队的期望进球 λ

    公式:
      λ = LEAGUE_AVG × attack_strength(team) × defense_strength(opponent) × [home_adv]
    """
    attack = 0.5 + team_rating.attack_score / 50.0    # attack_score 来自攻防维度的进攻部分
    defense_opp = 1.5 - opponent_rating.defense_score / 50.0

    lam = LEAGUE_AVG_GOALS * attack * defense_opp

    # 东道主优势
    if is_host and is_home:
        lam *= 1.15

    return lam


def predict_match(home_team: TeamRating, away_team: TeamRating,
                  is_home_host: bool = False,
                  away_is_host: bool = False) -> MatchPrediction:
    """
    ★ 核心算法: 预测单场比赛 ★

    流程:
      1. 计算两队期望进球 λ_home, λ_away
      2. 从泊松分布计算 P(胜)/P(平)/P(负)
      3. 返回完整预测 (含比分分布)
    """
    lam_home = _compute_lambda(home_team, away_team, True, is_home_host)
    lam_away = _compute_lambda(away_team, home_team, False, away_is_host)

    p_home, p_draw, p_away = _calc_win_draw_loss_probs(lam_home, lam_away)

    # 计算最可能比分
    best_score = "0-0"
    best_p = 0.0
    score_dist = []
    for i in range(POISSON_K_MAX + 1):
        for j in range(POISSON_K_MAX + 1):
            p = _poisson_pmf(i, lam_home) * _poisson_pmf(j, lam_away)
            score_dist.append({"score": f"{i}-{j}", "probability": round(p, 6)})
            if p > best_p:
                best_p = p
                best_score = f"{i}-{j}"

    return MatchPrediction(
        home_team_id=home_team.team_id,
        away_team_id=away_team.team_id,
        prob_home_win=round(p_home, 4),
        prob_draw=round(p_draw, 4),
        prob_away_win=round(p_away, 4),
        expected_goals_home=round(lam_home, 2),
        expected_goals_away=round(lam_away, 2),
        most_likely_score=best_score,
        score_distribution=score_dist[:10],  # 只保留前 10 个
    )


# =============================================================================
# 3. Algorithm: SimulateGroupStage — 小组赛模拟
# =============================================================================
#
# 48 队赛制: 16 组 × 3 队, 每队打 2 场, 前 2 名出线

@dataclass
class GroupResult:
    """一个小组的模拟结果"""
    group_id: str
    standings: List[Dict]       # [{team_id, pts, gd, gf, ga, rank}]
    qualifiers: List[str]       # 出线球队 ID (前 2 名)


def simulate_group_stage(group_teams: List[TeamRating],
                         group_id: str,
                         host_teams: List[str],
                         rng: np.random.RandomState) -> GroupResult:
    """
    ★ 核心算法: 小组赛模拟 ★

    流程:
      对组内每对球队:
        1. 调用 predict_match → P(胜/平/负)
        2. 按概率采样实际比分
        3. 累加积分 / 净胜球 / 进球
      排序 → 前 2 名出线
    """
    # 初始化积分表
    standings = {
        t.team_id: {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
        for t in group_teams
    }

    # 一一对阵 (每组 3 队, 每队 2 场比赛)
    for i in range(len(group_teams)):
        for j in range(i + 1, len(group_teams)):
            home = group_teams[i]
            away = group_teams[j]

            # 预测概率
            pred = predict_match(
                home, away,
                is_home_host=home.team_id in host_teams,
            )

            # 从概率分布采样比分
            score_a, score_b = _sample_score(pred.expected_goals_home,
                                             pred.expected_goals_away, rng)

            # 更新主队积分
            standings[home.team_id]["gf"] += score_a
            standings[home.team_id]["ga"] += score_b
            if score_a > score_b:
                standings[home.team_id]["pts"] += 3
            elif score_a == score_b:
                standings[home.team_id]["pts"] += 1

            # 更新客队积分
            standings[away.team_id]["gf"] += score_b
            standings[away.team_id]["ga"] += score_a
            if score_b > score_a:
                standings[away.team_id]["pts"] += 3
            elif score_b == score_a:
                standings[away.team_id]["pts"] += 1

    # 计算净胜球
    for tid in standings:
        standings[tid]["gd"] = standings[tid]["gf"] - standings[tid]["ga"]

    # 排序: 积分 → 净胜球 → 进球
    sorted_teams = sorted(
        standings.items(),
        key=lambda x: (x[1]["pts"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )

    # 生成排名
    result = []
    for rank, (tid, stats) in enumerate(sorted_teams, 1):
        result.append({
            "team_id": tid,
            "pts": stats["pts"],
            "gd": stats["gd"],
            "gf": stats["gf"],
            "ga": stats["ga"],
            "rank": rank,
        })

    return GroupResult(
        group_id=group_id,
        standings=result,
        qualifiers=[r["team_id"] for r in result[:2]],
    )


def _sample_score(lam_a: float, lam_b: float,
                  rng: np.random.RandomState) -> Tuple[int, int]:
    """从泊松分布采样比分"""
    score_a = min(rng.poisson(lam_a), POISSON_K_MAX)
    score_b = min(rng.poisson(lam_b), POISSON_K_MAX)
    return score_a, score_b


# =============================================================================
# 4. Algorithm: SimulateKnockout — 淘汰赛模拟
# =============================================================================
#
# 三阶段: 90 分钟 → 加时赛 → 点球

def simulate_knockout_match(team_a: TeamRating, team_b: TeamRating,
                            rng: np.random.RandomState) -> str:
    """
    ★ 核心算法: 淘汰赛单场模拟 (返回胜者 team_id) ★

    三阶段制胜:
      Stage 1 - 90 分钟: 泊松预测 P(胜)/P(平)/P(负)
      Stage 2 - 加时赛:  λ × 0.33 (30 分钟进球率)
      Stage 3 - 点球大战: 评分更高的队 55% 胜率

    采样决定胜者 (每次独立采样, 模拟比赛不确定性)
    """
    pred = predict_match(team_a, team_b)

    # Stage 1: 常规时间
    roll = rng.random()
    if roll < pred.prob_home_win:
        return team_a.team_id
    elif roll < pred.prob_home_win + pred.prob_away_win:
        return team_b.team_id
    # else: 平局 → 进入加时

    # Stage 2: 加时赛 (进球期望降为 1/3)
    lam_a_extra = pred.expected_goals_home * 0.33
    lam_b_extra = pred.expected_goals_away * 0.33
    p_a_extra, p_draw_extra, p_b_extra = _calc_win_draw_loss_probs(
        lam_a_extra, lam_b_extra
    )

    roll = rng.random()
    if roll < p_a_extra:
        return team_a.team_id
    elif roll < p_a_extra + p_b_extra:
        return team_b.team_id
    # else: 加时平局 → 点球

    # Stage 3: 点球大战 (强队 55% 胜率)
    if team_a.overall >= team_b.overall:
        p_penalty_win = 0.55
    else:
        p_penalty_win = 0.45

    if rng.random() < p_penalty_win:
        return team_a.team_id
    else:
        return team_b.team_id


def simulate_knockout_round(matches: List[Tuple[TeamRating, TeamRating]],
                            rng: np.random.RandomState) -> List[str]:
    """
    模拟一轮淘汰赛的所有比赛

    Args:
      matches: [(team_a, team_b), ...] 本轮所有对阵
    Returns:
      晋级到下一轮的球队 ID 列表
    """
    winners = []
    for team_a, team_b in matches:
        winner = simulate_knockout_match(team_a, team_b, rng)
        winners.append(winner)
    return winners


# =============================================================================
# 5. Algorithm: MonteCarloChampion — 蒙特卡洛冠军预测
# =============================================================================

@dataclass
class ChampionPrediction:
    """冠军预测聚合结果"""
    team_id: str
    champion_prob: float          # 夺冠概率
    confidence_95_low: float      # 95% CI 下界
    confidence_95_high: float     # 95% CI 上界
    final_prob: float             # 进入决赛概率
    semi_prob: float              # 进入半决赛概率
    most_likely_path: List[str]   # 最可能晋级路径 (对手序列)


def run_monte_carlo_simulation(
    all_teams: Dict[str, TeamRating],
    groups: Dict[str, List[str]],       # {group_id: [team_id, team_id, team_id]}
    bracket_structure: Dict,             # 淘汰赛对阵结构
    host_teams: List[str],
    n_simulations: int = MONTE_CARLO_N,
) -> Dict[str, ChampionPrediction]:
    """
    ★ 核心算法: 蒙特卡洛冠军预测 ★

    流程:
      1. 初始化计数器
      2. 循环 N 次:
         a. 小组赛: 每组调用 simulate_group_stage
         b. 淘汰赛: 逐轮调用 simulate_knockout_round
         c. 记录冠军 + 各队晋级轮次 + 晋级路径
      3. 聚合统计 → 夺冠概率 + 置信区间
    """
    rng = np.random.RandomState(RANDOM_SEED)

    # 初始化计数器
    champion_count: Dict[str, int] = defaultdict(int)
    final_count: Dict[str, int] = defaultdict(int)
    semi_count: Dict[str, int] = defaultdict(int)
    round_counts: Dict[str, Dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    path_records: Dict[str, List[List[str]]] = defaultdict(list)

    for sim_idx in range(n_simulations):
        # 设置本次模拟的独立种子
        sim_rng = np.random.RandomState(RANDOM_SEED + sim_idx * 1000)

        # --- 小组赛阶段 ---
        qualified_teams = []  # 32支出线队
        for group_id, team_ids in groups.items():
            group_teams = [all_teams[tid] for tid in team_ids]
            result = simulate_group_stage(group_teams, group_id, host_teams, sim_rng)
            qualified_teams.extend(result.qualifiers)

        # --- 淘汰赛阶段 ---
        # 按赛程对阵表逐轮推进
        current_round = qualified_teams  # 32 支球队
        path: List[List[str]] = [current_round]  # 记录每轮的球队

        for round_matches in bracket_structure["rounds"]:
            # 根据对阵表组织比赛
            matches = []
            for match_def in round_matches:
                idx_a = match_def["team_a_index"]
                idx_b = match_def["team_b_index"]
                if idx_a < len(current_round) and idx_b < len(current_round):
                    tid_a = current_round[idx_a]
                    tid_b = current_round[idx_b]
                    matches.append((all_teams[tid_a], all_teams[tid_b]))

            winners = simulate_knockout_round(matches, sim_rng)
            current_round = winners
            path.append(winners)

        # --- 记录结果 ---
        champion = current_round[0]
        champion_count[champion] += 1

        # 记录晋级轮次 (从 final 倒推)
        for stage_idx, stage_teams in enumerate(path):
            stage_name = _get_stage_name(stage_idx, len(path))
            for tid in stage_teams:
                round_counts[tid][stage_name] += 1

        # 记录决赛参与
        if len(path) >= 2:
            for tid in path[-2]:
                final_count[tid] += 1
        if len(path) >= 3:
            for tid in path[-3]:
                semi_count[tid] += 1

        # 记录路径 (每队取最近一次)
        all_seen = set()
        for stage_teams in path:
            for tid in stage_teams:
                if tid not in all_seen:
                    path_records[tid].append(list(stage_teams))
                    all_seen.add(tid)

    # --- 聚合统计 ---
    results = {}
    for tid in all_teams:
        count = champion_count.get(tid, 0)
        prob = count / n_simulations

        # Wilson 置信区间
        ci_low, ci_high = _wilson_confidence_interval(count, n_simulations)

        # 最可能路径
        best_path = _find_most_likely_path(path_records.get(tid, []))

        results[tid] = ChampionPrediction(
            team_id=tid,
            champion_prob=round(prob, 4),
            confidence_95_low=round(ci_low, 4),
            confidence_95_high=round(ci_high, 4),
            final_prob=round(final_count.get(tid, 0) / n_simulations, 4),
            semi_prob=round(semi_count.get(tid, 0) / n_simulations, 4),
            most_likely_path=best_path,
        )

    return results


def _wilson_confidence_interval(successes: int, total: int, z: float = 1.96):
    """Wilson score 二项分布置信区间"""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(
        (p * (1 - p) + z**2 / (4 * total)) / total
    ) / denominator
    return max(0, center - margin), min(1, center + margin)


def _get_stage_name(stage_idx: int, total_stages: int) -> str:
    """根据位置返回阶段名称"""
    mapping = {0: "group", 1: "round_32", 2: "round_16",
               3: "quarter", 4: "semi", 5: "final"}
    if stage_idx in mapping:
        return mapping[stage_idx]
    if stage_idx == total_stages - 1:
        return "final"
    return f"stage_{stage_idx}"


def _find_most_likely_path(paths: List[List[str]]) -> List[str]:
    """从多条路径中找到最常见的路径"""
    if not paths:
        return []
    path_counts = defaultdict(int)
    for p in paths:
        path_counts[tuple(p)] += 1
    best = max(path_counts, key=path_counts.get)
    return list(best)


# =============================================================================
# 6. Algorithm: ExplainPrediction — 因子归因可解释性
# =============================================================================
#
# 方法: 单项特征消融 (Single Feature Ablation)
#   对每个解释因子, 将其置为中立值后重新预测,
#   比较概率变化量作为该因子的"贡献度"

@dataclass
class FactorExplanation:
    """单个因子的解释"""
    factor_id: str
    display_name: str           # 中文名称 (前端展示)
    value_team_a: float         # 球队 A 在该因子的值
    value_team_b: float         # 球队 B 在该因子的值
    impact: float               # 贡献度 (概率变化绝对值)
    direction: str              # "team_a_advantage" / "team_b_advantage" / "neutral"


NEUTRAL_VALUES = {
    "historical":      25.0,   # 50 分制的中立值
    "strength":        25.0,
    "attack_defense":  25.0,
    "player_quality":  25.0,
    "recent_form":     25.0,
}

FACTOR_NAMES = {
    "historical":      "历史底蕴",
    "strength":        "FIFA 排名",
    "attack_defense":  "攻防效率",
    "player_quality":  "球员班底",
    "recent_form":     "近期状态",
    "home_advantage":  "东道主优势",
}


def explain_match_prediction(
    team_a: TeamRating,
    team_b: TeamRating,
    is_a_host: bool = False,
    is_b_host: bool = False,
) -> Dict:
    """
    ★ 核心算法: 比赛预测可解释性分析 ★

    流程:
      1. 计算基准预测 P0
      2. 对每个因子:
         a. 创建"消融版"评分 (该因子置为中立值)
         b. 重新预测 → P_ablated
         c. 贡献度 = |P0 - P_ablated|
      3. 按贡献度排序 → 返回 Top-N 因子
    """
    # 基准预测
    base_pred = predict_match(team_a, team_b, is_a_host, is_b_host)
    base_p_home = base_pred.prob_home_win

    factors = []

    for factor_id in ["historical", "strength", "attack_defense",
                       "player_quality", "recent_form"]:
        # 消融: 将两队的该因子置为中立值
        neutral = NEUTRAL_VALUES[factor_id]
        ablated_a = _replace_factor(team_a, factor_id, neutral)
        ablated_b = _replace_factor(team_b, factor_id, neutral)

        # 重新预测
        ablated_pred = predict_match(ablated_a, ablated_b, is_a_host, is_b_host)

        # 贡献度 = 概率变化的绝对值
        impact = abs(base_p_home - ablated_pred.prob_home_win)
        direction = "team_a_advantage" if base_p_home > ablated_pred.prob_home_win \
                    else "team_b_advantage"

        factors.append(FactorExplanation(
            factor_id=factor_id,
            display_name=FACTOR_NAMES.get(factor_id, factor_id),
            value_team_a=getattr(team_a, factor_id),
            value_team_b=getattr(team_b, factor_id),
            impact=round(impact, 4),
            direction=direction,
        ))

    # 按贡献度排序
    factors.sort(key=lambda f: f.impact, reverse=True)

    # 东道主优势
    if is_a_host:
        # 消融主场优势
        no_host_pred = predict_match(team_a, team_b, False, False)
        impact = abs(base_p_home - no_host_pred.prob_home_win)
        factors.insert(0, FactorExplanation(
            factor_id="home_advantage",
            display_name="东道主优势",
            value_team_a=1.0,
            value_team_b=0.0,
            impact=round(impact, 4),
            direction="team_a_advantage",
        ))

    return {
        "match": f"{team_a.team_id} vs {team_b.team_id}",
        "prediction": {
            f"{team_a.team_id}_win": base_pred.prob_home_win,
            "draw": base_pred.prob_draw,
            f"{team_b.team_id}_win": base_pred.prob_away_win,
        },
        "expected_goals": {
            team_a.team_id: base_pred.expected_goals_home,
            team_b.team_id: base_pred.expected_goals_away,
        },
        "top_factors": [
            {
                "factor": f.display_name,
                "team_a_value": f.value_team_a,
                "team_b_value": f.value_team_b,
                "impact": f.impact,
                "direction": f.direction,
                "display_text": _generate_factor_text(f, team_a, team_b),
            }
            for f in factors[:5]
        ],
    }


def _replace_factor(rating: TeamRating, factor_id: str,
                    neutral_value: float) -> TeamRating:
    """替换评分中的单个因子为中立值"""
    return TeamRating(
        team_id=rating.team_id,
        overall=rating.overall,  # 此处简化, 实际需重算
        historical=neutral_value if factor_id == "historical" else rating.historical,
        strength=neutral_value if factor_id == "strength" else rating.strength,
        attack_defense=neutral_value if factor_id == "attack_defense" else rating.attack_defense,
        player_quality=neutral_value if factor_id == "player_quality" else rating.player_quality,
        recent_form=neutral_value if factor_id == "recent_form" else rating.recent_form,
    )


def _generate_factor_text(f: FactorExplanation,
                          team_a: TeamRating, team_b: TeamRating) -> str:
    """生成因子的可读解释文本"""
    templates = {
        "历史底蕴": f"历史交锋与冠军底蕴方面占优 (评分: {f.value_team_a:.0f} vs {f.value_team_b:.0f})",
        "FIFA 排名": f"当前 FIFA 排名更具优势 (评分: {f.value_team_a:.0f} vs {f.value_team_b:.0f})",
        "攻防效率": f"近期攻防两端表现更好 (评分: {f.value_team_a:.0f} vs {f.value_team_b:.0f})",
        "球员班底": f"球员整体实力更强 (评分: {f.value_team_a:.0f} vs {f.value_team_b:.0f})",
        "近期状态": f"近期比赛状态更出色 (评分: {f.value_team_a:.0f} vs {f.value_team_b:.0f})",
        "东道主优势": "享有主场之利，历史数据显示东道主胜率提升约15%",
    }
    template = templates.get(f.display_name, f"{f.display_name} 占优")

    advantaged_team = team_a.team_id if f.direction == "team_a_advantage" else team_b.team_id
    return f"[{advantaged_team}] {template}"


# =============================================================================
# 7. 完整输出数据结构
# =============================================================================

"""
API 返回给前端的完整 JSON 结构:

{
  "model_version": "1.0.0-mvp",
  "generated_at": "2026-06-30T12:00:00Z",
  "random_seed": 42,
  "num_simulations": 10000,

  "champion_rankings": [
    {
      "team_id": "BRA",
      "team_name": "巴西",
      "champion_prob": 0.1850,
      "rank": 1,
      "confidence_95": [0.1778, 0.1922],
      "overall_rating": 87.3,
      "rating_breakdown": {
        "历史底蕴": 48.5,
        "FIFA 排名": 46.0,
        "攻防效率": 40.2,
        "球员班底": 42.3,
        "近期状态": 38.7
      },
      "advancement_probs": {
        "final": 0.320,
        "semi": 0.550,
        "quarter": 0.780,
        "round_16": 0.950
      },
      "most_likely_path": ["BRA", "GER", "FRA", "ARG"]
    }
    // ... 其他球队
  ],

  "bracket_tree": {
    "root": {
      "node_id": "FINAL",
      "stage": "final",
      "team_a": { "id": "BRA", "name": "巴西", "advance_prob": 0.580 },
      "team_b": { "id": "FRA", "name": "法国", "advance_prob": 0.420 },
      "left_child": { /* SF_01 节点 */ },
      "right_child": { /* SF_02 节点 */ }
    }
  },

  "match_explanations": {
    "BRA_vs_FRA": {
      "prediction": { "BRA_win": 0.580, "draw": 0.245, "FRA_win": 0.175 },
      "expected_goals": { "BRA": 1.52, "FRA": 1.08 },
      "top_factors": [
        {
          "factor": "FIFA 排名",
          "team_a_value": 46.0,
          "team_b_value": 38.5,
          "impact": 0.085,
          "direction": "team_a_advantage",
          "display_text": "[BRA] 当前 FIFA 排名更具优势 (评分: 46 vs 39)"
        }
        // ...
      ]
    }
  }
}
"""

# =============================================================================
# 算法复杂度总结
# =============================================================================
#
# | 算法                        | 时间复杂度              | 可解释性 |
# |-----------------------------|------------------------|----------|
# | TeamRating (评分)           | O(N) N=球队数          | 完全可解释 |
# | PoissonMatchPredict (单场)  | O(K²) K=10            | 完全可解释 |
# | SimulateGroupStage (小组)   | O(G × M) G=组 M=场    | 完全可解释 |
# | SimulateKnockout (淘汰赛)   | O(R × M) R=轮 M=场    | 完全可解释 |
# | MonteCarloChampion (冠军)   | O(S × 全部) S=10000   | 聚合可解释 |
# | ExplainPrediction (归因)    | O(F × K²) F=因子数    | 完全可解释 |
#
# MVP 阶段单次蒙特卡洛模拟 (10000次) 预估运行时间: < 30 秒 (Python)
