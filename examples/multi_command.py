"""Multi-command CLI demonstrating TyperPlus aliases, subgroups, and --version."""

from typing import Annotated

import typer

from mm_clikit import TyperPlus, fatal, print_json, print_plain, print_table

app = TyperPlus(package_name="mm-clikit")

# -- Config subgroup --
config_app = TyperPlus()


@config_app.command("show")
def config_show(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show current configuration."""
    data = {"host": "localhost", "port": 8080, "workers": 4}
    if as_json:
        print_json(data)
    else:
        print_table(
            columns=["Key", "Value"],
            rows=[[k, str(v)] for k, v in data.items()],
            title="Configuration",
        )


app.add_typer(config_app, name="config", aliases=["cfg"], help="Configuration subcommands.")


@app.callback()
def main(
    debug: Annotated[bool, typer.Option(help="Enable debug output.")] = False,
) -> None:
    """Server management tool."""
    if debug:
        print_plain("[debug mode enabled]")


@app.command("status", aliases=["st"])
def status() -> None:
    """Show server status."""
    print_table(
        columns=["Service", "Status", "PID"],
        rows=[
            ["api", "running", "1234"],
            ["worker", "running", "1235"],
            ["scheduler", "stopped", "-"],
        ],
        title="Services",
    )


@app.command("deploy", aliases=["d"])
def deploy(
    service: Annotated[str, typer.Argument(help="Service name to deploy.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without deploying.")] = False,
) -> None:
    """Deploy a service."""
    if service not in ("api", "worker", "scheduler"):
        fatal(f"unknown service: {service}")
    if dry_run:
        print_plain(f"[dry-run] would deploy {service}")
    else:
        print_plain(f"Deployed {service} successfully.")


if __name__ == "__main__":
    app()
