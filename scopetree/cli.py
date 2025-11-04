import click
import asyncio
from rich.console import Console
import logging
from scopetree.modules.subdomain import Subdomain

console = Console()
logger = logging.getLogger("scopetree")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# Simple config
class SimpleConfig:
    def get(self, key, default=None):
        return True  # Enable subfinder by default

# Simple DB
class SimpleDB:
    def __init__(self):
        self.domains_list = []
    
    def get_domains(self):
        return self.domains_list
    
    def add_domains(self, domains, source='passive'):
        added = 0
        for domain in domains:
            if domain not in self.domains_list:
                self.domains_list.append(domain)
                added += 1
        return added

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

@cli.command()
@click.option('--domain', '-d', required=True, help='Domain to enumerate')
def subdomain(domain):
    """Run subfinder subdomain enumeration"""
    config = SimpleConfig()
    db = SimpleDB()
    db.domains_list = [domain]
    
    module = Subdomain(config, db, logger)
    console.print(f"[cyan]Running subfinder for {domain}...[/cyan]")
    results = asyncio.run(module.execute())
    
    if results:
        console.print(f"[green]Found {len(results)} subdomains:[/green]")
        for sub in results:
            console.print(f"  {sub}")
    else:
        console.print("[yellow]No subdomains found[/yellow]")