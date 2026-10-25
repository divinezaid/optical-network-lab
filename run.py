"""One entry point for everything (works on Windows without make).

    python run.py test     # full pytest suite + HTML report in reports/
    python run.py plots    # regenerate plots/
    python run.py all      # both
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test() -> int:
    (ROOT / "reports").mkdir(exist_ok=True)
    return subprocess.call(
        [sys.executable, "-m", "pytest", "--html=reports/report.html", "--self-contained-html"],
        cwd=ROOT,
    )


def plots() -> int:
    return subprocess.call([sys.executable, "scripts/plot_link.py"], cwd=ROOT)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "test":
        return test()
    if target == "plots":
        return plots()
    if target == "all":
        return test() or plots()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
