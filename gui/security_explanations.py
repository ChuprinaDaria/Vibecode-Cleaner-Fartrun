"""Human-readable explanations for security findings.

Each finding type maps to a dict with:
- what: What this means in plain language
- risk: What an attacker could do
- fix: Copy-paste fix command or file change

Supports EN and UA via i18n module.
"""

from __future__ import annotations

import re
from i18n import get_language

COURSERA_LINKS: dict[str, dict[str, str]] = {
    "secrets": {"url": "https://www.coursera.org/learn/packt-fundamentals-of-secure-software-dqsu3", "title": "Fundamentals of Secure Software"},
    "malware": {"url": "https://www.coursera.org/professional-certificates/google-cybersecurity", "title": "Google Cybersecurity Professional Certificate"},
    "cybersecurity_intro": {"url": "https://www.coursera.org/learn/cybersecurity-for-everyone", "title": "Cybersecurity for Everyone"},
    "python": {"url": "https://www.coursera.org/learn/python", "title": "Programming for Everybody (Python)"},
    "frontend": {"url": "https://www.coursera.org/learn/developing-frontend-apps-with-react", "title": "Developing Front-End Apps with React"},
    "ai_agents": {"url": "https://www.coursera.org/specializations/ai-agents", "title": "AI Agent Developer Specialization"},
    "linux_security": {"url": "https://www.coursera.org/learn/securing-linux-systems", "title": "Securing Linux Systems"},
    "docker": {"url": "https://www.coursera.org/learn/docker-basics-for-devops", "title": "Docker Basics for DevOps"},
    "network": {"url": "https://www.coursera.org/learn/crypto", "title": "Cryptography I (Stanford)"},
    "llm_security": {"url": "https://www.coursera.org/learn/generative-ai-llm-security", "title": "Generative AI and LLM Security"},
    "supply_chain": {"url": "https://www.coursera.org/courses?query=application%20security", "title": "Application Security Courses"},
}

_TYPE_TO_COURSE: dict[str, str] = {
    "secrets": "secrets", "autostart": "linux_security", "packages": "supply_chain",
    "process": "malware", "network": "network", "cron": "linux_security",
    "filesystem": "linux_security", "docker": "docker", "deps": "supply_chain",
    "config": "secrets", "system": "cybersecurity_intro",
}

