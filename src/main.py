import time
import secrets
import json
import urllib.request
from pathlib import Path
from collections import deque
from importlib.metadata import version, PackageNotFoundError

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich.live import Live
from rich.prompt import Prompt

from .core.exceptions import XrayError, DockerOperationError
from .dependencies import get_docker_client, get_user_service, get_system_service


app = typer.Typer(help="CLI manager for Xray Reality proxy server.")
console = Console()

def resolve_service():
    """Wrapper to handle initialization errors gracefully in CLI."""
    try:
        return get_user_service()
    except Exception as e:
        console.print(f"[bold red]Critical Error during initialization:[/]\n{e}")
        raise typer.Exit(code=1)


def resolve_docker():
    """Wrapper to handle Docker connection errors gracefully."""
    try:
        return get_docker_client()
    except Exception as e:
        console.print(f"[bold red]Docker Connection Error:[/]\n{e}")
        raise typer.Exit(code=1)


def resolve_system_service():
    try:
        return get_system_service()
    except Exception as e:
        console.print(f"[bold red]System Service Error:[/]\n{e}")
        raise typer.Exit(code=1)


def sizeof_fmt(num: float, suffix: str = "B") -> str:
    """Converts a byte count into a human-readable string using binary prefixes.

     Args:
        num: The size in bytes to convert.
        suffix: The suffix to append to the unit. Defaults to "B".

    Returns:
        str: A formatted string (e.g., '12.5 MiB', '1.0 GiB').
    """
    for unit in ("", "Ki", "Mi", "Gi", "Ti"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Pi{suffix}"


def generate_sparkline(data: list[float], width: int = 40) -> str:
    """Generates a text-based sparkline chart using block characters."""
    if not data:
        return " " * width
    
    bar_chars = "  ▂▃▄▅▆▇█"
    
    recent_data = list(data)[-width:]
    
    if len(recent_data) < width:
        recent_data = [0.0] * (width - len(recent_data)) + recent_data
        
    max_val = max(recent_data) or 1
    
    result = ""
    for val in recent_data:
        idx = int((val / max_val) * (len(bar_chars) - 1))
        result += bar_chars[idx]
        
    return result


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


@app.command("init")
def initialize_server(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configs"),
    domain: str = typer.Option(None, "--domain", "-d", help="Masking domain (SNI) for Reality")
):
    """Automatically setups Xray: detects IP, generates keys, creates configs."""
    
    config_path = Path("config/config.json")
    env_path = Path(".env")
    example_config_path = Path("config/config.template.json")

    logs_path = Path("logs")
    logs_path.mkdir(exist_ok=True)

    if (config_path.exists() or env_path.exists()) and not force:
        console.print("[yellow]Configuration files already exist.[/]")
        if not Confirm.ask("Do you want to overwrite them?"):
            raise typer.Exit()
    
    docker = resolve_docker()

    with console.status("[bold blue]Detecting Server IP..."):
        try:
            with urllib.request.urlopen('https://api.ipify.org') as response:
                server_ip = response.read().decode('utf-8')
        except Exception:
            console.print("[red]Failed to detect IP automatically.[/]")
            server_ip = typer.prompt("Enter your Server IP manually")
    
    console.print(f"Server IP: [green]{server_ip}[/]")

    if not domain:
        default_domain = "web.max.ru"
        domain = typer.prompt("Enter masking domain (SNI)", default=default_domain)
    
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    console.print(f"Masking Domain: [green]{domain}[/]")

    with console.status("[bold blue]Generating X25519 Keys..."):
        try:
            priv_key, pub_key = docker.generate_x25519_keys()
        except Exception as e:
            console.print(f"[bold red]Failed to generate keys:[/]\n{e}")
            raise typer.Exit(code=1)
    
    short_id = secrets.token_hex(8)

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
            
            reality['dest'] = f"{domain}:443"
            reality['serverNames'] = [domain]
            
        except (KeyError, StopIteration):
            console.print("[red]Invalid example config format![/]")
            raise typer.Exit(code=1)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    
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
        f"SNI Domain:  [green]{domain}[/]",
        title="[bold green]Setup Completed Successfully![/]",
        border_style="green"
    ))
    
    console.print("\n[dim]Next step:[/]")
    console.print("[bold cyan]docker compose up -d[/]")
    console.print("[bold cyan]uv run xctl add <username>[/]\n")


