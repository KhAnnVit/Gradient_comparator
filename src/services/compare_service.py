import difflib
import unicodedata
from collections import Counter
from dataclasses import dataclass

from src.models.compare_models import CompareSettings, CompareResult, HighlightRange
from src.utils.logger import logger


@dataclass
class TextToken:
    """
    Внутренняя модель слова или ингредиента.

    value — нормализованное значение для сравнения.
    start/end — позиции в исходном тексте.
    """

    value: str
    start: int
    end: int
    display: str = ""


class CompareService:
    """
    Сервис сравнения текстов.

    ВАЖНО:
    этот класс ничего не знает про Tkinter и CustomTkinter.

    Он только:
    - принимает два текста;
    - принимает настройки;
    - возвращает CompareResult.
    """

    # =========================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================

    def compare_texts(
        self,
        text1: str,
        text2: str,
        settings: CompareSettings
    ) -> CompareResult:
        """
        Обычное сравнение.

        Если включён режим ignore_word_order,
        сравнивает как набор слов.

        Иначе сравнивает как последовательность символов
        с учётом настроек.
        """

        if settings.ignore_word_order:
            return self._compare_without_word_order(text1, text2, settings)

        return self._compare_with_order(text1, text2, settings)

    def compare_as_composition(
        self,
        text1: str,
        text2: str,
        settings: CompareSettings
    ) -> CompareResult:
        """
        Сравнивает два текста как состав.

        Элемент сравнения — ингредиент целиком.
        Разделитель ингредиентов — запятая.

        Например:
            "PROPYLENE GLYCOL"

        считается одним элементом, а не двумя словами.
        """

        ingredients1 = self._tokenize_ingredients_with_ranges(text1, settings)
        ingredients2 = self._tokenize_ingredients_with_ranges(text2, settings)

        values1 = [item.value for item in ingredients1]
        values2 = [item.value for item in ingredients2]

        counter1 = Counter(values1)
        counter2 = Counter(values2)

        only_left = counter1 - counter2
        only_right = counter2 - counter1
        common = counter1 & counter2

        ranges = []

        self._add_tokens_by_status(
            side="left",
            tokens=ingredients1,
            common_counts=common,
            diff_counts=only_left,
            show_matches=settings.show_matches,
            ranges=ranges
        )

        self._add_tokens_by_status(
            side="right",
            tokens=ingredients2,
            common_counts=common,
            diff_counts=only_right,
            show_matches=settings.show_matches,
            ranges=ranges
        )

        diff_count = sum(only_left.values()) + sum(only_right.values())

        if diff_count == 0:
            message = "Различий не найдено. Сравнение выполнено как состав по ингредиентам."
        else:
            message = (
                f"Найдено отличающихся ингредиентов: {diff_count}. "
                f"Сравнение выполнено как состав по запятым."
            )

        logger.info(
            "Сравнение как состав завершено. only_left=%s, only_right=%s",
            dict(only_left),
            dict(only_right)
        )

        return CompareResult(
            ranges=ranges,
            diff_count=diff_count,
            message=message
        )

    # =========================================================
    # ОБЩИЕ МЕТОДЫ
    # =========================================================

    def _is_punctuation(self, char: str) -> bool:
        """
        Проверяет, является ли символ пунктуацией.
        Работает не только с английской пунктуацией.
        """
        return unicodedata.category(char).startswith("P")

    # =========================================================
    # ОБЫЧНОЕ СРАВНЕНИЕ С УЧЁТОМ ПОРЯДКА
    # =========================================================

    def _normalize_text_with_map(
        self,
        text: str,
        settings: CompareSettings
    ) -> tuple[str, list[int]]:
        """
        Создаёт нормализованную строку и карту индексов.

        Пример:
            исходный текст:      "A Q U A"
            нормализованный:     "aqua"

        index_map нужен, чтобы потом подсветить символы
        именно в исходном тексте.
        """

        normalized_chars = []
        index_map = []

        for original_index, char in enumerate(text):
            if settings.ignore_whitespace and char.isspace():
                continue

            if settings.ignore_punctuation and self._is_punctuation(char):
                continue

            if not settings.case_sensitive:
                char = char.lower()

            normalized_chars.append(char)
            index_map.append(original_index)

        return "".join(normalized_chars), index_map

    def _add_ranges_for_normalized_part(
        self,
        side: str,
        index_map: list[int],
        norm_start: int,
        norm_end: int,
        tag: str,
        ranges: list[HighlightRange]
    ):
        """
        Переводит диапазон из нормализованного текста
        в диапазоны исходного текста.

        Если пробелы игнорировались, они не подсвечиваются.
        """

        if norm_start >= norm_end:
            return

        if not index_map:
            return

        original_positions = index_map[norm_start:norm_end]

        if not original_positions:
            return

        range_start = original_positions[0]
        previous_pos = original_positions[0]

        for pos in original_positions[1:]:
            if pos == previous_pos + 1:
                previous_pos = pos
            else:
                ranges.append(
                    HighlightRange(
                        side=side,
                        start=range_start,
                        end=previous_pos + 1,
                        tag=tag
                    )
                )
                range_start = pos
                previous_pos = pos

        ranges.append(
            HighlightRange(
                side=side,
                start=range_start,
                end=previous_pos + 1,
                tag=tag
            )
        )

    def _compare_with_order(
        self,
        text1: str,
        text2: str,
        settings: CompareSettings
    ) -> CompareResult:
        """
        Обычный режим сравнения.

        Порядок символов важен.
        Но применяются настройки:
        - игнор пробелов;
        - учёт регистра;
        - игнор пунктуации.
        """

        normalized_1, map_1 = self._normalize_text_with_map(text1, settings)
        normalized_2, map_2 = self._normalize_text_with_map(text2, settings)

        matcher = difflib.SequenceMatcher(None, normalized_1, normalized_2)

        ranges = []
        diff_blocks_count = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                if settings.show_matches:
                    self._add_ranges_for_normalized_part(
                        side="left",
                        index_map=map_1,
                        norm_start=i1,
                        norm_end=i2,
                        tag="match",
                        ranges=ranges
                    )
                    self._add_ranges_for_normalized_part(
                        side="right",
                        index_map=map_2,
                        norm_start=j1,
                        norm_end=j2,
                        tag="match",
                        ranges=ranges
                    )

            elif tag in ("replace", "delete", "insert"):
                diff_blocks_count += 1

                if tag in ("replace", "delete"):
                    self._add_ranges_for_normalized_part(
                        side="left",
                        index_map=map_1,
                        norm_start=i1,
                        norm_end=i2,
                        tag="diff",
                        ranges=ranges
                    )

                if tag in ("replace", "insert"):
                    self._add_ranges_for_normalized_part(
                        side="right",
                        index_map=map_2,
                        norm_start=j1,
                        norm_end=j2,
                        tag="diff",
                        ranges=ranges
                    )

        if diff_blocks_count == 0:
            message = "Различий не найдено."
        else:
            message = f"Найдено блоков различий: {diff_blocks_count}."

        logger.info(
            "Сравнение с учётом порядка завершено. Блоков различий: %s",
            diff_blocks_count
        )

        return CompareResult(
            ranges=ranges,
            diff_count=diff_blocks_count,
            message=message
        )

    # =========================================================
    # СРАВНЕНИЕ БЕЗ УЧЁТА ПОРЯДКА СЛОВ
    # =========================================================

    def _tokenize_words_with_ranges(
        self,
        text: str,
        settings: CompareSettings
    ) -> list[TextToken]:
        """
        Разбивает текст на слова и запоминает позиции слов
        в исходном тексте.
        """

        tokens = []

        current_chars = []
        current_start = None
        current_end = None

        def flush_token():
            nonlocal current_chars, current_start, current_end

            if not current_chars:
                return

            token_value = "".join(current_chars)

            if not settings.case_sensitive:
                token_value = token_value.lower()

            tokens.append(
                TextToken(
                    value=token_value,
                    start=current_start,
                    end=current_end,
                    display=token_value
                )
            )

            current_chars = []
            current_start = None
            current_end = None

        for index, char in enumerate(text):
            if char.isspace():
                flush_token()
                continue

            if self._is_punctuation(char):
                if char in ("/", "-"):
                    if settings.ignore_punctuation:
                        continue

                    if current_start is None:
                        current_start = index

                    current_chars.append(char)
                    current_end = index + 1
                    continue

                flush_token()
                continue

            if current_start is None:
                current_start = index

            current_chars.append(char)
            current_end = index + 1

        flush_token()

        return tokens

    def _add_tokens_by_status(
        self,
        side: str,
        tokens: list[TextToken],
        common_counts: Counter,
        diff_counts: Counter,
        show_matches: bool,
        ranges: list[HighlightRange]
    ):
        """
        Добавляет диапазоны подсветки без наложения цветов.

        Одно конкретное слово или ингредиент может быть только:
        - match;
        - diff;
        - без подсветки.
        """

        remaining_common = Counter(common_counts)
        remaining_diff = Counter(diff_counts)

        for token in tokens:
            value = token.value

            if remaining_common[value] > 0:
                if show_matches:
                    ranges.append(
                        HighlightRange(
                            side=side,
                            start=token.start,
                            end=token.end,
                            tag="match"
                        )
                    )

                remaining_common[value] -= 1
                continue

            if remaining_diff[value] > 0:
                ranges.append(
                    HighlightRange(
                        side=side,
                        start=token.start,
                        end=token.end,
                        tag="diff"
                    )
                )

                remaining_diff[value] -= 1

    def _compare_without_word_order(
        self,
        text1: str,
        text2: str,
        settings: CompareSettings
    ) -> CompareResult:
        """
        Сравнивает тексты как наборы слов.
        Порядок слов не учитывается.
        """

        tokens1 = self._tokenize_words_with_ranges(text1, settings)
        tokens2 = self._tokenize_words_with_ranges(text2, settings)

        values1 = [token.value for token in tokens1]
        values2 = [token.value for token in tokens2]

        counter1 = Counter(values1)
        counter2 = Counter(values2)

        only_left = counter1 - counter2
        only_right = counter2 - counter1
        common = counter1 & counter2

        ranges = []

        self._add_tokens_by_status(
            side="left",
            tokens=tokens1,
            common_counts=common,
            diff_counts=only_left,
            show_matches=settings.show_matches,
            ranges=ranges
        )

        self._add_tokens_by_status(
            side="right",
            tokens=tokens2,
            common_counts=common,
            diff_counts=only_right,
            show_matches=settings.show_matches,
            ranges=ranges
        )

        diff_words_count = sum(only_left.values()) + sum(only_right.values())

        if diff_words_count == 0:
            message = "Различий не найдено. Порядок слов не учитывался."
        else:
            message = (
                f"Найдено отличающихся слов: {diff_words_count}. "
                f"Порядок слов не учитывался."
            )

        logger.info(
            "Сравнение без учёта порядка слов завершено. only_left=%s, only_right=%s",
            dict(only_left),
            dict(only_right)
        )

        return CompareResult(
            ranges=ranges,
            diff_count=diff_words_count,
            message=message
        )

    # =========================================================
    # СРАВНЕНИЕ КАК СОСТАВ
    # =========================================================

    def _normalize_ingredient_for_compare(
        self,
        ingredient: str,
        settings: CompareSettings
    ) -> str:
        """
        Нормализует один ингредиент для сравнения.
        """

        ingredient = ingredient.strip()
        ingredient = " ".join(ingredient.split())

        if settings.ignore_punctuation:
            ingredient = "".join(
                char for char in ingredient
                if not self._is_punctuation(char)
            )
            ingredient = " ".join(ingredient.split())

        if not settings.case_sensitive:
            ingredient = ingredient.lower()

        return ingredient

    def _remove_composition_prefix(
        self,
        text: str,
        start_index: int
    ) -> tuple[str, int]:
        """
        Убирает служебный префикс перед первым ингредиентом.

        Например:
            "СОСТАВ: AQUA" -> "AQUA"
            "INGREDIENTS: Aqua" -> "Aqua"
        """

        stripped_left = len(text) - len(text.lstrip())
        text_lstripped = text.lstrip()
        current_start = start_index + stripped_left

        if ":" in text_lstripped:
            colon_pos = text_lstripped.find(":")
            prefix = text_lstripped[:colon_pos].strip().lower()

            known_prefixes = {
                "состав",
                "ingredients",
                "ingredient",
                "inci",
                "composition"
            }

            if prefix in known_prefixes:
                after_colon = text_lstripped[colon_pos + 1:]
                spaces_after_colon = len(after_colon) - len(after_colon.lstrip())

                new_text = after_colon.lstrip()
                new_start = current_start + colon_pos + 1 + spaces_after_colon

                return new_text, new_start

        return text, start_index

    def _tokenize_ingredients_with_ranges(
        self,
        text: str,
        settings: CompareSettings
    ) -> list[TextToken]:
        """
        Разбивает состав на ингредиенты по запятым.
        """

        ingredients = []

        part_start = 0
        parts = text.split(",")

        for part_index, raw_part in enumerate(parts):
            original_start = part_start
            original_end = part_start + len(raw_part)

            left_spaces = len(raw_part) - len(raw_part.lstrip())
            right_spaces = len(raw_part) - len(raw_part.rstrip())

            clean_start = original_start + left_spaces
            clean_end = original_end - right_spaces

            clean_text = raw_part.strip()

            if part_index == 0:
                clean_text, clean_start = self._remove_composition_prefix(
                    clean_text,
                    clean_start
                )
                clean_text = clean_text.strip()
                clean_end = clean_start + len(clean_text)

            if not clean_text:
                part_start += len(raw_part) + 1
                continue

            normalized_value = self._normalize_ingredient_for_compare(
                clean_text,
                settings
            )

            if not normalized_value:
                part_start += len(raw_part) + 1
                continue

            ingredients.append(
                TextToken(
                    value=normalized_value,
                    start=clean_start,
                    end=clean_end,
                    display=clean_text
                )
            )

            part_start += len(raw_part) + 1

        return ingredients