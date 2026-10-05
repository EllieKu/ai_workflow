# 代理路由與授權檢查

2026-10-05，依本機 Dify `1.17.1` tag 原始碼核對；使用 `git -C dify show 1.17.1:<path>`，不混用目前 main。下表是原型的程式審查結果，不能替代實際瀏覽器與跨帳號整合驗收。

## 已開放的候選路由

「綁定 passport」表示 Portal 同時檢查有效登入、啟用帳號／Bot、當前 BotGrant、passport 摘要、登入 Session、App ID／code 與到期時間。再由 Dify 驗證原生 passport 簽章、解析實際 App／EndUser。寫入另要求精確同源 Origin。

| 方法／路由 | Portal 檢查 | Dify 的物件隔離／用途 |
| --- | --- | --- |
| GET／HEAD `/chat/<code>` | 登入、Bot 啟用、BotGrant | 原生 HTML；不等於後續 API 授權 |
| GET／HEAD `/_next/static/<asset>` | 登入、限定資源路徑 | 共用 JS／CSS，不含對話資料 |
| GET `/api/system-features` | 登入 | 共用系統功能設定，無 Bot 物件 |
| GET `/api/webapp/access-mode` | 伺服器核對 Bot code 與授權；不轉送客戶端 App ID | App 存取模式 |
| GET `/api/passport` | 授權 Bot；以隨機內部 session ID 取得憑證；核對 App ID／code 及 EndUser ID 格式 | `WebPassportService` 解析該 App 的 EndUser；Portal 只登記摘要 |
| GET `/api/login/status` | Portal 自行判定登入與 passport 綁定 | 不採用前端傳來的 user_id 判定身分 |
| GET `/api/site`、`parameters`、`meta` | 綁定 passport | 該 App 的原生頁面設定 |
| GET `/api/conversations` | 綁定 passport | `WebConversationService.pagination_by_last_id` 以 App／使用者列出對話 |
| GET `/api/messages` | 綁定 passport | `MessageService.pagination_by_first_id` 先以 `ConversationService.get_conversation` 檢查對話；分頁訊息限於該對話 |
| POST `/api/chat-messages` | 綁定 passport、Origin；僅允許文字輸入欄位 | Dify 原生生成流程；既有 conversation／parent message 的完整隔離仍須實機驗證 |
| DELETE `/api/conversations/<id>`；POST `…/<id>/name` | 綁定 passport、Origin | `ConversationService` 檢查對話所屬 App／EndUser |
| PATCH `/api/conversations/<id>/pin`、`unpin` | 綁定 passport、Origin | pin 檢查對話；unpin 僅刪除該 App、該使用者自己的釘選 |
| POST `/api/messages/<id>/feedbacks`；GET `…/<id>/suggested-questions` | 綁定 passport；POST 另檢查 Origin | `MessageService.get_message` 同時篩選 App、來源及 EndUser |

相關原始碼位於 Dify tag 的 `api/controllers/web/{wraps,completion,conversation,message}.py`、`api/services/{web_passport_service,conversation_service,web_conversation_service,message_service}.py`。Portal 不解析任意瀏覽器 JWT 作為授權依據；只有直接向可信任上游取得的憑證才可登記。

## 暫不放行的路由與原因

| 路由 | 目前行為 | 開放前需要完成 |
| --- | --- | --- |
| POST `/api/chat-messages/<task_id>/stop` | 403，不送至 Dify | 建立可信任的 task → 使用者／Bot 所有權證明，或集中修正 Dify 的停止授權；實測跨使用者與跨 Bot 拒絕 |
| `/api/files/upload`、`remote-files/upload` | 403 | 上傳結果的所有權登記、檔案大小／型別限制，以及聊天引用檔案 ID 的所有權檢查 |
| `/files/…` | 404 | 上傳及生成檔案均需有可信任的使用者／Bot 關聯，下載時檢查當前授權；保留必要的 Content-Disposition 等安全標頭 |
| 語音、獨立 Workflow、分享及未列出的 `/api/…` | 403（未持有效憑證時先拒絕認證） | 逐一盤點路由、方法、App 解析與物件授權後才加入 |
| `/v1/…`、`/console/api/…`、`/mcp/…` 等 | Portal 無路由，404 | 部署端另行限制原生直連；管理用途與使用者入口分離 |

### 停止生成的原始碼發現

`api/controllers/web/completion.py` 的 `ChatStopApi` 呼叫 `AppTaskService.stop_task`。在 `api/services/app_task_service.py` 中，舊機制 `AppQueueManager.set_stop_flag` 結束後，ADVANCED_CHAT／WORKFLOW 仍會呼叫 `GraphEngineManager.send_stop_command(task_id)`。

`api/core/app/apps/base_app_queue_manager.py` 的 `set_stop_flag` 在任務不存在或所有人不符時僅 return，沒有回傳可供呼叫端判斷的授權結果。因此不能由前段檢查推論後段命令已通過所有權驗證。本輪先移除 Portal 的 stop 允許規則；未修改 Dify，也未對其他人的實際工作發送停止命令。這是原始碼發現，尚非實機重現。

### 檔案與原生 UI 的關係

Dify 原生 UI 會另外呼叫上傳 API，並以 `/files/…` 簽名網址顯示或下載檔案。`api/controllers/files/upload_file_delivery.py` 的預覽端點使用檔案簽名，不帶 Portal 的 Bot 授權；有效簽名不能直接證明目前登入者擁有檔案。

不能因為模型回答、Markdown 或使用者輸入出現某個檔案網址，就將它登記成該人的檔案。工具生成檔案也需檢查可信任的來源關聯。檔案仍是需求，暫時封鎖只是原型的限制。

## 部署邊界

所有上述規則只保護經 Portal 的請求。原生 Dify 80／443 尚未收斂至內部入口；在完成直連限制、替代發布入口檢查與實機驗收前，不能宣稱防繞過已完成。瀏覽器相容性、SSE 中斷、負載及檔案驗收仍待執行。
