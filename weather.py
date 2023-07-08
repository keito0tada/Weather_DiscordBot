import datetime
import enum
import os
import zoneinfo

import discord
import psycopg2
import psycopg2.extras
from discord.ext import commands, tasks

from UtilityClasses_DiscordBot import base
from owm.openweathermap import OWM

DATABASE_URL = os.getenv('DATABASE_URL')
ZONE_TOKYO = zoneinfo.ZoneInfo('Asia/Tokyo')
DEFAULT_TIMES = [datetime.time(hour=0, minute=5)]


class WinID(enum.IntEnum):
    MENU = 0
    WEATHER = 1
    FORECAST = 2
    WEATHER_SETTING = 3
    FORECAST_SETTING = 4
    WEATHER_NOTICE_SETTING = 5
    FORECAST_NOTICE_SETTING = 6


class Button(discord.ui.Button):
    def __init__(self, window: base.IWindow, index: WinID, label: str,
                 style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style)
        self.index = index
        self.window = window

    async def callback(self, interaction: discord.Interaction):
        await self.window.response_edit(interaction=interaction, index=self.index)


class WeatherButton(discord.ui.Button):
    def __init__(self, window: base.IWindow, runner: 'Runner'):
        super().__init__(label='現在のお天気', style=discord.ButtonStyle.primary)
        self.window = window
        self.runner = runner

    async def callback(self, interaction: discord.Interaction):
        weather = await self.runner.owm.get_current_weather(lat=35.689, lon=139.692)
        embed_dict = self.window.get_embed_dict(index=WinID.WEATHER)
        embed_dict['title'] = '{}'.format(weather.city.name)
        embed_dict['description'] = '現在{0}時点でのお天気は{1}です。'.format(
                weather.time.strftime('%H時%M分'), weather.conditions[0].description
            )
        embed_dict['thumbnail'] = {'url': weather.get_icon_url()}
        embed_dict['fields'] = [
            {'name': '気温', 'value': '{}°C'.format(weather.main.temperature), 'inline': True},
            {'name': '最高気温', 'value': '{}°C'.format(weather.main.temperature_max), 'inline': True},
            {'name': '最低気温', 'value': '{}°C'.format(weather.main.temperature_min), 'inline': True},
            {'name': '湿度', 'value': '{}%'.format(weather.main.humidity), 'inline': True},
            {'name': '気圧', 'value': '{}hPa'.format(weather.main.pressure), 'inline': True}
        ]
        embed_dict['footer'] = {'text': 'OpenWeatherを参照しています。', 'url': OWM.OPEN_WEATHER_ICON_URL}
        await self.window.response_edit(interaction=interaction, index=WinID.WEATHER)


class ForecastButton(discord.ui.Button):
    def __init__(self, runner: 'Runner'):
        super().__init__(label='天気予報', style=discord.ButtonStyle.primary)
        self.runner = runner

    async def callback(self, interaction: discord.Interaction):
        await self.runner.change_forecast_datetime(interaction=interaction)


class ForecastDatetimeSelect(discord.ui.Select):
    def __init__(self, runner: 'Runner', times: list[datetime.datetime]):
        super().__init__(options=[
            discord.SelectOption(label=time.strftime('%m月%d日%H時%M分'), value=time.isoformat()) for time in times[0:25]
        ])
        self.runner = runner

    async def callback(self, interaction: discord.Interaction):
        await self.runner.change_forecast_datetime(
            interaction=interaction, time=datetime.datetime.fromisoformat(self.values[0]))


class PlaceSelect(discord.ui.Select):
    def __init__(self, runner: 'Runner', places: list[tuple[int, int]]):
        super().__init__(options=[
        ])


class InputPlaceModal(discord.ui.Modal):
    RAT_TEXT = discord.ui.TextInput(label='緯度', required=True)
    LON_TEXT = discord.ui.TextInput(label='経度', required=True)

    def __init__(self):
        super().__init__(title='追加')

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()


class Windows(base.ExWindows):
    def __init__(self, runner: 'Runner'):
        super().__init__(
            windows=(
                base.ExWindow(embed_dict={
                    'title': 'お天気 Bot',
                    'thumbnail': {
                        'url': OWM.OPEN_WEATHER_ICON_WITH_TEXT_URL
                    }
                }, view_items=[
                    WeatherButton(window=self, runner=runner),
                    ForecastButton(runner=runner),
                    Button(window=self, index=WinID.WEATHER_NOTICE_SETTING,
                           label='お天気通知設定', style=discord.ButtonStyle.primary),
                    Button(window=self, index=WinID.FORECAST_NOTICE_SETTING,
                           label='天気予報通知設定', style=discord.ButtonStyle.primary)
                ]),
                base.ExWindow(embed_dict={
                    'title': '', 'description': 'status'
                }, view_items=[
                    Button(window=self, index=WinID.MENU, label='戻る'),
                    Button(window=self, index=WinID.WEATHER_SETTING, label='追加', style=discord.ButtonStyle.primary)
                ]),
                base.ExWindow(embed_dict={
                    'title': 'city name', 'description': 'status'
                }, view_items=[
                    None,
                    Button(window=self, index=WinID.FORECAST_SETTING, label='追加', style=discord.ButtonStyle.primary),
                    Button(window=self, index=WinID.MENU, label='戻る')
                ]),
                base.ExWindow(
                    embed_dict={
                        'title': 'お天気設定', 'description': 'under construction'
                    },
                    view_items=[
                        Button(window=self, index=WinID.WEATHER, label='戻る')
                    ]
                ),
                base.ExWindow(
                    embed_dict={
                        'title': '天気予報設定', 'description': 'under construction'
                    },
                    view_items=[
                        Button(window=self, index=WinID.FORECAST, label='戻る')
                    ]
                ),
                base.ExWindow(
                    embed_dict={
                        'title': 'お天気通知設定', 'description': 'under construction'
                    },
                    view_items=[
                        Button(window=self, index=WinID.MENU, label='戻る')
                    ]
                ),
                base.ExWindow(
                    embed_dict={
                        'title': '天気予報通知設定', 'description': 'under construction'
                    },
                    view_items=[
                        Button(window=self, index=WinID.MENU, label='戻る')
                    ]
                )
            )
        )


