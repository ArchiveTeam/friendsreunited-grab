# encoding=utf8
import datetime
from distutils.version import StrictVersion
import hashlib
import os.path
import random
from seesaw.config import realize, NumberConfigValue
from seesaw.item import ItemInterpolation, ItemValue
from seesaw.task import SimpleTask, LimitConcurrent
from seesaw.tracker import GetItemFromTracker, PrepareStatsForTracker, \
    UploadWithTracker, SendDoneToTracker
import shutil
import socket
import subprocess
import sys
import time
import string
import requests

import seesaw
from seesaw.externalprocess import WgetDownload
from seesaw.pipeline import Pipeline
from seesaw.project import Project
from seesaw.util import find_executable


# check the seesaw version
if StrictVersion(seesaw.__version__) < StrictVersion("0.8.5"):
    raise Exception("This pipeline needs seesaw version 0.8.5 or higher.")


###########################################################################
# Find a useful Wget+Lua executable.
#
# WGET_LUA will be set to the first path that
# 1. does not crash with --version, and
# 2. prints the required version string
WGET_LUA = find_executable(
    "Wget+Lua",
    ["GNU Wget 1.14.lua.20130523-9a5c"],
    [
        "./wget-lua",
        "./wget-lua-warrior",
        "./wget-lua-local",
        "../wget-lua",
        "../../wget-lua",
        "/home/warrior/wget-lua",
        "/usr/bin/wget-lua"
    ]
)

if not WGET_LUA:
    raise Exception("No usable Wget+Lua found.")


###########################################################################
# The version number of this pipeline definition.
#
# Update this each time you make a non-cosmetic change.
# It will be added to the WARC files and reported to the tracker.
VERSION = "20160205.04"
USER_AGENT = 'ArchiveTeam'
TRACKER_ID = 'friendsreunited'
TRACKER_HOST = 'tracker.archiveteam.org'


###########################################################################
# This section defines project-specific tasks.
#
# Simple tasks (tasks that do not need any concurrency) are based on the
# SimpleTask class and have a process(item) method that is called for
# each item.
class CheckIP(SimpleTask):
    def __init__(self):
        SimpleTask.__init__(self, "CheckIP")
        self._counter = 0

    def process(self, item):
        # NEW for 2014! Check if we are behind firewall/proxy

        if self._counter <= 0:
            item.log_output('Checking IP address.')
            ip_set = set()

            ip_set.add(socket.gethostbyname('twitter.com'))
            ip_set.add(socket.gethostbyname('facebook.com'))
            ip_set.add(socket.gethostbyname('youtube.com'))
            ip_set.add(socket.gethostbyname('microsoft.com'))
            ip_set.add(socket.gethostbyname('icanhas.cheezburger.com'))
            ip_set.add(socket.gethostbyname('archiveteam.org'))

            if len(ip_set) != 6:
                item.log_output('Got IP addresses: {0}'.format(ip_set))
                item.log_output(
                    'Are you behind a firewall/proxy? That is a big no-no!')
                raise Exception(
                    'Are you behind a firewall/proxy? That is a big no-no!')

        # Check only occasionally
        if self._counter <= 0:
            self._counter = 10
        else:
            self._counter -= 1


class PrepareDirectories(SimpleTask):
    def __init__(self, warc_prefix):
        SimpleTask.__init__(self, "PrepareDirectories")
        self.warc_prefix = warc_prefix

    def process(self, item):
        item_name = item["item_name"]
        escaped_item_name = item_name.replace(':', '_').replace('/', '_').replace('~', '_')
        dirname = "/".join((item["data_dir"], escaped_item_name))

        if os.path.isdir(dirname):
            shutil.rmtree(dirname)

        os.makedirs(dirname)

        item["item_dir"] = dirname
        item["warc_file_base"] = "%s-%s-%s" % (self.warc_prefix, escaped_item_name,
            time.strftime("%Y%m%d-%H%M%S"))

        open("%(item_dir)s/%(warc_file_base)s.warc.gz" % item, "w").close()
        open("%(item_dir)s/%(warc_file_base)s_data.txt" % item, "w").close()


