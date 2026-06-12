from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope.

    All endpoints return this structure:
      {"status": "success"|"error", "data": <T>, "error": null|"<message>"}
    """

    status: str
    data: T | None = None
    error: str | None = None

    @classmethod
    def success(cls, data: T) -> "ApiResponse[T]":
        return cls(status="success", data=data, error=None)

    @classmethod
    def failure(cls, message: str) -> "ApiResponse[None]":
        return cls(status="error", data=None, error=message)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response — used as the data payload inside ApiResponse.

    Example full response:
      {
        "status": "success",
        "data": {
          "items": [...],
          "total": 120,
          "page": 1,
          "page_size": 20
        },
        "error": null
      }
    """

    items: list[T]
    total: int
    page: int
    page_size: int
