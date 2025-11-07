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
        # Enable both subfinder and puredns by default
        if key in ['tools.subfinder.enabled', 'tools.puredns.enabled']:
            return True
        return default if default is not None else True

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
@click.option('--domain', '-d', help='Domain to enumerate')
@click.option('--file', '-f', 'input_file', help='File containing list of domains (one per line)')
@click.option('--output', '-o', help='Output file to save results')
def subdomain(domain, input_file, output):
    """Run subfinder subdomain enumeration"""
    if not domain and not input_file:
        console.print("[red]Error: Either --domain or --file must be provided[/red]")
        return
    domains = []
    if domain:
        domains.append(domain)
    if input_file:
        try:
            with open(input_file, 'r') as f:
                file_domains = [line.strip() for line in f if line.strip()]
                domains.extend(file_domains)
            console.print(f"[cyan]Loaded {len(file_domains)} domains from {input_file}[/cyan]")
        except FileNotFoundError:
            console.print(f"[red]Error: File '{input_file}' not found[/red]")
            return
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            return
    
    console.print(f"[cyan]Total domains to scan: {len(domains)}[/cyan]")

    all_results = []
    config = SimpleConfig()
    
    for target_domain in domains:
        db = SimpleDB()
        db.domains_list = [target_domain]
        
        module = Subdomain(config, db, logger)
        console.print(f"[cyan]Running subfinder for {target_domain}...[/cyan]")
        results = asyncio.run(module.execute())
        
        if results:
            console.print(f"[green]Found {len(results)} subdomains for {target_domain}[/green]")
            all_results.extend(results)
        else:
            console.print(f"[yellow]No subdomains found for {target_domain}[/yellow]")

    if all_results:
        console.print(f"\n[green]Total: {len(all_results)} subdomains found:[/green]")
        for sub in all_results:
            console.print(f"  {sub}")
        if output:
            try:
                with open(output, 'w') as f:
                    for sub in all_results:
                        f.write(f"{sub}\n")
                console.print(f"\n[green]✓ Results saved to {output}[/green]")
            except Exception as e:
                console.print(f"\n[red]Error saving to file: {e}[/red]")
    else:
        console.print("[yellow]No subdomains found[/yellow]")