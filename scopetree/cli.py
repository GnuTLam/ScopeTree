import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    pass

@cli.command()
@click.option('--name', '-n', required=True)
@click.option('--domain', '-d', required=True)
def init(name, domain):
    """Initialize program"""
    console.print(f"[green]✓[/green] Initialized {name} - {domain}")

@cli.command()
@click.option('--program', '-p', required=True)
def scan(program):
    """Run scan"""
    console.print(f"[cyan]Scanning {program}...[/cyan]")

@cli.command()
def check():
    """Check tools"""
    console.print("[yellow]Checking tools...[/yellow]")