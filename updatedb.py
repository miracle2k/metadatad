#!/usr/bin/env python
import sys, os
from os import path
import mutagen

import db


assert len(sys.argv) == 2, "Syntax: ./updatedb.py DIRECTORY"
dir_to_parse = sys.argv[1]

database = db.Database()

counters = {'audio': 0}
skipped = []
no_mbdata = []
try:
    for dirpath, dirnames, filenames in os.walk(dir_to_parse, followlinks=True):
        for filename in filenames:
            # Determine full path, the base, and the filename
            # relative to the base; the base concept can be used
            # to have multiple media file "root"s.
            fullpath = path.join(dirpath, filename)
            base = dir_to_parse
            relpath = path.relpath(fullpath, base)

            dbfile = db.File(base, relpath)

            # For now, only process new files
            print 'Looking at', relpath,
            if dbfile.key() in database.files:
                print 'already known'
            else:
                print

            # Open the file
            try:
                audio = mutagen.File(fullpath, easy=True)
            except Exception, e:
                skipped.append((fullpath, e))
                continue

            if not audio:
                skipped.append((fullpath, 'mutagen-failed'))
                continue
            counters['audio'] += 1

            # Does it have MusicBrainz links?
            if 'musicbrainz_artistid' in audio:
                try:
                    artist = database.artists[audio['musicbrainz_artistid'][0]]
                except KeyError:
                    artist = db.Artist(audio['musicbrainz_artistid'][0],
                                       name=audio['artist'][0])
                    database.set(artist)
            else:
                artist = None
            if 'musicbrainz_trackid' in audio:
                try:
                    track = database.tracks[audio['musicbrainz_trackid'][0]]
                except KeyError:
                    track = db.Track(audio['musicbrainz_trackid'][0],
                                     name=audio['title'][0],
                                     artist_name=audio['artist'][0])
                    database.set(track)
            else:
                track = None

            if not track and not artist:
                no_mbdata.append(fullpath)

            dbfile.artist = artist
            dbfile.track = track
            # http://code.google.com/p/mutagen/issues/detail?id=102
            #dbfile.metadata = audio
            database.set(dbfile)
finally:
    print '%s files found' % counters['audio']
    print 'Saving...'
    database.commit()
    database.close()

    print '%s files skipped - writing to updatedb.skipped' % len(skipped)
    with open('updatedb.skipped', 'w') as f:
        f.write('\n'.join(map(lambda s: '%s: %s' % s, skipped)))

    print '%s files have no musicbrainz ids - writing to updatedb.nomb' % len(no_mbdata)
    with open('updatedb.nomb', 'w') as f:
        f.write('\n'.join(no_mbdata))
