"""通用辅助函数"""

from typing import Optional, Dict


def format_probability(prob: float, decimals: int = 2) -> str:
    """
    格式化概率为百分比字符串。

    Args:
        prob: 概率值 (0-1)
        decimals: 小数位数

    Returns:
        如 "18.50%"
    """
    return f"{prob * 100:.{decimals}f}%"


def format_percentage(value: float, decimals: int = 1) -> str:
    """格式化数值为百分比 (如 0.185 → '18.5%')"""
    return f"{value * 100:.{decimals}f}%"


def team_id_to_name(team_id: str, team_map: Optional[Dict[str, str]] = None) -> str:
    """
    FIFA 3 字母代码转中文名。

    Args:
        team_id: FIFA 3 字母代码 (如 BRA)
        team_map: 自定义映射表

    Returns:
        中文名称，未知则返回原代码
    """
    _DEFAULT_MAP = {
        "BRA": "巴西", "ARG": "阿根廷", "GER": "德国", "FRA": "法国",
        "ENG": "英格兰", "ESP": "西班牙", "ITA": "意大利", "NED": "荷兰",
        "POR": "葡萄牙", "BEL": "比利时", "CRO": "克罗地亚", "URU": "乌拉圭",
        "DEN": "丹麦", "MEX": "墨西哥", "SUI": "瑞士", "COL": "哥伦比亚",
        "SEN": "塞内加尔", "MAR": "摩洛哥", "JPN": "日本", "KOR": "韩国",
        "IRN": "伊朗", "AUS": "澳大利亚", "KSA": "沙特阿拉伯", "QAT": "卡塔尔",
        "ECU": "厄瓜多尔", "PER": "秘鲁", "CHI": "智利", "CAN": "加拿大",
        "USA": "美国", "WAL": "威尔士", "POL": "波兰", "SRB": "塞尔维亚",
        "SWE": "瑞典", "CZE": "捷克", "AUT": "奥地利", "UKR": "乌克兰",
        "TUR": "土耳其", "GRE": "希腊", "RUS": "俄罗斯", "NOR": "挪威",
        "CMR": "喀麦隆", "GHA": "加纳", "NGA": "尼日利亚", "TUN": "突尼斯",
        "ALG": "阿尔及利亚", "EGY": "埃及", "CRC": "哥斯达黎加",
        "NZL": "新西兰", "CHN": "中国",
    }
    mapping = team_map or _DEFAULT_MAP
    return mapping.get(team_id, team_id)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """将值钳制在 [min_val, max_val] 范围内"""
    return max(min_val, min(max_val, value))
