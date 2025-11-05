# Raspberry Pi 5 部署（Docker + systemd + Nginx）
目標網址： https://gilko.redirectme.net/market_monitor

## 1) 前置
- Pi5（ARM64）、Docker + Compose v2、Nginx、（可選）certbot
- 動態 DNS 已指到你的 Pi 外網

## 2) 安裝
```bash
mkdir -p /opt/market_monitor
unzip market_monitor_docker.zip -d /opt/market_monitor
cd /opt/market_monitor
docker compose up -d --build
```

## 3) Nginx 反代（加入到主站 server{} 的 location）
```nginx
location /market_monitor/ {
    proxy_pass http://127.0.0.1:8088/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```
若沒有主站 server{}，可用 `nginx/site.conf` 建一個虛擬主機，再 `nginx -t && systemctl reload nginx`。

## 4) HTTPS（可選）
```bash
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d gilko.redirectme.net
```

## 5) systemd 自動啟動
```bash
sudo cp systemd/market-monitor.service /etc/systemd/system/market-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable market-monitor
sudo systemctl start market-monitor
```

## 6) 環境變數
- `UPDATE_INTERVAL_MIN`：背景更新頻率（預設 10）
- `TICKERS`：追蹤清單，例 `NVDA,SMCI,QQQ,MSFT,GOOGL`
- `NEWS_PER_TICKER`：每檔新聞數

修改 `docker-compose.yml` 後，`docker compose up -d --build` 套用。

## 7) 測試
- 內部：`curl http://127.0.0.1:8088/`
- 外部：`https://gilko.redirectme.net/market_monitor`

## 8) 結構
```
market_monitor/
├─ docker-compose.yml
├─ app/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  ├─ server.py
│  ├─ templates/dashboard.html
│  ├─ static/style.css
│  └─ data/dashboard.json (自動生成)
├─ nginx/site.conf
└─ systemd/market-monitor.service
```
