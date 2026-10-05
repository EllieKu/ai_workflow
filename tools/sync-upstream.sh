#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# Dify Upstream Sync Script
#
# 目錄結構：
#
# ai_workflow/
# ├── dify/
# ├── dify-portal/
# └── tools/
#     └── sync-upstream.sh
#
# 用途：
#   將官方 Dify upstream/main 同步至：
#
#   upstream/main -> local main -> origin/main
#
# 注意：
#   - 不處理 feature branch
#   - 不允許 main 存在自訂 commit
#   - 不允許工作區有未提交修改
#   - 只允許 Fast-forward
# ============================================================

MAIN_BRANCH="main"
UPSTREAM_REMOTE="upstream"
ORIGIN_REMOTE="origin"

# ------------------------------------------------------------
# 找到 Dify repository
# ------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIFY_DIR="$(cd "$SCRIPT_DIR/../dify" && pwd)"

echo "========================================"
echo " Dify Upstream Sync"
echo "========================================"
echo
echo "Repository:"
echo "  $DIFY_DIR"
echo

cd "$DIFY_DIR"

# ------------------------------------------------------------
# 1. 確認是 Git repository
# ------------------------------------------------------------

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: $DIFY_DIR 不是 Git repository。"
    exit 1
fi

# ------------------------------------------------------------
# 2. 確認工作區乾淨
# ------------------------------------------------------------

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR: Dify 工作區有尚未提交的修改。"
    echo
    git status --short
    echo
    echo "請先 commit、stash 或處理修改後再執行同步。"
    exit 1
fi

# ------------------------------------------------------------
# 3. 確認 origin / upstream 存在
# ------------------------------------------------------------

if ! git remote get-url "$ORIGIN_REMOTE" >/dev/null 2>&1; then
    echo "ERROR: 找不到 remote '$ORIGIN_REMOTE'。"
    exit 1
fi

if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
    echo "ERROR: 找不到 remote '$UPSTREAM_REMOTE'。"
    echo
    echo "請先設定 upstream，例如："
    echo "git remote add upstream https://github.com/langgenius/dify.git"
    exit 1
fi

echo "origin:"
echo "  $(git remote get-url "$ORIGIN_REMOTE")"
echo
echo "upstream:"
echo "  $(git remote get-url "$UPSTREAM_REMOTE")"

# ------------------------------------------------------------
# 4. Fetch
# ------------------------------------------------------------

echo
echo "Fetching origin..."
git fetch "$ORIGIN_REMOTE"

echo
echo "Fetching upstream..."
git fetch "$UPSTREAM_REMOTE"

# ------------------------------------------------------------
# 5. 切換 main
# ------------------------------------------------------------

CURRENT_BRANCH="$(git branch --show-current)"

if [[ "$CURRENT_BRANCH" != "$MAIN_BRANCH" ]]; then
    echo
    echo "Switching branch:"
    echo "  $CURRENT_BRANCH -> $MAIN_BRANCH"
    git switch "$MAIN_BRANCH"
fi

# ------------------------------------------------------------
# 6. 檢查 main 是否有自己的 commit
# ------------------------------------------------------------

LOCAL_ONLY="$(
    git rev-list --count \
    "$UPSTREAM_REMOTE/$MAIN_BRANCH..$MAIN_BRANCH"
)"

UPSTREAM_ONLY="$(
    git rev-list --count \
    "$MAIN_BRANCH..$UPSTREAM_REMOTE/$MAIN_BRANCH"
)"

echo
echo "========================================"
echo " Status"
echo "========================================"
echo
echo "Local-only commits   : $LOCAL_ONLY"
echo "Upstream new commits : $UPSTREAM_ONLY"
echo

# main 原則上應完全追蹤 upstream/main
if [[ "$LOCAL_ONLY" -ne 0 ]]; then
    echo "ERROR: main 有 upstream/main 不存在的 commit。"
    echo
    echo "為避免產生非預期 merge，已停止同步。"
    echo
    echo "請檢查："
    echo
    echo "  git log upstream/main..main --oneline"
    echo
    exit 1
fi

# ------------------------------------------------------------
# 7. 已是最新版
# ------------------------------------------------------------

if [[ "$UPSTREAM_ONLY" -eq 0 ]]; then
    echo "Dify main 已經是官方最新版。"
    echo
    exit 0
fi

# ------------------------------------------------------------
# 8. 顯示官方新增 commits
# ------------------------------------------------------------

echo "Official Dify new commits:"
echo "----------------------------------------"

git log \
    --oneline \
    "$MAIN_BRANCH..$UPSTREAM_REMOTE/$MAIN_BRANCH"

echo "----------------------------------------"
echo

# ------------------------------------------------------------
# 9. 人工確認
# ------------------------------------------------------------

read -r -p "同步以上更新到 main？ [y/N] " ANSWER

if [[ ! "$ANSWER" =~ ^[Yy]$ ]]; then
    echo
    echo "已取消。沒有修改任何內容。"
    exit 0
fi

# ------------------------------------------------------------
# 10. Fast-forward main
# ------------------------------------------------------------

echo
echo "Updating local main..."

git merge \
    --ff-only \
    "$UPSTREAM_REMOTE/$MAIN_BRANCH"

# ------------------------------------------------------------
# 11. Push 到自己的 Fork
# ------------------------------------------------------------

echo
echo "Pushing main to origin..."

git push \
    "$ORIGIN_REMOTE" \
    "$MAIN_BRANCH"

# ------------------------------------------------------------
# Done
# ------------------------------------------------------------

echo
echo "========================================"
echo " Sync completed"
echo "========================================"
echo
echo "upstream/main -> local main -> origin/main"
echo