"""
Таблица символов MiniCompiler.

Иерархическая таблица с вложенными областями видимости.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .type_system import Type, FunctionType, StructType


# --- Виды символов ---

class SymbolKind:
    VARIABLE = "variable"
    FUNCTION = "function"
    PARAMETER = "parameter"
    STRUCT = "struct"


@dataclass
class SymbolInfo:
    """Информация о символе: имя, тип, вид, позиция объявления."""
    name: str
    type: Type
    kind: str               # SymbolKind.*
    line: int = 0
    column: int = 0
    # Для функций: типы параметров и возвращаемый тип
    params: Optional[List[Type]] = None
    return_type: Optional[Type] = None
    # Для структур: поля
    fields: Optional[Dict[str, Type]] = None
    # Инициализирована ли переменная
    initialized: bool = False

    def __str__(self) -> str:
        return f"{self.name}: {self.type} ({self.kind}, строка {self.line})"


# --- Область видимости ---

@dataclass
class Scope:
    """Область видимости: словарь символов + ссылка на родительскую."""
    name: str = "global"
    parent: Optional['Scope'] = None
    symbols: Dict[str, SymbolInfo] = field(default_factory=dict)
    depth: int = 0

    def insert(self, symbol: SymbolInfo) -> bool:
        """
        Добавить символ в текущую область.
        Возвращает False, если символ уже существует в этой же области.
        """
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True

    def lookup_local(self, name: str) -> Optional[SymbolInfo]:
        """Искать только в текущей области."""
        return self.symbols.get(name)

    def lookup(self, name: str) -> Optional[SymbolInfo]:
        """Искать от текущей области до глобальной."""
        sym = self.symbols.get(name)
        if sym is not None:
            return sym
        if self.parent is not None:
            return self.parent.lookup(name)
        return None


# --- Таблица символов ---

class SymbolTable:
    """
    Иерархическая таблица символов.

    enter_scope / exit_scope для вложенных областей,
    insert / lookup / lookup_local для работы с символами.
    """

    def __init__(self):
        self._global_scope = Scope(name="global", depth=0)
        self._current_scope = self._global_scope
        # История всех областей (для дампа)
        self._all_scopes: List[Scope] = [self._global_scope]

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @property
    def global_scope(self) -> Scope:
        return self._global_scope

    @property
    def depth(self) -> int:
        return self._current_scope.depth

    def enter_scope(self, name: str = "block"):
        """Создать и войти во вложенную область видимости."""
        new_scope = Scope(
            name=name,
            parent=self._current_scope,
            depth=self._current_scope.depth + 1,
        )
        self._current_scope = new_scope
        self._all_scopes.append(new_scope)

    def exit_scope(self):
        """Выйти из текущей области, вернуться к родительской."""
        if self._current_scope.parent is not None:
            self._current_scope = self._current_scope.parent

    def insert(self, symbol: SymbolInfo) -> bool:
        """
        Добавить символ в текущую область.
        Возвращает False, если символ уже объявлен в текущей области.
        """
        return self._current_scope.insert(symbol)

    def lookup(self, name: str) -> Optional[SymbolInfo]:
        """Поиск символа от текущей области до глобальной."""
        return self._current_scope.lookup(name)

    def lookup_local(self, name: str) -> Optional[SymbolInfo]:
        """Поиск символа только в текущей области."""
        return self._current_scope.lookup_local(name)

    # --- Дамп таблицы ---

    def dump(self) -> str:
        """Текстовый дамп всех областей видимости."""
        lines = ["=== Таблица символов ==="]
        for scope in self._all_scopes:
            indent = "  " * scope.depth
            lines.append(f"{indent}Scope: {scope.name} (depth={scope.depth})")
            for sym_name, sym_info in scope.symbols.items():
                lines.append(f"{indent}  - {sym_info}")
        return "\n".join(lines)

    def dump_json(self) -> dict:
        """JSON-представление таблицы символов."""
        result = []
        for scope in self._all_scopes:
            scope_data = {
                "name": scope.name,
                "depth": scope.depth,
                "symbols": {},
            }
            for sym_name, sym_info in scope.symbols.items():
                sym_data = {
                    "type": str(sym_info.type),
                    "kind": sym_info.kind,
                    "line": sym_info.line,
                    "column": sym_info.column,
                    "initialized": sym_info.initialized,
                }
                if sym_info.params is not None:
                    sym_data["params"] = [str(p) for p in sym_info.params]
                if sym_info.return_type is not None:
                    sym_data["return_type"] = str(sym_info.return_type)
                if sym_info.fields is not None:
                    sym_data["fields"] = {k: str(v) for k, v in sym_info.fields.items()}
                scope_data["symbols"][sym_name] = sym_data
            result.append(scope_data)
        return {"scopes": result}
