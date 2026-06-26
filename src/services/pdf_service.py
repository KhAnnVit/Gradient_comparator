from pathlib import Path

from pdf2image import convert_from_path, pdfinfo_from_path

from src.models.pdf_models import PDFLoadSettings, PDFLoadResult
from src.utils.logger import logger


class PDFService:
    """
    Сервис для загрузки PDF.

    Этот класс не знает ничего про Tkinter, Canvas,
    кнопки, messagebox и GUI.

    Его задача:
    - проверить путь к PDF;
    - узнать количество страниц;
    - сконвертировать нужную страницу PDF в PIL.Image.
    """

    def load_first_page(
        self,
        pdf_path: str | Path,
        settings: PDFLoadSettings
    ) -> PDFLoadResult:
        """
        Загружает первую страницу PDF.

        Оставляем метод для совместимости.
        """

        return self.load_page(
            pdf_path=pdf_path,
            page_number=0,
            settings=settings
        )

    def load_page(
        self,
        pdf_path: str | Path,
        page_number: int,
        settings: PDFLoadSettings
    ) -> PDFLoadResult:
        """
        Загружает конкретную страницу PDF.

        page_number внутри приложения 0-based:
            0 — первая страница.
        """

        pdf_path_obj = None

        try:
            pdf_path_obj = Path(pdf_path)

            validation_error = self._validate_pdf_path(pdf_path_obj)

            if validation_error:
                return PDFLoadResult(
                    success=False,
                    pdf_path=pdf_path_obj,
                    page_number=page_number,
                    error_message=validation_error
                )

            poppler_path = self._prepare_poppler_path(settings.poppler_path)

            page_count = self.get_page_count(
                pdf_path=pdf_path_obj,
                settings=settings
            )

            if page_count <= 0:
                return PDFLoadResult(
                    success=False,
                    pdf_path=pdf_path_obj,
                    page_number=page_number,
                    page_count=page_count,
                    error_message="Не удалось определить количество страниц PDF."
                )

            if page_number < 0 or page_number >= page_count:
                return PDFLoadResult(
                    success=False,
                    pdf_path=pdf_path_obj,
                    page_number=page_number,
                    page_count=page_count,
                    error_message=(
                        f"Страница вне диапазона. "
                        f"Доступно страниц: {page_count}."
                    )
                )

            # pdf2image использует 1-based номера страниц.
            pdf2image_page_number = page_number + 1

            logger.info(
                "Начата загрузка PDF-страницы. path=%s, page=%s/%s, dpi=%s",
                pdf_path_obj,
                pdf2image_page_number,
                page_count,
                settings.dpi
            )

            pages = convert_from_path(
                str(pdf_path_obj),
                dpi=settings.dpi,
                poppler_path=poppler_path,
                first_page=pdf2image_page_number,
                last_page=pdf2image_page_number
            )

            if not pages:
                return PDFLoadResult(
                    success=False,
                    pdf_path=pdf_path_obj,
                    page_number=page_number,
                    page_count=page_count,
                    error_message="Не удалось получить страницу из PDF-файла."
                )

            page_image = pages[0]

            logger.info(
                "PDF-страница загружена. path=%s, page=%s/%s, size=%sx%s",
                pdf_path_obj,
                pdf2image_page_number,
                page_count,
                page_image.width,
                page_image.height
            )

            return PDFLoadResult(
                success=True,
                pdf_path=pdf_path_obj,
                page_image=page_image,
                page_number=page_number,
                page_count=page_count
            )

        except Exception as error:
            logger.exception("Ошибка при загрузке PDF-страницы")

            return PDFLoadResult(
                success=False,
                pdf_path=pdf_path_obj,
                page_number=page_number,
                error_message=str(error)
            )

    def get_page_count(
        self,
        pdf_path: str | Path,
        settings: PDFLoadSettings
    ) -> int:
        """
        Возвращает количество страниц PDF.
        """

        pdf_path = Path(pdf_path)
        poppler_path = self._prepare_poppler_path(settings.poppler_path)

        info = pdfinfo_from_path(
            str(pdf_path),
            poppler_path=poppler_path
        )

        return int(info.get("Pages", 0))

    def _validate_pdf_path(self, pdf_path: Path) -> str:
        """
        Проверяет путь к PDF.
        Возвращает текст ошибки или пустую строку.
        """

        if not pdf_path.exists():
            return "PDF-файл не найден."

        if not pdf_path.is_file():
            return "Выбранный путь не является файлом."

        if pdf_path.suffix.lower() != ".pdf":
            return "Выбранный файл не является PDF."

        return ""

    def _prepare_poppler_path(self, poppler_path):
        """
        Подготавливает путь к Poppler для pdf2image.

        pdf2image ждёт строку или None.
        """

        if poppler_path is None:
            return None

        return str(poppler_path)