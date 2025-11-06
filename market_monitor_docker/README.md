# 市場監控面板 Market Monitor Dashboard

進階股市監控儀表板，整合即時股價、歷史圖表、AI 智能分析與新聞追蹤。

## ✨ 功能特色

### 📊 股價監控
- **即時價格更新** - 每 10 分鐘自動更新
- **30天歷史圖表** - Chart.js 互動式折線圖
- **關鍵統計數據** - 日變化、30天高低點
- **價格變動指標** - 綠色▲上漲 / 紅色▼下跌

### 🤖 AI 智能分析
- **多 AI 引擎支援** - 支援 OpenAI GPT 和 Anthropic Claude（可選擇）
- **趨勢判斷** - AI 分析市場趨勢（看漲/看跌/中性）
- **關鍵要點提取** - AI 自動總結 3-5 個重要市場動態
- **每 10 分鐘更新** - 隨股價數據同步更新 AI 分析

### 📰 新聞追蹤
- **Google News 整合** - 自動抓取相關市場新聞
- **多來源聚合** - 涵蓋財報、產業動態、市場分析
- **即時更新** - 與價格數據同步

### 🎨 現代化界面
- **深色主題** - 專業金融面板風格
- **響應式設計** - 完美支援桌面與行動裝置
- **流暢動畫** - 卡片懸停、數據更新過渡效果
- **倒數計時器** - 視覺化顯示下次更新時間

## 🚀 快速開始

### 1. 前置需求
- Docker & Docker Compose
- AI API Key（OpenAI 或 Anthropic，二選一）

### 2. 設定 API Key

複製環境變數範例檔案：
```bash
cp .env.example .env
```

編輯 `.env` 檔案，選擇 AI 引擎並填入對應的 API Key：

#### 選項 A：使用 OpenAI GPT（推薦，預設）
```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

**取得 OpenAI API Key：**
1. 前往 [OpenAI Platform](https://platform.openai.com/api-keys)
2. 註冊/登入帳號
3. 建立新的 API Key
4. 模型：使用 `gpt-4o-mini`（成本低、速度快）

#### 選項 B：使用 Anthropic Claude
```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

**取得 Anthropic API Key：**
1. 前往 [Anthropic Console](https://console.anthropic.com/)
2. 註冊/登入帳號
3. 建立新的 API Key
4. 模型：使用 `claude-3-5-sonnet`

#### 選項 C：停用 AI 分析
```env
AI_PROVIDER=none
```

### 3. 啟動服務

使用 Docker Compose 一鍵啟動：
```bash
docker-compose up -d
```

### 4. 訪問面板

開啟瀏覽器，前往：
```
http://localhost:8090
```

## ⚙️ 環境變數配置

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `AI_PROVIDER` | `openai` | AI 引擎選擇（`openai`、`anthropic`、`none`） |
| `OPENAI_API_KEY` | - | OpenAI API 金鑰（當 `AI_PROVIDER=openai` 時需要） |
| `ANTHROPIC_API_KEY` | - | Anthropic API 金鑰（當 `AI_PROVIDER=anthropic` 時需要） |
| `TZ` | `Asia/Taipei` | 時區設定 |
| `UPDATE_INTERVAL_MIN` | `10` | 數據更新間隔（分鐘） |
| `TICKERS` | `NVDA,SMCI,QQQ` | 監控股票代碼（逗號分隔） |
| `NEWS_PER_TICKER` | `12` | 每支股票新聞數量 |
| `HISTORY_DAYS` | `30` | 歷史數據天數 |

### 自訂監控股票

編輯 `docker-compose.yml`：
```yaml
environment:
  - TICKERS=AAPL,MSFT,GOOGL,TSLA
```

## 📁 專案結構

```
market_monitor_docker/
├── app/
│   ├── server.py              # FastAPI 後端服務
│   ├── templates/
│   │   └── dashboard.html     # 前端儀表板
│   ├── static/
│   │   └── style.css          # 樣式表
│   ├── data/
│   │   └── dashboard.json     # 數據快取
│   ├── requirements.txt       # Python 依賴
│   └── Dockerfile
├── docker-compose.yml         # Docker Compose 配置
├── .env.example               # 環境變數範例
└── README.md                  # 專案文件
```

## 🛠️ 技術棧

### 後端
- **FastAPI** - 高性能 Python Web 框架
- **yfinance** - Yahoo Finance API 包裝
- **OpenAI GPT-4o-mini** - AI 分析引擎（預設）
- **Anthropic Claude 3.5 Sonnet** - AI 分析引擎（可選）
- **feedparser** - RSS 新聞解析

### 前端
- **Chart.js** - 互動式圖表庫
- **Vanilla JavaScript** - 無框架依賴
- **現代 CSS** - Grid、Flexbox、動畫

## 🔄 更新日誌

### v2.1.0 (最新)
- ✅ 新增 OpenAI GPT 支援（預設使用 `gpt-4o-mini`）
- ✅ AI 引擎可選擇（OpenAI / Anthropic / None）
- ✅ 改進 AI 分析錯誤處理

### v2.0.0
- ✅ 新增 30 天歷史價格圖表
- ✅ 整合 Anthropic Claude AI 智能分析
- ✅ 新增關鍵統計數據（高低點、變化率）
- ✅ 改進視覺設計（AI 分析卡片、統計面板）
- ✅ 圖表懸停工具提示
- ✅ 響應式圖表設計

### v1.0.0
- 基礎股價監控功能
- Google News 整合
- 10 分鐘自動更新
- 深色主題界面

## 🐛 故障排除

### AI 分析顯示「未啟用」
- 確認 `.env` 檔案中已設定 `AI_PROVIDER` 和對應的 API Key
- OpenAI: `OPENAI_API_KEY` 格式應為 `sk-proj-...`
- Anthropic: `ANTHROPIC_API_KEY` 格式應為 `sk-ant-api03-...`
- 確認 Docker Compose 已讀取環境變數：`docker-compose config`
- 重新建構容器：`docker-compose up -d --build`

### 圖表不顯示
- 檢查瀏覽器控制台是否有 Chart.js 載入錯誤
- 確認網路可連接 CDN：`cdn.jsdelivr.net`

### 股價數據為 null
- 確認網路可連接 Yahoo Finance API
- 檢查股票代碼是否正確
- 查看容器日誌：`docker-compose logs -f market-monitor`

## 📝 授權

本專案僅供學習與個人使用。

## 🤝 貢獻

歡迎提交 Issue 與 Pull Request！

## 📧 聯絡

如有問題或建議，請提交 GitHub Issue。
