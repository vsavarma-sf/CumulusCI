import httplib
import re
import os
import requests
import json

from datetime import datetime
from distutils.version import LooseVersion

from .parser import ChangeNotesLinesParser
from .parser import IssuesParser
from .parser import GithubIssuesParser
from .provider import StaticChangeNotesProvider
from .provider import DirectoryChangeNotesProvider
from .provider import GithubChangeNotesProvider


class BaseReleaseNotesGenerator(object):

    def __init__(self):
        self.change_notes = []
        self.init_parsers()
        self.init_change_notes()

    def __call__(self):
        self._parse_change_notes()
        return self.render()

    def init_change_notes(self):
        self.change_notes = self._init_change_notes()

    def _init_change_notes(self):
        """ Subclasses should override this method to return an initialized
        subclass of BaseChangeNotesProvider """
        return []

    def init_parsers(self):
        """ Initializes the parser instances as the list self.parsers """
        self.parsers = []
        self._init_parsers()

    def _init_parsers(self):
        """ Subclasses should override this method to initialize their
        parsers """
        pass

    def _parse_change_notes(self):
        """ Parses all change_notes in self.change_notes() through all parsers
        in self.parsers """
        for change_note in self.change_notes():
            self._parse_change_note(change_note)

    def _parse_change_note(self, change_note):
        """ Parses an individual change note through all parsers in
        self.parsers """
        for parser in self.parsers:
            parser.parse(change_note)

    def render(self):
        """ Returns the rendered release notes from all parsers as a string """
        release_notes = []
        for parser in self.parsers:
            parser_content = parser.render()
            if parser_content is not None:
                release_notes.append(parser_content)
        return u'\r\n\r\n'.join(release_notes)


class StaticReleaseNotesGenerator(BaseReleaseNotesGenerator):

    def __init__(self, change_notes):
        self._change_notes = change_notes
        super(StaticReleaseNotesGenerator, self).__init__()

    def _init_parsers(self):
        self.parsers.append(ChangeNotesLinesParser(
            self, 'Critical Changes'))
        self.parsers.append(ChangeNotesLinesParser(self, 'Changes'))
        self.parsers.append(IssuesParser(
            self, 'Issues Closed'))

    def _init_change_notes(self):
        return StaticChangeNotesProvider(self, self._change_notes)


class DirectoryReleaseNotesGenerator(BaseReleaseNotesGenerator):

    def __init__(self, directory):
        self.directory = directory
        super(DirectoryReleaseNotesGenerator, self).__init__()

    def _init_parsers(self):
        self.parsers.append(ChangeNotesLinesParser(
            self, 'Critical Changes'))
        self.parsers.append(ChangeNotesLinesParser(self, 'Changes'))
        self.parsers.append(IssuesParser(
            self, 'Issues Closed'))

    def _init_change_notes(self):
        return DirectoryChangeNotesProvider(self, self.directory)

class GithubReleaseNotesGenerator(BaseReleaseNotesGenerator):

    def __init__(self, github_info, current_tag, last_tag=None):
        self.github_info = github_info
        self.current_tag = current_tag
        self.last_tag = last_tag
        super(GithubReleaseNotesGenerator, self).__init__()

    def _init_parsers(self):
        self.parsers.append(
            ChangeNotesLinesParser(
                self, 
                'Critical Changes', 
            )
        )
        self.parsers.append(
            ChangeNotesLinesParser(self, 'Changes')
        )
        self.parsers.append(
            GithubIssuesParser(self, 'Issues Closed')
        )

    def _init_change_notes(self):
        return GithubChangeNotesProvider(
            self, 
            self.current_tag, 
            self.last_tag
        )

class PublishingGithubReleaseNotesGenerator(GithubReleaseNotesGenerator):
   
    def __call__(self):
        content = super(PublishingGithubReleaseNotesGenerator, self)() 
        self.publish()
        return content

    def publish(self):
        release = self._get_or_create_release()


    def _get_or_create_release(self):
        # Query for the release
        try:
            release = self.call_api('/releases/tags/{}'.format(self.current_tag))
        except GithubApiNotFoundError:
            release = {
                "tag_name": release['tag_name'],
                "target_commitish": release['target_commitish'],
                "name": release['name'],
                "body": release['body'],
                "draft": release['draft'],
                "prerelease": release['prerelease'],
            }
        return release
        
    def _update_release(self):
        data = {
            "tag_name": release['tag_name'],
            "target_commitish": release['target_commitish'],
            "name": release['name'],
            "body": release['body'],
            "draft": release['draft'],
            "prerelease": release['prerelease'],
        }

        if data['body']:
            new_body = []
            found_release_notes = False
            in_release_notes = False
            in_parser_section = False

            for line in data['body'].splitlines():

                for parser in self.parsers:
                    if parser._render_heading() == parser._process_line(line):
                        in_parser_section = parser
                        break

                if in_parser_section:
                    # If inside a parser section, skip emitting any lines
                    # and instead render the parser and add its content once
                    # the parser finds an endline
                    if in_parser_section._is_end_line(parser._process_line(line)):
                        parser_content = parser.render()
                        if parser_content:
                            new_body.append(parser_content + '\r\n')
                        in_parser_section = False
                        continue
                else:
                    new_body.append(line.strip())

            if in_parser_section:
                new_body.append(in_parser_section.render())
                    
            release_notes['body'] = u'\r\n'.join(new_body)
        else:
            data['body'] = release_notes

        if release.get('id'):
            resp = self.call_api('/releases/{}'.format(release['id']), data=release)
        else:
            resp = self.call_api('/releases', data=release)

        return resp
        

