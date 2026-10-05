# Dify Portal

Django Portal 的第一批基礎實作，使用 SQLite。共用開發規則與驗收進度位於上層 [AGENTS.md](../AGENTS.md) 與 [PLAN.md](../PLAN.md)。

目前已有登入／POST 登出、UUID 帳號識別、Bot／個別帳號授權模型、Django Admin、授權列表與明細，以及預設關閉的原生 Web App 授權原型。**2026-10-05：54 個自動化測試通過，測試執行時的 Django 系統檢查與 migration 一致性檢查無問題；完整 Dify 整合尚未驗收。**

目前不簽發交接 Token、不提供 Dify 直連入口。Portal 的授權僅保護 Portal 頁面，尚未保護 Dify 原生入口或 API；聊天存取授權整合、部署與並行驗證仍待完成。Dify 後台日誌維持原生顯示，不要求辨識 Portal 帳號或 user_id。請勿將現階段部署當成正式 Bot 權限控管。

目標使用單一 Dify Nginx 與 Django `auth_request` 端點，使用 Dify 原生 passport，未自行簽發交接 Token；候選設定預設不啟用。檔案及停止生成尚未安全開放，原生直連入口也尚未封鎖。詳見[授權閘門](docs/gateway.md)及[路由與授權清單](docs/gateway-routes.md)。

## 本機開發

使用 Python 3.14 與 Django 5.2 LTS。先確保系統已提供對應的 `venv`／`ensurepip`，在本目錄執行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

若因缺少 `ensurepip` 建立失敗，且系統 Python 已有 pip，可改用以下方式補齊環境與安裝依賴，無須安裝到系統 Python：

```bash
python3 -m venv --without-pip .venv
python3 -m pip --python .venv/bin/python install pip -r requirements.txt
```

完成後可在 `dify-portal/` 執行 `source .venv/bin/activate`。啟用環境只會調整目前終端機的 Python 路徑，不會自動安裝套件。


產生本機 Secret Key（不輸出內容，已加入 `.gitignore`；檔案存在時會拒絕覆寫）：

```bash
python3 - <<'PY'
import os
import secrets
with os.fdopen(os.open('.secret-key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as target:
    target.write(secrets.token_urlsafe(64))
PY
```

首次啟動：

```bash
export DJANGO_DEBUG=true
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

開啟 `http://127.0.0.1:8000/admin/`，建立使用者、Bot 與 Bot 授權。Bot 預設停用；啟用且明確授權後才會出現在該帳號的首頁。管理員也需要 Bot 授權，管理權限不等於使用權限。一般帳號無須給予 staff 或 superuser。

`.env.example` 是設定參考，Django 不會自動讀取 `.env`。本機資料預設位於 `data/db.sqlite3`；可用 `PORTAL_DATA_DIR` 指定目錄。`DJANGO_DEBUG` 預設為 false，會啟用 HTTPS 導向與 Secure Cookie，本機 HTTP 開發才設為 true。

## 檢查與測試

```bash
.venv/bin/python manage.py check --settings=config.test_settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings
.venv/bin/python manage.py test --settings=config.test_settings
```

`config.test_settings` 只供測試，使用固定測試金鑰與快速密碼雜湊，禁止用它啟動服務。測試涵蓋帳號隔離、直接網址越權、撤權／停用、管理與使用權限分離、登入與登出 CSRF、外部導向防護、Session 失效及改名後識別穩定。

## 部署狀態

目前尚未提供 Compose 或正式部署設定。預計使用單一 Portal container，SQLite 完整資料目錄掛載到持久化儲存，不需另外啟動資料庫 container。Gunicorn 與 WhiteNoise 已列入依賴，正式設定須在整合驗證後完成。

部署前仍需完成：登入嘗試限制、受信任代理／HTTPS 設定、完整依賴鎖定、靜態檔案收集、資料一致性備份與還原測試，以及 Dify 原生入口、檔案與 API 的授權防護。持久化不等於備份，亦不可直接以 SQLite 檔案搬移取代正式的 PostgreSQL 遷移驗證。
