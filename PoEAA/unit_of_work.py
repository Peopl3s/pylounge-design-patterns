from typing import Protocol, TypeVar, Optional, runtime_checkable


T = TypeVar("T")
EntityId = TypeVar("EntityId")


@runtime_checkable
class DataMapperProtocol(Protocol[T, EntityId]):
    async def insert(self, entity: T) -> None: ...
    async def update(self, entity: T) -> None: ...
    async def delete(self, entity_id: EntityId) -> None: ...
    async def get_by_id(self, entity_id: EntityId) -> Optional[T]: ...

############################################################################################

from dataclasses import dataclass, field
from typing import Callable, Generic, Optional
from sqlalchemy.ext.asyncio import AsyncSession, AsyncTransaction


@dataclass(slots=True)
class UnitOfWork(Generic[T, EntityId]):
    _session: AsyncSession
    _mapper_factory: Callable[[AsyncSession], DataMapperProtocol[T, EntityId]]

    _new: list[T] = field(default_factory=list)
    _modified: list[T] = field(default_factory=list)
    _deleted: list[EntityId] = field(default_factory=list)

    _transaction: Optional[AsyncTransaction] = None
    _mapper: Optional[DataMapperProtocol[T, EntityId]] = None
    _is_active: bool = field(default=True, init=False)

    @property
    def mapper(self) -> DataMapperProtocol[T, EntityId]:
        if self._mapper is None:
            self._mapper = self._mapper_factory(self._session)
        return self._mapper

    def _ensure_active(self) -> None:
        if not self._is_active:
            raise RuntimeError("UnitOfWork уже завершён")

    def register_new(self, entity: T) -> None:
        self._ensure_active()
        if entity not in self._new:
            self._new.append(entity)

    def register_modified(self, entity: T) -> None:
        self._ensure_active()
        if entity not in self._new and entity not in self._modified:
            self._modified.append(entity)

    def register_deleted(self, entity_id: EntityId) -> None:
        self._ensure_active()
        if entity_id not in self._deleted:
            self._deleted.append(entity_id)

    async def __aenter__(self) -> "UnitOfWork[T, EntityId]":
        self._transaction = await self._session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._is_active = False

        try:
            if exc_type:
                await self._transaction.rollback()
                return

            for entity in self._new:
                await self.mapper.insert(entity)

            for entity in self._modified:
                await self.mapper.update(entity)

            for entity_id in self._deleted:
                await self.mapper.delete(entity_id)

            await self._transaction.commit()

        except Exception:
            await self._transaction.rollback()
            raise
        finally:
            self._new.clear()
            self._modified.clear()
            self._deleted.clear()

############################################################################################

from typing import Optional
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession


class OrderMapper:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert(self, order: "Order") -> None:
        from .entities import OrderORM, OrderItemORM, OrderStatusORM

        orm_order = OrderORM(
            customer_id=order.customer_id,
            status=OrderStatusORM(order.status.value),
        )
        self._session.add(orm_order)
        await self._session.flush()

        order.id = orm_order.id

        for item in order.items:
            self._session.add(
                OrderItemORM(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price,
                )
            )

    async def update(self, order: "Order") -> None:
        from .entities import OrderORM, OrderItemORM, OrderStatusORM

        orm_order = await self._session.get(OrderORM, order.id)
        orm_order.status = OrderStatusORM(order.status.value)

        await self._session.execute(
            sa_delete(OrderItemORM).where(OrderItemORM.order_id == order.id)
        )

        for item in order.items:
            self._session.add(
                OrderItemORM(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price,
                )
            )

    async def delete(self, order_id: int) -> None:
        from .entities import OrderORM, OrderItemORM

        await self._session.execute(
            sa_delete(OrderItemORM).where(OrderItemORM.order_id == order_id)
        )
        await self._session.execute(
            sa_delete(OrderORM).where(OrderORM.id == order_id)
        )

    async def get_by_id(self, order_id: int) -> Optional["Order"]:
        from .entities import (
            OrderORM,
            OrderItemORM,
            Order,
            OrderItem,
            OrderStatus,
        )

        stmt = select(OrderORM).where(OrderORM.id == order_id)
        result = await self._session.execute(stmt)
        orm_order = result.scalar_one_or_none()
        if orm_order is None:
            return None

        stmt_items = select(OrderItemORM).where(
            OrderItemORM.order_id == order_id
        )
        items_result = await self._session.execute(stmt_items)

        items = [
            OrderItem(
                product_id=i.product_id,
                quantity=i.quantity,
                price=i.price,
            )
            for i in items_result.scalars()
        ]

        return Order(
            id=orm_order.id,
            customer_id=orm_order.customer_id,
            status=OrderStatus(orm_order.status.value),
            items=items,
        )

############################################################################################

from sqlalchemy.ext.asyncio import AsyncSession


async def place_order(
    session: AsyncSession,
    customer_id: int,
    items: list[tuple[int, int, float]],
) -> int:
    from .entities import Order, OrderItem, OrderStatus

    order = Order(
        id=None,
        customer_id=customer_id,
        status=OrderStatus.PENDING,
        items=[],
    )

    for product_id, quantity, price in items:
        if quantity <= 0 or price <= 0:
            raise ValueError("Invalid item")
        order.add_item(OrderItem(product_id, quantity, price))

    if order.total < 10:
        raise ValueError("Order total below minimum")

    async with UnitOfWork[Order, int](session, OrderMapper) as uow:
        uow.register_new(order)

        order.status = OrderStatus.CONFIRMED
        uow.register_modified(order)

    if order.id is None:
        raise RuntimeError("Order id not set after commit")

    return order.id
