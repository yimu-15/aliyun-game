"""
球队名称标准化工具

不同数据源对同一国家的命名方式可能不同：
  - kaggle_intl_matches: "Brazil", "United States"
  - kaggle_fifa_rankings: "Brazil", "USA"
  - openfootball: "Brazil", "United States"

本模块负责将所有名称统一为标准的 FIFA 3 字母代码 (如 BRA, USA)。
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# 内置名称映射表
# 覆盖所有常见国家队名称变体 → FIFA 三字母代码
# 数据来源: FIFA 官方成员国列表 (https://www.fifa.com/en/member-associations)
# =============================================================================

_BUILTIN_NAME_MAPPING: Dict[str, str] = {
    # ———— 英文全名 → FIFA 代码 ————
    "Brazil": "BRA",
    "Argentina": "ARG",
    "Germany": "GER",
    "France": "FRA",
    "England": "ENG",
    "Spain": "ESP",
    "Italy": "ITA",
    "Netherlands": "NED",
    "Portugal": "POR",
    "Belgium": "BEL",
    "Croatia": "CRO",
    "Uruguay": "URU",
    "Denmark": "DEN",
    "Mexico": "MEX",
    "Switzerland": "SUI",
    "Colombia": "COL",
    "Senegal": "SEN",
    "Morocco": "MAR",
    "Japan": "JPN",
    "South Korea": "KOR",
    "Korea Republic": "KOR",
    "Iran": "IRN",
    "Australia": "AUS",
    "Saudi Arabia": "KSA",
    "Qatar": "QAT",
    "Ecuador": "ECU",
    "Peru": "PER",
    "Chile": "CHI",
    "Paraguay": "PAR",
    "Canada": "CAN",
    "United States": "USA",
    "USA": "USA",
    "Wales": "WAL",
    "Poland": "POL",
    "Serbia": "SRB",
    "Sweden": "SWE",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Austria": "AUT",
    "Hungary": "HUN",
    "Ukraine": "UKR",
    "Turkey": "TUR",
    "Greece": "GRE",
    "Russia": "RUS",
    "Norway": "NOR",
    "Scotland": "SCO",
    "Republic of Ireland": "IRL",
    "Ireland": "IRL",
    "Slovakia": "SVK",
    "Romania": "ROU",
    "Bulgaria": "BUL",
    "Finland": "FIN",
    "Iceland": "ISL",
    "Slovenia": "SVN",
    "Bosnia and Herzegovina": "BIH",
    "Montenegro": "MNE",
    "North Macedonia": "MKD",
    "Albania": "ALB",
    "Georgia": "GEO",
    "Israel": "ISR",
    "Northern Ireland": "NIR",
    "Cameroon": "CMR",
    "Ghana": "GHA",
    "Nigeria": "NGA",
    "Egypt": "EGY",
    "Tunisia": "TUN",
    "Algeria": "ALG",
    "Ivory Coast": "CIV",
    "Côte d'Ivoire": "CIV",
    "South Africa": "RSA",
    "Mali": "MLI",
    "Burkina Faso": "BFA",
    "Costa Rica": "CRC",
    "Panama": "PAN",
    "Jamaica": "JAM",
    "Honduras": "HON",
    "New Zealand": "NZL",
    "China": "CHN",
    "United Arab Emirates": "UAE",
    "Kuwait": "KUW",
    "Iraq": "IRQ",
    "Syria": "SYR",
    "Uzbekistan": "UZB",
    "Bahrain": "BHR",
    "Oman": "OMA",
    "Jordan": "JOR",
    "Lebanon": "LBN",
    "Thailand": "THA",
    "Vietnam": "VIE",
    "Venezuela": "VEN",
    "Bolivia": "BOL",
    # ———— 缩写/常见变体 → FIFA 代码 ————
    "GRE": "GRE",
    "CRO": "CRO",
    "GER": "GER",
    "FRA": "FRA",
    "POR": "POR",
    "ENG": "ENG",
    "POL": "POL",
    "DEN": "DEN",
    "BEL": "BEL",
    "WAL": "WAL",
    "ESP": "ESP",
    "RUS": "RUS",
    "SWE": "SWE",
    "CZE": "CZE",
    "SUI": "SUI",
    "TUR": "TUR",
    "ITA": "ITA",
    "AUT": "AUT",
    "SRB": "SRB",
    "NED": "NED",
    "UKR": "UKR",
    "ECU": "ECU",
    "URU": "URU",
    "COL": "COL",
    "PER": "PER",
    "CHI": "CHI",
    "ARG": "ARG",
    "BRA": "BRA",
    "CMR": "CMR",
    "AUS": "AUS",
    "JPN": "JPN",
    "KSA": "KSA",
    "KOR": "KOR",
    "QAT": "QAT",
    "IRN": "IRN",
    "CRC": "CRC",
    "GHA": "GHA",
    "MAR": "MAR",
    "TUN": "TUN",
    "SEN": "SEN",
    "MEX": "MEX",
    "CAN": "CAN",
    "USA": "USA",
    "NZL": "NZL",
    "ALG": "ALG",
    "UAE": "UAE",
    "VEN": "VEN",
    "BOL": "BOL",
    "PAR": "PAR",
    "HUN": "HUN",
    "HON": "HON",
    "JAM": "JAM",
    "PAN": "PAN",
    "EGY": "EGY",
    "NGA": "NGA",
    "RSA": "RSA",
    "CHN": "CHN",
}


class NameNormalizer:
    """
    球队名称标准化器。

    使用方法:
        normalizer = NameNormalizer()
        code = normalizer.normalize("United States")  # → "USA"
        code = normalizer.normalize("Korea Republic")  # → "KOR"
    """

    def __init__(self, custom_mapping_path: Optional[str] = None):
        """
        Args:
            custom_mapping_path: 自定义名称映射 JSON 文件路径（可选）
        """
        self.mapping: Dict[str, str] = dict(_BUILTIN_NAME_MAPPING)

        # 加载自定义映射（如存在）
        if custom_mapping_path:
            self._load_custom_mapping(custom_mapping_path)

    def _load_custom_mapping(self, path: str):
        """加载自定义名称映射"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                custom = json.load(f)
            self.mapping.update(custom)
            logger.info(f"已加载自定义名称映射: {path} ({len(custom)} 条)")
        except Exception as e:
            logger.warning(f"加载自定义映射失败: {e}")

    def normalize(self, name: str) -> str:
        """
        将球队名称标准化为 FIFA 3 字母代码。

        Args:
            name: 原始球队名称（任意格式）

        Returns:
            FIFA 3 字母代码，如无法识别则返回原始名称
        """
        if not name or not isinstance(name, str):
            return ""

        # 清理输入
        cleaned = name.strip()

        # 直接匹配
        if cleaned in self.mapping:
            return self.mapping[cleaned]

        # 尝试 title case 匹配
        title_case = cleaned.title()
        if title_case in self.mapping:
            return self.mapping[title_case]

        # 无法识别
        logger.debug(f"无法识别的球队名: '{name}'")
        return cleaned

    def normalize_series(self, names):
        """批量标准化 Pandas Series"""
        return names.apply(self.normalize)

    def get_unrecognized(self, names) -> set:
        """返回无法识别的名称集合，用于发现需要补充的映射"""
        unique = set(names.dropna().unique())
        return {n for n in unique if n not in self.mapping}

    def save_mapping(self, path: str):
        """保存当前映射表到文件（用于审查和补充）"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                dict(sorted(self.mapping.items())),
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"映射表已保存到: {path}")
