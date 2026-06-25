from dataclasses import dataclass, field


@dataclass
class CompareSettings:
    """
    Настройки сравнения.

    Этот объект создаётся в GUI на основе состояния чекбоксов
    и передаётся в CompareService.
    """

    # Игнорировать пробелы, табы и переносы строк.
    ignore_whitespace: bool = True

    # Учитывать регистр.
    # Если False, то AQUA и aqua считаются одинаковыми.
    case_sensitive: bool = False

    # Игнорировать пунктуацию.
    # Например, PEG-40 и PEG40 могут считаться одинаковыми.
    ignore_punctuation: bool = False

    # Не учитывать порядок слов.
    # Например: "AQUA PVP" == "PVP AQUA".
    ignore_word_order: bool = False

    # Подсвечивать совпадения зелёным.
    show_matches: bool = False


@dataclass
class HighlightRange:
    """
    Один диапазон подсветки.

    side:
        "left"  — левое поле
        "right" — правое поле

    start/end:
        позиции символов в исходном тексте

    tag:
        "diff"  — различие
        "match" — совпадение
    """

    side: str
    start: int
    end: int
    tag: str


@dataclass
class CompareResult:
    """
    Результат сравнения.

    GUI получает этот объект и сам решает,
    как подсветить текст.
    """

    ranges: list[HighlightRange] = field(default_factory=list)
    diff_count: int = 0
    message: str = ""