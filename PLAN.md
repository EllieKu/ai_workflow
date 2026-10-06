# PLAN.md — Dify Portal 實作計畫

狀態：實作中。2026-10-05 已選定並在本機套用 Dify Compose 現有 `nginx` service＋Django `auth_request` 候選整合；不新增外層或 Portal Nginx。Portal 共 55 個測試通過，migration 一致性檢查無差異。首次瀏覽器進入聊天發現內部授權請求 Host傳遞錯誤，已修正並重載原有 Nginx；登入後聊天、完整防繞過與檔案隔離仍待驗收，不能視為正式整合。

本文件記錄需求、實作方案與進度；開發必須遵守 `AGENTS.md`。下列「建議」及「待確認」是待技術驗證的方案，不代表使用者已指定所有實作細節。

## 1. 已確認目標

- 使用 Django 建立 Portal，提供登入與依帳號權限顯示的 Bot 列表。
- 使用者選擇 Bot 後，使用 Dify 原生 Web App 對話。
- Dify 使用 Community Edition，以 Docker Compose 啟動。
- Portal 負責登入、Bot 權限控管與可用 Bot 列表；優先評估代理層與現有認證機制的最小整合，必要時才增加交接 Token 或修改 Dify。
- Dify 保留原生對話與日誌，不要求後台辨識 Portal 帳號或 user_id，也不客製日誌身分顯示。
- 盡量保留 Dify 現有功能，讓後續升級仍可維護。
- Portal 第一版使用 SQLite，依實測結果評估是否遷移 PostgreSQL。

第一版範圍：本地帳號、登入／登出、Bot 管理、帳號與 Bot 授權、Bot 列表與原生 Web App 存取授權；不包含 Dify 日誌帳號對應。

不打算加入：AD／LDAP、另做聊天 UI、計費、多租戶或與本需求無關的 Dify 核心改造。

## 2. 目錄與責任

| 路徑 | 用途 |
| --- | --- |
| `AGENTS.md` | 兩個專案共用的長期開發規則 |
| `PLAN.md` | 需求、設計、待辦、驗收進度 |
| `README.md` | 專案介紹、文件導覽與維護操作入口 |
| `dify/` | 官方 Dify 與必要的存取授權整合修改 |
| `dify-portal/` | Django 登入、Bot 管理、授權與聊天入口 |
| `tools/` | 跨專案維護工具 |

三份文件放在共同根目錄。若目前開發工具只開啟其中一個專案，須確保工作時也能讀取共同規範；不要為符合示例搬動既有專案。

## 3. 預計使用流程

1. 使用者登入 Portal，建立 Django Session。
2. Portal 後端依帳號及 Bot 啟用狀態，顯示可使用的 Bot。
3. 點選 Bot 後，Portal 後端再次檢查登入、帳號、Bot 啟用狀態及授權。
4. 透過經驗證的 Dify／代理層授權機制開啟原生 Web App，交接方式待定。
5. 後續受保護請求持續檢查授權及物件所有權，確保使用者與 Bot 間隔離。
6. Dify 保留原生日誌與 user_id 顯示，不新增 Portal 帳號對照。

不能只用隱藏卡片或導向公開網址完成權限控管。先驗證原生入口、API 與檔案的防繞過方式，再決定最小整合方案；若採 Token，登入交換 Token 與後續聊天憑證分開管理。

## 4. 建議方案與待確認事項

### 授權方案與決策順序

- 已確認：保留原生 Web App；Portal 為登入與 Bot 授權來源，安全性不依賴隱藏 URL。已登入且有權限者可直接開啟受保護網址，未登入或無權限者即使取得網址也不得使用。
- 優先評估同源入口及 host-only Session Cookie；iframe 與一般導向均需同樣的後端防護，不預設共享父網域 Cookie。
- 已選定 Dify Compose 原有的 `nginx` service 作為唯一公開入口；在該 service 掛載版本化設定，使用 `auth_request` 向 Django 檢查 Session、BotGrant 與已登記的原生 passport。不新增第二個 Nginx service、外層 Nginx 或 Portal Nginx；Django 不承擔一般歷史與設定 API 的內容傳輸。
- `/api/passport` 與 `/api/login/status` 仍由 Django 處理，因前者必須以伺服器端身分向 Dify 取證並登記摘要。`/api/chat-messages` 暫時保留 Django 的文字輸入檢查與 SSE relay，直到實際版本能可靠確認檔案引用所有權；這是過渡限制，不將 `auth_request` 誤當成能檢查 JSON body。
- 判定純代理不足時，記錄無法可靠驗證的端點及原因，再選擇最小 Dify 修改。不以既有候選程式存在作為方案已定案的依據。

