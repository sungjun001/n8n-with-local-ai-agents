#!/bin/bash
# Check Tools Debug Script
# Run this from INSIDE the claude-bridge container to diagnose why tools are missing.

SSH_HOST=${SSH_HOST:-claude-ssh-server}
SSH_USER=${SSH_USER:-claudeuser}
SSH_PASS=${SSH_PASS:-1234}

echo "========================================"
echo "🔍 Diagnosing SSH & Tool Availability"
echo "Target: $SSH_USER@$SSH_HOST"
echo "========================================"

# Helper function
run_ssh() {
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$SSH_USER@$SSH_HOST" "$1"
}

# 1. Check Connectivity
echo "[1] Checking SSH Connectivity..."
if run_ssh "echo 'SSH Connected OK'"; then
    echo "✅ SSH Connection Successful"
else
    echo "❌ SSH Connection Failed"
    exit 1
fi

# 2. Check PATH
echo ""
echo "[2] Checking PATH via SSH..."
REMOTE_PATH=$(run_ssh "echo \$PATH")
echo "   PATH: $REMOTE_PATH"
if [[ "$REMOTE_PATH" == *".local/bin"* ]]; then
    echo "✅ .local/bin is in PATH"
else
    echo "⚠️  WARNING: .local/bin is MISSING from PATH"
fi

# 3. Check Tools
check_tool() {
    NAME=$1
    echo ""
    echo "[3] Checking Tool: $NAME"
    
    echo "   > which $NAME"
    WHICH_OUT=$(run_ssh "which $NAME")
    RET=$?
    if [ $RET -eq 0 ]; then
        echo "   ✅ Found at: $WHICH_OUT"
    else
        echo "   ❌ 'which $NAME' failed (Exit: $RET)"
    fi
    
    echo "   > $NAME --version"
    VER_OUT=$(run_ssh "$NAME --version")
    if [ $? -eq 0 ]; then
        echo "   ✅ Version: $VER_OUT"
    else
        echo "   ❌ Execution failed"
        echo "      Output: $VER_OUT"
    fi
}

check_tool "claude"
check_tool "gemini"
check_tool "codex"
# check_tool "mc"

echo "========================================"
echo "Done."
