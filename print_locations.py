import database as db

db.initialize('locations.db')

if __name__ == '__main__':
    db.print_all()