### Portal

| 項目 | 方案／初步建議 | 確認方式 |
| --- | --- | --- |
| 頁面 | 已建立 Django Templates 登入頁、Bot 列表與明細 | Django 檢查與 Portal 測試通過；瀏覽器操作待確認 |
| 管理 | 已建立 Django Admin 帳號、Bot 與授權管理 | 管理權限測試通過 |
| 資料庫 | 已確認第一版使用 SQLite；不足時再評估 PostgreSQL | 上線前驗證並行情境，測試規模待確認，記錄鎖定錯誤與請求延遲 |
| 授權模型 | 已建立個別帳號與 Bot 授權；管理員無隱含 Bot 使用權 | Portal 正反向授權測試通過 |
| 開啟聊天 | 優先一般頁面導向 | 驗證授權交接，不預設需要 iframe |

已存在 User、Bot、BotGrant；代理原型另有 DifyIdentity、DifyPassport，是否保留依選定方案與驗證結果決定。稽核資料按實際需要設計。Bot 保存 Dify App 識別與 Web App code；不因其他架構範例而預先加入不需要的 Service API Key。

若加入群組授權，建議採個人與群組允許權限聯集、預設拒絕，且停用帳號／Bot 優先。Portal 管理權限與 Bot 使用權限分開。

### Portal 資料庫與持久化

- SQLite 保存 Portal 帳號、Bot、授權與 Session；身分映射、憑證登記、交換與稽核資料僅在所選方案需要時保存；聊天內容與對話日誌仍由 Dify 保存。
- 容器部署時將 SQLite 所在的完整資料目錄掛載至固定的持久化儲存，並建立一致性備份與還原流程；驗證容器重建後資料仍可使用。
- 使用 Django ORM 與 migration，減少資料庫專屬語法；若採一次性 Token，其原子消耗須在實際使用的 SQLite 與多 worker 環境驗證。
- 上線前測試並行登入、授權交接、聊天期間授權檢查及撤權；記錄請求延遲、失敗率與資料庫鎖定錯誤，事先確認測試規模與延遲驗收門檻。
- 若持續發生寫入競爭、延遲未達驗收門檻，或需要多台主機部署，再評估遷移 PostgreSQL。
- 遷移需另行規劃備份、資料搬移、切換與回滾，並驗證帳號、授權及身分映射完整性，不只修改連線設定。

### Session、撤權與失敗處理（所有方案適用）

- 每個受保護請求須驗證有效 Portal Session、帳號／Bot 啟用狀態與當前 Bot 授權，並確認授權對象與 Dify 實際處理的 App／EndUser 一致。
- 登出、停用或撤權後的下一個受保護請求必須被拒絕；快取或憑證期限不能放寬此目標。若使用快取，須有符合此目標的失效機制。
- 無法取得可靠授權結果時拒絕存取，不降級至匿名模式；區分未登入、無權限與上游故障的回應。`auth_request` 驗證端應回傳 401／403 而非登入頁導向。
- 保留 CSRF、Cookie 與可信代理防護，驗證內部端點及身分 Header 不可由外部偽造。
- 原型目前讓已開始的 SSE 串流完成或逾時，不主動中止；這是候選行為，正式策略仍待定案與實測。`auth_request` 不會持續重新驗證已建立的串流。

### 額外交接 Token（僅在需要時採用）

原生 Dify passport 與額外的 Portal 交接 Token 是不同機制。目前代理原型向 Dify 取得原生 passport，登記其摘要並綁定 Portal Session，未自行簽發交接 Token。

