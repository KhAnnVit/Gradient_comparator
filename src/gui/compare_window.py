import customtkinter as ctk
import tkinter as tk
from tkinter import Menu

from src.models.compare_models import CompareSettings, CompareResult
from src.services.compare_service import CompareService
from src.utils.logger import logger


class CompareSection(ctk.CTkFrame):
    """
    Третий раздел приложения: сравнение двух текстов.

    Теперь этот класс отвечает только за GUI:
    - поля ввода;
    - кнопки;
    - чекбоксы;
    - контекстное меню;
    - подсветку результата.

    Вся логика сравнения находится в CompareService.
    """

    def __init__(self, master):
        super().__init__(master)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.active_textbox = None

        # Сервис сравнения.
        self.compare_service = CompareService()

        self._create_settings_variables()
        self._create_widgets()
        self._create_context_menu()
        self._configure_text_tags()

    # =========================================================
    # НАСТРОЙКИ
    # =========================================================

    def _create_settings_variables(self):
        """Создаёт BooleanVar-переменные для чекбоксов."""

        self.ignore_whitespace_var = tk.BooleanVar(value=True)
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.ignore_punctuation_var = tk.BooleanVar(value=False)
        self.ignore_word_order_var = tk.BooleanVar(value=False)
        self.show_matches_var = tk.BooleanVar(value=False)

    def _get_compare_settings(self) -> CompareSettings:
        """
        Собирает настройки из чекбоксов и возвращает CompareSettings.
        """

        return CompareSettings(
            ignore_whitespace=self.ignore_whitespace_var.get(),
            case_sensitive=self.case_sensitive_var.get(),
            ignore_punctuation=self.ignore_punctuation_var.get(),
            ignore_word_order=self.ignore_word_order_var.get(),
            show_matches=self.show_matches_var.get()
        )

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт все элементы интерфейса."""

        self.title_label = ctk.CTkLabel(
            self,
            text="Сравнение текстов",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="ew", pady=(10, 5))

        # ---------- Панель настроек ----------
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))

        for col in range(3):
            self.settings_frame.grid_columnconfigure(col, weight=1)

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

        # ---------- Поля текста ----------
        self.texts_frame = ctk.CTkFrame(self)
        self.texts_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.texts_frame.grid_rowconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(0, weight=1)
        self.texts_frame.grid_columnconfigure(1, weight=1)

        self._create_left_textbox()
        self._create_right_textbox()

        # ---------- Нижняя панель ----------
        self.bottom_panel = ctk.CTkFrame(self)
        self.bottom_panel.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.btn_compare = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить",
            command=self.compare_texts,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare.pack(side="left", padx=(20, 10), pady=10, fill="x", expand=True)

        self.btn_compare_composition = ctk.CTkButton(
            self.bottom_panel,
            text="Сравнить как состав",
            command=self.compare_as_composition,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.btn_compare_composition.pack(side="left", padx=(10, 20), pady=10, fill="x", expand=True)

        self.result_label = ctk.CTkLabel(
            self,
            text="Настройки по умолчанию: пробелы и переносы игнорируются, регистр не учитывается.",
            anchor="w"
        )
        self.result_label.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 10))

    def _create_left_textbox(self):
        """Создаёт левое текстовое поле."""

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

    def _create_right_textbox(self):
        """Создаёт правое текстовое поле."""

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

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================

    def _create_context_menu(self):
        """Создаёт контекстное меню."""

        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Копировать", command=self.copy_text)
        self.context_menu.add_command(label="Вставить", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выделить всё", command=self.select_all)

        self.left_textbox.bind("<Button-3>", self.show_context_menu)
        self.right_textbox.bind("<Button-3>", self.show_context_menu)

        self.left_textbox.bind("<Button-1>", lambda event: self.set_active_textbox(self.left_textbox))
        self.right_textbox.bind("<Button-1>", lambda event: self.set_active_textbox(self.right_textbox))

        self.left_textbox.bind("<FocusIn>", lambda event: self.set_active_textbox(self.left_textbox))
        self.right_textbox.bind("<FocusIn>", lambda event: self.set_active_textbox(self.right_textbox))

        self.active_textbox = self.left_textbox

    def set_active_textbox(self, textbox):
        """Запоминает активное поле."""
        self.active_textbox = textbox

    def show_context_menu(self, event):
        """Показывает контекстное меню."""
        self.active_textbox = event.widget
        self.context_menu.post(event.x_root, event.y_root)

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
        except tk.TclError:
            pass

    def select_all(self):
        """Выделяет весь текст в активном поле."""
        if self.active_textbox is None:
            return

        self.active_textbox.focus_set()
        self.active_textbox.tag_add("sel", "1.0", "end")

    # =========================================================
    # ПОДСВЕТКА
    # =========================================================

    def _configure_text_tags(self):
        """Настраивает теги подсветки."""

        for textbox in (self.left_textbox, self.right_textbox):
            textbox.tag_configure(
                "diff",
                foreground="red",
                background="#ffcccc"
            )

            textbox.tag_configure(
                "match",
                foreground="green"
            )

    def clear_highlights(self):
        """Очищает подсветку."""

        for textbox in (self.left_textbox, self.right_textbox):
            textbox.tag_remove("diff", "1.0", "end")
            textbox.tag_remove("match", "1.0", "end")

        self.result_label.configure(text="Подсветка очищена.")

    def _add_text_tag(self, textbox, start_char, end_char, tag_name):
        """Добавляет тег подсветки в tk.Text."""

        if start_char is None or end_char is None:
            return

        if start_char >= end_char:
            return

        textbox.tag_add(
            tag_name,
            f"1.0+{start_char}c",
            f"1.0+{end_char}c"
        )

    def _apply_compare_result(self, result: CompareResult):
        """
        Применяет CompareResult к интерфейсу:
        - ставит подсветку;
        - обновляет строку результата.
        """

        for highlight in result.ranges:
            if highlight.side == "left":
                textbox = self.left_textbox
            elif highlight.side == "right":
                textbox = self.right_textbox
            else:
                continue

            self._add_text_tag(
                textbox=textbox,
                start_char=highlight.start,
                end_char=highlight.end,
                tag_name=highlight.tag
            )

        self.result_label.configure(text=result.message)

    # =========================================================
    # СРАВНЕНИЕ
    # =========================================================

    def _get_texts(self):
        """Возвращает тексты из двух полей."""

        text1 = self.left_textbox.get("1.0", "end-1c")
        text2 = self.right_textbox.get("1.0", "end-1c")

        return text1, text2

    def _validate_texts(self, text1, text2) -> bool:
        """Проверяет, можно ли сравнивать тексты."""

        if not text1 and not text2:
            self.result_label.configure(text="Оба поля пустые.")
            return False

        if not text1 or not text2:
            self.result_label.configure(text="Одно из полей пустое. Сравнение невозможно.")
            return False

        return True

    def compare_texts(self):
        """Запускает обычное сравнение."""

        self.clear_highlights()

        text1, text2 = self._get_texts()

        if not self._validate_texts(text1, text2):
            return

        try:
            settings = self._get_compare_settings()

            result = self.compare_service.compare_texts(
                text1=text1,
                text2=text2,
                settings=settings
            )

            self._apply_compare_result(result)

        except Exception:
            logger.exception("Ошибка при сравнении текстов")
            self.result_label.configure(
                text="Ошибка при сравнении текстов. Подробности в app.log."
            )

    def compare_as_composition(self):
        """Запускает сравнение как состав."""

        self.clear_highlights()

        text1, text2 = self._get_texts()

        if not self._validate_texts(text1, text2):
            return

        try:
            settings = self._get_compare_settings()

            result = self.compare_service.compare_as_composition(
                text1=text1,
                text2=text2,
                settings=settings
            )

            self._apply_compare_result(result)

        except Exception:
            logger.exception("Ошибка при сравнении как состав")
            self.result_label.configure(
                text="Ошибка при сравнении как состав. Подробности в app.log."
            )

    # =========================================================
    # МЕТОДЫ ДЛЯ ПЕРЕДАЧИ ТЕКСТА ИЗ OCR/EXCEL
    # =========================================================

    def set_text_left(self, text):
        """Устанавливает текст в левое поле."""

        self.left_textbox.delete("1.0", "end")
        self.left_textbox.insert("1.0", text)
        self.clear_highlights()

    def set_text_right(self, text):
        """Устанавливает текст в правое поле."""

        self.right_textbox.delete("1.0", "end")
        self.right_textbox.insert("1.0", text)
        self.clear_highlights()