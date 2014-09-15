# coding: utf-8
import os, sys
from os import path
import logging
import pytest
import mock
from py.path import local
import filesorter
from filesorter import process_path, config, log, generic_main


log.addHandler(logging.StreamHandler(sys.stdout))


@pytest.fixture()
def setup(request, tmpdir):
    indir = tmpdir.join('in').ensure(dir=True)
    outdir = tmpdir.join('out').ensure(dir=True)
    def setup_maker(seriesname, files):
        # Create the in files
        for file in files:
            if isinstance(file, tuple):
                file, size = file
            else:
                size = 1
            # Size is sometimes necessary for testing. We use a couple of
            # bytes, and the 100 is there to overcome any differences in
            # filename length.
            indir.join(file).write('%s\n%s' % (file, 'b'*100*size))
        # Create the desired out structure - TODO: Too complicated!
        sdir = outdir.join(seriesname).ensure(dir=True)
        sdir.join('Season 1').ensure(dir=True).join('%s - 1x1.mkv' % seriesname).ensure(file=True)
        return indir, outdir

    # TODO: For testing we should have a "just write to this dir" mode.
    olddir = config.get('tv-dir', None)
    config['tv-dir'] = outdir.strpath
    def close():
        config['tv-dir'] = olddir
    request.addfinalizer(close)
    return setup_maker


@pytest.fixture()
def notifications(request):
    """Mock the notification sending."""
    patcher = mock.patch('filesorter.filesorter.send_notification')
    patcher.__enter__()
    def close():
        patcher.__exit__()
    request.addfinalizer(close)
    return filesorter.send_notification


def test_agressive_sampler(setup):
    """If the input file contains both the proper video and a sample, we
    need to be sure we sort the real file.
    """
    indir, outdir = setup('show title', [
        (u'show.title.S02E05.episode.title.720p.HDTV.x264-BWB.mkv', 10),
        u'sampside.er.s02e05.episode.title.72ts.720p.hds.720p.hdtv.x264-bwb-s.mkv',
        (u'show.title.S02E05.episode.title.720p.HDTV.x264-BWB-s.mkv', 2),
    ])
    tv_episodes, other_vids, failed = process_path(indir.strpath)

    assert other_vids == []
    assert len(failed) == 2
    assert len(tv_episodes) == 1
    assert local(tv_episodes[0].filename).readlines()[0].strip() == \
        'show.title.S02E05.episode.title.720p.HDTV.x264-BWB.mkv'


class TestNotification(object):

    def test_send(self, setup, notifications):
        indir, outdir = setup('show title', [
            u'show.title.S02E05.episode.title.720p.HDTV.x264-BWB.mkv',
        ])
        generic_main(indir.strpath, 'some title here')
        assert notifications.mock_calls == [mock.call('New Episode', u'show title - 2x05')]
