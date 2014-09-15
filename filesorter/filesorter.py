#!/opt/bin/python
"""Post-process script to be called by Transmission upon finishing
a download (script-torrent-done-filename setting).

Will unpack archives, and tries to sort TV shows within a directory
structure, the files properly renamed.

When using transmission <2.2, you need to wrap this in a shell script
which does "{ ./this.py } &", to prevent Transmission from blocking,
see: https://forum.transmissionbt.com/viewtopic.php?f=3&t=11397

Easiest way to test this when debugging is calling it like so:

    TR_TORRENT_DIR=foo python torrent-postprocess.py

With foo being a directory containing a custom archive file that contains
a (maybe fake) video file.
"""

import sys
import os
from os import path
import logging
from subprocess import Popen, PIPE
import urllib, urllib2
import base64

from parser import NameParser, InvalidNameException


log = logging.getLogger('torrent-postprocess')

config = __import__('config').config


class Torrent(object):
    def __init__(self, id, name, dir, hash):
        self.id, self.name, self.dir, self.hash = id, name, dir or '', hash

    def __unicode__(self):
        return "%s (%s)" % (self.path, self.id)

    def __repr__(self):
        return "<Torrent path=%s, id=%s, hash=%s>" % (
            repr(self.path), self.id, self.hash)

    @property
    def path(self):
        return path.join(self.dir, self.name or '')


def get_files(directory):
    """Returns, recursively, all the files in the given directory.
    """
    for (top, dirs, files) in os.walk(directory):
        for f in files:
            yield path.join(top, f)


def is_video(filename):
    return path.splitext(filename)[1] in ('.mkv', '.avi', '.mov', '.wmv', '.mp4')


def first_part_only(filename):
    """Filter to return only those archives which represent a "first"
    part in a multi volume series. This is necessary because sometimes,
    multipart RAR archive use "partXX.rar" rather than ".rXX" extensions
    (according to Wikipedia, "partXX.rar" is the new approach with RAR3).
    """
    m = re.search(r'part(\d+)\.rar$', filename)
    if not m:  # Not one of the multipart archives we need to filter
        return True
    return int(m.groups()[0]) == 1


def unpack(torrent):
    """Unpack the torrent as necessary, yield a list of movie files
    we need to process.
    """
    if path.isfile(torrent.path):
        log.error('Torrent "%s" is a file, this is currently not supported',
                  torrent.path)

    else:
        all_files = list(get_files(torrent.path))

        # Unpack all archives
        rar_files = filter(lambda x: path.splitext(x)[1] == '.rar', all_files)
        rar_files = filter(first_part_only, rar_files)

        # If there are no archives, look for videos in original set
        if not rar_files:
            log.info('No archives found, assume video files are contained directly')
            for file in all_files:
                if is_video(file):
                    yield file
            return

        for archive in rar_files:
            log.info('Unpacking archive: %s' % archive)
            p = Popen([config.get('unrar-bin', '/usr/syno/bin/unrar'), 'x', '-y', archive, torrent.path],
                      stdout=PIPE, stderr=PIPE)
            p.wait()
            if p.returncode != 0:
                log.error('Failed to unpack "%s":\n%s\n%s' % (
                    archive, p.stderr.read(), p.stdout.read()))
                continue

            # Find the files that are new in this archive
            updated_all_files = list(get_files(torrent.path))
            added_files = set(updated_all_files) - set(all_files)
            all_files = updated_all_files
            log.debug('Unpack yielded %d new files', len(added_files))

            # Process all files we unpacked
            for file in added_files:
                print added_files, file
                if is_video(file):
                    yield file
                else:
                    log.info('Ignoring unpacked file "%s"', file)


def parse_tv_filename(filename):
    """Wrapper around NameParser which does a couple extra things we
    want.
    """
    try:
        # It might seem it is more reliable to parse only the actual filename;
        # the directory sometimes contains torrent site tags, stuff that
        # NameParser isn't good at handling, and those then can get preference.
        show = NameParser().parse(path.basename(filename))
        if not show.series_name:
            # Sometimes the parser gives us name-less shows.
            raise InvalidNameException('No series name')
    except InvalidNameException, e:
        log.debug('Failed to parse "%s": %s', filename, e, exc_info=1)
        return False
    else:
        # Deal with filenames that contain the show year at the end.
        # NameParser may give us for example "Castle 2009". We want
        # to remove that part for our sorting purposes, but we do
        # need it for TVdb, so store both values.
        # This process is very simple right now and assumes we have
        # no shows that need the year for unique identification.
        show.series_name_with_year = show.series_name
        show.series_name = re.sub(r'[ (]\d\d\d\d\)?$', '', show.series_name).strip()

        return show


