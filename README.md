# AI Workflow

公司內部 AI Workflow 專案。

專案規劃以 Dify Community Edition 作為 AI 應用與 Workflow 平台，並透過自建 Django Portal 提供員工登入、身分識別及應用程式存取控制，聊天介面沿用 Dify 原生 Web App。

已開始實作，完成 Dify 原始碼初步盤點與 Portal 基礎程式；Django 基礎檢查與 21 個 Portal 測試已通過，Dify 存取授權整合尚未完成。已建立的功能與本機啟動方式請見 [Portal README](dify-portal/README.md)，完整進度以 `PLAN.md` 為準。

## 文件導覽

- [AGENTS.md](AGENTS.md)：長期開發規則、身分安全與驗證要求。
- [PLAN.md](PLAN.md)：需求、建議方案、待辦與驗收進度；實作狀態以此文件為準。
- 本文件：專案介紹與維護操作說明。

## 專案結構

```text
ai_workflow/
├── README.md
├── AGENTS.md
├── PLAN.md
│
├── dify/
│   └── Dify Fork
│
├── dify-portal/
│   └── 自建 Portal / Authentication
│
└── tools/
    └── sync-upstream.sh
```

### `dify/`

Fork 自官方 Dify Repository：

- `origin`：自己的 GitHub Fork
- `upstream`：官方 Dify Repository

預期 Remote 設定（實際值待版本盤點確認）：

```text
origin    https://github.com/EllieKu/dify.git
upstream  https://github.com/langgenius/dify.git
```

`main` 分支原則上保持與官方 `upstream/main` 一致。

Dify 的客製修改不應直接開發在 `main`。

---

### `dify-portal/`

公司內部 AI Portal。

預計負責：

- 員工登入
- 使用者身分識別
- 員工 ID 管理
- AI 應用程式權限控制
- Dify 整合

Portal 為獨立專案，負責登入、Bot 授權與可用機器人列表。使用者透過 Dify 原生 Web App 聊天；Dify 後台日誌維持原生 user_id，不要求辨識 Portal 帳號。Dify／代理層的最小授權整合方式仍待驗證，須防止直接網址或 API 繞過授權。

---

### `tools/`

存放整個 AI Workflow 專案的維護工具。

目前包含：

```text
tools/
└── sync-upstream.sh
```

## Dify Upstream 同步

Dify 官方專案更新時，不直接手動修改 `main`。

在共同根目錄執行（會更新本機 `main`，並在符合下述條件時 push 到 Fork）：

```bash
./tools/sync-upstream.sh
```

同步流程：

```text
upstream/main
      │
      ▼
local main
      │
      ▼
origin/main
```

腳本會先執行安全檢查，包括：

- 確認 Dify 工作區沒有未提交修改
- 確認 `origin` Remote 存在
- 確認 `upstream` Remote 存在
- Fetch 最新的 Remote 狀態
- 切換至本機 `main`
- 檢查 `main` 是否存在官方沒有的 Commit
- 顯示官方新增的 Commits
- 要求人工確認
- 僅允許 Fast-forward 更新
- 更新完成後 Push 至自己的 Fork

腳本不會自動更新 Feature Branch，也不會重建 image 或部署服務。

注意：fetch 與切換至 `main` 發生在人工確認之前；取消或後續檢查失敗時，不會自動切回原分支。若本機 `main` 已與 `upstream/main` 一致，腳本直接結束，不會補做 push；因此不能以成功結束判定 `origin/main` 已同步。腳本僅檢查 Remote 是否存在，不驗證 URL 是否符合上列預期設定。

## Git 分支原則

本機原始碼建置步驟見 [Dify 客製 image 建置](tools/dify-build.md)。

### `main`

`main` 用來追蹤：

```text
upstream/main
```

原則：

- 不直接修改程式
- 不直接建立客製 Commit
- 不在 `main` 開發功能
- 保持可 Fast-forward 至官方最新版

### Feature Branch

Dify 客製功能使用獨立分支，例如：

```text
feature/portal-auth
feature/user-identity
feature/custom-webapp
```

建立方式：

先依 [PLAN.md](PLAN.md) 階段 0 選定並記錄基準版本，再建立分支；下例的 `<verified-tag-or-commit>` 須替換為已驗證的 release tag 或 commit。

```bash
cd dify

git switch -c feature/portal-auth <verified-tag-or-commit>
```

功能修改及 Commit 應留在 Feature Branch。`main` 用於追蹤官方動態；客製版本與部署須固定基準 commit 及 image 版本，不直接將最新 `main` 視為可部署版本。

## 官方 Dify 更新後

先由維護者決定是否更新 Dify：

```bash
./tools/sync-upstream.sh
```

有官方新增 commit、確認更新且 push 成功後：

```text
upstream/main
      │
      ▼
local main
      │
      ▼
origin/main
```

此時不會自動修改既有 Feature Branch。

如果需要讓某個 Feature Branch 套用新版 Dify，再另外進行整合與測試。

例如，先將下例的 `<target-tag-or-commit>` 替換為此次選定的升級版本：

```bash
cd dify

git switch feature/portal-auth

git merge <target-tag-or-commit>
```

如果發生 Conflict，應先確認官方 Dify 的變更內容，再決定如何處理，不應直接覆蓋。

整合後須依 `PLAN.md` 執行認證、越權、對話隔離與實際聊天驗收，重建 image 並記錄回滾方式，才能作為部署版本。

## 維護原則

Dify 為外部開源專案，因此：

> 官方程式碼與公司客製程式碼應盡可能分離。

維護時應優先考慮：

```text
官方 Dify
    │
    ▼
upstream/main
    │
    │  維護者決定是否更新
    ▼
main
    │
    │  測試 / 整合
    ▼
feature/*
    │
    ▼
公司客製版本
```

避免直接修改 `main`，降低未來 Dify 官方版本更新時的維護與 Merge Conflict 成本。
