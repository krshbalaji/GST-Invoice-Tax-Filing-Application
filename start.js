const { spawn } = require("child_process");
const path = require("path");

const cwd = __dirname;
const isWin = process.platform === "win32";

function pythonCmd() {
  if (process.env.PYTHON) return process.env.PYTHON;
  return isWin ? "python" : "python3";
}

function npmCmd() {
  return isWin ? "npm.cmd" : "npm";
}

function run(name, cmd, args, extra = {}) {
  const child = spawn(cmd, args, {
    cwd: extra.cwd || cwd,
    env: { ...process.env, ...(extra.env || {}) },
    stdio: ["ignore", "pipe", "pipe"],
    shell: isWin,
  });
  const tag = (buf, stream) => {
    String(buf)
      .split(/\r?\n/)
      .filter(Boolean)
      .forEach((line) => process[stream].write(`[${name}] ${line}\n`));
  };
  child.stdout.on("data", (d) => tag(d, "stdout"));
  child.stderr.on("data", (d) => tag(d, "stderr"));
  child.on("error", (err) => {
    console.error(`[${name}] failed to start: ${err.message}`);
    process.exit(1);
  });
  child.on("exit", (code) => {
    console.log(`[${name}] exited ${code}`);
    if (name === "api" || name === "web") process.exit(code || 1);
  });
  return child;
}

run("api", pythonCmd(), ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"], {
  cwd: path.join(cwd, "backend"),
});
run("web", npmCmd(), ["run", "dev"], { cwd: path.join(cwd, "frontend") });
