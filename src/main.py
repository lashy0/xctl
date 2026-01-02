import secrets
import json
import urllib.request
from pathlib import Path

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


@app.command("init")
def initialize_server(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configs")
):
    """Automatically setups Xray: detects IP, generates keys, creates configs."""
    
    config_path = Path("config/config.json")
    env_path = Path(".env")
    example_config_path = Path("config/config.example.json")

    if (config_path.exists() or env_path.exists()) and not force:
        console.print("[yellow]Configuration files already exist.[/]")
        if not Confirm.ask("Do you want to overwrite them?"):
            raise typer.Exit()

    from .core.docker_controller import DockerController
    docker = DockerController("xray-core")

    with console.status("[bold blue]Detecting Server IP..."):
        try:
            with urllib.request.urlopen('https://api.ipify.org') as response:
                server_ip = response.read().decode('utf-8')
        except Exception:
            console.print("[red]Failed to detect IP automatically.[/]")
            server_ip = typer.prompt("Enter your Server IP manually")
    
    console.print(f"Server IP: [green]{server_ip}[/]")

    with console.status("[bold blue]Generating X25519 Keys..."):
        try:
            priv_key, pub_key = docker.generate_x25519_keys()
        except Exception as e:
            console.print(f"[bold red]Failed to generate keys:[/]\n{e}")
            raise typer.Exit(code=1)
    
    short_id = secrets.token_hex(4)

    with console.status("[bold blue]Creating config.json..."):
        if not example_config_path.exists():
             console.print("[red]Error: config/config.example.json missing![/]")
             raise typer.Exit(code=1)
        
        with open(example_config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        try:
            inbound = next(i for i in config_data['inbounds'] 
                         if i['protocol'] == 'vless' and i['streamSettings']['security'] == 'reality')
            
            reality = inbound['streamSettings']['realitySettings']
            reality['privateKey'] = priv_key
            reality['shortIds'] = [short_id]
            
            reality['dest'] = "web.max.ru:443"
            reality['serverNames'] = ["web.max.ru"]
            
        except (KeyError, StopIteration):
            console.print("[red]Invalid example config format![/]")
            raise typer.Exit(code=1)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    # 6. Создание .env
    with console.status("[bold blue]Creating .env file..."):
        env_content = (
            f"SERVER_IP={server_ip}\n"
            f"XRAY_PORT=443\n"
            f"XRAY_PUB_KEY={pub_key}\n"
        )
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)

    console.print(Panel(
        f"Private Key: [green]{priv_key}[/]\n"
        f"Public Key:  [green]{pub_key}[/]\n"
        f"Short ID:    [green]{short_id}[/]\n"
        f"Server IP:   [green]{server_ip}[/]",
        title="[bold green]Setup Completed Successfully![/]",
        border_style="green"
    ))
    
    console.print("\n[dim]Now run:[/]")
    console.print("[bold cyan]docker compose up -d[/]")
    console.print("[bold cyan]uv run xctl add <username>[/]")


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


if __name__ == "__main__":
    app()
