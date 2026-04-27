#!/usr/bin/env node

const { createWriteStream } = require("fs");
const fs = require("fs");
const path = require("path");
const os = require("os");
const https = require("https");
const crypto = require("crypto");
const zlib = require("zlib");

const REPO = "ChuprinaDaria/Vibecode-Cleaner-Fartrun";
const VERSION = require(path.join(__dirname, "..", "package.json")).version;

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
  if (platform === "darwin" && arch === "arm64") {
    // Prefer native arm64 build, fall back to x64 via Rosetta
    return { key: "macos", file: "fartrun-macos-arm64.zip", fallback: "fartrun-macos-x64.zip" };
  }
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

// --- Streaming download with progress bar, retry, and SHA256 ---

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpsGet(res.headers.location).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      resolve(res);
    }).on("error", reject);
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function downloadToFile(url, destPath) {
  return new Promise(async (resolve, reject) => {
    try {
      const res = await httpsGet(url);
      const total = parseInt(res.headers["content-length"], 10) || 0;
      const hash = crypto.createHash("sha256");
      const file = createWriteStream(destPath);
      let downloaded = 0;

      res.on("data", (chunk) => {
        downloaded += chunk.length;
        hash.update(chunk);
        if (total > 0) {
          const pct = Math.round((downloaded / total) * 100);
          const bar = "█".repeat(Math.floor(pct / 4)) + "░".repeat(25 - Math.floor(pct / 4));
          process.stdout.write(`\r  ${bar} ${pct}% ${formatBytes(downloaded)}/${formatBytes(total)}`);
        } else {
          process.stdout.write(`\r  ${formatBytes(downloaded)} downloaded...`);
        }
      });

      res.pipe(file);

      file.on("finish", () => {
        process.stdout.write("\n");
        file.close(() => resolve(hash.digest("hex")));
      });
      file.on("error", (err) => {
        fs.unlink(destPath, () => {});
        reject(err);
      });
    } catch (err) {
      reject(err);
    }
  });
}

async function downloadWithRetry(url, destPath, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await downloadToFile(url, destPath);
    } catch (err) {
      if (attempt === retries) throw err;
      console.log(`${YELLOW}  Retry ${attempt + 1}/${retries}...${RESET}`);
    }
  }
}

async function fetchChecksums(tag) {
  const url = `https://github.com/${REPO}/releases/download/${tag}/SHA256SUMS.txt`;
  try {
    const res = await httpsGet(url);
    const chunks = [];
    for await (const chunk of res) chunks.push(chunk);
    const text = Buffer.concat(chunks).toString("utf8");
    const map = {};
    for (const line of text.split("\n")) {
      const [hash, name] = line.trim().split(/\s+/);
      if (hash && name) map[name] = hash;
    }
    return map;
  } catch {
    return null;
  }
}

// --- Node.js native extraction (no system tar/unzip/powershell) ---

function extractTarGz(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    // tar format: 512-byte header blocks
    const gunzip = zlib.createGunzip();
    const input = fs.createReadStream(archivePath);

    let buffer = Buffer.alloc(0);
    const files = [];

    gunzip.on("data", (chunk) => {
      buffer = Buffer.concat([buffer, chunk]);

      while (buffer.length >= 512) {
        // Read header
        const header = buffer.subarray(0, 512);

        // Check for end-of-archive (two zero blocks)
        if (header.every((b) => b === 0)) {
          buffer = buffer.subarray(512);
          continue;
        }

        // Parse name and size from header
        let name = header.subarray(0, 100).toString("utf8").replace(/\0/g, "");
        const sizeOctal = header.subarray(124, 136).toString("utf8").replace(/\0/g, "").trim();
        const size = parseInt(sizeOctal, 8) || 0;
        const typeFlag = header[156];

        // Handle UStar prefix
        const prefix = header.subarray(345, 500).toString("utf8").replace(/\0/g, "");
        if (prefix) name = prefix + "/" + name;

        // Calculate padded size (512-byte blocks)
        const paddedSize = Math.ceil(size / 512) * 512;
        const totalNeeded = 512 + paddedSize;

        if (buffer.length < totalNeeded) break; // Wait for more data

        if (typeFlag === 53 || name.endsWith("/")) {
          // Directory
          fs.mkdirSync(path.join(destDir, name), { recursive: true });
        } else if (typeFlag === 0 || typeFlag === 48) {
          // Regular file
          const fileData = buffer.subarray(512, 512 + size);
          const filePath = path.join(destDir, name);
          fs.mkdirSync(path.dirname(filePath), { recursive: true });
          fs.writeFileSync(filePath, fileData);
          files.push(filePath);
        }

        buffer = buffer.subarray(totalNeeded);
      }
    });

    gunzip.on("end", () => resolve(files));
    gunzip.on("error", reject);
    input.pipe(gunzip);
  });
}

