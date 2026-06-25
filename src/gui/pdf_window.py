import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, Menu, messagebox

from PIL import ImageTk
from pdf2image import convert_from_path

from config import POPPLER_PATH
from src.ocr_engine import extract_text_from_pil
from src.utils.logger import logger


class PDFViewerFrame(ctk.CTkFrame):
    """
    Первый раздел приложения: просмотр PDF, перемещение изображения,
    масштабирование, поворот, выделение области и отправка её в OCR.
    """

    # Ограничения зума, чтобы пользователь случайно не сделал изображение
    # слишком маленьким или слишком огромным.
    MIN_ZOOM = 0.2
    MAX_ZOOM = 5.0
    ZOOM_STEP = 1.1

    # DPI для конвертации PDF в изображение.
    # Чем выше DPI, тем лучше качество OCR, но тем тяжелее изображение.
    PDF_DPI = 300

    def __init__(self, master):
        super().__init__(master)

        # Главная сетка фрейма:
        # row=0 — верхняя панель кнопок
        # row=1 — Canvas с PDF
        # row=2 — строка статуса
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._init_state()
        self._create_widgets()
        self._bind_events()

    # =========================================================
    # ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ
    # =========================================================

    def _init_state(self):
        """
        Создаёт все переменные состояния для PDF-просмотра.

        Важно:
        - original_image хранит страницу PDF без зума и поворота;
        - rotated_image хранит страницу после поворота;
        - current_image хранит страницу после поворота и зума;
        - tk_image нужен Tkinter, чтобы показать картинку на Canvas.
        """

        # Путь к загруженному PDF.
        self.pdf_path = None

        # Изображения.
        self.original_image = None
        self.rotated_image = None
        self.current_image = None
        self.tk_image = None

        # Текущий масштаб.
        self.zoom_factor = 1.0

        # Текущий угол поворота.
        # Значения: 0, 90, 180, 270.
        self.angle = 0

        # Смещение изображения относительно центра Canvas.
        # Нужно для режима "Перемещение".
        self.offset_x = 0
        self.offset_y = 0

        # Координаты мыши на предыдущем шаге перемещения.
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        # ID прямоугольника выделения на Canvas.
        self.rect_id = None

        # Начальная точка выделения.
        self.start_x = 0
        self.start_y = 0

    # =========================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =========================================================

    def _create_widgets(self):
        """Создаёт все элементы интерфейса этого раздела."""

        # ---------- Верхняя панель ----------
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

        # Переключатель режимов:
        # - Перемещение: пользователь двигает PDF по Canvas.
        # - Выделение: пользователь рисует рамку для OCR.
        self.mode_switch = ctk.CTkSegmentedButton(
            self.top_panel,
            values=["Перемещение", "Выделение"],
            width=220
        )
        self.mode_switch.pack(side="left", padx=20, pady=5)
        self.mode_switch.set("Выделение")

        # ---------- Canvas ----------
        # Canvas используется, потому что на нём удобно:
        # - показывать изображение;
        # - двигать его;
        # - рисовать прямоугольник выделения.
        self.canvas = tk.Canvas(
            self,
            bg="#2b2b2b",
            highlightthickness=0
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # ---------- Строка статуса ----------
        self.status_label = ctk.CTkLabel(
            self,
            text="Загрузите PDF для начала работы.",
            anchor="w"
        )
        self.status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        # ---------- Контекстное меню ----------
        # Показывается при правом клике по выделенной области.
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Распознать текст",
            command=self.send_to_ocr
        )

    # =========================================================
    # ПРИВЯЗКА СОБЫТИЙ
    # =========================================================

    def _bind_events(self):
        """Привязывает события мыши и изменения размера Canvas."""

        # Колёсико мыши на Windows/macOS.
        self.canvas.bind("<MouseWheel>", self.zoom_image)

        # Колёсико мыши на некоторых Linux-системах.
        self.canvas.bind("<Button-4>", self.zoom_image)
        self.canvas.bind("<Button-5>", self.zoom_image)

        # Левая кнопка мыши:
        # в зависимости от режима либо двигает изображение,
        # либо начинает выделение области.
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)

        # Правая кнопка мыши открывает меню,
        # если клик был внутри выделенной области.
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # При изменении размера Canvas перерисовываем изображение,
        # чтобы оно оставалось корректно расположенным.
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    # =========================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ ИНТЕРФЕЙСА
    # =========================================================

    def set_status(self, text):
        """Обновляет текст в нижней строке статуса."""
        self.status_label.configure(text=text)

    def clear_selection(self):
        """Удаляет текущую рамку выделения, если она есть."""
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
            self.set_status("Выделение очищено.")

    def reset_view(self):
        """
        Возвращает изображение к начальному виду:
        - масштаб 100%;
        - угол 0°;
        - без смещения;
        - без выделения.
        """
        if self.original_image is None:
            return

        self.zoom_factor = 1.0
        self.angle = 0
        self.offset_x = 0
        self.offset_y = 0
        self.clear_selection()
        self.update_image()
        self.set_status("Вид сброшен.")

    # =========================================================
    # ЗАГРУЗКА PDF
    # =========================================================

    def load_pdf(self):
        """Открывает PDF-файл и конвертирует первую страницу в изображение."""

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

            pages = convert_from_path(
                file_path,
                dpi=self.PDF_DPI,
                poppler_path=str(POPPLER_PATH)
            )

            if not pages:
                messagebox.showwarning(
                    "PDF не загружен",
                    "Не удалось получить страницы из PDF-файла."
                )
                self.set_status("PDF не загружен.")
                return

            # Пока берём только первую страницу.
            # Позже можно добавить переключение страниц.
            self.pdf_path = file_path
            self.original_image = pages[0]

            # Сохраняем путь к PDF в общем состоянии приложения
            self.master.controller.set_current_pdf(file_path)

            # Сбрасываем состояние просмотра для нового файла.
            self.zoom_factor = 1.0
            self.angle = 0
            self.offset_x = 0
            self.offset_y = 0
            self.rect_id = None

            self.update_image()

            self.set_status(f"PDF загружен: {file_path}")
            logger.info("PDF успешно загружен. Размер первой страницы: %sx%s",
                        self.original_image.width, self.original_image.height)

        except Exception:
            logger.exception("Ошибка при загрузке PDF")
            messagebox.showerror(
                "Ошибка загрузки PDF",
                "Не удалось загрузить PDF. Проверьте файл и путь к Poppler."
            )
            self.set_status("Ошибка загрузки PDF.")

    # =========================================================
    # ОТРИСОВКА ИЗОБРАЖЕНИЯ
    # =========================================================

    def update_image(self):
        """
        Перерисовывает изображение на Canvas.

        Этот метод единственный отвечает за:
        - поворот;
        - масштабирование;
        - создание ImageTk.PhotoImage;
        - размещение изображения на Canvas.
        """

        if self.original_image is None:
            return

        # 1. Поворачиваем исходную страницу.
        # rotated_image нужен отдельно, потому что crop делается именно из него.
        self.rotated_image = self.original_image.rotate(self.angle, expand=True)

        # 2. Считаем новый размер после зума.
        new_width = max(1, int(self.rotated_image.width * self.zoom_factor))
        new_height = max(1, int(self.rotated_image.height * self.zoom_factor))

        # 3. Создаём изображение, которое реально будет показано на Canvas.
        self.current_image = self.rotated_image.resize(
            (new_width, new_height),
            resample=ImageTk.Image.Resampling.LANCZOS
        )

        # 4. Преобразуем PIL.Image в формат, который понимает Tkinter.
        self.tk_image = ImageTk.PhotoImage(self.current_image)

        # 5. Очищаем Canvas и рисуем изображение заново.
        self.canvas.delete("all")

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())

        # Центр изображения = центр Canvas + пользовательское смещение.
        center_x = canvas_w // 2 + self.offset_x
        center_y = canvas_h // 2 + self.offset_y

        self.canvas.create_image(
            center_x,
            center_y,
            anchor="center",
            image=self.tk_image,
            tags="image"
        )

        # После полной перерисовки старое выделение теряет смысл,
        # потому что координаты Canvas могли измениться.
        self.rect_id = None

    def on_canvas_resize(self, event=None):
        """
        Вызывается при изменении размера Canvas.

        Нужно для случаев, когда пользователь растянул окно приложения.
        """
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
        """
        Масштабирует изображение колесиком мыши.

        На Windows используется event.delta.
        На Linux часто используются Button-4 и Button-5.
        """

        if self.original_image is None:
            return

        old_zoom = self.zoom_factor

        # Windows/macOS.
        if hasattr(event, "delta") and event.delta:
            if event.delta > 0:
                self.zoom_factor *= self.ZOOM_STEP
            else:
                self.zoom_factor /= self.ZOOM_STEP

        # Linux.
        elif hasattr(event, "num"):
            if event.num == 4:
                self.zoom_factor *= self.ZOOM_STEP
            elif event.num == 5:
                self.zoom_factor /= self.ZOOM_STEP

        # Ограничиваем масштаб.
        self.zoom_factor = max(self.MIN_ZOOM, min(self.zoom_factor, self.MAX_ZOOM))

        # Если масштаб реально изменился — перерисовываем.
        if self.zoom_factor != old_zoom:
            self.clear_selection()
            self.update_image()
            self.set_status(f"Масштаб: {int(self.zoom_factor * 100)}%")

    # =========================================================
    # ОБРАБОТКА МЫШИ: ПЕРЕМЕЩЕНИЕ И ВЫДЕЛЕНИЕ
    # =========================================================

    def on_mouse_press(self, event):
        """
        Срабатывает при нажатии левой кнопки мыши.

        В режиме "Перемещение" запоминает стартовую точку.
        В режиме "Выделение" создаёт новый прямоугольник.
        """

        if self.original_image is None:
            return

        current_mode = self.mode_switch.get()

        if current_mode == "Перемещение":
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

        elif current_mode == "Выделение":
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
        """
        Срабатывает при движении мыши с зажатой левой кнопкой.

        В режиме "Перемещение" двигает всё содержимое Canvas.
        В режиме "Выделение" изменяет размер красной рамки.
        """

        if self.original_image is None:
            return

        current_mode = self.mode_switch.get()

        if current_mode == "Перемещение":
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

            self.offset_x += dx
            self.offset_y += dy

            self.canvas.move("all", dx, dy)

        elif current_mode == "Выделение":
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
        Показывает контекстное меню только если:
        - есть выделенная область;
        - пользователь кликнул правой кнопкой внутри этой области.
        """

        if self.rect_id is None:
            return

        x1, y1, x2, y2 = self.canvas.coords(self.rect_id)

        click_x = self.canvas.canvasx(event.x)
        click_y = self.canvas.canvasy(event.y)

        min_x, max_x = sorted([x1, x2])
        min_y, max_y = sorted([y1, y2])

        is_inside_selection = (
            min_x <= click_x <= max_x and
            min_y <= click_y <= max_y
        )

        if is_inside_selection:
            self.context_menu.post(event.x_root, event.y_root)

    # =========================================================
    # ВЫРЕЗАНИЕ ВЫДЕЛЕННОЙ ОБЛАСТИ
    # =========================================================

    def get_cropped_image(self):
        """
        Вырезает выделенную область из PDF-изображения.

        Основная идея:
        1. Пользователь рисует рамку на Canvas.
        2. Canvas показывает уже увеличенное и повернутое изображение.
        3. Нужно перевести координаты рамки обратно в координаты rotated_image.
        4. Потом вырезать область из rotated_image.
        """

        if self.rect_id is None or self.original_image is None:
            return None

        if self.current_image is None or self.rotated_image is None:
            return None

        # Координаты рамки на Canvas.
        x1, y1, x2, y2 = self.canvas.coords(self.rect_id)

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())

        # Левый верхний угол картинки на Canvas.
        image_left = canvas_w / 2 + self.offset_x - self.current_image.width / 2
        image_top = canvas_h / 2 + self.offset_y - self.current_image.height / 2

        # Перевод координат Canvas → координаты изображения без зума.
        crop_x1 = (x1 - image_left) / self.zoom_factor
        crop_y1 = (y1 - image_top) / self.zoom_factor
        crop_x2 = (x2 - image_left) / self.zoom_factor
        crop_y2 = (y2 - image_top) / self.zoom_factor

        # Если рамку тянули справа налево или снизу вверх,
        # координаты нужно отсортировать.
        crop_x1, crop_x2 = sorted([crop_x1, crop_x2])
        crop_y1, crop_y2 = sorted([crop_y1, crop_y2])

        # Обрезаем координаты по границам изображения.
        crop_x1 = max(0, min(crop_x1, self.rotated_image.width))
        crop_y1 = max(0, min(crop_y1, self.rotated_image.height))
        crop_x2 = max(0, min(crop_x2, self.rotated_image.width))
        crop_y2 = max(0, min(crop_y2, self.rotated_image.height))

        # Переводим в int, потому что PIL crop работает с пикселями.
        crop_box = (
            int(round(crop_x1)),
            int(round(crop_y1)),
            int(round(crop_x2)),
            int(round(crop_y2))
        )

        left, top, right, bottom = crop_box

        # Защита от слишком маленькой или пустой области.
        if left >= right or top >= bottom:
            return None

        cropped_image = self.rotated_image.crop(crop_box)

        # Возвращаем фрагмент в исходную ориентацию.
        # Если PDF был повернут для удобства просмотра, OCR лучше дать
        # фрагмент в нормальном положении.
        cropped_image = cropped_image.rotate(-self.angle, expand=True)

        return cropped_image

    # =========================================================
    # ОТПРАВКА В OCR
    # =========================================================

    def send_to_ocr(self):
        """
        Вырезает выделенную область, запускает OCR и передаёт результат
        во второй раздел приложения.
        """

        cropped_image = self.get_cropped_image()

        if cropped_image is None:
            messagebox.showwarning(
                "Нет области",
                "Не удалось вырезать область. Проверьте, что выделение находится на изображении."
            )
            self.set_status("Не удалось вырезать область.")
            return

        try:
            self.set_status("Распознавание текста...")
            self.configure(cursor="watch")
            self.update_idletasks()

            logger.info("Запущено OCR для выделенной области. Размер: %sx%s",
                        cropped_image.width, cropped_image.height)

            recognized_text = extract_text_from_pil(cropped_image)

            logger.info("OCR завершено. Длина текста: %s символов",
                        len(recognized_text))

            # Пока оставляем старую схему связи между окнами.
            # На следующем архитектурном этапе это лучше заменить на AppController.
            ocr_frame = self.master.frames["tab2"]
            ocr_frame.update_content(cropped_image, recognized_text)

            self.master.select_frame("tab2")

            self.set_status("Текст распознан и отправлен в раздел OCR.")

        except Exception:
            logger.exception("Ошибка во время OCR")
            messagebox.showerror(
                "Ошибка OCR",
                "Не удалось распознать текст в выделенной области."
            )
            self.set_status("Ошибка OCR.")

        finally:
            self.configure(cursor="")