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


################################################################################
################################################################################
### All the code below is ripped from Sick-Beard (sickbeard.name_parser),
### licensed under GPL3. Changes are marked "m2k".
################################################################################

import datetime
import os.path
import re

ep_regexes = [
              ('standard_repeat',
               # Show.Name.S01E02.S01E03.Source.Quality.Etc-Group
               # Show Name - S01E02 - S01E03 - S01E04 - Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               s(?P<season_num>\d+)[. _-]*                 # S01 and optional separator
               e(?P<ep_num>\d+)                            # E02 and separator
               ([. _-]+s(?P=season_num)[. _-]*             # S01 and optional separator
               e(?P<extra_ep_num>\d+))+                    # E03/etc and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('fov_repeat',
               # Show.Name.1x02.1x03.Source.Quality.Etc-Group
               # Show Name - 1x02 - 1x03 - 1x04 - Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               (?P<season_num>\d+)x                        # 1x
               (?P<ep_num>\d+)                             # 02 and separator
               ([. _-]+(?P=season_num)x                    # 1x
               (?P<extra_ep_num>\d+))+                     # 03/etc and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('standard',
               # Show.Name.S01E02.Source.Quality.Etc-Group
               # Show Name - S01E02 - My Ep Name
               # Show.Name.S01.E03.My.Ep.Name
               # Show.Name.S01E02E03.Source.Quality.Etc-Group
               # Show Name - S01E02-03 - My Ep Name
               # Show.Name.S01.E02.E03
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               s(?P<season_num>\d+)[. _-]*                 # S01 and optional separator
               e(?P<ep_num>\d+)                            # E02 and separator
               (([. _-]*e|-)                               # linking e/- char
               (?P<extra_ep_num>(?!(1080|720)[pi])\d+))*   # additional E03/etc
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('fov',
               # Show_Name.1x02.Source_Quality_Etc-Group
               # Show Name - 1x02 - My Ep Name
               # Show_Name.1x02x03x04.Source_Quality_Etc-Group
               # Show Name - 1x02-03-04 - My Ep Name
               '''
               ^((?P<series_name>.+?)[\[. _-]+)?             # Show_Name and separator
               (?P<season_num>\d+)x                        # 1x
               (?P<ep_num>\d+)                             # 02 and separator
               (([. _-]*x|-)                               # linking x/- char
               (?P<extra_ep_num>(?!(1080|720)[pi])\d+))*   # additional x03/etc
               [\]. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('scene_date_format',
               # Show.Name.2010.11.23.Source.Quality.Etc-Group
               # Show Name - 2010-11-23 - Ep Name
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (?P<air_year>\d{4})[. _-]+                  # 2010 and separator
               (?P<air_month>\d{2})[. _-]+                 # 11 and separator
               (?P<air_day>\d{2})                          # 23 and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('stupid',
               # tpz-abc102
               '''
               (?P<release_group>.+?)-\w+?[\. ]?           # tpz-abc
               (?P<season_num>\d{1,2})                     # 1
               (?P<ep_num>\d{2})$                          # 02
               '''),

              ('verbose',
               # Show Name Season 1 Episode 2 Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show Name and separator
               season[. _-]+                               # season and separator
               (?P<season_num>\d+)[. _-]+                  # 1
               episode[. _-]+                              # episode and separator
               (?P<ep_num>\d+)[. _-]+                      # 02 and separator
               (?P<extra_info>.+)$                         # Source_Quality_Etc-
               '''),

              ('season_only',
               # Show.Name.S01.Source.Quality.Etc-Group
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               s(eason[. _-])?                             # S01/Season 01
               (?P<season_num>\d+)[. _-]*                  # S01 and optional separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('no_season_multi_ep',
               # Show.Name.E02-03
               # Show.Name.E02.2010
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (e(p(isode)?)?|part|pt)[. _-]?              # e, ep, episode, or part
               (?P<ep_num>(\d+|[ivx]+))                    # first ep num
               ((([. _-]+(and|&|to)[. _-]+)|-)                # and/&/to joiner
               (?P<extra_ep_num>(?!(1080|720)[pi])(\d+|[ivx]+))[. _-])            # second ep num
               ([. _-]*(?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('no_season_general',
               # Show.Name.E23.Test
               # Show.Name.Part.3.Source.Quality.Etc-Group
               # Show.Name.Part.1.and.Part.2.Blah-Group
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (e(p(isode)?)?|part|pt)[. _-]?              # e, ep, episode, or part
               (?P<ep_num>(\d+|([ivx]+(?=[. _-]))))                    # first ep num
               ([. _-]+((and|&|to)[. _-]+)?                # and/&/to joiner
               ((e(p(isode)?)?|part|pt)[. _-]?)           # e, ep, episode, or part
               (?P<extra_ep_num>(?!(1080|720)[pi])
               (\d+|([ivx]+(?=[. _-]))))[. _-])*            # second ep num
               ([. _-]*(?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('bare',
               # Show.Name.102.Source.Quality.Etc-Group
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               (?P<season_num>\d{1,2})                     # 1
               (?P<ep_num>\d{2})                           # 02 and separator
               ([. _-]+(?P<extra_info>(?!\d{3}[. _-]+)[^-]+) # Source_Quality_Etc-
               (-(?P<release_group>.+))?)?$                # Group
               '''),

              ('no_season',
               # Show Name - 01 - Ep Name
               # 01 - Ep Name
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (?P<ep_num>\d{2})                           # 02
               [. _-]+((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),
              ]


class NameParser(object):
    def __init__(self, file_name=True):

        self.file_name = file_name
        self.compiled_regexes = []
        self._compile_regexes()

    def clean_series_name(self, series_name):
        """Cleans up series name by removing any . and _
        characters, along with any trailing hyphens.

        Is basically equivalent to replacing all _ and . with a
        space, but handles decimal numbers in string, for example:

        >>> cleanRegexedSeriesName("an.example.1.0.test")
        'an example 1.0 test'
        >>> cleanRegexedSeriesName("an_example_1.0_test")
        'an example 1.0 test'

        Stolen from dbr's tvnamer
        """

        series_name = re.sub("(\D)\.(?!\s)(\D)", "\\1 \\2", series_name)
        series_name = re.sub("(\d)\.(\d{4})", "\\1 \\2", series_name) # if it ends in a year then don't keep the dot
        series_name = re.sub("(\D)\.(?!\s)", "\\1 ", series_name)
        series_name = re.sub("\.(?!\s)(\D)", " \\1", series_name)
        series_name = series_name.replace("_", " ")
        series_name = re.sub("-$", "", series_name)
        return series_name.strip()

    def _compile_regexes(self):
        for (cur_pattern_name, cur_pattern) in ep_regexes:
            try:
                cur_regex = re.compile(cur_pattern, re.VERBOSE | re.IGNORECASE)
            except re.error, errormsg:
                # m2k
                # logger.log(u"WARNING: Invalid episode_pattern, %s. %s" % (errormsg, cur_regex.pattern))
                raise TypeError('Invalid episode pattern, %s. %s' % (errormsg, cur_regex.pattern))
            else:
                self.compiled_regexes.append((cur_pattern_name, cur_regex))

    def _parse_string(self, name):

        if not name:
            return None

        for (cur_regex_name, cur_regex) in self.compiled_regexes:
            match = cur_regex.match(name)

            if not match:
                continue

            result = ParseResult(name)
            result.which_regex = [cur_regex_name]

            named_groups = match.groupdict().keys()

            if 'series_name' in named_groups:
                result.series_name = match.group('series_name')
                if result.series_name:
                    result.series_name = self.clean_series_name(result.series_name)

            if 'season_num' in named_groups:
                tmp_season = int(match.group('season_num'))
                if cur_regex_name == 'bare' and tmp_season in (19,20):
                    continue
                result.season_number = tmp_season

            if 'ep_num' in named_groups:
                ep_num = self._convert_number(match.group('ep_num'))
                if 'extra_ep_num' in named_groups and match.group('extra_ep_num'):
                    result.episode_numbers = range(ep_num, self._convert_number(match.group('extra_ep_num'))+1)
                else:
                    result.episode_numbers = [ep_num]

            if 'air_year' in named_groups and 'air_month' in named_groups and 'air_day' in named_groups:
                year = int(match.group('air_year'))
                month = int(match.group('air_month'))
                day = int(match.group('air_day'))

                # make an attempt to detect YYYY-DD-MM formats
                if month > 12:
                    tmp_month = month
                    month = day
                    day = tmp_month

                try:
                    result.air_date = datetime.date(year, month, day)
                except ValueError, e:
                    raise InvalidNameException(str(e))

            if 'extra_info' in named_groups:
                tmp_extra_info = match.group('extra_info')

                # Show.S04.Special is almost certainly not every episode in the season
                if tmp_extra_info and cur_regex_name == 'season_only' and re.match(r'([. _-]|^)(special|extra)\w*([. _-]|$)', tmp_extra_info, re.I):
                    continue
                result.extra_info = tmp_extra_info

            if 'release_group' in named_groups:
                result.release_group = match.group('release_group')

            return result

        return None

    def _combine_results(self, first, second, attr):
        # if the first doesn't exist then return the second or nothing
        if not first:
            if not second:
                return None
            else:
                return getattr(second, attr)

        # if the second doesn't exist then return the first
        if not second:
            return getattr(first, attr)

        a = getattr(first, attr)
        b = getattr(second, attr)

        # if a is good use it
        if a != None or (type(a) == list and len(a)):
            return a
        # if not use b (if b isn't set it'll just be default)
        else:
            return b

    def _unicodify(self, obj, encoding = "utf-8"):
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj

    def _convert_number(self, number):
        if type(number) == int:
            return number

        # the lazy way
        if number.lower() == 'i': return 1
        if number.lower() == 'ii': return 2
        if number.lower() == 'iii': return 3
        if number.lower() == 'iv': return 4
        if number.lower() == 'v': return 5
        if number.lower() == 'vi': return 6
        if number.lower() == 'vii': return 7
        if number.lower() == 'viii': return 8
        if number.lower() == 'ix': return 9
        if number.lower() == 'x': return 10
        if number.lower() == 'xi': return 11
        if number.lower() == 'xii': return 12
        if number.lower() == 'xiii': return 13
        if number.lower() == 'xiv': return 14
        if number.lower() == 'xv': return 15

        return int(number)

    def parse(self, name):

        name = self._unicodify(name)

        # break it into parts if there are any (dirname, file name, extension)
        dir_name, file_name = os.path.split(name)
        ext_match = re.match('(.*)\.\w{3,4}$', file_name)
        if ext_match and self.file_name:
            base_file_name = ext_match.group(1)
        else:
            base_file_name = file_name

        # use only the direct parent dir
        dir_name = os.path.basename(dir_name)

        # set up a result to use
        final_result = ParseResult(name)

        # try parsing the file name
        file_name_result = self._parse_string(base_file_name)

        # parse the dirname for extra info if needed
        dir_name_result = self._parse_string(dir_name)

        # build the ParseResult object
        final_result.air_date = self._combine_results(file_name_result, dir_name_result, 'air_date')

        if not final_result.air_date:
            final_result.season_number = self._combine_results(file_name_result, dir_name_result, 'season_number')
            final_result.episode_numbers = self._combine_results(file_name_result, dir_name_result, 'episode_numbers')

        # if the dirname has a release group/show name I believe it over the filename
        final_result.series_name = self._combine_results(dir_name_result, file_name_result, 'series_name')
        final_result.extra_info = self._combine_results(dir_name_result, file_name_result, 'extra_info')
        final_result.release_group = self._combine_results(dir_name_result, file_name_result, 'release_group')

        final_result.which_regex = []
        if final_result == file_name_result:
            final_result.which_regex = file_name_result.which_regex
        elif final_result == dir_name_result:
            final_result.which_regex = dir_name_result.which_regex
        else:
            if file_name_result:
                final_result.which_regex += file_name_result.which_regex
            if dir_name_result:
                final_result.which_regex += dir_name_result.which_regex

        # if there's no useful info in it then raise an exception
        if final_result.season_number == None and not final_result.episode_numbers and final_result.air_date == None and not final_result.series_name:
            raise InvalidNameException("Unable to parse "+name)

        # return it
        return final_result

class ParseResult(object):
    def __init__(self,
                 original_name,
                 series_name=None,
                 season_number=None,
                 episode_numbers=None,
                 extra_info=None,
                 release_group=None,
                 air_date=None
                 ):

        self.original_name = original_name

        self.series_name = series_name
        self.season_number = season_number
        if not episode_numbers:
            self.episode_numbers = []
        else:
            self.episode_numbers = episode_numbers

        self.extra_info = extra_info
        self.release_group = release_group

        self.air_date = air_date

        self.which_regex = None

    def __eq__(self, other):
        if not other:
            return False

        if self.series_name != other.series_name:
            return False
        if self.season_number != other.season_number:
            return False
        if self.episode_numbers != other.episode_numbers:
            return False
        if self.extra_info != other.extra_info:
            return False
        if self.release_group != other.release_group:
            return False
        if self.air_date != other.air_date:
            return False

        return True

    def __str__(self):
        to_return = str(self.series_name) + ' - '
        if self.season_number != None:
            to_return += 'S'+str(self.season_number)
        if self.episode_numbers and len(self.episode_numbers):
            for e in self.episode_numbers:
                to_return += 'E'+str(e)

        if self.air_by_date:
            to_return += str(self.air_date)

        if self.extra_info:
            to_return += ' - ' + self.extra_info
        if self.release_group:
            to_return += ' (' + self.release_group + ')'

        to_return += ' [ABD: '+str(self.air_by_date)+']'

        return to_return.encode('utf-8')

    def _is_air_by_date(self):
        if self.season_number == None and len(self.episode_numbers) == 0 and self.air_date:
            return True
        return False
    air_by_date = property(_is_air_by_date)

class InvalidNameException(Exception):
    "The given name is not valid"

################################################################################
### END SICK-BEARD RIP
################################################################################
################################################################################


log = logging.getLogger('torrent-postprocess')

config = __import__('torrent-postprocess-config').config


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
