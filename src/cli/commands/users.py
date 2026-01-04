import typer
from rich.table import Table
from rich.prompt import Confirm

from ...core.exceptions import XrayError
from ..utils import resolve_service, console


def list_users():
    """Displays a table of all registered users."""
    service = resolve_service()
    
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


def add_user(name: str = typer.Argument(..., help="Unique name/email for the user")):
    """Creates a new user and generates a connection link."""
    service = resolve_service()

    with console.status(f"[bold green]Adding user '{name}' and reloading config..."):
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


def remove_user(
    name: str = typer.Argument(..., help="Name of the user to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
):
    """Deletes a user and reloads the service."""
    service = resolve_service()

    if not force:
        if not Confirm.ask(f"Are you sure you want to delete user [cyan]{name}[/]?"):
            console.print("[yellow]Operation cancelled.[/]")
            return

    with console.status(f"[bold red]Removing user '{name}' and reloading config..."):
        try:
            success = service.remove_user(name)
        except XrayError as e:
            console.print(f"[bold red]System Error:[/]\n{e}")
            raise typer.Exit(code=1)

    if success:
        console.print(f"[bold green]User '{name}' removed.[/]")
    else:
        console.print(f"[bold yellow]User '{name}' not found.[/]")


def show_link(name: str = typer.Argument(..., help="Name of the user")):
    """Retrieves the connection link for an existing user."""
    service = resolve_service()

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
