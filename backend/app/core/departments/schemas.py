from pydantic import BaseModel, ConfigDict


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str


class DepartmentListResponse(BaseModel):
    items: list[DepartmentResponse]
