from appdaemon.plugins.hass.hassapi import Hass
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import requests

AP_IP = '192.168.3.130'
MAC = '000002B3353A3413'
SENSOR = 'sensor.nordpool_kwh_se3_sek_3_10_025'

IMG_WIDTH = 400
IMG_HEIGHT = 300
CHART_EVENT = 'EPAPER_GENERATE_CHART_LARGE'

class BigDisplayChart(Hass):
    def initialize(self):
        self.listen_event(self.generate_chart, CHART_EVENT)
        t  = datetime.now()
        # round to the next full hour
        t -= timedelta(minutes = t.minute, seconds = t.second, microseconds =  t.microsecond)
        t += timedelta(hours = 1)
        self.log(f'Starting hourly from {t}')
        self.run_every(self.callback, t, 60*60)


    def callback(self, kwargs):
        self.generate_chart(None, None, kwargs)


    def generate_chart(self, event, data, kwargs):
        CHART_HEIGHT = IMG_HEIGHT*0.65
        HOUR_NOW = datetime.now().hour
        VALUES = (self.get_state(SENSOR, 'today')[HOUR_NOW::] + \
                  self.get_state(SENSOR, 'tomorrow'))[:24]

        self.log(f'Values in array: {len(VALUES)}. Values: {VALUES}')

        min_value = min(VALUES) if len(VALUES) > 0 else 0
        max_value = max(VALUES) if len(VALUES) > 0 else 0

        # Calculate span between min and max converted to pixel/unit (ppu)
        ppu = round(CHART_HEIGHT/(max_value), 1) if min_value > 0 else round(CHART_HEIGHT/(max_value-min_value), 1)
        ppu_min = round(min_value*ppu)
        ppu_fraction = lambda p: round(CHART_HEIGHT-(p*ppu))+2 if min_value > 0 else round(CHART_HEIGHT-(p*ppu))+ppu_min+2 #2 pixels for top padding
        ppu_0 = ppu_fraction(0)
        factor_x = round(IMG_WIDTH/len(VALUES))

        iterator_y = map(ppu_fraction, VALUES)
        price_line = []
        price_rect = []

        for k,v in enumerate(iterator_y):
          price_line.append((k*factor_x, v))
          price_line.append((k*factor_x+factor_x, v))
          price_rect.append([(k*factor_x, min(v, ppu_0)), (k*factor_x+factor_x, max(v, ppu_0))])

        image = Image.new('P', (IMG_WIDTH, IMG_HEIGHT))
        palette = [
          255, 255, 255,  # white
            0,   0,   0,  # black
          255,   0,   0   # red
        ]
        image.putpalette(palette)
        draw = ImageDraw.Draw(image)

        FONT_BIG = ImageFont.truetype('/config/apps/Bungee-Regular.ttf', size=46)
        FONT_STD = ImageFont.truetype('/config/apps/FreeMonoBold.ttf', size=16)
        FONT_UPD = ImageFont.truetype('/config/apps/FreeMonoBold.ttf', size=14)

        # Colourize chart
        for (pr, v) in zip(price_rect, VALUES):
          if v > 1:
            draw.rectangle(pr, fill=2)

        draw.line(price_line, fill=1, width=4)

        # x-lines
        y_val = -1
        draw.line([(0, ppu_0), (400, ppu_0)], fill=1, width=1)
        while y_val < max_value:
          y_pos = ppu_fraction(y_val)
          if y_val > min_value and y_val != 0 or y_val > 0:
            draw.line([(0, y_pos), (400, y_pos)], fill=1, width=1)
            draw.text((0, y_pos), f'{round(y_val, 2)}', font=FONT_STD, fill=1, stroke_width=1, stroke_fill=0)
          y_val += 0.25 if ppu > 110 else 0.5 if ppu > 60 else 1

        # y-lines
        for k,v in enumerate(price_line[::4]):
          draw.line([(v[0],ppu_0-10), (v[0], ppu_0)], fill=1, width=1)
          draw.text((v[0], ppu_0), f'{(HOUR_NOW+k*2)%24:02d}', font=FONT_STD, fill=1, stroke_width=1, stroke_fill=0)

        # y-line midnight
        midnight = (24-HOUR_NOW)*factor_x
        mid_y = 0
        while mid_y < CHART_HEIGHT-5:
          draw.line([(midnight, mid_y), (midnight, mid_y+3)], fill=2, width=1)
          mid_y += 8

        # Chart max/min meta data
        fill = lambda v: 1 if v < 1.00 else 2
        val_adj = 80
        lbl_adj = 35
        draw.text((5, IMG_HEIGHT-val_adj), f'{VALUES[0]:.2f}', font=FONT_BIG, fill=fill(VALUES[0]))
        draw.text((7, IMG_HEIGHT-lbl_adj), f'@{HOUR_NOW:02d}', font=FONT_STD, fill=1)
        draw.text((135, IMG_HEIGHT-val_adj), f'{max_value:.2f}', font=FONT_BIG, fill=fill(max_value))
        draw.text((138, IMG_HEIGHT-lbl_adj), f'max', font=FONT_STD, fill=1)
        draw.text((265, IMG_HEIGHT-val_adj), f'{min_value:.2f}', font=FONT_BIG, fill=fill(min_value))
        draw.text((268, IMG_HEIGHT-lbl_adj), f'min', font=FONT_STD, fill=1)

        draw.text((250, IMG_HEIGHT-16), f'{datetime.now().strftime("%y-%m-%d %H.%M")}', font=FONT_UPD, fill=1)

        rgb_image = image.convert('RGB')
        image_path = 'display.jpg'
        rgb_image.save(image_path, 'JPEG', quality="maximum")

        url = "http://" + AP_IP + "/imgupload"
        payload = {"dither": 0, "mac": MAC}
        files = {"file": open(image_path, "rb")}
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
          self.log('INFO: Image uploaded to e-paper AP')
        else:
          self.log('WARNING: Failed to upload image to e-paper AP')
