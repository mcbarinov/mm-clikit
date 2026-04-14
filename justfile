set dotenv-load := true

version := `uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'`


clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage dist build src/*.egg-info

build: clean
    uv build

format:
    uv run ruff check --select I --fix src tests examples
    uv run ruff format src tests examples

test:
    uv run pytest -n auto tests

lint: format pre-commit
    uv run ruff check src tests examples
    uv run ty check
    uv run mypy src

examples:
    #!/usr/bin/env bash
    for f in examples/*.py; do
        echo "--- $f ---"
        uv run "$f" --help
    done

audit:
    uv export --no-dev --all-extras --format requirements-txt --no-emit-project > requirements.txt
    uv run pip-audit -r requirements.txt --disable-pip
    rm requirements.txt
    uv run bandit -q -r -c "pyproject.toml" src

publish: build lint audit test
    git diff-index --quiet HEAD
    printf "Enter PyPI token: " && IFS= read -rs TOKEN && echo && uv publish --token "$TOKEN"
    git tag -a 'v{{version}}' -m 'v{{version}}'
    git push origin v{{version}}

sync:
    uv sync --all-extras

pre-commit:
    uv run pre-commit run --all-files

pre-commit-autoupdate:
    uv run pre-commit autoupdate

sync-docs *args:
    #!/usr/bin/env bash
    set -euo pipefail
    : "${CLI_PROJECTS:?CLI_PROJECTS not set in .env}"
    src="docs/cli-architecture.md"
    apply=false
    [[ "{{args}}" == "apply" ]] && apply=true
    for proj in $CLI_PROJECTS; do
        proj="${proj/#\~/$HOME}"
        dst="$proj/docs/cli-architecture.md"
        if [[ ! -f "$dst" ]]; then
            echo "skip (no target): $dst"
            continue
        fi
        if cmp -s "$src" "$dst"; then
            echo "unchanged: $dst"
            continue
        fi
        if $apply; then
            cp "$src" "$dst"
            echo "updated:   $dst"
        else
            echo "would update: $dst"
        fi
    done
    $apply || echo "(dry run — re-run with 'just sync-docs apply' to write)"
