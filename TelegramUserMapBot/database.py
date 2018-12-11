import datetime
from peewee import *
import json

db = SqliteDatabase(None)

class BaseModel(Model):
    class Meta:
        database = db

class SFUser(BaseModel):
    id = IntegerField(primary_key=True)
    location = CharField()
    lat = FloatField()
    lng = FloatField()
    lastupdated = DateTimeField()

def initialize(dbfile):
    db.init(dbfile)
    db.connect()
    db.create_tables([SFUser], safe=True)
    db.commit()

def set_location(user_id, location, lat, lng):
    with db.atomic() as txn:
        try:
            user = SFUser.get(id=user_id)
            user.location = location
            user.lat = lat
            user.lng = lng
            user.lastupdated = datetime.datetime.now()
        except SFUser.DoesNotExist:
            user = SFUser.create(
                id = user_id,
                location = location,
                lat = lat,
                lng = lng,
                lastupdated = datetime.datetime.now(),
            )
        user.save()

def get_user(user_id):
    try:
        user = SFUser.get(id=user_id)
        return user
    except SFUser.DoesNotExist:
        return None

def get_location(user_id):
    try:
        user = SFUser.get(id=user_id)
        return user.location
    except SFUser.DoesNotExist:
        return None

def get_geo(user_id):
    try:
        user = SFUser.get(id=user_id)
        return user.lat, user.lng
    except SFUser.DoesNotExist:
        return None

def delete_user(user_id):
    with db.atomic() as txn:
        SFUser.delete().where(SFUser.id == user_id).execute()

def get_all():
    """Returns a list of all stored geo coordinates."""
    return [(user.lat, user.lng, user.location, user.id) for user in SFUser.select()]

def export_csv(fname='locations.csv'):
    with open(fname, 'w') as fd:
        # head
        fd.write('lat,lon,name\n')
        # data
        for row in get_all():
            fd.write('{},{},{}\n'.format(*row[:3]))

def export_geojson(fname='locations.json'):
    data = []
    for row in get_all():
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

def print_all():
    from pprint import pprint
    pprint(get_all())
