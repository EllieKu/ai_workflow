# PLAN.md — Dify Portal 實作計畫

本文件只保留目前有效的需求、設計決策、進度、限制與驗收項目。歷史變更由 Git 紀錄，開發必須遵守 `AGENTS.md`。

## 1. 目前狀態

**狀態：本機整合驗收中，尚不是正式部署。**

| 項目 | 目前狀態 |
| --- | --- |
| Dify | Community Edition；本機整合目標使用官方 API／Web image `1.17.1` |
| Portal | Django 5.2 LTS，SQLite，已建立 Portal image |
| 公開入口 | 沿用 Dify Compose 原有 `nginx` service，不新增外層或 Portal Nginx |
| 授權方式 | Nginx `auth_request` 查詢 Django Session、BotGrant 及已登記的 Dify passport |
| 已完成檢查 | 2026-10-07：62 個 Portal 測試通過，migration 一致性檢查無差異；既有 Compose 合併設定與 Nginx 語法檢查曾通過 |
| 本機運行檢查 | 2026-10-07：Portal healthcheck 為 healthy；`/password/change/` 經公開 Nginx 正確導向 Portal，未登入時回到 Portal 登入頁 |
| 尚未完成 | 實際提問與 SSE、跨使用者／Bot 隔離、全面防繞過、檔案所有權、停止生成、並行負載與正式部署驗收 |

未登入聊天入口會回應 401；登入後已能開啟 Dify 原生 Web App，初始相關 API 回應 200。實際提問、SSE 回答及完整隔離仍待驗證。

## 2. 目標與範圍

- 使用 Django 內建認證提供本地帳號登入與登出。
- 管理 Bot、Bot 啟用狀態及帳號與 Bot 的個別授權。
- 使用者只看到已授權 Bot，並使用 Dify 原生 Web App 聊天。
- 在可信任的伺服器端檢查登入、Bot 授權、實際 Dify App／EndUser 及物件所有權。
- 保留 Dify 原生對話、模型、RAG、Workflow 與日誌；日誌不顯示或對應 Portal 帳號。


## 3. 目錄與元件責任

| 路徑／元件 | 責任 |
| --- | --- |
| `AGENTS.md` | 長期開發、安全與交付規則 |
| `PLAN.md` | 目前需求、設計、進度與驗收狀態 |
| `README.md` | 專案入口、文件導覽與常用操作 |
| `dify/` | 官方 Dify |
| `dify-portal/` | Django 登入、Bot 管理、授權與 Dify 存取閥門 |
| `tools/` | Portal／Dify Compose override、Nginx 模板與整合測試操作工具 |

Portal SQLite 保存 Portal 帳號、Bot、BotGrant、Django Session、DifyIdentity 與 DifyPassport 摘要。聊天內容、對話及 Dify 原生日誌由 Dify 保存。

## 4. 現行架構與請求流程

### 公開入口

- Dify Compose 原有 `nginx` service 是唯一公開入口。
- `tools/dify-compose.portal-nginx.yaml` 新增只執行 Django／Gunicorn 的 `portal` service，並將版本管理的 `tools/portal-nginx/default.conf.template` 掛載到原有 Nginx。
- 公開 listener 提供 Portal 頁面、受保護的 Dify Web App 及已審查 API。
- 同一 Nginx 的 `8081` listener 是 Portal 取得原生 passport 的上游；主機只發布至 `127.0.0.1:8081`。

### 授權流程

1. 使用者登入 Portal，Django 建立 Session。
2. Portal 依使用者、帳號與 Bot 啟用狀態及 BotGrant 顯示可使用 Bot。
3. 瀏覽器請求 `/chat/<code>` 或受保護 API 時，Nginx 先透過內部 `auth_request` 請求 Django。
4. `/api/passport` 由 Django 處理。Portal 使用隨機內部 session ID 向 Dify 取得原生 passport，核對 App ID、App code 與 EndUser ID 格式後，只儲存 SHA-256 摘要。
5. 後續請求必須同時符合 Portal Session、BotGrant、App、DifyIdentity、passport 摘要與到期時間。
6. 一般歷史與設定 API 在授權通過後由 Nginx 直送 Dify。`/api/chat-messages` 暫時經 Django 檢查純文字 body 並 relay SSE。

