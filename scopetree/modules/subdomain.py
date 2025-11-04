import asyncio
from scopetree.modules.base import BaseModule
from scopetree.tools.wrappers import *

class Subdomain(BaseModule):
    """Subdomain enumeration"""
    
    @property
    def name(self) -> str:
        return "Subdomain Enumeration"
    
    async def execute(self):
        # Get root domain
        domains = self.db.get_domains()
        if not domains:
            self.logger.warning("No domains found")
            return []
        
        root_domain = domains[0]
        self.logger.info(f"Enumerating: {root_domain}")
        
        # Initialize tools
        tools = []
        if self.config.get('tools.subfinder.enabled'):
            tools.append(Subfinder(self.logger))
        
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