- 僅在所選交接方式需要時設計 Token；使用成熟套件，驗證來源、接收者、期限、目標 Bot、登入關聯與重放防護，不以 Token 取代即時授權及物件所有權檢查。
- 若採 JWT，選定演算法與必要 claims，記錄金鑰保存、輪替、期限與續期；不預先固定非對稱簽章或 60 秒期限。
- 若採一次性交換，使用資料庫或 Redis 等機制原子消耗，並驗證多 worker 並行情境。一般聊天憑證可在有效綁定下重複使用，不能將所有憑證重用都視為一次性 Token 重放。
- 優先評估同源 POST 與安全 Cookie，禁止把完整憑證放入 URL 或一般日誌；不在 Token 內放原始 Django Session 憑證。

### 對話隔離與原生日誌

- 查證 EndUser 在實際版本的 App／tenant 範圍及唯一性。
- 為同帳號歷史與跨帳號隔離，評估是否需要 Portal 使用者、App 與 EndUser 的穩定內部關聯；不以在 Dify 日誌中顯示帳號為目的。
- Dify 日誌維持既有欄位與原生顯示，不要求呈現或追溯 Portal 帳號。
- 保留 Dify 內部 ID 與 `sys.user_id` 的既有語意，不替換成 Portal 帳號或工號。
- Portal 帳號改名須保留原授權與隔離用身分，不修改既有 Dify 日誌。

### 部署與路由

- 固定 Dify release tag／commit 與 image 版本；記錄 Compose override、重建、備份與回滾步驟。
- `main` 追蹤官方更新，客製分支與部署使用已驗證的固定基準；同步 `main` 不代表已完成版本升級或部署驗收。
- Portal 可先在主機執行或日後使用只包含 Django／Gunicorn 的 container；兩種方式都由 Dify Compose 現有 `nginx` service 反向代理，不為 Portal 增加 Nginx。
- 優先驗證同源路由；分清 Portal、Dify Web App、Console、Service API 與檔案路由。
- 列出受管理 App 的匿名 Token 入口、公開分享及其他可能的繞過路徑，逐一決定封鎖或適配方式。
- 驗證後端直連限制、HTTPS、Cookie、CSRF、Host 與可信代理設定。
- 檢查 SSE 的代理緩衝、timeout、取消與斷線行為。
- `.env.example` 僅含占位值；正式環境關閉 DEBUG。

## 5. 實作階段

### 階段 0：版本盤點與最小整合驗證

- [x] 盤點 Dify checkout、Compose image 設定、工作區修改與 Portal 初始狀態（詳見第 7 節）。
- [ ] 核對實際運行環境版本與測試 Bot，選定並驗證部署基準；需要客製原始碼時才選定客製基準。
- [x] 找出目前 checkout 的 Web App 認證、EndUser、對話所有權及日誌顯示接點（尚未修改或執行驗證）。
- [ ] 建立最小測試流程：測試帳號登入 → 顯示授權 Bot → 原生 Web App 提問成功；未授權及直接繞過入口的操作遭拒絕。
- [ ] 建立路由／方法清單：各端點的 App 解析、身分綁定、物件所有權、防直連及未支援功能處理；依結果列出必要修改，更新第 4 節。

完成條件：以實際版本證明 Portal 授權可保護原生聊天與後續請求，再擴充功能；目前尚未完成此驗證，不包含日誌帳號辨識。

### 階段 1：Portal 基礎功能

- [x] 建立登入／登出、Bot 與授權模型及初始 migration；已在本機 SQLite 成功執行。
- [x] 建立 Django Admin 管理與依權限篩選的 Bot 列表、明細；相關自動化測試通過。
- [x] 驗證 Portal 停用帳號、無權限 Bot、管理與使用權限的差異；Dify 操作仍待整合驗證。

### 階段 2：Dify 存取授權整合

- [ ] 實作選定的授權交接機制與必要的使用者／Bot 隔離關聯；若採 Token，完成簽發、後端驗證與一次性交換。
- [ ] 接上原生 Web App，完成聊天、歷史與檔案的授權檢查。
- [ ] 封鎖受管理 App 的匿名繞過路徑。
- [ ] 完成登出、撤權、停用、過期與續期處理。

### 階段 3：部署與驗收

已提供並套用本機整合測試用 Portal image與 Compose候選設定；override沿用 Dify原有 `nginx` service，並建立只執行 Django／Gunicorn的 `portal` service，掛載 SQLite資料目錄，不包含第二個 Nginx，也不另啟動資料庫 container。這仍是候選測試設定，尚未完成正式部署驗收。

