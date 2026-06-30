"""
数据采集器基类

所有数据采集器必须继承此基类，确保：
1. 统一的日志记录
2. 数据来源追溯
3. 原始数据哈希校验
"""

import hashlib
import logging
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class DataFetcher(ABC):
    """数据采集器抽象基类"""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        source_url: str,
        local_path: str,
        data_dir: str = "data",
    ):
        """
        Args:
            source_id: 数据源唯一标识 (对应 data_sources.yaml 中的 id)
            source_name: 数据源名称
            source_url: 数据源 URL
            local_path: 本地存储路径 (相对于 data_dir)
            data_dir: 数据根目录
        """
        self.source_id = source_id
        self.source_name = source_name
        self.source_url = source_url
        self.local_path = Path(data_dir) / local_path
        self.data_dir = Path(data_dir)
        self.download_date: Optional[str] = None
        self.raw_file_hash: Optional[str] = None

        # 确保父目录存在
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def fetch(self) -> bool:
        """
        执行数据采集。

        Returns:
            True 表示采集成功，False 表示失败
        """
        ...

    @abstractmethod
    def validate(self) -> bool:
        """
        验证已下载数据的完整性和正确性。

        Returns:
            True 表示数据有效，False 表示无效
        """
        ...

    def compute_hash(self, file_path: Optional[Path] = None) -> str:
        """计算文件的 SHA256 哈希值，用于数据版本追溯"""
        target = file_path or self.local_path
        if not target.exists():
            logger.warning(f"文件不存在，无法计算哈希: {target}")
            return ""
        sha256 = hashlib.sha256()
        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def record_trace(
        self,
        data_version: str = "",
        notes: str = "",
    ) -> dict:
        """
        记录数据来源追溯信息。

        Returns:
            追溯信息字典，可存入 source_trace 表
        """
        self.download_date = self.download_date or datetime.now().isoformat()
        self.raw_file_hash = self.raw_file_hash or self.compute_hash()

        trace = {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_file": str(self.local_path),
            "download_date": self.download_date,
            "data_version": data_version,
            "raw_file_hash": self.raw_file_hash,
            "notes": notes,
        }

        # 写入本地追溯文件
        trace_dir = self.data_dir / "sources"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / f"{self.source_id}_trace.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

        logger.info(f"数据追溯记录已保存: {trace_file}")
        return trace

    def log_status(self, message: str, level: str = "info"):
        """统一日志记录"""
        prefix = f"[{self.source_id}]"
        getattr(logger, level)(f"{prefix} {message}")
