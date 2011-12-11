#!/usr/bin/env python

import sys
from xml.etree.ElementTree import ElementTree
from urllib import quote
import eventlet
from eventlet.green import urllib2

import db

def main():
    assert len(sys.argv) == 1, "Syntax: ./fetchtags.py"

    database = db.Database()

    pool = eventlet.GreenPool(200)

    try:
        def getartist(artist):
            if hasattr(artist, 'tags'):
                print 'Already have tags for %s' % artist.name
                return
            print 'Requesting for %s' % artist.name
            tags = get_artist_tags(artist.name)
            artist.tags = tags
            print "%s artist tags" % len(tags)
            database.set(artist)
        for _ in pool.imap(getartist, database.artists.values()):
            pass

        def gettrack(track):
            if hasattr(track, 'tags'):
                print 'Already have tags for %s' % track.name
                return
            print 'Requesting for %s' % track.name
            tags = get_track_tags(track.artist_name, track.name)
            track.tags = tags
            print "%s track tags" % len(tags)
            database.set(track)
        for _ in pool.imap(gettrack, database.tracks.values()):
            pass
    finally:
        database.commit()
        database.close()


def get_artist_tags(artist):
    return get_tags("/1.0/artist/%s/toptags.xml" % artist)


def get_track_tags(artist, track):
    path = "/1.0/track/%s/%s/toptags.xml" % (artist, track)
    return get_tags(path)


def get_tags(path):
    url = 'http://ws.audioscrobbler.com' + quote(path.encode('utf-8'))
    print url
    tree = ElementTree()
    try:
        tree.parse(urllib2.urlopen(url))
    except urllib2.HTTPError, e:
        if e.code != 404:  # 404 are to be expected
            print e
        return {}

    ret = {}
    for tag in tree.getroot():
        name = tag.find('name').text.strip().lower()
        try:
            count = int(tag.find('count').text.strip())
        except ValueError:
            count = 0
        ret[name] = count
    return ret


main()