- [ ] 固定官方 image；有 Dify 原始碼修改時才重建相應 image。完成 Portal image、Compose、反向代理與環境變數範例。
- [ ] 完成登入嘗試限制、受信任代理／HTTPS 設定與完整依賴鎖定，將靜態檔案收集納入正式部署流程；既有本機 `collectstatic` 紀錄不代表部署流程已完成。
- [ ] 執行下列驗收與現有工具鏈檢查，記錄實際命令及結果。
- [ ] 補齊啟動、管理 Bot／權限、升級、備份及回滾操作說明。

## 6. 驗收清單

- [ ] 未登入使用者無法使用受管理 Bot，包含直接網址、匿名 Token 及直接 API。
- [ ] 兩個測試帳號只可使用各自授權的 Bot，不能讀取或操作對方的對話、訊息與檔案。
- [ ] 聊天憑證偽造、過期、跨帳號／登入 Session／Bot 使用均遭拒絕；若另採交接 Token，追加錯誤來源、接收者及一次性交換重放驗證。
- [ ] 前端修改 username、user_id、app_id、X-App-Code、passport 或 Conversation ID 無法冒用或越權；包含兩個帳號都可使用同一 Bot 的情境。
- [ ] 代理授權服務故障不放行；外部偽造內部身分 Header、直連 Dify、替代網域／埠或其他發布入口不能繞過。
- [ ] 同帳號重新登入維持自己的歷史；不同帳號不混用。
- [ ] 登出、停用及撤權後，既有聊天憑證的下一個受保護請求遭拒絕；串流行為符合已定義方案。
- [ ] 串流、歷史、上傳、回饋、停止生成等已啟用功能正常。
- [ ] 若採一次性 Token，多 worker 下同一交換 Token 僅能成功使用一次。
- [ ] 依事先確認的測試規模驗證並行情境，登入、授權交接、授權檢查與撤權正確，無資料庫鎖定導致的請求失敗，延遲符合事先訂定的門檻。
- [ ] 重建 Portal 容器後 SQLite 資料保留，且備份可成功還原帳號、Bot、授權與身分映射。
- [ ] URL、Git、前端靜態產物、一般日誌及錯誤訊息不暴露秘密或完整認證 Token；瀏覽器僅依協定接收必要使用者憑證。

檢查範圍：Django check、migration 檢查、相關單元與整合測試，以及 Dify 修改範圍的既有 lint／typecheck／測試。依實際專案決定命令，不將範例命令當成已執行結果。

## 7. 實作紀錄與驗證限制

| 項目 | 目前狀態 |
| --- | --- |
| Dify 基準版本／commit | 已盤點 checkout `4c640ff898ccfd48e0796276c999885ef1b5fdb8`；正式客製基準仍待選定與驗證 |
| Portal 資料庫 | 已確認第一版使用 SQLite；持久化、備份還原及並行驗證待實作，測試規模待確認 |
| 修改檔案與端點 | Portal 基礎路由及候選 `/chat/<code>`、`/api/<path>`、`/_next/static/<asset>`；另有 `gateway.py`、migration `0002` 與代理測試；本次未修改程式 |
| Session 與撤權方案 | 已在本機套用 Nginx內部授權端點候選：以 passport摘要綁定登入 Session／授權／身分，每次請求重查授權；完整瀏覽器驗收尚未完成 |
| Dify 日誌 | 維持原生顯示；已取消 Portal 帳號／user_id 辨識需求 |
| 已完成檢查與測試 | 2026-10-05：55 個測試通過，測試系統檢查及 migration 一致性檢查無問題；Compose 合併設定與運行中 Nginx 語法檢查通過；統一啟動後 Portal healthcheck為 healthy，首頁回應 302導向登入頁且登入頁回應 200；完整瀏覽器整合驗收尚未完成 |
| 部署、備份與回滾命令 | 已新增並套用本機候選操作工具與 SQLite online backup；回滾尚未實際驗證 |

已建立 [Dify 本機建置 override](tools/dify-compose.build.yaml) 與 [操作說明](tools/dify-build.md)：以現有 commit 作為候選基準，API／worker／worker_beat／api_websocket 共用客製 API image，Web 使用客製 Web image；其他輔助服務維持官方 image，相容性仍待驗證。Compose `config --quiet` 已通過；尚未切換分支、執行 build 或啟動服務，不能視為已驗收版本。

