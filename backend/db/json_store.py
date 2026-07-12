import json
import os
from typing import Any, Dict, List, Optional, TypeVar, Generic

T = TypeVar('T')


class JSONStore(Generic[T]):
    def __init__(self, file_path: str, default_data: Any = None):
        self.file_path = file_path
        self.default_data = default_data or {}
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.default_data, f, ensure_ascii=False, indent=2)

    def read(self) -> Any:
        self._ensure_file_exists()
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return self.default_data.copy()

    def write(self, data: Any):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update(self, data: Dict[str, Any]):
        current = self.read()
        if isinstance(current, dict):
            current.update(data)
            self.write(current)
            return current
        return current

    def get(self, key: str, default: Any = None) -> Any:
        data = self.read()
        if isinstance(data, dict):
            return data.get(key, default)
        return default

    def set(self, key: str, value: Any):
        data = self.read()
        if isinstance(data, dict):
            data[key] = value
            self.write(data)


class CollectionStore(Generic[T]):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def list(self) -> List[T]:
        self._ensure_file_exists()
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def get_by_id(self, item_id: str, id_field: str = 'id') -> Optional[T]:
        items = self.list()
        for item in items:
            if item.get(id_field) == item_id:
                return item
        return None

    def add(self, item: T) -> T:
        items = self.list()
        items.append(item)
        self._write(items)
        return item

    def update(self, item_id: str, updates: Dict[str, Any], id_field: str = 'id') -> Optional[T]:
        items = self.list()
        for idx, item in enumerate(items):
            if item.get(id_field) == item_id:
                items[idx] = {**item, **updates}
                self._write(items)
                return items[idx]
        return None

    def delete(self, item_id: str, id_field: str = 'id') -> bool:
        items = self.list()
        original_count = len(items)
        items = [item for item in items if item.get(id_field) != item_id]
        if len(items) != original_count:
            self._write(items)
            return True
        return False

    def _write(self, items: List[T]):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)