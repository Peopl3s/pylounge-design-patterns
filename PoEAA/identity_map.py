from typing import Generic, TypeVar, Dict, Callable
from threading import RLock
from dataclasses import dataclass, field
from datetime import timedelta
import weakref
from time import monotonic_ns


T = TypeVar("T")
ID = TypeVar("ID")


@dataclass(slots=True, kw_only=True)
class _CacheEntry(Generic[T]):
    obj: T | weakref.ref
    is_weak: bool
    created_at: int = field(default_factory=monotonic_ns)
    accessed_at: int = field(default_factory=monotonic_ns)
    version: int = 0


class IdentityMap(Generic[T, ID]):
    """https://martinfowler.com/eaaCatalog/identityMap.html"""
    __slots__ = (
        "_id_getter",
        "_idle_ttl_ns",
        "_lock",
        "_store",
        "_cleanup_threshold",
        "_cleanup_interval",
        "_operation_count",
        "_use_weak_refs",
    )

    def __init__(
        self,
        id_getter: Callable[[T], ID],
        idle_ttl: timedelta | None = None,
        *,
        use_weak_refs: bool = True,
        cleanup_threshold: int | None = None,
        cleanup_interval: int = 100,
    ) -> None:
        self._id_getter = id_getter
        self._idle_ttl_ns = (
            int(idle_ttl.total_seconds() * 1e9) if idle_ttl else None # nanosecs
        )
        self._use_weak_refs = use_weak_refs

        self._lock = RLock()
        self._store: Dict[ID, _CacheEntry[T]] = {}

        self._cleanup_threshold = cleanup_threshold
        self._cleanup_interval = cleanup_interval
        self._operation_count = 0

    def _is_expired_locked(self, entry: _CacheEntry) -> bool:
        if not self._idle_ttl_ns:
            return False
        return (monotonic_ns() - entry.accessed_at) > self._idle_ttl_ns

    def _try_cleanup_by_threshold_locked(self) -> None:
        if not self._cleanup_threshold:
            return

        self._operation_count += 1
        if self._operation_count < self._cleanup_interval:
            return

        self._operation_count = 0
        if len(self._store) < self._cleanup_threshold:
            return

        now = monotonic_ns() if self._idle_ttl_ns else None
        to_remove: list[ID] = []

        for id_, entry in self._store.items():
            if now and (now - entry.accessed_at) > self._idle_ttl_ns:
                to_remove.append(id_)
            elif entry.is_weak and entry.obj() is None:
                to_remove.append(id_)

        for id_ in to_remove:
            self._store.pop(id_, None)

    def get(self, id_: ID) -> T | None:
        with self._lock:
            entry = self._store.get(id_)
            if entry is None:
                return None

            if self._is_expired_locked(entry):
                del self._store[id_]
                return None

            entry.accessed_at = monotonic_ns()

            if entry.is_weak:
                obj = entry.obj()
                if obj is None:
                    del self._store[id_]
                return obj

            return entry.obj

    def add(self, obj: T) -> None:
        id_ = self._id_getter(obj)
        now = monotonic_ns()

        if self._use_weak_refs:
            stored_obj = weakref.ref(obj)
            is_weak = True
        else:
            stored_obj = obj
            is_weak = False

        with self._lock:
            existing = self._store.get(id_)
            if existing:
                existing.obj = stored_obj
                existing.is_weak = is_weak
                existing.version += 1
                existing.created_at = now
                existing.accessed_at = now
            else:
                self._store[id_] = _CacheEntry(
                    obj=stored_obj,
                    is_weak=is_weak,
                    created_at=now,
                    accessed_at=now,
                )

            self._try_cleanup_by_threshold_locked()

    def remove(self, id_: ID) -> bool:
        with self._lock:
            return self._store.pop(id_, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cleanup(self) -> int:
        with self._lock:
            before = len(self._store)
            if before == 0:
                return 0

            now = monotonic_ns() if self._idle_ttl_ns else None
            to_remove: list[ID] = []

            for id_, entry in self._store.items():
                if now and (now - entry.accessed_at) > self._idle_ttl_ns:
                    to_remove.append(id_)
                elif entry.is_weak and entry.obj() is None:
                    to_remove.append(id_)

            for id_ in to_remove:
                self._store.pop(id_, None)

            return before - len(self._store)

    def get_entry_version(self, id_: ID) -> int | None:
        with self._lock:
            entry = self._store.get(id_)
            if entry is None or self._is_expired_locked(entry):
                return None
            return entry.version

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, id_: ID) -> bool:
        with self._lock:
            entry = self._store.get(id_)
            return entry is not None and not self._is_expired_locked(entry)



@dataclass(frozen=True, kw_only=True)
class User:
    id: int
    name: str

identity_map = IdentityMap(
    id_getter=lambda u: u.id,
    idle_ttl=timedelta(seconds=10),       
    use_weak_refs=True,                   
    cleanup_threshold=100,              
    cleanup_interval=50              
)

user1 = User(id=1, name="Alice")
identity_map.add(user1)

retrieved = identity_map.get(1)

print(retrieved)  # User(id=1, name='Alice')