### 先前原始碼盤點與整合接點（非運行環境證明）

- Dify 在 `main`，`git describe --tags --always` 為 `1.17.1-502-g4c640ff898`，工作區無未提交修改；`docker/docker-compose.yaml` 的 API／Web image 設為 `1.17.1`。原始碼與 image 不同，尚未查證實際運行版本，不能混用作為驗收依據。
- Portal 起始只有 `.gitignore`；現已新增 Django 5.2 LTS 基礎程式。User 繼承 Django `AbstractUser`，使用 UUID 主鍵，帳號改名不改識別；Bot 與 Dify App 一對一，授權有資料庫唯一約束。
- `dify/api/controllers/web/passport.py` 接收 `X-App-Code` 與可選的前端 `user_id`，交由 `services/web_passport_service.py` 簽發 passport。標準流程不是 Portal 身分驗證，不能直接信任前端帳號。
- `dify/api/repositories/web_passport_repository.py` 以 tenant、App 與 `session_id` 查找 EndUser；`models/model.py` 的 EndUser 沒有對此組合建立唯一約束。代理原型已有內部映射與序列化建立策略，實際版本相容性及多 worker 行為仍待驗證。
- `dify/api/controllers/web/wraps.py` 的 `decode_jwt_token` 是 Web API 驗證接點；`libs/token.py` 讀取 App 對應 passport Cookie 或 Header。`web/service/share.ts` 的 `requestAccessToken` 是前端 passport 取得接點。
- `dify/api/services/conversation_service.py` 的 `get_conversation` 依 App、來源與 EndUser 檢查對話；仍須逐項檢查其他訊息、停止生成、上傳與檔案路徑，不能由此推論所有操作已隔離。
- 聊天日誌 `dify/web/app/components/app/log/list-utils.ts` 使用 `from_end_user_session_id`；Workflow 日誌與執行明細使用 `created_by_end_user.session_id`。此為先前盤點結果；日誌帳號顯示適配已移出需求，保留原生欄位語意。
- 原生 passport、`controllers/service_api/wraps.py` 的獨立 API Token 流程、簽名檔案路由，以及分享／嵌入與其他發布路徑，都需納入後續受管理 App 防繞過盤點；不能僅因 Portal 代理存在就視為這些入口已受保護。

### 2026-10-05：Nginx `auth_request` 方案評估

- 本次為方案與原始碼審查，未修改 Nginx／Dify 程式或部署；checkout 仍為 `4c640ff898ccfd48e0796276c999885ef1b5fdb8`，實際運行版本仍待核對。
- 可繼續沿用原生 Web App；iframe 或一般導向不決定授權安全性。`auth_request` 可作為伺服器端授權閘門，但不能將僅解析 `/chat/<code>` 的範例視為完整整合。
- 現有 Nginx 的 `/api`、`/files`、`/v1` 等為獨立 location；只在 `location /` 加驗證不涵蓋這些入口。需建立路由清單，對使用者端開放必要路由，其他發布／管理入口依用途隔離或封鎖，並限制後端直連。
- `controllers/web/passport.py` 使用 `X-App-Code` 與可選 `user_id`；`controllers/web/wraps.py` 驗證 passport 後以其 claims 決定 App 與 EndUser。代理若只檢查瀏覽器傳來的 App code，無法證明其與實際執行的 App／使用者相同；需驗證並綁定 Portal Session、授權 Bot 及實際 Dify 身分，且逐項核對物件所有權。是否可全部由代理完成或需集中修改 Dify 認證接點，仍待最小整合驗證。
- 優先評估同源部署與 host-only Session Cookie，不預設將 Session Cookie 分享至整個父網域。驗證端點需只接受可信代理的請求資訊；未登入／無權限回應 401／403，授權服務故障時不得放行，並保留必要 CSRF 防護。
- `docker/nginx/docker-entrypoint.sh` 會從 `conf.d/default.conf.template` 產生 `default.conf`；後續實作應使用可版本管理的模板／掛載設定，不直接修改產生檔作為交付。
- 仍以撤權後下一個受保護請求遭拒絕為驗收目標；既有 SSE 串流不會因 `auth_request` 自動重新驗證或中止，串流終止策略待定。
- 本次核對本機程式及 Nginx 官方 `auth_request`／location 文件；未執行聊天、跨帳號、跨 Bot、檔案或撤權整合測試，尚不能宣稱已防止繞過。無部署步驟。

