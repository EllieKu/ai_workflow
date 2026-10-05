# Dify Portal

Django Portal 負責使用者登入、Bot 授權與可用機器人列表，使用 SQLite 保存 Portal 資料，聊天沿用 Dify 原生 Web App。

Portal 基礎功能可供本機開發使用；Dify 存取授權整合尚未完成驗收，請勿視為正式權限控管。實作進度與驗收結果見 [PLAN.md](../PLAN.md)。

## 文件導覽

- [共用開發規則](../AGENTS.md)：開發範圍、身分安全與交付要求。
- [實作計畫](../PLAN.md)：設計決策、進度、測試結果、部署待辦與驗收清單。
- [授權閘門](docs/gateway.md)：Dify 整合機制、設定方式、功能限制與部署注意事項。
- [路由與授權清單](docs/gateway-routes.md)：各路由的授權、所有權檢查與支援範圍。

## 本機開發

以下指令均在 `dify-portal/` 目錄執行。若目前位於共同根目錄 `ai_workflow/`，先執行：

```bash
cd dify-portal
```

首次安裝依賴：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

首次設定 Secret Key：

Secret Key 是 Django Portal 用來簽章及驗證 Session 等資料的伺服器秘密金鑰。必須在第一次執行 `migrate`、建立管理員或啟動服務之前準備好，否則 Django 無法載入設定。

以下指令只需執行一次，會將隨機金鑰存入目前目錄的 `.secret-key`，不輸出內容，並以 `0600` 權限建立檔案（僅擁有者可讀寫）。檔案已加入 `.gitignore`，請勿提交或分享。若 `.secret-key` 已存在，請略過此步驟；指令會拒絕覆寫既有檔案。

```bash
python3 - <<'PY'
import os
import secrets
with os.fdopen(os.open('.secret-key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as target:
    target.write(secrets.token_urlsafe(64))
PY
```

Django 會優先讀取環境變數 `DJANGO_SECRET_KEY`；未設定時，讀取 `DJANGO_SECRET_KEY_FILE` 指定的檔案，預設為 `dify-portal/.secret-key`。金鑰至少需有 50 個字元，上述指令產生的長度符合要求。若已透過環境變數提供有效金鑰，可略過產生本機檔案。

後續啟動請沿用同一份金鑰。更換金鑰會使既有登入 Session 等簽章資料失效，使用者需要重新登入。

首次初始化資料庫、建立管理員並啟動：

```bash
export DJANGO_DEBUG=true
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

後續啟動（仍在 `dify-portal/` 目錄執行）：

```bash
export DJANGO_DEBUG=true
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

`.env.example` 是設定參考，Django 不會自動讀取 `.env`。本機資料預設位於 `data/db.sqlite3`；可用 `PORTAL_DATA_DIR` 指定目錄。`DJANGO_DEBUG` 預設為 false，會啟用 HTTPS 導向與 Secure Cookie，本機 HTTP 開發才設為 true。

## 檢查與測試

```bash
.venv/bin/python manage.py check --settings=config.test_settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings
.venv/bin/python manage.py test --settings=config.test_settings
```

`config.test_settings` 只供測試，使用固定測試金鑰與快速密碼雜湊，禁止用它啟動服務。驗收範圍與已執行的測試結果統一記錄於 [PLAN.md](../PLAN.md)。
