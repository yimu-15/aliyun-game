# 世界杯冠军预测 Agent — 功能总览与 CLI 参考手册

---

## 一、功能总览

```
世界杯冠军预测 Agent
│
├── 📊 数据采集与处理
│   ├── 1.1 下载 Kaggle 真实数据集
│   ├── 1.2 克隆 FootballData 开源仓库
│   ├── 1.3 多源数据融合清洗
│   └── 1.4 数据质量检查
│
├── 🧠 预测引擎
│   ├── 2.1 球队五维度评分
│   ├── 2.2 泊松单场预测
│   ├── 2.3 小组赛模拟
│   ├── 2.4 淘汰赛三阶段模拟
│   ├── 2.5 蒙特卡洛冠军预测
│   └── 2.6 因子归因可解释分析
│
├── 🖥️ 可视化页面
│   ├── 3.1 首页概览 (夺冠排行 + 指标)
│   ├── 3.2 球队实力榜 (评分 + 雷达图)
│   ├── 3.3 赛程对阵树 (交互式)
│   ├── 3.4 比分预测 (瀑布图归因)
│   └── 3.5 预测报告 (下载)
│
├── 🔌 API 服务
│   ├── 4.1 冠军排行 API
│   ├── 4.2 赛程树 API
│   └── 4.3 单场预测 API
│
├── 📋 答辩与文档
│   ├── 5.1 生成可视化素材
│   ├── 5.2 生成路演 PPT
│   ├── 5.3 生成 Markdown 报告
│   └── 5.4 快速演示
│
└── 🐳 部署
    ├── 6.1 Docker 构建
    ├── 6.2 docker-compose 启动
    └── 6.3 阿里云一键部署
```

---

## 二、功能分类与终端命令

### 📊 第一类: 数据采集与处理

#### 1.1 下载 Kaggle 真实数据集

| 项目 | 说明 |
|------|------|
| **功能** | 从 Kaggle 下载 International Football Results + FIFA Rankings |
| **脚本** | `scripts/fetch_data.py` |
| **命令** | `python scripts/fetch_data.py` |
| **命令 (强制)** | `python scripts/fetch_data.py --force` |
| **输入** | 无 (自动调用 kagglehub API) |
| **输出** | `data/raw/matches/kaggle_intl_matches.csv` (3.6MB) |
|  | `data/raw/rankings/kaggle_fifa_rankings.csv` (1.7MB) |
| **验证** | `ls data/raw/matches/kaggle_intl_matches.csv` |

#### 1.2 克隆 FootballData 开源仓库

| 项目 | 说明 |
|------|------|
| **功能** | 从 GitCode 克隆 FootballData 仓库 (4403 文件) |
| **命令** | `git clone --depth 1 https://gitcode.com/gh_mirrors/fo/FootballData data/external/FootballData` |
| **输入** | 无 |
| **输出** | `data/external/FootballData/` (含 17 届世界杯数据) |
| **验证** | `ls data/external/FootballData/World\ Cups/world-cup-2014/group_matches.csv` |

#### 1.3 多源数据融合清洗

| 项目 | 说明 |
|------|------|
| **功能** | 解析 FootballData CSV + Kaggle 数据，合并为统一数据集 |
| **脚本** | `scripts/collect_real_data.py` |
| **命令** | `python scripts/collect_real_data.py` |
| **命令 (含下载)** | `python scripts/collect_real_data.py --fetch` |
| **输入** | `data/raw/` + `data/external/FootballData/` |
| **输出** | `data/processed/matches.csv` (10,567 场, 835KB) |
|  | `data/processed/rankings.csv` (64,757 条, 3MB) |
|  | `data/processed/teams.csv` (232 队, 15KB) |
|  | `data/metadata/collection_report.json` |
| **验证** | `python -c "import pandas as pd; print(len(pd.read_csv('data/processed/matches.csv')))"` → 应 > 10000 |

#### 1.4 运行完整数据处理流水线

| 项目 | 说明 |
|------|------|
| **功能** | 一键运行数据获取 → 清洗 → 标准化 → 存储 (旧版) |
| **脚本** | `scripts/run_pipeline.py` |
| **命令** | `python scripts/run_pipeline.py` |
| **命令 (跳过获取)** | `python scripts/run_pipeline.py --no-fetch` |

---

### 🧠 第二类: 预测引擎

#### 2.1 球队五维度评分

| 项目 | 说明 |
|------|------|
| **功能** | 计算球队综合评分 (历史+排名+攻防+球员+状态) |
| **模块** | `models/team_rating.py` |
| **命令** | `python models/team_rating.py` (自测) |
| **输入** | dict 快照 `{"team_id":"BRA","wc_titles":5,"fifa_rank":5,...}` |
| **输出** | `TeamRating(overall, historical, strength, attack_defense, player_quality, recent_form)` |
| **验证** | 输出应显示 "巴西: 42.7 分" 等 |

