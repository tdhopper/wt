#!/bin/bash
# Send desktop notification when worktree is ready
#
# macOS: Uses osascript for native notifications
# Linux: Uses notify-send if available

TITLE="Worktree Ready"
MESSAGE="Branch '$WT_BRANCH_NAME' is ready at $WT_WORKTREE_PATH"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\""
elif command -v notify-send &> /dev/null; then
    # Linux with notify-send
    notify-send "$TITLE" "$MESSAGE"
fi
