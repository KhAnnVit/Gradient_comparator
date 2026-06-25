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

        self.title("PDF & Excel Data Reconciliator")
        self.geometry("1200x750")

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

        self.bind_all("<Control-c>", self._global_copy)
        self.bind_all("<Control-v>", self._global_paste)
        self.bind_all("<Control-a>", self._global_select_all)

        # Открываем первый раздел по умолчанию.
        self.controller.go_to_tab("tab1")

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
    # ГЛОБАЛЬНОЕ КОПИРОВАНИЕ
    # =========================================================

    def _global_copy(self, event=None):
        """
        Глобальный Ctrl+C для tk.Text и CTkTextbox.
        """

        widget = self.focus_get()

        if not widget:
            return

        if isinstance(widget, (tk.Text, ctk.CTkTextbox)):
            try:
                selected_text = widget.get("sel.first", "sel.last")
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                return "break"
            except tk.TclError:
                pass

    # =========================================================
    # ГЛОБАЛЬНАЯ ВСТАВКА
    # =========================================================

    def _global_paste(self, event=None):
        """
        Глобальный Ctrl+V для tk.Text и CTkTextbox.
        """

        widget = self.focus_get()

        if not widget:
            return

        if isinstance(widget, (tk.Text, ctk.CTkTextbox)):
            try:
                clipboard_text = self.clipboard_get()

                # Если есть выделение — удаляем его перед вставкой.
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass

                widget.insert("insert", clipboard_text)
                return "break"

            except tk.TclError:
                pass

    # =========================================================
    # ГЛОБАЛЬНОЕ ВЫДЕЛЕНИЕ ВСЕГО
    # =========================================================

    def _global_select_all(self, event=None):
        """
        Глобальный Ctrl+A для текстовых полей.
        """

        widget = self.focus_get()

        if not widget:
            return

        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end")
            return "break"

        if isinstance(widget, ctk.CTkTextbox):
            try:
                widget.tag_add("sel", "1.0", "end")
                return "break"
            except tk.TclError:
                pass