# === English explanations ===
_EXPLANATIONS_EN: dict[tuple[str, str], dict[str, str]] = {
    ("docker", "privileged"): {
        "what": "Container runs with full system privileges — same as root on the host machine.",
        "risk": "If an attacker compromises this container, they gain complete control over your server.",
        "fix": "Remove 'privileged: true' from docker-compose.yml.\nUse cap_add instead:\n\n  cap_add:\n    - NET_ADMIN  # only what you actually need",
    },
    ("docker", "docker.sock"): {
        "what": "Docker control socket is mounted inside the container.",
        "risk": "An attacker inside this container can create new containers, read secrets, or escape to the host.",
        "fix": "Remove the docker.sock volume mount:\n\n  # DELETE this line:\n  - /var/run/docker.sock:/var/run/docker.sock",
    },
    ("docker", "host network"): {
        "what": "Container shares the host's network directly instead of having its own isolated network.",
        "risk": "The container can see all network traffic, access localhost services, bypass isolation.",
        "fix": "Remove 'network_mode: host'. Use port mapping:\n\n  ports:\n    - '8080:8080'",
    },
    ("docker", "root"): {
        "what": "Container runs as admin (root). If hacked, attacker gets full access inside the container.",
        "risk": "Root access makes container escape much easier.",
        "fix": "Add USER to Dockerfile:\n\n  RUN adduser --disabled-password appuser\n  USER appuser\n\nOr: user: '1000:1000'",
    },
    ("docker", "latest"): {
        "what": "Container uses :latest tag. You don't know exactly which version is running.",
        "risk": "A compromised update could be pulled automatically. Builds are not reproducible.",
        "fix": "Pin version:\n\n  # Instead of: image: postgres:latest\n  image: postgres:16.2-alpine",
    },
    ("config", "env_in_git"): {
        "what": "A .env file with secrets is committed to git. Anyone with repo access can see them.",
        "risk": "All your secrets are exposed — passwords, API keys, database credentials.",
        "fix": "1. echo '.env*' >> .gitignore\n2. git rm --cached .env\n3. Rotate ALL secrets — they're compromised.",
    },
    ("config", "permissions"): {
        "what": "A sensitive file has too broad permissions. Other users can read it.",
        "risk": "Any user on the server can steal credentials or certificates.",
        "fix": "chmod 600 <filename>",
    },
    ("network", "exposed"): {
        "what": "Service listens on 0.0.0.0 — accessible from outside your machine.",
        "risk": "Anyone on your network can connect. Databases, Redis, debug servers should never be exposed.",
        "fix": "Bind to localhost:\n  - '127.0.0.1:5432:5432'",
    },
    ("deps", "vulnerability"): {
        "what": "A dependency has a known vulnerability (CVE).",
        "risk": "An attacker could execute code on your server, steal data, or crash your app.",
        "fix": "pip install --upgrade <package-name>",
    },
    ("system", "firewall_inactive"): {
        "what": "Your firewall is not active.",
        "risk": "Any service is exposed to the network. Attackers can probe and exploit open ports.",
        "fix": "sudo ufw enable\nsudo ufw default deny incoming\nsudo ufw allow ssh",
    },
    ("system", "ssh_root"): {
        "what": "SSH allows direct root login — #1 brute-force target.",
        "risk": "If they guess the password, they own your machine.",
        "fix": "PermitRootLogin no\nsudo systemctl restart sshd",
    },
    ("system", "ssh_password"): {
        "what": "SSH allows password authentication.",
        "risk": "Passwords can be guessed. Key-based auth is immune to brute-force.",
        "fix": "ssh-keygen -t ed25519\nPasswordAuthentication no\nsudo systemctl restart sshd",
    },
    ("system", "updates"): {
        "what": "Security updates available but not installed.",
        "risk": "Attackers actively exploit known CVEs. Unpatched = low-hanging fruit.",
        "fix": "sudo apt update && sudo apt upgrade -y",
    },
    ("system", "sudoers"): {
        "what": "Your user has passwordless sudo for ALL commands.",
        "risk": "If account is compromised, attacker gets instant root.",
        "fix": "sudo visudo\nRemove NOPASSWD or limit to specific commands.",
    },
    ("system", "world_writable"): {
        "what": "A PATH directory is writable by any user.",
        "risk": "Attacker can place a malicious binary that executes with your privileges.",
        "fix": "sudo chmod 755 <directory>",
    },
    ("system", "risky_port"): {
        "what": "A database/cache service listening on 0.0.0.0.",
        "risk": "Anyone on the network can connect. Redis and MongoDB have no auth by default.",
        "fix": "bind 127.0.0.1\nOr: '127.0.0.1:6379:6379'",
    },
    ("process", "cryptominer"): {
        "what": "A cryptocurrency miner is running on your system.",
        "risk": "Your machine slows down, electricity costs up, someone profits from your hardware.",
        "fix": "kill -9 <PID>\nls -la /proc/<PID>/exe\ncrontab -l",
    },
    ("process", "reverse_shell"): {
        "what": "A reverse shell is active — attacker has remote command access.",
        "risk": "CRITICAL: Attacker has real-time shell access to your system.",
        "fix": "IMMEDIATELY:\n1. kill -9 <PID>\n2. ss -tnp | grep <PID>\n3. crontab -l && ls /tmp/.*\n4. Rotate all credentials.",
    },
    ("process", "suspicious"): {
        "what": "Process with suspicious behavior — high CPU or unusual arguments.",
        "risk": "Could be a cryptominer, data exfiltration, or other malware.",
        "fix": "ps aux | grep <PID>\nls -la /proc/<PID>/exe\nkill -9 <PID>",
    },
    ("network", "c2_connection"): {
        "what": "Connection to a port used by C2 servers, malware, or mining pools.",
        "risk": "Your machine may be part of a botnet or mining cryptocurrency.",
        "fix": "ss -tnp | grep <remote_ip>\nkill -9 <PID>\nsudo ufw deny out to <remote_ip>",
    },
    ("network", "tor"): {
        "what": "Connection to the Tor network detected.",
        "risk": "If you didn't install Tor, malware may be using it to hide C2 traffic.",
        "fix": "If not intentional:\nkill -9 <PID>\nsudo apt remove tor",
    },
    ("filesystem", "permissions"): {
        "what": "Sensitive file has permissions that let others read/write it.",
        "risk": "Any user on the system can read your secrets.",
        "fix": "chmod 600 <file>  # owner read/write only",
    },
    ("filesystem", "malware_path"): {
        "what": "Suspicious file in location used by malware (/tmp, /dev/shm, hidden dirs).",
        "risk": "Malware hides in /tmp, /dev/shm (RAM disk), or hidden directories.",
        "fix": "file <path>\nstrings <path> | head -20\nrm <path>  # if unauthorized",
    },
    ("filesystem", "suid"): {
        "what": "Binary has SUID bit — runs with owner's permissions (often root).",
        "risk": "SUID vulnerability = instant root access for attackers.",
        "fix": "sudo chmod u-s <binary>\ndpkg -S <binary>  # verify",
    },
    ("filesystem", "suspicious_exec"): {
        "what": "Recently created executable in /tmp. Legitimate software rarely does this.",
        "risk": "Malware and exploit payloads often drop executables in /tmp.",
        "fix": "file <path>\nstrings <path> | head\nrm <path>",
    },
    ("cron", "suspicious"): {
        "what": "Scheduled task with suspicious commands (pipe-to-shell, base64, mining).",
        "risk": "Malware uses cron for persistence. Kill the process — cron brings it back.",
        "fix": "crontab -e\nls -la /etc/cron.d/\nsystemctl list-timers --all",
    },
    ("secrets", "api_key"): {
        "what": "A hardcoded API key was found in your files. Cloud/service credentials stored in plaintext.",
        "risk": "Anyone who reads this file can use your account, run up bills, exfiltrate data, or take over services.",
        "fix": "1. Move the key to .env:\n   API_KEY=your_key_here\n2. Load it: os.getenv('API_KEY')\n3. echo '.env' >> .gitignore\n4. ROTATE the key immediately — assume it's compromised.",
    },
    ("secrets", "private_key"): {
        "what": "A private key (SSH, TLS, PGP) was found in a file.",
        "risk": "Private keys give access to servers, encrypted communications, or signed artifacts. If stolen, an attacker can impersonate you.",
        "fix": "1. Move to ~/.ssh/ with permissions 600\n2. chmod 600 <keyfile>\n3. If committed to git — generate new keys immediately:\n   ssh-keygen -t ed25519",
    },
    ("secrets", "database_url"): {
        "what": "A database connection URL with credentials is hardcoded in the codebase.",
        "risk": "DB credentials allow direct access to all your data — read, write, delete.",
        "fix": "1. Move to .env:\n   DATABASE_URL=postgres://user:pass@host/db\n2. echo '.env' >> .gitignore\n3. Rotate DB password:\n   ALTER USER myuser WITH PASSWORD 'new_secure_password';",
    },
    ("autostart", "shell_rc"): {
        "what": "A suspicious command was found in a shell startup file (~/.bashrc, ~/.zshrc, ~/.profile).",
        "risk": "Malware adds itself to shell configs for persistence — runs every time you open a terminal.",
        "fix": "1. Open the file: nano ~/.bashrc\n2. Remove suspicious lines\n3. Reload: source ~/.bashrc\n4. Check other profiles: ~/.bash_profile, ~/.profile, ~/.zshrc",
    },
    ("autostart", "systemd_user"): {
        "what": "A suspicious systemd user service is registered to start automatically.",
        "risk": "Malware can install user-level systemd services that run at login without root privileges.",
        "fix": "systemctl --user list-units --all\nsystemctl --user stop <service>\nsystemctl --user disable <service>\nrm ~/.config/systemd/user/<service>.service",
    },
    ("autostart", "xdg_autostart"): {
        "what": "A .desktop file in XDG autostart directories runs a program at login.",
        "risk": "Malware uses XDG autostart for GUI-session persistence — starts with every desktop login.",
        "fix": "ls ~/.config/autostart/\ncat ~/.config/autostart/<file>.desktop\nrm ~/.config/autostart/<suspicious>.desktop",
    },
    ("packages", "typosquat"): {
        "what": "A package with a name very similar to a popular library is installed — possible typosquatting.",
        "risk": "Typosquatted packages mimic real ones to steal credentials, run backdoors, or exfiltrate data.",
        "fix": "pip uninstall <package>\nVerify the real package name on pypi.org\nCheck what was imported in your code",
    },
    ("packages", "malicious"): {
        "what": "A known malicious Python package is installed on this system.",
        "risk": "This package is confirmed to steal credentials, exfiltrate data, or provide attacker access.",
        "fix": "pip uninstall <package> -y\nRotate ALL credentials that were accessible while this package was installed\nCheck pip list for other suspicious packages",
    },
    ("packages", "postinstall"): {
        "what": "A package with postinstall scripts was detected — code that runs automatically during pip install.",
        "risk": "Postinstall scripts execute with your user permissions and can steal credentials, install backdoors, or modify system files.",
        "fix": "pip uninstall <package>\nAudit setup.py / pyproject.toml before installing unknown packages\nUse pip install --no-deps for untrusted packages",
    },
    ("process", "tunnel"): {
        "what": "A tunneling tool (ngrok, localtunnel, cloudflared, bore) is running and exposing local services to the internet.",
        "risk": "Your localhost services are reachable from anywhere on the internet. Dev databases, admin panels, debug servers — all exposed.",
        "fix": "kill -9 <PID>\nIf you need tunneling — use it temporarily and close when done\nNever tunnel production databases or admin interfaces",
    },
    ("process", "bruteforce"): {
        "what": "A brute-force or password cracking tool is running (hydra, hashcat, john, medusa).",
        "risk": "If this is on your system without your knowledge — someone is cracking credentials using your hardware.",
        "fix": "kill -9 <PID>\nls -la /proc/<PID>/exe\nCheck who started it: ps aux | grep <name>\nReview crontab and startup scripts",
    },
    ("process", "masquerading"): {
        "what": "A process has a name designed to look like a legitimate system process (kworker, sshd, systemd with unusual path).",
        "risk": "Malware disguises itself as system processes to avoid detection during casual inspection.",
        "fix": "ls -la /proc/<PID>/exe\nfile /proc/<PID>/exe\nstrings /proc/<PID>/exe | head -30\nkill -9 <PID> if unauthorized",
    },
    ("process", "temp_exec"): {
        "what": "An executable is running from /tmp, /dev/shm, or another temporary directory.",
        "risk": "Legitimate software almost never executes from /tmp. This is a classic malware behavior — drop and run.",
        "fix": "ls -la /proc/<PID>/exe\nfile <path>\nstrings <path> | head\nkill -9 <PID>\nrm <path>",
    },
}

