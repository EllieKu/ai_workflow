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

## 開發 Portal

需要修改 Portal程式並同時連接 Dify時，在共同根目錄執行：

```bash
./tools/portal-nginx-test.sh dev-start
```

此模式同樣啟動完整 Dify與單一公開的 Dify Nginx，但 Portal container改用 Django開發伺服器，並將本機`dify-portal/`掛載至 container。修改 Python、template或靜態檔案後，Django會自動重新載入，不需重新 build；瀏覽器仍從`http://localhost/`進入。

新增或變更 Python套件、Dockerfile、Compose或 Nginx設定時，需重新執行`dev-start`。此模式會直接使用現有`dify-portal/data/db.sqlite3`，只供本機開發，不可用於正式環境。

## 停止完整 Dify 與 Portal

```bash
./tools/portal-nginx-test.sh stop
```

`stop`會停止合併設定中的 Dify與 Portal container，但不會刪除 container、Portal SQLite、Dify資料或 Docker volumes。之後可再次使用`start`啟動。

## 查看狀態

```bash
./tools/portal-nginx-test.sh status
```

查看 Portal與 Nginx最近日誌：

```bash
./tools/portal-nginx-test.sh logs
```

此指令透過 Compose service名稱合併顯示 Portal與 Nginx最近 160行輸出；若要持續追蹤單一 container，可直接使用 `docker logs -f <container>`。

設定異常或需要強制重新建立 Dify原有 Nginx時：

```bash
./tools/portal-nginx-test.sh reload-nginx
```

## 回復原本 Dify Nginx

```bash
./tools/portal-nginx-test.sh rollback
```

回復後 Dify原本的公開入口會再次直接開放，因此只用於中止候選整合測試，不代表仍有 Portal授權保護。Rollback不會刪除 Portal資料、備份、image或 container volume。
