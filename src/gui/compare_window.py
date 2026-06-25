import customtkinter as ctk
import tkinter as tk
from tkinter import Menu
import difflib
import unicodedata
from collections import Counter

from src.utils.logger import logger


class CompareSection(ctk.CTkFrame):
    """
    Третий раздел приложения: сравнение двух текстов.

    Что умеет:
    1. Сравнивать два текста с подсветкой различий.
    2. Игнорировать пробелы, табы и переносы строк.
    3. Учитывать или не учитывать регистр.
    4. Игнорировать пунктуацию.
    5. Не учитывать порядок слов.
    6. Подсвечивать совпадения по желанию пользователя.
    """

    def __init__(self, master):
        super().__init__(master)

        # Главная сетка всего раздела:
        # row=0 — заголовок
        # row=1 — панель настроек сравнения
        # row=2 — два текстовых поля
        # row=3 — кнопка "Сравнить"
        # row=4 — строка результата
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Переменная, в которой хранится активное текстовое поле.
        # Нужно для контекстного меню: копировать, вставить, выделить всё.
        self.active_textbox = None

        # Создаём переменные для настроек сравнения.
        self._create_settings_variables()

        # Создаём интерфейс.
        self._create_widgets()

        # Создаём контекстное меню для текстовых полей.
        self._create_context_menu()

        # Настраиваем теги подсветки.
        self._configure_text_tags()

    # =========================================================
    # СОЗДАНИЕ ПЕРЕМЕННЫХ НАСТРОЕК
    # =========================================================

    def _create_settings_variables(self):
        """
        Создаёт BooleanVar-переменные для чекбоксов.

        Каждая такая переменная хранит True или False.
        Например:
        - True: настройка включена
        - False: настройка выключена
        """

        # По умолчанию пробелы и переносы строк игнорируются.
        # Это удобно для OCR, потому что OCR часто ломает переносы строк.
        self.ignore_whitespace_var = tk.BooleanVar(value=True)

        # По умолчанию регистр НЕ учитывается.
        # То есть AQUA и aqua будут считаться одинаковыми.
        self.case_sensitive_var = tk.BooleanVar(value=False)

        # По умолчанию пунктуация учитывается.
        # То есть PEG-40 и PEG40 будут разными, пока пользователь не включит эту настройку.
        self.ignore_punctuation_var = tk.BooleanVar(value=False)

        # По умолчанию порядок слов учитывается.
        # Если включить, программа будет сравнивать тексты как набор слов.
        self.ignore_word_order_var = tk.BooleanVar(value=False)

        # По умолчанию совпадения зелёным не подсвечиваются,
        # чтобы интерфейс не был слишком "шумным".
        self.show_matches_var = tk.BooleanVar(value=False)

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт все элементы интерфейса раздела сравнения."""

        # ---------- Заголовок ----------
        self.title_label = ctk.CTkLabel(
            self,
            text="Сравнение текстов",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="ew", pady=(10, 5))

        # ---------- Панель настроек ----------
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))

        # Делаем 3 колонки, чтобы настройки нормально переносились на 2 строки.
        for col in range(3):
            self.settings_frame.grid_columnconfigure(col, weight=1)

        # Первая строка настроек
        self.ignore_whitespace_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Игнорировать пробелы и переносы",
            variable=self.ignore_whitespace_var,
            command=self.clear_highlights
        )
        self.ignore_whitespace_checkbox.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 5))

        self.case_sensitive_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Учитывать регистр",
            variable=self.case_sensitive_var,
            command=self.clear_highlights
        )
        self.case_sensitive_checkbox.grid(row=0, column=1, sticky="w", padx=12, pady=(10, 5))

        self.ignore_punctuation_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Игнорировать пунктуацию",
            variable=self.ignore_punctuation_var,
            command=self.clear_highlights
        )
        self.ignore_punctuation_checkbox.grid(row=0, column=2, sticky="w", padx=12, pady=(10, 5))

        # Вторая строка настроек.
        # ВАЖНО: вот эта кнопка, которую тебе нужно было добавить.
        self.ignore_word_order_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Не учитывать порядок слов",
            variable=self.ignore_word_order_var,
            command=self.clear_highlights
        )
        self.ignore_word_order_checkbox.grid(row=1, column=0, sticky="w", padx=12, pady=(5, 10))

        self.show_matches_checkbox = ctk.CTkCheckBox(
            self.settings_frame,
            text="Подсвечивать совпадения",
            variable=self.show_matches_var,
            command=self.clear_highlights
        )
        self.show_matches_checkbox.grid(row=1, column=1, sticky="w", padx=12, pady=(5, 10))

        self.btn_clear_highlights = ctk.CTkButton(
            self.settings_frame,
            text="Очистить подсветку",
            command=self.clear_highlights,
            width=160
        )
        self.btn_clear_highlights.grid(row=1, column=2, sticky="e", padx=12, pady=(5, 10))

        # ---------- Контейнер для двух текстовых полей ----------
        self.texts_frame = ctk.CTkFrame(self)
        self.texts_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.texts_frame.grid_rowconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(1, weight=1)

        # Левое поле
        self.left_frame = ctk.CTkFrame(self.texts_frame)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.left_label = ctk.CTkLabel(
            self.left_frame,
            text="Текст 1",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.left_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.left_textbox = tk.Text(
            self.left_frame,
            wrap="word",
            font=("Consolas", 12),
            undo=True,
            padx=10,
            pady=10
        )
        self.left_textbox.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))

        self.left_scrollbar = ctk.CTkScrollbar(
            self.left_frame,
            command=self.left_textbox.yview
        )
        self.left_scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 10))
        self.left_textbox.configure(yscrollcommand=self.left_scrollbar.set)

        # Правое поле
        self.right_frame = ctk.CTkFrame(self.texts_frame)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.right_label = ctk.CTkLabel(
            self.right_frame,
            text="Текст 2",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.right_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.right_textbox = tk.Text(
            self.right_frame,
            wrap="word",
            font=("Consolas", 12),
            undo=True,
            padx=10,
            pady=10
        )
        self.right_textbox.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))

        self.right_scrollbar = ctk.CTkScrollbar(
            self.right_frame,
            command=self.right_textbox.yview
        )
        self.right_scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 10))
        self.right_textbox.configure(yscrollcommand=self.right_scrollbar.set)

        # ---------- Нижняя панель ----------
        self.bottom_panel = ctk.CTkFrame(self)
        self.bottom_panel.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        # Кнопка обычного сравнения
        self.btn_compare = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить",
            command=self.compare_texts,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare.pack(side="left", padx=(20, 10), pady=10, fill="x", expand=True)

        # Кнопка специального режима для составов
        self.btn_compare_composition = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить как состав",
            command=self.compare_as_composition,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare_composition.pack(side="left", padx=(10, 20), pady=10, fill="x", expand=True)

        # ---------- Строка результата ----------
        self.result_label = ctk.CTkLabel(
            self,
            text="Настройки по умолчанию: пробелы и переносы игнорируются, регистр не учитывается.",
            anchor="w"
        )
        self.result_label.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 10))

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================

    def _create_context_menu(self):
        """Создаёт контекстное меню для обоих текстовых полей."""

        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Копировать", command=self.copy_text)
        self.context_menu.add_command(label="Вставить", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выделить всё", command=self.select_all)

        # Привязываем правый клик.
        self.left_textbox.bind("<Button-3>", self.show_context_menu)
        self.right_textbox.bind("<Button-3>", self.show_context_menu)

        # Запоминаем активное поле при клике или фокусе.
        self.left_textbox.bind("<Button-1>", lambda event: self.set_active_textbox(self.left_textbox))
        self.right_textbox.bind("<Button-1>", lambda event: self.set_active_textbox(self.right_textbox))

        self.left_textbox.bind("<FocusIn>", lambda event: self.set_active_textbox(self.left_textbox))
        self.right_textbox.bind("<FocusIn>", lambda event: self.set_active_textbox(self.right_textbox))

        self.active_textbox = self.left_textbox

    def set_active_textbox(self, textbox):
        """Запоминает активное текстовое поле."""
        self.active_textbox = textbox

    def show_context_menu(self, event):
        """Показывает контекстное меню и запоминает поле, по которому кликнули."""
        self.active_textbox = event.widget
        self.context_menu.post(event.x_root, event.y_root)

    def copy_text(self):
        """Копирует выделенный текст из активного поля."""
        if self.active_textbox is None:
            return

        try:
            selected_text = self.active_textbox.get("sel.first", "sel.last")
            self.master.clipboard_clear()
            self.master.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def paste_text(self):
        """Вставляет текст из буфера обмена в активное поле."""
        if self.active_textbox is None:
            return

        try:
            clipboard_text = self.master.clipboard_get()

            try:
                self.active_textbox.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

            self.active_textbox.insert("insert", clipboard_text)
        except tk.TclError:
            pass

    def select_all(self):
        """Выделяет весь текст в активном поле."""
        if self.active_textbox is None:
            return

        self.active_textbox.focus_set()
        self.active_textbox.tag_add("sel", "1.0", "end")

    # =========================================================
    # НАСТРОЙКА ПОДСВЕТКИ
    # =========================================================

    def _configure_text_tags(self):
        """Настраивает теги для подсветки совпадений и различий."""

        for textbox in (self.left_textbox, self.right_textbox):
            # Красный — различия.
            textbox.tag_configure(
                "diff",
                foreground="red",
                background="#ffcccc"
            )

            # Зелёный — совпадения.
            textbox.tag_configure(
                "match",
                foreground="green"
            )

    def clear_highlights(self):
        """Удаляет подсветку из обоих текстовых полей."""

        for textbox in (self.left_textbox, self.right_textbox):
            textbox.tag_remove("diff", "1.0", "end")
            textbox.tag_remove("match", "1.0", "end")

        self.result_label.configure(text="Подсветка очищена.")

    # =========================================================
    # ОБЩИЕ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================

    def _is_punctuation(self, char):
        """
        Проверяет, является ли символ пунктуацией.

        unicodedata позволяет определять не только английскую пунктуацию,
        но и разные типы кавычек, тире и прочие символы.
        """
        return unicodedata.category(char).startswith("P")

    def _add_text_tag(self, textbox, start_char, end_char, tag_name):
        """
        Добавляет тег к диапазону символов в tk.Text.

        start_char и end_char — это позиции в обычной Python-строке.
        Tkinter понимает формат "1.0+Nc", где N — количество символов
        от начала текста.
        """

        if start_char is None or end_char is None:
            return

        if start_char >= end_char:
            return

        start_index = f"1.0+{start_char}c"
        end_index = f"1.0+{end_char}c"

        textbox.tag_add(tag_name, start_index, end_index)

    # =========================================================
    # ОБЫЧНОЕ СРАВНЕНИЕ С УЧЁТОМ НАСТРОЕК
    # =========================================================

    def _normalize_text_with_map(self, text):
        """
        Создаёт нормализованную строку и карту индексов.

        Зачем нужна карта:
        мы сравниваем очищенный текст, например:
            "A Q U A" -> "aqua"

        Но подсвечивать нужно исходный текст:
            "A Q U A"

        Поэтому map хранит связь:
            индекс символа в очищенном тексте -> индекс символа в исходном тексте
        """

        normalized_chars = []
        index_map = []

        ignore_whitespace = self.ignore_whitespace_var.get()
        case_sensitive = self.case_sensitive_var.get()
        ignore_punctuation = self.ignore_punctuation_var.get()

        for original_index, char in enumerate(text):
            # Игнорируем пробелы, табы и переносы строк.
            if ignore_whitespace and char.isspace():
                continue

            # Игнорируем пунктуацию.
            if ignore_punctuation and self._is_punctuation(char):
                continue

            # Если регистр не учитывается, приводим символ к нижнему регистру.
            if not case_sensitive:
                char = char.lower()

            normalized_chars.append(char)
            index_map.append(original_index)

        normalized_text = "".join(normalized_chars)

        return normalized_text, index_map

    def _add_tag_for_normalized_range(self, textbox, index_map, norm_start, norm_end, tag_name):
        """
        Подсвечивает диапазон из нормализованного текста в исходном tk.Text.

        Важно:
        если пробелы игнорировались, мы НЕ подсвечиваем сами пробелы.
        Поэтому подсветка добавляется по символам/непрерывным группам,
        которые реально участвовали в сравнении.
        """

        if norm_start >= norm_end:
            return

        if not index_map:
            return

        original_positions = index_map[norm_start:norm_end]

        if not original_positions:
            return

        # Группируем соседние символы в непрерывные диапазоны.
        range_start = original_positions[0]
        previous_pos = original_positions[0]

        for pos in original_positions[1:]:
            if pos == previous_pos + 1:
                previous_pos = pos
            else:
                self._add_text_tag(textbox, range_start, previous_pos + 1, tag_name)
                range_start = pos
                previous_pos = pos

        self._add_text_tag(textbox, range_start, previous_pos + 1, tag_name)

    def _compare_with_order(self, text1, text2):
        """
        Обычный режим сравнения.

        Здесь порядок символов важен.
        Но перед сравнением применяются настройки:
        - игнорировать пробелы;
        - учитывать/не учитывать регистр;
        - игнорировать пунктуацию.
        """

        normalized_1, map_1 = self._normalize_text_with_map(text1)
        normalized_2, map_2 = self._normalize_text_with_map(text2)

        matcher = difflib.SequenceMatcher(None, normalized_1, normalized_2)

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

            elif tag in ("replace", "delete", "insert"):
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

        logger.info("Сравнение с учётом порядка завершено. Блоков различий: %s", diff_blocks_count)

    # =========================================================
    # СРАВНЕНИЕ БЕЗ УЧЁТА ПОРЯДКА СЛОВ
    # =========================================================

    def _tokenize_words_with_ranges(self, text):
        """
        Разбивает текст на слова и запоминает позиции этих слов в исходном тексте.

        Возвращает список вида:
        [
            {"value": "aqua", "start": 0, "end": 4},
            {"value": "pvp", "start": 6, "end": 9}
        ]

        value — слово для сравнения.
        start/end — позиции слова в исходной строке для подсветки.
        """

        tokens = []

        current_chars = []
        current_start = None
        current_end = None

        case_sensitive = self.case_sensitive_var.get()
        ignore_punctuation = self.ignore_punctuation_var.get()

        def flush_token():
            """
            Сохраняет накопленное слово в список tokens.
            Вызывается, когда встретился разделитель: пробел, запятая и т.д.
            """
            nonlocal current_chars, current_start, current_end

            if not current_chars:
                return

            token_value = "".join(current_chars)

            if not case_sensitive:
                token_value = token_value.lower()

            tokens.append({
                "value": token_value,
                "start": current_start,
                "end": current_end
            })

            current_chars = []
            current_start = None
            current_end = None

        for index, char in enumerate(text):
            # Пробелы, табы и переносы строк всегда разделяют слова.
            if char.isspace():
                flush_token()
                continue

            # Пунктуация требует отдельной логики.
            if self._is_punctuation(char):
                # Слэш и дефис часто являются частью названий ингредиентов:
                # VP/VA, PEG-40, CI-77491.
                if char in ("/", "-"):
                    if ignore_punctuation:
                        # Если пунктуацию игнорируем, то VP/VA станет VPVA,
                        # PEG-40 станет PEG40.
                        continue

                    # Если пунктуацию не игнорируем, оставляем / и - внутри слова.
                    if current_start is None:
                        current_start = index

                    current_chars.append(char)
                    current_end = index + 1
                    continue

                # Остальная пунктуация, например запятая, точка, скобки,
                # считается разделителем слов.
                flush_token()
                continue

            # Обычный символ слова.
            if current_start is None:
                current_start = index

            current_chars.append(char)
            current_end = index + 1

        # Сохраняем последнее слово, если текст не закончился разделителем.
        flush_token()

        return tokens

    def _highlight_tokens_by_status(self, textbox, tokens, common_counts, diff_counts):
        """
        Подсвечивает слова без наложения зелёной и красной подсветки.

        Одно конкретное вхождение слова может быть только:
        - либо совпадением;
        - либо отличием;
        - либо вообще не подсвечиваться.

        Это исправляет ситуацию, когда слово одновременно подсвечивалось
        зелёным и красным.
        """

        remaining_common = Counter(common_counts)
        remaining_diff = Counter(diff_counts)

        for token in tokens:
            value = token["value"]

            # Сначала проверяем, является ли это конкретное вхождение совпадением.
            if remaining_common[value] > 0:
                if self.show_matches_var.get():
                    self._add_text_tag(
                        textbox,
                        token["start"],
                        token["end"],
                        "match"
                    )

                remaining_common[value] -= 1
                continue

            # Если совпадающие вхождения этого слова уже закончились,
            # проверяем, не является ли это лишним/отличающимся словом.
            if remaining_diff[value] > 0:
                self._add_text_tag(
                    textbox,
                    token["start"],
                    token["end"],
                    "diff"
                )

                remaining_diff[value] -= 1

    def _compare_without_word_order(self, text1, text2):
        """
        Сравнивает тексты как наборы слов без учёта порядка.

        Пример:
            Текст 1: AQUA, PVP, GLYCERIN
            Текст 2: GLYCERIN, AQUA, PVP

        При включённом режиме "Не учитывать порядок слов"
        эти тексты считаются одинаковыми.
        """

        tokens1 = self._tokenize_words_with_ranges(text1)
        tokens2 = self._tokenize_words_with_ranges(text2)

        values1 = [token["value"] for token in tokens1]
        values2 = [token["value"] for token in tokens2]

        counter1 = Counter(values1)
        counter2 = Counter(values2)

        # Слова, которые есть слева, но отсутствуют справа.
        only_left = counter1 - counter2

        # Слова, которые есть справа, но отсутствуют слева.
        only_right = counter2 - counter1

        # Слова, которые есть в обоих текстах.
        common = counter1 & counter2

        # ВАЖНО:
        # теперь подсветка делается одним проходом,
        # поэтому одно слово не может стать и зелёным, и красным.
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

        if diff_words_count == 0:
            self.result_label.configure(
                text="Различий не найдено. Порядок слов не учитывался."
            )
        else:
            self.result_label.configure(
                text=f"Найдено отличающихся слов: {diff_words_count}. Порядок слов не учитывался."
            )

        logger.info(
            "Сравнение без учёта порядка слов завершено. only_left=%s, only_right=%s",
            dict(only_left),
            dict(only_right)
        )
    # =========================================================
    # СРАВНЕНИЕ КАК СОСТАВ ПО ЗАПЯТЫМ
    # =========================================================

    def _normalize_ingredient_for_compare(self, ingredient):
        """
        Нормализует один ингредиент для сравнения.

        Пример:
            " Propylene   Glycol " -> "propylene glycol"

        Здесь мы:
        - убираем лишние пробелы по краям;
        - схлопываем несколько пробелов/переносов в один пробел;
        - применяем настройку регистра;
        - при необходимости игнорируем пунктуацию.
        """

        # Убираем пробелы по краям
        ingredient = ingredient.strip()

        # Схлопываем все пробелы, табы и переносы внутри ингредиента
        ingredient = " ".join(ingredient.split())

        # Если включена настройка "Игнорировать пунктуацию",
        # удаляем пунктуационные символы.
        if self.ignore_punctuation_var.get():
            ingredient = "".join(
                char for char in ingredient
                if not self._is_punctuation(char)
            )

            # После удаления пунктуации снова чистим пробелы
            ingredient = " ".join(ingredient.split())

        # Если регистр не учитывается, приводим к нижнему регистру
        if not self.case_sensitive_var.get():
            ingredient = ingredient.lower()

        return ingredient


    def _remove_composition_prefix(self, text, start_index):
        """
        Убирает служебный префикс перед первым ингредиентом.

        Например:
            "СОСТАВ: AQUA" -> "AQUA"
            "INGREDIENTS: Aqua" -> "Aqua"
            "INCI: Aqua" -> "Aqua"

        start_index нужен, чтобы правильно подсветить ингредиент
        в исходном tk.Text.
        """

        stripped_left = len(text) - len(text.lstrip())
        text_lstripped = text.lstrip()
        current_start = start_index + stripped_left

        # Если в первом фрагменте есть двоеточие,
        # считаем всё до двоеточия заголовком состава.
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

            # Убираем префикс только если он похож на заголовок состава
            if prefix in known_prefixes:
                after_colon = text_lstripped[colon_pos + 1:]
                spaces_after_colon = len(after_colon) - len(after_colon.lstrip())

                new_text = after_colon.lstrip()
                new_start = current_start + colon_pos + 1 + spaces_after_colon

                return new_text, new_start

        return text, start_index


    def _tokenize_ingredients_with_ranges(self, text):
        """
        Разбивает текст состава на ингредиенты по запятым.

        Возвращает список словарей:
        [
            {
                "value": "propylene glycol",
                "display": "PROPYLENE GLYCOL",
                "start": 20,
                "end": 36
            }
        ]

        value — нормализованное значение для сравнения.
        display — исходный текст ингредиента.
        start/end — позиции ингредиента в исходном тексте для подсветки.
        """

        ingredients = []

        part_start = 0
        parts = text.split(",")

        for part_index, raw_part in enumerate(parts):
            # Находим реальную позицию этого фрагмента в исходном тексте.
            # part_start — индекс начала фрагмента между запятыми.
            original_start = part_start
            original_end = part_start + len(raw_part)

            # Убираем пробелы слева и справа, но корректируем координаты.
            left_spaces = len(raw_part) - len(raw_part.lstrip())
            right_spaces = len(raw_part) - len(raw_part.rstrip())

            clean_start = original_start + left_spaces
            clean_end = original_end - right_spaces

            clean_text = raw_part.strip()

            # Для первого элемента убираем "СОСТАВ:", "INGREDIENTS:" и т.д.
            if part_index == 0:
                clean_text, clean_start = self._remove_composition_prefix(
                    clean_text,
                    clean_start
                )
                clean_text = clean_text.strip()

                # После удаления префикса ещё раз пересчитываем правую границу
                clean_end = clean_start + len(clean_text)

            # Если после очистки ничего не осталось — пропускаем.
            if not clean_text:
                part_start += len(raw_part) + 1
                continue

            normalized_value = self._normalize_ingredient_for_compare(clean_text)

            if not normalized_value:
                part_start += len(raw_part) + 1
                continue

            ingredients.append({
                "value": normalized_value,
                "display": clean_text,
                "start": clean_start,
                "end": clean_end
            })

            # +1 — это запятая, которую split убрал
            part_start += len(raw_part) + 1

        return ingredients


    def _highlight_ingredients_by_status(self, textbox, ingredients, common_counts, diff_counts):
        """
        Подсвечивает ингредиенты без наложения зелёного и красного.

        Один конкретный ингредиент может быть только:
        - совпадением;
        - отличием;
        - не подсвечиваться.
        """

        remaining_common = Counter(common_counts)
        remaining_diff = Counter(diff_counts)

        for ingredient in ingredients:
            value = ingredient["value"]

            # Сначала помечаем совпадения
            if remaining_common[value] > 0:
                if self.show_matches_var.get():
                    self._add_text_tag(
                        textbox,
                        ingredient["start"],
                        ingredient["end"],
                        "match"
                    )

                remaining_common[value] -= 1
                continue

            # Потом помечаем отличия
            if remaining_diff[value] > 0:
                self._add_text_tag(
                    textbox,
                    ingredient["start"],
                    ingredient["end"],
                    "diff"
                )

                remaining_diff[value] -= 1


    def compare_as_composition(self):
        """
        Сравнивает два текста как состав.

        Главное отличие от режима "Не учитывать порядок слов":
        здесь элемент сравнения — не слово, а ингредиент целиком.

        Пример:
            "PROPYLENE GLYCOL" считается одним ингредиентом,
            а не двумя словами.
        """

        self.clear_highlights()

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return

        if not text1 or not text2:
            self.result_label.configure(text="Одно из полей пустое. Сравнение невозможно.")
            return

        try:
            ingredients1 = self._tokenize_ingredients_with_ranges(text1)
            ingredients2 = self._tokenize_ingredients_with_ranges(text2)

            values1 = [item["value"] for item in ingredients1]
            values2 = [item["value"] for item in ingredients2]

            counter1 = Counter(values1)
            counter2 = Counter(values2)

            # Ингредиенты, которые есть слева, но отсутствуют справа
            only_left = counter1 - counter2

            # Ингредиенты, которые есть справа, но отсутствуют слева
            only_right = counter2 - counter1

            # Ингредиенты, которые есть в обоих составах
            common = counter1 & counter2

            self._highlight_ingredients_by_status(
                self.left_textbox,
                ingredients1,
                common,
                only_left
            )

            self._highlight_ingredients_by_status(
                self.right_textbox,
                ingredients2,
                common,
                only_right
            )

            diff_count = sum(only_left.values()) + sum(only_right.values())

            if diff_count == 0:
                self.result_label.configure(
                    text="Различий не найдено. Сравнение выполнено как состав по ингредиентам."
                )
            else:
                self.result_label.configure(
                    text=(
                        f"Найдено отличающихся ингредиентов: {diff_count}. "
                        f"Сравнение выполнено как состав по запятым."
                    )
                )

            logger.info(
                "Сравнение как состав завершено. only_left=%s, only_right=%s",
                dict(only_left),
                dict(only_right)
            )

        except Exception:
            logger.exception("Ошибка при сравнении как состав")
            self.result_label.configure(
                text="Ошибка при сравнении как состав. Подробности в app.log."
            )
    # =========================================================
    # ГЛАВНЫЙ МЕТОД СРАВНЕНИЯ
    # =========================================================

    def compare_texts(self):
        """
        Главный метод сравнения.

        Он выбирает режим:
        1. Если включено "Не учитывать порядок слов" —
           сравниваем как набор слов.
        2. Иначе сравниваем как последовательность символов
           с учётом выбранных настроек.
        """

        self.clear_highlights()

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return

        if not text1 or not text2:
            self.result_label.configure(text="Одно из полей пустое. Сравнение невозможно.")
            return

        try:
            if self.ignore_word_order_var.get():
                self._compare_without_word_order(text1, text2)
            else:
                self._compare_with_order(text1, text2)

        except Exception:
            logger.exception("Ошибка при сравнении текстов")
            self.result_label.configure(text="Ошибка при сравнении текстов. Подробности в app.log.")

    # =========================================================
    # МЕТОДЫ ДЛЯ ПЕРЕДАЧИ ТЕКСТА ИЗ OCR/EXCEL
    # =========================================================

    def set_text_left(self, text):
        """
        Устанавливает текст в левое поле.

        Этот метод вызывается из ocr_window.py и excel_window.py.
        """
        self.left_textbox.delete("1.0", "end")
        self.left_textbox.insert("1.0", text)
        self.clear_highlights()

    def set_text_right(self, text):
        """
        Устанавливает текст в правое поле.

        Этот метод вызывается из ocr_window.py и excel_window.py.
        """
        self.right_textbox.delete("1.0", "end")
        self.right_textbox.insert("1.0", text)
        self.clear_highlights()