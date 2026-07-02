import ctypes
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from PIL import Image

from config import PROCESSED_DATA_DIR
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

    Важно для exe:
    в собранной версии pdf2image может падать на pdfinfo_from_path,
    хотя Poppler сам работает.

    Поэтому здесь Poppler вызывается напрямую:
    - pdfinfo.exe — для получения количества страниц;
    - pdftoppm.exe — для конвертации страницы PDF в PNG.

    Также перед запуском Poppler временно сбрасывается DLL search path
    PyInstaller, чтобы Poppler использовал свои DLL, а не конфликтующие
    DLL из папки _internal.
    """

    TEMP_PDF_DIR_NAME = "temp_pdf"

    # =========================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================

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

        original_pdf_path = None
        work_pdf_path = None

        try:
            original_pdf_path = Path(pdf_path)

            validation_error = self._validate_pdf_path(original_pdf_path)

            if validation_error:
                return PDFLoadResult(
                    success=False,
                    pdf_path=original_pdf_path,
                    page_number=page_number,
                    error_message=validation_error
                )

            poppler_path = self._prepare_poppler_path(settings.poppler_path)

            work_pdf_path = self._create_temporary_pdf_copy(
                original_pdf_path
            )

            logger.info(
                (
                    "PDF подготовлен для обработки. "
                    "original_path=%s, work_path=%s, poppler_path=%s"
                ),
                original_pdf_path,
                work_pdf_path,
                poppler_path
            )

            page_count = self.get_page_count(
                pdf_path=work_pdf_path,
                settings=settings
            )

            if page_count <= 0:
                return PDFLoadResult(
                    success=False,
                    pdf_path=original_pdf_path,
                    page_number=page_number,
                    page_count=page_count,
                    error_message="Не удалось определить количество страниц PDF."
                )

            if page_number < 0 or page_number >= page_count:
                return PDFLoadResult(
                    success=False,
                    pdf_path=original_pdf_path,
                    page_number=page_number,
                    page_count=page_count,
                    error_message=(
                        f"Страница вне диапазона. "
                        f"Доступно страниц: {page_count}."
                    )
                )

            # Poppler использует 1-based номера страниц.
            poppler_page_number = page_number + 1

            logger.info(
                "Начата загрузка PDF-страницы. path=%s, page=%s/%s, dpi=%s",
                work_pdf_path,
                poppler_page_number,
                page_count,
                settings.dpi
            )

            page_image = self._convert_pdf_page_to_image(
                pdf_path=work_pdf_path,
                page_number=poppler_page_number,
                dpi=settings.dpi,
                poppler_path=poppler_path
            )

            logger.info(
                (
                    "PDF-страница загружена. "
                    "original_path=%s, page=%s/%s, size=%sx%s"
                ),
                original_pdf_path,
                poppler_page_number,
                page_count,
                page_image.width,
                page_image.height
            )

            return PDFLoadResult(
                success=True,
                pdf_path=original_pdf_path,
                page_image=page_image,
                page_number=page_number,
                page_count=page_count
            )

        except Exception as error:
            logger.exception(
                (
                    "Ошибка при загрузке PDF-страницы. "
                    "original_path=%s, work_path=%s"
                ),
                original_pdf_path,
                work_pdf_path
            )

            return PDFLoadResult(
                success=False,
                pdf_path=original_pdf_path,
                page_number=page_number,
                error_message=str(error)
            )

        finally:
            self._delete_temporary_pdf_copy(work_pdf_path)

    def get_page_count(
        self,
        pdf_path: str | Path,
        settings: PDFLoadSettings
    ) -> int:
        """
        Возвращает количество страниц PDF через pdfinfo.exe.
        """

        pdf_path = Path(pdf_path)
        poppler_path = self._prepare_poppler_path(settings.poppler_path)

        logger.debug(
            "Получение количества страниц PDF через pdfinfo. path=%s, poppler_path=%s",
            pdf_path,
            poppler_path
        )

        return self._get_page_count_with_pdfinfo(
            pdf_path=pdf_path,
            poppler_path=poppler_path
        )

    # =========================================================
    # POPPLER: КОЛИЧЕСТВО СТРАНИЦ
    # =========================================================

    def _get_page_count_with_pdfinfo(
        self,
        pdf_path: Path,
        poppler_path: Path | None
    ) -> int:
        """
        Получает количество страниц через прямой вызов pdfinfo.exe.

        Не используем pdf2image.pdfinfo_from_path,
        потому что в exe он может падать, даже когда pdfinfo.exe работает.
        """

        pdfinfo_exe = self._get_poppler_executable(
            poppler_path=poppler_path,
            executable_name="pdfinfo.exe"
        )

        command = [
            str(pdfinfo_exe),
            str(pdf_path)
        ]

        completed_process = self._run_poppler_command(
            command=command,
            poppler_path=poppler_path
        )

        output = completed_process.stdout or ""

        for line in output.splitlines():
            line = line.strip()

            if not line.lower().startswith("pages:"):
                continue

            pages_text = line.split(":", 1)[1].strip()

            return int(pages_text)

        logger.error(
            "pdfinfo не вернул строку Pages. stdout=%s, stderr=%s",
            completed_process.stdout,
            completed_process.stderr
        )

        raise RuntimeError("Poppler не смог определить количество страниц PDF.")

    # =========================================================
    # POPPLER: КОНВЕРТАЦИЯ СТРАНИЦЫ
    # =========================================================

    def _convert_pdf_page_to_image(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        poppler_path: Path | None
    ) -> Image.Image:
        """
        Конвертирует одну страницу PDF в изображение через pdftoppm.exe.
        """

        pdftoppm_exe = self._get_poppler_executable(
            poppler_path=poppler_path,
            executable_name="pdftoppm.exe"
        )

        temp_dir = self._get_temp_pdf_dir()
        output_prefix = temp_dir / f"page_{uuid.uuid4().hex}"
        output_image_path = output_prefix.with_suffix(".png")

        command = [
            str(pdftoppm_exe),
            "-r",
            str(dpi),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            "-png",
            str(pdf_path),
            str(output_prefix)
        ]

        try:
            self._run_poppler_command(
                command=command,
                poppler_path=poppler_path
            )

            if not output_image_path.exists():
                raise RuntimeError(
                    f"Poppler не создал изображение страницы: {output_image_path}"
                )

            with Image.open(output_image_path) as image:
                return image.copy()

        finally:
            self._delete_file_safely(output_image_path)

    # =========================================================
    # ЗАПУСК ВНЕШНИХ КОМАНД POPPLER
    # =========================================================

    def _run_poppler_command(
        self,
        command: list[str],
        poppler_path: Path | None
    ) -> subprocess.CompletedProcess:
        """
        Запускает команду Poppler.

        В exe, собранном PyInstaller, внешние exe-файлы могут падать
        из-за конфликта DLL из папки _internal.

        Поэтому перед запуском Poppler:
        - добавляем poppler/bin в PATH;
        - убираем лишние пути PyInstaller из PATH;
        - временно сбрасываем DLL search path PyInstaller.
        """

        env = self._build_poppler_environment(poppler_path)

        logger.debug(
            "Запуск Poppler-команды: %s",
            " ".join(command)
        )

        creation_flags = 0

        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._reset_windows_dll_search_path_for_subprocess()

        try:
            completed_process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(poppler_path) if poppler_path is not None else None,
                check=False,
                creationflags=creation_flags
            )

        finally:
            self._restore_windows_dll_search_path_after_subprocess()

        if completed_process.returncode != 0:
            logger.error(
                (
                    "Poppler-команда завершилась с ошибкой. "
                    "returncode=%s, stdout=%s, stderr=%s"
                ),
                completed_process.returncode,
                completed_process.stdout,
                completed_process.stderr
            )

            error_text = completed_process.stderr or completed_process.stdout
            error_text = error_text.strip()

            # 3221225477 = 0xC0000005, access violation.
            # Обычно это конфликт DLL при запуске внешнего exe из PyInstaller.
            if completed_process.returncode == 3221225477:
                error_text = (
                    "Poppler аварийно завершился из-за конфликта DLL. "
                    "Подробности смотрите в app.log."
                )

            if not error_text:
                error_text = "Poppler завершился с ошибкой."

            raise RuntimeError(error_text)

        return completed_process

    def _build_poppler_environment(
        self,
        poppler_path: Path | None
    ) -> dict:
        """
        Создаёт окружение для запуска Poppler.

        Убираем из PATH папку PyInstaller _internal,
        потому что из-за неё Poppler может подхватить чужие DLL.

        Потом добавляем poppler/bin в начало PATH.
        """

        env = os.environ.copy()

        path_parts = env.get("PATH", "").split(os.pathsep)

        if hasattr(sys, "_MEIPASS"):
            internal_path = Path(sys._MEIPASS).resolve()

            path_parts = [
                path_part
                for path_part in path_parts
                if path_part
                and not self._path_is_inside(path_part, internal_path)
            ]

        if poppler_path is not None:
            path_parts.insert(0, str(poppler_path))

        env["PATH"] = os.pathsep.join(path_parts)

        return env

    def _path_is_inside(self, path_value: str, parent_path: Path) -> bool:
        """
        Проверяет, находится ли путь внутри другой папки.
        """

        try:
            checked_path = Path(path_value).resolve()

            return (
                checked_path == parent_path
                or parent_path in checked_path.parents
            )

        except Exception:
            return False

    def _reset_windows_dll_search_path_for_subprocess(self):
        """
        Сбрасывает DLL search path PyInstaller перед запуском внешней программы.

        Это нужно для Poppler, чтобы он использовал свои DLL,
        а не DLL из _internal.
        """

        if os.name != "nt":
            return

        if not hasattr(sys, "_MEIPASS"):
            return

        try:
            ctypes.windll.kernel32.SetDllDirectoryW(None)

            logger.debug(
                "DLL search path PyInstaller временно сброшен перед запуском Poppler"
            )

        except Exception:
            logger.debug(
                "Не удалось сбросить DLL search path PyInstaller",
                exc_info=True
            )

    def _restore_windows_dll_search_path_after_subprocess(self):
        """
        Возвращает DLL search path PyInstaller после запуска внешней программы.
        """

        if os.name != "nt":
            return

        if not hasattr(sys, "_MEIPASS"):
            return

        try:
            ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))

            logger.debug(
                "DLL search path PyInstaller восстановлен после запуска Poppler"
            )

        except Exception:
            logger.debug(
                "Не удалось восстановить DLL search path PyInstaller",
                exc_info=True
            )

    def _get_poppler_executable(
        self,
        poppler_path: Path | None,
        executable_name: str
    ) -> Path | str:
        """
        Возвращает путь к exe-файлу Poppler.

        Если poppler_path задан, ищем exe внутри этой папки.
        Если poppler_path не задан, возвращаем имя команды.
        """

        if poppler_path is None:
            return executable_name

        executable_path = poppler_path / executable_name

        if not executable_path.exists():
            raise FileNotFoundError(
                f"Не найден файл Poppler: {executable_path}"
            )

        return executable_path

    # =========================================================
    # ПУТИ И ВРЕМЕННЫЕ ФАЙЛЫ
    # =========================================================

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

    def _prepare_poppler_path(self, poppler_path) -> Path | None:
        """
        Подготавливает путь к Poppler.
        """

        if poppler_path is None:
            return None

        return Path(poppler_path)

    def _get_temp_pdf_dir(self) -> Path:
        """
        Возвращает временную папку для обработки PDF.
        """

        temp_dir = PROCESSED_DATA_DIR / self.TEMP_PDF_DIR_NAME
        temp_dir.mkdir(parents=True, exist_ok=True)

        return temp_dir

    def _create_temporary_pdf_copy(self, pdf_path: Path) -> Path:
        """
        Создаёт временную копию PDF с простым техническим именем.

        Это защищает обработку PDF от проблем с:
        - кириллицей в пути;
        - длинными путями;
        - пробелами и спецсимволами;
        - путями из облачных папок.
        """

        temp_dir = self._get_temp_pdf_dir()

        temp_file_name = f"pdf_work_{uuid.uuid4().hex}.pdf"
        temp_pdf_path = temp_dir / temp_file_name

        shutil.copy2(pdf_path, temp_pdf_path)

        logger.debug(
            "Создана временная копия PDF. source=%s, temp=%s",
            pdf_path,
            temp_pdf_path
        )

        return temp_pdf_path

    def _delete_temporary_pdf_copy(self, pdf_path: Path | None):
        """
        Удаляет временную копию PDF после обработки.
        """

        self._delete_file_safely(pdf_path)

    def _delete_file_safely(self, file_path: Path | None):
        """
        Безопасно удаляет временный файл.
        """

        if file_path is None:
            return

        try:
            if file_path.exists():
                file_path.unlink()

                logger.debug(
                    "Временный файл удалён: %s",
                    file_path
                )

        except Exception:
            logger.debug(
                "Не удалось удалить временный файл: %s",
                file_path,
                exc_info=True
            )