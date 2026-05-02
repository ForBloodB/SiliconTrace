#!/usr/bin/env bash
# Poll TASK_BOARD.md for Claude-DONE tasks and trigger Codex CLI.
# Called by cron every 15 minutes.

set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
PROJECT_DIR="/home/mufire/SiliconTrace"
TASK_BOARD="$PROJECT_DIR/TASK_BOARD.md"

cd "$PROJECT_DIR"

# Check model分工 state: 0 = Claude reviewer / GPT modifier, 1 = GPT reviewer / Claude modifier
MODE_STATE=$(grep -A1 '# 模型分工' "$TASK_BOARD" | grep '当前状态为' | grep -o '[0-9]')

if [ "$MODE_STATE" = "0" ]; then
    # Claude is reviewer, GPT is modifier → look for Claude-DONE (Claude finished reviewing, GPT needs to act)
    # But wait - Claude-DONE means Claude completed a fix task. In state 0, Claude is reviewer not modifier.
    # Actually: Claude-DONE = Claude已完成，等待GPT审核. This happens when state=1 and Claude finished fixing.
    # In state 0, GPT should look for Claude-DONE to review. But we're triggering Codex (GPT).
    # So we should look for Claude-DONE tasks when state=0? No...
    # Let me re-read the rules:
    # - state 0: Claude=reviewer, GPT=modifier → GPT looks for Claude-NEEDS_FIX? No, GPT writes code, Claude reviews.
    #   Claude reviews GPT-DONE tasks. GPT doesn't need to be triggered in state 0.
    # - state 1: GPT=reviewer, Claude=modifier → GPT reviews Claude-DONE tasks.
    #
    # So Codex should be triggered when:
    #   state=1 AND there are Claude-DONE tasks → GPT reviews them
    #   state=0 AND there are Claude-NEEDS_FIX tasks → Wait, that's not right either.
    #
    # Actually in state 0: GPT is modifier, Claude is reviewer.
    # GPT writes code → marks GPT-DONE → Claude reviews.
    # If Claude marks Claude-NEEDS_FIX → GPT needs to fix → GPT should be triggered.
    #
    # So: state=0 + Claude-NEEDS_FIX → trigger Codex (GPT fixes)
    #     state=1 + Claude-DONE → trigger Codex (GPT reviews)

    MATCH_STATUS="Claude-NEEDS_FIX"
else
    MATCH_STATUS="Claude-DONE"
fi

# Find tasks with the target status
FOUND=$(grep -c "状态: $MATCH_STATUS" "$TASK_BOARD" || true)

if [ "$FOUND" -eq 0 ]; then
    echo "$(date): No $MATCH_STATUS tasks found. Skipping."
    exit 0
fi

echo "$(date): Found $FOUND $MATCH_STATUS task(s). Triggering Codex..."

# Build the prompt for Codex
if [ "$MODE_STATE" = "0" ]; then
    PROMPT="读取 /home/mufire/SiliconTrace/TASK_BOARD.md。按照文档规则：
1. 你是修改者（状态0时GPT为修改者）
2. 查找状态为 Claude-NEEDS_FIX 的任务，按照审核记录中的建议修改代码
3. 修改完成后将任务状态改为 GPT-DONE
4. 注意\"任务看板\"、\"说明部分\"、\"任务说明\"、\"模型分工\"部分不能修改
5. 修改前先阅读审核记录中的\"建议修改\"部分"
else
    PROMPT="读取 /home/mufire/SiliconTrace/TASK_BOARD.md。按照文档规则：
1. 你是审核者（状态1时GPT为审核者）
2. 查找状态为 Claude-DONE 的任务，审核其改动文件的代码
3. 审核通过改为 GPT-REVIEWED，有问题改为 GPT-NEEDS_FIX，并在\"审核记录\"中写明意见
4. 注意\"任务看板\"、\"说明部分\"、\"任务说明\"、\"模型分工\"部分不能修改
5. 修改前先阅读审核记录"
fi

# Run Codex in non-interactive mode (fresh session each time to avoid resume timeout)
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral -C "$PROJECT_DIR" "$PROMPT" 2>&1 | tee -a /tmp/codex_poll.log

echo "$(date): Codex execution completed."
