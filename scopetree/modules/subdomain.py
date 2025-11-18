import asyncio
from typing import List
from scopetree.modules.base import BaseModule
from scopetree.tools.wrappers import *
from rich.panel import Panel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

class Subdomain(BaseModule):
    """Subdomain enumeration"""

    @property
    def name(self) -> str:
        return "Subdomain Enumeration"

    def get_all_tools(self) -> dict:
        from scopetree.tools import wrappers
        import inspect

        module_id = 'subdomain'
        tool_classes = {}
        all_classes = inspect.getmembers(wrappers, inspect.isclass)
        for class_name, tool_class in all_classes:
            if class_name == 'BaseTool':
                continue
            
            if not hasattr(tool_class, 'modules'):
                continue
            
            if module_id in tool_class.modules:
                tool_classes[tool_class.name] = tool_class
        return tool_classes

    async def validate(self) -> bool:
        domain = self.db.get_domains()
        if not domain:
            return False

        tool_classes = self.get_all_tools()

        installed_tools = []
        for tool_name, tool_class in tool_classes.items():
            if tool_class.is_installed():
                installed_tools.append(tool_name)
            else:
                self.logger.warning(f"{tool_name} is not installed")

        if not installed_tools:
            self.logger.error("No subdomain enumeration tools installed")
            return False

        return True


    async def execute(self):
        """Execute subdomain enumeration"""
        domains = self.db.get_domains()
        if not domains:
            self.logger.warning("No domains found")
            return []

        root_domain = domains[0]
        
        # Auto-detect and initialize tools
        tool_classes = self.get_all_tools()
        tools = []
        available_tool_names = []

        for tool_name, tool_class in tool_classes.items():
            # Check if tool is enabled in config (optional)
            if self.config.get(f'tools.{tool_name}.enabled', True):
                if tool_class.is_installed():
                    tools.append(tool_class(self.logger))
                    available_tool_names.append(tool_name)
                else:
                    self.logger.debug(f"Skipping {tool_name}: not installed")

        if not tools:
            self.logger.warning("No tools available to run")
            return []
        
        # Display module info panel
        console = Console()
        tools_str = ', '.join(available_tool_names) if available_tool_names else 'None'
        console.print(Panel.fit(
            f"[bold cyan]{self.name}[/bold cyan]\n"
            f"[yellow]Target:[/yellow] {root_domain}\n"
            f"[yellow]Tools:[/yellow] {tools_str}",
            border_style="cyan"
        ))
        
        # Run tools in parallel with progress bar
        all_subdomains = set()
        completed = {'count': 0}

        # Temporarily disable logger output to avoid interfering with progress bar
        import logging
        old_level = self.logger.level
        self.logger.setLevel(logging.CRITICAL + 1)  # Disable all logging

        async def run_tool_tracked(tool):
            """Run tool and track completion"""
            try:
                result = await tool.run(root_domain)
                completed['count'] += 1
                return (tool, result, None)
            except Exception as e:
                completed['count'] += 1
                return (tool, [], e)

        # Run with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Create progress task
            task = progress.add_task(f"[cyan]Running {len(tools)} tools in parallel...", total=len(tools))

            # Launch all tools in parallel
            tasks = [asyncio.create_task(run_tool_tracked(tool)) for tool in tools]

            # Update progress while tasks run
            while completed['count'] < len(tools):
                await asyncio.sleep(0.1)
                progress.update(task, completed=completed['count'])

            # Gather results
            results = await asyncio.gather(*tasks)

        # Restore logger
        self.logger.setLevel(old_level)

        # Process and display results
        console.print()
        for tool, result, error in results:
            if error:
                console.print(f"[red]✗ {tool.name}: Failed[/red]")
                continue
            count = len(result)
            all_subdomains.update(result)
            console.print(f"[green]✓ {tool.name}: {count} subdomains[/green]")

        # Print summary
        console.print(f"\n[bold cyan]Total unique: {len(all_subdomains)} subdomains[/bold cyan]")
        
        # Save to DB
        added = self.db.add_domains(list(all_subdomains), source='passive')
        self.logger.debug(f"Added {added} new subdomains (total: {len(all_subdomains)})")

        return list(all_subdomains)