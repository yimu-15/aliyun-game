"""
运行完整数据处理流水线

用法:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --no-fetch
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_pipeline.pipeline import DataPipeline


def main():
    parser = argparse.ArgumentParser(description="运行数据处理流水线")
    parser.add_argument("--no-fetch", action="store_true", help="跳过数据获取")
    parser.add_argument("--force-fetch", action="store_true", help="强制重新下载")
    args = parser.parse_args()

    pipeline = DataPipeline(data_dir="data")
    pipeline.run(
        fetch=not args.no_fetch,
        skip_existing=not args.force_fetch,
    )


if __name__ == "__main__":
    main()
