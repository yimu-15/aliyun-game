"""
真实数据采集管线 — 世界杯冠军预测 Agent

数据源:
  1. FootballData Git Repo (data/external/FootballData/) — 世界杯历史 + 球队信息
  2. Kaggle — International Football Results 1872-2024 (kagglehub 下载)
  3. Kaggle — FIFA World Rankings 1992-2024 (kagglehub 下载)

输出:
  data/processed/teams.csv       — 球队主表 (含世界杯历史战绩)
  data/processed/matches.csv     — 世界杯比赛表
  data/processed/rankings.csv    — FIFA 排名表
  data/metadata/collection_report.json — 采集报告

用法:
  python scripts/collect_real_data.py          # 仅解析已有数据
  python scripts/collect_real_data.py --fetch  # 先下载再解析
"""

import argparse
import json
import logging
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# 确保根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("collect")


# =============================================================================
# 配置
# =============================================================================

FOOTBALL_DATA_DIR = Path("data/external/FootballData/World Cups")
FOOTBALL_OTHER_DIR = Path("data/external/FootballData/other")
KAGGLE_MATCHES = Path("data/raw/matches/kaggle_intl_matches.csv")
KAGGLE_RANKINGS = Path("data/raw/rankings/kaggle_fifa_rankings.csv")
OUTPUT_DIR = Path("data/processed")
METADATA_DIR = Path("data/metadata")

# FIFA 三字母代码映射 (来自 FootballData)
COUNTRY_CODE_FILE = FOOTBALL_DATA_DIR / "FIFA_country_codes.csv"


# =============================================================================
# Step 1: 下载 Kaggle 数据 (如需要)
# =============================================================================

def download_kaggle_datasets():
    """通过 kagglehub 下载真实数据集"""
    import kagglehub, shutil

    results = {}

    # 1. FIFA Rankings
    logger.info("下载 FIFA World Rankings...")
    try:
        path = kagglehub.dataset_download("cashncarry/fifaworldranking")
        p = Path(path)
        csv_files = list(p.glob("*.csv"))
        if csv_files:
            dest = KAGGLE_RANKINGS
            dest.parent.mkdir(parents=True, exist_ok=True)
            # 取最新的 CSV
            latest = sorted(csv_files)[-1]
            shutil.copy2(latest, dest)
            logger.info(f"  OK: {dest} ({dest.stat().st_size/1024:.0f} KB)")
            results["rankings"] = True
        else:
            logger.error("  No CSV found in FIFA rankings download")
            results["rankings"] = False
    except Exception as e:
        logger.error(f"  FAIL: {e}")
        results["rankings"] = False

    # 2. International Football Results
    logger.info("下载 International Football Results...")
    try:
        path = kagglehub.dataset_download(
            "martj42/international-football-results-from-1872-to-2017"
        )
        src = Path(path) / "results.csv"
        if src.exists():
            dest = KAGGLE_MATCHES
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            logger.info(f"  OK: {dest} ({dest.stat().st_size/1024:.0f} KB)")
            results["matches"] = True
        else:
            logger.error(f"  results.csv not found in {path}")
            results["matches"] = False
    except Exception as e:
        logger.error(f"  FAIL: {e}")
        results["matches"] = False

    return results


# =============================================================================
# Step 2: 解析 FootballData 世界杯历史数据
# =============================================================================