class Runner(base.Runner):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(channel=channel)
        self.window: base.IWindow = Windows(runner=self)
        self.owm = OWM()

    async def run(self):
        await self.window.send(sender=self.channel, index=WinID.MENU)

    async def change_forecast_datetime(self, interaction: discord.Interaction,
                                       time: datetime = datetime.datetime.now(tz=ZONE_TOKYO)):
        forecast = await self.owm.get_forecast(lat=35.689, lon=139.692)
        weather = forecast.get_forecast_at(time)
        embed_dict = self.window.get_embed_dict(index=WinID.FORECAST)
        embed_dict['title'] = '{}'.format(weather.city.name)
        embed_dict['description'] = '{0}時点でのお天気は{1}と予測されています。'.format(
            weather.time.strftime('%Y年%m月%d日%H時%M分'), weather.conditions[0].description
        )
        embed_dict['thumbnail'] = {'url': weather.get_icon_url()}
        embed_dict['fields'] = [
            {'name': '気温', 'value': '{}°C'.format(weather.main.temperature), 'inline': True},
            {'name': '最高気温', 'value': '{}°C'.format(weather.main.temperature_max), 'inline': True},
            {'name': '最低気温', 'value': '{}°C'.format(weather.main.temperature_min), 'inline': True},
            {'name': '湿度', 'value': '{}%'.format(weather.main.humidity), 'inline': True},
            {'name': '気圧', 'value': '{}hPa'.format(weather.main.pressure), 'inline': True}
        ]
        embed_dict['footer'] = {'text': 'OpenWeatherを参照しています。', 'url': OWM.OPEN_WEATHER_ICON_URL}
        view_items = self.window.get_view_items(index=WinID.FORECAST)
        view_items[0] = ForecastDatetimeSelect(runner=self, times=forecast.get_datetime_list())
        await self.window.response_edit(interaction=interaction, index=WinID.FORECAST)

    async def add_new_place(self, lat: int, lon: int, interaction: discord.Interaction):
        pass


class Weather(base.Command):
    def __init__(self, bot: discord.ext.commands.Bot):
        super().__init__(bot=bot)
        self.owm = OWM()
        self.database_connector = psycopg2.connect(DATABASE_URL)
        with self.database_connector.cursor() as cur:
            cur.execute(
                'CREATE TABLE IF NOT EXISTS weather (channel_id BIGINT, time TIME, interval INTERVAL, last TIMESTAMP, is_forecast BOOLEAN, lat REAL, lon REAL)'
            )
            self.database_connector.commit()
            cur.execute(
                'SELECT time FROM weather'
            )
            results = cur.fetchall()
            self.database_connector.commit()
        self.notice_weather.change_interval(time=DEFAULT_TIMES + [result[0] for result in results])
        self.notice_weather.start()

    @commands.command()
    async def weather(self, ctx: discord.ext.commands.Context):
        self.runners.append(Runner(channel=ctx.channel))
        await self.runners[len(self.runners) - 1].run()

    async def send_weather(self, channel_id: int, lat: float, lon: float):
        pass

    async def send_forecast(self, channel_id: int, lat: float, lon: float, date: datetime):
        pass

    @tasks.loop(time=DEFAULT_TIMES)
    async def notice_weather(self):
        with self.database_connector.cursor() as cur:
            cur.execute(
                'SELECT channel_id, interval, last, lat, lon FROM weather WHERE %s < time AND time < %s',
                ((datetime.datetime.now() - datetime.timedelta(minutes=1)).time(),
                 (datetime.datetime.now() + datetime.timedelta(minutes=1)).time())
            )
            results = cur.fetchall()
            self.database_connector.commit()
        updates = []
        for result in results:
            if result[1] + datetime.datetime.fromtimestamp(result[2], tz=ZONE_TOKYO) - datetime.timedelta(
                    minutes=1) <= datetime.datetime.now():
                updates.append((result[0], datetime.datetime.now()))
                await self.send_weather(channel_id=result[0], lat=result[3], lon=result[5])
        with self.database_connector.cursor() as cur:
            for update in updates:
                cur.execute(
                    'UPDATE weather SET last = %s WHERE channel_id = %s',
                    (update[1], update[0])
                )


async def setup(bot: discord.ext.commands.Bot):
    await bot.add_cog(Weather(bot=bot))
