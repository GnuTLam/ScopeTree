import asyncio
from typing import List
from scopetree.modules.base import BaseModule
from scopetree.tools.wrappers import *
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.console import Console

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
        
        # Run tools with progress bars
        all_subdomains = set()
        
        # Create progress bar for each tool
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=False
        ) as progress:
            
            # Create tasks with progress tracking
            async def run_tool_with_progress(tool, domain):
                task_id = progress.add_task(
                    f"[cyan]Running {tool.name}...",
                    total=None  # Indeterminate progress (spinner only)
                )
                try:
                    result = await tool.run(domain)
                    progress.update(task_id, description=f"[green]✓ {tool.name} completed")
                    # Small delay to show completion
                    await asyncio.sleep(0.5)
                    return result
                except Exception as e:
                    progress.update(task_id, description=f"[red]✗ {tool.name} failed: {str(e)[:50]}")
                    await asyncio.sleep(0.5)
                    raise e
                finally:
                    progress.remove_task(task_id)
            
            # Run all tools in parallel
            tasks = [run_tool_with_progress(tool, root_domain) for tool in tools]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            for tool, result in zip(tools, results):
                if isinstance(result, Exception):
                    self.logger.error(f"{tool.name} failed: {result}")
                    continue
                self.logger.debug(f"{tool.name} found {len(result)} subdomains")
                all_subdomains.update(result)
        
        # Save to DB
        added = self.db.add_domains(list(all_subdomains), source='passive')
        self.logger.debug(f"Added {added} new subdomains (total: {len(all_subdomains)})")

        return list(all_subdomains)