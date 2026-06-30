"""
数据获取脚本 — 从 Kaggle 下载真实数据集

用法:
    python scripts/fetch_data.py
    python scripts/fetch_data.py --force
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.logger import setup_logger
from src.data_pipeline.fetchers.kaggle_fetcher import (
    create_kaggle_intl_matches_fetcher,
    create_kaggle_worldcup_fetcher,
    create_kaggle_fifa_rankings_fetcher,
)

logger = setup_logger("fetch_data")


def main():
    parser = argparse.ArgumentParser(description="下载世界杯预测所需数据集")
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    args = parser.parse_args()

    skip_existing = not args.force

    logger.info("=" * 50)
    logger.info("开始获取数据集...")
    logger.info("=" * 50)

    fetchers = [
        create_kaggle_intl_matches_fetcher("data"),
        create_kaggle_worldcup_fetcher("data"),
        create_kaggle_fifa_rankings_fetcher("data"),
    ]

    for f in fetchers:
        if skip_existing and f.local_path.exists():
            logger.info(f"跳过 (已存在): {f.source_name}")
            continue
        if f.fetch():
            logger.info(f"✓ {f.source_name}")
        else:
            logger.error(f"✗ 下载失败: {f.source_name}")

    logger.info("=" * 50)
    logger.info("数据获取完成!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
