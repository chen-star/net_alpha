"""`net-alpha service ...` Typer subcommand group."""

from __future__ import annotations

import json as _json

import typer

from net_alpha.service import control

service_app = typer.Typer(no_args_is_help=True, help="Manage the always-on local service.")


@service_app.command("install")
def install_cmd(port: int = typer.Option(8765, "--port", help="Port to bind on (default 8765).")):
    control.install(port=port)
    typer.echo(f"Installed. Service running on http://127.0.0.1:{port}")


@service_app.command("uninstall")
def uninstall_cmd():
    control.uninstall()
    typer.echo("Uninstalled. (Data at ~/.net_alpha left untouched.)")


@service_app.command("start")
def start_cmd():
    control.start()
    typer.echo("Service started.")


@service_app.command("stop")
def stop_cmd():
    control.stop(reason="cli stop")
    typer.echo("Service stopped. It will not auto-restart.")


@service_app.command("restart")
def restart_cmd():
    control.restart()
    typer.echo("Service restarted.")


@service_app.command("pause")
def pause_cmd():
    control.pause()
    typer.echo("Service paused (web UI stays up; jobs frozen).")


@service_app.command("resume")
def resume_cmd():
    control.resume()
    typer.echo("Service resumed.")


@service_app.command("status")
def status_cmd(json: bool = typer.Option(False, "--json", help="Emit JSON for scripting.")):
    s = control.status()
    if json:
        typer.echo(
            _json.dumps(
                {
                    "installed": s.installed,
                    "running": s.running,
                    "paused": s.paused,
                    "pid": s.pid,
                    "disabled": s.disabled,
                }
            )
        )
        return
    if not s.installed:
        typer.echo("Not installed.")
        return
    if s.disabled:
        typer.echo("Stopped (disabled flag set).")
        return
    state = "Running" if s.running else "Idle"
    pid_str = f" pid {s.pid}" if s.pid else ""
    typer.echo(f"{state}{pid_str}")


@service_app.command("logs")
def logs_cmd(
    follow: bool = typer.Option(False, "-f", "--follow", help="Tail the log."),
    lines: int = typer.Option(50, "-n", "--lines", help="Lines from the end."),
):
    control.logs(follow=follow, lines=lines)
