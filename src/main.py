import time
import secrets
import json
import urllib.request
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich.live import Live

from .core.exceptions import XrayError, DockerOperationError
from .dependencies import get_docker_client, get_user_service


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


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Pi{suffix}"


@app.command("init")
def initialize_server(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configs")
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
            
            reality['dest'] = "web.max.ru:443"
            reality['serverNames'] = ["web.max.ru"]
            
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
        title="[bold green]Setup Completed Successfully![/]",
        border_style="green"
    ))
    
    console.print("\n[dim]Now run:[/]")
    console.print("[bold cyan]docker compose up -d[/]")
    console.print("[bold cyan]uv run xctl add <username>[/]")


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
    """Shows traffic usage snapshot. Specify a name for user stats, or leave empty for server totals."""
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
    """Creates a new user and generates a connection link.

    Automatically restarts the Xray container to apply changes.
    """
    service = resolve_service()

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
    """Deletes a user and restarts the service."""
    service = resolve_service()

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
    service = resolve_service()

    with console.status("[bold blue]Restarting Xray container..."):
        try:
            service.docker.restart()
        except XrayError as e:
            console.print(f"[bold red]Failed to restart:[/]\n{e}")
            raise typer.Exit(code=1)

    console.print("[bold green]Service restarted successfully.[/]")


@app.command("watch")
def watch_server(
    interval: float = typer.Option(1.0, help="Refresh interval in seconds")
):
    """Real-time dashboard showing TOTAL server traffic and speed."""
    service = resolve_service()
    prev_state = None
    
    def generate_view():
        nonlocal prev_state
        
        try:
            users = service.get_users_with_stats()
        except Exception as e:
            return Panel(f"Error fetching stats: {e}", style="red")
        
        total_up = sum(u.get('traffic_up', 0) for u in users)
        total_down = sum(u.get('traffic_down', 0) for u in users)
        active_users_count = len(users)
        
        current_time = time.time()
        
        speed_up_str = "0.0 B/s"
        speed_down_str = "0.0 B/s"
        
        if prev_state:
            delta_time = current_time - prev_state['time']
            delta_up = total_up - prev_state['up']
            delta_down = total_down - prev_state['down']
            
            if delta_time > 0:
                spd_up = delta_up / delta_time
                spd_down = delta_down / delta_time
                
                speed_up_str = f"{sizeof_fmt(spd_up)}/s"
                speed_down_str = f"{sizeof_fmt(spd_down)}/s"
                
                if spd_up > 1024 * 1024: speed_up_str = f"[bold blue]{speed_up_str}[/]"
                if spd_down > 1024 * 1024: speed_down_str = f"[bold green]{speed_down_str}[/]"

        prev_state = {
            'up': total_up,
            'down': total_down,
            'time': current_time
        }

        grid = Table.grid(padding=(0, 2))
        
        grid.add_column(justify="left", style="bold")
        grid.add_column(justify="right")
        grid.add_column(justify="right")
        
        grid.add_row("", "[u dim]Total Volume[/]", "[u dim]Current Speed[/]")
        
        grid.add_row(
            "[blue]Total Upload (↑)[/]", 
            f"[blue]{sizeof_fmt(total_up)}[/]", 
            speed_up_str
        )
        grid.add_row(
            "[green]Total Download (↓)[/]", 
            f"[green]{sizeof_fmt(total_down)}[/]", 
            speed_down_str
        )

        return Panel(
            grid,
            title="[bold]Global Monitor[/]",
            subtitle=f"[dim]Users: {active_users_count} | Refresh: {interval}s[/]",
            border_style="cyan",
            expand=False
        )
    
    console.print(f"Global Monitor   [dim]Press [white]Ctrl+C[/] to stop[/]\n")

    try:
        with Live(generate_view(), refresh_per_second=4, transient=True) as live:
            while True:
                time.sleep(interval)
                live.update(generate_view())
    except KeyboardInterrupt:
        console.print("[yellow]Stopped.[/]")


@app.command("watch-user")
def watch_single_user(
    name: str = typer.Argument(..., help="Name of the user to monitor"),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds")
):
    """Real-time dashboard for a SINGLE user (Upload/Download speeds)."""
    service = resolve_service()
    
    prev_state = None
    
    def generate_view():
        nonlocal prev_state
        
        try:
            user_data = service.get_user_traffic(name)
        except Exception as e:
            return Panel(f"Error: {e}", style="red")
            
        current_time = time.time()
        curr_up = user_data['traffic_up']
        curr_down = user_data['traffic_down']
        
        speed_up_str = "0.0 B/s"
        speed_down_str = "0.0 B/s"
        
        if prev_state:
            delta_time = current_time - prev_state['time']
            delta_up = curr_up - prev_state['up']
            delta_down = curr_down - prev_state['down']
            
            if delta_time > 0:
                spd_up = delta_up / delta_time
                spd_down = delta_down / delta_time
                
                speed_up_str = f"{sizeof_fmt(spd_up)}/s"
                speed_down_str = f"{sizeof_fmt(spd_down)}/s"

                if spd_up > 1024: speed_up_str = f"[bold blue]{speed_up_str}[/]"
                if spd_down > 1024: speed_down_str = f"[bold green]{speed_down_str}[/]"
        
        prev_state = {
            'up': curr_up,
            'down': curr_down,
            'time': current_time
        }
        
        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="left", style="bold")
        grid.add_column(justify="right")
        grid.add_column(justify="right")
        
        grid.add_row("", "[u dim]Total Volume[/]", "[u dim]Current Speed[/]")
        
        grid.add_row(
            "[blue]Upload (↑)[/]", 
            f"[blue]{sizeof_fmt(curr_up)}[/]", 
            speed_up_str
        )
        grid.add_row(
            "[green]Download (↓)[/]", 
            f"[green]{sizeof_fmt(curr_down)}[/]", 
            speed_down_str
        )
        
        return Panel(
            grid,
            title=f"[bold cyan]{name}[/]",
            subtitle=f"[dim]Refresh: {interval}s[/]",
            border_style="white",
            expand=False
        )

    console.print(f"Monitoring target: [bold cyan]{name}[/]   [dim]Press [white]Ctrl+C[/] to stop[/]\n")
    
    try:
        with Live(generate_view(), refresh_per_second=10, transient=True) as live:
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


if __name__ == "__main__":
    app()
