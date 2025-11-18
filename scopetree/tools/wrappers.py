import asyncio
import shutil
import json
import tempfile
import os
from typing import List, Dict, Optional


class BaseTool:
    """Base class for security tools"""

    name = None
    command = None
    modules = []

    def __init__(self, logger, config: Optional[Dict] = None):
        self.logger = logger
        self.config = config or {}

    @classmethod
    def is_installed(cls) -> bool:
        """Check if tool is installed"""
        return shutil.which(cls.command) is not None

    async def run(self, domain: str) -> List[str]:
        """Run tool - override in subclass"""
        raise NotImplementedError


class Subfinder(BaseTool):
    """Subfinder - Passive subdomain discovery"""

    name = "subfinder"
    command = "subfinder"
    modules = ['subdomain']

    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            return []

        # Build command
        cmd = [
            'subfinder', '-d', domain,
            '-all', '-silent',
            '-t', str(self.config.get('threads', 1)),
        ]

        # Run
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()

        # Parse
        lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
        subdomains = {s.strip().lower() for s in lines if s.strip()}

        return sorted(subdomains)


class Puredns(BaseTool):
    """Puredns - DNS resolver"""

    name = "puredns"
    command = "puredns"
    modules = ['subdomain']

    async def run(self, domain: str) -> List[str]:
        return []

    async def resolve(self, domains: List[str]) -> List[str]:
        if not self.is_installed() or not domains:
            return []

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('\n'.join(domains) + '\n')
            tmp_path = f.name

        try:
            # Run puredns
            proc = await asyncio.create_subprocess_exec(
                'puredns', 'resolve', tmp_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            # Parse
            lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
            resolved = {s.strip().lower() for s in lines if s.strip()}

            return sorted(resolved)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class Crtsh(BaseTool):
    """Crtsh - Certificate Transparency logs"""

    name = "crtsh"
    command = "curl"
    modules = ['subdomain']

    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            return []

        # Query crt.sh
        proc = await asyncio.create_subprocess_exec(
            'curl', '-s', f'https://crt.sh/?q=%.{domain}&output=json',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()

        try:
            data = json.loads(stdout.decode('utf-8', errors='ignore'))
            if not isinstance(data, list):
                return []

            # Extract subdomains
            subdomains = set()
            for entry in data:
                for subdomain in entry.get('name_value', '').split('\n'):
                    s = subdomain.strip().lower()
                    if s and '*' not in s and (s.endswith(f'.{domain}') or s == domain):
                        subdomains.add(s)

            return sorted(subdomains)
        except json.JSONDecodeError:
            return []


class Amass(BaseTool):
    """Amass - Passive subdomain enumeration"""

    name = "amass"
    command = "amass"
    modules = ['subdomain']

    async def run(self, domain: str) -> List[str]:
        if not self.is_installed():
            return []

        # Build command (passive mode only, fast settings)
        cmd = [
            'amass', 'enum',
            '-d', domain,
            '-passive'      # Passive mode only
        ]

        # Short timeout (amass passive can be slow)
        timeout = self.config.get('timeout', 30)

        # Run
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return []

        # Parse
        lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
        subdomains = {s.strip().lower() for s in lines if s.strip()}

        return sorted(subdomains)
