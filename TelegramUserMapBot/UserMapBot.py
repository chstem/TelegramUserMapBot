#!/usr/bin/env python3
import os
import sys
import json
import logging
import re
from types import SimpleNamespace

import requests
from requests.compat import urljoin
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode, error
from telegram import Bot
from pkg_resources import resource_filename

import TelegramUserMapBot.Database as db

try:
    from systemd import journal
except ImportError:
    pass

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
        self.updater = Updater(token=self.config.BOT_TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # logging
        logger = logging.getLogger('TelegramUserMapBot')
        logger.setLevel(logging.INFO)
        formatter = \
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if self.config.log_file == 'journald':
            log_handle = journal.JournaldLogHandler(
                SYSLOG_IDENTIFIER='TelegramUserMaptBot')
        else:
            log_handle = logging.FileHandler(self.config.log_file)

        log_handle.setFormatter(formatter)
        log_handle.setLevel(logging.INFO)
        logger.addHandler(log_handle)


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

    def send_message(self, update, context, text, **kwargs):
        """Wrapper for Bot.send_message. Try to send to user first, then to orignal channel."""
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        try:
            context.bot.send_message(user_id, text, **kwargs)
        except error.Unauthorized:
            text += self.gettext('hint').format(botname=context.bot.username)
            context.bot.send_message(chat_id, text, **kwargs)

    def gettext(self, key):
        text = self.l10n[key].get(self.config.lang)
        if not text:
            # fallback to en
            text = self.l10n[key].get('en')
        return text

    ### define bot: Bot commands

    def start(self, update, context):
        self.send_message(update, context, self.gettext('start'), parse_mode=ParseMode.MARKDOWN)

    def intro(self, update, context):
        text = self.gettext('intro').format(username=context.bot.username, map=self.config.map_url)
        context.bot.send_message(update.message.chat_id, text, parse_mode=ParseMode.MARKDOWN)

    def show_help(self, update, context):
        self.send_message(update, context, self.gettext('help'), parse_mode=ParseMode.MARKDOWN)

    def region(self, update, context):

        i = update.message.text.find(' ')
        location = update.message.text[i+1:]   # everything after first space

        if not location or i == -1:
            self.send_message(update, context,
                              self.gettext('region_help'), parse_mode=ParseMode.MARKDOWN)
            return

        geo = self.parse_location(location)

        if geo:
            lat, lng = geo
            self.db.set_location(update.message.from_user.id, location, lat, lng)
            text = self.gettext('region_success').format(loc=location)
            self.send_message(update, context, text, parse_mode=ParseMode.MARKDOWN)
            self.export()
        else:
            text = self.gettext('region_error').format(loc=location)
            self.send_message(update, context, text)

    def geo(self, update, context):

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
                self.send_message(update, context, self.gettext('geo_help'))
                raise

            self.db.set_location(update.message.from_user.id, location, lat, lng)
            text = self.gettext('geo_success').format(lat=lat, lng=lng, loc=location)
            self.send_message(update, context, text, parse_mode=ParseMode.MARKDOWN)
            self.export()

        else:
            self.send_message(update, context, self.gettext('geo_help'))

    def show_map(self, update, context):
        self.send_message(update, context, self.config.map_url)

    def get(self,  update, context):
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
        self.send_message(update, context, text)

    def delete(self, update, context):
        self.db.delete_user(update.message.from_user.id)
        self.send_message(update, context, self.gettext('delete'))
        self.export()

    def unknown(self, update, context):
        self.send_message(update, context, self.gettext('unkown'))

def main():
    import argparse
    import signal

    parser = argparse.ArgumentParser()
    parser.add_argument('--export', help='export currently stored data, instead of running the bot', action='store_true')
    parser.add_argument('--print', help='print currently stored data, instead of running the bot', action='store_true')
    parser.add_argument('--config', help='config file')

    args = parser.parse_args()

    # configuration
    if args.config:
        config_RAW = args.config
    else:
        config_RAW = UserMapBot.CONFIG_DEFAULT

    if not os.path.exists(config_RAW):
        print("Given config doesn't exist, please setup the bot first", file=sys.stderr)
        print("(see:", resource_filename(__name__, 'config.json.template'),")",
              file=sys.stderr)
        sys.exit(1)

    bot = UserMapBot(config_RAW)

    if args.export:
        bot.export()

    if args.print:
        bot.db.print_all()

    if args.export or args.print:
        return

    def botstop(__signo, __stackframe):
        bot.stop()
        sys.exit(__signo)

    signal.signal(signal.SIGTERM, botstop)
    signal.signal(signal.SIGINT, botstop)

    print('bot initialized')
    bot.run()

if __name__ == '__main__':
    main()
