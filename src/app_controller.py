from pathlib import Path
from typing import Any

from src.app_state import AppState
from src.utils.logger import logger


class AppController:
    """
    Центральный контроллер приложения.

    Его задача — связывать окна между собой.

    ВАЖНО:
    окна GUI не должны напрямую обращаться друг к другу.

    Было плохо:
        self.master.frames["tab3"].set_text_left(text)

    Станет лучше:
        self.master.controller.send_text_to_compare(text, field_num=1)

    Тогда GUI-окна становятся проще:
    они только сообщают контроллеру, что произошло.
    """

    def __init__(self, app, state: AppState):
        """
        app — главное окно приложения, то есть объект App из main_window.py.
        state — общий объект состояния приложения.
        """
        self.app = app
        self.state = state

    # =========================================================
    # НАВИГАЦИЯ
    # =========================================================

    def go_to_tab(self, tab_name: str):
        """
        Переключает приложение на нужный раздел.

        tab_name:
            "tab1" — PDF
            "tab2" — OCR
            "tab3" — Сравнение
            "tab4" — Excel
        """

        if tab_name not in self.app.frames:
            logger.warning("Попытка перейти на неизвестную вкладку: %s", tab_name)
            return

        self.state.current_tab = tab_name
        self.app.select_frame(tab_name)

        logger.info("Переход на вкладку: %s", tab_name)

    # =========================================================
    # PDF
    # =========================================================

    def set_current_pdf(self, pdf_path: str | Path):
        """
        Сохраняет путь к текущему PDF-файлу в AppState.
        """

        self.state.current_pdf_path = Path(pdf_path)
        self.state.current_pdf_page = 0

        logger.info("Текущий PDF сохранён в состоянии: %s", pdf_path)

    def show_ocr_result(self, image: Any, text: str, source: str = "pdf_selection"):
        """
        Получает результат OCR и передаёт его в раздел OCR.

        image — вырезанная картинка, обычно PIL.Image.
        text — распознанный текст.
        source — источник текста.

        Этот метод заменит прямую связь:
            PDFWindow -> OCRWindow
        """

        # 1. Сохраняем данные в общем состоянии.
        self.state.selected_image = image
        self.state.ocr_text = text
        self.state.ocr_source = source

        logger.info(
            "OCR-результат сохранён. Источник: %s, длина текста: %s",
            source,
            len(text)
        )

        # 2. Обновляем OCR-раздел, если он существует.
        ocr_frame = self.app.frames.get("tab2")

        if ocr_frame is None:
            logger.warning("OCR frame не найден: tab2")
            return

        if not hasattr(ocr_frame, "update_content"):
            logger.warning("OCR frame не имеет метода update_content")
            return

        ocr_frame.update_content(image, text)

        # 3. Переходим на вкладку OCR.
        self.go_to_tab("tab2")

    # =========================================================
    # COMPARE
    # =========================================================

    def send_text_to_compare(self, text: str, field_num: int, source: str = "unknown"):
        """
        Отправляет текст в одно из полей сравнения.

        field_num:
            1 — левое поле
            2 — правое поле

        source:
            "ocr"
            "excel"
            "manual"
            "unknown"
        """

        if field_num not in (1, 2):
            logger.warning("Некорректный номер поля сравнения: %s", field_num)
            return

        compare_frame = self.app.frames.get("tab3")

        if compare_frame is None:
            logger.warning("Compare frame не найден: tab3")
            return

        if field_num == 1:
            self.state.compare_text_1 = text
            self.state.compare_text_1_source = source

            if hasattr(compare_frame, "set_text_left"):
                compare_frame.set_text_left(text)
            else:
                logger.warning("Compare frame не имеет метода set_text_left")

        else:
            self.state.compare_text_2 = text
            self.state.compare_text_2_source = source

            if hasattr(compare_frame, "set_text_right"):
                compare_frame.set_text_right(text)
            else:
                logger.warning("Compare frame не имеет метода set_text_right")

        logger.info(
            "Текст отправлен в поле сравнения %s. Источник: %s, длина: %s",
            field_num,
            source,
            len(text)
        )

        self.go_to_tab("tab3")

    def clear_compare(self):
        """
        Очищает оба поля сравнения:
        - в состоянии;
        - в интерфейсе.
        """

        self.state.reset_compare()

        compare_frame = self.app.frames.get("tab3")

        if compare_frame is not None:
            if hasattr(compare_frame, "set_text_left"):
                compare_frame.set_text_left("")

            if hasattr(compare_frame, "set_text_right"):
                compare_frame.set_text_right("")

        logger.info("Поля сравнения очищены")

    # =========================================================
    # EXCEL
    # =========================================================

    def set_current_excel(self, excel_path: str | Path):
        """
        Сохраняет путь к текущему Excel-файлу.
        """

        self.state.current_excel_path = Path(excel_path)

        logger.info("Текущий Excel сохранён в состоянии: %s", excel_path)

    def set_current_excel_cell(self, row: int, col: int, value: str):
        """
        Сохраняет информацию о текущей выбранной ячейке Excel.
        """

        self.state.current_excel_row = row
        self.state.current_excel_col = col
        self.state.current_excel_cell_value = value

        logger.info(
            "Выбрана Excel-ячейка: row=%s, col=%s, value_length=%s",
            row,
            col,
            len(value)
        )

    def send_excel_cell_to_compare(self, value: str, field_num: int):
        """
        Отправляет значение Excel-ячейки в поле сравнения.
        """

        self.send_text_to_compare(
            text=value,
            field_num=field_num,
            source="excel"
        )

    # =========================================================
    # STATUS
    # =========================================================

    def set_status(self, message: str):
        """
        Сохраняет статусное сообщение.

        Пока мы просто записываем его в AppState и лог.
        Позже можно будет сделать общую строку статуса в главном окне.
        """

        self.state.set_status(message)
        logger.info("STATUS: %s", message)