### 2026-10-05：沿用 Dify 現有 Nginx 的候選實作

- 使用者已選定沿用 Dify Compose 現有 `nginx` service；不新增外層、第二個或 Portal Nginx。新增 `/_internal/dify-auth`，只接受共享伺服器秘密，並檢查 Django Session、帳號／Bot 狀態、BotGrant、允許路由、同源寫入、passport 摘要、Portal Session、App 與到期時間；授權失敗時關閉存取。
- 新增 `tools/portal-nginx/default.conf.template` 與 `tools/dify-compose.portal-nginx.yaml`，以 Compose override 將模板掛載至 Dify 原有 `nginx` service，不直接修改產生的 `default.conf`，也不建立新的 Nginx image／service。該 Nginx的公開 listener執行授權；同一 service的原生 listener作為 Portal上游，主機發布僅綁定 `127.0.0.1:8081`。
- 候選 override另建立只含 Django／Gunicorn的 `portal` service，透過 Docker內網供 Dify原有 Nginx存取；新增 `tools/portal-nginx-test.sh` 與操作文件，提供秘密產生、SQLite online backup、完整服務啟動、狀態查看及回復原 Nginx的明確命令。啟動命令合併 Dify原始 Compose與 Portal override，讓原有 Nginx從建立時即掛載授權設定；Portal healthcheck會讓 Nginx等待 Gunicorn可用。候選服務已在本機套用。
- 已成功建置本機 `docker-portal:latest` 候選 image，並以 container執行 `python manage.py check`，結果無問題。候選 Compose為本機 HTTP測試暫時設定 `DJANGO_DEBUG=true`，正式環境必須改用 HTTPS並關閉 DEBUG。
- 已在本機啟動 Portal container並重新建立 Dify原有 Nginx。首次登入 Portal後開啟 `/chat/<code>` 回傳 500；日誌確認 Nginx內部 `auth_request` 使用 `Host: portal:8000`，被 Django `ALLOWED_HOSTS` 以 400拒絕。模板已改為保留原始 `$http_host`；修正後未登入聊天入口正確回傳 401，且不再產生新的 `DisallowedHost`。登入後已能開啟原生 Web App，相關 API回應 200；實際提問、SSE回答與完整隔離驗收仍待確認。
- Portal image重建會改變 container IP；既有 Nginx曾因保留舊 upstream位址回傳 502。Nginx模板已改用內建 Docker DNS動態解析 Portal upstream，不再依賴每次重建 Nginx來更新位址；修復後首頁回應 302導向登入頁，登入頁回應 200。
- `/api/passport`、`/api/login/status` 及暫時的文字聊天 relay 仍送至 Django；其他已審查 API 在 `auth_request` 通過後由 Nginx 直送 Dify。檔案、停止生成、Service API、MCP 與其他未審查發布面在公開 listener 拒絕。
- 新增 6 個 Nginx 授權端點測試及 Portal healthcheck測試，總計 55 個 Portal 測試通過；`check`、migration dry-run、Compose `config --quiet` 及運行中 container 的 `nginx -t` 通過。候選設定已用合併後的統一啟動流程在本機啟動，Portal狀態為 healthy；真實 SSE、跨使用者／Bot 與直連封鎖仍待整合驗收。

### 先前 Portal 基礎驗證紀錄（本次未重跑）

