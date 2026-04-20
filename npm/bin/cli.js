#!/usr/bin/env node

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");
const https = require("https");

const REPO = "ChuprinaDaria/Vibecode-Cleaner-Fartrun";
const VERSION = "3.0.0";

const PINK = "\x1b[35m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";

const LOGO = `${PINK}
  ╔═╗╔═╗╦═╗╔╦╗╦═╗╦ ╦╔╗╔
  ╠╣ ╠═╣╠╦╝ ║ ╠╦╝║ ║║║║
  ╚  ╩ ╩╩╚═ ╩ ╩╚═╚═╝╝╚╝  v${VERSION}
${RESET}`;

function getPlatform() {
  const platform = os.platform();
  const arch = os.arch();

  if (platform === "linux" && arch === "x64") return { key: "linux", file: "fartrun-linux-x64.tar.gz" };
  if (platform === "darwin" && arch === "x64") return { key: "macos", file: "fartrun-macos-x64.zip" };
  if (platform === "darwin" && arch === "arm64") return { key: "macos", file: "fartrun-macos-x64.zip" };
  if (platform === "win32" && arch === "x64") return { key: "windows", file: "fartrun-windows-x64.zip" };

  console.error(`${RED}Unsupported platform: ${platform}-${arch}${RESET}`);
  process.exit(1);
}

function getInstallDir() {
  const home = os.homedir();
  if (os.platform() === "win32") return path.join(home, "AppData", "Local", "fartrun");
  return path.join(home, ".local", "bin");
}

function getSettingsPath(client) {
  const home = os.homedir();
  const platform = os.platform();

  const paths = {
    "claude-code": path.join(home, ".claude", "settings.json"),
    cursor: platform === "darwin"
      ? path.join(home, "Library", "Application Support", "Cursor", "User", "globalStorage", "rooveterinaryinc.roo-cline", "settings", "mcp_settings.json")
      : platform === "win32"
        ? path.join(home, "AppData", "Roaming", "Cursor", "User", "globalStorage", "rooveterinaryinc.roo-cline", "settings", "mcp_settings.json")
        : path.join(home, ".config", "Cursor", "User", "globalStorage", "rooveterinaryinc.roo-cline", "settings", "mcp_settings.json"),
    windsurf: platform === "darwin"
      ? path.join(home, "Library", "Application Support", "Windsurf", "User", "globalStorage", "codeium.windsurf", "mcp_settings.json")
      : platform === "win32"
        ? path.join(home, "AppData", "Roaming", "Windsurf", "User", "globalStorage", "codeium.windsurf", "mcp_settings.json")
        : path.join(home, ".config", "Windsurf", "User", "globalStorage", "codeium.windsurf", "mcp_settings.json"),
  };

  return paths[client];
}

function download(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return download(res.headers.location).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve(Buffer.concat(chunks)));
      res.on("error", reject);
    }).on("error", reject);
  });
}

async function downloadBinary() {
  const { key, file } = getPlatform();
  const installDir = getInstallDir();

  console.log(`${DIM}Platform: ${os.platform()}-${os.arch()} → ${file}${RESET}`);
  console.log(`${DIM}Install to: ${installDir}${RESET}\n`);

  fs.mkdirSync(installDir, { recursive: true });

  const url = `https://github.com/${REPO}/releases/latest/download/${file}`;
  console.log(`Downloading ${file}...`);

  const data = await download(url);
  const tmpFile = path.join(os.tmpdir(), file);
  fs.writeFileSync(tmpFile, data);

  console.log(`Extracting...`);

  if (key === "linux") {
    execFileSync("tar", ["xzf", tmpFile, "-C", installDir]);
    const bin = path.join(installDir, "fartrun");
    fs.chmodSync(bin, 0o755);
  } else if (key === "macos") {
    execFileSync("unzip", ["-o", tmpFile, "-d", installDir]);
    const bin = path.join(installDir, "fartrun");
    if (fs.existsSync(bin)) fs.chmodSync(bin, 0o755);
  } else if (key === "windows") {
    execFileSync("powershell", [
      "-NoProfile", "-Command",
      `Expand-Archive -Force -Path '${tmpFile}' -DestinationPath '${installDir}'`
    ]);
  }

  fs.unlinkSync(tmpFile);
  console.log(`${GREEN}Binary installed to ${installDir}/fartrun${RESET}\n`);
  return path.join(installDir, key === "windows" ? "fartrun.exe" : "fartrun");
}