class MoveFiles(SimpleTask):
    def __init__(self):
        SimpleTask.__init__(self, "MoveFiles")

    def process(self, item):
        # NEW for 2014! Check if wget was compiled with zlib support
        if os.path.exists("%(item_dir)s/%(warc_file_base)s.warc" % item):
            raise Exception('Please compile wget with zlib support!')

        os.rename("%(item_dir)s/%(warc_file_base)s.warc.gz" % item,
              "%(data_dir)s/%(warc_file_base)s.warc.gz" % item)

        os.rename("%(item_dir)s/%(warc_file_base)s_data.txt" % item,
              "%(data_dir)s/%(warc_file_base)s_data.txt" % item)

        shutil.rmtree("%(item_dir)s" % item)


def get_hash(filename):
    with open(filename, 'rb') as in_file:
        return hashlib.sha1(in_file.read()).hexdigest()


CWD = os.getcwd()
PIPELINE_SHA1 = get_hash(os.path.join(CWD, 'pipeline.py'))
LUA_SHA1 = get_hash(os.path.join(CWD, 'friendsreunited.lua'))


def stats_id_function(item):
    # NEW for 2014! Some accountability hashes and stats.
    d = {
        'pipeline_hash': PIPELINE_SHA1,
        'lua_hash': LUA_SHA1,
        'python_version': sys.version,
    }

    return d


class WgetArgs(object):
    def realize(self, item):
        wget_args = [
            WGET_LUA,
            "-U", USER_AGENT,
            "-nv",
            "--load-cookies", "cookies.txt",
            "--lua-script", "friendsreunited.lua",
            "-o", ItemInterpolation("%(item_dir)s/wget.log"),
            "--no-check-certificate",
            "--output-document", ItemInterpolation("%(item_dir)s/wget.tmp"),
            "--truncate-output",
            "-e", "robots=off",
            "--rotate-dns",
            "--recursive", "--level=inf",
            "--no-parent",
            "--page-requisites",
            "--timeout", "30",
            "--tries", "inf",
            "--domains", "friendsreunited.com,friendsreunited.co.uk",
            "--span-hosts",
            "--waitretry", "30",
            "--warc-file", ItemInterpolation("%(item_dir)s/%(warc_file_base)s"),
            "--warc-header", "operator: Archive Team",
            "--warc-header", "friendsreunited-dld-script-version: " + VERSION,
            "--warc-header", ItemInterpolation("friendsreunited-user: %(item_name)s"),
        ]
        
        item_name = item['item_name']
        assert ':' in item_name
        item_type, item_value = item_name.split(':', 1)

        item_value = item_value.replace(':', '/')
        
        item['item_type'] = item_type
        item['item_value'] = item_value
        
        assert item_type in ('group_com', 'group_co_uk', '100discussions_com', '100discussions_co_uk')

        if os.path.isfile('account'):
            with open('account', 'r') as file:
                myemail, mypassword = file.read().splitlines()
        else:
            raise Exception('Please add the e-mail to the first line and the password to the second line in a file named "account".')
        
        if item_type == 'group_com':
            session = requests.Session()
            sessionlogin = session.post('http://www.friendsreunited.com/Account/LogOn', data={'ReturnUrl': '', 'UserName': myemail, 'Password': mypassword, 'RememberMe': 'true'})
            if '/Home/Login' in sessionlogin.url:
                raise Exception('Something went wrong while login in! ABORTING')
            wget_args.append(session.get('http://www.friendsreunited.com/{0}'.format(item_value)).url)
            wget_args.append('http://www.friendsreunited.com/{0}'.format(item_value))
        elif item_type == 'group_co_uk':
            session = requests.Session()
            sessionlogin = session.post('http://www.friendsreunited.co.uk/Account/LogOn', data={'ReturnUrl': '', 'UserName': myemail, 'Password': mypassword, 'RememberMe': 'true'})
            if '/Home/Login' in sessionlogin.url:
                raise Exception('Something went wrong while login in! ABORTING')
            wget_args.append(session.get('http://www.friendsreunited.co.uk/{0}'.format(item_value)).url)
            wget_args.append('http://www.friendsreunited.co.uk/{0}'.format(item_value))
        elif item_type == '100discussions_com':
            suffixes = string.digits
            for url in ['http://www.friendsreunited.com/Discussion/{0}{1}{2}'.format(item_value, a, b) for a in suffixes for b in suffixes]:
                wget_args.append(url)
        elif item_type == '100discussions_co_uk':
            suffixes = string.digits
            for url in ['http://www.friendsreunited.co.uk/Discussion/{0}{1}{2}'.format(item_value, a, b) for a in suffixes for b in suffixes]:
                wget_args.append(url)
        else:
            raise Exception('Unknown item')

        if item_type.endswith('_co_uk'):
            tld = 'co.uk'
        elif item_type.endswith('_com'):
            tld = 'com'

        os.system("wget --save-cookies cookies.txt --keep-session-cookies --post-data 'ReturnUrl=&UserName=" + myemail + "&Password=" + mypassword + "&RememberMe=true' --referer http://www.friendsreunited."+tld+"/ http://www.friendsreunited."+tld+"/Account/LogOn")
        os.remove('LogOn')
        
        if 'bind_address' in globals():
            wget_args.extend(['--bind-address', globals()['bind_address']])
            print('')
            print('*** Wget will bind address at {0} ***'.format(
                globals()['bind_address']))
            print('')
            
        return realize(wget_args, item)