@app.command("list")
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


@app.command("stats")
def user_stats(
    name: str = typer.Argument(None, help="Name of the user. Omit to see global stats.")
):
    """Shows traffic usage snapshot."""
    service = resolve_service()

    try:
        if name:
            data = service.get_user_traffic(name)
            up = data['traffic_up']
            down = data['traffic_down']
            total = data['total']
            
            title = f"[bold cyan]{name}[/]"
            subtitle = f"[dim]UUID: {data['id']}[/]"
            border_color = "white"
        else:
            users = service.get_users_with_stats()
            up = sum(u.get('traffic_up', 0) for u in users)
            down = sum(u.get('traffic_down', 0) for u in users)
            total = up + down
            
            title = "[bold]Global Server Stats[/]"
            subtitle = f"[dim]Active Users: {len(users)}[/]"
            border_color = "cyan"

    except ValueError as e:
        console.print(f"[bold red]Error:[/]\n{e}")
        raise typer.Exit(code=1)
    except XrayError as e:
        console.print(f"[bold red]System Error:[/]\n{e}")
        raise typer.Exit(code=1)
    
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="left", style="bold")
    grid.add_column(justify="right")

    grid.add_row("", "[u dim]Total Volume[/]")
    
    grid.add_row(
        "[blue]Upload (↑)[/]", 
        f"[blue]{sizeof_fmt(up)}[/]"
    )
    grid.add_row(
        "[green]Download (↓)[/]", 
        f"[green]{sizeof_fmt(down)}[/]"
    )
    
    grid.add_row("", "")
    
    grid.add_row(
        "[white]Total (∑)[/]", 
        f"[bold white]{sizeof_fmt(total)}[/]"
    )

    console.print(Panel(
        grid,
        title=title,
        subtitle=subtitle,
        border_style=border_color,
        expand=False
    ))


@app.command("add")
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


@app.command("link")
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


@app.command("remove")
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


@app.command("restart")
def restart_service():
    """Force restarts the Xray Docker container."""
    service = resolve_service()

    with console.status("[bold blue]Restarting Xray container..."):
        try:
            service.docker.restart()
        except XrayError as e:
            console.print(f"[bold red]Failed to restart:[/]\n{e}")
            raise typer.Exit(code=1)

    console.print("[bold green]Service restarted successfully.[/]")


