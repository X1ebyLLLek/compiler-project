"""
Граф потока управления (Control Flow Graph, CFG) для IR MiniCompiler.

Содержит:
  - IRFunction — IR-представление одной функции (CFG + аргументы)
  - ControlFlowGraph — граф базовых блоков внутри функции
  - IRProgram — набор всех функций программы

Sprint 4: IR Generation.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from .basic_block import BasicBlock
from .ir_instructions import IRInstruction, IROpcode, VarOperand


@dataclass
class ControlFlowGraph:
    """
    Граф потока управления — упорядоченный набор базовых блоков.

    - entry_block — всегда первый блок (точка входа)
    - blocks — все блоки в порядке добавления
    - named_blocks — словарь label -> BasicBlock
    """
    entry_block: Optional[BasicBlock] = None
    blocks: List[BasicBlock] = field(default_factory=list)
    _named: Dict[str, BasicBlock] = field(default_factory=dict, repr=False)

    def add_block(self, block: BasicBlock) -> None:
        """Добавить базовый блок в граф."""
        if block.label in self._named:
            raise ValueError(
                f"Блок с меткой '{block.label}' уже существует в CFG."
            )
        self.blocks.append(block)
        self._named[block.label] = block
        if self.entry_block is None:
            self.entry_block = block

    def get_block(self, label: str) -> Optional[BasicBlock]:
        """Найти блок по имени метки."""
        return self._named.get(label)

    def block_count(self) -> int:
        """Количество базовых блоков в графе."""
        return len(self.blocks)

    def total_instructions(self) -> int:
        """Суммарное количество инструкций во всех блоках."""
        return sum(b.instruction_count() for b in self.blocks)

    def all_instructions(self) -> List[IRInstruction]:
        """Все инструкции во всех блоках (в порядке следования блоков)."""
        result = []
        for block in self.blocks:
            result.extend(block.instructions)
        return result

    def dump(self) -> str:
        """Текстовый дамп CFG."""
        parts = []
        for block in self.blocks:
            parts.append(block.dump())
        return "\n\n".join(parts)

    def to_dot(self, func_name: str = "function") -> str:
        """
        Сгенерировать описание CFG в формате Graphviz DOT.

        Использование:
            dot -Tpng cfg.dot -o cfg.png
        """
        lines = [
            f'digraph "{func_name}" {{',
            '    rankdir=TB;',
            '    node [shape=record, fontname="Courier", fontsize=10];',
            '    edge [fontname="Courier", fontsize=9];',
            '',
        ]

        # Цвет узлов по типу
        for block in self.blocks:
            if block.label == "entry":
                color = "#d5e8d4"  # зелёный — точка входа
                border = "#82b366"
            elif block.label == "exit" or (
                block.instructions
                and block.instructions[-1].opcode == IROpcode.RETURN
            ):
                color = "#dae8fc"  # синий — выход
                border = "#6c8ebf"
            else:
                color = "#fff2cc"  # жёлтый — обычный блок
                border = "#d6b656"

            # Инструкции блока в строку для DOT
            instr_lines = []
            for instr in block.instructions:
                text = instr.format().strip()
                # Экранируем спецсимволы DOT
                text = (text.replace("\\", "\\\\")
                             .replace('"', '\\"')
                             .replace('<', '\\<')
                             .replace('>', '\\>')
                             .replace('{', '\\{')
                             .replace('}', '\\}')
                             .replace('|', '\\|'))
                instr_lines.append(text)

            label_body = "\\l".join(instr_lines) + "\\l"
            node_label = f"{{{block.label}:|{label_body}}}"
            lines.append(
                f'    "{block.label}" ['
                f'label="{node_label}", '
                f'style="filled", '
                f'fillcolor="{color}", '
                f'color="{border}"];'
            )

        lines.append('')

        # Рёбра графа
        for block in self.blocks:
            term = block.get_terminator()
            for succ in block.successors:
                edge_label = ""
                if term and term.opcode == IROpcode.JUMP_IF:
                    if succ == block.successors[0]:
                        edge_label = ' [label="true"]'
                    else:
                        edge_label = ' [label="false"]'
                elif term and term.opcode == IROpcode.JUMP_IF_NOT:
                    if succ == block.successors[0]:
                        edge_label = ' [label="false"]'
                    else:
                        edge_label = ' [label="true"]'
                lines.append(
                    f'    "{block.label}" -> "{succ.label}"{edge_label};'
                )

        lines.append('}')
        return "\n".join(lines)

    def to_json_dict(self) -> dict:
        """Словарь для JSON-сериализации CFG."""
        return {
            "blocks": [
                {
                    "label": b.label,
                    "instructions": [
                        {
                            "opcode": i.opcode.value,
                            "dest": str(i.dest) if i.dest else None,
                            "src1": str(i.src1) if i.src1 else None,
                            "src2": str(i.src2) if i.src2 else None,
                            "args": [str(a) for a in i.args],
                            "comment": i.comment,
                        }
                        for i in b.instructions
                    ],
                    "successors": [s.label for s in b.successors],
                    "predecessors": [p.label for p in b.predecessors],
                }
                for b in self.blocks
            ]
        }


@dataclass
class IRFunction:
    """
    IR-представление одной функции.

    Содержит:
    - name — имя функции
    - return_type — строковое имя типа возврата
    - params — список пар (имя, тип) параметров
    - cfg — граф потока управления
    - var_map — отображение имени переменной -> VarOperand
    - temp_count — счётчик сгенерированных временных переменных
    """
    name: str
    return_type: str = "void"
    params: List[Tuple[str, str]] = field(default_factory=list)
    cfg: ControlFlowGraph = field(default_factory=ControlFlowGraph)
    var_map: Dict[str, VarOperand] = field(default_factory=dict)
    temp_count: int = 0

    def dump(self) -> str:
        """Текстовый дамп всей функции."""
        params_str = ", ".join(f"{t} {n}" for n, t in self.params)
        header = f"function {self.name}: {self.return_type} ({params_str})"
        body = self.cfg.dump()
        return f"{header}\n{body}"

    def stats(self) -> dict:
        """Статистика IR функции."""
        cfg = self.cfg
        instr_by_type: Dict[str, int] = {}
        for instr in cfg.all_instructions():
            key = instr.opcode.value
            instr_by_type[key] = instr_by_type.get(key, 0) + 1

        return {
            "function": self.name,
            "blocks": cfg.block_count(),
            "total_instructions": cfg.total_instructions(),
            "temporaries": self.temp_count,
            "by_opcode": instr_by_type,
        }

    def to_dot(self) -> str:
        """Graphviz DOT для CFG функции."""
        return self.cfg.to_dot(self.name)

    def to_json_dict(self) -> dict:
        params_str = [{"name": n, "type": t} for n, t in self.params]
        return {
            "name": self.name,
            "return_type": self.return_type,
            "params": params_str,
            "cfg": self.cfg.to_json_dict(),
            "temp_count": self.temp_count,
        }


@dataclass
class IRProgram:
    """
    Полная IR-программа — набор всех IR-функций.

    Sprint 4: главный объект, возвращаемый IRGenerator.generate().
    """
    functions: List[IRFunction] = field(default_factory=list)
    _func_map: Dict[str, IRFunction] = field(default_factory=dict, repr=False)

    def add_function(self, func: IRFunction) -> None:
        """Добавить функцию в программу."""
        self.functions.append(func)
        self._func_map[func.name] = func

    def get_function(self, name: str) -> Optional[IRFunction]:
        """Найти функцию по имени."""
        return self._func_map.get(name)

    def dump(self) -> str:
        """Полный текстовый дамп всей программы."""
        parts = []
        for func in self.functions:
            parts.append(func.dump())
        return "\n\n".join(parts)

    def stats(self) -> dict:
        """Суммарная статистика по всей программе."""
        total_blocks = 0
        total_instrs = 0
        total_temps = 0
        all_by_opcode: Dict[str, int] = {}

        for func in self.functions:
            s = func.stats()
            total_blocks += s["blocks"]
            total_instrs += s["total_instructions"]
            total_temps += s["temporaries"]
            for op, cnt in s["by_opcode"].items():
                all_by_opcode[op] = all_by_opcode.get(op, 0) + cnt

        return {
            "functions": len(self.functions),
            "total_blocks": total_blocks,
            "total_instructions": total_instrs,
            "total_temporaries": total_temps,
            "by_opcode": all_by_opcode,
        }

    def to_dot_all(self) -> Dict[str, str]:
        """DOT-описания для всех функций."""
        return {f.name: f.to_dot() for f in self.functions}

    def to_json(self) -> str:
        """JSON-сериализация программы."""
        data = {
            "program": [f.to_json_dict() for f in self.functions]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
