from abc import abstractmethod
from typing import Protocol, final
from dataclasses import dataclass
from uuid import UUID, uuid4


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    id: UUID
    email: str
    name: str
    is_active: bool = True


class UserRepositoryProtocol(Protocol):
    """https://martinfowler.com/eaaCatalog/repository.html"""
    @abstractmethod
    def save(self, user: User) -> User: ...

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def list_all(self) -> list[User]: ...

    @abstractmethod
    def delete(self, user_id: UUID) -> bool: ...


@final
class InMemoryUserRepository(UserRepositoryProtocol):
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    def save(self, user: User) -> User:
        self.users[user.id] = user
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def list_all(self) -> list[User]:
        return list(self.users.values())

    def delete(self, user_id: UUID) -> bool:
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False


user_repository = InMemoryUserRepository()

user = User(id=uuid4(), email="email@email.ru", name="say my name")
user_repository.save(user)


print(user_repository.get_by_email(email="email@email.ru"))
