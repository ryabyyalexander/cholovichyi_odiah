# enums/weather_enums.py
from enum import Enum

class Weather(str, Enum):
    SUNNY_1 = "sunny_1"
    SUNNY_2 = "sunny_2"
    SUNNY_3 = "sunny_3"
    PARTLY_CLOUDY_1 = "partly_cloudy_1"
    PARTLY_CLOUDY_2 = "partly_cloudy_2"
    CLOUDY_1 = "cloudy_1"
    CLOUDY_2 = "cloudy_2"
    LIGHT_RAIN = "light_rain"
    RAIN = "rain"
    THUNDERSTORM = "thunderstorm"
    LIGHTNING = "lightning"
    SNOW = "snow"
    SNOW_1 = "snow_1"
    SNOW_2 = "snow_2"
    SNOW_3 = "snow_3"

    @property
    def label(self) -> str:
        return {
            Weather.SUNNY_1: "Сонячно (1 сонце)",
            Weather.SUNNY_2: "Сонячно (2 сонця)",
            Weather.SUNNY_3: "Сонячно (3 сонця)",
            Weather.PARTLY_CLOUDY_1: "Невелика хмарність 1",
            Weather.PARTLY_CLOUDY_2: "Невелика хмарність 2",
            Weather.CLOUDY_1: "Хмарно 1",
            Weather.CLOUDY_2: "Хмарно 2",
            Weather.LIGHT_RAIN: "Невеликий дощ",
            Weather.RAIN: "Дощ",
            Weather.THUNDERSTORM: "Гроза",
            Weather.LIGHTNING: "Блискавка",
            Weather.SNOW: "Сніг",
            Weather.SNOW_1: "Сніг (1 сніжинка)",
            Weather.SNOW_2: "Сніг (2 сніжинки)",
            Weather.SNOW_3: "Сніг (3 сніжинки)",
        }[self]

    @property
    def emoji(self) -> str:
        return {
            Weather.SUNNY_1: "☀️",
            Weather.SUNNY_2: "☀️☀️",
            Weather.SUNNY_3: "☀️☀️☀️",
            Weather.PARTLY_CLOUDY_1: "🌤",
            Weather.PARTLY_CLOUDY_2: "⛅️",
            Weather.CLOUDY_1: "🌥",
            Weather.CLOUDY_2: "☁️",
            Weather.LIGHT_RAIN: "🌦",
            Weather.RAIN: "🌧",
            Weather.THUNDERSTORM: "⛈",
            Weather.LIGHTNING: "🌩",
            Weather.SNOW: "🌨",
            Weather.SNOW_1: "❄️",
            Weather.SNOW_2: "❄️❄️",
            Weather.SNOW_3: "❄️❄️❄️",
        }[self]