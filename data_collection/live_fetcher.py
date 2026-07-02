"""
实时多源数据采集模块 — 世界杯预测 Agent

数据源:
  1. Football-Data.org API — 世界杯球队/积分榜/赛程
     API Key: 2e0828890687497591a69119c6aed07d
     Endpoints: /competitions/WC/{teams,standings,matches}

  2. FIFA 官方排名页面 — 抓取最新男足排名
     URL: https://inside.fifa.com/fifa-world-ranking

  3. Elo 评分推算 — 根据 FIFA 排名估算 (缺实时 Elo 时)

输出:
  data/processed/current_teams_power.csv — 队名/FIFA排名/Elo/近5场胜率
  data/fifa_ranking.csv — FIFA 排名缓存

用法:
  python data_collection/live_fetcher.py           # 单次采集
  python data_collection/live_fetcher.py --force   # 强制刷新
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 确保根目录在 path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("data/logs/live_fetcher.log", encoding="utf-8")],
)
logger = logging.getLogger("live_fetcher")

# =============================================================================
# 配置
# =============================================================================

FOOTBALL_API_KEY = "2e0828890687497591a69119c6aed07d"
FOOTBALL_API_BASE = "https://api.football-data.org/v4"
FIFA_RANKING_URL = "https://inside.fifa.com/fifa-world-ranking"
FIFA_RANKING_CACHE = Path("data/fifa_ranking.csv")
OUTPUT_POWER = Path("data/processed/current_teams_power.csv")
CACHE_TTL_HOURS = 6  # 缓存有效期

# 国家队名 → FIFA 三字母代码映射
NAME_TO_TLA = {
    "Argentina": "ARG", "Brazil": "BRA", "France": "FRA", "England": "ENG",
    "Spain": "ESP", "Portugal": "POR", "Netherlands": "NED", "Germany": "GER",
    "Italy": "ITA", "Croatia": "CRO", "Uruguay": "URU", "Belgium": "BEL",
    "Morocco": "MAR", "Colombia": "COL", "Mexico": "MEX", "Japan": "JPN",
    "South Korea": "KOR", "Senegal": "SEN", "USA": "USA", "Denmark": "DEN",
    "Switzerland": "SUI", "Austria": "AUT", "Serbia": "SRB", "Iran": "IRN",
    "Australia": "AUS", "Saudi Arabia": "KSA", "Qatar": "QAT", "Canada": "CAN",
    "Poland": "POL", "Sweden": "SWE", "Wales": "WAL", "Tunisia": "TUN",
    "Costa Rica": "CRC", "Ghana": "GHA", "Cameroon": "CMR", "Egypt": "EGY",
    "Nigeria": "NGA", "Ecuador": "ECU", "Peru": "PER", "Chile": "CHI",
    "Scotland": "SCO", "Norway": "NOR", "Ukraine": "UKR", "Turkey": "TUR",
    "Czech Republic": "CZE", "Hungary": "HUN", "Greece": "GRE",
    "Côte d'Ivoire": "CIV", "Algeria": "ALG", "South Africa": "RSA",
}


# =============================================================================
# 1. Football-Data.org API
# =============================================================================

class FootballDataAPI:
    """Football-Data.org API 封装"""

    def __init__(self, api_key: str = FOOTBALL_API_KEY):
        self.api_key = api_key
        self.base = FOOTBALL_API_BASE
        self.headers = {"X-Auth-Token": api_key}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._request_count = 0

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """带重试的 API 请求"""
        url = f"{self.base}{endpoint}"
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=20)
                self._request_count += 1
                if resp.status_code == 429:  # Rate limit
                    wait = int(resp.headers.get("X-RequestCounter-Reset", 60))
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"API error: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise
        return {}

    def get_wc_teams(self) -> List[dict]:
        """获取 2026 世界杯所有参赛球队"""
        data = self._get("/competitions/WC/teams")
        teams = data.get("teams", [])
        logger.info(f"Football-Data API: {len(teams)} 支世界杯参赛球队")
        return teams

    def get_wc_standings(self) -> List[dict]:
        """获取世界杯小组赛积分榜"""
        data = self._get("/competitions/WC/standings")
        standings = data.get("standings", [])
        logger.info(f"Football-Data API: {len(standings)} 个小组积分榜")
        return standings

    def get_wc_matches(self, status: str = "SCHEDULED") -> List[dict]:
        """获取世界杯赛程 (SCHEDULED / FINISHED / LIVE)"""
        data = self._get("/competitions/WC/matches", params={"status": status})
        matches = data.get("matches", [])
        logger.info(f"Football-Data API: {len(matches)} 场比赛 (status={status})")
        return matches

    def get_team_recent_matches(self, team_id: int, limit: int = 5) -> List[dict]:
        """获取某队最近比赛 (用于计算近期胜率)"""
        data = self._get(f"/teams/{team_id}/matches", params={"limit": limit})
        return data.get("matches", [])


# =============================================================================
# 2. FIFA 排名抓取
# =============================================================================

def fetch_fifa_rankings(force: bool = False) -> pd.DataFrame:
    """
    从 FIFA 官网抓取最新排名。

    策略:
      1. 如果缓存文件存在且未过期，直接使用缓存
      2. 否则用 requests + BeautifulSoup 解析排名表格
      3. 保存到缓存
    """
    if not force and _cache_valid(FIFA_RANKING_CACHE, CACHE_TTL_HOURS):
        logger.info("使用缓存的 FIFA 排名")
        return pd.read_csv(FIFA_RANKING_CACHE)

    logger.info("抓取 FIFA 官方排名...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(FIFA_RANKING_URL, headers=headers, timeout=20, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"FIFA 页面请求失败: {e}")
        return _fallback_rankings()

    soup = BeautifulSoup(resp.text, "lxml")

    # 尝试解析表格 (FIFA 页面可能有多种结构)
    rankings = _parse_fifa_table(soup)
    if not rankings:
        # 尝试从 JSON-LD 或 script 标签提取
        rankings = _parse_fifa_jsonld(soup)

    if not rankings:
        logger.warning("未能从 FIFA 页面解析排名，使用估算数据")
        return _fallback_rankings()

    df = pd.DataFrame(rankings)
    df.to_csv(FIFA_RANKING_CACHE, index=False)
    logger.info(f"FIFA 排名已缓存: {len(df)} 队, {FIFA_RANKING_CACHE}")
    return df


def _cache_valid(cache_path: Path, ttl_hours: int) -> bool:
    """检查缓存是否有效"""
    if not cache_path.exists():
        return False
    age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
    return age_hours < ttl_hours


def _parse_fifa_table(soup: BeautifulSoup) -> List[dict]:
    """尝试从 HTML 表格解析 FIFA 排名"""
    rankings = []
    table = soup.find("table")
    if not table:
        return rankings

    rows = table.find_all("tr")[1:]  # 跳过表头
    for row in rows:
        cols = row.find_all(["td", "th"])
        if len(cols) < 3:
            continue
        try:
            rank = _clean_num(cols[0].get_text())
            team = cols[1].get_text().strip()
            # 移除国家名中的缩写和括号内容
            team = re.sub(r'\s*\([^)]*\)', '', team).strip()
            points = _clean_float(cols[2].get_text()) if len(cols) > 2 else 0.0
            prev_rank = _clean_num(cols[3].get_text()) if len(cols) > 3 else rank

            if rank and team and len(team) > 1:
                rankings.append({
                    "rank": int(rank),
                    "team": team,
                    "points": points,
                    "previous_rank": int(prev_rank) if prev_rank else int(rank),
                })
        except (ValueError, IndexError):
            continue

    return rankings


def _parse_fifa_jsonld(soup: BeautifulSoup) -> List[dict]:
    """尝试从 JSON-LD 提取排名"""
    rankings = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and "itemListElement" in data:
                for item in data["itemListElement"]:
                    rankings.append({
                        "rank": item.get("position", 0),
                        "team": item.get("item", {}).get("name", ""),
                        "points": 0.0,
                        "previous_rank": 0,
                    })
                break
        except (json.JSONDecodeError, AttributeError):
            continue
    return rankings


def _clean_num(text: str) -> Optional[int]:
    """提取数字"""
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else None


def _clean_float(text: str) -> float:
    """提取浮点数"""
    nums = re.findall(r'[\d.]+', text)
    return float(nums[0]) if nums else 0.0


def _fallback_rankings() -> pd.DataFrame:
    """
    当 FIFA 抓取失败时，使用内置参考排名。
    基于 2024 年底 FIFA 官方排名。
    """
    logger.warning("使用内置参考排名 (2024 年底)")

    # 从 Kaggle 排名数据提取最新排名
    kaggle_path = Path("data/raw/rankings/kaggle_fifa_rankings.csv")
    if kaggle_path.exists():
        df = pd.read_csv(kaggle_path, low_memory=False)
        if "rank_date" in df.columns and "country_abrv" in df.columns:
            df["rank_date"] = pd.to_datetime(df["rank_date"], errors="coerce")
            latest = df.sort_values("rank_date").groupby("country_abrv").last().reset_index()
            return latest.rename(columns={
                "country_abrv": "team",
                "rank": "rank",
                "total_points": "points",
            })[["rank", "team", "points"]]

    # 最终降级：内置数据
    builtin = [
        {"rank": 1, "team": "ARG", "points": 1889.0},
        {"rank": 2, "team": "FRA", "points": 1851.0},
        {"rank": 3, "team": "ESP", "points": 1832.0},
        {"rank": 4, "team": "ENG", "points": 1810.0},
        {"rank": 5, "team": "BRA", "points": 1785.0},
        {"rank": 6, "team": "POR", "points": 1756.0},
        {"rank": 7, "team": "NED", "points": 1740.0},
        {"rank": 8, "team": "BEL", "points": 1721.0},
        {"rank": 9, "team": "ITA", "points": 1704.0},
        {"rank": 10, "team": "GER", "points": 1688.0},
        {"rank": 11, "team": "URU", "points": 1665.0},
        {"rank": 12, "team": "COL", "points": 1650.0},
        {"rank": 13, "team": "CRO", "points": 1635.0},
        {"rank": 14, "team": "MAR", "points": 1620.0},
        {"rank": 15, "team": "JPN", "points": 1605.0},
        {"rank": 16, "team": "USA", "points": 1590.0},
        {"rank": 17, "team": "SEN", "points": 1575.0},
        {"rank": 18, "team": "IRN", "points": 1560.0},
        {"rank": 19, "team": "MEX", "points": 1545.0},
        {"rank": 20, "team": "SUI", "points": 1530.0},
        {"rank": 21, "team": "DEN", "points": 1515.0},
        {"rank": 22, "team": "AUT", "points": 1500.0},
        {"rank": 23, "team": "KOR", "points": 1485.0},
        {"rank": 24, "team": "AUS", "points": 1470.0},
        {"rank": 25, "team": "UKR", "points": 1455.0},
        {"rank": 26, "team": "SWE", "points": 1440.0},
        {"rank": 27, "team": "POL", "points": 1425.0},
        {"rank": 28, "team": "HUN", "points": 1410.0},
        {"rank": 29, "team": "WAL", "points": 1395.0},
        {"rank": 30, "team": "SRB", "points": 1380.0},
        {"rank": 31, "team": "EGY", "points": 1365.0},
        {"rank": 32, "team": "NGA", "points": 1350.0},
        {"rank": 33, "team": "CAN", "points": 1335.0},
        {"rank": 34, "team": "ECU", "points": 1320.0},
        {"rank": 35, "team": "CIV", "points": 1305.0},
        {"rank": 36, "team": "TUN", "points": 1290.0},
        {"rank": 37, "team": "ALG", "points": 1275.0},
        {"rank": 38, "team": "CMR", "points": 1260.0},
        {"rank": 39, "team": "CHI", "points": 1245.0},
        {"rank": 40, "team": "PER", "points": 1230.0},
    ]
    return pd.DataFrame(builtin)


# =============================================================================
# 3. Elo 评分估算
# =============================================================================

def estimate_elo(fifa_rank: int) -> float:
    """根据 FIFA 排名估算 Elo 评分"""
    # Elo 大约在 1200-2200 之间，排名第1约 2150，排名第211约 1200
    return max(1200, 2200 - (fifa_rank - 1) * (1000 / 210))


# =============================================================================
# 4. 主采集流程
# =============================================================================

def fetch_all(force: bool = False) -> pd.DataFrame:
    """
    执行完整数据采集流程:
      1. Football-Data API → 球队列表 + 积分榜
      2. FIFA 官方排名抓取
      3. 数据整合 → current_teams_power.csv

    Returns:
        整合后的球队实力 DataFrame
    """
    logger.info("=" * 60)
    logger.info("实时数据采集开始")
    logger.info("=" * 60)

    # ── 1. Football-Data API ──
    api = FootballDataAPI()

    try:
        teams = api.get_wc_teams()
        standings = api.get_wc_standings()
    except Exception as e:
        logger.warning(f"Football-Data API 失败: {e}，使用降级方案")
        teams = []
        standings = []

    # ── 2. FIFA 排名 ──
    rankings_df = fetch_fifa_rankings(force=force)

    # ── 3. 数据整合 ──
    logger.info("整合数据...")
    power_rows = []

    if teams:
        for team in teams:
            name = team.get("name", "")
            tla = team.get("tla", "") or NAME_TO_TLA.get(name, name[:3].upper())
            team_id = team.get("id")

            # 从排名匹配
            rank_row = _find_ranking(rankings_df, tla, name)
            fifa_rank = int(rank_row.get("rank", 99)) if rank_row is not None else 99
            elo = estimate_elo(fifa_rank)

            # 从积分榜计算近期胜率 (MVP简化: API无比赛时用模拟值)
            win_rate = _calc_win_rate_from_standings(team_id, standings, api)

            power_rows.append({
                "team_name": name,
                "tla": tla,
                "fifa_rank": fifa_rank,
                "elo_rating": round(elo),
                "win_rate_last_5": round(win_rate, 3),
                "source": "football_data_api",
            })
    else:
        # 降级: 仅用排名数据
        for _, row in rankings_df.head(48).iterrows():
            team_code = str(row.get("team", ""))
            power_rows.append({
                "team_name": team_code,
                "tla": team_code[:3].upper(),
                "fifa_rank": int(row.get("rank", 99)),
                "elo_rating": round(estimate_elo(int(row.get("rank", 99)))),
                "win_rate_last_5": 0.5,
                "source": "fifa_ranking_only",
            })

    df = pd.DataFrame(power_rows)

    # 保存
    OUTPUT_POWER.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_POWER, index=False)
    logger.info(f"球队实力数据已保存: {OUTPUT_POWER} ({len(df)} 队)")

    # 打印摘要
    logger.info(f"\n{'='*60}")
    logger.info(f"采集完成! 共 {len(df)} 支球队")
    logger.info(f"\nTop-10 实力排行:")
    top10 = df.nsmallest(10, "fifa_rank")
    for _, row in top10.iterrows():
        logger.info(f"  #{row['fifa_rank']:<4} {row['team_name']:<20} Elo={row['elo_rating']:<6} WR={row['win_rate_last_5']:.3f}")
    logger.info(f"{'='*60}")

    return df


def _find_ranking(rankings_df: pd.DataFrame, tla: str, name: str) -> Optional[dict]:
    """在排名 DataFrame 中查找球队"""
    for _, row in rankings_df.iterrows():
        team_val = str(row.get("team", "")).strip().upper()
        if tla.upper() in team_val or team_val in tla.upper():
            return row.to_dict()
    # 尝试名称匹配
    for _, row in rankings_df.iterrows():
        team_val = str(row.get("team", "")).strip()
        if name.lower() in team_val.lower() or team_val.lower() in name.lower():
            return row.to_dict()
    return None


def _calc_win_rate_from_standings(team_id: int, standings: List[dict], api: FootballDataAPI) -> float:
    """从积分榜或最近比赛计算胜率"""
    # 尝试从积分榜计算
    for group in standings:
        for entry in group.get("table", []):
            if entry.get("team", {}).get("id") == team_id:
                played = entry.get("playedGames", 0)
                won = entry.get("won", 0)
                return won / played if played > 0 else 0.5

    # 降级: 尝试获取最近比赛
    try:
        matches = api.get_team_recent_matches(team_id, limit=5)
        if matches:
            wins = sum(1 for m in matches
                       if (m.get("score", {}).get("winner") == "HOME_TEAM"
                           and m.get("homeTeam", {}).get("id") == team_id)
                       or (m.get("score", {}).get("winner") == "AWAY_TEAM"
                           and m.get("awayTeam", {}).get("id") == team_id))
            return wins / len(matches) if matches else 0.5
    except Exception:
        pass

    return 0.5


# =============================================================================
# 测试与 CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="实时数据采集")
    parser.add_argument("--force", action="store_true", help="强制刷新缓存")
    parser.add_argument("--ranking-only", action="store_true", help="仅抓取 FIFA 排名")
    args = parser.parse_args()

    if args.ranking_only:
        df = fetch_fifa_rankings(force=args.force)
        print(df.head(10).to_string(index=False))
    else:
        df = fetch_all(force=args.force)
        print("\n" + df[["team_name", "tla", "fifa_rank", "elo_rating", "win_rate_last_5"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
