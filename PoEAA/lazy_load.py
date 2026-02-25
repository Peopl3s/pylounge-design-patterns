"""https://martinfowler.com/eaaCatalog/lazyLoad.html"""

from typing import Callable, Generic, TypeVar, final

T = TypeVar("T")


@final
class ValueHolder(Generic[T]):
    def __init__(self, loader: Callable[[], T]) -> None:
        self._loader = loader
        self._value: T | None = None
        self._loaded = False

    def get(self) -> T:
        if not self._loaded:
            print("Loading value...")
            self._value = self._loader()
            self._loaded = True
        return self._value


def heavy_load_user_profile() -> dict[str, str | int]:
    print("Fetching data from database...")
    return {"bio": "Senior Python Developer", "followers": 1337}


@final
class User:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self._profile_holder = ValueHolder(heavy_load_user_profile)

    @property
    def profile(self) -> dict[str, str | int]:
        return self._profile_holder.get()


user = User(1)
print(user.profile)
print(user.profile)

##################################################################################################

class RealImage:
    def __init__(self, filename: str) -> None:
        print(f"Loading image {filename} from disk...")
        self.filename = filename

    def display(self) -> None:
        print(f"Displaying {self.filename}")


@final
class ImageVirtualProxy:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._real_image: RealImage | None = None

    def _ensure_loaded(self) -> None:
        if self._real_image is None:
            self._real_image = RealImage(self.filename)

    def display(self) -> None:
        self._ensure_loaded()
        self._real_image.display()


image = ImageVirtualProxy("photo.png")
image.display()
image.display()

##################################################################################################

@final
class UserGhost:
    def __init__(self, user_id: int) -> None:
        self.user_id: int = user_id
        self._loaded: bool = False
        self.name: str | None = None
        self.email: str | None = None

    def _load(self) -> None:
        print("Loading user from database...")
        self.name = "PyLounge"
        self.email = "pylounge@example.com"
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load()

    @property
    def name(self) -> str | None:
        self._ensure_loaded()
        return self._name

    @name.setter
    def name(self, value: str | None) -> None:
        self._name = value

    @property
    def email(self) -> str | None:
        self._ensure_loaded()
        return self._email

    @email.setter
    def email(self, value: str | None) -> None:
        self._email = value


user = UserGhost(1)
print(user.name)
print(user.email)