"""Автоматическая классификация документов при загрузке в базу знаний.

Определяет метаданные из текста документа БЕЗ ИИ — регулярными выражениями
и словарями маркеров. Это базовая версия, которую легко расширять на реальных
данных.

Определяет:
  - doc_type:      "judicial_practice" | "law" | "other"
  - year:          год решения суда (для законов = None)
  - court_level:   "arbitration" | "general" | None
  - case_number:   номер дела (для судебных решений)
"""
import re
from dataclasses import dataclass


@dataclass
class DocumentMetadata:
    """Метаданные документа, извлечённые из текста."""

    doc_type: str  # "judicial_practice" | "law" | "other"
    year: int | None
    court_level: str | None  # "arbitration" | "general" | None
    case_number: str | None


# ============================================================
#  Паттерны — вынесены в константы для лёгкого расширения
# ============================================================

# --- Номера дел арбитражных судов ---
# Формат: А40-12345/2021, А40-12345/2021 (буква А + 2 цифры региона)
ARBITRATION_CASE_RE = re.compile(
    r"\b([АA]\d{2,3}[-\s]?\d{1,7}/\d{4})\b"
)

# --- Маркеры арбитражного суда в тексте ---
ARBITRATION_MARKERS = [
    "арбитражный суд",
    "арбитражного суда",
    "арбитражным судом",
    "девятый арбитражный",
    "десятый арбитражный",
    "аа с",  # сокращения типа «ААС»
    "аао",  # Арбитражный апелляционный округ
    "в арбитражный суд",
]

# --- Маркеры судов общей юрисдикции ---
GENERAL_COURT_MARKERS = [
    "районный суд",
    "городской суд",
    "областной суд",
    "краевой суд",
    "верховный суд",
    "мировой суд",
    "судебный участок",
    "судья ",
    "районном суде",
    "областного суда",
]

# --- Маркеры судебного решения (для определения doc_type) ---
JUDICIAL_DOC_MARKERS = [
    "постановление",
    "решение суда",
    "решение по делу",
    "определение суда",
    "судебный акт",
    "апелляционное определение",
    "кассационное определение",
    "надзорное определение",
    "резолютивная часть",
]

# --- Маркеры закона/кодекса ---
LAW_MARKERS = [
    "гражданский кодекс",
    "налоговый кодекс",
    "уголовный кодекс",
    "трудовой кодекс",
    "жилищный кодекс",
    "семейный кодекс",
    "кодекс российской федерации",
    "федеральный закон",
]

# --- Паттерны даты ---
# «от 12 мая 2021 года», «от 12 мая 2021 г.»
DATE_TEXT_RE = re.compile(
    r"от\s+(\d{1,2})\s+"
    r"(января|февраля|марта|апреля|мая|июня|июля|"
    r"августа|сентября|октября|ноября|декабря)\s+"
    r"(20\d{2})",
    re.IGNORECASE,
)

# «от 12.05.2021», «от 12.05.2021 г.»
DATE_NUMERIC_RE = re.compile(
    r"(?:от|от\s+|\s)(\d{1,2})[./](\d{1,2})[./](20\d{2})"
)

# «/2021» в номере дела (например А40-12345/2021)
CASE_YEAR_RE = re.compile(r"/(\d{4})")


# Словарь месяцев для валидации
_MONTHS_MAX = {
    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


def extract_metadata(text: str, file_name: str = "") -> DocumentMetadata:
    """Извлечь метаданные из текста документа.

    Порядок определения:
      1. case_number (по номеру дела арбитража — самый надёжный сигнал)
      2. court_level (маркеры + номер дела)
      3. doc_type (маркеры судебного решения vs закона)
      4. year (дата решения или год из номера дела)
    """
    text_lower = text.lower()
    # Ограничиваем анализ первыми ~5000 символов — метаданные в начале документа
    head = text_lower[:5000]

    # 1. Номер дела
    case_number = _find_case_number(text)

    # 2. Тип суда
    court_level = _determine_court_level(head, case_number)

    # 3. Тип документа
    doc_type = _determine_doc_type(head, file_name, case_number, court_level)

    # 4. Год решения (только для судебной практики)
    year = None
    if doc_type == "judicial_practice":
        year = _find_year(text, case_number)

    return DocumentMetadata(
        doc_type=doc_type,
        year=year,
        court_level=court_level if doc_type == "judicial_practice" else None,
        case_number=case_number if doc_type == "judicial_practice" else None,
    )


def _find_case_number(text: str) -> str | None:
    """Найти номер дела арбитражного суда."""
    match = ARBITRATION_CASE_RE.search(text)
    if match:
        # Нормализуем: убираем пробелы
        return re.sub(r"\s+", "-", match.group(1).strip())
    return None


def _determine_court_level(head: str, case_number: str | None) -> str | None:
    """Определить тип суда: arbitration | general | None."""
    # Номер дела арбитража — самый сильный сигнал
    if case_number:
        return "arbitration"

    # Маркеры арбитража
    for marker in ARBITRATION_MARKERS:
        if marker in head:
            return "arbitration"

    # Маркеры общей юрисдикции
    for marker in GENERAL_COURT_MARKERS:
        if marker in head:
            return "general"

    return None


def _determine_doc_type(
    head: str,
    file_name: str,
    case_number: str | None,
    court_level: str | None,
) -> str:
    """Определить тип документа: judicial_practice | law | other."""
    name_lower = file_name.lower()

    # По имени файла — быстрые проверки
    if any(m in name_lower for m in ("гк рф", "гражданский кодекс")):
        return "law"
    if any(m in name_lower for m in ("нк рф", "налоговый кодекс")):
        return "law"
    if any(m in name_lower for m in ("ук рф", "уголовный кодекс")):
        return "law"

    # Если есть номер дела или маркеры суда — это судебная практика
    if case_number or court_level:
        return "judicial_practice"

    # Маркеры судебного решения в тексте
    for marker in JUDICIAL_DOC_MARKERS:
        if marker in head:
            return "judicial_practice"

    # Маркеры закона/кодекса
    for marker in LAW_MARKERS:
        if marker in head:
            return "law"

    return "other"


def _find_year(text: str, case_number: str | None) -> int | None:
    """Найти год судебного решения."""
    # Сначала ищем полную дату «от DD месяц YYYY» или «от DD.MM.YYYY»
    match = DATE_TEXT_RE.search(text)
    if match:
        year = int(match.group(3))
        month = _month_name_to_num(match.group(2))
        day = int(match.group(1))
        if _is_valid_date(day, month, year):
            return year

    match = DATE_NUMERIC_RE.search(text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        if _is_valid_date(day, month, year):
            return year

    # Год из номера дела арбитража: А40-12345/2021 → 2021
    if case_number:
        match = CASE_YEAR_RE.search(case_number)
        if match:
            return int(match.group(1))

    return None


def _month_name_to_num(name: str) -> int:
    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }
    return months.get(name.lower(), 0)


def _is_valid_date(day: int, month: int, year: int) -> bool:
    if month < 1 or month > 12:
        return False
    if day < 1 or day > _MONTHS_MAX.get(month, 31):
        return False
    if year < 2000 or year > 2030:
        return False
    return True
