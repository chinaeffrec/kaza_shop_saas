from pydantic import BaseModel, Field


class CartItemAction(BaseModel):
    user_id: int = Field(gt=0)
    product_id: int = Field(gt=0)


class CartAddRequest(CartItemAction):
    quantity: int = Field(default=1, ge=1, le=1000)
