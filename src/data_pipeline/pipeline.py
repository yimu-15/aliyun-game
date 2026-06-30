"""
数据采集与处理主流程

完整流程:
1. 获取 (fetch)      — 从 Kaggle/本地/手动获取原始数据
2. 清洗 (clean)      — 缺失值/重复值/异常值处理
3. 标准化 (normalize) — 球队名统一、日期格式统一
4. 合并 (merge)      — 多数据源合并为统一数据集
5. 存储 (store)      — 写入 SQLite 数据库
6. 追溯 (trace)      — 记录数据来源链路

用法:
    python -m src.data_pipeline.pipeline --fetch --clean --store
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_pipeline.fetchers.base_fetcher import DataFetcher
from src.data_pipeline.fetchers.kaggle_fetcher import (
    create_kaggle_intl_matches_fetcher,
    create_kaggle_worldcup_fetcher,
    create_kaggle_fifa_rankings_fetcher,
)
from src.data_pipeline.cleaners.name_normalizer import NameNormalizer
from src.data_pipeline.quality import DataQualityController, QualityReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/logs/pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class DataPipeline:
    """
    数据采集与处理主流程协调器。

    ┌────────┐    ┌────────┐    ┌──────────┐    ┌────────┐    ┌────────┐
    │ 获取   │→→→│ 清洗   │→→→│ 标准化    │→→→│ 合并   │→→→│ 存储   │
    │ fetch  │    │ clean  │    │ normalize │    │ merge  │    │ store  │
    └────────┘    └────────┘    └──────────┘    └────────┘    └────────┘
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.logs_dir = self.data_dir / "logs"
        self.sources_dir = self.data_dir / "sources"
        for d in [self.raw_dir, self.processed_dir, self.logs_dir, self.sources_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 工具
        self.normalizer = NameNormalizer()
        self.qc = DataQualityController(normalizer=self.normalizer)

        # 中间数据
        self.raw_matches: Optional[pd.DataFrame] = None       # 原始比赛数据
        self.raw_rankings: Optional[pd.DataFrame] = None      # 原始排名数据
        self.cleaned_matches: Optional[pd.DataFrame] = None   # 清洗后比赛数据
        self.cleaned_rankings: Optional[pd.DataFrame] = None  # 清洗后排名数据
        self.teams_df: Optional[pd.DataFrame] = None          # 球队主表
        self.matches_df: Optional[pd.DataFrame] = None        # 合并后比赛表
        self.rankings_df: Optional[pd.DataFrame] = None       # 合并后排名表

    # =========================================================================
    # Phase 1: 获取 (Fetch)
    # =========================================================================

    def fetch_all(self, skip_existing: bool = True) -> dict:
        """
        获取所有 MVP 所需的数据。

        Args:
            skip_existing: 如果本地已有文件，是否跳过下载

        Returns:
            {source_id: 是否成功} 字典
        """
        logger.info("=" * 60)
        logger.info("Phase 1: 数据获取 (Fetch)")
        logger.info("=" * 60)

        results = {}

        fetchers = [
            create_kaggle_intl_matches_fetcher(str(self.data_dir)),
            create_kaggle_worldcup_fetcher(str(self.data_dir)),
            create_kaggle_fifa_rankings_fetcher(str(self.data_dir)),
        ]

        for fetcher in fetchers:
            if skip_existing and fetcher.local_path.exists():
                logger.info(f"跳过 (已存在): {fetcher.source_name}")
                results[fetcher.source_id] = True
                continue

            success = fetcher.fetch()
            results[fetcher.source_id] = success
            if success:
                logger.info(f"✓ 获取成功: {fetcher.source_name}")
            else:
                logger.error(f"✗ 获取失败: {fetcher.source_name}")

        return results

    # =========================================================================
    # Phase 2: 清洗与标准化 (Clean & Normalize)
    # =========================================================================

    def load_raw_data(self) -> dict:
        """加载原始 CSV 数据到内存"""
        logger.info("加载原始数据...")

        loaded = {}

        # 加载 kaggle_intl_matches
        path = self.raw_dir / "matches" / "kaggle_intl_matches.csv"
        if path.exists():
            self.raw_matches = pd.read_csv(path, low_memory=False)
            loaded["matches"] = len(self.raw_matches)
            logger.info(f"  比赛数据: {len(self.raw_matches)} 行")
        else:
            logger.warning(f"  比赛数据不存在: {path}")
            loaded["matches"] = 0

        # 加载 kaggle_fifa_rankings
        path = self.raw_dir / "rankings" / "kaggle_fifa_rankings.csv"
        if path.exists():
            self.raw_rankings = pd.read_csv(path, low_memory=False)
            loaded["rankings"] = len(self.raw_rankings)
            logger.info(f"  排名数据: {len(self.raw_rankings)} 行")
        else:
            logger.warning(f"  排名数据不存在: {path}")
            loaded["rankings"] = 0

        return loaded

    def clean_matches(self) -> QualityReport:
        """
        清洗比赛数据。

        处理步骤:
        1. 删除关键字段缺失的行
        2. 球队名标准化
        3. 日期格式统一
        4. 筛选世界杯相关比赛
        5. 删除无效比分 (负数、非整数)
        """
        logger.info("-" * 40)
        logger.info("清洗比赛数据...")

        if self.raw_matches is None:
            raise ValueError("请先调用 load_raw_data()")

        df = self.raw_matches.copy()

        # 1. 关键字段缺失处理
        critical_cols = ["date", "home_team", "away_team", "home_score", "away_score"]
        for col in critical_cols:
            if col in df.columns:
                before = len(df)
                df = df.dropna(subset=[col])
                logger.info(f"  删除 {col} 缺失: {before - len(df)} 行")

        # 2. 删除无效比分
        score_cols = ["home_score", "away_score"]
        for col in score_cols:
            if col in df.columns:
                # 确保数值类型
                df[col] = pd.to_numeric(df[col], errors="coerce")
                before = len(df)
                df = df.dropna(subset=[col])
                # 删除负分
                df = df[df[col] >= 0]
                logger.info(f"  清理 {col}: 删除 {before - len(df)} 行")

        # 3. 球队名标准化
        team_cols = ["home_team", "away_team"]
        df, unrecognized = self.qc.normalize_team_names(df, team_cols)
        if unrecognized:
            logger.warning(f"  未识别球队名: {unrecognized[:10]}")

        # 4. 日期格式统一
        df, date_issues = self.qc.normalize_dates(df, ["date"])
        logger.info(f"  日期格式问题: {date_issues} 行")

        # 5. 去重
        before = len(df)
        df = self.qc.remove_duplicates(
            df, subset=["date", "home_team", "away_team"]
        )
        logger.info(f"  去重: 删除 {before - len(df)} 行")

        self.cleaned_matches = df
        logger.info(f"  清洗后: {len(df)} 行")

        # 生成质量报告
        report = self.qc.run_quality_check(
            df,
            source_name="kaggle_intl_matches (清洗后)",
            team_columns=team_cols,
            date_columns=["date"],
        )
        logger.info(report.summary())

        return report

    def clean_rankings(self) -> QualityReport:
        """
        清洗 FIFA 排名数据。

        处理步骤:
        1. 列名映射
        2. 球队名标准化
        3. 日期格式统一
        4. 筛选最新排名
        """
        logger.info("-" * 40)
        logger.info("清洗排名数据...")

        if self.raw_rankings is None:
            raise ValueError("请先调用 load_raw_data()")

        df = self.raw_rankings.copy()

        # 球队名标准化 (kaggle_fifa_rankings 使用 country_full 和 country_abrv)
        # 优先使用 country_abrv (已经是 3 字母代码)
        if "country_abrv" in df.columns:
            df["team_id"] = df["country_abrv"]
        elif "country_full" in df.columns:
            df["team_id"] = df["country_full"].apply(self.normalizer.normalize)

        # 日期标准化
        if "rank_date" in df.columns:
            df, _ = self.qc.normalize_dates(df, ["rank_date"])

        # 去重：同一天同一队保留最新排名
        if "rank_date" in df.columns and "team_id" in df.columns:
            df = self.qc.remove_duplicates(df, subset=["rank_date", "team_id"])

        self.cleaned_rankings = df
        logger.info(f"  清洗后: {len(df)} 行")

        report = self.qc.run_quality_check(
            df,
            source_name="kaggle_fifa_rankings (清洗后)",
            team_columns=["team_id"] if "team_id" in df.columns else None,
            date_columns=["rank_date"] if "rank_date" in df.columns else None,
        )
        logger.info(report.summary())

        return report

    # =========================================================================
    # Phase 3: 合并 (Merge)
    # =========================================================================

    def build_teams_table(self) -> pd.DataFrame:
        """
        构建球队主表。

        从排名数据和比赛数据中提取所有出现过的唯一球队，
        合并 FIFA 排名和 ELO 评分信息。
        """
        logger.info("-" * 40)
        logger.info("构建球队主表...")

        if self.cleaned_matches is None or self.cleaned_rankings is None:
            raise ValueError("请先执行 clean_matches() 和 clean_rankings()")

        # 从比赛数据中提取所有球队
        home_teams = self.cleaned_matches["home_team"].unique()
        away_teams = self.cleaned_matches["away_team"].unique()
        all_teams = set(home_teams) | set(away_teams)

        # 从排名数据中获取最新排名
        if "rank_date" in self.cleaned_rankings.columns:
            latest_rankings = (
                self.cleaned_rankings
                .sort_values("rank_date")
                .groupby("team_id")
                .last()
                .reset_index()
            )
        else:
            latest_rankings = self.cleaned_rankings.copy()

        # 合并
        teams = pd.DataFrame({"team_id": sorted(all_teams)})

        # 关联排名信息
        rank_cols = ["team_id", "rank", "total_points", "confederation"]
        available_rank_cols = [c for c in rank_cols if c in latest_rankings.columns]
        teams = teams.merge(
            latest_rankings[available_rank_cols],
            on="team_id",
            how="left",
        )

        # 从排名数据补充 confederation
        if "confederation" not in teams.columns:
            if "confederation" in self.cleaned_rankings.columns:
                confed_map = (
                    self.cleaned_rankings
                    .groupby("team_id")["confederation"]
                    .first()
                    .to_dict()
                )
                teams["confederation"] = teams["team_id"].map(confed_map)

        self.teams_df = teams
        logger.info(f"  球队主表: {len(teams)} 支球队")
        logger.info(f"  有排名信息的: {teams['rank'].notna().sum()} 支")
        return teams

    def build_matches_table(self) -> pd.DataFrame:
        """
        构建统一比赛表。

        将 kaggle_intl_matches 和 kaggle_worldcup 合并，
        添加世界杯标注、stage 信息等。
        """
        logger.info("-" * 40)
        logger.info("构建比赛表...")

        if self.cleaned_matches is None:
            raise ValueError("请先执行 clean_matches()")

        df = self.cleaned_matches.copy()

        # 标注世界杯比赛
        if "tournament" in df.columns:
            df["is_worldcup"] = df["tournament"].str.contains(
                "FIFA World Cup", case=False, na=False
            ).astype(int)
            wc_count = df["is_worldcup"].sum()
            logger.info(f"  世界杯比赛: {wc_count} 场")

        # 添加结果编码
        if "home_score" in df.columns and "away_score" in df.columns:
            conditions = [
                df["home_score"] > df["away_score"],
                df["home_score"] == df["away_score"],
                df["home_score"] < df["away_score"],
            ]
            choices = ["H", "D", "A"]
            df["result"] = pd.Series(
                np.select(conditions, choices, default=None),
                index=df.index,
            )
            # 导入 numpy
            import numpy as np

        self.matches_df = df
        logger.info(f"  比赛表: {len(df)} 行")
        return df

    # =========================================================================
    # Phase 4: 存储 (Store)
    # =========================================================================

    def save_processed(self):
        """将处理后的数据保存到 processed/ 目录"""
        logger.info("-" * 40)
        logger.info("保存处理结果...")

        files = {
            "teams.csv": self.teams_df,
            "matches.csv": self.matches_df,
            "rankings.csv": self.cleaned_rankings,
        }

        for filename, df in files.items():
            if df is not None:
                path = self.processed_dir / "features" / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(path, index=False)
                logger.info(f"  ✓ {path} ({len(df)} 行)")

    def save_metadata(self):
        """保存数据处理元数据"""
        metadata = {
            "pipeline_version": "1.0.0",
            "processed_at": datetime.now().isoformat(),
            "teams_count": len(self.teams_df) if self.teams_df is not None else 0,
            "matches_count": len(self.matches_df) if self.matches_df is not None else 0,
            "rankings_count": len(self.cleaned_rankings) if self.cleaned_rankings is not None else 0,
            "data_sources_used": [
                "kaggle_intl_matches",
                "kaggle_fifa_rankings",
            ],
        }

        path = self.data_dir / "metadata" / "pipeline_metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"元数据保存到: {path}")

    # =========================================================================
    # 主入口
    # =========================================================================

    def run(self, fetch: bool = True, skip_existing: bool = True):
        """
        运行完整的数据处理流程。

        Args:
            fetch: 是否执行数据获取步骤
            skip_existing: 是否跳过已存在的文件
        """
        logger.info("=" * 60)
        logger.info("世界杯冠军预测 Agent — 数据采集与处理流程")
        logger.info("=" * 60)

        # Phase 1: 获取
        if fetch:
            results = self.fetch_all(skip_existing=skip_existing)
            failed = [k for k, v in results.items() if not v]
            if failed:
                logger.warning(f"以下数据源获取失败: {failed}")
                # 不中断流程，使用已有数据继续
        else:
            logger.info("跳过数据获取（使用已有文件）")

        # Phase 2: 加载原始数据
        loaded = self.load_raw_data()
        if loaded.get("matches", 0) == 0:
            logger.error("无比赛数据可用，流程终止")
            return

        # Phase 3: 清洗
        self.clean_matches()
        if self.cleaned_rankings is not None or (
            self.raw_rankings is not None and len(self.raw_rankings) > 0
        ):
            self.clean_rankings()
        else:
            logger.warning("无排名数据，跳过清洗")

        # Phase 4: 合并
        if self.cleaned_rankings is not None:
            self.build_teams_table()
        else:
            logger.warning("无排名数据，跳过球队表构建")
        self.build_matches_table()

        # Phase 5: 存储
        self.save_processed()
        self.save_metadata()

        logger.info("=" * 60)
        logger.info("数据采集与处理流程完成!")
        logger.info("=" * 60)


# =============================================================================
# 命令行入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="世界杯冠军预测 Agent 数据采集与处理流程"
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        default=True,
        help="执行数据获取步骤 (默认: True)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="跳过数据获取步骤（使用已有文件）",
    )
    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="强制重新下载所有数据（不跳过已存在文件）",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="数据根目录 (默认: data)",
    )

    args = parser.parse_args()

    should_fetch = args.fetch and not args.no_fetch
    skip_existing = not args.force_fetch

    pipeline = DataPipeline(data_dir=args.data_dir)
    pipeline.run(fetch=should_fetch, skip_existing=skip_existing)


if __name__ == "__main__":
    main()
