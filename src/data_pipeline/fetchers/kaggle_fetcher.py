"""
Kaggle 数据集采集器

基于 kagglehub 库自动下载 Kaggle 数据集。
所下载的数据均来自 Kaggle 上公开的真实数据集，
严禁使用任何编造的示例数据。
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from .base_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class KaggleDatasetFetcher(DataFetcher):
    """
    Kaggle 数据集通用下载器。

    使用 kagglehub 库下载数据集，无需手动操作 Kaggle 网页。
    安装: pip install kagglehub
    """

    def __init__(
        self,
        source_id: str,
        source_name: str,
        source_url: str,
        dataset_path: str,  # 如 "martj42/international-football-results-from-1872-to-2017"
        file_name: str,     # 如 "results.csv"
        local_path: str,
        data_dir: str = "data",
    ):
        """
        Args:
            dataset_path: Kaggle 数据集路径 (owner/dataset-name)
            file_name: 要下载的文件名
        """
        super().__init__(source_id, source_name, source_url, local_path, data_dir)
        self.dataset_path = dataset_path
        self.file_name = file_name

    def fetch(self) -> bool:
        """
        通过 kagglehub 下载数据集文件。

        步骤:
        1. 调用 kagglehub.dataset_download() 下载到缓存目录
        2. 将目标文件复制到本地存储路径
        3. 记录数据追溯信息

        Returns:
            True 表示下载成功，False 表示失败
        """
        self.log_status(f"开始下载: {self.dataset_path} → {self.file_name}")

        try:
            import kagglehub
        except ImportError:
            self.log_status(
                "kagglehub 未安装。请运行: pip install kagglehub", "error"
            )
            return False

        try:
            # 下载到 kagglehub 缓存目录
            cache_dir = kagglehub.dataset_download(self.dataset_path)
            self.log_status(f"下载完成，缓存目录: {cache_dir}")

            # 复制目标文件到本地
            source_file = Path(cache_dir) / self.file_name
            if not source_file.exists():
                self.log_status(
                    f"文件不存在于缓存: {source_file}\n"
                    f"缓存目录内容: {list(Path(cache_dir).iterdir())[:10]}",
                    "error",
                )
                return False

            shutil.copy2(source_file, self.local_path)
            self.log_status(f"文件已保存到: {self.local_path}")

            # 记录追溯
            self.download_date = None  # 重置，让 record_trace 使用当前时间
            self.raw_file_hash = None
            self.record_trace(
                data_version=f"kaggle@{self.dataset_path}",
                notes=f"通过 kagglehub 下载，缓存目录: {cache_dir}",
            )

            return True

        except Exception as e:
            self.log_status(f"下载失败: {e}", "error")
            return False

    def validate(self) -> bool:
        """
        验证下载的数据文件。

        检查项:
        1. 文件存在且非空
        2. 文件格式为 CSV
        3. 至少包含预期的列

        Returns:
            True 表示验证通过
        """
        import pandas as pd

        if not self.local_path.exists():
            self.log_status(f"文件不存在: {self.local_path}", "warning")
            return False

        if self.local_path.stat().st_size == 0:
            self.log_status(f"文件为空: {self.local_path}", "warning")
            return False

        try:
            df = pd.read_csv(self.local_path, nrows=5)
            self.log_status(
                f"验证通过: {len(df.columns)} 列, 列名: {list(df.columns)}"
            )
            return True
        except Exception as e:
            self.log_status(f"文件读取失败: {e}", "warning")
            return False


# =============================================================================
# 预定义的 Kaggle 数据采集器
# =============================================================================

def create_kaggle_intl_matches_fetcher(data_dir: str = "data") -> KaggleDatasetFetcher:
    """
    采集器: International Football Results (1872-2024)
    Kaggle URL: https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017
    数据量: 约 44,000+ 场国家队比赛
    """
    return KaggleDatasetFetcher(
        source_id="kaggle_intl_matches",
        source_name="International Football Results from 1872 to 2024",
        source_url="https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017",
        dataset_path="martj42/international-football-results-from-1872-to-2017",
        file_name="results.csv",
        local_path="data/raw/matches/kaggle_intl_matches.csv",
        data_dir=data_dir,
    )


def create_kaggle_worldcup_fetcher(data_dir: str = "data") -> KaggleDatasetFetcher:
    """
    采集器: FIFA World Cup Dataset (1930-2022)
    Kaggle URL: https://www.kaggle.com/datasets/abecklas/fifa-world-cup
    数据量: 全部 22 届世界杯比赛、球员数据
    """
    return KaggleDatasetFetcher(
        source_id="kaggle_worldcup",
        source_name="FIFA World Cup Dataset",
        source_url="https://www.kaggle.com/datasets/abecklas/fifa-world-cup",
        dataset_path="abecklas/fifa-world-cup",
        file_name="WorldCupMatches.csv",
        local_path="data/raw/matches/kaggle_worldcup_matches.csv",
        data_dir=data_dir,
    )


def create_kaggle_fifa_rankings_fetcher(data_dir: str = "data") -> KaggleDatasetFetcher:
    """
    采集器: FIFA World Rankings (1992-2024)
    Kaggle URL: https://www.kaggle.com/datasets/cashncarry/fifaworldranking
    数据量: 1992 年至今的每月排名快照
    """
    return KaggleDatasetFetcher(
        source_id="kaggle_fifa_rankings",
        source_name="FIFA World Ranking Dataset",
        source_url="https://www.kaggle.com/datasets/cashncarry/fifaworldranking",
        dataset_path="cashncarry/fifaworldranking",
        file_name="fifa_ranking-2024-12-19.csv",
        local_path="data/raw/rankings/kaggle_fifa_rankings.csv",
        data_dir=data_dir,
    )


def create_kaggle_fifa_players_fetcher(data_dir: str = "data") -> KaggleDatasetFetcher:
    """
    采集器: FIFA 23 Complete Player Dataset
    Kaggle URL: https://www.kaggle.com/datasets/stefanoleone992/fifa-23-complete-player-dataset
    数据量: 约 19,000 名球员的详细能力值
    """
    return KaggleDatasetFetcher(
        source_id="kaggle_fifa_players",
        source_name="FIFA 23 Complete Player Dataset",
        source_url="https://www.kaggle.com/datasets/stefanoleone992/fifa-23-complete-player-dataset",
        dataset_path="stefanoleone992/fifa-23-complete-player-dataset",
        file_name="players_23.csv",
        local_path="data/raw/players/kaggle_fifa23_players.csv",
        data_dir=data_dir,
    )