#### 2.2 泊松单场预测

| 项目 | 说明 |
|------|------|
| **功能** | 基于独立泊松分布预测 P(胜)/P(平)/P(负) |
| **模块** | `models/group_stage.py` |
| **命令** | `python models/group_stage.py` (自测) |
| **输入** | 两个 TeamRating 对象 |
| **输出** | `MatchPrediction(p_home_win, p_draw, p_away_win, lam_home, lam_away, best_score)` |
| **验证** | 应输出 "BRA vs ARG: P(胜)=36.9% P(平)=26.2% P(负)=36.9%" |

#### 2.3 小组赛模拟

| 项目 | 说明 |
|------|------|
| **功能** | 模拟一个小组的完整赛程，输出积分榜和出线队 |
| **模块** | `models/group_stage.py` (simulate_group) |
| **输入** | List[TeamRating] + 组名 + 东道主列表 |
| **输出** | `{"group": "A组", "standings": [{team_id,pts,gf,ga,gd,rank}], "qualified": [top2]}` |

#### 2.4 淘汰赛三阶段模拟

| 项目 | 说明 |
|------|------|
| **功能** | 模拟一场淘汰赛 (90min → 加时×0.33 → 点球55%) |
| **模块** | `models/knockout.py` |
| **命令** | `python models/knockout.py` (自测) |
| **输入** | 两个 TeamRating + RandomState |
| **输出** | 胜者 team_id (字符串) |
| **验证** | 应输出晋级概率和1000次模拟统计 |

#### 2.5 蒙特卡洛冠军预测 (CLI 主入口)

| 项目 | 说明 |
|------|------|
| **功能** | 完整端到端冠军预测 (数据加载→评分→模拟→输出) |
| **脚本** | `main.py` |
| **命令** | `python main.py --teams 8 --sim 5000` |
| **命令 (32队)** | `python main.py --teams 32 --sim 10000` |
| **命令 (自定义输出)** | `python main.py --teams 16 --sim 5000 --output results.json --seed 123` |
| **命令 (使用真实数据)** | `python main.py --teams 32 --sim 10000 --real-data` |
| **输入** | 参数: `--teams`, `--sim`, `--seed`, `--output`, `--real-data` |
| **输出** | `data/processed/champion_prediction.json` (JSON 完整结果) |
| **验证** | 终端输出夺冠排行榜 + `ls data/processed/champion_prediction.json` |

#### 2.6 因子归因可解释分析

| 项目 | 说明 |
|------|------|
| **功能** | 单特征消融法分析胜负因子贡献度 |
| **模块** | `models/explainer.py` |
| **输入** | 两个 TeamRating 对象 |
| **输出** | `{match, prediction, top_factors: [{factor, impact, direction}]}` |

---

### 🖥️ 第三类: 可视化页面 (Streamlit)

#### 3.x 启动全部可视化页面

| 项目 | 说明 |
|------|------|
| **功能** | 启动 5 页面的 Streamlit 交互式前端 |
| **命令** | `streamlit run app/main.py` |
| **访问** | http://localhost:8501 |
| **输入** | 侧边栏参数 (球队数/模拟次数/权重/种子/赛制) |
| **输出** | 交互式 Web 页面 (5 个页面) |
| **验证** | 浏览器打开 localhost:8501，应显示夺冠卡片 + 赛程树 |

**5 个页面:**

| 页面 | 路由 | 功能 |
|------|------|------|
| 首页概览 | `🏠 首页概览` | 冠军卡片 + 数据概览 + 推理面板 |
| 球队实力榜 | `📊 球队实力榜` | 评分排行 + 雷达对比 + 小组赛预测 |
| 赛程对阵树 | `🌳 赛程对阵树` | Plotly 交互式对阵树 + 热度图 |
| 比分预测 | `🔍 比分预测` | 胜平负概率 + 瀑布图因子归因 + 计算过程 |
| 预测报告 | `📋 预测报告` | Markdown 预览 + 下载 JSON/CSV/MD |

---

### 🔌 第四类: API 服务

| 项目 | 说明 |
|------|------|
| **功能** | 启动 FastAPI 后端服务 |
| **命令** | `python backend/main.py` |
| **访问** | http://localhost:8000/docs (Swagger) |
| **端点** | `GET /api/health` |
|  | `GET /api/prediction/champion` |
|  | `GET /api/prediction/bracket` |
|  | `GET /api/prediction/match/{team_a}/{team_b}` |
| **验证** | `curl http://localhost:8000/api/health` → `{"status":"ok"}` |

---

### 📋 第五类: 答辩与文档

#### 5.1 生成可视化素材

