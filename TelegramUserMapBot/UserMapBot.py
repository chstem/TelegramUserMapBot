#!/usr/bin/env python3
import os
import sys
import json
import logging
import re
import requests
from requests.compat import urljoin
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode, error
from types import SimpleNamespace
from pkg_resources import resource_filename

import TelegramUserMapBot.Database as db


class UserMapBot:
    __CONFIG_DIR = '/etc/TelegramUserMapBot'
    CONFIG_DEFAULT = __CONFIG_DIR + '/config.json'

    __L10N_FILE = resource_filename(__name__, "l10n.json")

    def __init__(self, config):

        with open(config) as fd:
            config = json.load(fd)

        self.config = SimpleNamespace(**config)

        # localization
        with open(self.__L10N_FILE) as fd:
            self.l10n = json.load(fd)

        # local database
        self.db = db.UserDatabase(self.config.database_file)
        # authorizing with Telegram Bot API
        self.updater = Updater(token=self.config.BOT_TOKEN)
        self.dispatcher = self.updater.dispatcher

        # logging
        logging.basicConfig(
            filename = self.config.log_file,
            format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level = logging.INFO,
        )

        # register handlers
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        intro_handler = CommandHandler('intro', self.intro)
        self.dispatcher.add_handler(intro_handler)

        help_handler = CommandHandler('help', self.show_help)
        self.dispatcher.add_handler(help_handler)

        region_handler = CommandHandler('region', self.region)
        self.dispatcher.add_handler(region_handler)

        geo_handler = CommandHandler('geo', self.geo)
        self.dispatcher.add_handler(geo_handler)

        get_handler = CommandHandler('get', self.get)
        self.dispatcher.add_handler(get_handler)

        delete_handler = CommandHandler('delete', self.delete)
        self.dispatcher.add_handler(delete_handler)

        map_handler = CommandHandler('map', self.show_map)
        self.dispatcher.add_handler(map_handler)

        unknown_handler = MessageHandler(Filters.command, self.unknown)
        self.dispatcher.add_handler(unknown_handler)

    def run(self):
        self.updater.start_polling()

    def stop(self):
        self.updater.stop()

    def __del__(self):
        self.stop()
        logging.shutdown()

    ### utililty functions

    def parse_location(self, location):
        url = urljoin(self.config.DSTK_URL, '/maps/api/geocode/json')
        payload = {'address' : location}
        r = requests.get(url, params=payload)
        results = r.json()['results']
        if results:
            geo = results[0]['geometry']['location']
            return geo['lat'], geo['lng']
        else:
            return None

    def parse_geo(self, lat, lng):
        url = urljoin(self.config.DSTK_URL, 'coordinates2politics/{},{}'.format(lat,lng))
        r = requests.get(url)
        results = r.json()
        if results:
            return results[0]['politics'][-1]['name']
        else:
            return ''

    def export(self, fname=''):
        if not fname:
            fname = self.config.export_file
        if fname.endswith('.csv'):
            self.db.export_csv(fname)
        elif fname.endswith('.json'):
            self.db.export_geojson(fname)

    def send_message(self, bot, update, text, **kwargs):
        """Wrapper for bot.send_message. Try to send to user first, then to orignal channel."""
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        try:
            bot.send_message(user_id, text, **kwargs)
        except error.Unauthorized:
            text += self.gettext('hint').format(botname=bot.username)
            bot.send_message(chat_id, text, **kwargs)

    def gettext(self, key):
        text = self.l10n[key].get(self.config.lang)
        if not text:
            # fallback to en
            text = self.l10n[key].get('en')
        return text

    ### define bot commands

    def start(self, bot, update):
        self.send_message(bot, update, self.gettext('start'), parse_mode=ParseMode.MARKDOWN)

    def intro(self, bot, update):
        text = self.gettext('intro').format(username=bot.username, map=self.config.map_url)
        bot.send_message(update.message.chat_id, text, parse_mode=ParseMode.MARKDOWN)

    def show_help(self, bot, update):
        self.send_message(bot, update, self.gettext('help'), parse_mode=ParseMode.MARKDOWN)

    def region(self, bot, update):

        i = update.message.text.find(' ')
        location = update.message.text[i+1:]   # everything after first space

        if not location:
            self.send_message(bot, update,
                              self.gettext('region_help'), parse_mode=ParseMode.MARKDOWN)
            return

        geo = self.parse_location(location)

        if geo:
            lat, lng = geo
            self.db.set_location(update.message.from_user.id, location, lat, lng)
            text = self.gettext('region_success').format(loc=location)
            self.send_message(bot, update, text, parse_mode=ParseMode.MARKDOWN)
            self.export()
        else:
            text = self.gettext('region_error').format(loc=location)
            self.send_message(bot, update, text)

    def geo(self, bot, update):

        cmd = update.message.text.split()
        coord = update.message.text[5:]     # cut '/geo '
        match = re.match('(\d*\.\d*)[^\d\.]+(\d*\.\d*)', coord)
        if not match:
            # try ',' as decimal separator
            match = re.match('(\d*,\d*)[^\d,]+(\d*,\d*)', coord)

        if match:
            try:
                lat, lng = match.groups()
                if ',' in lat:
                    lat = lat.replace(',', '.')
                    lng = lng.replace(',', '.')
                location = self.parse_geo(lat, lng)
            except:
                self.send_message(bot, update, self.gettext('geo_help'))
                raise

            self.db.set_location(update.message.from_user.id, location, lat, lng)
            text = self.gettext('geo_success').format(lat=lat, lng=lng, loc=location)
            self.send_message(bot, update, text, parse_mode=ParseMode.MARKDOWN)
            self.export()

        else:
            self.send_message(bot, update, self.gettext('geo_help'))

    def show_map(self, bot, update):
        self.send_message(bot, update, self.config.map_url)

    def get(self, bot, update):
        user = self.db.get_user(update.message.from_user.id)
        if user:
            text = self.gettext('get_found').format(
                loc = user.location,
                lat = user.lat,
                lng = user.lng,
                time = user.lastupdated.strftime('%Y-%m-%d %H:%M')
            )
        else:
            text = self.gettext('get_notfound')
        self.send_message(bot, update, text)

    def delete(self, bot, update):
        self.db.delete_user(update.message.from_user.id)
        self.send_message(bot, update, self.gettext('delete'))
        self.export()

    def unknown(self, bot, update):
        self.send_message(bot, update, self.gettext('unkown'))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='config file')

    args = parser.parse_args()

    # configuration
    if args.config:
        config_RAW = args.config
        if not os.path.exists(config_RAW):
            print("given config doesn't exist", file=sys.stderr)
            sys.exit(1)

    else:
        config_RAW = UserMapBot.CONFIG_DEFAULT

    bot = UserMapBot(config_RAW)
    print('bot initialized')
    bot.run()

if __name__ == '__main__':
    main()