# === Ukrainian explanations ===
_EXPLANATIONS_UA: dict[tuple[str, str], dict[str, str]] = {
    ("docker", "privileged"): {
        "what": "Контейнер працює з повними системними привілеями — як root на хост-машині.",
        "risk": "Якщо зламають контейнер — отримають повний контроль над сервером.",
        "fix": "Видаліть 'privileged: true' з docker-compose.yml.\nВикористовуйте cap_add:\n\n  cap_add:\n    - NET_ADMIN  # тільки те, що реально потрібно",
    },
    ("docker", "docker.sock"): {
        "what": "Docker сокет змонтований всередині контейнера — контейнер керує Docker.",
        "risk": "Зловмисник може створювати контейнери, читати секрети, вибратися на хост.",
        "fix": "Видаліть монтування docker.sock:\n\n  # ВИДАЛІТЬ цей рядок:\n  - /var/run/docker.sock:/var/run/docker.sock",
    },
    ("docker", "host network"): {
        "what": "Контейнер використовує мережу хоста напряму, без ізоляції.",
        "risk": "Бачить весь мережевий трафік, може звертатися до localhost сервісів.",
        "fix": "Видаліть 'network_mode: host'. Використовуйте порт-маппінг:\n\n  ports:\n    - '8080:8080'",
    },
    ("docker", "root"): {
        "what": "Контейнер працює від root. Якщо зламають — повний доступ всередині.",
        "risk": "Root спрощує вихід з контейнера на хост.",
        "fix": "Додайте USER в Dockerfile:\n\n  RUN adduser --disabled-password appuser\n  USER appuser",
    },
    ("docker", "latest"): {
        "what": "Контейнер використовує :latest тег — невідомо, яка саме версія працює.",
        "risk": "Скомпрометоване оновлення може підтягнутись автоматично.",
        "fix": "Закріпіть версію:\n\n  # Замість: image: postgres:latest\n  image: postgres:16.2-alpine",
    },
    ("config", "env_in_git"): {
        "what": ".env файл з секретами закомічений в git. Будь-хто з доступом до репо бачить їх.",
        "risk": "Всі секрети скомпрометовані — паролі, API ключі, дані БД.",
        "fix": "1. echo '.env*' >> .gitignore\n2. git rm --cached .env\n3. Ротуйте ВСІ секрети — вони вже скомпрометовані.",
    },
    ("config", "permissions"): {
        "what": "Чутливий файл має занадто широкі дозволи. Інші користувачі можуть його читати.",
        "risk": "Будь-хто на сервері може вкрасти облікові дані.",
        "fix": "chmod 600 <filename>",
    },
    ("network", "exposed"): {
        "what": "Сервіс слухає на 0.0.0.0 — доступний ззовні вашої машини.",
        "risk": "Будь-хто в мережі може підключитися. БД, Redis, dev-сервери не мають бути відкритими.",
        "fix": "Прив'яжіть до localhost:\n  - '127.0.0.1:5432:5432'",
    },
    ("deps", "vulnerability"): {
        "what": "Залежність має відому вразливість (CVE).",
        "risk": "Зловмисник може виконати код, вкрасти дані або покласти сервіс.",
        "fix": "pip install --upgrade <package-name>",
    },
    ("system", "firewall_inactive"): {
        "what": "Фаєрвол не активний.",
        "risk": "Всі сервіси відкриті в мережу. Зловмисники можуть сканувати і експлуатувати порти.",
        "fix": "sudo ufw enable\nsudo ufw default deny incoming\nsudo ufw allow ssh",
    },
    ("system", "ssh_root"): {
        "what": "SSH дозволяє прямий вхід як root — ціль №1 для брутфорсу.",
        "risk": "Якщо вгадають пароль — машина їхня.",
        "fix": "PermitRootLogin no\nsudo systemctl restart sshd",
    },
    ("system", "ssh_password"): {
        "what": "SSH дозволяє автентифікацію за паролем.",
        "risk": "Паролі можна підібрати. SSH ключі захищають від брутфорсу.",
        "fix": "ssh-keygen -t ed25519\nPasswordAuthentication no\nsudo systemctl restart sshd",
    },
    ("system", "updates"): {
        "what": "Є доступні оновлення безпеки, але вони не встановлені.",
        "risk": "Зловмисники активно експлуатують відомі CVE. Непатчена система — легка ціль.",
        "fix": "sudo apt update && sudo apt upgrade -y",
    },
    ("system", "sudoers"): {
        "what": "Ваш користувач має sudo без пароля для ВСІХ команд.",
        "risk": "Якщо акаунт скомпрометований — зловмисник отримує root миттєво.",
        "fix": "sudo visudo\nВидаліть NOPASSWD або обмежте конкретними командами.",
    },
    ("system", "world_writable"): {
        "what": "Директорія з PATH доступна для запису всім користувачам.",
        "risk": "Зловмисник може підкласти шкідливий бінарник з ім'ям як у звичайної команди.",
        "fix": "sudo chmod 755 <directory>",
    },
    ("system", "risky_port"): {
        "what": "БД або кеш-сервіс слухає на 0.0.0.0.",
        "risk": "Будь-хто в мережі може підключитися. Redis і MongoDB без автентифікації за замовчуванням.",
        "fix": "bind 127.0.0.1\nАбо: '127.0.0.1:6379:6379'",
    },
    ("process", "cryptominer"): {
        "what": "На вашій системі працює криптомайнер. Хтось майнить на ВАШОМУ залізі.",
        "risk": "Машина гальмує, рахунки за електрику ростуть, хтось заробляє на вас.",
        "fix": "kill -9 <PID>\nls -la /proc/<PID>/exe\ncrontab -l",
    },
    ("process", "reverse_shell"): {
        "what": "Активний reverse shell — ваша машина підключається НАЗАД до зловмисника.",
        "risk": "КРИТИЧНО: Зловмисник має shell-доступ до системи в реальному часі.",
        "fix": "НЕГАЙНО:\n1. kill -9 <PID>\n2. ss -tnp | grep <PID>\n3. crontab -l && ls /tmp/.*\n4. Ротуйте всі облікові дані.",
    },
    ("process", "suspicious"): {
        "what": "Процес з підозрілою поведінкою — високе CPU або незвичні аргументи.",
        "risk": "Може бути криптомайнер, інструмент ексфільтрації або інше шкідливе ПЗ.",
        "fix": "ps aux | grep <PID>\nls -la /proc/<PID>/exe\nkill -9 <PID>",
    },
    ("network", "c2_connection"): {
        "what": "З'єднання з портом, який використовують C2 сервери, малварь або майнінг-пули.",
        "risk": "Ваша машина може бути частиною ботнету або майнити крипту.",
        "fix": "ss -tnp | grep <remote_ip>\nkill -9 <PID>\nsudo ufw deny out to <remote_ip>",
    },
    ("network", "tor"): {
        "what": "Виявлено з'єднання з мережею Tor.",
        "risk": "Якщо ви не встановлювали Tor — малварь може використовувати його для прихованого C2.",
        "fix": "Якщо не навмисно:\nkill -9 <PID>\nsudo apt remove tor",
    },
    ("filesystem", "permissions"): {
        "what": "Чутливий файл має дозволи, що дозволяють іншим читати/писати.",
        "risk": "Будь-хто на системі може прочитати ваші секрети.",
        "fix": "chmod 600 <file>  # тільки для власника",
    },
    ("filesystem", "malware_path"): {
        "what": "Підозрілий файл у місці, де малварь зберігає persistence (/tmp, /dev/shm).",
        "risk": "Малварь ховається в /tmp, /dev/shm (RAM-диск), прихованих директоріях.",
        "fix": "file <path>\nstrings <path> | head -20\nrm <path>  # якщо не ваше",
    },
    ("filesystem", "suid"): {
        "what": "Бінарник має SUID біт — запускається з правами власника (часто root).",
        "risk": "Вразливість у SUID бінарнику = миттєвий root для зловмисника.",
        "fix": "sudo chmod u-s <binary>\ndpkg -S <binary>  # перевірте",
    },
    ("filesystem", "suspicious_exec"): {
        "what": "Нещодавно створений executable у /tmp. Легітимне ПЗ рідко так робить.",
        "risk": "Малварь і payload-и часто створюють executable в /tmp перед запуском.",
        "fix": "file <path>\nstrings <path> | head\nrm <path>",
    },
    ("cron", "suspicious"): {
        "what": "Планове завдання з підозрілими командами (pipe-to-shell, base64, майнінг).",
        "risk": "Малварь використовує cron для persistence. Вбиваєш процес — cron поверне.",
        "fix": "crontab -e\nls -la /etc/cron.d/\nsystemctl list-timers --all",
    },
    ("secrets", "api_key"): {
        "what": "Захардкоджений API ключ знайдено у файлах. Облікові дані хмарного сервісу зберігаються відкритим текстом.",
        "risk": "Будь-хто, хто прочитає цей файл, може використати ваш акаунт, накрутити рахунки, викрасти дані або захопити сервіси.",
        "fix": "1. Перенесіть ключ у .env:\n   API_KEY=your_key_here\n2. Завантажуйте через: os.getenv('API_KEY')\n3. echo '.env' >> .gitignore\n4. РОТУЙТЕ ключ негайно — вважайте його скомпрометованим.",
    },
    ("secrets", "private_key"): {
        "what": "Знайдено приватний ключ (SSH, TLS, PGP) у файлі.",
        "risk": "Приватні ключі дають доступ до серверів, зашифрованих комунікацій або підписаних артефактів. Якщо вкрадуть — зловмисник може видавати себе за вас.",
        "fix": "1. Перемістіть у ~/.ssh/ з правами 600\n2. chmod 600 <keyfile>\n3. Якщо закомічений в git — генеруйте нові ключі негайно:\n   ssh-keygen -t ed25519",
    },
    ("secrets", "database_url"): {
        "what": "URL підключення до БД з обліковими даними захардкоджений у коді.",
        "risk": "Дані БД дають прямий доступ до всіх ваших даних — читання, запис, видалення.",
        "fix": "1. Перенесіть у .env:\n   DATABASE_URL=postgres://user:pass@host/db\n2. echo '.env' >> .gitignore\n3. Змініть пароль БД:\n   ALTER USER myuser WITH PASSWORD 'new_secure_password';",
    },
    ("autostart", "shell_rc"): {
        "what": "Підозрілу команду знайдено у файлі запуску оболонки (~/.bashrc, ~/.zshrc, ~/.profile).",
        "risk": "Малварь додає себе до конфігів оболонки для persistence — запускається щоразу, коли відкриваєте термінал.",
        "fix": "1. Відкрийте файл: nano ~/.bashrc\n2. Видаліть підозрілі рядки\n3. Перезавантажте: source ~/.bashrc\n4. Перевірте інші профілі: ~/.bash_profile, ~/.profile, ~/.zshrc",
    },
    ("autostart", "systemd_user"): {
        "what": "Зареєстровано підозрілий systemd user service, що запускається автоматично.",
        "risk": "Малварь може встановлювати user-level systemd сервіси без root-привілеїв, що запускаються при вході.",
        "fix": "systemctl --user list-units --all\nsystemctl --user stop <service>\nsystemctl --user disable <service>\nrm ~/.config/systemd/user/<service>.service",
    },
    ("autostart", "xdg_autostart"): {
        "what": ".desktop файл у директоріях XDG autostart запускає програму при вході.",
        "risk": "Малварь використовує XDG autostart для persistence у графічному сеансі — запускається з кожним входом на робочий стіл.",
        "fix": "ls ~/.config/autostart/\ncat ~/.config/autostart/<file>.desktop\nrm ~/.config/autostart/<підозрілий>.desktop",
    },
    ("packages", "typosquat"): {
        "what": "Встановлено пакет з іменем, дуже схожим на популярну бібліотеку — можливий тайпосквот.",
        "risk": "Тайпосквотовані пакети імітують справжні, щоб красти облікові дані, запускати бекдори або ексфільтрувати дані.",
        "fix": "pip uninstall <package>\nПеревірте справжнє ім'я пакету на pypi.org\nПеревірте що імпортувалось у вашому коді",
    },
    ("packages", "malicious"): {
        "what": "Встановлено відомий шкідливий Python пакет.",
        "risk": "Цей пакет підтверджено краде облікові дані, ексфільтрує дані або надає зловмиснику доступ.",
        "fix": "pip uninstall <package> -y\nРотуйте ВСІ облікові дані, доступні поки пакет був встановлений\nПеревірте pip list на інші підозрілі пакети",
    },
    ("packages", "postinstall"): {
        "what": "Виявлено пакет з postinstall скриптами — код, що виконується автоматично під час pip install.",
        "risk": "Postinstall скрипти виконуються з вашими правами і можуть красти облікові дані, встановлювати бекдори або змінювати системні файли.",
        "fix": "pip uninstall <package>\nАудитуйте setup.py / pyproject.toml перед встановленням незнайомих пакетів\nВикористовуйте pip install --no-deps для ненадійних пакетів",
    },
    ("process", "tunnel"): {
        "what": "Запущено інструмент тунелювання (ngrok, localtunnel, cloudflared, bore), який відкриває локальні сервіси в інтернет.",
        "risk": "Ваші localhost сервіси доступні звідусіль. Dev бази даних, адмін-панелі, debug сервери — все відкрито.",
        "fix": "kill -9 <PID>\nЯкщо потрібен тунель — використовуйте тимчасово і закривайте\nНіколи не тунелюйте production БД або адмін-інтерфейси",
    },
    ("process", "bruteforce"): {
        "what": "Запущено інструмент брутфорсу або зламу паролів (hydra, hashcat, john, medusa).",
        "risk": "Якщо це на вашій системі без вашого відома — хтось ламає облікові дані на вашому залізі.",
        "fix": "kill -9 <PID>\nls -la /proc/<PID>/exe\nПеревірте хто запустив: ps aux | grep <name>\nПеревірте crontab і скрипти автозапуску",
    },
    ("process", "masquerading"): {
        "what": "Процес має ім'я, що імітує легітимний системний процес (kworker, sshd, systemd з незвичним шляхом).",
        "risk": "Малварь маскується під системні процеси, щоб уникнути виявлення під час звичайного огляду.",
        "fix": "ls -la /proc/<PID>/exe\nfile /proc/<PID>/exe\nstrings /proc/<PID>/exe | head -30\nkill -9 <PID> якщо несанкціоновано",
    },
    ("process", "temp_exec"): {
        "what": "Executable запущено з /tmp, /dev/shm або іншої тимчасової директорії.",
        "risk": "Легітимне ПЗ майже ніколи не виконується з /tmp. Це класична поведінка малварі — скинути і запустити.",
        "fix": "ls -la /proc/<PID>/exe\nfile <path>\nstrings <path> | head\nkill -9 <PID>\nrm <path>",
    },
}

