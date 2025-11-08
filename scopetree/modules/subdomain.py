import asyncio
from typing import List, Set
from scopetree.modules.base import BaseModule, ModuleResult, ModuleStatus
from scopetree.tools.wrappers import *

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

        self.logger.info(f"Available tools: {', '.join(installed_tools)}")
        return True


    async def execute(self):
        """Execute subdomain enumeration"""
        domains = self.db.get_domains()
        if not domains:
            self.logger.warning("No domains found")
            return []

        root_domain = domains[0]
        self.logger.info(f"Enumerating: {root_domain}")
        
        # Auto-detect and initialize tools
        tool_classes = self.get_all_tools()
        tools = []

        for tool_name, tool_class in tool_classes.items():
            # Check if tool is enabled in config (optional)
            if self.config.get(f'tools.{tool_name}.enabled', True):
                if tool_class.is_installed():
                    tools.append(tool_class(self.logger))
                    self.logger.info(f"Using tool: {tool_name}")
                else:
                    self.logger.debug(f"Skipping {tool_name}: not installed")

        if not tools:
            self.logger.warning("No tools available to run")
            return []
        
        # Run parallel
        tasks = [tool.run(root_domain) for tool in tools]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_subdomains = set()
        for tool, result in zip(tools, results):
            if isinstance(result, Exception):
                self.logger.error(f"{tool.name} failed: {result}")
                continue
            self.logger.info(f"{tool.name} found {len(result)} subdomains")
            all_subdomains.update(result)
        
        # Save to DB
        added = self.db.add_domains(list(all_subdomains), source='passive')
        self.logger.info(f"Added {added} new subdomains (total: {len(all_subdomains)})")

        return list(all_subdomains)