def parse_footballdata_worldcup() -> pd.DataFrame:
    """
    从 FootballData 解析世界杯历史比赛数据。

    数据来源: https://gitcode.com/gh_mirrors/fo/FootballData
    文件: World Cups/world-cup-YYYY/group_matches.csv + final_matches.csv
    """
    logger.info("解析 FootballData 世界杯数据...")

    all_matches = []

    # 遍历每届世界杯子目录
    subdirs = sorted(FOOTBALL_DATA_DIR.glob("world-cup-*"))
    for subdir in subdirs:
        year_str = subdir.name.replace("world-cup-", "")
        try:
            year = int(year_str)
        except ValueError:
            continue

        # 加载 group_matches.csv 和 final_matches.csv
        for csv_name in ["group_matches.csv", "final_matches.csv"]:
            csv_path = subdir / csv_name
            if not csv_path.exists():
                continue
            try:
                df = pd.read_csv(csv_path, encoding="utf-8")
            except Exception:
                continue

            # 映射列名
            col_map = {}
            for col in df.columns:
                cl = col.lower().replace(" ", "_").replace("/", "_")
                if "home" in cl or col == "home":
                    col_map[col] = "home_team"
                elif "away" in cl or col == "away":
                    col_map[col] = "away_team"
                elif "home_score" in cl:
                    col_map[col] = "home_score"
                elif "away_score" in cl:
                    col_map[col] = "away_score"
                elif "date" in cl:
                    col_map[col] = "date"
                elif "round" in cl or "group" in cl:
                    col_map[col] = "stage"
                elif "stadium" in cl:
                    col_map[col] = "stadium"
                elif "where" in cl:
                    col_map[col] = "city"

            df = df.rename(columns=col_map)

            # 确保需要的列存在
            for req in ["home_team", "away_team"]:
                if req not in df.columns:
                    df[req] = ""
            for req in ["home_score", "away_score"]:
                if req not in df.columns:
                    df[req] = 0

            df["tournament"] = f"FIFA World Cup {year}"
            df["year"] = year
            df["source"] = "FootballData"

            keep_cols = ["date", "home_team", "away_team", "home_score", "away_score",
                         "tournament", "stage", "city", "year", "source"]
            df = df[[c for c in keep_cols if c in df.columns]].reset_index(drop=True)
            all_matches.append(df)

    if not all_matches:
        logger.warning("  FootballData 中未找到 CSV 比赛数据")
        return pd.DataFrame()

    # 统一列名, 去除重复列
    for i, df in enumerate(all_matches):
        df = df.loc[:, ~df.columns.duplicated()]
        all_matches[i] = df

    # 取所有 DataFrame 共有的列
    common_cols = set(all_matches[0].columns)
    for df in all_matches[1:]:
        common_cols &= set(df.columns)
    common_cols = sorted(common_cols)

    aligned = [df[common_cols].reset_index(drop=True) for df in all_matches]
    matches_df = pd.concat(aligned, ignore_index=True)
    matches_df["home_score"] = pd.to_numeric(matches_df["home_score"], errors="coerce").fillna(0).astype(int)
    matches_df["away_score"] = pd.to_numeric(matches_df["away_score"], errors="coerce").fillna(0).astype(int)

    years = sorted(matches_df["year"].unique())
    logger.info(f"  世界杯比赛: {len(matches_df)} 场, 覆盖 {len(years)} 届 ({years[0]}-{years[-1]})")

    return matches_df


# =============================================================================
# Step 3: 处理 Kaggle 比赛数据
# =============================================================================

def process_kaggle_matches() -> pd.DataFrame:
    """
    处理 Kaggle 国际足球比赛数据, 提取世界杯相关比赛。

    数据来源: Kaggle — International Football Results 1872-2024
    URL: https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017
    """
    logger.info("处理 Kaggle 比赛数据...")

    if not KAGGLE_MATCHES.exists():
        logger.warning(f"  {KAGGLE_MATCHES} 不存在, 跳过")
        return pd.DataFrame()

    df = pd.read_csv(KAGGLE_MATCHES, low_memory=False)

    # 标准化列名
    col_map = {}
    for col in df.columns:
        col_map[col] = col.lower().replace(" ", "_")
    df = df.rename(columns=col_map)

    # 筛选世界杯比赛
    if "tournament" in df.columns:
        wc = df[df["tournament"].str.contains("FIFA World Cup", na=False, case=False)].copy()
    else:
        wc = df.copy()

    wc["source"] = "Kaggle"
    logger.info(f"  Kaggle 总比赛: {len(df)} 场, 世界杯: {len(wc)} 场")

    return wc


# =============================================================================
# Step 4: 处理 FIFA 排名
# =============================================================================