Portal 不自行簽發額外交接 Token，也不接受瀏覽器自行登記 passport。若後續需要額外 Token，必須另行設計到期、目標 App 綁定與重放防護。

## 5. 已完成

- [x] Django 登入與 POST 登出，使用 UUID 帳號主鍵。
- [x] 管理員建立帳號或重設臨時密碼後，強制使用者登入並修改為不同密碼；完成前拒絕 Bot、聊天 API 與內部授權請求。
- [x] 既有且啟用中的非 superuser 帳號已透過 migration 標記為必須修改密碼；公開 Nginx 已加入 `/password/` Portal 路由。
- [x] Bot、BotGrant、DifyIdentity 與 DifyPassport 模型及 migration。
- [x] Django Admin 的帳號、Bot 與授權管理。
- [x] 依授權篩選的 Bot 列表；管理權不自動賦予 Bot 使用權。
- [x] Bot 列表顯示名稱與簡介；點擊 Bot 卡片會以新分頁開啟受保護的 Dify 原生 Web App。
- [x] Portal gateway、Nginx `auth_request` 端點、passport 摘要與 Portal Session／Bot／App 綁定。
- [x] 已審查的文字聊天、對話歷史、訊息、命名、釘選與回饋路由候選規則。
- [x] 本機 Portal image、Compose override、Nginx 模板、Portal healthcheck、SQLite online backup 及整合操作腳本。
- [x] 路由與授權檢查紀錄於 `dify-portal/docs/gateway-routes.md`。

## 6. 已知限制與待辦

### 功能與安全

- 帳號不使用郵件重設。管理員核實使用者身分後，在 Django Admin 為該帳號設定個別臨時密碼；既有 Session 會因密碼雜湊變更而失效，使用者以臨時密碼登入後必須先修改密碼。導入此流程時，migration 會標記既有且啟用中的非 superuser 帳號。禁止多人共用同一組臨時密碼。
- [ ] 用兩個帳號、不同 Bot 及共同授權 Bot 完成原生瀏覽器聊天、歷史、跨帳號／Bot 拒絕與撤權驗收。
- [ ] 盤點並封鎖受管理 App 的原生匿名入口、直接 API、替代網域／埠及其他發布入口。
- [ ] 完成檔案上傳、聊天引用、產生檔案與下載的使用者／Bot 所有權設計與驗收。
- [ ] 建立 task 與使用者／Bot 的可信任所有權後，才恢復停止生成。
- [ ] 逐一審查語音、獨立 Workflow、分享及其他未列出路由。
- [ ] 驗證 SSE timeout、中斷與已建立串流在登出／撤權後的最終策略。目前已開始的串流允許完成或逾時。

### 資料庫與部署

- [ ] 設定並驗證並行登入、passport 取得、授權檢查與撤權的測試規模、錯誤率與延遲門檻。
- [ ] 驗證 Portal container 重建後 SQLite 資料保留，並實際測試備份還原。
- [ ] 完成登入嘗試限制、HTTPS、可信任代理、Host／CSRF 設定與正式依賴鎖定。
- [ ] 正式環境關閉 `DJANGO_DEBUG`，限制後端直連，固定 Dify image 版本，並記錄 image digest。
- [ ] 實際驗證回滾。目前 `rollback` 會恢復原本 Dify Nginx，也會重新開放原生入口，不是保留 Portal 授權的正式回滾方案。

若 SQLite 在驗證規模下持續發生寫入競爭、延遲不符門檻，或需要多台主機，再規劃 PostgreSQL 遷移。遷移必須包含備份、資料搬移、切換、回滾與完整性驗證。

## 7. 重要技術限制

- Nginx `auth_request` 不讀取原始 JSON body，無法單獨判斷聊天內引用的檔案 ID 是否屬於當前使用者與 Bot。
- Dify 原生 `/files/` 使用簽名網址；有效簽名本身不能證明當前 Portal 使用者擁有檔案。
- Dify `1.17.1` 的停止流程中，舊機制所有權檢查不會回傳可供後續 GraphEngine 停止命令判斷的結果，因此 Portal 目前回應 403 且不轉送停止請求。
- `auth_request` 只在建立請求時檢查授權，不會持續重驗已建立的 SSE 串流。
- Portal 管理權與 Bot 使用權分開；staff／superuser 不自動取得 BotGrant。
- `sys.user_id`、Dify EndUser ID 與 Portal 帳號／工號不是同一欄位，不可互換或改寫日誌語意。

