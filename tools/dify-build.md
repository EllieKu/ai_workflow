# Dify 原始碼建置測試

目前候選基準為 `4c640ff898ccfd48e0796276c999885ef1b5fdb8`（`1.17.1-502-g4c640ff898`），尚未通過 image 建置與整合驗證，不是已驗收的正式版本。現有 `feature/portal-auth` 分支在檢查時指向該 commit。

以下從共同根目錄執行。先確認工作區修改，再切換現有客製分支；不在 `main` 開發：

```bash
cd dify
git status --short
git switch feature/portal-auth
git rev-parse HEAD

export DIFY_BUILD_COMMIT="$(git rev-parse HEAD)"
export DIFY_BUILD_TAG="$(git rev-parse --short=10 HEAD)-baseline-1"
cd docker
```

需先準備 `docker/.env`。每次內容改動使用新 tag；有未提交修改時，tag 要標記開發建置，不能只憑 commit 宣稱可重現。正式交付須提交原始碼並記錄 image ID／digest。

先驗證設定，再建置 API 與 Web：

```bash
docker compose -f docker-compose.yaml -f ../../tools/dify-compose.build.yaml config --quiet
docker compose -f docker-compose.yaml -f ../../tools/dify-compose.build.yaml build api web
```

API 與 Web 都以 `dify/` 根目錄作為 build context，使用各自 Dockerfile；不能以 `api/` 或 `web/` 目錄作為 context。建置會下載基礎 image 與依賴，尚未實測耗時及資源需求。

API、worker、worker_beat、api_websocket 使用同一個客製 API image；Web 使用客製 Web image。WebSocket 仍受官方 `collaboration` profile 控制，不會因 override 自動啟用。Agent backend、sandbox、plugin daemon、資料庫等仍沿用原 Compose image，與目前 checkout 的相容性待驗證；本設定不是整套 Dify 所有元件的原始碼建置。

build 成功後，才啟動並查看狀態：

```bash
docker compose -f docker-compose.yaml -f ../../tools/dify-compose.build.yaml up -d --no-build
docker compose -f docker-compose.yaml -f ../../tools/dify-compose.build.yaml ps
```

所有操作都使用同一組 `-f` 與 build 環境變數，避免誤用官方 API／Web image。若環境已有資料，啟動前先備份資料庫與儲存目錄，因啟動流程可能執行 migration；勿用 `down -v` 重建。

後續修改後使用新的 tag，重新 build，再執行相同的 `up` 命令。保留上一組 API／Web image 與對應資料備份；回滾時指定上一組 tag。如果資料庫 schema 已變更，須先確認相容性並依驗證過的還原方案處理，單純換回舊 image 不保證可回滾。

目前只通過 Compose `config --quiet` 驗證，尚未執行 build、啟動、對話或 Portal 整合驗收。