@app.command("watch")
def watch_traffic(
    name: str = typer.Argument(None, help="Name of the user. Omit to see global stats."),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds")
):
    """Real-time traffic monitor."""
    service = resolve_service()

    history_len = 60
    
    history_up = deque(maxlen=history_len)
    history_down = deque(maxlen=history_len)
    last_snapshot = None

    total_seconds = int(history_len * interval)
    if total_seconds < 60:
        time_label = f"{total_seconds}s"
    else:
        minutes = round(total_seconds / 60, 1)
        if minutes.is_integer():
            minutes = int(minutes)
        time_label = f"{minutes}m"
    
    chart_header = f"[u dim]Activity ({time_label})[/]"

    def generate_view():
        nonlocal last_snapshot

        try:
            if name:
                data = service.get_user_traffic(name)
                curr_up_total = data['traffic_up']
                curr_down_total = data['traffic_down']
                title = f"[bold cyan]{name}[/]"
                subtitle_prefix = ""
                border_style = "white"
            else:
                users = service.get_users_with_stats()
                curr_up_total = sum(u.get('traffic_up', 0) for u in users)
                curr_down_total = sum(u.get('traffic_down', 0) for u in users)
                title = "[bold]Global Monitor[/]"
                subtitle_prefix = f"Users: {len(users)} | "
                border_style = "cyan"

        except Exception as e:
            return Panel(f"Error fetching stats: {e}", style="red")
        
        current_time = time.time()

        speed_up = 0.0
        speed_down = 0.0

        if last_snapshot:
            t_old, up_old, down_old = last_snapshot
            delta_time = current_time - t_old
            if delta_time > 0:
                speed_up = (curr_up_total - up_old) / delta_time
                speed_down = (curr_down_total - down_old) / delta_time
        
        last_snapshot = (current_time, curr_up_total, curr_down_total)

        history_up.append(speed_up)
        history_down.append(speed_down)

        speed_up_str = f"{sizeof_fmt(speed_up)}/s"
        speed_down_str = f"{sizeof_fmt(speed_down)}/s"

        chart_up = generate_sparkline(history_up, width=history_len)
        chart_down = generate_sparkline(history_down, width=history_len)

        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="left", style="bold")
        grid.add_column(justify="right")
        grid.add_column(justify="right")
        grid.add_column(justify="left", style="dim")
        
        grid.add_row("", "[u dim]Total Volume[/]", "[u dim]Current Speed[/]", chart_header)
        grid.add_row(
            "[blue]Upload (↑)[/]", 
            f"[blue]{sizeof_fmt(curr_up_total)}[/]", 
            f"[bold blue]{speed_up_str}[/]",
            f"[blue]{chart_up}[/]"
        )
        grid.add_row(
            "[green]Download (↓)[/]", 
            f"[green]{sizeof_fmt(curr_down_total)}[/]", 
            f"[bold green]{speed_down_str}[/]",
            f"[green]{chart_down}[/]"
        )

        return Panel(
            grid,
            title=title,
            subtitle=f"[dim]{subtitle_prefix}Refresh: {interval}s[/]",
            border_style=border_style,
            expand=False
        )
    
    header_target = f"[bold cyan]{name}[/]" if name else "Global Server"
    console.print(f"Monitoring: {header_target}   [dim]Press [white]Ctrl+C[/] to stop[/]\n")
    
    try:
        with Live(generate_view(), refresh_per_second=1/interval, transient=True) as live:
            while True:
                time.sleep(interval)
                live.update(generate_view())
    except KeyboardInterrupt:
        console.print("[yellow]Stopped.[/]")


@app.command("stop")
def stop_service():
    """Stops the Xray Docker container."""
    docker = resolve_docker()
    with console.status("[bold red]Stopping Xray server..."):
        try:
            docker.stop()
        except DockerOperationError as e:
            console.print(f"[red]Error:[/]\n{e}")
            raise typer.Exit(code=1)
    console.print("[bold red]Service stopped.[/]")


@app.command("start")
def start_service():
    """Starts the Xray Docker container."""
    docker = resolve_docker()
    with console.status("[bold green]Starting Xray server..."):
        try:
            docker.start()
        except DockerOperationError as e:
            console.print(f"[red]Error:[/]\n{e}")
            raise typer.Exit(code=1)
    console.print("[bold green]Service started.[/]")


@app.command("restore")
def restore_configuration(
    latest: bool = typer.Option(False, "--latest", help="Automatically restore the most recent backup without prompting")
):
    """Restores configuration from a backup file."""
    service = resolve_system_service()
    
    backups = service.get_backups()

    if not backups:
        console.print("[yellow]No backups found in config/backups/[/]")
        raise typer.Exit()

    if latest:
        target = backups[0]
    else:
        table = Table(title="Available Backups", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Date (UTC)", style="cyan")
        table.add_column("Filename", style="green")

        for idx, backup in enumerate(backups, 1):
            table.add_row(str(idx), backup['date'], backup['name'])
        
        console.print(table)
        
        choice = Prompt.ask(
            "Select backup number to restore", 
            choices=[str(i) for i in range(1, len(backups) + 1)],
            default="1"
        )
        target = backups[int(choice) - 1]

    console.print(f"\nSelected: [bold cyan]{target['name']}[/]")
    
    if not latest and not Confirm.ask("Are you sure you want to overwrite current config?"):
        console.print("[yellow]Operation cancelled.[/]")
        raise typer.Exit()

    with console.status("[bold blue]Restoring configuration and restarting Xray..."):
        try:
            service.restore_backup(target['path'])
        except Exception as e:
            console.print(f"[bold red]Restore Failed:[/]\n{e}")
            raise typer.Exit(code=1)

    console.print(f"[bold green]Successfully restored backup from {target['date']}![/]")


if __name__ == "__main__":
    app()
