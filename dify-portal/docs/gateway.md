# 原生 Web App 授權閘門

目前驗證目標是官方 Dify API／Web image `1.17.1`，沿用 Dify HTML、JavaScript、CSS 與聊天 UI，不修改 Dify 原始碼或日誌顯示。

目標採用單一 Dify Nginx 作為公開入口，以 Django 內部端點執行 `auth_request`。此版本尚未切換現有入口，`DIFY_GATEWAY_ENABLED` 預設 false；尚未完成實際 Nginx 與瀏覽器驗收，不能宣稱正式整合完成。

## 授權機制

- `/chat/<code>` 及已審查的 `/api/` 由 Nginx 在每次請求以 `auth_request` 檢查 Django Session、帳號／Bot 啟用狀態及 BotGrant。實際 API內容由 Nginx直接傳給 Dify。
- `/api/passport` 不採用瀏覽器傳入的 `user_id`。Portal 以使用者＋Bot＋Dify App 設定建立隨機內部 session ID，向 Dify 原生 passport 端點取得憑證，並確認回傳的 App ID／code 符合 Bot 設定。
- Portal 只儲存 passport 的 SHA-256 摘要，綁定當次 Portal Session、授權紀錄與到期時間。後續請求須符合這些關聯，避免只換 `X-App-Code` 就使用另一個 Bot 的 passport。
- 不將 Portal 帳號／工號送入 Dify，也不修改 Dify 原生 `user_id` 語意。內部關聯只用於對話隔離與穩定歷史。
- Nginx只把 Portal Session送至內部授權端點；Django授權端點不回傳 Session或秘密給 Dify。寫入 API 同時要求精確的同源 Origin與已綁定 passport；原有 Portal表單仍使用 Django CSRF。
- 首次 passport 解析在 SQLite IMMEDIATE transaction 內序列化，避免原生 EndUser 缺少唯一約束導致並行建立不同歷史。此處上游呼叫 timeout 為 5 秒；聊天與串流不持有資料庫 transaction。並行負載與 worker 行為仍需驗證。
- 撤權或登出後的下一個請求遭拒絕；已開始的串流允許完成或逾時，本原型不主動中止既有串流。

## 目前功能範圍

原型只允許已盤點的文字聊天、歷史與相關操作路由。檔案上傳／下載、語音、獨立 Workflow 執行、公開分享及其他未驗證路由暫不開放。檔案功能仍是後續待辦，不代表取消保留 Dify 原生功能的目標。

停止生成也暫時拒絕：1.17.1 的原始碼顯示後段停止命令未依前段所有權檢查結果決定是否執行。各端點的檢查分工、發現與待辦見[路由清單](gateway-routes.md)。

原生 Web App 的檔案下載使用獨立 `/files/` 簽名網址；僅驗證 Portal 登入不足以確認該檔案屬於哪位使用者／Bot。需先完成上傳、引用、下載及產生檔案的所有權設計，才能安全開放。

## 單一 Nginx 候選部署

目前 Dify 的 80／443 仍對外開放，**尚未封鎖原生入口繞過**。不得只開啟 gateway flag 就宣稱有完整存取保護。

候選設定位於上層 `tools/portal-nginx/default.conf.template` 與 `tools/dify-compose.portal-nginx.yaml`。同一個 Dify Nginx提供公開 listener與原生內部 listener；後者在主機只發布至 `127.0.0.1:8081`，供 Portal取得 passport，避免公開路由再次代理回 Portal。此設定尚未套用。主機本機管理者仍能連到內部埠，這不是隔離不受信任本機帳號的方案。

在確認接受本輪測試功能範圍、完成瀏覽器驗證與部署檢查後，才進行切換。不得套用自建 image override；本原型使用官方 image。

準備步驟為：備份 Portal SQLite、建立不寫入 Git 的共享授權秘密、設定 `PORTAL_UPSTREAM`，再以 `DIFY_GATEWAY_ENABLED=true`、`DIFY_UPSTREAM_URL=http://127.0.0.1:8081` 與相同的 `DIFY_AUTH_REQUEST_SECRET` 啟動 Portal。`.env.example` 仍只供參考，不會自動載入。

`auth_request` 不會讀取原始 JSON body。為避免使用聊天 body 引用尚未驗證所有權的檔案 ID，候選設定暫時仍把 `/api/chat-messages` 交給 Django做文字輸入過濾與 SSE relay。完成 Dify實際版本的檔案引用隔離驗證後，才可把這條高流量路由改為 Nginx直送。

正式部署還需驗證 HTTPS、可信任代理、埠與防火牆、Dify 對外 URL 設定、SSE timeout，以及所有替代入口。若回復原 Compose 埠設定，代表重新開放 Dify 直連，不能當作維持相同授權保護的回滾方案。

## 已完成驗證

- Django 單元／請求測試通過；結果詳見根目錄 `PLAN.md`。
- 使用獨立暫存 Portal 測試資料庫，以 Django Client 實際提交登入表單，連接正在運行的官方 Dify：取得原生 HTML、passport、site、parameters、conversations，並發送一次測試問題，收到 `message_end`。
- 跨帳號使用 passport、撤權後請求與登出後請求皆遭拒絕。Dify 留下一筆測試對話，沒有修改既有 Portal 帳號。
- 此驗證不是瀏覽器操作測試，也未代表原生公開入口已封鎖、檔案已隔離或負載驗收完成。
