"""
快速演示脚本 — 无需数据即可运行

用法:
    python scripts/run_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.team_rating import rate_team
from models.group_stage import predict_match


def format_pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def main():
    print("=" * 60)
    print("  世界杯冠军预测 Agent — 快速演示")
    print("=" * 60)

    # 1. 构建球队评分 (使用 dict 快照)
    print("\n[1] 构建球队评分...")
    brazil = rate_team({
        "team_id": "BRA", "team_name": "巴西",
        "wc_titles": 5, "fifa_rank": 5, "elo_rating": 2100,
        "goals_for_20": 1.8, "goals_against_20": 0.7,
        "avg_starter_rating": 84, "avg_bench_rating": 78,
        "win_rate_10": 0.80, "streak_wins": 4,
    })
    argentina = rate_team({
        "team_id": "ARG", "team_name": "阿根廷",
        "wc_titles": 3, "fifa_rank": 1, "elo_rating": 2135,
        "goals_for_20": 1.6, "goals_against_20": 0.5,
        "avg_starter_rating": 85, "avg_bench_rating": 79,
        "win_rate_10": 0.90, "streak_wins": 6,
    })
    france = rate_team({
        "team_id": "FRA", "team_name": "法国",
        "wc_titles": 2, "fifa_rank": 2, "elo_rating": 2080,
        "goals_for_20": 1.7, "goals_against_20": 0.8,
        "avg_starter_rating": 83, "avg_bench_rating": 77,
        "win_rate_10": 0.75,
    })
    england = rate_team({
        "team_id": "ENG", "team_name": "英格兰",
        "wc_titles": 1, "fifa_rank": 4, "elo_rating": 2020,
        "goals_for_20": 1.5, "goals_against_20": 0.6,
        "avg_starter_rating": 82, "avg_bench_rating": 78,
        "win_rate_10": 0.70,
    })

    for t in [brazil, argentina, france, england]:
        name = t.team_name or t.team_id
        print(f"  {name}: {t.overall:.1f} 分 (历史{t.historical:.0f} 排名{t.strength:.0f} 攻防{t.attack_defense:.0f} 状态{t.recent_form:.0f})")

    # 2. 预测比赛
    print("\n[2] 预测比赛:")
    for h, a in [(brazil, argentina), (france, england), (brazil, france)]:
        pred = predict_match(h, a)
        hn = h.team_name or h.team_id
        an = a.team_name or a.team_id
        print(f"  {hn} vs {an}:")
        print(f"    胜 {format_pct(pred.p_home_win)} / 平 {format_pct(pred.p_draw)} / 负 {format_pct(pred.p_away_win)}")
        print(f"    xG: {pred.lam_home:.2f} - {pred.lam_away:.2f}  |  最可能比分: {pred.best_score}")

    # 3. 淘汰赛晋级概率
    print("\n[3] 淘汰赛晋级概率:")
    from models.knockout import calc_advance_probability
    for h, a in [(brazil, argentina), (france, england)]:
        hn = h.team_name or h.team_id
        an = a.team_name or a.team_id
        prob = calc_advance_probability(h, a)
        print(f"  {hn} vs {an}: {hn} 晋级概率 {format_pct(prob)}")

    print("\n" + "=" * 60)
    print("  演示完成! 启动完整服务:")
    print("    streamlit run app/main.py    # 前端页面")
    print("    python main.py --teams 32    # CLI 预测")
    print("=" * 60)


if __name__ == "__main__":
    main()
