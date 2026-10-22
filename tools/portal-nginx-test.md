# Portal 與 Dify Web App 整合測試

本流程沿用 Dify Compose 現有的 `nginx` service，不建立第二個 Nginx。候選 override 另外建立只執行 Django／Gunicorn 的 `portal` service，讓原有 Nginx透過 Docker內網代理 Portal並執行 `auth_request`。

## 影響範圍

- `start` 會先以 SQLite online backup建立 Portal資料庫備份，再合併 Dify原始 Compose與 Portal override，一次啟動目前 profile使用的完整 Dify服務及 Portal。
- Compose只會建立設定或 image有變更的 service；既有且設定未變的 container不會因每次 `start` 全部重建。
- Portal具有 healthcheck，Dify原有 Nginx會等 Gunicorn可回應後再啟動。
- Nginx透過 Docker DNS動態解析 Portal；Portal container重建並更換 IP後，不需要為此重新建立 Nginx。
- 公開 `80/443` 會改用 Portal授權路由；同一個 Nginx另在 container內監聽 `8081`，主機僅發布為 `127.0.0.1:8081`。
- `.portal-auth-secret` 由工具首次產生，權限為 `0600`，已被 Portal repository忽略，不會輸出內容或寫入 Git。
- 候選設定為配合本機 `http://localhost/` 測試而啟用 `DJANGO_DEBUG=true`，避免 Django永久導向尚未設定的 HTTPS；不得直接當成正式環境設定。

## 套用前檢查

### Portal 獨立環境設定

首次設定可在共同根目錄執行（已有 `.env` 時請直接編輯，不要覆蓋）：

```bash
cp dify-portal/.env.example dify-portal/.env
```

在 `dify-portal/.env` 設定 Portal 的連線參數，例如主機區網 IP 為 `192.168.1.100`：

```dotenv
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],192.168.1.100
DJANGO_CSRF_TRUSTED_ORIGINS=http://192.168.1.100
```

保留 `localhost` 供健康檢查使用；使用非 80 埠時，origin 需附上埠號。`.env` 已由 Git 忽略。

腳本的 `--env-file` 只讀取 `dify/docker/.env`，用於 Compose 變數替換；Portal service 另透過 `env_file` 將 `dify-portal/.env` 的變數直接傳入容器。Portal `.env` 必須存在，首次使用請從範例複製。`environment` 的同名設定優先於 `env_file`；shell 匯出的同名變數不會覆蓋 `.env` 中直接填寫的值（若值含 `${...}`，仍會進行 Compose 插值）。

Compose override 將 `DJANGO_ALLOWED_HOSTS` 以相同名稱傳入容器，再由 Django 讀取為 `ALLOWED_HOSTS`；未設定時由 Django 預設為 localhost／loopback，空字串則會產生空白名單。既有環境檔若使用 `PORTAL_ALLOWED_HOSTS`，須將名稱改成 `DJANGO_ALLOWED_HOSTS`，舊名稱不再讀取。此清單填寫 Portal 的網域或 IP，不含協定、埠號或路徑，也不是連線者電腦的 IP。

部署參數統一由 `.env` 提供，Compose 以相同名稱傳入容器：

| 變數 | `.env.example` 的建議值 |
| --- | --- |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 空字串 |
| `DJANGO_DEBUG` | `true`（僅供本機 HTTP） |
| `DJANGO_TRUST_PROXY` | `true`（信任此整合的 Nginx） |
| `DJANGO_HSTS_SECONDS` | `0` |

Compose 不再為這五項設定提供預設值。缺少變數時由 Django 使用自身預設值；空字串不等於未設定，DEBUG、代理信任與 HSTS 不可留空。Django 的 DEBUG 與代理信任預設為 `false`，本機 HTTP 整合請保留範例中的明確值。

既有 `.env` 的 `PORTAL_CSRF_TRUSTED_ORIGINS` 須改名為 `DJANGO_CSRF_TRUSTED_ORIGINS` 並保留值；不再讀取舊名稱。舊範例的 DEBUG 與代理設定曾被 Compose 固定值覆蓋，遷移時應明確設為 `true`，以維持本機 HTTP 整合行為。

`PORTAL_DATA_DIR`、`DIFY_UPSTREAM_URL` 與 `DIFY_GATEWAY_ENABLED` 由 Compose 管理，請勿在 Portal `.env` 重複設定。金鑰維持 `.secret-key` 掛載與腳本讀取 `.portal-auth-secret` 的方式。直接執行 Django 不會自動載入 `.env`，須自行匯出需要的環境變數；本機直接啟動時，請依是否經過可信任代理設定 `DJANGO_TRUST_PROXY`。

修改後執行下方 `check`，再使用 `start`重建套用設定。其他電腦透過 `http://<主機區網 IP>/` 存取，主機防火牆須允許所需內網連入公開埠；不可對外開放內部 8081 入口。

確認 `dify-portal/.secret-key`、`dify-portal/data/db.sqlite3` 與 `.venv` 已存在，並在共同根目錄執行：

```bash
./tools/portal-nginx-test.sh check
```

## 啟動完整 Dify 與 Portal

```bash
./tools/portal-nginx-test.sh start
```

不要另行先執行只讀取 `dify/docker/docker-compose.yaml` 的 `docker compose up -d`；`start`已使用合併後的設定啟動整套服務，確保 Nginx從建立時就掛載 Portal授權設定。

完成後開啟：

```text
http://localhost/
```

依序驗證 Portal登入、授權 Bot列表、開啟原生 Dify Web App、送出文字問題、SSE回答與歷史紀錄。再驗證未登入、未授權 Bot、跨 Bot憑證、登出與撤權後的請求遭拒絕。

本輪仍不驗收檔案、語音與停止生成；公開 listener會拒絕尚未審查的路由。

## 停止完整 Dify 與 Portal

```bash
./tools/portal-nginx-test.sh stop
```

`stop`會停止合併設定中的 Dify與 Portal container，但不會刪除 container、Portal SQLite、Dify資料或 Docker volumes。之後可再次使用`start`啟動。

## 查看狀態

```bash
./tools/portal-nginx-test.sh status
```

## 重新建立 Nginx

設定異常或需要強制重新建立 Dify原有 Nginx時：

```bash
./tools/portal-nginx-test.sh reload-nginx
```
