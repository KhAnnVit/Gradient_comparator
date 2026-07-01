import customtkinter as ctk
import tkinter as tk
from tkinter import Menu
import difflib
import re
import unicodedata
from collections import Counter

from src.utils.logger import logger


class CompareSection(ctk.CTkFrame):
    """
    Третий раздел приложения: сравнение двух текстов.

    Основная идея:
    - обычное сравнение всего текста;
    - сравнение без учёта порядка слов;
    - сравнение составов по ингредиентам;
    - поиск нескольких похожих последовательных блоков.

    Новый режим похожих блоков:
    - не опирается на строки и абзацы;
    - режет текст на токены;
    - ищет совпадающие последовательности токенов;
    - соседние совпадения объединяет в один блок, если порядок одинаковый;
    - если порядок изменился, создаёт отдельный цветной блок;
    - различия внутри найденного блока подсвечивает красным;
    - текст без пары подсвечивает красным.
    """

    SEQUENCE_BLOCK_COLORS = [
        "#dbeafe",  # голубой
        "#dcfce7",  # зелёный
        "#fef3c7",  # жёлтый
        "#fce7f3",  # розовый
        "#ede9fe",  # фиолетовый
        "#ccfbf1",  # бирюзовый
        "#ffedd5",  # оранжевый
        "#e0e7ff",  # синий
    ]

    def __init__(self, master):
        super().__init__(master)

        self.active_textbox = None

        self._configure_grid()
        self._create_settings_variables()
        self._create_widgets()
        self._create_context_menu()
        self._configure_text_tags()

    # =========================================================
    # ИНИЦИАЛИЗАЦИЯ
    # =========================================================

    def _configure_grid(self):
        """Настраивает главную сетку раздела."""

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _create_settings_variables(self):
        """Создаёт переменные настроек сравнения."""

        self.ignore_whitespace_var = tk.BooleanVar(value=True)
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.ignore_punctuation_var = tk.BooleanVar(value=False)
        self.ignore_word_order_var = tk.BooleanVar(value=False)

        # Теперь этот режим ищет не один блок, а несколько последовательных блоков.
        self.find_similar_block_var = tk.BooleanVar(value=True)

        self.show_matches_var = tk.BooleanVar(value=False)

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт все элементы интерфейса."""

        self._create_title()
        self._create_settings_panel()
        self._create_text_fields()
        self._create_bottom_panel()
        self._create_result_label()

    def _create_title(self):
        """Создаёт заголовок раздела."""

        self.title_label = ctk.CTkLabel(
            self,
            text="Сравнение текстов",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(10, 5)
        )

    def _create_settings_panel(self):
        """Создаёт панель настроек сравнения."""

        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=10,
            pady=(5, 10)
        )

        for column_index in range(3):
            self.settings_frame.grid_columnconfigure(
                column_index,
                weight=1
            )

        self.ignore_whitespace_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Игнорировать пробелы и переносы",
            variable=self.ignore_whitespace_var,
            command=self.clear_highlights
        )
        self.ignore_whitespace_checkbox.grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(10, 5)
        )

        self.case_sensitive_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Учитывать регистр",
            variable=self.case_sensitive_var,
            command=self.clear_highlights
        )
        self.case_sensitive_checkbox.grid(
            row=0,
            column=1,
            sticky="w",
            padx=12,
            pady=(10, 5)
        )

        self.ignore_punctuation_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Игнорировать пунктуацию",
            variable=self.ignore_punctuation_var,
            command=self.clear_highlights
        )
        self.ignore_punctuation_checkbox.grid(
            row=0,
            column=2,
            sticky="w",
            padx=12,
            pady=(10, 5)
        )

        self.find_similar_block_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Искать похожие блоки",
            variable=self.find_similar_block_var,
            command=self.clear_highlights
        )
        self.find_similar_block_checkbox.grid(
            row=1,
            column=0,
            sticky="w",
            padx=12,
            pady=(5, 5)
        )

        self.ignore_word_order_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Не учитывать порядок слов внутри сравнения",
            variable=self.ignore_word_order_var,
            command=self.clear_highlights
        )
        self.ignore_word_order_checkbox.grid(
            row=1,
            column=1,
            sticky="w",
            padx=12,
            pady=(5, 5)
        )

        self.show_matches_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Подсвечивать совпадения",
            variable=self.show_matches_var,
            command=self.clear_highlights
        )
        self.show_matches_checkbox.grid(
            row=1,
            column=2,
            sticky="w",
            padx=12,
            pady=(5, 5)
        )

        self.btn_clear_highlights = ctk.CTkButton(
            self.settings_frame,
            text="Очистить подсветку",
            command=self.clear_highlights,
            width=160
        )
        self.btn_clear_highlights.grid(
            row=2,
            column=2,
            sticky="e",
            padx=12,
            pady=(5, 10)
        )

    def _create_text_fields(self):
        """Создаёт два текстовых поля."""

        self.texts_frame = ctk.CTkFrame(self)
        self.texts_frame.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10
        )

        self.texts_frame.grid_rowconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(1, weight=1)

        self.left_frame = ctk.CTkFrame(self.texts_frame)
        self.left_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 5)
        )
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.left_label = ctk.CTkLabel(
            self.left_frame,
            text="Текст 1",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.left_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=10,
            pady=(10, 5)
        )

        self.left_textbox = tk.Text(
            self.left_frame,
            wrap="word",
            font=("Consolas", 12),
            undo=True,
            padx=10,
            pady=10
        )
        self.left_textbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(10, 0),
            pady=(0, 10)
        )

        self.left_scrollbar = ctk.CTkScrollbar(
            self.left_frame,
            command=self.left_textbox.yview
        )
        self.left_scrollbar.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 10),
            pady=(0, 10)
        )
        self.left_textbox.configure(
            yscrollcommand=self.left_scrollbar.set
        )

        self.right_frame = ctk.CTkFrame(self.texts_frame)
        self.right_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(5, 0)
        )
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.right_label = ctk.CTkLabel(
            self.right_frame,
            text="Текст 2",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.right_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=10,
            pady=(10, 5)
        )

        self.right_textbox = tk.Text(
            self.right_frame,
            wrap="word",
            font=("Consolas", 12),
            undo=True,
            padx=10,
            pady=10
        )
        self.right_textbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(10, 0),
            pady=(0, 10)
        )

        self.right_scrollbar = ctk.CTkScrollbar(
            self.right_frame,
            command=self.right_textbox.yview
        )
        self.right_scrollbar.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 10),
            pady=(0, 10)
        )
        self.right_textbox.configure(
            yscrollcommand=self.right_scrollbar.set
        )

    def _create_bottom_panel(self):
        """Создаёт нижнюю панель с кнопками сравнения."""

        self.bottom_panel = ctk.CTkFrame(self)
        self.bottom_panel.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=10,
            pady=(0, 5)
        )

        for column_index in range(4):
            self.bottom_panel.grid_columnconfigure(column_index, weight=1)

        self.btn_compare = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить",
            command=self.compare_texts,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(20, 8),
            pady=10
        )

        self.btn_compare_blocks = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить блоками",
            command=self.compare_as_sequence_blocks,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare_blocks.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=8,
            pady=10
        )

        self.btn_compare_composition = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить как состав",
            command=self.compare_as_composition,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare_composition.grid(
            row=0,
            column=2,
            sticky="ew",
            padx=8,
            pady=10
        )

        self.btn_clear_fields = ctk.CTkButton(
            self.bottom_panel,
            text="Очистить поля",
            command=self.clear_fields,
            height=40
        )
        self.btn_clear_fields.grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 20),
            pady=10
        )

    def _create_result_label(self):
        """Создаёт строку результата."""

        self.result_label = ctk.CTkLabel(
            self,
            text=(
                "По умолчанию: ищутся похожие последовательные блоки. "
                "Строки и абзацы не влияют на поиск."
            ),
            anchor="w"
        )
        self.result_label.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=15,
            pady=(0, 10)
        )

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================

    def _create_context_menu(self):
        """Создаёт контекстное меню для двух текстовых полей."""

        self.context_menu = Menu(self, tearoff=0)

        self.context_menu.add_command(
            label="Копировать",
            command=self.copy_text
        )

        self.context_menu.add_command(
            label="Вставить",
            command=self.paste_text
        )

        self.context_menu.add_separator()

        self.context_menu.add_command(
            label="Выделить всё",
            command=self.select_all
        )

        self.left_textbox.bind("<Button-3>", self.show_context_menu)
        self.right_textbox.bind("<Button-3>", self.show_context_menu)

        self.left_textbox.bind(
            "<Button-1>",
            lambda event: self.set_active_textbox(self.left_textbox)
        )
        self.right_textbox.bind(
            "<Button-1>",
            lambda event: self.set_active_textbox(self.right_textbox)
        )

        self.left_textbox.bind(
            "<FocusIn>",
            lambda event: self.set_active_textbox(self.left_textbox)
        )
        self.right_textbox.bind(
            "<FocusIn>",
            lambda event: self.set_active_textbox(self.right_textbox)
        )

        self.active_textbox = self.left_textbox

    def set_active_textbox(self, textbox):
        """Запоминает активное текстовое поле."""

        self.active_textbox = textbox

    def show_context_menu(self, event):
        """Показывает контекстное меню."""

        self.active_textbox = event.widget

        try:
            self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            logger.exception("Ошибка при открытии контекстного меню сравнения")

    def copy_text(self):
        """Копирует выделенный текст."""

        if self.active_textbox is None:
            return

        try:
            selected_text = self.active_textbox.get("sel.first", "sel.last")
            self.master.clipboard_clear()
            self.master.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def paste_text(self):
        """Вставляет текст из буфера обмена."""

        if self.active_textbox is None:
            return

        try:
            clipboard_text = self.master.clipboard_get()

            try:
                self.active_textbox.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

            self.active_textbox.insert("insert", clipboard_text)
            self.clear_highlights()

        except tk.TclError:
            pass

    def select_all(self):
        """Выделяет весь текст в активном поле."""

        if self.active_textbox is None:
            return

        self.active_textbox.focus_set()
        self.active_textbox.tag_add("sel", "1.0", "end")
        self._raise_selection_tag(self.active_textbox)

    # =========================================================
    # ПОДСВЕТКА
    # =========================================================

    def _configure_text_tags(self):
        """
        Настраивает теги для подсветки.

        Важно:
        системное выделение текста в tk.Text — это тег "sel".
        Поэтому "sel" всегда поднимаем наверх.
        """

        for textbox in (self.left_textbox, self.right_textbox):
            self._configure_selection_style(textbox)

            textbox.tag_configure(
                "diff",
                foreground="#991b1b",
                background="#fecaca"
            )

            textbox.tag_configure(
                "match",
                foreground="#166534",
                background="#dcfce7"
            )

            textbox.tag_configure(
                "similar",
                foreground="#111827",
                background="#fef08a"
            )

            textbox.tag_configure(
                "search_match",
                foreground="#111827",
                background="#fef08a"
            )

            textbox.tag_configure(
                "sequence_missing",
                foreground="#991b1b",
                background="#fee2e2"
            )

            for index, color in enumerate(self.SEQUENCE_BLOCK_COLORS):
                textbox.tag_configure(
                    f"sequence_block_{index}",
                    foreground="#111827",
                    background=color
                )

            try:
                textbox.tag_raise("diff")
                textbox.tag_raise("sequence_missing")
                textbox.tag_raise("sel")
            except tk.TclError:
                pass

            self._bind_selection_visibility_events(textbox)

    def _configure_selection_style(self, textbox):
        """Делает пользовательское выделение текста контрастным."""

        try:
            textbox.configure(
                selectbackground="#2563eb",
                selectforeground="#ffffff",
                inactiveselectbackground="#1d4ed8"
            )
        except tk.TclError:
            try:
                textbox.configure(
                    selectbackground="#2563eb",
                    selectforeground="#ffffff"
                )
            except tk.TclError:
                logger.debug(
                    "Не удалось настроить цвет выделения текста",
                    exc_info=True
                )

    def _raise_selection_tag(self, textbox):
        """Поднимает системный тег выделения 'sel' выше всех тегов."""

        try:
            textbox.tag_raise("sel")
        except tk.TclError:
            pass

    def _bind_selection_visibility_events(self, textbox):
        """Следит, чтобы выделение оставалось видимым."""

        textbox.bind(
            "<ButtonRelease-1>",
            lambda event, tb=textbox: self._raise_selection_tag(tb),
            add="+"
        )

        textbox.bind(
            "<B1-Motion>",
            lambda event, tb=textbox: tb.after_idle(
                lambda: self._raise_selection_tag(tb)
            ),
            add="+"
        )

        textbox.bind(
            "<KeyRelease>",
            lambda event, tb=textbox: self._raise_selection_tag(tb),
            add="+"
        )

        textbox.bind(
            "<<Selection>>",
            lambda event, tb=textbox: self._raise_selection_tag(tb),
            add="+"
        )

    def clear_highlights(self):
        """Удаляет подсветку из обоих текстовых полей."""

        for textbox in (self.left_textbox, self.right_textbox):
            textbox.tag_remove("diff", "1.0", "end")
            textbox.tag_remove("match", "1.0", "end")
            textbox.tag_remove("similar", "1.0", "end")
            textbox.tag_remove("search_match", "1.0", "end")
            textbox.tag_remove("sequence_missing", "1.0", "end")

            for tag_name in textbox.tag_names():
                if tag_name.startswith("sequence_block_"):
                    textbox.tag_remove(tag_name, "1.0", "end")

            self._raise_selection_tag(textbox)

        self.result_label.configure(text="Подсветка очищена.")

    def clear_fields(self):
        """Очищает оба поля сравнения."""

        self.left_textbox.delete("1.0", "end")
        self.right_textbox.delete("1.0", "end")
        self.clear_highlights()
        self.result_label.configure(text="Поля очищены.")

    def _add_text_tag(self, textbox, start_char, end_char, tag_name):
        """Добавляет тег к диапазону символов."""

        if start_char is None or end_char is None:
            return

        if start_char >= end_char:
            return

        start_index = f"1.0+{start_char}c"
        end_index = f"1.0+{end_char}c"

        try:
            textbox.tag_add(tag_name, start_index, end_index)
            self._raise_selection_tag(textbox)
        except tk.TclError:
            logger.debug(
                "Не удалось добавить тег подсветки. tag=%s, start=%s, end=%s",
                tag_name,
                start_index,
                end_index,
                exc_info=True
            )

    def _add_tag_for_normalized_range(
        self,
        textbox,
        index_map,
        norm_start,
        norm_end,
        tag_name
    ):
        """Подсвечивает диапазон нормализованного текста в исходном тексте."""

        if norm_start >= norm_end:
            return

        if not index_map:
            return

        original_positions = index_map[norm_start:norm_end]

        if not original_positions:
            return

        range_start = original_positions[0]
        previous_position = original_positions[0]

        for position in original_positions[1:]:
            if position == previous_position + 1:
                previous_position = position
                continue

            self._add_text_tag(
                textbox,
                range_start,
                previous_position + 1,
                tag_name
            )

            range_start = position
            previous_position = position

        self._add_text_tag(
            textbox,
            range_start,
            previous_position + 1,
            tag_name
        )

    # =========================================================
    # НОРМАЛИЗАЦИЯ
    # =========================================================

    def _is_punctuation(self, char):
        """Проверяет, является ли символ пунктуацией."""

        return unicodedata.category(char).startswith("P")

    def _normalize_char_for_compare(self, char):
        """Нормализует один символ для сравнения."""

        replacements = {
            "ё": "е",
            "Ё": "Е",
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
            "«": '"',
            "»": '"',
            "–": "-",
            "—": "-",
            "−": "-",
        }

        char = replacements.get(char, char)

        if not self.case_sensitive_var.get():
            char = char.lower()

        return char

    def _normalize_text_with_map(self, text):
        """
        Возвращает:
            normalized_text — строка для сравнения;
            index_map — карта индексов normalized_text -> исходный текст.
        """

        normalized_chars = []
        index_map = []

        ignore_whitespace = self.ignore_whitespace_var.get()
        ignore_punctuation = self.ignore_punctuation_var.get()

        for original_index, original_char in enumerate(text):
            if ignore_whitespace and original_char.isspace():
                continue

            if ignore_punctuation and self._is_punctuation(original_char):
                continue

            normalized_char = self._normalize_char_for_compare(original_char)

            normalized_chars.append(normalized_char)
            index_map.append(original_index)

        return "".join(normalized_chars), index_map

    def _normalize_text_range_with_map(self, text, start_char, end_char):
        """Нормализует только выбранный диапазон текста."""

        substring = text[start_char:end_char]

        normalized_text, local_index_map = self._normalize_text_with_map(
            substring
        )

        global_index_map = [
            start_char + local_index
            for local_index in local_index_map
        ]

        return normalized_text, global_index_map

    def _normalize_word_for_compare(self, word):
        """Нормализует слово/токен для сравнения."""

        if not word:
            return ""

        normalized_chars = []

        for char in word:
            if self.ignore_punctuation_var.get() and self._is_punctuation(char):
                continue

            if char.isspace():
                continue

            normalized_chars.append(
                self._normalize_char_for_compare(char)
            )

        normalized_word = "".join(normalized_chars)

        return normalized_word.strip()

    def _normalize_ingredient_for_compare(self, ingredient):
        """
        Нормализует ингредиент состава.

        Для состава нормализация мягче к пунктуации:
        PEG-40, PEG 40 и PEG40 часто должны восприниматься как одно.
        """

        if not ingredient:
            return ""

        ingredient = ingredient.strip()
        ingredient = self._remove_composition_prefix_from_text(ingredient)

        chars = []

        for char in ingredient:
            if char.isspace():
                continue

            if self._is_punctuation(char):
                continue

            chars.append(
                self._normalize_char_for_compare(char)
            )

        return "".join(chars)

    # =========================================================
    # ТОКЕНИЗАЦИЯ
    # =========================================================

    def _tokenize_words_with_ranges(self, text, offset=0):
        """
        Разбивает текст на токены с позициями.

        Используется для сравнения без учёта порядка слов.
        """

        tokens = []

        for match in re.finditer(r"\S+", text):
            display_value = match.group(0)
            normalized_value = self._normalize_word_for_compare(display_value)

            if not normalized_value:
                continue

            tokens.append({
                "value": normalized_value,
                "display": display_value,
                "start": offset + match.start(),
                "end": offset + match.end()
            })

        return tokens

    def _tokenize_sequence_units_with_ranges(self, text):
        """
        Разбивает текст на токены для поиска последовательных блоков.

        Не используем строки и абзацы.
        OCR может переносить один блок на несколько строк
        или склеивать несколько блоков в одну строку.
        """

        tokens = []

        pattern = re.compile(
            r"[0-9A-Za-zА-Яа-яЁё]+"
            r"(?:[-/][0-9A-Za-zА-Яа-яЁё]+)*"
        )

        for match in pattern.finditer(text):
            display_value = match.group(0)
            normalized_value = self._normalize_word_for_compare(display_value)

            if not normalized_value:
                continue

            tokens.append({
                "value": normalized_value,
                "display": display_value,
                "start": match.start(),
                "end": match.end()
            })

        return tokens

    def _tokenize_ingredients_with_ranges(self, text):
        """
        Разбивает текст состава на ингредиенты по запятым.

        Если найдено слово СОСТАВ / INGREDIENTS / INCI,
        всё до него отрезается.
        """

        composition_text, composition_offset = (
            self._extract_composition_text_with_offset(text)
        )

        ingredients = []

        parts = re.split(r"[,;]", composition_text)

        current_position = 0

        for raw_part in parts:
            part_start_in_composition = current_position
            part_end_in_composition = current_position + len(raw_part)

            current_position += len(raw_part) + 1

            raw_start = composition_offset + part_start_in_composition
            raw_end = composition_offset + part_end_in_composition

            left_spaces = len(raw_part) - len(raw_part.lstrip())
            right_spaces = len(raw_part) - len(raw_part.rstrip())

            clean_start = raw_start + left_spaces
            clean_end = raw_end - right_spaces

            clean_display = raw_part.strip()

            clean_display = self._remove_composition_prefix_from_text(
                clean_display
            )

            if not clean_display:
                continue

            normalized_value = self._normalize_ingredient_for_compare(
                clean_display
            )

            if not normalized_value:
                continue

            clean_end = clean_start + len(clean_display)

            ingredients.append({
                "value": normalized_value,
                "display": clean_display,
                "start": clean_start,
                "end": clean_end
            })

        return ingredients

    # =========================================================
    # ОБЫЧНОЕ СРАВНЕНИЕ ВСЕГО ТЕКСТА
    # =========================================================

    def _compare_with_order(self, text1, text2):
        """Сравнивает весь текст как последовательность символов."""

        normalized_1, map_1 = self._normalize_text_with_map(text1)
        normalized_2, map_2 = self._normalize_text_with_map(text2)

        matcher = difflib.SequenceMatcher(
            None,
            normalized_1,
            normalized_2,
            autojunk=False
        )

        diff_blocks_count = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                if self.show_matches_var.get():
                    self._add_tag_for_normalized_range(
                        self.left_textbox,
                        map_1,
                        i1,
                        i2,
                        "match"
                    )

                    self._add_tag_for_normalized_range(
                        self.right_textbox,
                        map_2,
                        j1,
                        j2,
                        "match"
                    )

                continue

            diff_blocks_count += 1

            if tag in ("replace", "delete"):
                self._add_tag_for_normalized_range(
                    self.left_textbox,
                    map_1,
                    i1,
                    i2,
                    "diff"
                )

            if tag in ("replace", "insert"):
                self._add_tag_for_normalized_range(
                    self.right_textbox,
                    map_2,
                    j1,
                    j2,
                    "diff"
                )

        if diff_blocks_count == 0:
            self.result_label.configure(text="Различий не найдено.")
        else:
            self.result_label.configure(
                text=f"Найдено блоков различий: {diff_blocks_count}."
            )

        logger.info(
            "Сравнение всего текста завершено. diff_blocks=%s",
            diff_blocks_count
        )

    # =========================================================
    # СРАВНЕНИЕ БЕЗ УЧЁТА ПОРЯДКА СЛОВ
    # =========================================================

    def _highlight_tokens_by_status(
        self,
        textbox,
        tokens,
        common_counter,
        diff_counter
    ):
        """
        Подсвечивает токены по статусу.

        Красным — то, что есть только в одном тексте.
        Зелёным — совпадения, если включена соответствующая настройка.
        """

        common_left = Counter(common_counter)
        diff_left = Counter(diff_counter)

        for token in tokens:
            value = token["value"]

            if diff_left[value] > 0:
                self._add_text_tag(
                    textbox,
                    token["start"],
                    token["end"],
                    "diff"
                )
                diff_left[value] -= 1
                continue

            if self.show_matches_var.get() and common_left[value] > 0:
                self._add_text_tag(
                    textbox,
                    token["start"],
                    token["end"],
                    "match"
                )
                common_left[value] -= 1

    def _compare_tokens_without_word_order(self, tokens1, tokens2):
        """Сравнивает два списка токенов без учёта порядка."""

        counter1 = Counter(
            token["value"]
            for token in tokens1
        )

        counter2 = Counter(
            token["value"]
            for token in tokens2
        )

        only_left = counter1 - counter2
        only_right = counter2 - counter1
        common = counter1 & counter2

        self._highlight_tokens_by_status(
            self.left_textbox,
            tokens1,
            common,
            only_left
        )

        self._highlight_tokens_by_status(
            self.right_textbox,
            tokens2,
            common,
            only_right
        )

        diff_words_count = sum(only_left.values()) + sum(only_right.values())

        return diff_words_count

    def _compare_without_word_order(self, text1, text2):
        """Сравнивает весь текст как набор слов."""

        tokens1 = self._tokenize_words_with_ranges(text1)
        tokens2 = self._tokenize_words_with_ranges(text2)

        diff_words_count = self._compare_tokens_without_word_order(
            tokens1,
            tokens2
        )

        if diff_words_count == 0:
            self.result_label.configure(
                text="Различий не найдено. Порядок слов не учитывался."
            )
        else:
            self.result_label.configure(
                text=(
                    f"Найдено отличающихся слов: {diff_words_count}. "
                    "Порядок слов не учитывался."
                )
            )

        logger.info(
            "Сравнение без учёта порядка слов завершено. diff_words=%s",
            diff_words_count
        )

    # =========================================================
    # СРАВНЕНИЕ ПОСЛЕДОВАТЕЛЬНЫМИ БЛОКАМИ
    # =========================================================

    def compare_as_sequence_blocks(self):
        """Публичный метод для кнопки 'Сравнить блоками'."""

        self.clear_highlights()

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return

        if not text1 or not text2:
            self.result_label.configure(
                text="Одно из полей пустое. Сравнение невозможно."
            )
            return

        try:
            self._compare_by_sequence_blocks(text1, text2)
        except Exception:
            logger.exception("Ошибка при сравнении последовательными блоками")
            self.result_label.configure(
                text="Ошибка при сравнении блоками. Подробности в app.log."
            )

    def _compare_by_sequence_blocks(self, text1, text2):
        """
        Сравнивает тексты как набор последовательных совпадающих участков.

        Цветной фон = найденный общий блок.
        Красный фон внутри цветного блока = отличие внутри найденного блока.
        Красный фон вне цветных блоков = текст без пары.
        """

        tokens1 = self._tokenize_sequence_units_with_ranges(text1)
        tokens2 = self._tokenize_sequence_units_with_ranges(text2)

        if not tokens1 or not tokens2:
            self._compare_with_order(text1, text2)
            return

        matched_runs = self._find_matching_token_runs(
            left_tokens=tokens1,
            right_tokens=tokens2
        )

        if not matched_runs:
            self._compare_with_order(text1, text2)
            self.result_label.configure(
                text=(
                    "Похожие последовательные блоки не найдены. "
                    "Выполнено обычное сравнение всего текста."
                )
            )
            return

        groups = self._build_sequence_groups_from_runs(
            matched_runs=matched_runs,
            left_tokens=tokens1,
            right_tokens=tokens2
        )

        groups = self._extend_sequence_groups_to_nearby_diffs(
            groups=groups,
            left_tokens=tokens1,
            right_tokens=tokens2
        )

        if not groups:
            self._compare_with_order(text1, text2)
            return

        diff_count = self._highlight_sequence_groups(
            groups=groups,
            left_tokens=tokens1,
            right_tokens=tokens2,
            text1=text1,
            text2=text2
        )

        left_missing_count, right_missing_count = (
            self._highlight_uncovered_sequence_tokens(
                groups=groups,
                left_tokens=tokens1,
                right_tokens=tokens2
            )
        )

        self._raise_diff_tags_above_blocks()

        self.result_label.configure(
            text=(
                f"Найдено блоков: {len(groups)}. "
                f"Различий внутри блоков: {diff_count}. "
                f"Без пары: слева {left_missing_count}, справа {right_missing_count}."
            )
        )

        logger.info(
            (
                "Сравнение последовательных блоков завершено. "
                "groups=%s, diff_count=%s, left_missing=%s, right_missing=%s"
            ),
            len(groups),
            diff_count,
            left_missing_count,
            right_missing_count
        )

    def _find_matching_token_runs(self, left_tokens, right_tokens):
        """
        Ищет совпадающие последовательности токенов между двумя полями.

        Если блоки поменялись местами, совпадения всё равно найдутся.
        Объединение в блоки решается позже по порядку.
        """

        right_index = {}

        for index, token in enumerate(right_tokens):
            value = token["value"]

            if len(value) <= 1:
                continue

            right_index.setdefault(value, []).append(index)

        candidates = []

        for left_start, left_token in enumerate(left_tokens):
            value = left_token["value"]

            if value not in right_index:
                continue

            # Слишком частые слова дают шум.
            if len(right_index[value]) > 40:
                continue

            for right_start in right_index[value]:
                length = self._expand_equal_token_run(
                    left_tokens=left_tokens,
                    right_tokens=right_tokens,
                    left_start=left_start,
                    right_start=right_start
                )

                if length <= 0:
                    continue

                left_end = left_start + length
                right_end = right_start + length

                if not self._is_meaningful_token_run(
                    tokens=left_tokens,
                    start=left_start,
                    end=left_end
                ):
                    continue

                candidates.append({
                    "left_start": left_start,
                    "left_end": left_end,
                    "right_start": right_start,
                    "right_end": right_end,
                    "length": length,
                    "char_length": self._token_slice_char_length(
                        left_tokens,
                        left_start,
                        left_end
                    )
                })

        candidates.sort(
            key=lambda item: (
                item["length"],
                item["char_length"]
            ),
            reverse=True
        )

        selected_runs = []
        used_left = set()
        used_right = set()

        for candidate in candidates:
            left_range = set(
                range(candidate["left_start"], candidate["left_end"])
            )
            right_range = set(
                range(candidate["right_start"], candidate["right_end"])
            )

            if left_range & used_left:
                continue

            if right_range & used_right:
                continue

            selected_runs.append(candidate)

            used_left.update(left_range)
            used_right.update(right_range)

        selected_runs.sort(
            key=lambda item: (
                item["left_start"],
                item["right_start"]
            )
        )

        return selected_runs

    def _expand_equal_token_run(
        self,
        left_tokens,
        right_tokens,
        left_start,
        right_start
    ):
        """Расширяет совпадение вправо, пока токены одинаковые."""

        length = 0

        while (
            left_start + length < len(left_tokens)
            and right_start + length < len(right_tokens)
            and left_tokens[left_start + length]["value"]
            == right_tokens[right_start + length]["value"]
        ):
            length += 1

        return length

    def _is_meaningful_token_run(self, tokens, start, end):
        """Проверяет, достаточно ли совпадение большое."""

        token_count = end - start

        if token_count >= 2:
            return True

        char_length = self._token_slice_char_length(tokens, start, end)

        return char_length >= 8

    def _token_slice_char_length(self, tokens, start, end):
        """Возвращает длину диапазона токенов в символах исходного текста."""

        if not tokens or start >= end:
            return 0

        start = max(0, min(start, len(tokens) - 1))
        end = max(start + 1, min(end, len(tokens)))

        return tokens[end - 1]["end"] - tokens[start]["start"]

    def _build_sequence_groups_from_runs(
        self,
        matched_runs,
        left_tokens,
        right_tokens
    ):
        """
        Объединяет найденные совпадения в блоки.

        Два совпадения объединяются, если они идут в одинаковом порядке
        и расстояние между ними небольшое.
        """

        if not matched_runs:
            return []

        groups = []
        current_group = None

        for run in matched_runs:
            if current_group is None:
                current_group = self._create_sequence_group_from_run(run)
                continue

            if self._can_merge_run_into_group(
                group=current_group,
                run=run,
                left_tokens=left_tokens,
                right_tokens=right_tokens
            ):
                current_group["left_end"] = run["left_end"]
                current_group["right_end"] = run["right_end"]
                current_group["runs"].append(run)
            else:
                groups.append(current_group)
                current_group = self._create_sequence_group_from_run(run)

        if current_group is not None:
            groups.append(current_group)

        return groups

    def _create_sequence_group_from_run(self, run):
        """Создаёт цветной блок из одного найденного совпадения."""

        return {
            "left_start": run["left_start"],
            "left_end": run["left_end"],
            "right_start": run["right_start"],
            "right_end": run["right_end"],
            "runs": [run]
        }

    def _can_merge_run_into_group(
        self,
        group,
        run,
        left_tokens,
        right_tokens
    ):
        """Проверяет, можно ли присоединить run к текущему блоку."""

        if run["left_start"] < group["left_end"]:
            return False

        # Если в правом поле run оказался раньше, значит порядок поменялся.
        if run["right_start"] < group["right_end"]:
            return False

        left_gap = run["left_start"] - group["left_end"]
        right_gap = run["right_start"] - group["right_end"]

        max_gap_tokens = 8
        max_gap_chars = 120

        if left_gap > max_gap_tokens:
            return False

        if right_gap > max_gap_tokens:
            return False

        left_gap_chars = self._token_gap_char_length(
            tokens=left_tokens,
            start=group["left_end"],
            end=run["left_start"]
        )

        right_gap_chars = self._token_gap_char_length(
            tokens=right_tokens,
            start=group["right_end"],
            end=run["right_start"]
        )

        if left_gap_chars > max_gap_chars:
            return False

        if right_gap_chars > max_gap_chars:
            return False

        return True

    def _token_gap_char_length(self, tokens, start, end):
        """Возвращает длину промежутка между двумя токенами."""

        if not tokens or start >= end:
            return 0

        start = max(0, min(start, len(tokens) - 1))
        end = max(0, min(end, len(tokens)))

        return tokens[end - 1]["end"] - tokens[start]["start"]

    def _extend_sequence_groups_to_nearby_diffs(
        self,
        groups,
        left_tokens,
        right_tokens
    ):
        """
        Немного расширяет границы найденных блоков.

        Это нужно, чтобы небольшие добавления внутри блока считались
        отличиями внутри найденного блока, а не отдельным потерянным текстом.
        """

        if not groups:
            return []

        max_tail_tokens = 6
        max_tail_chars = 80

        extended = []

        for index, group in enumerate(groups):
            new_group = dict(group)
            new_group["runs"] = list(group["runs"])

            if index + 1 < len(groups):
                next_group = groups[index + 1]
                next_left_start = next_group["left_start"]
                next_right_start = next_group["right_start"]
            else:
                next_left_start = len(left_tokens)
                next_right_start = len(right_tokens)

            left_tail_tokens = next_left_start - new_group["left_end"]

            if 0 < left_tail_tokens <= max_tail_tokens:
                left_tail_chars = self._token_gap_char_length(
                    tokens=left_tokens,
                    start=new_group["left_end"],
                    end=next_left_start
                )

                if left_tail_chars <= max_tail_chars:
                    new_group["left_end"] = next_left_start

            right_tail_tokens = next_right_start - new_group["right_end"]

            if 0 < right_tail_tokens <= max_tail_tokens:
                right_tail_chars = self._token_gap_char_length(
                    tokens=right_tokens,
                    start=new_group["right_end"],
                    end=next_right_start
                )

                if right_tail_chars <= max_tail_chars:
                    new_group["right_end"] = next_right_start

            extended.append(new_group)

        return extended

    def _highlight_sequence_groups(
        self,
        groups,
        left_tokens,
        right_tokens,
        text1,
        text2
    ):
        """
        Подсвечивает найденные группы.

        Цветной фон показывает общий найденный блок.
        Красный фон внутри блока показывает различия.
        """

        total_diff_count = 0

        for group_index, group in enumerate(groups):
            tag_index = group_index % len(self.SEQUENCE_BLOCK_COLORS)
            tag_name = f"sequence_block_{tag_index}"

            left_range = self._get_token_slice_text_range(
                tokens=left_tokens,
                slice_start=group["left_start"],
                slice_end=group["left_end"]
            )

            right_range = self._get_token_slice_text_range(
                tokens=right_tokens,
                slice_start=group["right_start"],
                slice_end=group["right_end"]
            )

            self._add_text_tag(
                self.left_textbox,
                left_range[0],
                left_range[1],
                tag_name
            )

            self._add_text_tag(
                self.right_textbox,
                right_range[0],
                right_range[1],
                tag_name
            )

            if self.ignore_word_order_var.get():
                diff_count = self._compare_ranges_without_word_order(
                    text1=text1,
                    text2=text2,
                    left_range=left_range,
                    right_range=right_range
                )
            else:
                diff_count = self._compare_ranges_with_order(
                    text1=text1,
                    text2=text2,
                    left_range=left_range,
                    right_range=right_range
                )

            total_diff_count += diff_count

        return total_diff_count

    def _highlight_uncovered_sequence_tokens(
        self,
        groups,
        left_tokens,
        right_tokens
    ):
        """Подсвечивает красным токены, которые не попали ни в один блок."""

        left_covered = self._collect_covered_token_indexes(
            groups=groups,
            side="left"
        )

        right_covered = self._collect_covered_token_indexes(
            groups=groups,
            side="right"
        )

        left_missing_count = self._highlight_uncovered_token_runs(
            textbox=self.left_textbox,
            tokens=left_tokens,
            covered_indexes=left_covered
        )

        right_missing_count = self._highlight_uncovered_token_runs(
            textbox=self.right_textbox,
            tokens=right_tokens,
            covered_indexes=right_covered
        )

        return left_missing_count, right_missing_count

    def _collect_covered_token_indexes(self, groups, side):
        """Собирает индексы токенов, попавших в найденные блоки."""

        covered = set()

        for group in groups:
            if side == "left":
                start = group["left_start"]
                end = group["left_end"]
            else:
                start = group["right_start"]
                end = group["right_end"]

            covered.update(range(start, end))

        return covered

    def _highlight_uncovered_token_runs(
        self,
        textbox,
        tokens,
        covered_indexes
    ):
        """Подсвечивает непокрытые токены группами."""

        missing_count = 0
        run_start = None
        run_end = None

        for index, token in enumerate(tokens):
            if index in covered_indexes:
                if run_start is not None:
                    self._add_text_tag(
                        textbox,
                        run_start,
                        run_end,
                        "sequence_missing"
                    )
                    run_start = None
                    run_end = None

                continue

            missing_count += 1

            if run_start is None:
                run_start = token["start"]

            run_end = token["end"]

        if run_start is not None:
            self._add_text_tag(
                textbox,
                run_start,
                run_end,
                "sequence_missing"
            )

        return missing_count

    def _raise_diff_tags_above_blocks(self):
        """Поднимает красную подсветку выше цветных блоков."""

        for textbox in (self.left_textbox, self.right_textbox):
            try:
                textbox.tag_raise("diff")
                textbox.tag_raise("sequence_missing")
                textbox.tag_raise("sel")
            except tk.TclError:
                pass

    def _get_token_slice_text_range(self, tokens, slice_start, slice_end):
        """Превращает диапазон токенов в диапазон символов исходного текста."""

        if not tokens:
            return 0, 0

        if slice_start >= slice_end:
            return 0, 0

        slice_start = max(0, min(slice_start, len(tokens) - 1))
        slice_end = max(slice_start + 1, min(slice_end, len(tokens)))

        text_start = tokens[slice_start]["start"]
        text_end = tokens[slice_end - 1]["end"]

        return text_start, text_end

    def _compare_ranges_with_order(
        self,
        text1,
        text2,
        left_range,
        right_range
    ):
        """Сравнивает только выбранные диапазоны с учётом порядка."""

        left_start, left_end = left_range
        right_start, right_end = right_range

        normalized_1, map_1 = self._normalize_text_range_with_map(
            text=text1,
            start_char=left_start,
            end_char=left_end
        )

        normalized_2, map_2 = self._normalize_text_range_with_map(
            text=text2,
            start_char=right_start,
            end_char=right_end
        )

        matcher = difflib.SequenceMatcher(
            None,
            normalized_1,
            normalized_2,
            autojunk=False
        )

        diff_blocks_count = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                if self.show_matches_var.get():
                    self._add_tag_for_normalized_range(
                        self.left_textbox,
                        map_1,
                        i1,
                        i2,
                        "match"
                    )

                    self._add_tag_for_normalized_range(
                        self.right_textbox,
                        map_2,
                        j1,
                        j2,
                        "match"
                    )

                continue

            diff_blocks_count += 1

            if tag in ("replace", "delete"):
                self._add_tag_for_normalized_range(
                    self.left_textbox,
                    map_1,
                    i1,
                    i2,
                    "diff"
                )

            if tag in ("replace", "insert"):
                self._add_tag_for_normalized_range(
                    self.right_textbox,
                    map_2,
                    j1,
                    j2,
                    "diff"
                )

        return diff_blocks_count

    def _compare_ranges_without_word_order(
        self,
        text1,
        text2,
        left_range,
        right_range
    ):
        """Сравнивает выбранные диапазоны без учёта порядка слов."""

        left_start, left_end = left_range
        right_start, right_end = right_range

        left_substring = text1[left_start:left_end]
        right_substring = text2[right_start:right_end]

        tokens1 = self._tokenize_words_with_ranges(
            left_substring,
            offset=left_start
        )

        tokens2 = self._tokenize_words_with_ranges(
            right_substring,
            offset=right_start
        )

        return self._compare_tokens_without_word_order(
            tokens1,
            tokens2
        )

    # =========================================================
    # СРАВНЕНИЕ СОСТАВА
    # =========================================================

    def _extract_composition_text_with_offset(self, text):
        """
        Находит начало состава.

        Поддерживает:
        - СОСТАВ:
        - INGREDIENTS:
        - INCI:
        - COMPOSITION:
        - частые OCR-варианты вроде COCTAB:
        """

        if not text:
            return text, 0

        patterns = [
            r"\bсостав\s*[:：]",
            r"\bingredients?\s*[:：]",
            r"\binci\s*[:：]",
            r"\bcomposition\s*[:：]",
            r"\bcoctab\s*[:：]",
            r"\bc0ctab\s*[:：]",
            r"\bс0став\s*[:：]",
            r"\bcостав\s*[:：]",
            r"\bсoctab\s*[:：]",
        ]

        best_match = None

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            if match is None:
                continue

            if best_match is None or match.start() < best_match.start():
                best_match = match

        if best_match is None:
            return text, 0

        return text[best_match.end():], best_match.end()

    def _remove_composition_prefix_from_text(self, text):
        """Удаляет заголовок состава из фрагмента текста."""

        if not text:
            return ""

        patterns = [
            r"^\s*состав\s*[:：]\s*",
            r"^\s*ingredients?\s*[:：]\s*",
            r"^\s*inci\s*[:：]\s*",
            r"^\s*composition\s*[:：]\s*",
            r"^\s*coctab\s*[:：]\s*",
            r"^\s*c0ctab\s*[:：]\s*",
            r"^\s*с0став\s*[:：]\s*",
            r"^\s*cостав\s*[:：]\s*",
            r"^\s*сoctab\s*[:：]\s*",
        ]

        cleaned = text

        for pattern in patterns:
            cleaned = re.sub(
                pattern,
                "",
                cleaned,
                flags=re.IGNORECASE
            )

        return cleaned.strip()

    def _compare_ingredient_tokens(self, ingredients1, ingredients2):
        """Сравнивает ингредиенты как набор значений."""

        counter1 = Counter(
            ingredient["value"]
            for ingredient in ingredients1
        )

        counter2 = Counter(
            ingredient["value"]
            for ingredient in ingredients2
        )

        only_left = counter1 - counter2
        only_right = counter2 - counter1
        common = counter1 & counter2

        self._highlight_tokens_by_status(
            self.left_textbox,
            ingredients1,
            common,
            only_left
        )

        self._highlight_tokens_by_status(
            self.right_textbox,
            ingredients2,
            common,
            only_right
        )

        return only_left, only_right, common

    def compare_as_composition(self):
        """
        Сравнивает тексты как составы.

        Порядок ингредиентов не учитывается.
        Лишний текст до слова СОСТАВ не учитывается.
        """

        self.clear_highlights()

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return

        if not text1 or not text2:
            self.result_label.configure(
                text="Одно из полей пустое. Сравнение невозможно."
            )
            return

        try:
            ingredients1 = self._tokenize_ingredients_with_ranges(text1)
            ingredients2 = self._tokenize_ingredients_with_ranges(text2)

            if not ingredients1 or not ingredients2:
                self.result_label.configure(
                    text="Не удалось выделить ингредиенты для сравнения состава."
                )
                return

            only_left, only_right, common = self._compare_ingredient_tokens(
                ingredients1,
                ingredients2
            )

            diff_count = sum(only_left.values()) + sum(only_right.values())

            if diff_count == 0:
                self.result_label.configure(
                    text=(
                        "Различий в составе не найдено. "
                        "Порядок ингредиентов не учитывался."
                    )
                )
            else:
                self.result_label.configure(
                    text=(
                        f"Найдено отличающихся ингредиентов: {diff_count}. "
                        f"Только слева: {sum(only_left.values())}. "
                        f"Только справа: {sum(only_right.values())}."
                    )
                )

            logger.info(
                (
                    "Сравнение состава завершено. "
                    "left_only=%s, right_only=%s, common=%s"
                ),
                dict(only_left),
                dict(only_right),
                dict(common)
            )

        except Exception:
            logger.exception("Ошибка при сравнении состава")
            self.result_label.configure(
                text="Ошибка при сравнении состава. Подробности в app.log."
            )

    # =========================================================
    # ГЛАВНЫЙ МЕТОД СРАВНЕНИЯ
    # =========================================================

    def compare_texts(self):
        """
        Главный метод сравнения.

        Логика:
        1. Если включено "Искать похожие блоки" —
           ищем несколько последовательных блоков.
        2. Если похожие блоки выключены, но включено
           "Не учитывать порядок слов" — сравниваем весь текст как набор слов.
        3. Иначе сравниваем весь текст как последовательность символов.
        """

        self.clear_highlights()

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return

        if not text1 or not text2:
            self.result_label.configure(
                text="Одно из полей пустое. Сравнение невозможно."
            )
            return

        try:
            if self.find_similar_block_var.get():
                self._compare_by_sequence_blocks(text1, text2)

            elif self.ignore_word_order_var.get():
                self._compare_without_word_order(text1, text2)

            else:
                self._compare_with_order(text1, text2)

        except Exception:
            logger.exception("Ошибка при сравнении текстов")
            self.result_label.configure(
                text="Ошибка при сравнении текстов. Подробности в app.log."
            )

    # =========================================================
    # МЕТОДЫ ДЛЯ ПЕРЕДАЧИ ТЕКСТА ИЗ OCR/EXCEL
    # =========================================================

    def set_text_left(self, text):
        """Устанавливает текст в левое поле."""

        self.left_textbox.delete("1.0", "end")
        self.left_textbox.insert("1.0", text or "")
        self.clear_highlights()

    def set_text_right(self, text):
        """Устанавливает текст в правое поле."""

        self.right_textbox.delete("1.0", "end")
        self.right_textbox.insert("1.0", text or "")
        self.clear_highlights()


# Алиасы на случай, если в main_window.py используется другое имя класса.
CompareViewerFrame = CompareSection
CompareFrame = CompareSection