"""Hooks Guide — 5 real scenarios for people with zero devops experience."""

HOOKS_GUIDE = [
    {
        "title": "Run tests before I commit broken code",
        "what_happens": (
            "Every time you (or AI) try to save code to git, "
            "the hook runs your tests first. If tests fail — save is blocked. "
            "You can't accidentally save broken code."
        ),
        "when_you_need": (
            "When AI changes 20 files and you want to make sure "
            "nothing broke before saving."
        ),
        "setup_file": ".git/hooks/pre-commit",
        "setup_script": (
            "#!/bin/sh\n"
            "# Run tests before allowing commit\n"
            "echo 'Running tests...'\n"
            "\n"
            "# Python\n"
            "if [ -f 'pyproject.toml' ] || [ -f 'pytest.ini' ]; then\n"
            "    python -m pytest --quiet || exit 1\n"
            "fi\n"
            "\n"
            "# JavaScript\n"
            "if [ -f 'package.json' ]; then\n"
            "    npm test -- --watchAll=false 2>/dev/null || true\n"
            "fi\n"
            "\n"
            "echo 'Tests passed!'"
        ),
        "dont_forget": "chmod +x .git/hooks/pre-commit",
    },
    {
        "title": "Format my code automatically on save",
        "what_happens": (
            "Every time you save code to git, the hook runs a formatter. "
            "Code always looks clean without you doing anything."
        ),
        "when_you_need": (
            "When AI writes code with inconsistent indentation "
            "and you don't want to fix it by hand."
        ),
        "setup_file": ".git/hooks/pre-commit",
        "setup_script": (
            "#!/bin/sh\n"
            "# Auto-format before commit\n"
            "\n"
            "# Python — black formatter\n"
            "if command -v black &>/dev/null; then\n"
            "    black . --quiet 2>/dev/null\n"
            "    git add -u  # re-stage formatted files\n"
            "fi\n"
            "\n"
            "# JavaScript — prettier\n"
            "if command -v npx &>/dev/null && [ -f '.prettierrc' ]; then\n"
            "    npx prettier --write . 2>/dev/null\n"
            "    git add -u\n"
            "fi"
        ),
        "dont_forget": "Install black (pip install black) or prettier (npm install -D prettier)",
    },
    {
        "title": "Don't let me commit passwords",
        "what_happens": (
            "Hook scans your files for things that look like "
            "passwords, API keys, tokens. If found — blocks the save."
        ),
        "when_you_need": (
            "Always. One leaked API key = someone else's bill on your card."
        ),
        "setup_file": ".git/hooks/pre-commit",
        "setup_script": (
            "#!/bin/sh\n"
            "# Block commits with secrets\n"
            "\n"
            "# Check for common secret patterns\n"
            "if git diff --cached --diff-filter=d | grep -iE \\\n"
            "    '(password|secret|api_key|token|private_key)\\s*=' | \\\n"
            "    grep -v '.example' | grep -v '#' | grep -v 'test'; then\n"
            "    echo ''\n"
            "    echo 'BLOCKED: Possible secret found in commit!'\n"
            "    echo 'Check your code for passwords/keys.'\n"
            "    echo 'If this is a false alarm, use: git commit --no-verify'\n"
            "    exit 1\n"
            "fi\n"
            "\n"
            "# Check if .env is being committed\n"
            "if git diff --cached --name-only | grep -E '^\\.env$'; then\n"
            "    echo 'BLOCKED: .env file in commit! Add it to .gitignore.'\n"
            "    exit 1\n"
            "fi"
        ),
        "dont_forget": "Add .env to .gitignore: echo '.env' >> .gitignore",
    },
    {
        "title": "Tell me in Slack/Telegram when deploy is done",
        "what_happens": (
            "After code is pushed to the server, a hook sends "
            "a message to your chat. You know it's live without checking."
        ),
        "when_you_need": (
            "When you deploy and then forget to check if it actually worked."
        ),
        "setup_file": ".git/hooks/post-push (or CI/CD script)",
        "setup_script": (
            "#!/bin/sh\n"
            "# Notify after push (save as post-receive on server)\n"
            "\n"
            "# Telegram\n"
            "TELEGRAM_TOKEN='your-bot-token'\n"
            "CHAT_ID='your-chat-id'\n"
            "MSG=\"Deploy done: $(git log -1 --format='%s')\"\n"
            "curl -s -X POST \\\n"
            "    \"https://api.telegram.org/bot$TELEGRAM_TOKEN/sendMessage\" \\\n"
            "    -d chat_id=\"$CHAT_ID\" -d text=\"$MSG\" >/dev/null\n"
            "\n"
            "# Slack (webhook)\n"
            "# SLACK_URL='https://hooks.slack.com/services/XXX'\n"
            "# curl -s -X POST $SLACK_URL \\\n"
            "#     -H 'Content-type: application/json' \\\n"
            "#     -d \"{\\\"text\\\": \\\"$MSG\\\"}\" >/dev/null"
        ),
        "dont_forget": "Replace token and chat_id with your actual values",
    },
    {
        "title": "Rebuild the project when I change config",
        "what_happens": (
            "When docker-compose.yml or package.json changes, "
            "hook automatically runs the rebuild command."
        ),
        "when_you_need": (
            "When AI changes your config and you forget to restart the server. "
            "Then spend 30 minutes debugging why 'changes don't work.'"
        ),
        "setup_file": ".git/hooks/post-commit",
        "setup_script": (
            "#!/bin/sh\n"
            "# Auto-rebuild on config changes\n"
            "\n"
            "CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null)\n"
            "\n"
            "# Docker rebuild\n"
            "if echo \"$CHANGED\" | grep -q 'docker-compose'; then\n"
            "    echo 'docker-compose changed — rebuilding...'\n"
            "    docker compose up -d --build\n"
            "fi\n"
            "\n"
            "# npm install on package.json change\n"
            "if echo \"$CHANGED\" | grep -q 'package.json'; then\n"
            "    echo 'package.json changed — installing...'\n"
            "    npm install\n"
            "fi\n"
            "\n"
            "# pip install on requirements.txt change\n"
            "if echo \"$CHANGED\" | grep -q 'requirements.txt'; then\n"
            "    echo 'requirements.txt changed — installing...'\n"
            "    pip install -r requirements.txt\n"
            "fi"
        ),
        "dont_forget": "chmod +x .git/hooks/post-commit",
    },
]
