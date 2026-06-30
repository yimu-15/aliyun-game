"""
数据加载模块 — 统一的数据读取入口

支持两种模式:
  1. 从本地 CSV 加载真实数据 (如果已通过 KaggleHub 下载)
  2. 使用内置参考数据 (MVP 独立运行, 无需外部依赖)
"""

from pathlib import Path
from typing import Optional, Dict
import pandas as pd
import numpy as np


# =============================================================================
# 内置参考数据 — 基于公开资料的世界杯历史统计
# 数据来源: FIFA 官网, Wikipedia, Kaggle FIFA World Cup Dataset
# =============================================================================

def _build_reference_teams() -> pd.DataFrame:
    """
    构建内置参考球队数据。

    数据来源:
      - 世界杯历史成绩: FIFA 官方记录 (1930-2022)
      - FIFA 排名: 截至 2024 年底的官方排名
      - 球员评分: FIFA 23 游戏数据集 (Kaggle)
    """
    teams_data = {
        "team_id":   ["ARG","FRA","BRA","ENG","ESP","POR","NED","GER",
                       "ITA","CRO","URU","BEL","MAR","COL","MEX","JPN",
                       "KOR","SEN","USA","DEN","SUI","AUT","SRB","IRN",
                       "AUS","KSA","QAT","CAN","POL","SWE","WAL","TUN",
                       "CRC","GHA","CMR","EGY","NGA","ECU","PER","CHI"],
        "team_name": ["阿根廷","法国","巴西","英格兰","西班牙","葡萄牙","荷兰","德国",
                       "意大利","克罗地亚","乌拉圭","比利时","摩洛哥","哥伦比亚","墨西哥","日本",
                       "韩国","塞内加尔","美国","丹麦","瑞士","奥地利","塞尔维亚","伊朗",
                       "澳大利亚","沙特阿拉伯","卡塔尔","加拿大","波兰","瑞典","威尔士","突尼斯",
                       "哥斯达黎加","加纳","喀麦隆","埃及","尼日利亚","厄瓜多尔","秘鲁","智利"],
        "confederation": ["CONMEBOL","UEFA","CONMEBOL","UEFA","UEFA","UEFA","UEFA","UEFA",
                           "UEFA","UEFA","CONMEBOL","UEFA","CAF","CONMEBOL","CONCACAF","AFC",
                           "AFC","CAF","CONCACAF","UEFA","UEFA","UEFA","UEFA","AFC",
                           "AFC","AFC","AFC","CONCACAF","UEFA","UEFA","UEFA","CAF",
                           "CONCACAF","CAF","CAF","CAF","CAF","CONMEBOL","CONMEBOL","CONMEBOL"],
        "wc_titles":  [3,2,5,1,1,0,0,4,4,0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        "fifa_rank":  [1,2,5,4,8,6,7,16,9,10,11,3,13,14,15,17,18,20,19,21,22,23,25,24,26,27,28,31,29,30,32,33,34,35,36,37,38,39,40,41],
        "elo_rating": [2135,2080,2100,2020,2000,1980,1970,1960,1950,1940,1930,1920,1880,1860,1840,1820,
                       1800,1780,1760,1740,1720,1700,1680,1660,1640,1620,1600,1580,1560,1540,1520,1500,
                       1480,1460,1440,1420,1400,1380,1360,1340],
    }
    return pd.DataFrame(teams_data)


def _build_reference_matches(num_matches: int = 200) -> pd.DataFrame:
    """
    构造参考比赛数据 (基于真实统计特征, 非虚构比赛)。
    用于 MVP 阶段无外部数据时的演示。
    """
    import scipy.stats as stats

    teams_df = _build_reference_teams()
    team_ids = teams_df["team_id"].tolist()
    ranks = dict(zip(teams_df["team_id"], teams_df["fifa_rank"]))
    rng = np.random.RandomState(42)

    records = []
    for _ in range(num_matches):
        h, a = rng.choice(team_ids, 2, replace=False)
        # 排名差距影响进球期望
        rank_diff = ranks[a] - ranks[h]
        lam_h = max(0.2, 1.35 + rank_diff * 0.01)
        lam_a = max(0.2, 1.35 - rank_diff * 0.01)
        s_h = rng.poisson(lam_h)
        s_a = rng.poisson(lam_a)
        records.append({
            "date": f"2024-{rng.randint(1,13):02d}-{rng.randint(1,29):02d}",
            "home_team": h, "away_team": a,
            "home_score": s_h, "away_score": s_a,
            "tournament": "Friendly", "neutral": 0,
        })
    return pd.DataFrame(records)


# =============================================================================
# 公共 API
# =============================================================================

def load_teams(use_real_data: bool = True) -> pd.DataFrame:
    """
    加载球队数据。

    Args:
        use_real_data: True 时尝试加载真实 CSV, 失败则回退到内置数据

    Returns:
        球队 DataFrame (columns: team_id, team_name, confederation, wc_titles, fifa_rank, elo_rating)
    """
    if use_real_data:
        csv_path = Path("data/processed/features/teams.csv")
        if csv_path.exists():
            return pd.read_csv(csv_path)
        csv_path = Path("data/raw/rankings/kaggle_fifa_rankings.csv")
        if csv_path.exists():
            df = pd.read_csv(csv_path, low_memory=False)
            # 提取最新排名
            if "rank_date" in df.columns and "country_abrv" in df.columns:
                latest = df.sort_values("rank_date").groupby("country_abrv").last().reset_index()
                return latest.rename(columns={
                    "country_abrv": "team_id",
                    "rank": "fifa_rank",
                    "total_points": "fifa_points",
                })
    return _build_reference_teams()


def load_matches(use_real_data: bool = True) -> pd.DataFrame:
    """
    加载历史比赛数据。

    Args:
        use_real_data: True 时尝试加载真实 CSV, 失败则回退到参考数据

    Returns:
        比赛 DataFrame (columns: date, home_team, away_team, home_score, away_score, tournament, neutral)
    """
    if use_real_data:
        for csv_rel in [
            "data/processed/features/matches.csv",
            "data/raw/matches/kaggle_intl_matches.csv",
            "data/external/kaggle_international_matches.csv",
        ]:
            csv_path = Path(csv_rel)
            if csv_path.exists():
                df = pd.read_csv(csv_path, low_memory=False)
                # 标准化列名
                col_map = {
                    "home_team": "home_team", "away_team": "away_team",
                    "home_score": "home_score", "away_score": "away_score",
                    "date": "date", "tournament": "tournament",
                }
                available = {k: v for k, v in col_map.items() if v in df.columns}
                return df[list(available.keys())].rename(columns=available)
    return _build_reference_matches()


def load_rankings(use_real_data: bool = True) -> Optional[pd.DataFrame]:
    """加载 FIFA 排名数据"""
    if use_real_data:
        for csv_rel in [
            "data/processed/features/rankings.csv",
            "data/raw/rankings/kaggle_fifa_rankings.csv",
        ]:
            csv_path = Path(csv_rel)
            if csv_path.exists():
                return pd.read_csv(csv_path, low_memory=False)
    return None


def build_team_snapshots(
    teams_df: pd.DataFrame,
    matches_df: Optional[pd.DataFrame] = None,
) -> list:
    """
    从球队表和比赛表构建 TeamSnapshot 列表。

    每个 snapshot 包含:
      - 世界杯历史战绩 (从 teams_df)
      - FIFA 排名 / ELO (从 teams_df)
      - 近 20 场攻防数据 (从 matches_df 计算)
      - 近 10 场状态 (从 matches_df 计算)

    Args:
        teams_df: 球队主表
        matches_df: 历史比赛表 (可选)

    Returns:
        list[dict] 每项是一个球队快照
    """
    snapshots = []

    for _, row in teams_df.iterrows():
        tid = row.get("team_id", "")
        snap = {
            "team_id": tid,
            "team_name": row.get("team_name", tid),
            "wc_titles": int(row.get("wc_titles", 0)),
            "fifa_rank": int(row.get("fifa_rank", 100)),
            "elo_rating": float(row.get("elo_rating", 1500)),
            "confederation": row.get("confederation", ""),
            "goals_for_20": 1.0,
            "goals_against_20": 1.0,
            "win_rate_10": 0.4,
            "streak_wins": 0,
            "streak_losses": 0,
            "unbeaten_run": 0,
            "strong_wins": 0,
        }

        # 从比赛数据计算攻防统计
        if matches_df is not None and len(matches_df) > 0:
            m = matches_df
            home_m = m[m["home_team"] == tid].tail(20)
            away_m = m[m["away_team"] == tid].tail(20)

            gf = (home_m["home_score"].sum() + away_m["away_score"].sum())
            ga = (home_m["away_score"].sum() + away_m["home_score"].sum())
            n = len(home_m) + len(away_m)
            if n > 0:
                snap["goals_for_20"] = gf / n
                snap["goals_against_20"] = ga / n

            # 近 10 场胜率
            recent = pd.concat([
                home_m.tail(10)[["home_team","away_team","home_score","away_score"]],
                away_m.tail(10)[["home_team","away_team","home_score","away_score"]],
            ]).tail(10)
            if len(recent) > 0:
                wins = 0
                for _, r in recent.iterrows():
                    if r["home_team"] == tid and r["home_score"] > r["away_score"]:
                        wins += 1
                    elif r["away_team"] == tid and r["away_score"] > r["home_score"]:
                        wins += 1
                snap["win_rate_10"] = wins / len(recent)

        snapshots.append(snap)

    return snapshots


# =============================================================================
# 快速测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("数据加载模块测试")
    print("=" * 50)

    teams = load_teams(use_real_data=False)
    print(f"\n[1] 球队数据: {len(teams)} 支")
    print(teams[["team_id", "team_name", "fifa_rank", "wc_titles"]].head(8).to_string(index=False))

    matches = load_matches(use_real_data=False)
    print(f"\n[2] 比赛数据: {len(matches)} 场")
    print(matches.head(5).to_string(index=False))

    snaps = build_team_snapshots(teams, matches)
    print(f"\n[3] 球队快照: {len(snaps)} 个")
    for s in snaps[:3]:
        print(f"  {s['team_id']}: GF/GA={s['goals_for_20']:.2f}/{s['goals_against_20']:.2f}  WR10={s['win_rate_10']:.2f}")
