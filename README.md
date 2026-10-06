# AI Workflow

公司內部 AI Workflow 專案，以 Dify Community Edition 提供 AI 應用、Workflow 與原生 Web App，並由 Django Portal 管理員工登入、Bot 授權及可用機器人列表。

Portal 與 Dify 的存取授權整合仍在驗收中，不應視為正式權限控管。最新實作狀態、測試結果與待辦統一記錄於 [PLAN.md](PLAN.md)。

## 文件導覽

- [AGENTS.md](AGENTS.md)：長期開發規則、身分安全與驗證要求。
- [PLAN.md](PLAN.md)：需求、建議方案、待辦與驗收進度；實作狀態以此文件為準。
- [Portal README](dify-portal/README.md)：Portal 安裝、本機啟動與測試指令。
- [整合測試操作](tools/portal-nginx-test.md)：Portal 與 Dify 的 Compose 啟動、狀態、日誌及回復方式。

## 專案結構

```text
ai_workflow/
├── README.md
├── AGENTS.md
├── PLAN.md
│
├── dify/                   # Dify 官方
│   └── docker/
│       ├── docker-compose.yaml
│       └── .env
│
├── dify-portal/            # 自建公司入口系統
│
└── tools/                  # 整合測試與 Nginx 掛載工具
    ├── dify-compose.portal-nginx.yaml  # Portal 與 Dify Compose override
    ├── dify-compose.portal-dev.yaml    # Portal 原始碼熱更新 override
    ├── portal-nginx-test.sh            # 整合測試操作腳本
    ├── portal-nginx-test.md            # 整合測試操作說明
    └── portal-nginx/
        └── default.conf.template       # Nginx 授權與路由模板
```

## 常用操作

在共同根目錄執行：

```bash
./tools/portal-nginx-test.sh check
./tools/portal-nginx-test.sh start
./tools/portal-nginx-test.sh dev-start
./tools/portal-nginx-test.sh stop
./tools/portal-nginx-test.sh status
./tools/portal-nginx-test.sh logs
```

這組設定用於本機 HTTP 整合測試，尚不是正式部署設定。完整前置條件、影響範圍與回復方式見[整合測試操作](tools/portal-nginx-test.md)。
