import secrets

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from .core.exceptions import XrayError


app = typer.Typer(help="CLI manager for Xray Reality proxy server.")
console = Console()

def get_service():
    """Helper to initialize UserService and handle startup errors."""
    from .services.user_service import UserService

    try:
        return UserService()
    except Exception as e:
        console.print(f"[bold red]Critical Error during initialization:[/]\n{e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_users():
    """Displays a table of all registered users."""
    service = get_service()
    
    try:
        users = service.get_users()
    except XrayError as e:
        console.print(f"[bold red]Error reading configuration:[/]\n{e}")
        raise typer.Exit(code=1)

    if not users:
        console.print("[yellow]No users found. Use 'add <name>' to create one.[/]")
        return
    
    table = Table(title="Xray Users", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Email (Name)", style="cyan", no_wrap=True)
    table.add_column("UUID", style="green")
    table.add_column("Flow", style="blue")

    for idx, user in enumerate(users, 1):
        table.add_row(
            str(idx),
            user.get("email", "N/A"),
            user.get("id", "N/A"),
            user.get("flow", "N/A")
        )

    console.print(table)


@app.command("add")
def add_user(name: str = typer.Argument(..., help="Unique name/email for the user")):
    """Creates a new user and generates a connection link.

    Automatically restarts the Xray container to apply changes.
    """
    service = get_service()

    with console.status(f"[bold green]Adding user '{name}' and restarting Xray..."):
        try:
            link = service.add_user(name)
        except ValueError as e:
            console.print(f"[bold red]Validation Error:[/]\n{e}")
            raise typer.Exit(code=1)
        except XrayError as e:
            console.print(f"[bold red]System Error:[/]\n{e}")
            raise typer.Exit(code=1)

    console.print(f"[bold green]User '{name}' successfully added![/]\n")
    
    console.print("[dim]VLESS Connection Link:[/]")
    console.print(f"[yellow]{link}[/]\n")


@app.command("link")
def show_link(name: str = typer.Argument(..., help="Name of the user")):
    """Retrieves the connection link for an existing user."""
    service = get_service()

    try:
        link = service.get_user_link(name)
    except ValueError as e:
        console.print(f"[bold red]Error:[/]\n{e}")
        raise typer.Exit(code=1)
    except XrayError as e:
        console.print(f"[bold red]System Error:[/]\n{e}")
        raise typer.Exit(code=1)
    
    console.print(f"[dim]Link for user '{name}':[/]")
    console.print(f"[yellow]{link}[/]")


@app.command("remove")
def remove_user(
    name: str = typer.Argument(..., help="Name of the user to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
):
    """Deletes a user and restarts the service."""
    service = get_service()

    if not force:
        if not Confirm.ask(f"Are you sure you want to delete user [cyan]{name}[/]?"):
            console.print("[yellow]Operation cancelled.[/]")
            return

    with console.status(f"[bold red]Removing user '{name}'..."):
        try:
            success = service.remove_user(name)
        except XrayError as e:
            console.print(f"[bold red]System Error:[/]\n{e}")
            raise typer.Exit(code=1)

    if success:
        console.print(f"[bold green]User '{name}' removed.[/]")
    else:
        console.print(f"[bold yellow]User '{name}' not found.[/]")


@app.command("restart")
def restart_service():
    """Force restarts the Xray Docker container."""
    service = get_service()

    with console.status("[bold blue]Restarting Xray container..."):
        try:
            service.docker.restart()
        except XrayError as e:
            console.print(f"[bold red]Failed to restart:[/]\n{e}")
            raise typer.Exit(code=1)

    console.print("[bold green]✔ Service restarted successfully.[/]")


@app.command("gen-id")
def generate_short_id(
    length: int = typer.Option(4, help="Length in bytes (default 4 = 8 hex chars)")
):
    """Generates a secure ShortId for Reality configuration."""
    sid = secrets.token_hex(length)
    console.print(f"ShortId: [bold green]{sid}[/]")


@app.command("gen-keys")
def generate_keys():
    """Generates new X25519 keys using the Xray container."""
    from .core.docker_controller import DockerController

    docker = DockerController("xray-core")
    
    with console.status("[bold blue]Generating keys via Xray..."):
        try:
            priv_key, pub_key = docker.generate_x25519_keys()
        except XrayError as e:
            console.print(f"[bold red]Error:[/]\n{e}")
            console.print("[dim]Make sure Docker is installed and running.[/]")
            raise typer.Exit(code=1)

    console.print()
    
    grid = Table.grid(padding=(0, 2))
    
    grid.add_column(justify="right", style="dim")
    grid.add_column(style="bold")

    grid.add_row("Private Key:", f"[green]{priv_key}[/]")
    grid.add_row("Public Key:",  f"[yellow]{pub_key}[/]")
    
    console.print(grid)
    console.print()


if __name__ == "__main__":
    app()
