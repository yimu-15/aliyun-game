"""
数据采集与处理模块

提供从真实数据源采集、清洗、标准化到存储的完整数据流水线。
"""

from .pipeline import DataPipeline
from .quality import DataQualityController, QualityReport
from .cleaners.name_normalizer import NameNormalizer
