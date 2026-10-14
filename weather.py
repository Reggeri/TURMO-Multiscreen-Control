"""Low-frequency Open-Meteo weather lookup, no API key required."""
import json, threading, time, urllib.parse, urllib.request

WEATHER_CODES={0:'Clear',1:'Mostly clear',2:'Partly cloudy',3:'Cloudy',45:'Fog',48:'Fog',51:'Drizzle',53:'Drizzle',55:'Drizzle',61:'Rain',63:'Rain',65:'Heavy rain',71:'Snow',73:'Snow',75:'Heavy snow',80:'Showers',81:'Showers',82:'Showers',95:'Thunderstorm',96:'Thunderstorm',99:'Thunderstorm'}

def fetch_weather(city):
    query=urllib.parse.urlencode({'name':city,'count':5,'language':'hu','format':'json'})
    with urllib.request.urlopen('https://geocoding-api.open-meteo.com/v1/search?'+query,timeout=8) as response:
        places=json.load(response).get('results') or []
    if not places:raise ValueError('City not found: '+city)
    place=next((p for p in places if p.get('country_code')=='HU'),places[0])
    query=urllib.parse.urlencode({'latitude':place['latitude'],'longitude':place['longitude'],
        'current':'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m',
        'timezone':'auto'})
    with urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?'+query,timeout=8) as response:
        current=json.load(response)['current']
    code=int(current.get('weather_code',-1))
    return {'weather_temp':current.get('temperature_2m'),
            'weather_feels':current.get('apparent_temperature'),
            'weather_humidity':current.get('relative_humidity_2m'),
            'weather_wind':current.get('wind_speed_10m'),
            'weather_condition':WEATHER_CODES.get(code,'Weather'),
            'weather_city':place['name']}

class WeatherService(threading.Thread):
    def __init__(self,stop,events,city):
        super().__init__(daemon=True)
        self.stop,self.events=stop,events
        self.lock=threading.Lock()
        self.city=city.strip()
        self.data={}
        self.wake=threading.Event()
    def set_city(self,city):
        with self.lock:
            self.city=city.strip();self.data={}
        self.wake.set()
    def get(self):
        with self.lock:return dict(self.data)
    def run(self):
        while not self.stop.is_set():
            with self.lock:city=self.city
            if city:
                try:
                    data=fetch_weather(city)
                    with self.lock:
                        if city==self.city:self.data=data
                    self.events.put(('Weather',data['weather_city']+': '+str(data['weather_temp'])+' °C'))
                except Exception as exc:
                    self.events.put(('Weather','Unavailable: '+str(exc)))
            self.wake.wait(900 if city else 3600)
            self.wake.clear()
