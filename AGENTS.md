# AGENTS.md

本文件適用於整個儲存庫；以下路徑皆相對於專案根目錄。

## 1. 專案結構
- dify/：Dify 原始碼，web 服務與後端服務。
- dify-portal/：使用者登入頁面，帳號與權限管理。
- tools/：專案啟動工具

## 2. 通則
- 使用繁體中文，程式碼的變數/函式等識別字使用英文。
- Dify 整合設定透過 tools/ 下的 Compose override 與 Nginx 模板調整。

## 3. 禁止事項
- 禁止修改 dify/ 下內容。
- 禁止執行 `docker compose down -v` 與 `docker compose down --volumes`。
- 禁止將私鑰、密碼、API Key、Session 憑證或完整認證 Token 寫入 Git、前端靜態產物、URL 或一般日誌中。

## 4. 指令
以下指令於專案根目錄執行：
- `./tools/portal-nginx-test.sh start`：啟動專案
- `./tools/portal-nginx-test.sh stop`：停止專案
