import json
from pathlib import Path

import typer
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.panel import Panel

from ...core.exceptions import XrayError, DockerOperationError
from ...core.verifier import DomainVerifier
from ...core.network import NetworkUtils
from ...core.protocol_factory import get_handler
from ..utils import resolve_service, resolve_docker, resolve_system_service, console


def initialize_server(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configs"),
    domain: str = typer.Option(None, "--domain", "-d", help="Masking domain (SNI) for Reality"),
    protocol: str = typer.Option("vless-reality", "--protocol", "-p", help="Xray protocol to use")
):
    """Automatically setups Xray with the selected protocol."""
    
    config_path = Path("config/config.json")
    env_path = Path(".env")
    template_path = Path(f"config/templates/config.{protocol}.json")

    logs_path = Path("logs")
    logs_path.mkdir(exist_ok=True)

    if (config_path.exists() or env_path.exists()) and not force:
        console.print("[yellow]Configuration files already exist.[/]")
        if not Confirm.ask("Do you want to overwrite them?"):
            raise typer.Exit()
    
    if not template_path.exists():
        console.print(f"[bold red]Error:[/ Template for protocol '{protocol}' not found!")
        console.print(f"Expected file at: [blue]{template_path}[/]")
        raise typer.Exit(code=1)
    
    docker = resolve_docker()

    server_ip = ""
    with console.status("[bold blue]Detecting Server IP..."):
        detected_ip = NetworkUtils.get_public_ip()
    
    if detected_ip:
        server_ip = detected_ip
    else:
        console.print("[red]Failed to detect IP automatically (all providers unreachable).[/]")
        server_ip = typer.prompt("Enter your Server IP manually")
    
    console.print(f"Server IP: [green]{server_ip}[/]")

    handler = get_handler(protocol)

    final_domain = None
    if handler.requires_domain:
        if domain:
            console.print(f"Verifying provided SNI: [cyan]{domain}[/]")
            clean_domain = DomainVerifier.extract_hostname(domain)
            is_valid, msg = DomainVerifier.verify(clean_domain, forbidden_ip=server_ip)

            if not is_valid:
                console.print(f"[bold yellow]Warning:[/ {msg}")
                if not Confirm.ask("Do you want to proceed with this domain anyway?"):
                    raise typer.Exit(code=1)
            else:
                console.print(f"[green]{msg}[/]")
                
            final_domain = clean_domain
        else:
            default_domain = "web.max.ru"
            while True:
                user_input = typer.prompt("Enter masking domain (SNI)", default=default_domain)
                clean_domain = DomainVerifier.extract_hostname(user_input)
                
                with console.status(f"[bold blue]Probing {clean_domain}..."):
                    is_valid, msg = DomainVerifier.verify(clean_domain, forbidden_ip=server_ip)
                
                if is_valid:
                    console.print(f"[green]{msg}[/]")
                    final_domain = clean_domain
                    break
                else:
                    console.print(f"[bold red]Domain issue: {msg}[/]")
                    console.print("[dim]A good domain must resolve, support TLS 1.3/H2, and not be this server.[/]")
                    
                    if Confirm.ask("Use this domain anyway (not recommended)?"):
                        final_domain = clean_domain
                        break
        
        console.print(f"Masking Domain: [green]{final_domain}[/]")

    with console.status(f"[bold blue]Configuring {handler.name}..."):
        with open(template_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        try:
            env_vars = handler.on_initialize(
                config=config_data,
                docker=docker,
                domain=final_domain
            )
            
        except Exception as e:
            console.print(f"[bold red]Protocol setup failed:[/]\n{e}")
            raise typer.Exit(code=1)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    
    with console.status("[bold blue]Creating .env file..."):
        env_content = [
            f"SERVER_IP={server_ip}",
            "XRAY_PORT=443",
            f"XRAY_PROTOCOL={protocol}"
        ]

        for key, value in env_vars.items():
            env_content.append(f"{key}={value}")
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(env_content) + "\n")

    console.print(Panel(
        f"Protocol:  [magenta]{protocol}[/]\n"
        f"Server IP: [green]{server_ip}[/]\n" +
        ("\n".join([f"{k}: [green]{v}[/]" for k, v in env_vars.items()])),
        title="[bold green]Setup Completed![/]",
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

