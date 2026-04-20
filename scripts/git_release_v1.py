"""
Birinchi reliz: git init (kerak bo'lsa), commit, v1.0.0 teg.
Ishga tushirish: mf3 ildizidan  python scripts/git_release_v1.py
GitLab: keyin  git remote add origin <URL>  va  git push -u origin main --tags
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, shell=False)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main() -> None:
    if not (ROOT / ".git").exists():
        run(["git", "init"])

    run(["git", "add", "-A"])
    # Agar o'zgarish bo'lmasa, commit xato beradi — e'tiborsiz qoldiramiz
    c = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        shell=False,
    )
    if c.returncode != 0:
        run(
            [
                "git",
                "commit",
                "-m",
                "chore: release v1.0.0 — hayriyalar, lenta, profil asosi",
            ]
        )
    else:
        print("(Staged o'zgarish yo'q — commit o'tkazib yuborildi.)", flush=True)

    run(
        [
            "git",
            "tag",
            "-fa",
            "v1.0.0",
            "-m",
            "Version 1.0.0 — birinchi barqaror reliz (hayriyalar va asosiy funksiyalar)",
        ]
    )
    print("\nTayyor. Tekshirish:  git log -1 --oneline  &&  git show v1.0.0", flush=True)
    print(
        "\nGitLab:  git remote add origin https://gitlab.com/USERNAME/mf3.git\n"
        "         git branch -M main\n"
        "         git push -u origin main --tags",
        flush=True,
    )


if __name__ == "__main__":
    main()
