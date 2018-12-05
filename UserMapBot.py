#!/usr/bin/env python3
import json
import logging
import requests
import re
from requests.compat import urljoin
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode, error

import database as db

### configuration

with open('config.json') as fd:
    config = json.load(fd)

logging.basicConfig(
    filename = config['log_file'],
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level = logging.INFO,
)

db.initialize(config['database_file'])

with open('l10n.json') as fd:
    l10n = json.load(fd)

### Utililty functions

def parse_location(location):
    url = urljoin(config['DSTK_URL'], '/maps/api/geocode/json')
    payload = {'address' : location}
    r = requests.get(url, params=payload)
    results = r.json()['results']
    if results:
        geo = results[0]['geometry']['location']
        return geo['lat'], geo['lng']
    else:
        return None

def parse_geo(lat, lng):
    url = urljoin(config['DSTK_URL'], 'coordinates2politics/{},{}'.format(lat, lng))
    r = requests.get(url)
    results = r.json()
    if results:
        return results[0]['politics'][-1]['name']
    else:
        return ''

def export():
    fname = config['export_file']
    if fname.endswith('.csv'):
        db.export_csv(fname)
    elif fname.endswith('.json'):
        db.export_geojson(fname)

def send_message(bot, update, text, **kwargs):
    """Wrapper for bot.send_message. Try to send to User first."""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    try:
        bot.send_message(user_id, text, **kwargs)
    except error.Unauthorized:
        text += gettext('hint').format(botname=bot.username)
        bot.send_message(chat_id, text, **kwargs)

def gettext(key):
    text = l10n[key].get(config['lang'])
    if not text:
        # fallback to en
        text = l10n[key].get('en')
    return text

### Authorizing with Telegram Bot API

updater = Updater(token=config['BOT_TOKEN'])
dispatcher = updater.dispatcher

### Define Bot Commands

def start(bot, update):
    send_message(bot, update, gettext('start'), parse_mode=ParseMode.MARKDOWN)

def intro(bot, update):
    text = gettext('intro').format(username=bot.username, map=config['map_url'])
    bot.send_message(update.message.chat_id, text, parse_mode=ParseMode.MARKDOWN)

def show_help(bot, update):
    send_message(bot, update, gettext('help'), parse_mode=ParseMode.MARKDOWN)

def region(bot, update):

    location = update.message.text[8:]   # cut '/region '

    if not location:
        send_message(bot, update, gettext('region_help'), parse_mode=ParseMode.MARKDOWN)
        return

    geo = parse_location(location)

    if geo:
        lat, lng = geo
        db.set_location(update.message.from_user.id, location, lat, lng)
        text = gettext('region_success').format(loc=location)
        send_message(bot, update, text, parse_mode=ParseMode.MARKDOWN)
        export()
    else:
        text = gettext('region_error').format(loc=location)
        send_message(bot, update, text)

def geo(bot, update):

    cmd = update.message.text.split()
    coord = update.message.text[5:]     # cut '/geo '
    match = re.match('(\d*\.\d*)[^\d\.]*(\d*\.\d*)', coord)

    if match:
        lat, lng = match.groups()
        location = parse_geo(lat, lng)
        db.set_location(update.message.from_user.id, location, lat, lng)
        text = gettext('geo_success').format(lat=lat, lng=lng, loc=location)
        send_message(bot, update, text, parse_mode=ParseMode.MARKDOWN)
        export()

    else:
        send_message(bot, update, gettext('geo_help'))

def show_map(bot, update):
    send_message(bot, update, config['map_url'])

def get(bot, update):
    user = db.get_user(update.message.from_user.id)
    if user:
        text = gettext('get_found').format(
            loc = user.location,
            lat = user.lat,
            lng = user.lng,
            time = user.lastupdated.strftime('%Y-%m-%d %H:%M')
        )
    else:
        text = gettext('get_notfound')
    send_message(bot, update, text)

def delete(bot, update):
    db.delete_user(update.message.from_user.id)
    send_message(bot, update, gettext('delete'))
    export()

def unknown(bot, update):
    send_message(bot, update, gettext('unkown'))

### Register Handlers

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

intro_handler = CommandHandler('intro', intro)
dispatcher.add_handler(intro_handler)

help_handler = CommandHandler('help', show_help)
dispatcher.add_handler(help_handler)

region_handler = CommandHandler('region', region)
dispatcher.add_handler(region_handler)

geo_handler = CommandHandler('geo', geo)
dispatcher.add_handler(geo_handler)

get_handler = CommandHandler('get', get)
dispatcher.add_handler(get_handler)

delete_handler = CommandHandler('delete', delete)
dispatcher.add_handler(delete_handler)

map_handler = CommandHandler('map', show_map)
dispatcher.add_handler(map_handler)

unknown_handler = MessageHandler(Filters.command, unknown)
dispatcher.add_handler(unknown_handler)

### Run

print('bot initialized')
updater.start_polling()

### On exit
logging.shutdown()