詳細路由、方法、物件檢查與暫停開放原因見 `dify-portal/docs/gateway-routes.md`。

## 8. 驗收清單

- [ ] 未登入使用者無法使用受管理 Bot，包含直接網址、匿名 Token 及直接 API。
- [ ] 兩個測試帳號只可使用各自授權 Bot，不能讀取或操作對方的對話、訊息、task 與檔案。
- [ ] 兩個帳號都可使用同一 Bot 時，仍維持對話與檔案隔離。
- [ ] 偽造或替換 username、user_id、app_id、`X-App-Code`、passport、Conversation ID、Message ID、task ID 與檔案 ID 均無法越權。
- [ ] 聊天憑證過期、跨 Portal Session、跨帳號或跨 Bot 使用時遭拒絕。
- [ ] 登出、帳號停用、Bot 停用與撤權後，下一個受保護請求遭拒絕；串流行為符合定義策略。
- [ ] 授權服務故障時拒絕存取；外部偽造內部 Header、直連 Dify 或使用替代入口無法繞過。
- [ ] 同帳號重新登入後只能取得自己的歷史，帳號改名不破壞授權與隔離關係。
- [ ] 已開啟的聊天、SSE、歷史、命名、釘選、回饋與建議問題可正常使用。
- [ ] 檔案與停止生成只在完成所有權設計後開啟，並通過正向及反向測試。
- [ ] 並行操作不發生導致請求失敗的 SQLite 鎖定，延遲符合事先設定的門檻。
- [ ] Portal container 重建後資料保留，且備份可成功還原帳號、Bot、授權與身分映射。
- [ ] URL、Git、前端靜態產物、一般日誌與錯誤訊息不暴露私鑰、密碼、API Key、Session 憑證或完整認證 Token。

完整授權驗收必須實際登入 Portal、開啟授權 Bot 並提問；單元測試或 mock 不可取代瀏覽器整合驗收。

## 9. 操作與交付

部署本次帳號流程前，需先套用 migration：

```bash
cd dify-portal
.venv/bin/python manage.py migrate
```

管理員在 Django Admin 新增使用者，或進入使用者頁面的密碼變更表單設定個別臨時密碼。系統會自動標記該帳號須修改密碼；使用者完成 Portal「修改密碼」後才可進入 Bot。首次套用此功能時，migration 也會標記既有且啟用中的非 superuser 帳號，superuser 不受影響。

本機候選整合在共同根目錄使用：

```bash
./tools/portal-nginx-test.sh check
./tools/portal-nginx-test.sh start
./tools/portal-nginx-test.sh stop
./tools/portal-nginx-test.sh status
./tools/portal-nginx-test.sh logs
```

`start` 會先使用 SQLite online backup 備份 Portal 資料庫，再合併 Dify 原始 Compose 與 Portal override 啟動目前 profile 的服務。`stop` 會停止相同 Compose project 的 container，但不刪除資料或 volumes。完整前置條件、影響範圍、Nginx 重載與回復方式見 `tools/portal-nginx-test.md`。

目前 Compose override 為配合 `http://localhost/` 將 `DJANGO_DEBUG` 設為 `true`，不可直接用於正式環境。正式交付前必須補齊 HTTPS、正式網域、Secure Cookie、CSRF、防火牆與後端直連限制，並完成第 8 節驗收。

### 區域網路連線設定盤點（2026-10-07）

