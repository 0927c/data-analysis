"""SandboxExecution: 轻量级 subprocess 沙盒，带超时和资源隔离。"""

import asyncio
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExecutionResult:
    """沙盒执行结果。"""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    duration_ms: float


class SandboxExecution:
    """
    通过 Python subprocess 执行任意代码，带超时控制。
    不使用 Docker（Windows 开发环境），通过超时和环境清理实现基本隔离。
    """

    def __init__(
        self,
        timeout_sec: int = 30,
        work_dir: Optional[Path] = None,
    ):
        self._timeout = timeout_sec
        self._work_dir = work_dir or Path("backend/data/sandbox")
        self._work_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, code: str, env: Optional[dict] = None) -> ExecutionResult:
        """
        在子进程中执行 Python 代码。
        写入临时文件 → 执行 → 捕获输出 → 清理。
        """
        script_path = self._work_dir / f"_sandbox_{hash(code)}.py"
        try:
            script_path.write_text(code, encoding="utf-8")
            start = time.monotonic()

            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._work_dir),
                env={**_safe_env(), **(env or {})},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = b"", b"Timeout exceeded"

            duration = (time.monotonic() - start) * 1000

            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=proc.returncode or -1,
                duration_ms=duration,
            )
        finally:
            if script_path.exists():
                script_path.unlink()


def _safe_env() -> dict:
    """返回白名单环境变量，避免泄露敏感信息。"""
    safe_keys = {"PATH", "PYTHONPATH", "HOME", "USERPROFILE", "SYSTEMROOT", "TEMP", "TMP"}
    return {k: v for k, v in os.environ.items() if k in safe_keys}
