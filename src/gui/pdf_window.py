import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, Menu, messagebox

from PIL import Image, ImageTk
from pdf2image import convert_from_path

from config import POPPLER_PATH, OCR_LANGUAGES
from src.models.ocr_models import OCRSettings
from src.models.image_crop_models import ImageCropRequest
from src.services.ocr_service import OCRService
from src.services.image_crop_service import ImageCropService
from src.utils.logger import logger



class PDFViewerFrame(ctk.CTkFrame):
    """
    Первый раздел приложения: просмотр PDF.

    Что умеет:
    - загружать PDF;
    - показывать первую страницу;
    - двигать изображение;
    - масштабировать изображение;
    - поворачивать изображение;
    - выделять область;
    - вырезать выделенную область;
    - отправлять выделенную область в OCR.
    """

    MIN_ZOOM = 0.2
    MAX_ZOOM = 5.0
    ZOOM_STEP = 1.1

    PDF_DPI = 300

    DEFAULT_OCR_MODE = "Обычный"

    OCR_MODE_MAP = {
        "Обычный": "default",
        "Мелкий текст": "small_text",
        "Блок текста": "block",
        "Состав": "composition",
        "Без обработки": "raw",
    }

    MODE_PAN = "Перемещение"
    MODE_SELECT = "Выделение"

    def __init__(self, master):
        super().__init__(master)

        self.ocr_service = OCRService()
        self.image_crop_service = ImageCropService()

        self._init_state()
        self._configure_grid()
        self._create_widgets()
        self._bind_events()

    # =========================================================
    # ИНИЦИАЛИЗАЦИЯ
    # =========================================================

    def _init_state(self):
        """
        Создаёт состояние PDF-раздела.
        """

        self.pdf_path = None

        # Изображения:
        # original_image — страница PDF без поворота и зума;
        # rotated_image — страница после поворота;
        # current_image — страница после поворота и зума;
        # tk_image — изображение для Canvas.
        self.original_image = None
        self.rotated_image = None
        self.current_image = None
        self.tk_image = None

        self.zoom_factor = 1.0
        self.angle = 0

        self.offset_x = 0
        self.offset_y = 0

        self.last_mouse_x = 0
        self.last_mouse_y = 0

        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

        self.ocr_mode_var = tk.StringVar(value=self.DEFAULT_OCR_MODE)

    def _configure_grid(self):
        """Настраивает сетку PDF-раздела."""

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт интерфейс PDF-раздела."""

        self._create_top_panel()
        self._create_canvas()
        self._create_status_label()
        self._create_context_menu()

    def _create_top_panel(self):
        """Создаёт верхнюю панель управления."""

        self.top_panel = ctk.CTkFrame(self, height=40)
        self.top_panel.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.btn_load = ctk.CTkButton(
            self.top_panel,
            text="Загрузить PDF",
            command=self.load_pdf,
            width=130
        )
        self.btn_load.pack(side="left", padx=5, pady=5)

        self.btn_rotate = ctk.CTkButton(
            self.top_panel,
            text="Повернуть 90°",
            command=self.rotate_image,
            width=130
        )
        self.btn_rotate.pack(side="left", padx=5, pady=5)

        self.btn_reset = ctk.CTkButton(
            self.top_panel,
            text="Сбросить вид",
            command=self.reset_view,
            width=120
        )
        self.btn_reset.pack(side="left", padx=5, pady=5)

        self.btn_clear_selection = ctk.CTkButton(
            self.top_panel,
            text="Убрать выделение",
            command=self.clear_selection,
            width=140
        )
        self.btn_clear_selection.pack(side="left", padx=5, pady=5)

        self.mode_switch = ctk.CTkSegmentedButton(
            self.top_panel,
            values=[self.MODE_PAN, self.MODE_SELECT],
            width=220
        )
        self.mode_switch.pack(side="left", padx=20, pady=5)
        self.mode_switch.set(self.MODE_SELECT)

        self.ocr_mode_label = ctk.CTkLabel(
            self.top_panel,
            text="OCR:"
        )
        self.ocr_mode_label.pack(side="left", padx=(10, 5), pady=5)

        self.ocr_mode_menu = ctk.CTkOptionMenu(
            self.top_panel,
            values=list(self.OCR_MODE_MAP.keys()),
            variable=self.ocr_mode_var,
            width=150
        )
        self.ocr_mode_menu.pack(side="left", padx=5, pady=5)

    def _create_canvas(self):
        """Создаёт Canvas для отображения PDF."""

        self.canvas = tk.Canvas(
            self,
            bg="#2b2b2b",
            highlightthickness=0
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _create_status_label(self):
        """Создаёт нижнюю строку статуса."""

        self.status_label = ctk.CTkLabel(
            self,
            text="Загрузите PDF для начала работы.",
            anchor="w"
        )
        self.status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

    def _create_context_menu(self):
        """Создаёт контекстное меню для выделенной области."""

        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Распознать текст",
            command=self.send_to_ocr
        )

    # =========================================================
    # СОБЫТИЯ
    # =========================================================

    def _bind_events(self):
        """Привязывает события Canvas."""

        self.canvas.bind("<MouseWheel>", self.zoom_image)

        # Linux-варианты колёсика.
        self.canvas.bind("<Button-4>", self.zoom_image)
        self.canvas.bind("<Button-5>", self.zoom_image)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    # =========================================================
    # СТАТУС И СБРОСЫ
    # =========================================================

    def set_status(self, text):
        """Обновляет строку статуса."""

        self.status_label.configure(text=text)

    def clear_selection(self):
        """Удаляет рамку выделения."""

        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
            self.set_status("Выделение очищено.")

    def reset_view(self):
        """
        Сбрасывает вид PDF:
        - масштаб;
        - поворот;
        - смещение;
        - выделение.
        """

        if self.original_image is None:
            return

        self._reset_view_state()
        self.clear_selection()
        self.update_image()
        self.set_status("Вид сброшен.")

    def _reset_view_state(self):
        """Сбрасывает параметры просмотра."""

        self.zoom_factor = 1.0
        self.angle = 0
        self.offset_x = 0
        self.offset_y = 0

    def _reset_selection_state(self):
        """Сбрасывает данные выделения без обращения к Canvas."""

        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

    # =========================================================
    # ЗАГРУЗКА PDF
    # =========================================================

    def load_pdf(self):
        """Открывает PDF и загружает первую страницу."""

        file_path = filedialog.askopenfilename(
            title="Выберите PDF-файл",
            filetypes=[("PDF Files", "*.pdf")]
        )

        if not file_path:
            return

        try:
            self.set_status("Загрузка PDF...")
            self.update_idletasks()

            logger.info("Загрузка PDF: %s", file_path)

            pages = self._convert_pdf_to_images(file_path)

            if not pages:
                self._handle_empty_pdf()
                return

            self._set_loaded_pdf(
                file_path=file_path,
                first_page=pages[0]
            )

            logger.info(
                "PDF успешно загружен. Размер первой страницы: %sx%s",
                self.original_image.width,
                self.original_image.height
            )

        except Exception:
            logger.exception("Ошибка при загрузке PDF")
            messagebox.showerror(
                "Ошибка загрузки PDF",
                "Не удалось загрузить PDF. Проверьте файл и путь к Poppler."
            )
            self.set_status("Ошибка загрузки PDF.")

    def _convert_pdf_to_images(self, file_path):
        """Конвертирует PDF в список PIL-изображений."""

        return convert_from_path(
            file_path,
            dpi=self.PDF_DPI,
            poppler_path=str(POPPLER_PATH)
        )

    def _handle_empty_pdf(self):
        """Показывает предупреждение, если PDF не дал страниц."""

        messagebox.showwarning(
            "PDF не загружен",
            "Не удалось получить страницы из PDF-файла."
        )
        self.set_status("PDF не загружен.")
        logger.warning("PDF не загружен: список страниц пуст")

    def _set_loaded_pdf(self, file_path, first_page):
        """
        Сохраняет новый PDF в состояние раздела
        и обновляет интерфейс.
        """

        self.pdf_path = file_path
        self.original_image = first_page

        self._save_pdf_path_to_state(file_path)

        self._reset_view_state()
        self._reset_selection_state()

        self.update_image()
        self.set_status(f"PDF загружен: {file_path}")

    def _save_pdf_path_to_state(self, file_path):
        """Сохраняет путь к PDF через AppController."""

        if hasattr(self.master, "controller"):
            self.master.controller.set_current_pdf(file_path)

    # =========================================================
    # ОТРИСОВКА ИЗОБРАЖЕНИЯ
    # =========================================================

    def update_image(self):
        """
        Перерисовывает PDF на Canvas.

        Здесь выполняется:
        - поворот;
        - масштабирование;
        - создание PhotoImage;
        - размещение изображения в центре Canvas с учётом смещения.
        """

        if self.original_image is None:
            return

        self._prepare_display_image()
        self._draw_current_image_on_canvas()

        # После полной перерисовки старое выделение может стать некорректным.
        self.rect_id = None

    def _prepare_display_image(self):
        """Готовит изображение для отображения на Canvas."""

        self.rotated_image = self.original_image.rotate(
            self.angle,
            expand=True
        )

        new_width = max(1, int(self.rotated_image.width * self.zoom_factor))
        new_height = max(1, int(self.rotated_image.height * self.zoom_factor))

        self.current_image = self.rotated_image.resize(
            (new_width, new_height),
            resample=Image.Resampling.LANCZOS
        )

        self.tk_image = ImageTk.PhotoImage(self.current_image)

    def _draw_current_image_on_canvas(self):
        """Рисует текущее изображение на Canvas."""

        self.canvas.delete("all")

        center_x, center_y = self._get_image_center_on_canvas()

        self.canvas.create_image(
            center_x,
            center_y,
            anchor="center",
            image=self.tk_image,
            tags="image"
        )

    def _get_image_center_on_canvas(self):
        """Возвращает центр изображения на Canvas с учётом смещения."""

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())

        center_x = canvas_w // 2 + self.offset_x
        center_y = canvas_h // 2 + self.offset_y

        return center_x, center_y

    def on_canvas_resize(self, event=None):
        """Перерисовывает изображение при изменении размера Canvas."""

        if self.original_image is not None:
            self.update_image()

    # =========================================================
    # ПОВОРОТ И МАСШТАБ
    # =========================================================

    def rotate_image(self):
        """Поворачивает изображение на 90 градусов против часовой стрелки."""

        if self.original_image is None:
            return

        self.angle = (self.angle - 90) % 360

        self.clear_selection()
        self.update_image()
        self.set_status(f"Поворот: {self.angle}°")

    def zoom_image(self, event):
        """Масштабирует изображение колёсиком мыши."""

        if self.original_image is None:
            return

        old_zoom = self.zoom_factor
        self.zoom_factor = self._calculate_new_zoom(event)

        if self.zoom_factor != old_zoom:
            self.clear_selection()
            self.update_image()
            self.set_status(f"Масштаб: {int(self.zoom_factor * 100)}%")

    def _calculate_new_zoom(self, event):
        """Считает новый масштаб по событию колёсика мыши."""

        new_zoom = self.zoom_factor

        if hasattr(event, "delta") and event.delta:
            if event.delta > 0:
                new_zoom *= self.ZOOM_STEP
            else:
                new_zoom /= self.ZOOM_STEP

        elif hasattr(event, "num"):
            if event.num == 4:
                new_zoom *= self.ZOOM_STEP
            elif event.num == 5:
                new_zoom /= self.ZOOM_STEP

        return max(self.MIN_ZOOM, min(new_zoom, self.MAX_ZOOM))

    # =========================================================
    # МЫШЬ: ПЕРЕМЕЩЕНИЕ И ВЫДЕЛЕНИЕ
    # =========================================================

    def on_mouse_press(self, event):
        """Обрабатывает нажатие левой кнопки мыши."""

        if self.original_image is None:
            return

        current_mode = self.mode_switch.get()

        if current_mode == self.MODE_PAN:
            self._start_pan(event)

        elif current_mode == self.MODE_SELECT:
            self._start_selection(event)

    def _start_pan(self, event):
        """Запоминает стартовую точку перемещения."""

        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def _start_selection(self, event):
        """Начинает выделение области."""

        self.clear_selection()

        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        self.rect_id = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline="red",
            width=2,
            dash=(4, 4),
            tags="selection"
        )

    def on_mouse_drag(self, event):
        """Обрабатывает движение мыши с зажатой левой кнопкой."""

        if self.original_image is None:
            return

        current_mode = self.mode_switch.get()

        if current_mode == self.MODE_PAN:
            self._drag_pan(event)

        elif current_mode == self.MODE_SELECT:
            self._drag_selection(event)

    def _drag_pan(self, event):
        """Перемещает изображение по Canvas."""

        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y

        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

        self.offset_x += dx
        self.offset_y += dy

        self.canvas.move("all", dx, dy)

    def _drag_selection(self, event):
        """Изменяет размер рамки выделения."""

        if self.rect_id is None:
            return

        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)

        self.canvas.coords(
            self.rect_id,
            self.start_x,
            self.start_y,
            current_x,
            current_y
        )

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================

    def show_context_menu(self, event):
        """
        Показывает контекстное меню, если правый клик был внутри выделения.
        """

        if not self._is_click_inside_selection(event):
            return

        try:
            self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            logger.exception("Ошибка при открытии контекстного меню PDF")

    def _is_click_inside_selection(self, event) -> bool:
        """Проверяет, находится ли правый клик внутри рамки выделения."""

        if self.rect_id is None:
            return False

        try:
            x1, y1, x2, y2 = self.canvas.coords(self.rect_id)
        except Exception:
            logger.exception("Ошибка при получении координат выделения")
            return False

        click_x = self.canvas.canvasx(event.x)
        click_y = self.canvas.canvasy(event.y)

        min_x, max_x = sorted([x1, x2])
        min_y, max_y = sorted([y1, y2])

        return (
            min_x <= click_x <= max_x and
            min_y <= click_y <= max_y
        )

    # =========================================================
    # ВЫРЕЗАНИЕ ОБЛАСТИ
    # =========================================================

    def get_cropped_image(self):
        """
        Вырезает выделенную область из текущего PDF-изображения.

        GUI-класс только собирает данные из Canvas и текущего состояния.
        Сама математика crop находится в ImageCropService.
        """

        if not self._can_crop():
            return None

        try:
            selection_coords = tuple(self.canvas.coords(self.rect_id))

            request = ImageCropRequest(
                source_image=self.rotated_image,
                selection_coords=selection_coords,
                canvas_width=max(1, self.canvas.winfo_width()),
                canvas_height=max(1, self.canvas.winfo_height()),
                displayed_image_width=self.current_image.width,
                displayed_image_height=self.current_image.height,
                offset_x=self.offset_x,
                offset_y=self.offset_y,
                zoom_factor=self.zoom_factor,
                angle=self.angle,
                restore_original_orientation=True
            )

            result = self.image_crop_service.crop_from_canvas_selection(request)

            if not result.success:
                logger.warning(
                    "Не удалось вырезать PDF-область: %s",
                    result.error_message
                )
                return None

            logger.info(
                "PDF-область вырезана. crop_box=%s, image_size=%s",
                result.crop_box,
                result.image.size if result.image else None
            )

            return result.image

        except Exception:
            logger.exception("Ошибка при подготовке данных для crop PDF")
            return None

    def _can_crop(self) -> bool:
        """
        Проверяет, есть ли всё необходимое для вырезания области.
        """

        return (
                self.rect_id is not None
                and self.original_image is not None
                and self.current_image is not None
                and self.rotated_image is not None
        )

    # =========================================================
    # OCR
    # =========================================================

    def get_selected_ocr_mode(self):
        """
        Возвращает внутренний OCR-режим.

        Например:
            "Мелкий текст" -> "small_text"
        """

        visible_mode = self.ocr_mode_var.get()
        return self.OCR_MODE_MAP.get(visible_mode, "default")

    def send_to_ocr(self):
        """
        Вырезает выделенную область, запускает OCR
        и отправляет результат в OCR-раздел через AppController.
        """

        cropped_image = self.get_cropped_image()

        if cropped_image is None:
            messagebox.showwarning(
                "Нет области",
                "Не удалось вырезать область. Проверьте, что выделение находится на изображении."
            )
            logger.warning("OCR не запущен: не удалось вырезать выделенную область")
            return

        selected_mode = self.get_selected_ocr_mode()
        visible_mode = self.ocr_mode_var.get()

        try:
            self._set_wait_cursor(True)

            result = self._recognize_cropped_image(
                cropped_image=cropped_image,
                selected_mode=selected_mode,
                visible_mode=visible_mode
            )

            if not result.success:
                self._handle_ocr_error(result, visible_mode)
                return

            self._send_ocr_result_to_controller(
                cropped_image=cropped_image,
                recognized_text=result.text,
                selected_mode=selected_mode
            )

            logger.info(
                "OCR успешно завершён. mode=%s, text_length=%s",
                selected_mode,
                len(result.text)
            )

        except Exception:
            logger.exception("Ошибка при OCR из PDF")
            messagebox.showerror(
                "Ошибка OCR",
                "Произошла ошибка во время распознавания текста. Подробности в app.log."
            )

        finally:
            self._set_wait_cursor(False)

    def _recognize_cropped_image(self, cropped_image, selected_mode, visible_mode):
        """Запускает OCRService для выделенной области."""

        logger.info(
            "Запущено OCR из PDF. mode=%s, visible_mode=%s, image_size=%s",
            selected_mode,
            visible_mode,
            cropped_image.size
        )

        return self.ocr_service.recognize_from_pil(
            pil_image=cropped_image,
            settings=OCRSettings(
                mode=selected_mode,
                languages=OCR_LANGUAGES
            )
        )

    def _handle_ocr_error(self, result, visible_mode):
        """Обрабатывает ошибку OCR."""

        logger.error(
            "OCR завершился ошибкой. mode=%s, error=%s",
            result.mode,
            result.error_message
        )

        messagebox.showerror(
            "Ошибка OCR",
            (
                "Не удалось распознать текст.\n\n"
                f"Режим: {visible_mode}\n"
                f"Ошибка: {result.error_message}"
            )
        )

    def _send_ocr_result_to_controller(self, cropped_image, recognized_text, selected_mode):
        """Передаёт OCR-результат в AppController."""

        if not hasattr(self.master, "controller"):
            logger.warning("AppController не найден. OCR-результат не отправлен.")
            messagebox.showerror(
                "Ошибка",
                "Не удалось отправить результат OCR: контроллер приложения не найден."
            )
            return

        self.master.controller.show_ocr_result(
            image=cropped_image,
            text=recognized_text,
            source=f"pdf_selection:{selected_mode}"
        )

    def _set_wait_cursor(self, enabled: bool):
        """Включает или выключает курсор ожидания."""

        if enabled:
            self.configure(cursor="watch")
            self.update_idletasks()
        else:
            self.configure(cursor="")