def process_fifa_rankings() -> pd.DataFrame:
    """
    处理 FIFA 官方排名数据。

    数据来源: Kaggle — FIFA World Ranking
    URL: https://www.kaggle.com/datasets/cashncarry/fifaworldranking
    """
    logger.info("处理 FIFA 排名数据...")

    if not KAGGLE_RANKINGS.exists():
        logger.warning(f"  {KAGGLE_RANKINGS} 不存在, 跳过")
        return pd.DataFrame()

    df = pd.read_csv(KAGGLE_RANKINGS, low_memory=False)
    logger.info(f"  FIFA 排名记录: {len(df)} 条")

    return df


# =============================================================================
# Step 5: 构建球队主表
# =============================================================================

def build_teams_table(matches_df: pd.DataFrame,
                       rankings_df: pd.DataFrame,
                       football_squads: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    从所有数据源合并构建球队主表。

    字段:
      team_id, team_name, confederation, fifa_rank, fifa_points,
      wc_titles, wc_appearances, wc_matches_played,
      source_match, source_ranking
    """
    logger.info("构建球队主表...")

    # 从比赛数据提取球队
    team_ids = set()
    if "home_team" in matches_df.columns:
        team_ids.update(str(t) for t in matches_df["home_team"].dropna().unique())
    if "away_team" in matches_df.columns:
        team_ids.update(str(t) for t in matches_df["away_team"].dropna().unique())

    teams = pd.DataFrame({"team_id": sorted(team_ids)})

    # 加载 FIFA 国家代码映射 (名称 → 3字母代码)
    code_map = {}
    if COUNTRY_CODE_FILE.exists():
        codes_df = pd.read_csv(COUNTRY_CODE_FILE)
        # 第一列是代码, 第二列是国家名
        if len(codes_df.columns) >= 2:
            code_col = codes_df.columns[0]
            name_col = codes_df.columns[1]
            code_map = dict(zip(codes_df[name_col].str.strip().str.lower(),
                               codes_df[code_col].str.strip()))

    # 添加标准化代码
    teams["fifa_code"] = teams["team_id"].apply(
        lambda x: code_map.get(str(x).strip().lower(), str(x)[:3].upper())
    )

    # 从 FIFA 排名获取最新排名
    if not rankings_df.empty:
        # 尝试多种列名
        team_col = None
        for c in ["country_abrv", "country_code", "team_id"]:
            if c in rankings_df.columns:
                team_col = c
                break

        rank_col = None
        for c in ["rank", "rank_position", "fifa_rank"]:
            if c in rankings_df.columns:
                rank_col = c
                break

        date_col = None
        for c in ["rank_date", "date"]:
            if c in rankings_df.columns:
                date_col = c
                break

        if team_col and rank_col:
            rankings = rankings_df.copy()
            # 标准化排名中的球队代码
            rankings["country_code"] = rankings[team_col].astype(str).str.strip()
            if date_col:
                rankings[date_col] = pd.to_datetime(rankings[date_col], errors="coerce")
                rankings = rankings.sort_values(date_col)
                latest = rankings.groupby("country_code").last().reset_index()
            else:
                latest = rankings.groupby("country_code").first().reset_index()

            latest = latest.rename(columns={"country_code": "code", rank_col: "fifa_rank"})

            if "total_points" in latest.columns:
                latest = latest.rename(columns={"total_points": "fifa_points"})
            if "confederation" in latest.columns:
                latest = latest.rename(columns={"confederation": "confederation"})

            # 用 fifa_code 做 join
            teams = teams.merge(
                latest[["code", "fifa_rank"] +
                        [c for c in ["fifa_points", "confederation"] if c in latest.columns]],
                left_on="fifa_code", right_on="code", how="left",
            ).drop(columns=["code"])
            logger.info(f"  排名信息: {teams['fifa_rank'].notna().sum()}/{len(teams)} 队")

    # 计算世界杯历史战绩
    if not matches_df.empty and "tournament" in matches_df.columns:
        wc_matches = matches_df[matches_df["tournament"].str.contains("World Cup", na=False, case=False)]

        # 参赛次数
        for tid in teams["team_id"]:
            team_matches = wc_matches[
                (wc_matches["home_team"] == tid) | (wc_matches["away_team"] == tid)
            ]
            idx = teams[teams["team_id"] == tid].index
            if len(idx) > 0:
                teams.loc[idx[0], "wc_matches"] = len(team_matches)

    teams["source"] = "merged_from_kaggle_footballdata"
    logger.info(f"  球队主表: {len(teams)} 支")

    return teams


# =============================================================================
# Step 6: 质量检查
# =============================================================================

def run_quality_checks(matches_df: pd.DataFrame,
                        rankings_df: pd.DataFrame,
                        teams_df: pd.DataFrame) -> dict:
    """数据质量检查"""
    report = {
        "checked_at": datetime.now().isoformat(),
        "matches": {},
        "rankings": {},
        "teams": {},
        "overall": "PASS",
    }

    # 比赛数据
    if not matches_df.empty:
        report["matches"] = {
            "total_rows": len(matches_df),
            "columns": list(matches_df.columns),
            "null_home_team": int(matches_df["home_team"].isna().sum()) if "home_team" in matches_df.columns else -1,
            "null_away_team": int(matches_df["away_team"].isna().sum()) if "away_team" in matches_df.columns else -1,
            "null_score": int(matches_df["home_score"].isna().sum()) if "home_score" in matches_df.columns else -1,
            "years_covered": str(sorted(matches_df["year"].unique())) if "year" in matches_df.columns else "N/A",
        }

    # 排名数据
    if not rankings_df.empty:
        report["rankings"] = {
            "total_rows": len(rankings_df),
            "columns": list(rankings_df.columns),
            "unique_teams": int(rankings_df["country_abrv"].nunique()) if "country_abrv" in rankings_df.columns else -1,
        }

    # 球队数据
    if not teams_df.empty:
        report["teams"] = {
            "total_teams": len(teams_df),
            "with_rankings": int(teams_df["fifa_rank"].notna().sum()) if "fifa_rank" in teams_df.columns else 0,
            "with_wc_history": int((teams_df["wc_matches"] > 0).sum()) if "wc_matches" in teams_df.columns else 0,
        }

    # 整体判断
    issues = []
    if matches_df.empty:
        issues.append("matches 数据为空")
    if rankings_df.empty:
        issues.append("rankings 数据为空")
    if teams_df.empty:
        issues.append("teams 数据为空")

    report["overall"] = "PASS" if not issues else f"WARN: {'; '.join(issues)}"

    return report


# =============================================================================
# Step 7: 保存 + 生成报告
# =============================================================================

def save_data(matches_df: pd.DataFrame,
              rankings_df: pd.DataFrame,
              teams_df: pd.DataFrame):
    """保存处理后的数据到 processed/"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # 计算文件哈希
    def hash_dataframe(df, filename):
        path = OUTPUT_DIR / filename
        df.to_csv(path, index=False)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        size_kb = path.stat().st_size / 1024
        logger.info(f"  {filename}: {len(df)} rows, {size_kb:.0f} KB, SHA256={sha}")
        return str(path), sha, size_kb

    saved = {}
    if not matches_df.empty:
        saved["matches"] = hash_dataframe(matches_df, "matches.csv")
    if not rankings_df.empty:
        saved["rankings"] = hash_dataframe(rankings_df, "rankings.csv")
    if not teams_df.empty:
        saved["teams"] = hash_dataframe(teams_df, "teams.csv")

    return saved


def generate_report(saved_files: dict, quality: dict, sources: dict):
    """生成采集报告"""
    report = {
        "pipeline": "collect_real_data.py",
        "generated_at": datetime.now().isoformat(),
        "data_sources": [
            {
                "name": "FootballData (GitCode mirror)",
                "url": "https://gitcode.com/gh_mirrors/fo/FootballData",
                "type": "git_repo",
                "content": "World Cup history, squads, teams",
                "status": "OK" if FOOTBALL_DATA_DIR.exists() else "MISSING",
            },
            {
                "name": "Kaggle — International Football Results 1872-2024",
                "url": "https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017",
                "type": "kagglehub",
                "content": "44,000+ international matches",
                "status": "OK" if KAGGLE_MATCHES.exists() else "MISSING",
            },
            {
                "name": "Kaggle — FIFA World Ranking 1992-2024",
                "url": "https://www.kaggle.com/datasets/cashncarry/fifaworldranking",
                "type": "kagglehub",
                "content": "Monthly FIFA ranking snapshots",
                "status": "OK" if KAGGLE_RANKINGS.exists() else "MISSING",
            },
        ],
        "saved_files": saved_files,
        "quality_check": quality,
        "field_mapping": {
            "teams": ["team_id", "team_name", "fifa_rank", "fifa_points", "confederation", "wc_matches"],
            "matches": ["date", "home_team", "away_team", "home_score", "away_score", "tournament", "stage", "year"],
            "rankings": ["country_abrv", "rank", "total_points", "rank_date", "confederation"],
        },
    }

    report_path = METADATA_DIR / "collection_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n采集报告: {report_path}")
    return report