function configureMcp(binaryPath, client) {
  const settingsPath = getSettingsPath(client);
  if (!settingsPath) {
    console.log(`${YELLOW}Unknown client: ${client}${RESET}`);
    return false;
  }

  const dir = path.dirname(settingsPath);
  fs.mkdirSync(dir, { recursive: true });

  let settings = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    } catch {
      settings = {};
    }
  }

  if (client === "claude-code") {
    if (!settings.mcpServers) settings.mcpServers = {};
    settings.mcpServers.fartrun = {
      command: binaryPath + "-mcp",
    };
  } else {
    if (!settings.mcpServers) settings.mcpServers = {};
    settings.mcpServers.fartrun = {
      command: binaryPath,
      args: ["mcp"],
    };
  }

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`${GREEN}MCP configured in ${settingsPath}${RESET}`);
  return true;
}

function printUsage() {
  console.log(`${LOGO}
${GREEN}Usage:${RESET}
  npx fartrun@latest install          Download binary + configure MCP
  npx fartrun@latest install --claude  Configure for Claude Code only
  npx fartrun@latest install --cursor  Configure for Cursor only
  npx fartrun@latest install --windsurf Configure for Windsurf only
  npx fartrun@latest mcp-config       Show MCP JSON config (manual setup)
  npx fartrun@latest --help           This message

${DIM}29 MCP tools. Rust security scanner. Zero tokens. Maximum flatulence.${RESET}
`);
}

function printMcpConfig() {
  const installDir = getInstallDir();
  const bin = path.join(installDir, os.platform() === "win32" ? "fartrun.exe" : "fartrun");

  console.log(`${GREEN}stdio (Claude Code settings.json):${RESET}
{
  "mcpServers": {
    "fartrun": { "command": "${bin}-mcp" }
  }
}

${GREEN}HTTP (Cursor / Windsurf):${RESET}
Run: ${bin} mcp --http --port 3001

{
  "mcpServers": {
    "fartrun": { "url": "http://localhost:3001/sse" }
  }
}
`);
}

async function install(flags) {
  console.log(LOGO);
  console.log("Installing Fartrun...\n");

  const binaryPath = await downloadBinary();

  const clients = [];
  if (flags.includes("--claude")) clients.push("claude-code");
  else if (flags.includes("--cursor")) clients.push("cursor");
  else if (flags.includes("--windsurf")) clients.push("windsurf");
  else clients.push("claude-code", "cursor", "windsurf");

  let configured = 0;
  for (const client of clients) {
    if (configureMcp(binaryPath, client)) configured++;
  }

  console.log(`
${GREEN}Done!${RESET} Fartrun MCP is ready.

  ${DIM}29 tools available. Restart your editor to pick them up.${RESET}
  ${DIM}Run "fartrun scan ." to try the CLI.${RESET}

  ${YELLOW}Make sure ${getInstallDir()} is in your PATH${RESET}
`);
}

// --- main ---

const args = process.argv.slice(2);
const command = args[0];

if (!command || command === "--help" || command === "-h") {
  printUsage();
} else if (command === "install") {
  install(args.slice(1)).catch((err) => {
    console.error(`${RED}Error: ${err.message}${RESET}`);
    process.exit(1);
  });
} else if (command === "mcp-config") {
  console.log(LOGO);
  printMcpConfig();
} else {
  console.log(`${RED}Unknown command: ${command}${RESET}\n`);
  printUsage();
  process.exit(1);
}
