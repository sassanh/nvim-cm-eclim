# -*- coding: utf-8 -*-

import json
import os
import re
import subprocess

from pathlib import Path

from cm import Base, getLogger, register_source

register_source(
    name='eclim',
    priority=9,
    abbreviation='java',
    word_pattern=r'\w+',
    scoping=True,
    scopes=['java'],
    early_cache=1,
    cm_refresh_patterns=[r'\.'],
)


logger = getLogger(__name__)


class Source(Base):

    def __init__(self, nvim):
        super(Source, self).__init__(nvim)
        self.home_directory = os.path.join(
            str(Path.home()),
            '.eclim',
        )

    def _get_project_info(self):
        project_info_string = self.nvim.command_output(
            'silent! ProjectInfo',
        )
        self.project_info = re.match(
            r'\s*Name:\s*(?P<name>.*)\s*Path:\s*(?P<path>.*)\s*' +
            r'Workspace:\s*(?P<workspace>.*)',
            project_info_string,
        ).groupdict()
        return self.project_info

    def _get_instance(self):
        project_info = self._get_project_info()
        with open(os.path.join(
            self.home_directory,
            '.eclimd_instances',
        )) as instances_file:
            for line in instances_file:
                if not line:
                    continue
                instance = json.loads(line)
                if instance['workspace'] == project_info['workspace']:
                    self.instance = instance
                    return instance

    def cm_refresh(self, info, ctx, *args):
        instance_home = self._get_instance()['home']
        instance_port = self._get_instance()['port']
        executable = os.path.join(instance_home, 'bin/eclim')

        offset = self.nvim.call('line2byte', ctx['lnum']) + ctx['col'] - 1

        self.nvim.command('update')

        path = os.path.relpath(ctx['filepath'], self.project_info['path'])

        args = [
            executable,
            '--nailgun-server', 'localhost',
            '--nailgun-port', str(instance_port),
            '-editor', 'vim',
            '-command', 'java_complete',
            '-p', self.project_info['name'],
            '-f', path,
            '-o', str(offset - 1),
            '-e', 'utf-8',
            '-l', 'compact',
        ]

        proc = subprocess.Popen(args=args,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        result, errs = proc.communicate(timeout=30)

        logger.debug("args: %s, result: [%s]", args, result.decode())

        items = json.loads(result.decode('utf-8'))['completions']
        items = [dict(
            item,
            word=item['completion'],
            menu=item['menu'].replace(item['completion'] + ' : ', ''),
        ) for item in items]
        self.complete(info, ctx, ctx['startcol'], items)
