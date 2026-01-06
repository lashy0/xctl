import typer
from rich.panel import Panel
from ..utils import console
from ...core.verifier import DomainVerifier


def check_domain(
    domain: str = typer.Argument(..., help="The domain (SNI) to inspect.")
):
    """Inspects a domain for compatibility with Xray Reality (TLS/H2 check)."""
    
    with console.status(f"[bold blue]Inspecting {domain}..."):
        is_valid, message = DomainVerifier.verify(domain)

    if is_valid:
        console.print(Panel(
            message,
            title=f"[bold green]{domain} is excellent[/]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            message,
            title=f"[bold red]{domain} is poor[/]",
            border_style="red"
        ))
        raise typer.Exit(code=1)
