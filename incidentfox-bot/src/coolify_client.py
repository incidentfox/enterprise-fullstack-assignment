"""Coolify API client for deployment integration."""
import hashlib
import hmac
from typing import Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)


class CoolifyClient:
    """Coolify API client."""

    def __init__(self):
        """Initialize Coolify client."""
        self.api_url = settings.coolify_api_url.rstrip("/") if settings.coolify_api_url else None
        self.api_token = settings.coolify_api_token
        self.webhook_secret = settings.coolify_webhook_secret

        self.client: Optional[httpx.AsyncClient] = None

        if self.api_url and self.api_token:
            # Configure HTTP client
            self.client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            logger.info("coolify_client_initialized", api_url=self.api_url)
        else:
            logger.warning(
                "coolify_not_configured",
                has_api_url=bool(self.api_url),
                has_api_token=bool(self.api_token),
            )

    def _require_configured(self) -> None:
        if not self.client:
            raise RuntimeError("Coolify is not configured (set COOLIFY_API_URL and COOLIFY_API_TOKEN).")

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        """Verify Coolify webhook signature.

        Args:
            payload: Raw request body
            signature_header: X-Signature header value

        Returns:
            True if signature is valid or no secret configured
        """
        # If no webhook secret configured, skip verification (less secure)
        if not self.webhook_secret:
            logger.warning("coolify_webhook_secret_not_configured")
            return True

        if not signature_header:
            logger.warning("coolify_webhook_signature_missing")
            return False

        # Strip "sha256=" prefix if present
        if signature_header.startswith("sha256="):
            signature_header = signature_header[7:]

        # Compute expected signature (Coolify uses HMAC-SHA256)
        mac = hmac.new(
            self.webhook_secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()

        # Compare signatures
        is_valid = hmac.compare_digest(signature_header, expected_signature)

        if not is_valid:
            logger.warning("coolify_webhook_signature_mismatch")

        return is_valid

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_deployment(self, deployment_id: str) -> Optional[Dict]:
        """Get deployment details from Coolify API.

        Args:
            deployment_id: Deployment UUID

        Returns:
            Deployment data or None if not found
        """
        try:
            self._require_configured()
            # Coolify API endpoint: GET /deployments/{uuid}
            response = await self.client.get(f"/deployments/{deployment_id}")
            response.raise_for_status()

            data = response.json()
            logger.info("deployment_fetched", deployment_id=deployment_id, has_commit=bool(data.get("commit")))
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("deployment_not_found", deployment_id=deployment_id)
                return None
            logger.error(
                "deployment_fetch_failed",
                deployment_id=deployment_id,
                status=e.response.status_code,
                error=str(e)
            )
            raise

        except Exception as e:
            logger.error(
                "deployment_fetch_error",
                deployment_id=deployment_id,
                error=str(e)
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_deployment_logs(
        self,
        deployment_id: str,
        lines: int = 1000
    ) -> Optional[str]:
        """Get deployment logs from Coolify API.

        Coolify includes logs in the deployment object response.

        Args:
            deployment_id: Deployment UUID
            lines: Number of log lines (not used by Coolify API)

        Returns:
            Log content or None if not available
        """
        try:
            # Coolify API includes logs in the deployment object
            deployment = await self.get_deployment(deployment_id)

            if not deployment:
                logger.warning("deployment_logs_not_found", deployment_id=deployment_id)
                return None

            logs = deployment.get("logs", "")
            logger.info(
                "deployment_logs_extracted",
                deployment_id=deployment_id,
                log_length=len(logs) if logs else 0
            )
            return logs if logs else None

        except Exception as e:
            logger.error(
                "deployment_logs_fetch_error",
                deployment_id=deployment_id,
                error=str(e)
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_application(self, application_id: str) -> Optional[Dict]:
        """Get application details.

        Args:
            application_id: Application ID

        Returns:
            Application data or None if not found
        """
        try:
            self._require_configured()
            response = await self.client.get(f"/api/v1/applications/{application_id}")
            response.raise_for_status()

            data = response.json()
            logger.debug("application_fetched", application_id=application_id)
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("application_not_found", application_id=application_id)
                return None
            logger.error(
                "application_fetch_failed",
                application_id=application_id,
                status=e.response.status_code,
                error=str(e)
            )
            raise

        except Exception as e:
            logger.error(
                "application_fetch_error",
                application_id=application_id,
                error=str(e)
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def trigger_deployment(
        self,
        application_id: str,
        branch: Optional[str] = None
    ) -> Optional[str]:
        """Trigger a new deployment.

        Args:
            application_id: Application ID
            branch: Branch name (optional)

        Returns:
            Deployment ID if successful
        """
        try:
            self._require_configured()
            payload = {}
            if branch:
                payload["branch"] = branch

            response = await self.client.post(
                f"/api/v1/applications/{application_id}/deploy",
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            deployment_id = data.get("deployment_id")

            logger.info(
                "deployment_triggered",
                application_id=application_id,
                deployment_id=deployment_id,
                branch=branch
            )

            return deployment_id

        except Exception as e:
            logger.error(
                "deployment_trigger_failed",
                application_id=application_id,
                branch=branch,
                error=str(e)
            )
            raise

    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
        logger.debug("coolify_client_closed")


# Global instance
coolify_client = CoolifyClient()