- Python 語法檢查與 `git -C dify-portal diff --check` 通過；使用者已完成 `.venv` 依賴安裝，先前缺少 `ensurepip` 的啟用腳本問題已修復。
- 在 `dify-portal/` 執行 `.venv/bin/python manage.py check --settings=config.test_settings`：無問題。
- 執行 `.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings`：`No changes detected`。
- 執行 `.venv/bin/python manage.py test --settings=config.test_settings`：21 個測試全部通過。測試使用獨立測試資料庫，未建立實際管理員帳號。
- 已產生本機 `.secret-key`（未輸出內容），執行 `.venv/bin/python manage.py migrate --noinput` 成功建立 SQLite 資料表；`collectstatic --noinput` 成功收集 128 個靜態檔案，384 個後處理產物。
- 使用一般設定及 Django test client 發出 HTTPS 請求，`/login/`、`/static/portal/site.css`、`/static/admin/css/base.css` 均回應 200。這不是實際瀏覽器或反向代理驗收。
- 已確認 `.secret-key`、SQLite 資料庫與收集的靜態檔案均被 Git 忽略。
- 先前取得唯讀授權執行 `docker compose ls`，未列出運行中的 Compose 專案；尚未核對其他部署環境或修改 Dify。
- 上述 21 個測試屬於 Portal 基礎階段，不涵蓋後來的代理原型；完整授權整合、負載測試與正式部署均未驗收。
- 使用者已回報可登入 Portal。下一步核對 Dify 執行版本與可用測試 Bot，依調整後的權限控管範圍選定整合方式，完成階段 0 最小授權驗證。

- 本次目標調整已同步更新共用規範、計畫與兩份 README，核對移除日誌帳號辨識待辦與驗收條件；僅變更文件，未修改程式、資料或部署，也未重跑程式測試。
- 已重新審視 `AGENTS.md`：優先驗證現有機制與代理層授權；Token、EndUser 映射及自建 Dify image 不列為預設必做。現有建置 override 保留為候選工具，待選定授權方案再決定是否使用；未修改 Dify 時可採固定版本官方 image。保留防繞過、對話隔離及管理／使用權限分離要求，並限定完整端到端驗收的適用範圍。本次僅核對文件一致性，未修改程式或重跑測試。


### 2026-10-05：文件重新審視與工作區差異

- 本次唯讀核對 `portal/models.py`、`views.py`、`urls.py`、`gateway.py`、migration `0002`、設定、測試清單及代理文件，確認工作區已有候選代理；保留所有既有程式修改，未將其視為本次新增成果。
- `DIFY_GATEWAY_ENABLED` 預設關閉。原型轉送原生 HTML／靜態資源與允許清單內的 API；以內部身分取得 Dify passport，僅保存摘要，綁定 Portal Session、BotGrant 及 App 設定。這是程式盤點結果，不是安全性驗收。
- 原型限制為文字聊天；檔案、語音、獨立 Workflow 及其他未審查路由尚未支援，不能因此勾選完整功能／檔案隔離驗收。原型的精確 Origin 與 passport 寫入防護、上游信任及串流行為仍需實測。
- [代理原型文件](dify-portal/docs/gateway.md) 另記錄 Django Client 連接 Dify 的文字聊天及部分拒絕案例，亦記錄原生入口仍對外開放。這些屬於既有文件紀錄，本次未重新查證；不等於完整瀏覽器或防繞過驗收。其測試結果引用本計畫，但本計畫先前只有 21 個基礎測試紀錄；需補齊代理驗證的命令、數量、版本及結果。
- 當時曾建立只將 Dify Nginx 綁定 loopback 的獨立候選 override，但未套用；後續已由 `dify-compose.portal-nginx.yaml` 統一管理公開與內部 listener，因此移除該重複檔案。正式部署仍須依部署拓撲限制直連。
- `dify-portal/README.md` 仍主要描述基礎階段，後續在代理方案定案時同步更新。原型新增 migration 的實際套用狀態本次未查證。
- 本次只修改 `AGENTS.md` 與 `PLAN.md`，檢查文件差異與一致性；未重跑程式測試、執行 migration 或部署，無需重啟服務。

### 2026-10-05：Portal 本機啟動文件修正

- 修正 `dify-portal/README.md`：明確指定執行目錄，將 Secret Key 設定移至首次 migration 之前，補充用途、讀取優先順序、檔案權限及沿用既有金鑰的說明；區分 Portal 容器尚未提供的 Compose 與既有 Dify 候選 override。
- 已對照 `config/settings.py` 與 `.gitignore` 核對金鑰設定，README 的 `git diff --check` 通過。本次僅修改文件，未產生或讀取實際金鑰內容、執行 migration、重跑程式測試或切換部署，無需重啟服務。

