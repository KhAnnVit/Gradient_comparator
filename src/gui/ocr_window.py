import customtkinter as ctk
from tkinter import Menu
from PIL import Image

class OCRViewerFrame(ctk.CTkFrame):
    """Класс второго раздела: Результаты распознавания (OCR)"""

    def __init__(self, master):
        super().__init__(master)

        # Настраиваем сетку (строка 1 с текстом будет растягиваться)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Верхняя часть: Превью вырезанной картинки ---
        self.image_panel = ctk.CTkFrame(self, height=150)
        self.image_panel.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.image_panel.pack_propagate(False)  # Блокируем сжатие фрейма

        self.lbl_image = ctk.CTkLabel(self.image_panel, text="Здесь появится вырезанный фрагмент")
        self.lbl_image.pack(expand=True)

        # --- Средняя часть: Редактируемое текстовое поле ---
        self.textbox = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.textbox.insert("0.0", "Здесь появится распознанный текст...\n")

        # --- Всплывающее меню (Правая кнопка мыши) ---
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Перенести выделенное в Поле 1", command=lambda: self.send_selection(1))
        self.context_menu.add_command(label="Перенести выделенное в Поле 2", command=lambda: self.send_selection(2))

        # Привязываем правый клик (<Button-3>) к текстовому полю
        self.textbox.bind("<Button-3>", self.show_context_menu)

        # --- Нижняя часть: Кнопки полного переноса ---
        self.bottom_panel = ctk.CTkFrame(self)
        self.bottom_panel.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.bottom_panel.grid_columnconfigure((0, 1), weight=1)

        self.btn_send_1 = ctk.CTkButton(self.bottom_panel, text="Перенести полностью в Поле 1",
                                        command=lambda: self.send_full_text(1))
        self.btn_send_1.grid(row=0, column=0, padx=5, pady=10, sticky="ew")

        self.btn_send_2 = ctk.CTkButton(self.bottom_panel, text="Перенести полностью в Поле 2",
                                        command=lambda: self.send_full_text(2))
        self.btn_send_2.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

    def show_context_menu(self, event):
        """Показывает меню только если пользователь выделил часть текста"""
        try:
            # Метод tag_ranges("sel") проверяет, есть ли активное выделение курсором
            if self.textbox.tag_ranges("sel"):
                self.context_menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    def send_selection(self, field_num):
        """
        Отправляет выделенный фрагмент текста в одно из полей сравнения.

        Теперь OCR-раздел не обращается напрямую к CompareSection.
        Он передаёт текст через AppController.
        """

        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()

            if not selected_text:
                print("Текст не выделен!")
                return

            self.master.controller.send_text_to_compare(
                text=selected_text,
                field_num=field_num,
                source="ocr"
            )

        except Exception:
            print("Текст не выделен!")

    def send_full_text(self, field_num):
        """
        Отправляет весь OCR-текст в одно из полей сравнения.

        field_num:
            1 — левое поле сравнения
            2 — правое поле сравнения
        """

        full_text = self.textbox.get("0.0", "end").strip()

        if not full_text:
            print("OCR-текст пустой!")
            return

        self.master.controller.send_text_to_compare(
            text=full_text,
            field_num=field_num,
            source="ocr"
        )

    def update_content(self, pil_image, text):
        """Метод, который будет вызываться из первого раздела при успешном OCR"""
        # 1. Масштабируем картинку для превью, чтобы она не разорвала окно
        max_height = 130
        if pil_image.height > max_height:
            ratio = max_height / pil_image.height
            new_width = int(pil_image.width * ratio)
            pil_image = pil_image.resize((new_width, max_height), Image.Resampling.LANCZOS)

        # Загружаем картинку в интерфейс
        ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(pil_image.width, pil_image.height))
        self.lbl_image.configure(image=ctk_img, text="")
        self.lbl_image.image = ctk_img  # Сохраняем ссылку в памяти

        # 2. Обновляем текстовое поле
        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", text)