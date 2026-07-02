import customtkinter as ctk
import tkinter as tk

from src.gui.pdf_window import PDFViewerFrame
from src.gui.ocr_window import OCRViewerFrame
from src.gui.compare_window import CompareSection
from src.gui.excel_window import ExcelViewerFrame

# Новые импорты
from src.app_state import AppState
from src.app_controller import AppController


# Базовые настройки интерфейса
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """
    Главное окно приложения.

    Здесь создаются:
    - боковое меню;
    - все разделы приложения;
    - общее состояние AppState;
    - контроллер AppController.
    """

    def __init__(self):
        super().__init__()

        self.title("СверкаМакетов")
        self._set_initial_window_geometry()

        # =====================================================
        # STATE + CONTROLLER
        # =====================================================

        # AppState хранит общие данные приложения:
        # OCR-текст, текст для сравнения, текущий PDF, Excel и т.д.
        self.app_state = AppState()
        # AppController управляет переходами между разделами
        # и передачей данных между окнами.
        self.controller = AppController(self, self.app_state)

        # =====================================================
        # НАСТРОЙКА ОСНОВНОЙ СЕТКИ
        # =====================================================

        # row=0 занимает всё окно по высоте
        self.grid_rowconfigure(0, weight=1)

        # column=0 — боковое меню
        # column=1 — основной контент
        self.grid_columnconfigure(1, weight=1)

        # =====================================================
        # БОКОВАЯ ПАНЕЛЬ НАВИГАЦИИ
        # =====================================================

        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        # Пустая строка снизу будет растягиваться,
        # чтобы меню не расползалось.
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Меню",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # ВАЖНО:
        # Теперь кнопки навигации обращаются не напрямую к select_frame,
        # а через controller.go_to_tab().
        # Так контроллер тоже знает, какая вкладка активна.
        self.btn_tab1 = ctk.CTkButton(
            self.sidebar_frame,
            text="1. Просмотр PDF",
            command=lambda: self.controller.go_to_tab("tab1")
        )
        self.btn_tab1.grid(row=1, column=0, padx=20, pady=10)

        self.btn_tab2 = ctk.CTkButton(
            self.sidebar_frame,
            text="2. Распознавание",
            command=lambda: self.controller.go_to_tab("tab2")
        )
        self.btn_tab2.grid(row=2, column=0, padx=20, pady=10)

        self.btn_tab3 = ctk.CTkButton(
            self.sidebar_frame,
            text="3. Сравнение",
            command=lambda: self.controller.go_to_tab("tab3")
        )
        self.btn_tab3.grid(row=3, column=0, padx=20, pady=10)

        self.btn_tab4 = ctk.CTkButton(
            self.sidebar_frame,
            text="4. Просмотр Excel",
            command=lambda: self.controller.go_to_tab("tab4")
        )
        self.btn_tab4.grid(row=4, column=0, padx=20, pady=10)

        # =====================================================
        # ФРЕЙМЫ / РАЗДЕЛЫ ПРИЛОЖЕНИЯ
        # =====================================================

        self.frames = {}

        # Пока передаём только self, чтобы не ломать старые классы.
        # На следующих шагах будем переводить окна на controller/state.
        self.frames["tab1"] = PDFViewerFrame(self)
        self.frames["tab2"] = OCRViewerFrame(self)
        self.frames["tab3"] = CompareSection(self)
        self.frames["tab4"] = ExcelViewerFrame(self)

        # =====================================================
        # ГЛОБАЛЬНЫЕ ГОРЯЧИЕ КЛАВИШИ
        # =====================================================

        # Важно:
        # не используем <Control-c>, <Control-v>, <Control-a>,
        # потому что на русской раскладке символы другие.
        # Вместо этого ловим Ctrl + физическую клавишу через event.keycode.
        self.bind_all("<Control-KeyPress>", self._global_ctrl_keypress, add="+")

        # Открываем первый раздел по умолчанию.
        self.controller.go_to_tab("tab1")

    def _set_initial_window_geometry(self):
        """
        Задаёт стартовый размер окна и размещает его по центру экрана.

        Это нужно, чтобы окно не появлялось каждый раз в случайном месте
        и не выходило за пределы видимого экрана.
        """

        window_width = 1280
        window_height = 820

        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Если экран маленький, уменьшаем стартовый размер окна,
        # чтобы оно точно помещалось на экране.
        window_width = min(window_width, screen_width - 80)
        window_height = min(window_height, screen_height - 100)

        x = max(0, int((screen_width - window_width) / 2))
        y = max(0, int((screen_height - window_height) / 2))

        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(1000, 650)

    # =========================================================
    # НАВИГАЦИЯ
    # =========================================================

    def select_frame(self, name):
        """
        Показывает нужный раздел приложения.

        Этот метод вызывается контроллером.
        Также он оставлен для совместимости со старым кодом,
        потому что другие окна пока ещё вызывают:
            self.master.select_frame(...)
        """

        if name not in self.frames:
            return

        # Сохраняем активную вкладку в AppState.
        self.app_state.current_tab = name

        # Скрываем все разделы.
        for frame in self.frames.values():
            frame.grid_forget()

        # Показываем нужный раздел.
        self.frames[name].grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=10,
            pady=10
        )

    # =========================================================
    # ГЛОБАЛЬНЫЕ ГОРЯЧИЕ КЛАВИШИ
    # =========================================================

    def _global_ctrl_keypress(self, event=None):
        """
        Единый обработчик Ctrl+клавиша.

        Используем keycode, а не символ клавиши.
        Поэтому Ctrl+C / Ctrl+V / Ctrl+A работают и на русской,
        и на английской раскладке.

        Windows keycode:
            A = 65
            C = 67
            V = 86
            X = 88
            Z = 90
        """

        if event is None:
            return

        keycode = event.keycode

        if keycode == 67:
            return self._global_copy(event)

        if keycode == 86:
            return self._global_paste(event)

        if keycode == 88:
            return self._global_cut(event)

        if keycode == 65:
            return self._global_select_all(event)

        if keycode == 90:
            return self._global_undo(event)

    def _get_focused_text_widget(self):
        """
        Возвращает активный текстовый виджет.

        Поддерживает:
        - tk.Text
        - tk.Entry
        - внутренние Text/Entry виджеты CustomTkinter
        """

        widget = self.focus_get()

        if widget is None:
            return None

        widget_class = widget.winfo_class()

        if isinstance(widget, (tk.Text, tk.Entry)):
            return widget

        if widget_class in {"Text", "Entry", "TEntry"}:
            return widget

        return None

    def _global_copy(self, event=None):
        """
        Глобальный Ctrl+C для текстовых полей.
        Работает на русской и английской раскладке.
        """

        widget = self._get_focused_text_widget()

        if widget is None:
            return

        try:
            selected_text = widget.selection_get()
        except tk.TclError:
            return "break"

        self.clipboard_clear()
        self.clipboard_append(selected_text)

        return "break"

    def _global_paste(self, event=None):
        """
        Глобальный Ctrl+V для текстовых полей.
        Работает на русской и английской раскладке.
        """

        widget = self._get_focused_text_widget()

        if widget is None:
            return

        try:
            clipboard_text = self.clipboard_get()
        except tk.TclError:
            return "break"

        try:
            if isinstance(widget, tk.Text) or widget.winfo_class() == "Text":
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass

                widget.insert("insert", clipboard_text)
                return "break"

            if isinstance(widget, tk.Entry) or widget.winfo_class() in {"Entry", "TEntry"}:
                try:
                    if widget.selection_present():
                        widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass

                widget.insert("insert", clipboard_text)
                return "break"

        except tk.TclError:
            return "break"

    def _global_cut(self, event=None):
        """
        Глобальный Ctrl+X для текстовых полей.
        """

        widget = self._get_focused_text_widget()

        if widget is None:
            return

        try:
            selected_text = widget.selection_get()
        except tk.TclError:
            return "break"

        self.clipboard_clear()
        self.clipboard_append(selected_text)

        try:
            if isinstance(widget, tk.Text) or widget.winfo_class() == "Text":
                widget.delete("sel.first", "sel.last")
                return "break"

            if isinstance(widget, tk.Entry) or widget.winfo_class() in {"Entry", "TEntry"}:
                widget.delete("sel.first", "sel.last")
                return "break"

        except tk.TclError:
            return "break"

    def _global_select_all(self, event=None):
        """
        Глобальный Ctrl+A для текстовых полей.
        Работает на русской и английской раскладке.
        """

        widget = self._get_focused_text_widget()

        if widget is None:
            return

        try:
            if isinstance(widget, tk.Text) or widget.winfo_class() == "Text":
                widget.tag_add("sel", "1.0", "end")
                widget.mark_set("insert", "1.0")
                widget.see("insert")
                return "break"

            if isinstance(widget, tk.Entry) or widget.winfo_class() in {"Entry", "TEntry"}:
                widget.select_range(0, "end")
                widget.icursor("end")
                return "break"

        except tk.TclError:
            return "break"

    def _global_undo(self, event=None):
        """
        Глобальный Ctrl+Z.

        Для tk.Text и tk.Entry пробуем вызвать стандартное событие Undo.
        Если undo не поддерживается, просто ничего не делаем.
        """

        widget = self._get_focused_text_widget()

        if widget is None:
            return

        try:
            widget.event_generate("<<Undo>>")
            return "break"
        except tk.TclError:
            return "break"