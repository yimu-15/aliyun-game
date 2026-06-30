"""
模型训练脚本 (占位 — 后续迭代实现)

MVP 阶段使用规则引擎 (五维度加权评分 + 泊松模型)，
不需要训练。此脚本为后续 XGBoost 训练预留。

用法:
    python scripts/train_model.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("模型训练 (v1.1 迭代实现)")
    logger.info("=" * 50)
    logger.info("MVP 阶段使用规则引擎，无需模型训练。")
    logger.info("后续版本将在此脚本中实现 XGBoost + SHAP 训练。")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
