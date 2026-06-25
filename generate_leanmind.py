#!/usr/bin/env python3
"""LeanMind AI — Python 一键生成 / 初始化 / 启动

基于《LeanMind AI 软件技术规格说明书（SPEC）V1.2》

用法:
  python generate_leanmind.py init       # 安装依赖 + 初始化数据库 + mock 数据
  python generate_leanmind.py run        # 启动 FastAPI 后端 (:8000)
  python generate_leanmind.py test       # 运行 API 测试（无需 LLM Key）
  python generate_leanmind.py seed       # 仅写入 mock 演示数据
  python generate_leanmind.py scaffold   # 检查并补全项目目录结构
  python generate_leanmind.py frontend   # 生成前端 env 与启动说明

环境变量（backend/.env 或 export）:
  LLM_PROVIDER=deepseek          # 或 qwen
  DEEPSEEK_API_KEY=sk-...        # DeepSeek（默认）
  DASHSCOPE_API_KEY=sk-...        # 阿里云 Qwen
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEANMIND = ROOT / "leanmind"
BACKEND = LEANMIND / "backend"
FRONTEND = LEANMIND / "frontend"
DATA = BACKEND / "data"


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    print(f"\n$ {' '.join(cmd)}\n")
    return subprocess.run(cmd, cwd=cwd or ROOT, check=check).returncode


def scaffold() -> None:
    """确保 SPEC monorepo 目录结构存在。"""
    dirs = [
        BACKEND / "app" / "agents",
        BACKEND / "app" / "tools",
        BACKEND / "skills" / "canvas-generate" / "scripts",
        BACKEND / "skills" / "canvas-refine",
        BACKEND / "skills" / "review-pressure",
        BACKEND / "skills" / "competitor-scan",
        BACKEND / "tests",
        BACKEND / "data",
        FRONTEND / "src" / "app",
        FRONTEND / "src" / "components",
        FRONTEND / "src" / "lib",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d.relative_to(ROOT)}")

    env_example = BACKEND / ".env.example"
    env_local = BACKEND / ".env"
    if env_example.exists() and not env_local.exists():
        shutil.copy(env_example, env_local)
        print(f"  ✓ 已复制 {env_local.relative_to(ROOT)}（请填入 API Key）")

    fe_env = FRONTEND / ".env.local"
    if not fe_env.exists() and FRONTEND.exists():
        fe_env.write_text(
            "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n",
            encoding="utf-8",
        )
        print(f"  ✓ 已生成 {fe_env.relative_to(ROOT)}")

    print("\n✅ 目录结构就绪。改 Skill → leanmind/backend/skills/*/SKILL.md")


def list_skills() -> None:
    skills_dir = BACKEND / "skills"
    print("LeanMind LocalSkills：")
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        print(f"  - {skill_md.parent.name}")
    print("\n详见 leanmind/ARCHITECTURE.md")


def install_deps() -> None:
    req = BACKEND / "requirements.txt"
    if not req.exists():
        print("❌ 缺少 requirements.txt，请先运行 scaffold")
        sys.exit(1)
    _run([sys.executable, "-m", "pip", "install", "-r", str(req)])


def init_db() -> None:
    sys.path.insert(0, str(BACKEND))
    from app.database import init_db as _init

    _init()
    print("✅ 数据库表已创建")


def seed_mock() -> None:
    _run([sys.executable, "seed_mock.py"], cwd=BACKEND, check=False)


def run_tests() -> int:
    return _run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=BACKEND,
        check=False,
    )


def run_backend(host: str = "0.0.0.0", port: int = 8000, *, reload: bool = False) -> None:
    sys.path.insert(0, str(BACKEND))
    init_db()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    _run(cmd, cwd=BACKEND, check=False)


def run_frontend() -> None:
    if not shutil.which("npm"):
        print("❌ 未检测到 npm。请安装 Node.js 18+ 后执行:")
        print(f"   cd {FRONTEND.relative_to(ROOT)} && npm install && npm run dev")
        sys.exit(1)
    if not (FRONTEND / "node_modules").exists():
        _run(["npm", "install"], cwd=FRONTEND)
    _run(["npm", "run", "dev", "--", "-H", "0.0.0.0"], cwd=FRONTEND, check=False)


def pack_for_mentor() -> Path:
    """打包前后端 + SPEC，排除 node_modules、.env、缓存。"""
    ts = datetime.now().strftime("%Y%m%d")
    out_zip = ROOT / f"LeanMind_AI_交付_{ts}.zip"

    skip_dirs = {
        "node_modules",
        ".next",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        ".git",
    }
    skip_files = {".env", ".DS_Store"}

    def should_skip(path: Path) -> bool:
        for part in path.parts:
            if part in skip_dirs:
                return True
        return path.name in skip_files

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        handoff = LEANMIND / "导师交付说明.md"
        explicit = {f.resolve() for f in [
            ROOT / "LeanMind_AI_SPEC初稿",
            ROOT / "generate_leanmind.py",
            ROOT / "lean_canvas.py",
            handoff,
        ] if f.exists()}

        for f in explicit:
            zf.write(f, f.relative_to(ROOT))

        for path in LEANMIND.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            if path.resolve() in explicit:
                continue
            zf.write(path, path.relative_to(ROOT))

    print(f"\n✅ 已打包: {out_zip}")
    print("   已排除: node_modules, .next, .env, 数据库缓存")
    print("   导师解压后请看 leanmind/导师交付说明.md")
    return out_zip


def cmd_pack(_: argparse.Namespace) -> None:
    pack_for_mentor()


def cmd_init(_: argparse.Namespace) -> None:
    scaffold()
    install_deps()
    init_db()
    seed_mock()
    print("\n" + "=" * 50)
    print("初始化完成！下一步:")
    print("  1. 编辑 leanmind/backend/.env 填入 DEEPSEEK_API_KEY")
    print("  2. python generate_leanmind.py run")
    print("  3. python generate_leanmind.py frontend  # 可选")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="LeanMind AI Python 生成器")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("scaffold", help="补全目录结构")
    sub.add_parser("skills", help="列出 Agno Skills")
    sub.add_parser("pack", help="打包前后端交付给导师（生成 zip）")
    sub.add_parser("init", help="安装依赖 + 初始化 DB + mock 数据")
    sub.add_parser("seed", help="写入 mock 演示数据")
    sub.add_parser("test", help="运行 API 测试")
    sub.add_parser("frontend", help="启动 Next.js 前端")

    p_run = sub.add_parser("run", help="启动 FastAPI 后端")
    p_run.add_argument("--host", default="0.0.0.0")
    p_run.add_argument("--port", type=int, default=8000)
    p_run.add_argument("--reload", action="store_true", help="代码变更自动重启（演示时建议关闭）")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    handlers = {
        "scaffold": lambda a: scaffold(),
        "skills": lambda a: list_skills(),
        "pack": cmd_pack,
        "init": cmd_init,
        "seed": lambda a: (init_db(), seed_mock()),
        "test": lambda a: sys.exit(run_tests()),
        "run": lambda a: run_backend(a.host, a.port, reload=a.reload),
        "frontend": lambda a: run_frontend(),
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