function extractZip(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    const data = fs.readFileSync(archivePath);
    const files = [];

    // Find End of Central Directory record
    let eocdOffset = -1;
    for (let i = data.length - 22; i >= 0; i--) {
      if (data.readUInt32LE(i) === 0x06054b50) { eocdOffset = i; break; }
    }
    if (eocdOffset === -1) return reject(new Error("Invalid zip: no EOCD"));

    const cdOffset = data.readUInt32LE(eocdOffset + 16);
    const cdEntries = data.readUInt16LE(eocdOffset + 10);

    let pos = cdOffset;
    for (let i = 0; i < cdEntries; i++) {
      if (data.readUInt32LE(pos) !== 0x02014b50) break;

      const compMethod = data.readUInt16LE(pos + 10);
      const compSize = data.readUInt32LE(pos + 20);
      const uncompSize = data.readUInt32LE(pos + 24);
      const nameLen = data.readUInt16LE(pos + 28);
      const extraLen = data.readUInt16LE(pos + 30);
      const commentLen = data.readUInt16LE(pos + 32);
      const localHeaderOffset = data.readUInt32LE(pos + 42);
      const name = data.subarray(pos + 46, pos + 46 + nameLen).toString("utf8");

      pos += 46 + nameLen + extraLen + commentLen;

      if (name.endsWith("/")) {
        fs.mkdirSync(path.join(destDir, name), { recursive: true });
        continue;
      }

      // Read local file header to get actual data offset
      const localNameLen = data.readUInt16LE(localHeaderOffset + 26);
      const localExtraLen = data.readUInt16LE(localHeaderOffset + 28);
      const dataOffset = localHeaderOffset + 30 + localNameLen + localExtraLen;

      const raw = data.subarray(dataOffset, dataOffset + compSize);
      let fileData;

      if (compMethod === 0) {
        fileData = raw;
      } else if (compMethod === 8) {
        fileData = zlib.inflateRawSync(raw);
      } else {
        console.log(`${YELLOW}  Skipping ${name} (unsupported compression ${compMethod})${RESET}`);
        continue;
      }

      const filePath = path.join(destDir, name);
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, fileData);
      files.push(filePath);
    }

    resolve(files);
  });
}

// --- Main download + extract flow ---

async function downloadBinary() {
  const platInfo = getPlatform();
  const installDir = getInstallDir();

  console.log(`${DIM}Platform: ${os.platform()}-${os.arch()} → ${platInfo.file}${RESET}`);
  console.log(`${DIM}Install to: ${installDir}${RESET}\n`);

  fs.mkdirSync(installDir, { recursive: true });

  // Try to fetch checksums
  const checksums = await fetchChecksums("latest");
  if (checksums) {
    console.log(`${DIM}SHA256 checksums found — will verify after download${RESET}`);
  }

  let file = platInfo.file;
  const url = `https://github.com/${REPO}/releases/latest/download/${file}`;
  const tmpFile = path.join(os.tmpdir(), file);

  console.log(`Downloading ${file}...`);

  let sha256;
  try {
    sha256 = await downloadWithRetry(url, tmpFile);
  } catch (err) {
    // arm64: fall back to x64 via Rosetta
    if (platInfo.fallback) {
      console.log(`${YELLOW}arm64 build not available yet — falling back to x64 (Rosetta)${RESET}`);
      file = platInfo.fallback;
      const fallbackUrl = `https://github.com/${REPO}/releases/latest/download/${file}`;
      sha256 = await downloadWithRetry(fallbackUrl, path.join(os.tmpdir(), file));
    } else {
      throw err;
    }
  }

  // Verify checksum
  if (checksums) {
    const expected = checksums[file];
    if (expected) {
      if (sha256 === expected) {
        console.log(`${GREEN}SHA256 verified ✓${RESET}`);
      } else {
        fs.unlinkSync(tmpFile);
        console.error(`${RED}SHA256 MISMATCH — download may be corrupted or tampered with${RESET}`);
        console.error(`${RED}  Expected: ${expected}${RESET}`);
        console.error(`${RED}  Got:      ${sha256}${RESET}`);
        process.exit(1);
      }
    } else {
      console.log(`${YELLOW}No checksum for ${file} in SHA256SUMS.txt — skipping verify${RESET}`);
    }
  }

  console.log(`Extracting...`);

  const actualTmp = path.join(os.tmpdir(), file);
  if (file.endsWith(".tar.gz")) {
    await extractTarGz(actualTmp, installDir);
    const bin = path.join(installDir, "fartrun");
    if (fs.existsSync(bin)) fs.chmodSync(bin, 0o755);
  } else if (file.endsWith(".zip")) {
    await extractZip(actualTmp, installDir);
    const bin = path.join(installDir, "fartrun");
    if (fs.existsSync(bin)) fs.chmodSync(bin, 0o755);
  }

  fs.unlinkSync(actualTmp);
  console.log(`${GREEN}Binary installed to ${installDir}/fartrun${RESET}\n`);
  return path.join(installDir, platInfo.key === "windows" ? "fartrun.exe" : "fartrun");
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

  if (!settings.mcpServers) settings.mcpServers = {};
  settings.mcpServers.fartrun = {
    command: binaryPath,
    args: ["mcp"],
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`${GREEN}MCP configured in ${settingsPath}${RESET}`);
  return true;
}

function printUsage() {
  console.log(`${LOGO}
  Installs MCP server only. Desktop GUI → Releases page.

${GREEN}Usage:${RESET}
  npx fartrun@latest install           Download MCP binary + configure editor
  npx fartrun@latest install --claude   Claude Code only
  npx fartrun@latest install --cursor   Cursor only
  npx fartrun@latest install --windsurf Windsurf only
  npx fartrun@latest mcp-config        Show MCP JSON config (manual setup)
  npx fartrun@latest --help            This message

${DIM}29 MCP tools. Rust security scanner. Zero tokens. Maximum flatulence.${RESET}
`);
}

function printMcpConfig() {
  const installDir = getInstallDir();
  const bin = path.join(installDir, os.platform() === "win32" ? "fartrun.exe" : "fartrun");

  console.log(`${GREEN}stdio (Claude Code / Cursor / Windsurf):${RESET}
{
  "mcpServers": {
    "fartrun": { "command": "${bin}", "args": ["mcp"] }
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
  console.log("Installing Fartrun MCP server...\n");

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
  ${DIM}Run "fartrun scan ." to try the CLI scanner.${RESET}

  ${YELLOW}Make sure ${getInstallDir()} is in your PATH${RESET}

  ${DIM}Desktop GUI → download separately from Releases:${RESET}
  ${DIM}https://github.com/${REPO}/releases${RESET}
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
