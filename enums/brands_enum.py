# enums/brands_enum.py
from enums.base_enum import BaseCategoryEnum

class Brands(BaseCategoryEnum):
    """
    Enum для брендов одежды.
    """
    ALBERTO = "Alberto"
    MILESTONE = "Milestone"
    CASA_MODA = "Casa Moda"
    IMPULSO = "Impulso"
    MONTECHIARO = "Montechiaro"
    LORENZONI = "Lorenzoni"
    RED_POINT = "Red Point"
    MARINA = "Marina Militare"
    R2 = "R2 Amsterdam"

    @property
    def label(self) -> str:
        return {
            Brands.ALBERTO: "Alberto",
            Brands.MILESTONE: "Milestone",
            Brands.LORENZONI: "Lorenzoni",
            Brands.IMPULSO: "Impulso",
            Brands.MONTECHIARO: "Montechiaro",
            Brands.CASA_MODA: "Casa Moda",
            Brands.RED_POINT: "Red Point",
            Brands.MARINA: "Marina Militare",
            Brands.R2: "R2 Amsterdam"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            Brands.ALBERTO: "",
            Brands.MILESTONE: "",
            Brands.IMPULSO: "",
            Brands.LORENZONI: "",
            Brands.MONTECHIARO: "",
            Brands.CASA_MODA: "",
            Brands.RED_POINT: "",
            Brands.MARINA: "",
            Brands.R2: ""
        }[self]
