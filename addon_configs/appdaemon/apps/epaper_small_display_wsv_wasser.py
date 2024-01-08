from appdaemon.plugins.hass.hassapi import Hass
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import requests
import json

AP_IP = '192.168.3.130'
MAC = '0000021C6AB33B12'
# The UUID in the URL below is found at https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json
API_URL = 'https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/a6ee8177-107b-47dd-bcfd-30960ccc6e9c/W/measurements.json?start=P1D'
LEVEL_NORMAL = 6.5
LEVEL_WARNING = 7.08
CHART_LATEST_TO_RIGHT = True

CHART_EVENT = 'EPAPER_GENERATE_CHART_WSV_WASSER'
SECONDS_DELAY_TO_NOT_CHOKE_THE_POOR_AP = 90
SEND_DATA_TO_HA_AS_SENSOR = False
IMG_WIDTH = 296
IMG_HEIGHT = 128

class SmallDisplayChartWsvWasser(Hass):
    def initialize(self):
        self.listen_event(self.generate_chart, CHART_EVENT)
        t  = datetime.now()
        # round to the next full hour
        t -= timedelta(minutes = t.minute, seconds = t.second, microseconds =  t.microsecond)
        t += timedelta(hours = 1, seconds=SECONDS_DELAY_TO_NOT_CHOKE_THE_POOR_AP)
        self.log(f'Starting hourly from {t}')
        self.run_every(self.callback, t, 60*60)

    def run_me(self):
      self.generate_chart(None, None, None)

    def callback(self, kwargs):
        self.generate_chart(None, None, kwargs)

    def fetch_api(self, url):
        try:
          resp = requests.get(url)
          response = json.loads(resp.text)
          if SEND_DATA_TO_HA_AS_SENSOR:
            last_value = response[-1]
            self.set_state(f'sensor.{self.__class__.__name__}', state = last_value['value'],
                attributes = {'measurement_time': last_value['timestamp'], 
                              'from': CHART_EVENT, 
                              'device_class': 'measurement',
                              'friendly_name': f'Water Level {self.__class__.__name__}'})
          return response
        except requests.exceptions.RequestException as e:
          return []
    
    def reduce_to_hourly_values(self, json_arr):
        reduced = [x['value']/100 for x in json_arr[-1::-4]]
        if CHART_LATEST_TO_RIGHT: reduced.reverse()
        return reduced

    def generate_chart(self, event, data, kwargs):
        CHART_WIDTH = IMG_WIDTH*0.741
        CHART_HEIGHT = IMG_HEIGHT*0.85
        HOUR_NOW = datetime.now().hour
        FULL_DATA = self.fetch_api(API_URL)
        VALUES = self.reduce_to_hourly_values(FULL_DATA)

        self.log(f'Values in array: {len(VALUES)}. Values: {VALUES}')

        min_value = min(VALUES) if len(VALUES) > 0 else 0
        max_value = max(VALUES) if len(VALUES) > 0 else 0

        # Calculate span between min and max converted to pixel/unit (ppu)
        ppu = round(CHART_HEIGHT/(max_value-LEVEL_NORMAL), 2) if min_value > 0 else round(CHART_HEIGHT/(max_value-min_value), 2)
        ppu_min = round(min_value*ppu)
        ppu_fraction = lambda p: round(CHART_HEIGHT-(p-LEVEL_NORMAL)*ppu)+2 if min_value > 0 else round(CHART_HEIGHT-p*ppu)+ppu_min+2 #2 pixels for top padding
        ppu_0 = ppu_fraction(LEVEL_NORMAL)
        factor_x = round(CHART_WIDTH/len(VALUES))

        iterator_y = map(ppu_fraction, VALUES)
        value_line = []
        value_rect = []

        for k,v in enumerate(iterator_y):
          value_line.append((k*factor_x, v))
          value_line.append((k*factor_x+factor_x, v))
          value_rect.append([(k*factor_x, min(v, ppu_0)), (k*factor_x+factor_x, max(v, ppu_0))])

        image = Image.new('P', (IMG_WIDTH, IMG_HEIGHT))
        palette = [
          255, 255, 255,  # white
            0,   0,   0,  # black
          255,   0,   0   # red
        ]
        image.putpalette(palette)
        draw = ImageDraw.Draw(image)

        FONT_BIG = ImageFont.truetype('/config/apps/Bungee-Regular.ttf', size=24)
        FONT_STD = ImageFont.truetype('/config/apps/FreeMonoBold.ttf', size=12)
        FONT_UPD = ImageFont.truetype('/config/apps/FreeMonoBold.ttf', size=10)

        # Colourize chart
        for (pr, v) in zip(value_rect, VALUES):
          if v > LEVEL_WARNING:
            draw.rectangle(pr, fill=2)

        draw.line(value_line, fill=1, width=4)

        # x-lines
        y_val = -1
        draw.line([(0, ppu_0), (CHART_WIDTH, ppu_0)], fill=1, width=1)
        while y_val < max_value:
          y_pos = ppu_fraction(y_val)
          if y_val > min_value and y_val != LEVEL_NORMAL or y_val > LEVEL_NORMAL:
            draw.line([(0, y_pos), (CHART_WIDTH, y_pos)], fill=1, width=1)
            draw.text((0, y_pos), f'{round(y_val, 2)}', font=FONT_STD, fill=1, stroke_width=1, stroke_fill=0)
          y_val += 0.25 if ppu > 110 else 0.5 if ppu > 60 else 1

        # y-lines
        start_hour = HOUR_NOW-len(value_line[::2]) if CHART_LATEST_TO_RIGHT else HOUR_NOW
        direction = 1 if CHART_LATEST_TO_RIGHT else -1
        for k,v in enumerate(value_line[::4]):
          draw.line([(v[0],ppu_0-10), (v[0], ppu_0)], fill=1, width=1)
          draw.text((v[0], ppu_0), f'{(start_hour+(direction*k)*2)%24:02d}', font=FONT_STD, fill=1, stroke_width=1, stroke_fill=0)

        # y-line midnight
        midnight = (24-HOUR_NOW)*factor_x if CHART_LATEST_TO_RIGHT else HOUR_NOW*factor_x
        mid_y = 0
        while mid_y < CHART_HEIGHT-5:
          draw.line([(midnight, mid_y), (midnight, mid_y+3)], fill=2, width=1)
          mid_y += 8

        # Chart max/min meta data
        fill = lambda v: 1 if v < LEVEL_WARNING else 2
        start_x = IMG_WIDTH*0.76
        start_y = IMG_HEIGHT*0.04
        val_adj = 36
        lbl_adj = 20
        last_val = VALUES[-1] if CHART_LATEST_TO_RIGHT else VALUES[0]
        draw.text((start_x, start_y), f'{last_val:.2f}', font=FONT_BIG, fill=fill(last_val))
        draw.text((start_x, start_y+lbl_adj), f'@{HOUR_NOW:02d}', font=FONT_STD, fill=1)
        draw.text((start_x, start_y+val_adj), f'{max_value:.2f}', font=FONT_BIG, fill=fill(max_value))
        draw.text((start_x, start_y+val_adj+lbl_adj), f'max', font=FONT_STD, fill=1)
        draw.text((start_x, start_y+2*val_adj), f'{min_value:.2f}', font=FONT_BIG, fill=fill(min_value))
        draw.text((start_x, start_y+2*val_adj+lbl_adj), f'min', font=FONT_STD, fill=1)

        draw.text((IMG_WIDTH-36, IMG_HEIGHT-12), f'{datetime.now().strftime("%H:%M")}', font=FONT_UPD, fill=1)

        rgb_image = image.convert('RGB')
        image_path = f'{CHART_EVENT}_display_small.jpg'
        rgb_image.save(image_path, 'JPEG', quality="maximum")

        url = "http://" + AP_IP + "/imgupload"
        payload = {"dither": 0, "mac": MAC}
        files = {"file": open(image_path, "rb")}
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
          self.log('INFO: Image uploaded to e-paper AP')
        else:
          self.log('WARNING: Failed to upload image to e-paper AP')
