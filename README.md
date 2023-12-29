# Various Home Assistant Things

## AppDaemon

For real. Install Appdaemon and take the time to understand it. A fully working Py environment is so much better to work with than Yaml templating. In all aspects.

https://appdaemon.readthedocs.io/en/latest/index.html

## Open Epaper Displays

https://github.com/jjwbruijn/OpenEPaperLink

https://github.com/jjwbruijn/OpenEPaperLink/wiki

### Nordpool or any Other Input as Charts on Epaper Displays

![Chart examples](nordpools.jpg)

These examples don't need the Epaper integration to be installed, they are pushing images directly to the Epaper access point. 

- [epaper_big_display.py](addon_configs/appdaemon/apps/epaper_big_display.py), renders an image from sensor data to a 400x300 ink display

- [epaper_small_display.py](addon_configs/appdaemon/apps/epaper_small_display.py), renders an image from sensor data to a 296x128 ink display

#### Large Display Examples 
![Big Display example](display_.jpg)

![Big Display example](display_1.jpg)


#### Small Display Example
![Small Display example](display.jpg)

#### Setup

Your AppDaemon instance needs following extra dependencies:

 - `Pillow`
 - `requests`
 - `datetime`

You need the config in the [apps.yaml](addon_configs/appdaemon/apps/apps.yaml) file and the two TTF font files. They should all be placed in the `apps` folder of your Appdaemon setup. Change the config in the head of the classes to match your AP and display MAC.

If you want to manually trigger a re-render, it is easily made with a script in HA that can be executed in the Developer tools Events sections. Add this to `scripts.yaml`:

    alias: Generate small chart to epaper display
    sequence:
      - event: EPAPER_GENERATE_CHART_SMALL

    alias: Generate large chart to epaper display
    sequence:
      - event: EPAPER_GENERATE_CHART_LARGE

Reload the scripts and then the events can be fired in the Events section.

Please note that the epaper AP is not fast and don't like parallel posts! Make sure to run updates in sequence and not in parallel.
