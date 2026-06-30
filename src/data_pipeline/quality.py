"""
数据质量控制模块

处理流程:
1. 缺失值检测与处理
2. 重复值检测与去重
3. 异常值检测与处理
4. 国家名/球队名统一
5. 时间格式统一
6. 质量报告生成
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from .cleaners.name_normalizer import NameNormalizer

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """数据质量检测报告"""

    source_name: str
    total_rows: int
    total_columns: int
    missing_summary: Dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    outlier_summary: Dict[str, int] = field(default_factory=dict)
    unrecognized_names: List[str] = field(default_factory=list)
    date_format_issues: int = 0
    issues_found: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_clean(self) -> bool:
        """数据是否通过了所有质量检查"""
        return len(self.issues_found) == 0

    def summary(self) -> str:
        """生成可读的质量摘要"""
        lines = [
            "=" * 60,
            f"数据质量报告: {self.source_name}",
            f"生成时间: {self.timestamp}",
            f"数据规模: {self.total_rows} 行 × {self.total_columns} 列",
            "-" * 60,
        ]
        if self.missing_summary:
            lines.append("缺失值统计:")
            for col, count in self.missing_summary.items():
                pct = count / self.total_rows * 100 if self.total_rows else 0
                lines.append(f"  {col}: {count} ({pct:.1f}%)")
        if self.duplicate_rows:
            lines.append(f"重复行: {self.duplicate_rows}")
        if self.outlier_summary:
            lines.append("异常值统计:")
            for col, count in self.outlier_summary.items():
                lines.append(f"  {col}: {count}")
        if self.unrecognized_names:
            lines.append(
                f"未识别球队名 ({len(self.unrecognized_names)}): "
                f"{self.unrecognized_names[:10]}"
            )
        if self.date_format_issues:
            lines.append(f"日期格式问题: {self.date_format_issues} 行")
        lines.append("-" * 60)
        if self.issues_found:
            lines.append("发现的问题:")
            for issue in self.issues_found:
                lines.append(f"  - {issue}")
        else:
            lines.append("数据质量: 通过 ✓")
        lines.append("=" * 60)
        return "\n".join(lines)


class DataQualityController:
    """
    数据质量控制中心。

    处理流程:
    1. 缺失值 → 根据列类型采取不同策略
    2. 重复值 → 精确匹配去重 + 模糊匹配告警
    3. 异常值 → 3σ 原则 / IQR 原则
    4. 名称统一 → NameNormalizer
    5. 时间格式 → 统一为 ISO 8601
    6. 质量报告 → 输出 QualityReport
    """

    def __init__(
        self,
        normalizer: Optional[NameNormalizer] = None,
        outlier_method: str = "iqr",  # "iqr" 或 "zscore"
        outlier_threshold: float = 3.0,
    ):
        """
        Args:
            normalizer: 名称标准化器
            outlier_method: 异常值检测方法
            outlier_threshold: 异常值阈值 (IQR: 1.5, Z-Score: 3.0)
        """
        self.normalizer = normalizer or NameNormalizer()
        self.outlier_method = outlier_method
        self.outlier_threshold = outlier_threshold

    # =========================================================================
    # 1. 缺失值处理
    # =========================================================================

    def detect_missing(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        检测缺失值。

        Returns:
            {列名: 缺失数量} 字典
        """
        missing = df.isnull().sum()
        return missing[missing > 0].to_dict()

    def handle_missing(
        self,
        df: pd.DataFrame,
        strategy_map: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        处理缺失值。

        默认策略:
        - 数值型列 → 中位数填充
        - 类别型列 → 众数填充
        - 文本列 → 空字符串
        - 关键字段 (match_date, home_team, away_team) → 删除行

        Args:
            df: 输入数据框
            strategy_map: 自定义策略映射 {列名: 策略}
                          策略: "median", "mean", "mode", "drop", "zero", "ffill"

        Returns:
            处理后的数据框
        """
        strategy_map = strategy_map or {}
        df = df.copy()
        removed_count = 0

        # 关键字段：缺失则删除行
        critical_columns = {"date", "home_team", "away_team", "match_date"}
        for col in critical_columns.intersection(df.columns):
            before = len(df)
            df = df.dropna(subset=[col])
            removed = before - len(df)
            if removed:
                logger.info(f"关键字段 {col} 缺失，删除 {removed} 行")
                removed_count += removed

        # 其他字段：根据策略处理
        for col in df.columns:
            if col in critical_columns:
                continue
            if df[col].isnull().sum() == 0:
                continue

            strategy = strategy_map.get(col, "auto")

            if strategy == "auto":
                if pd.api.types.is_numeric_dtype(df[col]):
                    strategy = "median"
                else:
                    strategy = "mode"

            if strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            elif strategy == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val[0])
                else:
                    df[col] = df[col].fillna("")
            elif strategy == "zero":
                df[col] = df[col].fillna(0)
            elif strategy == "drop":
                df = df.dropna(subset=[col])
            elif strategy == "ffill":
                df[col] = df[col].ffill()

        logger.info(f"缺失值处理完成，删除 {removed_count} 行")
        return df

    # =========================================================================
    # 2. 重复值处理
    # =========================================================================

    def detect_duplicates(
        self, df: pd.DataFrame, subset: Optional[List[str]] = None
    ) -> Tuple[int, pd.DataFrame]:
        """
        检测重复行。

        Args:
            df: 输入数据框
            subset: 用于判断重复的列子集

        Returns:
            (重复行数, 重复行数据框)
        """
        duplicates = df[df.duplicated(subset=subset, keep=False)]
        return len(duplicates), duplicates

    def remove_duplicates(
        self,
        df: pd.DataFrame,
        subset: Optional[List[str]] = None,
        keep: str = "first",
    ) -> pd.DataFrame:
        """
        去除重复行。

        Args:
            df: 输入数据框
            subset: 用于判断重复的列子集
            keep: 保留策略 ("first", "last", False)

        Returns:
            去重后的数据框
        """
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep=keep)
        after = len(df)
        if before > after:
            logger.info(f"去重: 删除 {before - after} 行重复数据")
        return df

    # =========================================================================
    # 3. 异常值处理
    # =========================================================================

    def detect_outliers(
        self, df: pd.DataFrame, columns: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """
        检测数值型列的异常值。

        方法:
        - IQR: 超出 Q1 - 1.5*IQR 或 Q3 + 1.5*IQR
        - Z-Score: |z| > threshold

        Args:
            df: 输入数据框
            columns: 要检测的列（默认所有数值列）

        Returns:
            {列名: 异常值数量} 字典
        """
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        outliers = {}
        for col in columns:
            if col not in df.columns:
                continue
            series = df[col].dropna()

            if self.outlier_method == "iqr":
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - self.outlier_threshold * IQR
                upper = Q3 + self.outlier_threshold * IQR
                count = ((series < lower) | (series > upper)).sum()
            else:  # zscore
                z_scores = np.abs((series - series.mean()) / series.std())
                count = (z_scores > self.outlier_threshold).sum()

            if count > 0:
                outliers[col] = int(count)

        return outliers

    def handle_outliers(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        strategy: str = "cap",  # "cap", "median", "remove"
    ) -> pd.DataFrame:
        """
        处理异常值。

        策略:
        - "cap": 截断到上下界
        - "median": 替换为中位数
        - "remove": 删除包含异常值的行
        """
        df = df.copy()
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        for col in columns:
            if col not in df.columns:
                continue
            series = df[col].dropna()
            if len(series) == 0:
                continue

            if self.outlier_method == "iqr":
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - self.outlier_threshold * IQR
                upper = Q3 + self.outlier_threshold * IQR
            else:
                mean, std = series.mean(), series.std()
                lower = mean - self.outlier_threshold * std
                upper = mean + self.outlier_threshold * std

            if strategy == "cap":
                df[col] = df[col].clip(lower, upper)
            elif strategy == "median":
                mask = (df[col] < lower) | (df[col] > upper)
                df.loc[mask, col] = df[col].median()
            elif strategy == "remove":
                mask = (df[col] < lower) | (df[col] > upper)
                df = df[~mask]

        logger.info(f"异常值处理完成 (策略: {strategy})")
        return df

    # =========================================================================
    # 4. 球队名统一
    # =========================================================================

    def normalize_team_names(
        self,
        df: pd.DataFrame,
        team_columns: List[str],
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        将球队名称标准化为 FIFA 3 字母代码。

        Args:
            df: 输入数据框
            team_columns: 球队列名列表 (如 ["home_team", "away_team"])

        Returns:
            (处理后的数据框, 未识别的名称列表)
        """
        df = df.copy()
        all_unrecognized = []

        for col in team_columns:
            if col not in df.columns:
                continue

            # 记录标准化前的唯一值
            unique_before = set(df[col].dropna().unique())

            # 执行标准化
            df[col] = self.normalizer.normalize_series(df[col])

            # 找出未识别的名称
            unrecognized = unique_before - set(self.normalizer.mapping.keys())
            all_unrecognized.extend(unrecognized)

        if all_unrecognized:
            logger.warning(
                f"未识别的球队名 ({len(all_unrecognized)}): "
                f"{all_unrecognized[:20]}"
            )

        return df, list(set(all_unrecognized))

    # =========================================================================
    # 5. 时间格式统一
    # =========================================================================

    def normalize_dates(
        self, df: pd.DataFrame, date_columns: List[str]
    ) -> Tuple[pd.DataFrame, int]:
        """
        将日期列统一为 ISO 8601 格式 (YYYY-MM-DD)。

        Args:
            df: 输入数据框
            date_columns: 日期列名列表

        Returns:
            (处理后的数据框, 格式有问题的行数)
        """
        df = df.copy()
        issues = 0

        for col in date_columns:
            if col not in df.columns:
                continue
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                issues += parsed.isna().sum()
                df[col] = parsed.dt.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"日期列 {col} 解析失败: {e}")
                issues += len(df)

        if issues:
            logger.info(f"日期格式问题: {issues} 行")
        return df, issues

    # =========================================================================
    # 6. 综合质量报告
    # =========================================================================

    def run_quality_check(
        self,
        df: pd.DataFrame,
        source_name: str,
        team_columns: Optional[List[str]] = None,
        date_columns: Optional[List[str]] = None,
    ) -> QualityReport:
        """
        对数据执行完整的质量检查。

        Args:
            df: 输入数据框
            source_name: 数据源名称
            team_columns: 球队列名
            date_columns: 日期列名

        Returns:
            QualityReport 质量报告
        """
        report = QualityReport(
            source_name=source_name,
            total_rows=len(df),
            total_columns=len(df.columns),
        )

        # 缺失值
        report.missing_summary = self.detect_missing(df)
        if report.missing_summary:
            report.issues_found.append(
                f"缺失值: {len(report.missing_summary)} 列有缺失数据"
            )

        # 重复值
        report.duplicate_rows, _ = self.detect_duplicates(df)
        if report.duplicate_rows:
            report.issues_found.append(f"重复行: {report.duplicate_rows}")

        # 异常值
        report.outlier_summary = self.detect_outliers(df)
        if report.outlier_summary:
            report.issues_found.append(
                f"异常值: {len(report.outlier_summary)} 列有异常数据"
            )

        # 球队名
        if team_columns:
            _, unrecognized = self.normalize_team_names(df, team_columns)
            report.unrecognized_names = unrecognized
            if unrecognized:
                report.issues_found.append(
                    f"未识别球队名: {len(unrecognized)} 个"
                )

        # 日期格式
        if date_columns:
            _, date_issues = self.normalize_dates(df, date_columns)
            report.date_format_issues = date_issues
            if date_issues:
                report.issues_found.append(f"日期格式问题: {date_issues} 行")

        logger.info(f"质量检查完成: {source_name} - "
                     f"{'通过' if report.is_clean() else '发现问题'}")
        return report
