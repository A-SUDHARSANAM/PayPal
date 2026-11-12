import asyncio
from datetime import UTC, datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel
from ..models import AgentExecution, PurchaseRequest
from ..repository import MemoryRepository


class AgentError(RuntimeError): pass


class BaseAgent(ABC):
    name: str
    def __init__(self, repo: MemoryRepository, timeout_seconds: float = 12, retries: int = 2) -> None:
        self.repo, self.timeout_seconds, self.retries = repo, timeout_seconds, retries

    async def execute(self, request: PurchaseRequest, *args: object) -> BaseModel:
        started = datetime.now(UTC)
        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                result = await asyncio.wait_for(self.run(request, *args), timeout=self.timeout_seconds)
                finished = datetime.now(UTC)
                await self.repo.log(AgentExecution(request_id=request.id, agent=self.name, status="completed", output=result.model_dump(mode="json"), created_at=started, completed_at=finished, duration_ms=round((finished-started).total_seconds()*1000)))
                return result
            except Exception as exc:
                last_error = exc
        finished = datetime.now(UTC)
        await self.repo.log(AgentExecution(request_id=request.id, agent=self.name, status="failed", error=str(last_error), created_at=started, completed_at=finished, duration_ms=round((finished-started).total_seconds()*1000)))
        raise AgentError(f"{self.name} failed") from last_error

    @abstractmethod
    async def run(self, request: PurchaseRequest, *args: object) -> BaseModel: ...
