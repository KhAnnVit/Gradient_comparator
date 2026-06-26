import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, Menu, messagebox

from PIL import Image, ImageTk

from config import POPPLER_PATH, OCR_LANGUAGES
from src.models.ocr_models import OCRSettings
from src.models.image_crop_models import ImageCropRequest
from src.models.pdf_models import PDFLoadSettings
from src.services.ocr_service import OCRService
from src.services.image_crop_service import ImageCropService
from src.services.pdf_service import PDFService
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

    MIN_ZOOM = 0.05
    MAX_ZOOM = 5.0
    ZOOM_STEP = 1.05

    ZOOM_REDRAW_DELAY_MS = 16
    ZOOM_FINAL_REDRAW_DELAY_MS = 180

    FAST_ZOOM_RESAMPLE = Image.Resampling.BILINEAR
    QUALITY_RESAMPLE = Image.Resampling.LANCZOS

    DISPLAY_PDF_DPI = 150
    OCR_PDF_DPI = 300

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
        self.pdf_service = PDFService()

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
        self.current_page_index = 0
        self.page_count = 0

        # Изображения:
        # original_image — страница PDF без поворота и зума;
        # rotated_image — страница после поворота;
        # current_image — страница после поворота и зума;
        # tk_image — изображение для Canvas.
        self.original_image = None  # лёгкая картинка для просмотра
        self.ocr_source_image = None  # большая картинка для OCR

        self.rotated_image = None
        self.current_image = None
        self.tk_image = None

        self.zoom_factor = 1.0
        self.angle = 0

        self.zoom_redraw_after_id = None
        self.zoom_final_redraw_after_id = None

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

        self.btn_prev_page = ctk.CTkButton(
            self.top_panel,
            text="◀",
            command=self.go_to_previous_page,
            width=40,
            state="disabled"
        )
        self.btn_prev_page.pack(side="left", padx=(10, 3), pady=5)

        self.page_label = ctk.CTkLabel(
            self.top_panel,
            text="Стр. - / -",
            width=90
        )
        self.page_label.pack(side="left", padx=3, pady=5)

        self.btn_next_page = ctk.CTkButton(
            self.top_panel,
            text="▶",
            command=self.go_to_next_page,
            width=40,
            state="disabled"
        )
        self.btn_next_page.pack(side="left", padx=(3, 10), pady=5)

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

        self._reset_view_state(fit_to_page=True)
        self.clear_selection()
        self.update_image()
        self.set_status("Вид сброшен.")

    def _reset_view_state(self, fit_to_page: bool = False):
        """
        Сбрасывает параметры просмотра.

        fit_to_page=True:
            страница будет вписана целиком в Canvas.

        fit_to_page=False:
            масштаб будет 100%.
        """

        self.angle = 0
        self.offset_x = 0
        self.offset_y = 0

        if fit_to_page:
            self._fit_page_to_canvas()
        else:
            self.zoom_factor = 1.0

    def _reset_selection_state(self):
        """Сбрасывает данные выделения без обращения к Canvas."""

        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

    def _fit_page_to_canvas(self):
        """
        Подбирает zoom_factor так, чтобы вся страница PDF
        помещалась в Canvas.
        """

        if self.original_image is None:
            return

        # Canvas может ещё не успеть получить реальные размеры,
        # поэтому сначала просим Tkinter обновить геометрию.
        self.update_idletasks()

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())

        # Небольшой отступ, чтобы страница не прилипала к краям.
        padding = 20

        available_width = max(1, canvas_width - padding * 2)
        available_height = max(1, canvas_height - padding * 2)

        # Учитываем текущий угол поворота.
        preview_image = self.original_image.rotate(
            self.angle,
            expand=True
        )

        width_ratio = available_width / preview_image.width
        height_ratio = available_height / preview_image.height

        fit_zoom = min(width_ratio, height_ratio)

        self.zoom_factor = max(
            self.MIN_ZOOM,
            min(fit_zoom, self.MAX_ZOOM)
        )

        logger.info(
            "PDF масштабирован по размеру окна. zoom=%s, canvas=%sx%s, image=%sx%s",
            round(self.zoom_factor, 3),
            canvas_width,
            canvas_height,
            preview_image.width,
            preview_image.height
        )

    # =========================================================
    # ЗАГРУЗКА PDF
    # =========================================================

    def load_pdf(self):
        """
        Открывает PDF и загружает первую страницу.
        """

        file_path = filedialog.askopenfilename(
            title="Выберите PDF-файл",
            filetypes=[("PDF Files", "*.pdf")]
        )

        if not file_path:
            return

        self.load_pdf_page(
            file_path=file_path,
            page_index=0,
            is_new_file=True
        )

    def load_pdf_page(self, file_path=None, page_index=None, is_new_file=False):
        """
        Загружает конкретную страницу PDF.

        file_path:
            путь к PDF. Если None — используется текущий self.pdf_path.

        page_index:
            номер страницы 0-based.
        """

        if file_path is None:
            file_path = self.pdf_path

        if file_path is None:
            return

        if page_index is None:
            page_index = self.current_page_index

        try:
            self.set_status("Загрузка страницы PDF...")
            self.update_idletasks()

            display_result = self._load_pdf_page_with_service(
                file_path=file_path,
                page_index=page_index,
                dpi=self.DISPLAY_PDF_DPI
            )

            if not display_result.success:
                self._handle_pdf_load_error(display_result.error_message)
                return

            ocr_result = self._load_pdf_page_with_service(
                file_path=file_path,
                page_index=page_index,
                dpi=self.OCR_PDF_DPI
            )

            if not ocr_result.success:
                logger.warning(
                    "Не удалось загрузить OCR-версию страницы PDF. Используется display-версия. error=%s",
                    ocr_result.error_message
                )
                ocr_page_image = display_result.page_image
            else:
                ocr_page_image = ocr_result.page_image

            self._set_loaded_pdf_page(
                file_path=display_result.pdf_path,
                page_image=display_result.page_image,
                ocr_page_image=ocr_page_image,
                page_number=display_result.page_number,
                page_count=display_result.page_count,
                is_new_file=is_new_file
            )

            logger.info(
                "PDF-страница загружена в интерфейс. path=%s, page=%s/%s, display_size=%sx%s, ocr_size=%sx%s",
                display_result.pdf_path,
                display_result.page_number + 1,
                display_result.page_count,
                display_result.page_image.width,
                display_result.page_image.height,
                ocr_page_image.width,
                ocr_page_image.height
            )

        except Exception:
            logger.exception("Ошибка при загрузке PDF-страницы в интерфейсе")

            messagebox.showerror(
                "Ошибка загрузки PDF",
                "Не удалось загрузить страницу PDF. Подробности в app.log."
            )

            self.set_status("Ошибка загрузки PDF.")

    def _load_pdf_page_with_service(self, file_path, page_index, dpi):
        """
        Загружает страницу PDF через PDFService в указанном DPI.
        """

        settings = PDFLoadSettings(
            dpi=dpi,
            poppler_path=POPPLER_PATH
        )

        return self.pdf_service.load_page(
            pdf_path=file_path,
            page_number=page_index,
            settings=settings
        )

    def _handle_pdf_load_error(self, error_message):
        """
        Показывает ошибку загрузки PDF.
        """

        logger.warning("PDF не загружен: %s", error_message)

        messagebox.showerror(
            "Ошибка загрузки PDF",
            f"Не удалось загрузить PDF.\n\n{error_message}"
        )

        self.set_status("PDF не загружен.")

    def _set_loaded_pdf_page(
            self,
            file_path,
            page_image,
            ocr_page_image,
            page_number,
            page_count,
            is_new_file=False
    ):
        """
        Сохраняет загруженную страницу PDF
        и обновляет интерфейс.
        """

        self.pdf_path = file_path

        # Лёгкая версия страницы используется для просмотра и зума.
        self.original_image = page_image

        # Большая версия страницы используется для OCR-crop.
        self.ocr_source_image = ocr_page_image

        self.current_page_index = page_number
        self.page_count = page_count

        if is_new_file:
            self._save_pdf_path_to_state(file_path)

        self._save_pdf_page_to_state(page_number)

        self._reset_view_state(fit_to_page=True)
        self._reset_selection_state()

        self.update_image()
        self._update_page_controls()

        self.set_status(
            f"PDF загружен: страница {page_number + 1} из {page_count}"
        )

        logger.info(
            "Состояние PDF-страниц обновлено. current_page=%s, page_count=%s",
            self.current_page_index,
            self.page_count
        )

    def _save_pdf_path_to_state(self, file_path):
        """
        Сохраняет путь к PDF через AppController.
        """

        if hasattr(self.master, "controller"):
            self.master.controller.set_current_pdf(file_path)

    def _save_pdf_page_to_state(self, page_number):
        """
        Сохраняет текущую страницу PDF через AppController.
        """

        if (
                hasattr(self.master, "controller")
                and hasattr(self.master.controller, "set_current_pdf_page")
        ):
            self.master.controller.set_current_pdf_page(page_number)

    def _update_page_controls(self):
        """
        Обновляет кнопки и подпись текущей страницы.
        """

        if self.page_count <= 0:
            self.page_label.configure(text="Стр. - / -")
            self.btn_prev_page.configure(state="disabled")
            self.btn_next_page.configure(state="disabled")
            return

        self.page_label.configure(
            text=f"Стр. {self.current_page_index + 1} / {self.page_count}"
        )

        prev_state = "normal" if self.current_page_index > 0 else "disabled"
        next_state = "normal" if self.current_page_index < self.page_count - 1 else "disabled"

        self.btn_prev_page.configure(state=prev_state)
        self.btn_next_page.configure(state=next_state)

        logger.info(
            "Кнопки страниц обновлены. current=%s, total=%s, prev=%s, next=%s",
            self.current_page_index,
            self.page_count,
            prev_state,
            next_state
        )

    def go_to_previous_page(self):
        """
        Загружает предыдущую страницу PDF.
        """

        if self.current_page_index <= 0:
            return

        self.load_pdf_page(
            file_path=self.pdf_path,
            page_index=self.current_page_index - 1,
            is_new_file=False
        )

    def go_to_next_page(self):
        """
        Загружает следующую страницу PDF.
        """

        if self.current_page_index >= self.page_count - 1:
            return

        self.load_pdf_page(
            file_path=self.pdf_path,
            page_index=self.current_page_index + 1,
            is_new_file=False
        )

    # =========================================================
    # ОТРИСОВКА ИЗОБРАЖЕНИЯ
    # =========================================================

    def update_image(self, fast: bool = False):
        """
        Перерисовывает PDF на Canvas.

        fast=True:
            используется быстрый resize для плавного зума.

        fast=False:
            используется качественный resize.
        """

        if self.original_image is None:
            return

        self._prepare_display_image(fast=fast)
        self._draw_current_image_on_canvas()

        # После полной перерисовки старое выделение может стать некорректным.
        self.rect_id = None

    def _prepare_display_image(self, fast: bool = False):
        """Готовит изображение для отображения на Canvas."""

        self.rotated_image = self.original_image.rotate(
            self.angle,
            expand=True
        )

        new_width = max(1, int(self.rotated_image.width * self.zoom_factor))
        new_height = max(1, int(self.rotated_image.height * self.zoom_factor))

        resample_filter = (
            self.FAST_ZOOM_RESAMPLE
            if fast
            else self.QUALITY_RESAMPLE
        )

        self.current_image = self.rotated_image.resize(
            (new_width, new_height),
            resample=resample_filter
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
            return "break"

        old_zoom = self.zoom_factor
        self.zoom_factor = self._calculate_new_zoom(event)

        if self.zoom_factor == old_zoom:
            return "break"

        self.clear_selection()
        self.set_status(f"Масштаб: {int(self.zoom_factor * 100)}%")

        self._schedule_zoom_redraw()

        return "break"

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

    def _schedule_zoom_redraw(self):
        """
        Планирует перерисовку при зуме.

        Во время активного вращения колёсика делаем быстрый resize.
        Когда пользователь перестал крутить — делаем финальный качественный resize.
        """

        if self.zoom_redraw_after_id is None:
            self.zoom_redraw_after_id = self.after(
                self.ZOOM_REDRAW_DELAY_MS,
                self._run_fast_zoom_redraw
            )

        if self.zoom_final_redraw_after_id is not None:
            self.after_cancel(self.zoom_final_redraw_after_id)

        self.zoom_final_redraw_after_id = self.after(
            self.ZOOM_FINAL_REDRAW_DELAY_MS,
            self._run_quality_zoom_redraw
        )

    def _run_fast_zoom_redraw(self):
        """
        Быстрая перерисовка во время прокрутки.
        """

        self.zoom_redraw_after_id = None
        self.update_image(fast=True)

    def _run_quality_zoom_redraw(self):
        """
        Финальная качественная перерисовка после окончания прокрутки.
        """

        self.zoom_final_redraw_after_id = None
        self.update_image(fast=False)
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
        Вырезает выделенную область из PDF.

        На экране пользователь видит лёгкую display-версию страницы.
        Для OCR вырезаем ту же область из большой OCR-версии страницы.
        """

        if not self._can_crop():
            return None

        try:
            selection_coords = tuple(self.canvas.coords(self.rect_id))

            display_request = ImageCropRequest(
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

                # Важно:
                # сначала нам нужен crop_box в координатах display-картинки,
                # поэтому пока не разворачиваем обратно.
                restore_original_orientation=False
            )

            display_crop_result = self.image_crop_service.crop_from_canvas_selection(
                display_request
            )

            if not display_crop_result.success or display_crop_result.crop_box is None:
                logger.warning(
                    "Не удалось получить crop_box PDF-области: %s",
                    display_crop_result.error_message
                )
                return None

            cropped_image = self._crop_from_ocr_source(
                display_crop_box=display_crop_result.crop_box
            )

            logger.info(
                "PDF-область вырезана из OCR-источника. display_crop_box=%s, image_size=%s",
                display_crop_result.crop_box,
                cropped_image.size if cropped_image else None
            )

            return cropped_image

        except Exception:
            logger.exception("Ошибка при подготовке данных для OCR-crop PDF")
            return None

    def _crop_from_ocr_source(self, display_crop_box):
        """
        Пересчитывает crop_box с display-страницы на OCR-страницу
        и вырезает область из OCR-источника.
        """

        if self.ocr_source_image is None or self.rotated_image is None:
            return None

        # Поворачиваем OCR-источник так же, как display-страницу.
        ocr_rotated_image = self.ocr_source_image.rotate(
            self.angle,
            expand=True
        )

        display_width = max(1, self.rotated_image.width)
        display_height = max(1, self.rotated_image.height)

        scale_x = ocr_rotated_image.width / display_width
        scale_y = ocr_rotated_image.height / display_height

        left, top, right, bottom = display_crop_box

        ocr_crop_box = (
            int(round(left * scale_x)),
            int(round(top * scale_y)),
            int(round(right * scale_x)),
            int(round(bottom * scale_y))
        )

        cropped_image = ocr_rotated_image.crop(ocr_crop_box)

        # Возвращаем фрагмент в исходную ориентацию,
        # как и раньше.
        cropped_image = cropped_image.rotate(
            -self.angle,
            expand=True
        )

        return cropped_image

    def _can_crop(self) -> bool:
        """
        Проверяет, есть ли всё необходимое для вырезания области.
        """

        return (
                self.rect_id is not None
                and self.original_image is not None
                and self.ocr_source_image is not None
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