_PATTERNS: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"privileged mode", re.I), ("docker", "privileged")),
    (re.compile(r"docker\.sock", re.I), ("docker", "docker.sock")),
    (re.compile(r"host network", re.I), ("docker", "host network")),
    (re.compile(r"runs as root|no USER set", re.I), ("docker", "root")),
    (re.compile(r":latest tag|:latest\b", re.I), ("docker", "latest")),
    (re.compile(r"\.env.*committed|\.env.*git", re.I), ("config", "env_in_git")),
    (re.compile(r"[Bb]road permissions", re.I), ("config", "permissions")),
    (re.compile(r"exposed on 0\.0\.0\.0|0\.0\.0\.0", re.I), ("network", "exposed")),
    (re.compile(r"CVE-|vulnerability|vuln", re.I), ("deps", "vulnerability")),
    (re.compile(r"[Ff]irewall.*inactive|[Nn]o firewall", re.I), ("system", "firewall_inactive")),
    (re.compile(r"SSH allows root|root login", re.I), ("system", "ssh_root")),
    (re.compile(r"SSH allows password", re.I), ("system", "ssh_password")),
    (re.compile(r"security updates available|package updates", re.I), ("system", "updates")),
    (re.compile(r"passwordless sudo|NOPASSWD", re.I), ("system", "sudoers")),
    (re.compile(r"world-writable|world writable", re.I), ("system", "world_writable")),
    (re.compile(r"MySQL|PostgreSQL|Redis|MongoDB|Memcached|Elasticsearch.*exposed", re.I), ("system", "risky_port")),
    # Sentinel
    (re.compile(r"[Cc]ryptominer|xmrig|minerd|cpuminer|mining pool|stratum\+", re.I), ("process", "cryptominer")),
    (re.compile(r"[Rr]everse shell|nc -e|ncat -e|socat exec|/dev/tcp/", re.I), ("process", "reverse_shell")),
    (re.compile(r"[Pp]ipe-to-shell in scheduled|cron.*curl\|bash", re.I), ("cron", "suspicious")),
    (re.compile(r"[Pp]ipe-to-shell|curl\|bash|wget\|bash|base64.*decode.*shell", re.I), ("process", "reverse_shell")),
    (re.compile(r"CPU.*possible cryptominer|high.*CPU.*suspicious", re.I), ("process", "suspicious")),
    (re.compile(r"C2|Metasploit|Cobalt Strike|Back Orifice|NetBus", re.I), ("network", "c2_connection")),
    (re.compile(r"IRC|port 6667|port 6697", re.I), ("network", "c2_connection")),
    (re.compile(r"Tor.*SOCKS|Tor.*control|port 9050|port 9051", re.I), ("network", "tor")),
    (re.compile(r"[Ss]ensitive file with broad permissions", re.I), ("filesystem", "permissions")),
    (re.compile(r"malware persistence|Hidden file.*in /tmp|/dev/shm", re.I), ("filesystem", "malware_path")),
    (re.compile(r"SUID binary|suid", re.I), ("filesystem", "suid")),
    (re.compile(r"[Rr]ecently created executable|suspicious.*exec", re.I), ("filesystem", "suspicious_exec")),
    (re.compile(r"scheduled task|crontab|cron.*suspicious", re.I), ("cron", "suspicious")),
    # Secrets
    (re.compile(r"AWS Access Key|AWS Secret|AKIA[0-9A-Z]{16}|GitHub.*token|gh[ps]_[0-9a-zA-Z]+|OpenAI.*key|sk-[a-zA-Z0-9]{20,}|Anthropic.*key|sk-ant-|Stripe.*key|sk_live_|sk_test_|Slack.*token|xox[baprs]-|Google.*API.*key|AIza[0-9A-Za-z_-]{35}|Telegram.*token|[0-9]{8,10}:[A-Za-z0-9_-]{35}", re.I), ("secrets", "api_key")),
    (re.compile(r"Private Key|BEGIN.*PRIVATE KEY|BEGIN RSA PRIVATE|BEGIN EC PRIVATE|BEGIN OPENSSH PRIVATE", re.I), ("secrets", "private_key")),
    (re.compile(r"[Dd]atabase URL|DATABASE_URL|postgres://|postgresql://|mysql://|mongodb://.*:[^@]+@", re.I), ("secrets", "database_url")),
    # Autostart
    (re.compile(r"shell.*rc.*persistence|suspicious.*bashrc|suspicious.*zshrc|suspicious.*profile|\.bashrc|\.zshrc.*suspicious", re.I), ("autostart", "shell_rc")),
    (re.compile(r"systemd.*user.*service|suspicious.*systemd.*user|\.config/systemd/user", re.I), ("autostart", "systemd_user")),
    (re.compile(r"XDG.*autostart|\.config/autostart|\.desktop.*autostart|autostart.*\.desktop", re.I), ("autostart", "xdg_autostart")),
    # Packages
    (re.compile(r"[Tt]yposquat|typo.*squat|similar.*package.*name|package.*similar.*to", re.I), ("packages", "typosquat")),
    (re.compile(r"[Kk]nown malicious.*package|malicious.*Python package|malicious.*pip", re.I), ("packages", "malicious")),
    (re.compile(r"[Pp]ostinstall script|post.?install.*script|setup\.py.*exec|install.*hook", re.I), ("packages", "postinstall")),
    # Process
    (re.compile(r"[Tt]unneling tool|ngrok|localtunnel|cloudflared|bore\.pub|serveo|pagekite", re.I), ("process", "tunnel")),
    (re.compile(r"[Bb]rute.?force|hydra|hashcat|john.*ripper|medusa.*password|ncrack|patator", re.I), ("process", "bruteforce")),
    (re.compile(r"[Mm]asquerad|fake.*system.*process|process.*impersonat|suspicious.*name.*path", re.I), ("process", "masquerading")),
    (re.compile(r"[Rr]unning from /tmp|exec.*from.*/tmp|/dev/shm.*exec|executable.*tmp|temp.*exec", re.I), ("process", "temp_exec")),
]

