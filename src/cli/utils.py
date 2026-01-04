import typer
from rich.console import Console

from ..dependencies import get_docker_client, get_user_service, get_system_service


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
    
    max_val = max(recent_data)
    if max_val < 10240: 
        max_val = 10240

    result = ""
    for val in recent_data:
        if val == 0:
            idx = 0
        else:
            idx = int((val / max_val) * (len(bar_chars) - 1))
            idx = max(0, min(idx, len(bar_chars) - 1))
            
        result += bar_chars[idx]
        
    return result
