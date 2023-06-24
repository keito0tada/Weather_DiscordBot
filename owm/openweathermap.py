import datetime, zoneinfo, json
import aiohttp
import asyncio
import os
import collections
from typing import Optional, Union, Final, NamedTuple

OWM_API_KEY: Final[str] = os.getenv('OWM_API_KEY')
ZONE_TOKYO: Final[zoneinfo.ZoneInfo] = zoneinfo.ZoneInfo('Asia/Tokyo')
with open('lib/current_weather_temp.json', 'r') as f:
    CURRENT_WEATHER_DATA_TEMPLATE: Final[dict] = json.load(f)
with open('lib/forecast_temp.json', 'r') as f:
    FORECAST_DATA_TEMPLATE: Final[dict] = json.load(f)


class Weather:

    class City(NamedTuple):
        lat: Optional[int]
        lon: Optional[int]
        country: Optional[str]
        name: Optional[str]
        sunrise: Optional[datetime.datetime]
        sunset: Optional[datetime.datetime]

    class Condition(NamedTuple):
        id: Optional[int]
        main: Optional[str]
        description: Optional[str]
        icon: Optional[str]

    class Main(NamedTuple):
        temperature: Optional[float]
        feels_like: Optional[float]
        temperature_min: Optional[float]
        temperature_max: Optional[float]
        pressure: Optional[int]
        humidity: Optional[float]
        sea_level: Optional[int]
        ground_level: Optional[int]

    class Wind(NamedTuple):
        speed: Optional[float]
        degrees: Optional[int]
        gust: Optional[float]

    class Rain(NamedTuple):
        an_hour: Optional[float]
        three_hour: Optional[float]

    class Clouds(NamedTuple):
        cloudiness: Optional[float]

    class Snow(NamedTuple):
        an_hour: Optional[float]
        three_hour: Optional[float]

    def __init__(self, city: 'Weather.City', conditions: list['Weather.Condition'], main: 'Weather.Main',
                 wind: 'Weather.Wind', rain: 'Weather.Rain', clouds: 'Weather.Clouds', snow: 'Weather.Snow',
                 time: Optional[datetime.datetime], timezone: Optional[datetime.timezone], visibility: Optional[float],
                 probability: Optional[float]):
        self.city = city
        self.conditions = conditions
        self.main = main
        self.wind = wind
        self.rain = rain
        self.clouds = clouds
        self.snow = snow
        self.time = time
        self.timezone = timezone
        self.visibility = visibility
        self.probability = probability

    def get_icon_url(self):
        return 'https://openweathermap.org/img/wn/{0}@4x.png'.format(self.conditions[0].icon)


class Forecast:
    def __init__(self, weathers: list['Weather']):
        self.weathers = weathers

    def count(self):
        return len(self.weathers)

    def get_datetime_list(self) -> list[datetime.datetime]:
        return sorted([weather.time for weather in self.weathers])

    def get_forecast_at(self, date: datetime.datetime) -> Optional[Weather]:
        if len(self.weathers) == 0:
            return None
        else:
            nearest_weather = self.weathers[0]
            least_timedelta = abs(self.weathers[0].time - date)
            for weather in self.weathers:
                if abs(weather.time - date) < least_timedelta:
                    nearest_weather = weather
                    least_timedelta = abs(weather.time - date)
            return nearest_weather

    def get_forecast_index(self, index: int) -> Optional[Weather]:
        return self.weathers[index]