_GENERIC_EN = {
    "what": "A potential security issue was detected.",
    "risk": "This could expose your system to attacks.",
    "fix": "Review the finding description and consult security docs.",
}

_GENERIC_UA = {
    "what": "Виявлено потенційну проблему безпеки.",
    "risk": "Це може зробити вашу систему вразливою до атак.",
    "fix": "Перегляньте опис знахідки та документацію з безпеки.",
}

_HUMAN_EN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(.+): runs in privileged mode"), r"\1: повний адмін-доступ — зламають = контролюють сервер"),
    (re.compile(r"(.+): docker\.sock mounted inside container"), r"\1: Docker сокет відкритий — контролюють ВСІ контейнери"),
    (re.compile(r"(.+): uses host network mode"), r"\1: мережа хоста — бачить весь трафік"),
    (re.compile(r"(.+): runs as root \(no USER set\)"), r"\1: працює як root — зламають = повний доступ"),
    (re.compile(r"(.+): uses :latest tag \((.+)\)"), r"\1: версія не закріплена (\2) — оновлення можуть зламати"),
    (re.compile(r"\.env file committed in git: (.+)"), r"Секрети в git: \1 — паролі видно всім"),
    (re.compile(r"Broad permissions \((.+)\) on sensitive file: (.+)"), r"\2 читає хто завгодно (\1) — chmod 600!"),
    (re.compile(r"Port (\d+) \((.+)\) exposed on 0\.0\.0\.0"), r"Порт \1 (\2) відкритий у світ — тільки localhost!"),
    (re.compile(r"Firewall \(ufw\) is inactive"), "Фаєрвол ВИМКНЕНО — система без мережевого захисту"),
    (re.compile(r"No firewall detected"), "Фаєрвол не знайдено — система повністю відкрита"),
    (re.compile(r"Firewall has no rules"), "Фаєрвол без правил — весь трафік проходить"),
    (re.compile(r"SSH allows root login"), "SSH root логін увімкнено — ціль №1 для брутфорсу"),
    (re.compile(r"SSH allows password authentication"), "SSH з паролями — ключі набагато безпечніші"),
    (re.compile(r"SSH allows empty passwords"), "SSH з ПОРОЖНІМИ паролями — хто завгодно може зайти!"),
    (re.compile(r"SSH runs on default port"), "SSH на порту 22 — змініть для зменшення шуму сканів"),
    (re.compile(r"(\d+) security updates available"), r"\1 патчів безпеки не встановлено — apt upgrade!"),
    (re.compile(r"(\d+) package updates available"), r"\1 пакетів застаріли — можуть мати CVE"),
    (re.compile(r"passwordless sudo for ALL"), "Sudo без пароля — зламають = миттєвий root"),
    (re.compile(r"PATH directory (.+) is world-writable"), r"\1 у PATH доступна для запису всім — вектор малварі"),
    (re.compile(r"(.+) \(port (\d+)\) exposed on all interfaces"), r"\1 (порт \2) відкритий у мережу — тільки localhost!"),
    # Sentinel: процеси
    (re.compile(r"Cryptominer detected: (.+)"), r"КРИПТОМАЙНЕР: \1 — хтось майнить на ВАШОМУ залізі!"),
    (re.compile(r"Possible hidden miner.*: (.+)"), r"Підозрілий процес \1 — можливий прихований майнер"),
    (re.compile(r"Reverse shell \((.+)\): (.+)"), r"REVERSE SHELL (\1): \2 — зловмисник має доступ!"),
    (re.compile(r"Netcat reverse shell: (.+)"), r"NETCAT БЕКДОР: \1 — зловмисник слухає!"),
    (re.compile(r"Netcat listener.*: (.+)"), r"Netcat listener: \1 — можливий бекдор"),
    (re.compile(r"Pipe-to-shell.*: (.+)"), r"PIPE-TO-SHELL: \1 — виконання коду ззовні!"),
    (re.compile(r"Mining pool connection: (.+)"), r"З'єднання з майнінг-пулом: \1 — активний майнінг!"),
    (re.compile(r"Process '(.+)' \(PID (\d+)\) using (.+)% CPU.*cryptominer"), r"'\1' (PID \2) жере \3% CPU — можливий майнер"),
    # Sentinel: мережа
    (re.compile(r"Connection to (.+) port (\d+) \((.+)\).*from '(.+)'"), r"З'єднання \4 -> \1:\2 (\3) — підозріло!"),
    (re.compile(r"(.+) \(port (\d+)\) listening on 0\.0\.0\.0"), r"\1 (порт \2) відкритий у світ — прив'яжіть до localhost!"),
    # Sentinel: файли
    (re.compile(r"Sensitive file with broad permissions \((.+)\): (.+)"), r"\2 читає хто завгодно (\1) — chmod 600!"),
    (re.compile(r"Hidden file/directory in (.+): (.+)"), r"Прихований об'єкт у \1: \2 — може бути малварь"),
    (re.compile(r"Executable in /dev/shm.*: (.+)"), r"EXECUTABLE В RAM ДИСКУ: \1 — класична малварь!"),
    (re.compile(r"Non-standard SUID binary: (.+) \((.+)\)"), r"SUID бінарник \1 (\2) — ризик ескалації привілеїв"),
    (re.compile(r"Recently created executable in (.+): (.+)"), r"Новий executable у \1: \2 — перевірте походження!"),
    # Sentinel: cron
    (re.compile(r"Pipe-to-shell in scheduled task: (.+)"), r"CRON curl|bash: \1 — WTF!"),
    (re.compile(r"Cryptominer in scheduled task: (.+)"), r"МАЙНЕР В CRONTAB: \1 — постійний майнінг!"),
    (re.compile(r"Base64 decode in scheduled task: (.+)"), r"CRON base64 decode: \1 — обфусцований payload!"),
    (re.compile(r"Eval in scheduled task: (.+)"), r"CRON eval: \1 — виконання коду в cron!"),
    # Secrets
    (re.compile(r"AWS Access Key ID found in (.+)"), r"AWS КЛЮЧ захардкоджений у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"AWS Secret Access Key found in (.+)"), r"AWS SECRET захардкоджений у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"GitHub token found in (.+)"), r"GITHUB TOKEN у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"OpenAI API key found in (.+)"), r"OPENAI КЛЮЧ у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"Anthropic API key found in (.+)"), r"ANTHROPIC КЛЮЧ у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"Stripe API key found in (.+)"), r"STRIPE КЛЮЧ у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"Slack token found in (.+)"), r"SLACK TOKEN у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"Google API key found in (.+)"), r"GOOGLE API КЛЮЧ у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"Telegram bot token found in (.+)"), r"TELEGRAM TOKEN у \1 — РОТУЙТЕ НЕГАЙНО!"),
    (re.compile(r"API key found in (.+)"), r"API КЛЮЧ захардкоджений у \1 — перенесіть у .env!"),
    (re.compile(r"Private key found in (.+)"), r"ПРИВАТНИЙ КЛЮЧ у \1 — перемістіть та оновіть!"),
    (re.compile(r"Database URL with credentials in (.+)"), r"ДАНІ БД у \1 — перенесіть у .env та змініть пароль!"),
    # Autostart
    (re.compile(r"Suspicious command in (.+): (.+)"), r"ПІДОЗРІЛИЙ АВТОЗАПУСК у \1: \2 — перевірте!"),
    (re.compile(r"Suspicious systemd user service: (.+)"), r"SYSTEMD СЕРВІС: \1 — можлива persistence малварі!"),
    (re.compile(r"Suspicious XDG autostart entry: (.+)"), r"XDG AUTOSTART: \1 — запускається при кожному вході!"),
    # Packages
    (re.compile(r"Possible typosquat: (.+) \(similar to (.+)\)"), r"ТАЙПОСКВОТ: \1 схожий на \2 — перевірте!"),
    (re.compile(r"Known malicious Python package: (.+)"), r"ШКІДЛИВИЙ ПАКЕТ: \1 — ВИДАЛІТЬ НЕГАЙНО!"),
    (re.compile(r"Package with postinstall scripts: (.+)"), r"POSTINSTALL СКРИПТ: \1 — виконує код при встановленні!"),
    # Process
    (re.compile(r"Tunneling tool detected: (.+)"), r"ТУНЕЛЬ: \1 — ваші сервіси відкриті в інтернет!"),
    (re.compile(r"Brute-?force tool detected: (.+)"), r"БРУТФОРС: \1 — хтось ламає паролі на вашій машині!"),
    (re.compile(r"Process masquerading as system: (.+)"), r"МАСКУВАННЯ: \1 прикидається системним процесом!"),
    (re.compile(r"Executable running from /tmp: (.+)"), r"EXEC З /TMP: \1 — класична ознака малварі!"),
    (re.compile(r"Process running from temp directory: (.+)"), r"EXEC З TEMP: \1 — підозріло, перевірте!"),
]


def get_explanation(finding_type: str, description: str) -> dict[str, str]:
    lang = get_language()
    explanations = _EXPLANATIONS_UA if lang == "ua" else _EXPLANATIONS_EN
    generic = _GENERIC_UA if lang == "ua" else _GENERIC_EN

    for pattern, key in _PATTERNS:
        if pattern.search(description):
            return explanations.get(key, generic)
    for key, exp in explanations.items():
        if key[0] == finding_type:
            return exp
    return generic


def get_human_description(finding_type: str, description: str) -> str:
    lang = get_language()
    patterns = _HUMAN_EN  # UA patterns used for both — they contain Ukrainian text
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, description)
        if result != description:
            return result
    return description


def get_course_link(finding_type: str, description: str) -> dict[str, str] | None:
    course_key = _TYPE_TO_COURSE.get(finding_type)
    if course_key and course_key in COURSERA_LINKS:
        return COURSERA_LINKS[course_key]
    return None
