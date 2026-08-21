"""main 병합 전에 작업자 전용 루트 CLAUDE.md가 Git에 남아 있는지 검사한다."""

import subprocess


def main() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "CLAUDE.md"],
        capture_output=True,
        check=False,
        text=True,
    ).returncode == 0
    if tracked:
        raise SystemExit(
            "Root CLAUDE.md is worker-specific. Delete it from the PR branch "
            "or cherry-pick implementation commits only."
        )
    print("OK: worker-only root CLAUDE.md is not present.")


if __name__ == "__main__":
    main()