class OWM:
    OPEN_WEATHER_ICON_URL: Final[
        str] = 'https://openweathermap.org/themes/openweathermap/assets/img/mobile_app/android-app-top-banner.png'
    OPEN_WEATHER_ICON_WITH_TEXT_URL: Final[
        str] = 'https://openweathermap.org/themes/openweathermap/assets/img/logo_white_cropped.png'

    def __init__(self, api_key: str = OWM_API_KEY):
        self.api_key = api_key

    def _fix_dict(self, temp: dict, data: dict):
        fixed: dict[Union[dict, list, str, float, int]] = {}
        for key in temp:
            if key in data:
                if type(temp[key]) == dict and type(data[key]):
                    fixed[key] = self._fix_dict(temp=temp[key], data=data[key])
                elif type(temp[key]) == list and type(data[key]):
                    fixed[key] = self._fix_list(temp=temp[key], data=data[key])
                else:
                    fixed[key] = data[key]
            else:
                fixed[key] = temp[key]
        return fixed

    def _fix_list(self, temp: list, data: list):
        fixed = []
        for datum in data:
            if type(temp[0]) == dict and type(datum) == dict:
                fixed.append(self._fix_dict(temp=temp[0], data=datum))
            elif type(temp[0]) == list and type(datum) == list:
                fixed.append(self._fix_list(temp=temp, data=datum))
            else:
                fixed.append(datum)
        return fixed

    async def get_current_weather(self, lat: float, lon: float):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url='https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ja'.format(
                        lat=lat, lon=lon, api_key=self.api_key)
            ) as response:
                data = await response.json()
        data = self._fix_dict(temp=CURRENT_WEATHER_DATA_TEMPLATE, data=data)
        return Weather(
            city=Weather.City(
                lat=data['coord']['lat'], lon=data['coord']['lon'],
                name=data['name'], country=data['sys']['country'],
                sunrise=datetime.datetime.fromtimestamp(data['sys']['sunrise'], tz=ZONE_TOKYO),
                sunset=datetime.datetime.fromtimestamp(data['sys']['sunset'], tz=ZONE_TOKYO)
            ),
            conditions=[Weather.Condition(
                id=_weather['id'], main=_weather['main'],
                description=_weather['description'], icon=_weather['icon']) for _weather in data['weather']],
            main=Weather.Main(
                temperature=data['main']['temp'], feels_like=data['main']['feels_like'],
                pressure=data['main']['pressure'], humidity=data['main']['humidity'],
                temperature_max=data['main']['temp_max'], temperature_min=data['main']['temp_min'],
                sea_level=data['main']['sea_level'], ground_level=data['main']['grnd_level']
            ),
            visibility=data['visibility'],
            wind=Weather.Wind(
                speed=data['wind']['speed'],
                degrees=data['wind']['deg'],
                gust=data['wind']['gust']
            ),
            clouds=Weather.Clouds(
                cloudiness=data['clouds']['all']
            ),
            rain=Weather.Rain(
                an_hour=data['rain']['1h'],
                three_hour=data['rain']['3h']
            ),
            snow=Weather.Snow(
                an_hour=data['snow']['1h'],
                three_hour=data['snow']['3h']
            ),
            time=datetime.datetime.fromtimestamp(data['dt'], tz=ZONE_TOKYO),
            timezone=datetime.timezone(offset=datetime.timedelta(seconds=data['timezone'])),
            probability=None
        )

    async def get_forecast(self, lat: float, lon: float) -> Forecast:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url='https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ja'.format(
                        lat=lat, lon=lon, api_key=self.api_key
                    )) as response:
                data = await response.json()
        data = self._fix_dict(temp=FORECAST_DATA_TEMPLATE, data=data)
        return Forecast(
            weathers=[Weather(
                city=Weather.City(
                    lat=data['city']['coord']['lat'], lon=data['city']['coord']['lon'],
                    name=data['city']['name'], country=data['city']['country'],
                    sunrise=datetime.datetime.fromtimestamp(data['city']['sunrise'], tz=ZONE_TOKYO),
                    sunset=datetime.datetime.fromtimestamp(data['city']['sunset'], tz=ZONE_TOKYO)
                ),
                conditions=[Weather.Condition(
                    id=_weather['id'], main=_weather['main'],
                    description=_weather['description'], icon=_weather['icon']) for _weather in datum['weather']],
                main=Weather.Main(
                    temperature=datum['main']['temp'], feels_like=datum['main']['feels_like'],
                    pressure=datum['main']['pressure'], humidity=datum['main']['humidity'],
                    temperature_max=datum['main']['temp_max'], temperature_min=datum['main']['temp_min'],
                    sea_level=datum['main']['sea_level'], ground_level=datum['main']['grnd_level']
                ),
                visibility=datum['visibility'],
                wind=Weather.Wind(
                    speed=datum['wind']['speed'],
                    degrees=datum['wind']['deg'],
                    gust=datum['wind']['gust']
                ),
                clouds=Weather.Clouds(
                    cloudiness=datum['clouds']['all']
                ),
                rain=Weather.Rain(
                    an_hour=None,
                    three_hour=datum['rain']['3h']
                ),
                snow=Weather.Snow(
                    an_hour=None,
                    three_hour=datum['snow']['3h']
                ),
                time=datetime.datetime.fromtimestamp(datum['dt'], tz=ZONE_TOKYO),
                timezone=datetime.timezone(offset=datetime.timedelta(seconds=data['city']['timezone'])),
                probability=datum['pop']
            ) for datum in data['list']]
        )

    async def get_weather_map(self):
        pass