### 2026-10-05：README 與進度文件分工

- Portal README 保留專案用途、本機操作、測試指令、必要的整合未驗收提醒及文件導覽；移除重複的測試數量、候選架構進度與部署待辦。既有功能、授權限制與測試結果沿用本計畫的紀錄，Portal 部署現況及缺少的部署待辦補入階段 3。
- README 的 `git diff --check`、相對連結、程式碼區塊配對及 Secret Key 先於 migration 的順序檢查通過。僅調整文件，未重跑程式或整合測試，無部署或重啟步驟。

### 2026-10-06：根目錄 README 校正

- 移除根 README 過時的測試數量，讓動態進度統一由本計畫維護；修正 `tools/` 目錄樹，補上 Portal README、整合測試文件及常用操作入口。
- 僅調整文件，未重跑程式或整合測試，無部署或重啟步驟。

### 2026-10-05：共同根目錄 Git 忽略設定

- 根目錄 `.gitignore` 加入 `/dify/` 與 `/dify-portal/`，讓兩個子專案繼續獨立管理版本；共同文件與 `tools/` 留在根目錄 repository 管理。
- 使用 `git check-ignore` 與 `git status --short` 確認兩個目錄已忽略。本次僅調整版本管理設定與紀錄，無需部署或重跑程式測試。

### 下一步順序

1. 核對實際運行 image／版本、可用測試 Bot 及既有代理驗證證據，避免把 checkout 與官方 image 的行為混用。
2. 將候選設定套用至 Dify Compose 現有 `nginx` service，確認 Portal連線方式與共享授權秘密；不新增其他 Nginx。
3. 用兩個帳號、不同 Bot 及共同授權 Bot 驗證原生瀏覽器聊天、憑證綁定、越權與撤權；補足檔案所有權及其他需要保留的功能。
4. 部署入口封鎖並檢查替代網域／埠與後端直連，再完成端到端驗收、持久化／並行驗證及部署／回滾文件。回滾不得默默重新開放匿名入口。

### 2026-10-05：代理授權補強與路由檢查

- 本輪先核對運行中的 Compose：Dify API／Web 使用官方 `1.17.1` image，Nginx 仍發布 80／443。後續原始碼審查使用本機 `1.17.1` tag，不以較新的 main 代替運行基準。當時尚未切換服務或套用候選路由設定；後續已改由 `dify-compose.portal-nginx.yaml` 整合。
- 新增 [路由與授權清單](dify-portal/docs/gateway-routes.md)，列出允許的方法、App／passport 綁定、Dify 對話與訊息所有權檢查，以及檔案、停止生成和其他未支援路由的缺口。此為候選代理的審查成果，尚未完成整合驗收或方案定案。
- 發現 `AppTaskService.stop_task` 在舊機制所有權檢查 return 後，仍可能送出 GraphEngine 停止命令；因此移除 Portal 的 stop 允許規則，回應 403 且不轉送。這是原始碼發現，未對其他使用者的任務實際重現；停止功能須在可信任 task 所有權綁定或集中修正 Dify 後恢復並驗收。
- 補強 `/api/passport` 對異常上游回應的處理：要求 JSON 物件、完整三段憑證、符合設定的 App ID／code，以及 UUID 格式的 EndUser ID；失敗回應通用 502，不登記憑證。這是可信任上游回應的一致性檢查，不是自行實作 JWT 簽章驗證，也不接受瀏覽器憑證自行登記。
- 新增跨 Bot 憑證拒絕、異常上游回應回滾、停止端點拒絕測試。於 `dify-portal/` 執行 `.venv/bin/python manage.py test --settings=config.test_settings`：48 個測試通過，內含系統檢查無問題；`.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings`：`No changes detected`。
- 嘗試下載 Playwright 至暫存目錄供隔離瀏覽器測試，網路存取所需的權限未獲使用者允許；因此未完成瀏覽器測試，未把單元測試算成瀏覽器驗收。沒有更動正式依賴、既有帳號、資料庫 migration 或 Dify 原始碼／產生的 Nginx 設定。
- 同步 Portal README 與代理文件；檔案支援仍是需求。下一個實作重點是可信任的檔案／task 所有權來源與原生瀏覽器相容性，再進行入口封鎖與完整驗收。
