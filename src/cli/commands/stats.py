import time
from collections import deque

import typer
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

from ...core.exceptions import XrayError
from ..utils import resolve_service, console, sizeof_fmt, generate_sparkline



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


def watch_traffic(
    name: str = typer.Argument(None, help="Name of the user. Omit to see global stats."),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds")
):
    """Real-time traffic monitor."""
    service = resolve_service()

    history_len = 30
    
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
        grid.add_column(justify="left", no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)
        grid.add_column(justify="left", no_wrap=True)
        
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
