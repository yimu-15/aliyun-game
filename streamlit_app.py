"""
Streamlit Cloud 入口文件

Streamlit Cloud 会自动查找根目录的 streamlit_app.py 作为入口。
此文件是 app/main.py 的代理，确保云端能正确加载项目。

部署方式:
  1. 推送到 GitHub: git push origin main
  2. 在 https://share.streamlit.io 选择此仓库
  3. 入口文件: streamlit_app.py
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 委托给真正的 Streamlit 应用
from app.main import *