def find_tv_episode_target_filename(show, file):
    """Finds target folder and builds filename for this episode.
    Returns both as a 2-tuple.
    """
    # Find a fitting target folder.
    log.debug('Trying to find target folder within %s', config['tv-dir'])
    for top, _, files in os.walk(config['tv-dir']):
        for candidate in files:
            candidate_path = path.join(top, candidate)
            log.debug('Considering %s', candidate)
            n = parse_tv_filename(candidate_path)
            if not n:
                log.debug('Failed to parse %s', candidate)
            else:
                if n.series_name.lower() != show.series_name.lower():
                    log.debug('Candidate series "%s" does not match',
                              n.series_name)
                    continue

                log.debug('Candidate "%s" matches', candidate)

                # We have our match! Now determine the target folder.
                parent_folder = path.basename(path.dirname(candidate_path))
                if not parent_folder.startswith('Season'):
                    log.debug('No "Season" structure detected, assuming single folder')
                    single_folder = True
                    series_folder = path.join(path.dirname(candidate_path))
                else:
                    single_folder = False
                    series_folder = path.join(path.dirname(candidate_path), '..')

                # If a .metadatad file exists, read it. It contains the ID to
                # look for. This is neccessary (rarely) in case a show does
                # not yield the correct Tvdb result through a name search.
                id_file = path.join(series_folder, '.metadatad')
                tvdb_id = None
                if path.isfile(id_file):
                    try:
                        tvdb_id = int(open(id_file, 'r').read())
                        log.debug('Found fixed TVDB id: "%s"', tvdb_id)
                    except ValueError:
                        pass

                # Try to get the episode title via TVdb
                tbdb_show = None
                if len(show.episode_numbers) <= 1:
                    # We do not support titels for multi-episode file for now
                    try:
                        import tvdb_api
                    except ImportError:
                        log.debug('tvdb_api module not available, not getting title')
                    else:
                        log.debug('Trying to find show info via thetvdb.com')
                        db = tvdb_api.Tvdb()
                        try:
                            tbdb_series = \
                                db[tvdb_id] if tvdb_id else db[show.series_name_with_year]
                            if show.air_by_date:
                                tbdb_show = tbdb_series.airedOn(show.air_date)[0]
                            else:
                                tbdb_show = tbdb_series[show.season_number]\
                                              [show.episode_numbers[0]]
                            log.info('Found episode on tvdb')
                        except (tvdb_api.tvdb_error, tvdb_api.tvdb_shownotfound, tvdb_api.tvdb_seasonnotfound, tvdb_api.tvdb_episodenotfound), e:
                            log.warning('Unable to find episode on tvdb: %s', e)


                # Put together the full episode name that we will also use in
                # the notification. Use the candidate's series_name, the casing
                # is more likely to be what we want it to!
                episode_full_name = '%s' %  n.series_name
                if show.air_by_date:
                    episode_full_name += ' - %s' % (tbdb_show['firstaired'] if tbdb_show else str(show.air_date))
                else:
                    episode_full_name += ' - %sx%s' % (
                        show.season_number,
                        "+".join(map(lambda n: "%.2d" % n, show.episode_numbers)))
                if tbdb_show:
                    episode_full_name = "%s - %s" % (episode_full_name, tbdb_show['episodename'])

                # Determine target path
                parts = [series_folder]
                if not single_folder:
                    parts.extend(['Season %d' % show.season_number])
                parts.append('%s%s' % (episode_full_name, path.splitext(file)[1]))
                target_file = path.normpath(path.join(*parts))

                return target_file, episode_full_name
    else:
        log.error('No fitting target folder found for %s' % file)
        return None, None


def process_video(file):
    """Rename video file and move to target folder.

    Returns a 2-tuple (episode title, final file location). The first
    value will only be set if an episode was parsed and handled correctly.
    If the file was only moved to a location intended for files requiring
    manual intervention, then the first tuple element will be None.
    """
    log.info('Trying to process video file "%s"', file)
    show = parse_tv_filename(file)

    # Determine where to move the video.
    target_file = episode_title = None
    if show:
        log.info('Determined to be TV show: %s, S=%s, E=%s',
                 show.series_name, show.season_number, show.episode_numbers)
        target_file, episode_title = find_tv_episode_target_filename(show, file)
    else:
        log.warning('Filename doesn\'t look like a TV show: %s', file)

    # If we do not find a proper place for the video file, move it
    # none the less to a target folder, where it might easier to copy
    # from and manually deal with.
    if not target_file and "manual-dir" in config:
        filename = path.basename(file)
        folder = path.basename(path.dirname(file))
        target_file = path.join(config['manual-dir'], folder, filename)

    if not target_file:
        return None, None

    # Actually move the file
    log.info('Moving "%s" to "%s"', file, target_file)
    if not config['dryrun']:
        directory = path.dirname(target_file)
        if not path.exists(directory):
            os.makedirs(directory)
        os.rename(file, target_file.encode('utf-8'))

    return (episode_title, target_file)



