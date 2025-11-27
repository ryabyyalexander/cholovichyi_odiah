from enums.base_enum import BaseCategoryEnum

class JacketSizes(BaseCategoryEnum):
    """
    Размеры для курток и верхней одежды
    """
    SIZE_46 = "46"
    SIZE_48 = "48"
    SIZE_50 = "50"
    SIZE_52 = "52"
    SIZE_54 = "54"
    SIZE_56 = "56"
    SIZE_58 = "58"
    SIZE_60 = "60"

    @property
    def label(self) -> str:
        return {
            JacketSizes.SIZE_46: " 46",
            JacketSizes.SIZE_48: " 48",
            JacketSizes.SIZE_50: " 50",
            JacketSizes.SIZE_52: " 52",
            JacketSizes.SIZE_54: " 54",
            JacketSizes.SIZE_56: " 56",
            JacketSizes.SIZE_58: " 58",
            JacketSizes.SIZE_60: " 60"
        }[self]

    @property
    def emoji(self) -> str:
        return "🧥"  # Общая иконка для всех размеров


class JerseySizes(BaseCategoryEnum):
    """
    Размеры для трикотажа и футболок
    """
    XS = "xs"
    S = "s"
    M = "m"
    L = "l"
    XL = "xl"
    XXL = "2xl"
    XXXL = "3xl"
    XXXXL = "4xl"
    one_size = "one size"

    @property
    def label(self) -> str:
        return {
            JerseySizes.XS: " XS",
            JerseySizes.S: " S",
            JerseySizes.M: " M",
            JerseySizes.L: " L",
            JerseySizes.XL: " XL",
            JerseySizes.XXL: " 2XL",
            JerseySizes.XXXL: " 3XL",
            JerseySizes.XXXXL: " 4XL",
            JerseySizes.one_size: " one size"
        }[self]

    @property
    def emoji(self) -> str:
        return "👕"  # Иконка футболки для размеров


class JeansSizes(BaseCategoryEnum):
    """
    Размеры для джинсов и брюк
    """
    SIZE_31 = "31"
    SIZE_32 = "32"
    SIZE_33 = "33"
    SIZE_34 = "34"
    SIZE_35 = "35"
    SIZE_36 = "36"
    SIZE_38 = "38"
    SIZE_40 = "40"
    SIZE_42 = "42"

    @property
    def label(self) -> str:
        return {
            JeansSizes.SIZE_31: " 31",
            JeansSizes.SIZE_32: " 32",
            JeansSizes.SIZE_33: " 33",
            JeansSizes.SIZE_34: " 34",
            JeansSizes.SIZE_35: " 35",
            JeansSizes.SIZE_36: " 36",
            JeansSizes.SIZE_38: " 38",
            JeansSizes.SIZE_40: " 40",
            JeansSizes.SIZE_42: " 42"
        }[self]

    @property
    def emoji(self) -> str:
        return "👖"  # Иконка джинсов для размеров


class Size(BaseCategoryEnum):
    """
    Общий Enum для всех размеров
    """
    # Jacket sizes
    SIZE_46 = "46"
    SIZE_48 = "48"
    SIZE_50 = "50"
    SIZE_52 = "52"
    SIZE_54 = "54"
    SIZE_56 = "56"
    SIZE_58 = "58"
    SIZE_60 = "60"
    # Jersey sizes
    XS = "xs"
    S = "s"
    M = "m"
    L = "l"
    XL = "xl"
    XXL = "2xl"
    XXXL = "3xl"
    XXXXL = "4xl"
    one_size = "one size"
    # Jeans sizes
    SIZE_31 = "31"
    SIZE_32 = "32"
    SIZE_33 = "33"
    SIZE_34 = "34"
    SIZE_35 = "35"
    SIZE_36 = "36"
    SIZE_38 = "38"
    SIZE_40 = "40"
    SIZE_42 = "42"

    @property
    def label(self) -> str:
        return self.value

    @property
    def emoji(self) -> str:
        return ""
