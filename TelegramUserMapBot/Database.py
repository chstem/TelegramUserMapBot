import datetime
from peewee import *
import json

database_proxy = Proxy()

class UserDatabase:
    class __Model(Model):
        class Meta:
            database = database_proxy
    class SFUser(__Model):
        id = IntegerField(primary_key=True)
        location = CharField()
        lat = FloatField()
        lng = FloatField()
        lastupdated = DateTimeField()

    def __init__(self, dbfile):
        self.db = SqliteDatabase(None)
        self.db.init(dbfile)
        database_proxy.initialize(self.db)
        self.db.connect()
        self.db.create_tables([UserDatabase.SFUser], safe=True)
        self.db.commit()

    def __del__(self):
        self.db.close()

    def set_location(self, user_id, location, lat, lng):
        with self.db.atomic() as txn:
            try:
                user = UserDatabase.SFUser.get(id=user_id)
                user.location = location
                user.lat = lat
                user.lng = lng
                user.lastupdated = datetime.datetime.now()
            except UserDatabase.SFUser.DoesNotExist:
                user = UserDatabase.SFUser.create(
                    id = user_id,
                    location = location,
                    lat = lat,
                    lng = lng,
                    lastupdated = datetime.datetime.now(),
                )
            user.save()

    def get_user(self, user_id):
        try:
            user = UserDatabase.SFUser.get(id=user_id)
            return user
        except UserDatabase.SFUser.DoesNotExist:
            return None

    def get_location(self, user_id):
        try:
            user = UserDatabase.SFUser.get(id=user_id)
            return user.location
        except UserDatabase.SFUser.DoesNotExist:
            return None

    def get_geo(self, user_id):
        try:
            user = UserDatabase.SFUser.get(id=user_id)
            return user.lat, user.lng
        except SFUser.DoesNotExist:
            return None

    def delete_user(self, user_id):
        with self.db.atomic() as txn:
            UserDatabase.SFUser.delete().where(UserDatabase.SFUser.id == user_id).execute()

    def get_all(self):
        """Returns a list of all stored geo coordinates."""
        return [(user.lat, user.lng, user.location, user.id) for user in UserDatabase.SFUser.select()]

    def export_csv(self, fname='locations.csv'):
        with open(fname, 'w') as fd:
            # head
            fd.write('lat,lon,name\n')
            # data
            for row in self.get_all():
                fd.write('{},{},{}\n'.format(*row[:3]))

    def export_geojson(self, fname='locations.json'):
        data = []
        for row in self.get_all():
            data.append({
                'type' : 'Feature',
                'geometry' : {
                    'type' : 'Point',
                    'coordinates' : [row[1], row[0]],
                },
                'properties': {'name': row[2]},
            })
        with open(fname, 'w') as fd:
            json.dump(data, fd)

    def print_all(self):
        from pprint import pprint
        pprint(self.get_all())