- 已檢查現有設定：公開 Nginx port mapping 未限制為 loopback；`dify/docker/.env` 使用 HTTP 80，Portal 預設只接受 localhost／loopback Host。
- 供同網段測試時，在 `dify-portal/.env` 設定 `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],<主機區網 IP>`，保留 localhost 供 healthcheck 使用；可明列 `PORTAL_CSRF_TRUSTED_ORIGINS=http://<主機區網 IP>`（非 80 埠須附埠號）。兩者由 Portal Compose override 傳入 Django；`dify-portal/.env.example` 不會自動載入。
- 套用步驟：執行 `./tools/portal-nginx-test.sh check`，再執行 `./tools/portal-nginx-test.sh start`。其他電腦經主機區網 IP 的公開 Nginx 入口連線，防火牆僅對所需內網放行公開埠。
- 保留原生上游 `127.0.0.1:8081:8081` 限制，不公開 Portal／Dify 後端埠。現有 Dify 對外 URL 設定為空，沒有需替換的 localhost 絕對 URL。
- 已將 Portal 連線參數獨立至 `dify-portal/.env`（Git 忽略），啟動腳本的 Compose 流程依序載入 Dify 及 Portal 環境檔；Portal 檔案缺少時保留既有預設值。已更新範例與操作文件，不修改 Dify 原生環境檔。
- 未重啟服務或執行跨電腦連線驗證；本機 Portal 環境檔先保留 localhost 預設值，待填入實際區網 IP 後套用。內網正式使用仍須完成 HTTPS 與既定授權整合驗收。

- 本次設定調整驗證：`bash -n`、Compose `config --quiet`、Portal 環境映射與 8081 loopback 綁定檢查、Git 忽略與 `git diff --check` 均通過；未執行登入／聊天 E2E。

### 區網設定啟動修復（2026-10-07）

- Portal 啟動失敗原因：`PORTAL_CSRF_TRUSTED_ORIGINS` 填入裸 IP，Django 系統檢查回報 `4_0.E001` 並退出。
- 已將本機 `dify-portal/.env` 修正為 `PORTAL_CSRF_TRUSTED_ORIGINS=http://192.168.51.90`，保留既有 Host 清單。
- 已通過 Compose 設定檢查，執行 `start` 完成 SQLite 備份及服務啟動；Portal 為 healthy，Nginx 已啟動，8081 仍只綁定 loopback。
- 從主機透過 `http://192.168.51.90/login/` 檢查回應為 HTTP 200。尚未從其他電腦測試，亦未執行實際登入／提問與拒絕存取 E2E。

### 區網 Host 白名單修復（2026-10-19）

- 發現本機 `dify-portal/.env` 使用 `DJANGO_ALLOWED_HOSTS` 與 `DJANGO_CSRF_TRUSTED_ORIGINS`，但 Compose override 讀取的是 `PORTAL_*`，導致容器採用僅允許 localhost 的預設值。
- 當時將本機環境變數名稱修正為 `PORTAL_ALLOWED_HOSTS` 與 `PORTAL_CSRF_TRUSTED_ORIGINS`，保留 `192.168.51.90` 及 localhost 設定；一般與開發 Compose 設定檢查通過。Host 變數現已依下節統一為 `DJANGO_ALLOWED_HOSTS`。
- 已透過合併 Compose 執行 `up -d --no-deps portal`，重新建立 Portal 容器套用設定。日後修改相同環境變數可執行 `./tools/portal-nginx-test.sh start` 套用。
- 經本機公開 Nginx 請求 `/login/`：`Host: 192.168.51.90` 回應 200；`Host: untrusted.invalid` 回應 400。尚未從其他電腦驗證，也未執行登入／提問 E2E。

### Host 環境變數名稱統一（2026-10-19）

- 依需求將 Host 白名單統一為 `DJANGO_ALLOWED_HOSTS`，`.env` → Compose → Django 全程使用相同名稱；移除 Compose 對 `PORTAL_ALLOWED_HOSTS` 的讀取，不保留舊名稱別名。Django 設定讀取程式已使用相同名稱，無須修改。
- 已同步Compose override、本機 `.env`、範例、Portal README 與整合操作文件；本機白名單仍保留 localhost／loopback 及 `192.168.51.90`。CSRF 變數維持原有名稱與映射。
- 驗證：Compose `config --quiet` 通過；本機設定、shell 覆寫、空值採用 loopback 預設值、舊名稱不生效的映射檢查通過；範例僅有一筆 Host 設定，`git diff --check` 通過。未重跑瀏覽器登入／聊天 E2E。
- 部署：既有環境檔將 `PORTAL_ALLOWED_HOSTS` 改為 `DJANGO_ALLOWED_HOSTS` 並保留值，執行 `./tools/portal-nginx-test.sh check` 後，以 `start`套用。本次容器內變數名稱與有效白名單值均未改變，未重啟服務。
