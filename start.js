const { spawn } = require("child_process");
const path = require("path");

const cwd = __dirname;

function run(name, cmd, args, extra = {}) {
  const child = spawn(cmd, args, {
    cwd: extra.cwd || cwd,
    env: { ...process.env, ...(extra.env || {}) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const tag = (buf, stream) => {
    String(buf)
      .split(/\r?\n/)
      .filter(Boolean)
      .forEach((line) => process[stream].write(`[${name}] ${line}\n`));
  };
  child.stdout.on("data", (d) => tag(d, "stdout"));
  child.stderr.on("data", (d) => tag(d, "stderr"));
  child.on("exit", (code) => {
    console.log(`[${name}] exited ${code}`);
    if (name === "api" || name === "web") process.exit(code || 1);
  });
  return child;
}

run("api", "python3", ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"], {
  cwd: path.join(cwd, "backend"),
});
run("web", "npm", ["run", "dev"], { cwd: path.join(cwd, "frontend") });