def clear():
    """Delete torrents right away, except if they are from our
    private tracker, which requires us to seed. Only trash data
    if we were able to move all files, of course.
    """
    #if funfile and not force:
    #    return
    #
    #getridofit()


def clear_old():
    """Clear torrents from our private trackers after we seeded
    for a long enough time.
    """
    """for all torrents in torrents:
        if ended:
            clear:
                pass"""


def send_notification(subject, message):
    log.info('Sending message: %s - %s', subject, message)
    if not config['dryrun']:
        app_name = 'Your Dollhouse Handler'

        # send via prowl
        if 'prowl-key' in config:
            url = 'https://api.prowlapp.com/publicapi/add'
            post = {
                'apikey': config['prowl-key'],
                'application': app_name,
                'event': subject,
                'description': message,
            }
            try:
                r = urllib2.urlopen(url, urllib.urlencode(post))
                r.read()
                r.close()
            except IOError, e:
                log.error('Cannot send Prowl notification: %s', e)

        # send via notify
        if 'nma-key' in config:
            url = 'https://www.notifymyandroid.com/publicapi/notify'
            post = {
                'apikey': config['nma-key'],
                'application': app_name,
                'event': subject,
                'description': message,
            }
            request = urllib2.Request(url, urllib.urlencode(post))
            try:
                r = urllib2.urlopen(request)
                r.read()
                r.close()
            except IOError:
                log.error('Cannot send NMA notification: %s', e)


def main():
    # XXX Need to support a non-move mode for torrents that are not compressed.

    # Process the torrent
    torrent = Torrent(**{
        'id': os.environ.get('TR_TORRENT_ID'),
        'name': os.environ.get('TR_TORRENT_NAME'),
        'dir': os.environ.get('TR_TORRENT_DIR'),
        'hash': os.environ.get('TR_TORRENT_HASH'),
    })

    # Handle errors that are outright failures, no notification at
    # all are sent in those cases.
    if not torrent.path:
        log.error("No torrent given via environment. This script "+
                  "is to be called by Transmission.")
        return 1
    if not path.exists(torrent.path):
        log.error('Given torrent path "%s" does not exist' % torrent.path)
        return 1

    # Process the torrent
    log.info('Asked to process torrent "%s"' % torrent)
    tvepisodes, other_videos, failed = [], [], []
    for file in unpack(torrent):
        episode, filename = process_video(file)
        if episode:
            tvepisodes.append(episode)
        elif filename:
            other_videos.append(path.basename(filename))
        else:
            failed.append(file)

    if not tvepisodes and not other_videos:
        if not failed:
            # Extra message when we cannot even find a single video to process
            log.info('No video files found')
        send_notification('Download complete', torrent.name)
    else:
        if tvepisodes and other_videos:
            subject = 'New Episodes/Videos'
        elif tvepisodes:
            subject = 'New Episodes' if len(tvepisodes)+len(failed)>1 else 'New Episode'
        elif other_videos:
            subject = 'New Videos' if len(other_videos)+len(failed)>1 else 'New Video'
        message = ", ".join(tvepisodes+other_videos)
        if failed:
            message += " and %d unknown" % len(failed)
        send_notification(subject, message)

    # Delete empty directories
    if path.isdir(torrent.path) and os.listdir(torrent.path) == []:
        os.rmdir(torrent.path)

    # TODO
    #clear()
    #clear_old()


def main_wrapper(*a, **kw):
    """Because the Synology Cron doesn't send stdout/stderr messages
    per mail, make sure we log every failure.
    """
    # Configure logging
    log.setLevel(config['log-level'])
    if config.get('logfile'):
        h = logging.FileHandler(config.get('logfile'))
        h.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"))
        log.addHandler(h)
    log.addHandler(logging.StreamHandler())

    try:
        return main(*a, **kw)
    except Exception, e:
        log.exception(e)


if __name__ == '__main__':
    sys.exit(main_wrapper() or 0)
