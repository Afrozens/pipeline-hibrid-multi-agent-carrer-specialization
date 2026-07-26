from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    page_number: int
    page_size: int
    total_pages: int
    total_record: int
    data: List[T]
