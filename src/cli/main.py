from importlib.metadata import version, PackageNotFoundError

import typer

from .utils import console
from .commands import users, system, stats


app = typer.Typer(help="CLI manager for Xray Reality proxy server.")

app.command("list")(users.list_users)
app.command("add")(users.add_user)
app.command("remove")(users.remove_user)
app.command("link")(users.show_link)

app.command("init")(system.initialize_server)
app.command("start")(system.start_service)
app.command("stop")(system.stop_service)
app.command("restart")(system.restart_service)
app.command("restore")(system.restore_configuration)

app.command("stats")(stats.user_stats)
app.command("watch")(stats.watch_traffic)

def version_callback(value: bool):
    if value:
        try:
            v = version("xctl")
        except PackageNotFoundError:
            v = "unknown (dev)"
        
        console.print(f"xctl version: [bold cyan]{v}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, 
        "--version", 
        "-v", 
        callback=version_callback, 
        is_eager=True,
        help="Show the application version and exit."
    )
):
    return

if __name__ == "__main__":
    app()
