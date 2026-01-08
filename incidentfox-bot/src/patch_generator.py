"""Safe patch generation for common failure modes."""
import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .analyzer import AnalysisResult
from .config import settings
from .logging_config import get_logger
from .models import FailureCategory

logger = get_logger(__name__)


@dataclass
class PatchFile:
    """Represents a file patch."""
    file_path: str
    original_content: str
    patched_content: str
    description: str


@dataclass
class PatchSet:
    """Set of file patches."""
    files: List[PatchFile]
    description: str
    safety_checks_passed: bool
    warnings: List[str]


class PatchGenerator:
    """Generate safe patches for common failure modes."""

    def __init__(self):
        """Initialize patch generator."""
        self.allowed_patterns = settings.allowed_file_list
        logger.info("patch_generator_initialized", allowed_patterns=self.allowed_patterns)

    def is_file_allowed(self, file_path: str) -> bool:
        """Check if file is allowed for patching.

        Args:
            file_path: File path to check

        Returns:
            True if file is in whitelist
        """
        for pattern in self.allowed_patterns:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern):
                return True
        return False

    def extract_missing_env_vars(self, evidence: List) -> List[str]:
        """Extract missing environment variable names from evidence.

        Args:
            evidence: Analysis evidence

        Returns:
            List of variable names
        """
        env_vars = set()

        patterns = [
            r"environment variable\s+['\"]?([A-Z_][A-Z0-9_]*)['\"]?",
            r"([A-Z_][A-Z0-9_]*)\s+(?:not set|not found|missing|undefined|is required)",
            r"process\.env\.([A-Z_][A-Z0-9_]*)",
        ]

        for ev in evidence:
            text = ev.matched_text + (ev.context or "")
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                env_vars.update(matches)

        logger.debug("extracted_env_vars", vars=list(env_vars))
        return sorted(env_vars)

    def extract_port_numbers(self, evidence: List) -> List[int]:
        """Extract port numbers from evidence.

        Args:
            evidence: Analysis evidence

        Returns:
            List of port numbers
        """
        ports = set()

        for ev in evidence:
            text = ev.matched_text + (ev.context or "")
            # Extract port numbers
            matches = re.findall(r"(?:port|:)\s*(\d{2,5})", text, re.IGNORECASE)
            for match in matches:
                port = int(match)
                if 1024 <= port <= 65535:  # Valid port range
                    ports.add(port)

        logger.debug("extracted_ports", ports=list(ports))
        return sorted(ports)

    def extract_missing_packages(self, evidence: List) -> List[str]:
        """Extract missing package names from evidence.

        Args:
            evidence: Analysis evidence

        Returns:
            List of package names
        """
        packages = set()

        patterns = [
            r"Cannot find module\s+['\"]([^'\"]+)['\"]",
            r"ModuleNotFoundError:\s+No module named\s+['\"]([^'\"]+)['\"]",
            r"Error: Cannot find\s+['\"]([^'\"]+)['\"]",
        ]

        for ev in evidence:
            text = ev.matched_text + (ev.context or "")
            for pattern in patterns:
                matches = re.findall(pattern, text)
                packages.update(matches)

        logger.debug("extracted_packages", packages=list(packages))
        return sorted(packages)

    def generate_env_var_patch(
        self,
        analysis: AnalysisResult,
        repo_files: Dict[str, str]
    ) -> Optional[PatchSet]:
        """Generate patch for missing environment variables.

        Args:
            analysis: Failure analysis
            repo_files: Dict of {file_path: content} from repo

        Returns:
            Patch set or None if cannot generate
        """
        env_vars = self.extract_missing_env_vars(analysis.evidence)
        if not env_vars:
            logger.warning("no_env_vars_extracted")
            return None

        patches = []
        warnings = []

        # Try to patch docker-compose.yml
        compose_files = [f for f in repo_files.keys() if "docker-compose" in f and f.endswith(".yml")]
        if compose_files:
            compose_file = compose_files[0]
            if self.is_file_allowed(compose_file):
                original = repo_files[compose_file]
                patched = self._add_env_vars_to_compose(original, env_vars)

                if patched != original:
                    patches.append(PatchFile(
                        file_path=compose_file,
                        original_content=original,
                        patched_content=patched,
                        description=f"Add {len(env_vars)} environment variable(s) with placeholder values"
                    ))
            else:
                warnings.append(f"File {compose_file} not in whitelist")

        # Try to patch .env.example
        if ".env.example" in repo_files and self.is_file_allowed(".env.example"):
            original = repo_files[".env.example"]
            patched = self._add_env_vars_to_env_file(original, env_vars)

            if patched != original:
                patches.append(PatchFile(
                    file_path=".env.example",
                    original_content=original,
                    patched_content=patched,
                    description=f"Add {len(env_vars)} environment variable(s) to .env.example"
                ))

        if not patches:
            warnings.append("Could not generate patches for missing env vars")
            return PatchSet(files=[], description="No patches generated", safety_checks_passed=False, warnings=warnings)

        return PatchSet(
            files=patches,
            description=f"Add missing environment variables: {', '.join(env_vars)}",
            safety_checks_passed=True,
            warnings=warnings
        )

    def _add_env_vars_to_compose(self, content: str, env_vars: List[str]) -> str:
        """Add environment variables to docker-compose.yml.

        Args:
            content: Original file content
            env_vars: List of variable names

        Returns:
            Modified content
        """
        lines = content.split("\n")
        modified_lines = []
        in_environment_section = False
        indent = ""

        for line in lines:
            modified_lines.append(line)

            # Detect environment section
            if re.match(r"\s+environment:", line):
                in_environment_section = True
                indent = " " * (len(line) - len(line.lstrip()) + 2)
            elif in_environment_section and line.strip() and not line.strip().startswith("-") and not line.strip().startswith("#"):
                # End of environment section
                in_environment_section = False

            # Add variables at end of environment section
            if in_environment_section:
                # Check if this is the last env var line
                next_line_idx = lines.index(line) + 1
                if next_line_idx < len(lines):
                    next_line = lines[next_line_idx]
                    if not next_line.strip().startswith("-") or not next_line.strip():
                        # Add new variables
                        for var in env_vars:
                            if var not in content:
                                modified_lines.append(f"{indent}- {var}=PLACEHOLDER_VALUE_CHANGEME")

        return "\n".join(modified_lines)

    def _add_env_vars_to_env_file(self, content: str, env_vars: List[str]) -> str:
        """Add environment variables to .env file.

        Args:
            content: Original file content
            env_vars: List of variable names

        Returns:
            Modified content
        """
        lines = content.split("\n")

        # Check which vars are missing
        existing_vars = set()
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                var_name = line.split("=")[0].strip()
                existing_vars.add(var_name)

        # Add missing vars
        new_vars = [v for v in env_vars if v not in existing_vars]

        if new_vars:
            lines.append("")
            lines.append("# Added by IncidentFox")
            for var in new_vars:
                lines.append(f"{var}=PLACEHOLDER_VALUE_CHANGEME")

        return "\n".join(lines)

    def generate_port_patch(
        self,
        analysis: AnalysisResult,
        repo_files: Dict[str, str]
    ) -> Optional[PatchSet]:
        """Generate patch for port mismatches.

        Args:
            analysis: Failure analysis
            repo_files: Dict of {file_path: content} from repo

        Returns:
            Patch set or None if cannot generate
        """
        ports = self.extract_port_numbers(analysis.evidence)
        if not ports:
            logger.warning("no_ports_extracted")
            return None

        # This is complex and risky - for now, just document what needs to change
        warnings = [
            "Port mismatch detected but automatic patching is not safe",
            f"Detected ports: {', '.join(map(str, ports))}",
            "Manual review required to align ports in docker-compose.yml, Dockerfile, and healthchecks"
        ]

        return PatchSet(
            files=[],
            description="Port mismatch requires manual intervention",
            safety_checks_passed=False,
            warnings=warnings
        )

    def generate_dependency_patch(
        self,
        analysis: AnalysisResult,
        repo_files: Dict[str, str]
    ) -> Optional[PatchSet]:
        """Generate patch for dependency issues.

        Args:
            analysis: Failure analysis
            repo_files: Dict of {file_path: content} from repo

        Returns:
            Patch set or None if cannot generate
        """
        packages = self.extract_missing_packages(analysis.evidence)
        if not packages:
            logger.warning("no_packages_extracted")
            return None

        # This is risky - we don't know versions
        warnings = [
            "Dependency issues detected but automatic patching requires version information",
            f"Missing packages: {', '.join(packages)}",
            "Manual review required to add correct package versions to package.json or requirements.txt"
        ]

        return PatchSet(
            files=[],
            description="Dependency issues require manual intervention",
            safety_checks_passed=False,
            warnings=warnings
        )

    async def generate_patch(
        self,
        analysis: AnalysisResult,
        repo_files: Dict[str, str]
    ) -> Optional[PatchSet]:
        """Generate patch based on failure analysis.

        Args:
            analysis: Failure analysis
            repo_files: Dict of {file_path: content} from repository

        Returns:
            Patch set or None if cannot generate safe patch
        """
        logger.info("generating_patch", category=analysis.category.value)

        # Route to appropriate patch generator
        if analysis.category == FailureCategory.ENV_VAR_MISSING:
            return self.generate_env_var_patch(analysis, repo_files)
        elif analysis.category == FailureCategory.PORT_MISMATCH:
            return self.generate_port_patch(analysis, repo_files)
        elif analysis.category == FailureCategory.DEPENDENCY_ERROR:
            return self.generate_dependency_patch(analysis, repo_files)
        else:
            logger.warning("no_patch_generator_for_category", category=analysis.category.value)
            return PatchSet(
                files=[],
                description=f"No automatic patch available for {analysis.category.value}",
                safety_checks_passed=False,
                warnings=[f"Category {analysis.category.value} does not support automatic patching"]
            )

    def validate_patch_safety(self, patch_set: PatchSet) -> bool:
        """Validate that all patches are safe to apply.

        Args:
            patch_set: Patch set to validate

        Returns:
            True if all safety checks pass
        """
        # Check file count
        if len(patch_set.files) > settings.max_patch_files:
            logger.warning("too_many_files_in_patch", count=len(patch_set.files))
            patch_set.warnings.append(f"Patch modifies {len(patch_set.files)} files (max: {settings.max_patch_files})")
            return False

        # Check each file is whitelisted
        for patch in patch_set.files:
            if not self.is_file_allowed(patch.file_path):
                logger.warning("file_not_whitelisted", file=patch.file_path)
                patch_set.warnings.append(f"File {patch.file_path} not in whitelist")
                return False

        return patch_set.safety_checks_passed


# Global instance
patch_generator = PatchGenerator()
