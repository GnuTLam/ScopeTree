import click
import asyncio
from typing import Optional, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import logging
from pathlib import Path

from scopetree.modules.subdomain import Subdomain
from scopetree.modules.base import ModuleStatus
from scopetree.core.utils import validate_domain, parse_comma_separated

console = Console()
logger = logging.getLogger("scopetree")

MODULES = {
    'asset': {
        'name': 'Asset Discovery',
        'class': None,  # TODO: Implement
    },
    'subdomain': {
        'name': 'Subdomain Enumeration',
        'class': Subdomain
    },
    'dns': {
        'name': 'DNS Resolution',
        'class': None,  # TODO: Implement
    },
    'http': {
        'name': 'HTTP Probing',
        'class': None,  # TODO: Implement
    },
    'content': {
        'name': 'Content Discovery',
        'class': None,  # TODO: Implement
    }
}


class SimpleDB:
    """Simple in-memory database"""
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


class SimpleConfig:
    """Simple configuration"""
    def get(self, key, default=None):
        # Enable tools by default
        if 'enabled' in key:
            return True
        return default if default is not None else True


@click.command()
@click.option(
    '--target', '-t',
    required=True,
    help='Target domain(s), comma-separated'
)
@click.option(
    '--module', '-m',
    required=True,
    help='Module(s) to run: asset, subdomain, dns, http, content (comma-separated)'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file to save results'
)

@click.version_option(version='0.1.0', prog_name='scopetree')
def cli(target: str, module: str, output: Optional[str]):
    """
    ScopeTree - Modern Reconnaissance Platform

    Examples:

      scopetree -t example.com -m subdomain
      scopetree -t example.com,test.com -m subdomain,dns
      scopetree -t example.com -m subdomain,dns,http -o results.txt
    """

    # Setup logging
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Parse inputs
    targets = parse_comma_separated(target)
    modules = parse_comma_separated(module)

    # Validate targets
    invalid_targets = [t for t in targets if not validate_domain(t)]
    if invalid_targets:
        console.print(f"[red]Invalid domains: {', '.join(invalid_targets)}[/red]")
        raise click.Abort()

    # Validate modules
    invalid_modules = [m for m in modules if m not in MODULES]
    if invalid_modules:
        console.print(f"[red]Unknown modules: {', '.join(invalid_modules)}[/red]")
        console.print(f"[yellow]Available: {', '.join(MODULES.keys())}[/yellow]")
        raise click.Abort()

    # Check if modules are implemented
    not_implemented = [m for m in modules if MODULES[m]['class'] is None]
    if not_implemented:
        names = [MODULES[m]['name'] for m in not_implemented]
        console.print(f"[yellow]Modules not yet implemented: {', '.join(names)}[/yellow]")
        raise click.Abort()

    # Display configuration
    module_names = [MODULES[m]['name'] for m in modules]
    console.print(Panel.fit(
        f"[bold cyan]ScopeTree[/bold cyan]\n\n"
        f"[yellow]Targets:[/yellow] {', '.join(targets)}\n"
        f"[yellow]Modules:[/yellow] {', '.join(module_names)}\n"
        f"[yellow]Output:[/yellow] {output or 'Console'}",
        border_style="cyan"
    ))

    # Run modules
    config = SimpleConfig()
    results = {}

    for target_domain in targets:
        console.print(f"\n[bold cyan]Target: {target_domain}[/bold cyan]")
        results[target_domain] = {}

        # Initialize database
        db = SimpleDB()
        db.domains_list = [target_domain]

        for module_name in modules:
            module_info = MODULES[module_name]
            module_class = module_info['class']
            display_name = module_info['name']

            console.print(f"[cyan]→ {display_name}...[/cyan]")

            try:
                # Run module
                module = module_class(config, db, logger)
                result = asyncio.run(module.run())
                results[target_domain][module_name] = result

                # Display result
                if result.status == ModuleStatus.SUCCESS:
                    count = len(result.data) if result.data else 0
                    console.print(f"[green]✓ Found {count} items[/green]")
                elif result.status == ModuleStatus.SKIPPED:
                    console.print(f"[yellow]⊘ Skipped: {result.error}[/yellow]")
                else:
                    console.print(f"[red]✗ Failed: {result.error}[/red]")

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.exception(f"Error in {module_name}")

    # Display summary
    console.print("\n[bold cyan]Summary[/bold cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Target", style="cyan")
    table.add_column("Module", style="yellow")
    table.add_column("Status")
    table.add_column("Count", justify="right")

    for target_domain, module_results in results.items():
        for module_name, result in module_results.items():
            status_map = {
                ModuleStatus.SUCCESS: "[green]✓[/green]",
                ModuleStatus.SKIPPED: "[yellow]⊘[/yellow]",
                ModuleStatus.FAILED: "[red]✗[/red]"
            }
            status = status_map.get(result.status, "?")
            count = len(result.data) if result.data else 0

            table.add_row(
                target_domain,
                MODULES[module_name]['name'],
                status,
                str(count)
            )

    console.print(table)

    # Save output
    if output:
        try:
            output_path = Path(output)
            with open(output_path, 'w') as f:
                for target_domain, module_results in results.items():
                    f.write(f"# {target_domain}\n\n")
                    for module_name, result in module_results.items():
                        f.write(f"## {MODULES[module_name]['name']}\n")
                        if result.data:
                            for item in result.data:
                                f.write(f"{item}\n")
                        f.write("\n")
            console.print(f"[green]✓ Saved to {output}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving: {e}[/red]")

@click.command()
def modules():
    """List all available modules"""
    console.print("[bold cyan]Available Modules[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Module", style="cyan")
    table.add_column("Description", style="yellow")
    table.add_column("Status")

    for module_name, info in MODULES.items():
        status = "[green]Ready[/green]" if info['class'] else "[yellow]Coming soon[/yellow]"
        table.add_row(module_name, info['name'], status)

    console.print(table)


# Group commands
@click.group()
def main():
    """ScopeTree - Modern Reconnaissance Platform"""
    pass


main.add_command(cli, name='run')
main.add_command(modules)


if __name__ == '__main__':
    cli()
