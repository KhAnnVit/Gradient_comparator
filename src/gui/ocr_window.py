import customtkinter as ctk
import tkinter as tk
from tkinter import Menu, messagebox

from PIL import Image

from src.utils.logger import logger


class OCRViewerFrame(ctk.CTkFrame):
    """
    Второй раздел приложения: просмотр результата OCR.

    Что делает:
    - показывает вырезанный фрагмент изображения;
    - показывает распознанный текст;
    - позволяет отправить весь текст в поле сравнения;
    - позволяет отправить выделенный фрагмент текста в поле сравнения.
    """

    PREVIEW_MAX_HEIGHT = 130
    DEFAULT_TEXT = "Здесь появится распознанный текст...\n"
    DEFAULT_IMAGE_TEXT = "Здесь появится вырезанный фрагмент"

    def __init__(self, master):
        super().__init__(master)

        self.current_image = None
        self.current_ctk_image = None
        self.current_text = ""

        self._configure_grid()
        self._create_widgets()
        self._create_context_menu()
        self._bind_events()

    # =========================================================
    # ИНИЦИАЛИЗАЦИЯ
    # =========================================================

    def _configure_grid(self):
        """Настраивает сетку OCR-раздела."""

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт все элементы интерфейса."""

        self._create_image_panel()
        self._create_textbox()
        self._create_bottom_panel()

    def _create_image_panel(self):
        """Создаёт верхнюю панель с превью изображения."""

        self.image_panel = ctk.CTkFrame(self, height=150)
        self.image_panel.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=10,
            pady=(10, 5)
        )

        # Не даём фрейму сжиматься по содержимому.
        self.image_panel.pack_propagate(False)

        self.lbl_image = ctk.CTkLabel(
            self.image_panel,
            text=self.DEFAULT_IMAGE_TEXT
        )
        self.lbl_image.pack(expand=True)

    def _create_textbox(self):
        """Создаёт поле с распознанным текстом."""

        self.textbox = ctk.CTkTextbox(
            self,
            wrap="word",
            font=ctk.CTkFont(size=14)
        )
        self.textbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=5
        )

        self._set_text(self.DEFAULT_TEXT)

    def _create_bottom_panel(self):
        """Создаёт нижнюю панель с кнопками переноса текста."""

        self.bottom_panel = ctk.CTkFrame(self)
        self.bottom_panel.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=10,
            pady=(5, 10)
        )

        self.bottom_panel.grid_columnconfigure((0, 1), weight=1)

        self.btn_send_1 = ctk.CTkButton(
            self.bottom_panel,
            text="Перенести полностью в Поле 1",
            command=lambda: self.send_full_text(1)
        )
        self.btn_send_1.grid(
            row=0,
            column=0,
            padx=5,
            pady=10,
            sticky="ew"
        )

        self.btn_send_2 = ctk.CTkButton(
            self.bottom_panel,
            text="Перенести полностью в Поле 2",
            command=lambda: self.send_full_text(2)
        )
        self.btn_send_2.grid(
            row=0,
            column=1,
            padx=5,
            pady=10,
            sticky="ew"
        )

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================

    def _create_context_menu(self):
        """Создаёт контекстное меню для текстового поля."""

        self.context_menu = Menu(self, tearoff=0)

        self.context_menu.add_command(
            label="Перенести выделенное в Поле 1",
            command=lambda: self.send_selection(1)
        )

        self.context_menu.add_command(
            label="Перенести выделенное в Поле 2",
            command=lambda: self.send_selection(2)
        )

    def _bind_events(self):
        """Привязывает события OCR-раздела."""

        self.textbox.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """
        Показывает контекстное меню только если есть выделенный текст.
        """

        if not self._has_selected_text():
            return

        try:
            self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            logger.exception("Ошибка при открытии контекстного меню OCR")

    def _has_selected_text(self) -> bool:
        """Проверяет, есть ли выделение в текстовом поле."""

        try:
            return bool(self.textbox.tag_ranges("sel"))
        except tk.TclError:
            return False

    # =========================================================
    # ОБНОВЛЕНИЕ СОДЕРЖИМОГО
    # =========================================================

    def update_content(self, pil_image, text):
        """
        Обновляет OCR-раздел после распознавания.

        Этот метод вызывается через AppController.
        """

        self.current_image = pil_image
        self.current_text = text or ""

        self._show_image(pil_image)
        self._set_text(self.current_text)

        logger.info(
            "OCR-раздел обновлён. text_length=%s",
            len(self.current_text)
        )

    def _show_image(self, pil_image):
        """
        Показывает превью вырезанного изображения.
        """

        if pil_image is None:
            self.lbl_image.configure(
                image=None,
                text=self.DEFAULT_IMAGE_TEXT
            )
            self.current_ctk_image = None
            return

        try:
            preview_image = self._prepare_preview_image(pil_image)

            ctk_image = ctk.CTkImage(
                light_image=preview_image,
                dark_image=preview_image,
                size=(preview_image.width, preview_image.height)
            )

            self.lbl_image.configure(
                image=ctk_image,
                text=""
            )

            # Важно сохранить ссылку, иначе изображение может исчезнуть.
            self.current_ctk_image = ctk_image
            self.lbl_image.image = ctk_image

        except Exception:
            logger.exception("Ошибка при отображении OCR-изображения")
            self.lbl_image.configure(
                image=None,
                text="Не удалось показать изображение"
            )
            self.current_ctk_image = None

    def _prepare_preview_image(self, pil_image):
        """
        Подготавливает изображение для превью.

        Если изображение слишком высокое — уменьшаем его
        до PREVIEW_MAX_HEIGHT, сохраняя пропорции.
        """

        preview_image = pil_image.copy()

        if preview_image.height > self.PREVIEW_MAX_HEIGHT:
            ratio = self.PREVIEW_MAX_HEIGHT / preview_image.height
            new_width = int(preview_image.width * ratio)

            preview_image = preview_image.resize(
                (new_width, self.PREVIEW_MAX_HEIGHT),
                Image.Resampling.LANCZOS
            )

        return preview_image

    def _set_text(self, text):
        """Устанавливает текст в OCR-поле."""

        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text or "")

    def _get_full_text(self) -> str:
        """Возвращает весь текст из OCR-поля."""

        return self.textbox.get("1.0", "end-1c").strip()

    def _get_selected_text(self) -> str:
        """Возвращает выделенный текст из OCR-поля."""

        try:
            return self.textbox.get("sel.first", "sel.last").strip()
        except tk.TclError:
            return ""

    # =========================================================
    # ОТПРАВКА ТЕКСТА В СРАВНЕНИЕ
    # =========================================================

    def send_selection(self, field_num):
        """
        Отправляет выделенный фрагмент OCR-текста в поле сравнения.
        """

        selected_text = self._get_selected_text()

        if not selected_text:
            messagebox.showwarning(
                "Текст не выделен",
                "Сначала выделите текст для переноса."
            )
            logger.warning("Попытка отправить невыделенный OCR-текст")
            return

        self._send_text_to_compare(
            text=selected_text,
            field_num=field_num
        )

    def send_full_text(self, field_num):
        """
        Отправляет весь OCR-текст в поле сравнения.

        field_num:
            1 — левое поле сравнения
            2 — правое поле сравнения
        """

        full_text = self._get_full_text()

        if not full_text:
            messagebox.showwarning(
                "OCR-текст пуст",
                "Нет текста для переноса в сравнение."
            )
            logger.warning("Попытка отправить пустой OCR-текст")
            return

        self._send_text_to_compare(
            text=full_text,
            field_num=field_num
        )

    def _send_text_to_compare(self, text, field_num):
        """
        Отправляет текст в Compare-раздел через AppController.
        """

        if not hasattr(self.master, "controller"):
            logger.warning("AppController не найден. OCR-текст не отправлен.")
            messagebox.showerror(
                "Ошибка",
                "Не удалось отправить текст: контроллер приложения не найден."
            )
            return

        self.master.controller.send_text_to_compare(
            text=text,
            field_num=field_num,
            source="ocr"
        )

        logger.info(
            "OCR-текст отправлен в поле сравнения %s. Длина: %s",
            field_num,
            len(text)
        )