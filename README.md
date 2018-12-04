# UserMapBot

A Telegram Bot to collect location information from users and export the coordinates to a map service.

### Setup

- Clone repository

```bash
git clone https://github.com/chstem/TelegramUserMapBot.git
```

- Install required Python packages. (Add `--user` if you are not root.)

```bash
pip install peewee requests python-telegram-bot
```

- Create a new Telegram Bot by talking to [@BotFather](https://telegram.me/botfather)

- Create a new map, for example at [uMap](http://umap.openstreetmap.fr/en/).

- Rename `config.json.template` to `config.json` and edit. Add your bot token, obtained from [@BotFather](https://telegram.me/botfather).

- After each update, the data is exported to a CSV or GeoJSON file. In `config.json` you can set up a path for that file, which is publicly accessible on your webserver. Add its URL to the map service as "remote data" source, so it can fetch updates automatically.

- Finally, run `python UserMapBot.py`.

### List of Bot commands
List of commands to setup via [@BotFather](https://telegram.me/botfather)

```
region - Pass your hometown or next largest city.
geo - Pass coordinates.
map - Get map link.
get - Show your saved location.
delete - Delete your stored information.
intro - Shows a short introduction.
help - Shows all available commands.
```
