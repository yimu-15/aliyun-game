"""
数据采集器模块

支持的数据源:
- Kaggle 数据集 (通过 kagglehub)
- 本地 CSV 文件
- 手动导入数据
"""

from .base_fetcher import DataFetcher
from .kaggle_fetcher import (
    KaggleDatasetFetcher,
    create_kaggle_intl_matches_fetcher,
    create_kaggle_worldcup_fetcher,
    create_kaggle_fifa_rankings_fetcher,
    create_kaggle_fifa_players_fetcher,
)
