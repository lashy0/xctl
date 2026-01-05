import secrets
import json
import urllib.request
from pathlib import Path

import typer
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.panel import Panel

from ...core.exceptions import XrayError, DockerOperationError
from ...core.verifier import RealityVerifier
from ..utils import resolve_service, resolve_docker, resolve_system_service, console


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

    if domain:
        console.print(f"Verifying provided SNI: [cyan]{domain}[/]")
        clean_domain = RealityVerifier.extract_hostname(domain)
        is_valid, msg = RealityVerifier.verify(clean_domain, forbidden_ip=server_ip)

        if not is_valid:
            console.print(f"[bold yellow]Warning:[/ {msg}")
            if not Confirm.ask("Do you want to proceed with this domain anyway?"):
                raise typer.Exit(code=1)
        else:
            console.print(f"[green]{msg}[/]")
            
        domain = clean_domain
    else:
        default_domain = "web.max.ru"
        while True:
            user_input = typer.prompt("Enter masking domain (SNI)", default=default_domain)
            clean_domain = RealityVerifier.extract_hostname(user_input)
            
            with console.status(f"[bold blue]Probing {clean_domain}..."):
                is_valid, msg = RealityVerifier.verify(clean_domain, forbidden_ip=server_ip)
            
            if is_valid:
                console.print(f"[green]{msg}[/]")
                domain = clean_domain
                break
            else:
                console.print(f"[bold red]Domain issue: {msg}[/]")
                console.print("[dim]A good domain must resolve, support TLS 1.3/H2, and not be this server.[/]")
                
                if Confirm.ask("Use this domain anyway (not recommended)?"):
                    domain = clean_domain
                    break
    
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