| 项目 | 说明 |
|------|------|
| **功能** | 生成 6 张 PNG 图表 (架构/数据流/预测/排行/赛程/雷达) |
| **脚本** | `scripts/generate_assets.py` |
| **命令** | `python scripts/generate_assets.py` |
| **输出** | `docs/assets/*.png` (6 个文件) |
| **验证** | `ls docs/assets/` → 6 个 PNG 文件 |

#### 5.2 生成路演 PPT

| 项目 | 说明 |
|------|------|
| **功能** | 生成 13 页专业答辩 PPT (含真实图表) |
| **脚本** | `scripts/generate_pro_ppt.py` |
| **命令** | `python scripts/generate_pro_ppt.py` |
| **输出** | `docs/presentation/世界杯冠军预测Agent_路演.pptx` (686KB) |
| **验证** | `ls docs/presentation/世界杯冠军预测Agent_路演.pptx` → 文件存在 |
| **打开** | 用 PowerPoint / WPS / Google Slides 打开 |

#### 5.3 生成基础 PPT (旧版)

| 项目 | 说明 |
|------|------|
| **脚本** | `scripts/generate_ppt.py` |
| **命令** | `python scripts/generate_ppt.py` |
| **输出** | `docs/presentation/世界杯冠军预测Agent_答辩.pptx` (48KB) |

#### 5.4 快速演示 (无需数据)

| 项目 | 说明 |
|------|------|
| **功能** | 用内置数据演示评分和预测功能 |
| **脚本** | `scripts/run_demo.py` |
| **命令** | `python scripts/run_demo.py` |
| **输出** | 终端打印评分 + 预测 + 晋级概率 |
| **验证** | 应输出 "巴西: 42.7 分" "巴西 vs 阿根廷: 胜 36.9%" 等 |

---

### 🐳 第六类: 部署

| 项目 | 说明 |
|------|------|
| **功能** | 构建 Docker 镜像 |
| **命令** | `docker build -t worldcup-predictor .` |
| **功能** | docker-compose 一键启动 |
| **命令** | `docker-compose up -d` |
| **功能** | 阿里云 ECS 一键部署 |
| **命令** | `bash scripts/deploy_aliyun.sh` |
| **验证** | `curl http://localhost:8501/_stcore/health` |

---

## 三、终端执行总流程

### 快速体验 (2 分钟, 无需数据下载)

```bash
# Step 1: 激活环境
conda activate aliyun-game
cd D:/aliyun-game

# Step 2: 快速演示
python scripts/run_demo.py

# Step 3: 启动可视化
streamlit run app/main.py
# → 浏览器打开 http://localhost:8501
```

### 完整流程 (首次使用, 约 10 分钟)

```bash
conda activate aliyun-game
cd D:/aliyun-game

# ── 第一关: 数据 ──
# 1. 克隆 FootballData 仓库
git clone --depth 1 https://gitcode.com/gh_mirrors/fo/FootballData data/external/FootballData

# 2. 下载 Kaggle 数据集
python scripts/fetch_data.py

# 3. 数据融合清洗
python scripts/collect_real_data.py

# 验证数据
python -c "import pandas as pd; m=pd.read_csv('data/processed/matches.csv'); print(f'比赛:{len(m)} 排名:{len(pd.read_csv(\"data/processed/rankings.csv\"))} 球队:{len(pd.read_csv(\"data/processed/teams.csv\"))}')"

# ── 第二关: 预测 ──
# 4. CLI 冠军预测
python main.py --teams 32 --sim 10000

# 验证结果
python -c "import json; d=json.load(open('data/processed/champion_prediction.json','r',encoding='utf-8')); print(d['rankings'][0]['team_name'], d['rankings'][0]['champion_prob_pct'])"

# ── 第三关: 展示 ──
# 5. 启动前端
streamlit run app/main.py

# 6. 启动后端 (另一个终端)
python backend/main.py

# ── 第四关: 答辩 ──
# 7. 生成素材
python scripts/generate_assets.py

# 8. 生成 PPT
python scripts/generate_pro_ppt.py
```

---

## 四、功能-命令-文件-输出对照表

