from os import path
from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
from persistent.mapping import PersistentMapping
import transaction
import persistent

# ZODB occasionally wants to log warnings
import logging
logging.basicConfig()


class Root(persistent.Persistent):

    table = 'roots'

    def __init__(self, path):
        self.path = path

    def key(self):
        return self.path


class File(persistent.Persistent):

    table = 'files'

    def __init__(self, root, path):
        self.root = root
        self.path = path

    def key(self):
        return (self.root.path, self.path)

    @property
    def filename(self):
        return path.join(self.root, self.path)


class Artist(persistent.Persistent):

    table = 'artists'

    def __init__(self, mbid, name=None):
        self.mbid = mbid
        self.name = name

    def key(self):
        return self.mbid

    def __repr__(self):
        return u'<Artist %s, %s>' % (self.mbid, self.name)


class Track(persistent.Persistent):

    table = 'tracks'

    def __init__(self, mbid, name=None, artist_name=None):
        self.mbid = mbid
        self.name = name
        self.artist_name = artist_name

    def key(self):
        return self.mbid


class Database(object):

    def __init__(self, filename='data/metadatad.db'):
        storage = FileStorage(filename)
        self.db = DB(storage)
        self.connection = self.db.open()
        self.root = self.connection.root()
        self.files = self.root.setdefault(File.table, PersistentMapping())
        self.tracks = self.root.setdefault(Track.table, PersistentMapping())
        self.artists = self.root.setdefault(Artist.table, PersistentMapping())
        self.roots = self.root.setdefault(Root.table, PersistentMapping())

    def set(self, object):
        self.root[object.table][object.key()] = object

    def commit(self):
        transaction.commit()

    def close(self):
        self.connection.close()
        self.db.close()