###########################################################################
# Initialize the project.
#
# This will be shown in the warrior management panel. The logo should not
# be too big. The deadline is optional.
project = Project(
    title="friendsreunited",
    project_html="""
        <img class="project-logo" alt="Project logo" src="http://archiveteam.org/images/5/5e/Friends-reunited-logo-2012.jpg" height="50px" title=""/>
        <h2>friendsreunited.co.uk <span class="links"><a href="http://www.friendsreunited.co.uk/">Website</a> &middot; <a href="http://tracker.archiveteam.org/friendsreunited/">Leaderboard</a></span></h2>
        <p>Archiving Friends Reunited.</p>
    """
)

pipeline = Pipeline(
    CheckIP(),
    GetItemFromTracker("http://%s/%s" % (TRACKER_HOST, TRACKER_ID), downloader,
        VERSION),
    PrepareDirectories(warc_prefix="friendsreunited"),
    WgetDownload(
        WgetArgs(),
        max_tries=2,
        accept_on_exit_code=[0, 4, 8],
        env={
            "item_dir": ItemValue("item_dir"),
            "item_value": ItemValue("item_value"),
            "item_type": ItemValue("item_type"),
            "warc_file_base": ItemValue("warc_file_base"),
        }
    ),
    PrepareStatsForTracker(
        defaults={"downloader": downloader, "version": VERSION},
        file_groups={
            "data": [
                ItemInterpolation("%(item_dir)s/%(warc_file_base)s.warc.gz"),
                ItemInterpolation("%(item_dir)s/%(warc_file_base)s_data.txt")
            ]
        },
        id_function=stats_id_function,
    ),
    MoveFiles(),
    LimitConcurrent(NumberConfigValue(min=1, max=4, default="1",
        name="shared:rsync_threads", title="Rsync threads",
        description="The maximum number of concurrent uploads."),
        UploadWithTracker(
            "http://%s/%s" % (TRACKER_HOST, TRACKER_ID),
            downloader=downloader,
            version=VERSION,
            files=[
                ItemInterpolation("%(data_dir)s/%(warc_file_base)s.warc.gz"),
                ItemInterpolation("%(data_dir)s/%(warc_file_base)s_data.txt")
            ],
            rsync_target_source_path=ItemInterpolation("%(data_dir)s/"),
            rsync_extra_args=[
                "--recursive",
                "--partial",
                "--partial-dir", ".rsync-tmp",
            ]
            ),
    ),
    SendDoneToTracker(
        tracker_url="http://%s/%s" % (TRACKER_HOST, TRACKER_ID),
        stats=ItemValue("stats")
    )
)
