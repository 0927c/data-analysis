const { execSync } = require("child_process");
try {
  const result = execSync("npm install @flue/runtime@0.9.1", {
    cwd: __dirname,
    encoding: "utf8",
    stdio: "pipe",
    timeout: 60000,
  });
  console.log("INSTALL OUTPUT:", result.substring(0, 500));
} catch (e) {
  console.log("ERROR:", e.message.substring(0, 500));
  console.log("STDOUT:", (e.stdout || "").substring(0, 500));
  console.log("STDERR:", (e.stderr || "").substring(0, 500));
}

// Check if installed
try {
  const fs = require("fs");
  const installed = fs.existsSync(__dirname + "/node_modules/@flue/runtime");
  console.log("Flue installed:", installed);
} catch (_) {}