# =============================================================================
# 主入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="世界杯真实数据采集管线")
    parser.add_argument("--fetch", action="store_true", help="从 Kaggle 下载最新数据")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("世界杯冠军预测 Agent — 真实数据采集管线")
    logger.info("=" * 60)

    # Step 1: 下载 (可选)
    if args.fetch:
        logger.info("\n[Step 1] 下载 Kaggle 数据...")
        download_kaggle_datasets()

    # Step 2: 解析 FootballData
    logger.info("\n[Step 2] 解析 FootballData...")
    wc_matches = parse_footballdata_worldcup()

    # Step 3: 处理 Kaggle 比赛
    logger.info("\n[Step 3] 处理 Kaggle 比赛数据...")
    kaggle_matches = process_kaggle_matches()

    # Step 4: 处理 FIFA 排名
    logger.info("\n[Step 4] 处理 FIFA 排名...")
    rankings = process_fifa_rankings()

    # 合并比赛数据 (优先 Kaggle, FootballData 补充)
    if not wc_matches.empty and not kaggle_matches.empty:
        # 使用共同的列做 concat
        common_cols = list(set(wc_matches.columns) & set(kaggle_matches.columns))
        all_matches = pd.concat(
            [kaggle_matches[common_cols], wc_matches[common_cols]],
            ignore_index=True,
        ).drop_duplicates(subset=["date", "home_team", "away_team"], keep="first")
    elif not wc_matches.empty:
        all_matches = wc_matches
    else:
        all_matches = kaggle_matches

    logger.info(f"  合并后比赛: {len(all_matches)} 场")

    # Step 5: 构建球队表
    logger.info("\n[Step 5] 构建球队主表...")
    teams = build_teams_table(all_matches, rankings)

    # Step 6: 质量检查
    logger.info("\n[Step 6] 质量检查...")
    quality = run_quality_checks(all_matches, rankings, teams)
    print(f"  质量: {quality['overall']}")
    print(f"  比赛: {quality['matches'].get('total_rows', 0)} 行")
    print(f"  排名: {quality['rankings'].get('total_rows', 0)} 行")
    print(f"  球队: {quality['teams'].get('total_teams', 0)} 支 (有排名: {quality['teams'].get('with_rankings', 0)})")

    # Step 7: 保存
    logger.info("\n[Step 7] 保存数据...")
    saved = save_data(all_matches, rankings, teams)

    # 生成报告
    logger.info("\n[Step 8] 生成报告...")
    report = generate_report(saved, quality, {})

    logger.info("\n" + "=" * 60)
    logger.info("采集完成! 输出文件:")
    for name, (path, sha, size) in saved.items():
        logger.info(f"  {path} ({size:.0f} KB)")
    logger.info("=" * 60)

    # 打印数据样例
    if not teams.empty:
        print("\n球队样例 (前5):")
        print(teams[["team_id", "fifa_rank", "wc_matches"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
