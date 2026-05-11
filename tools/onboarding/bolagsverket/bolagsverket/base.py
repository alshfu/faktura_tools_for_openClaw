"""
bolagsverket.base
-----------------
Абстрактный базовый класс для всех клиентов библиотеки.
Определяет общий интерфейс независимо от источника данных.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AnnualReport, Company


class BaseCompanyClient(ABC):
    """
    Абстрактный клиент для получения данных о шведских компаниях.

    Реализации:
        BolagsverketClient  — официальный API (требует OAuth2-ключи)
        MackAnClient        — прокси без ключей (mackan.eu)

    Все методы возвращают одни и те же модели данных.
    """

    @abstractmethod
    def get_company(self, orgnr: str, include_docs: bool = False) -> Company:
        """
        Получить полную информацию о компании.

        Параметры:
            orgnr        — organisationsnummer (10 цифр, дефисы допустимы)
            include_docs — включить список годовых отчётов

        Возвращает:
            Company

        Raises:
            ValidationError / NotFoundError / RateLimitError / ApiError
        """

    @abstractmethod
    def get_documents(self, orgnr: str) -> list[AnnualReport]:
        """
        Получить список годовых отчётов компании.

        Параметры:
            orgnr — organisationsnummer

        Возвращает:
            list[AnnualReport]
        """

    def is_construction_company(self, orgnr: str) -> bool:
        """Проверить, относится ли компания к строительной отрасли (SNI 41–43)."""
        return self.get_company(orgnr).is_construction

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Название источника данных (для логирования и метаданных)."""