| # | 功能 | CLI 命令 | 入口文件 | 输出文件 | 验证方法 |
|---|------|----------|----------|----------|----------|
| 1 | 下载 Kaggle 数据 | `python scripts/fetch_data.py` | `scripts/fetch_data.py` | `data/raw/matches/kaggle_intl_matches.csv` | `ls -lh data/raw/matches/` |
| 2 | 克隆 FootballData | `git clone ...` (手动) | — | `data/external/FootballData/` | `ls data/external/FootballData/World\ Cups/` |
| 3 | 数据融合清洗 | `python scripts/collect_real_data.py` | `scripts/collect_real_data.py` | `data/processed/{matches,rankings,teams}.csv` | 终端输出 "质量: PASS" |
| 4 | 冠军预测 (CLI) | `python main.py --teams 32 --sim 10000` | `main.py` | `data/processed/champion_prediction.json` | 终端输出夺冠排行榜 |
| 5 | 冠军预测 (真实数据) | `python main.py --teams 32 --sim 10000 --real-data` | `main.py` | 同上 | 同上 |
| 6 | 快速演示 | `python scripts/run_demo.py` | `scripts/run_demo.py` | 终端输出 | 输出 "巴西: 42.7 分" |
| 7 | 启动 Streamlit | `streamlit run app/main.py` | `app/main.py` | Web 页面 | 浏览器访问 localhost:8501 |
| 8 | 启动 FastAPI | `python backend/main.py` | `backend/main.py` | REST API | `curl localhost:8000/api/health` |
| 9 | 生成可视化素材 | `python scripts/generate_assets.py` | `scripts/generate_assets.py` | `docs/assets/*.png` (6个) | `ls docs/assets/` |
| 10 | 生成路演 PPT | `python scripts/generate_pro_ppt.py` | `scripts/generate_pro_ppt.py` | `docs/presentation/世界杯冠军预测Agent_路演.pptx` | `ls -lh docs/presentation/` |
| 11 | 生成基础 PPT | `python scripts/generate_ppt.py` | `scripts/generate_ppt.py` | `docs/presentation/世界杯冠军预测Agent_答辩.pptx` | 同上 |
| 12 | Docker 部署 | `docker-compose up -d` | `docker-compose.yml` | 运行的容器 | `docker-compose ps` |
| 13 | 阿里云部署 | `bash scripts/deploy_aliyun.sh` | `scripts/deploy_aliyun.sh` | 远程 ECS 服务 | `curl http://<IP>:8501` |
| 14 | 数据流水线 (旧版) | `python scripts/run_pipeline.py` | `scripts/run_pipeline.py` | `data/processed/features/` | 终端日志 |
| 15 | 模型训练 (占位) | `python scripts/train_model.py` | `scripts/train_model.py` | 终端输出 | 提示 "v1.1 迭代实现" |

---

## 五、缺失 CLI 入口补充建议

### 当前缺失的 CLI 入口

以下功能目前只能在 Streamlit 中交互使用，缺少独立 CLI:

| 功能 | 当前状态 | 建议 CLI |
|------|----------|----------|
| 单场预测 | 仅 Streamlit / API | `python scripts/predict_match.py BRA ARG` |
| 淘汰赛晋级概率 | 仅 API | `python scripts/knockout_prob.py BRA ARG` |
| 数据质量报告 | 内嵌于 collect_real_data | `python scripts/check_data_quality.py` |
| Streamlit 无头导出 | 不支持 | `python scripts/export_screenshots.py` |

### 建议补充的 CLI 脚本

**1. 单场预测 CLI** (`scripts/predict_match.py`)

```bash
# 用法
python scripts/predict_match.py BRA ARG          # 巴西 vs 阿根廷
python scripts/predict_match.py FRA ENG --host   # 法国(主) vs 英格兰
python scripts/predict_match.py BRA ARG --json   # 输出 JSON
python scripts/predict_match.py --list           # 列出所有可用球队

# 输出示例
⚽ 巴西 vs 阿根廷
  巴西胜: 36.9%  平局: 26.2%  阿根廷胜: 36.9%
  xG: 1.32 - 1.32  |  最可能比分: 1-1
  Top-3 因子: 攻防效率 → 巴西优势, FIFA排名 → 阿根廷优势, ...
```

**2. 数据质量报告 CLI** (`scripts/check_data_quality.py`)

```bash
python scripts/check_data_quality.py             # 检查所有数据
python scripts/check_data_quality.py --json      # JSON 输出
python scripts/check_data_quality.py --fix       # 自动修复
```

**3. 批量预测 CLI** (`scripts/batch_predict.py`)

```bash
python scripts/batch_predict.py --teams 8 --sim 5000 --format csv
# 输出: data/processed/batch_results.csv
```

---

## 六、环境依赖速查

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行环境 |
| numpy | 2.2+ | 数值计算 |
| pandas | 2.3+ | 数据处理 |
| scipy | 1.15+ | 泊松分布 |
| streamlit | 1.58+ | 可视化前端 |
| plotly | 6.8+ | 图表渲染 |
| matplotlib | 3.8+ | 素材生成 |
| fastapi | 0.110+ | API 后端 |
| uvicorn | 0.29+ | ASGI 服务器 |
| kagglehub | 0.2+ | Kaggle 下载 |
| python-pptx | 1.0+ | PPT 生成 |
| pyyaml | 6.0+ | 配置解析 |

```bash
# 一键安装
pip install numpy pandas scipy streamlit plotly matplotlib fastapi uvicorn kagglehub python-pptx pyyaml
```

---

> **文档版本**: v2.0 | **最后更新**: 2026-06-30 | **适用**: README + 答辩材料
