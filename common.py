# -*- coding: utf-8 -*-
"""
----------------------------------------------------------------------------
"THE BEER-WARE LICENSE" (Revision 42):
<jean.francois.boismenu@autodesk.com> wrote this file.  As long as you retain
this notice you can do whatever you want with this stuff. If we meet some day,
and you think this stuff is worth it, you can buy me a beer in return. Or two.
Jean-François Boismenu
----------------------------------------------------------------------------
"""

import sys
import os
import datetime
import itertools
third_party_location = os.path.join(os.path.dirname(__file__), "3rd_party")
sys.path.insert(0, third_party_location)

# Disable SSL warnings on Windows.
import requests
from requests.packages.urllib3.exceptions import InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

from togglwrapper import Toggl
from jira import JIRA
from shotgun_api3 import Shotgun, AuthenticationFault
from getpass import getpass
import keyring
import json
import os
import re
import iso8601
from tzlocal import get_localzone

from collections import namedtuple

TogglProject = namedtuple("TogglProject", ["description", "id", "active"])


class Toggl2ShotgunError(Exception):
    pass


class UserInteractionRequiredError(Toggl2ShotgunError):
    pass


def _set_password(site, login, password):
    """
    Sets the password into the keyring. Ignores any errors.

    :param str site: Site we wish to save credentials for.
    :param str login: Login on the site we wish to save credentials for.
    :param str password: Password associated to the login we wish to save credentials for.
    """
    try:
        keyring.set_password(site, login, password)
    except:
        return


def _get_password(site, login):
    """
    Retrieves the password for given site and login pair. Ignores any errors.

    :param str site: Site for which we require the password.
    :param str login: Login for which we require the password.

    :returns: The password.
    """
    try:
        return keyring.get_password(site, login)
    except:
        print "It appears the keyring module doesn't support your platform."
        return None


def add_common_arguments(argument_parser):
    """
    Addds common arguments to the arguments parser.
    """
    argument_parser.add_argument("--headless", action="store_true", default=False)


def _get_credential(cred_name, cred_default):
    """
    Gets a credential from the command line. Will display a default if available.
    Prompt will be in the `cred_name [cred_default]:` format.

    Entering nothing will pick the default value if one is available, otherwise
    you'll be continuously queried.

    :param str cred_name: Name of the thing you want the user to enter
    :param str cred_default: Default value for that credential

    :returns: Value entered by the user.
    """
    if cred_default:
        cred_value = raw_input("%s [%s]: " % (cred_name, cred_default))
        return cred_value.strip() if cred_value.strip() else cred_default
    else:
        cred_value = None
        while not cred_value or not cred_value.strip():
            cred_value = raw_input("%s: " % cred_name)
        return cred_value.strip()


def _get_self(sg, login):
    """
    Finds the the human user associated with a given login.

    :param str login: Shotgun login string.

    :returns: HumanUser entity associated with the login.
    """
    return sg.find("HumanUser", [["login", "is", login]])


def _get_credential_file_path():
    """
    Retrieves the path to the credential file.
    """
    return os.path.expanduser("~/.toggl2shotgun")


def _get_credentials_from_file():
    """
    Reads the credentials from disk and returns them.

    :returns: Dictionary with keys site, login, session_token and toggl.
    """
    try:
        # Try to read it in.
        with open(_get_credential_file_path(), "r") as f:
            data = json.load(f)
            return data
    except Exception:
        return {}


def _log_into_toggl():
    """
    Ensures you are logged into Toggl with a API token. If not, credentials are queried.

    :returns: Toggl API key.
    """

    api_key = None
    data = {}
    try:
        with open(_get_credential_file_path(), "r") as f:
            data = json.load(f)
        api_key = data["toggl"]

        toggl = Toggl(api_key)
    except:
        api_key = _get_credential("Toggl API Key", api_key)

        toggl = Toggl(api_key)

        with open(_get_credential_file_path(), "w") as f:
            data["toggl"] = api_key
            json.dump(data, f)

    return toggl, _get_shotgun_workspace(toggl)


def _get_shotgun_workspace(toggl):
    """
    Retrieves the one and only workspace id we are using.
    """
    # Get the one and only workspace id.
    workspaces = toggl.Workspaces.get()
    for w in workspaces:
        if w["name"] == "Shotgun":
            return w["id"]
    else:
        raise Toggl2ShotgunError(
            "'Shotgun' workspace does not exist. Visit 'https://toggl.com/app/workspaces' "
            "and create a workspace named 'Shotgun'."
        )


def get_projects_from_toggl(toggl):
    """
    Retrieves all projects from Toggl.

    :returns: An iterable that yields (shotgun ticket id, (toggl project title, toggl project id)).
    """
    workspace_id = _get_shotgun_workspace(toggl)

    for project in toggl.Workspaces.get_projects(workspace_id, active="both") or []:
        yield project


def connect_to_toggl(is_headless):
    """
    Connects to Toggl.
    :returns: A tuple of (toggl API, user workspace).
    """
    return _log_into_toggl()


class JiraTickets(object):

    def __init__(self, is_headless):
        self._jira, self._jira_project = self._connect(is_headless)

    def _connect(self, is_headless):
        data = _get_credentials_from_file()

        if "jira_site" not in data or "jira_login" not in data or "jira_project" not in data:
            return self._create_new_connection(is_headless, data)

        password = _get_password(data["jira_site"], data["jira_login"])
        # If there is no password, ask for the credentials from scratch.
        if not password:
            print "Password not found in keyring or empty."
            return self._create_new_connection(is_headless, data)

        try:
            jira = JIRA(data["jira_site"], basic_auth=(data["jira_login"], password))
            return jira, data["jira_project"]
        except AuthenticationFault:
            print "Password in keychain doesnt't seem to work. Did you change it?"
            return self._create_new_connection(is_headless, data), data["jira_project"]

    def _create_new_connection(self, is_headless, data):

        if is_headless:
            raise UserInteractionRequiredError()

        site = _get_credential("JIRA site", data.get("jira_site", ""))
        login = _get_credential("JIRA login", data.get("jira_login", ""))
        project = _get_credential("JIRA project", data.get("jira_project", ""))

        jira = None
        while not jira:
            password = getpass("Password: ")

            try:
                jira = JIRA(site, basic_auth=(login, password))
            except Exception:
                jira = None
            else:
                _set_password(site, login, password)

        # Update the data dictionary. Note that the dictionary can also
        # contain information about Toggl, so we need to update it
        # instead of creating a new one.
        data["jira_site"] = site
        data["jira_login"] = login
        data["jira_project"] = project
        with open(_get_credential_file_path(), "w") as f:
            json.dump(data, f)

        return jira, project

    def filter_projects(self, projects):
        for project in projects:
            project_name = project["name"]
            if not project_name.startswith(self._jira_project + "-"):
                continue
            ticket_id, ticket_desc = re.match("({}-\d+) (.*)".format(self._jira_project), project_name).groups()
            yield ticket_id, TogglProject(str(ticket_desc), project["id"], project["active"])

    def get_tickets(self):

        # Find all issues.
        STEP_SIZE = 50
        for start_at in itertools.count(0, STEP_SIZE):
            # This pretty much replicates the query string from the Kanban board for the Toolkit
            # team.
            issues = self._jira.search_issues(
                #"project = %s AND assignee = currentUser()" % self._jira_project,
                "project = %s AND "
                "assignee = currentUser() AND "
                "issuetype != Initiative AND "
                "(labels != SG-No-Kanban OR labels is EMPTY) AND "
                "status != Open AND "
                "(status != Closed OR (status = Closed AND status changed after -14d)) "
                "ORDER BY Rank ASC" % self._jira_project,
                maxResults=STEP_SIZE,
                startAt=start_at,
                fields=["summary", "key"]
            )
            # If not issues have been returned, exit.
            if not issues:
                return
            for issue in issues:
               yield str(issue), issue.fields.summary, "%s %s" % (str(issue), issue.fields.summary)

    def update_ticket(self, ticket_id, task_name, date, total_task_duration):

        total_task_duration *= 60 # JIRA works in seconds

        # Get all the worklogs for this ticket.
        worklogs = self._jira.worklogs(ticket_id)

        # All logs are logged with a timestamp of 9am on the day in the current timezone.
        started = datetime.datetime(date.year, date.month, date.day, 9, 0, 0)
        started = get_localzone().localize(started)

        for w in worklogs:
            worklog_started = iso8601.parse_date(w.started)

            # If we've found a time log for the day/task pair.
            if w.comment == task_name and started == worklog_started:
                # ... and the total time is wrong, update it!
                if w.timeSpentSeconds != total_task_duration:
                    w.update(timeSpentSeconds=total_task_duration)

                # We're done!
                break
        else:
            # We haven't found the worklog, so we'll create a new one.
            self._jira.add_worklog(
                ticket_id,
                timeSpentSeconds=total_task_duration,
                started=started,
                comment=task_name
            )


class ShotgunTickets(object):

    def __init__(self, is_headless):
        self._sg, self._sg_self = self._connect(is_headless)

    def _create_new_connection(self, is_headless, data):
        """
        Creates a new Shotgun connection based on user input.

        :param bool is_headless: Indicates if the script was invoked without a shell.
        :param dict data: Data found in the credentials file.

        :returns: A Shotgun connection and a user entity for the loged in user.
        """

        if is_headless:
            raise UserInteractionRequiredError()

        # If the credentials didn't  work or the file didn't exist,
        # ask for the credentials.
        site = _get_credential("Site", data.get("site", ""))
        login = _get_credential("Login", data.get("login", ""))

        sg = None
        # While we don't have a valid connection, keep asking for a password.
        while not sg:
            password = getpass("Password: ")

            # Try to connect again. Assume it'll work.
            try:
                sg = Shotgun(site, login=login, password=password)
                session_token = sg.get_session_token()
            except AuthenticationFault:
                # Authentication failure, reset the connection handle.
                print "Authentication failure. Bad password?"
                print
                sg = None
            else:
                _set_password(site, login, password)

        # Update the data dictionary. Note that the dictionary can also
        # contain information about Toggl, so we need to update it
        # instead of creating a new one.
        data["site"] = site
        data["login"] = login
        data["session_token"] = session_token
        with open(_get_credential_file_path(), "w") as f:
            json.dump(data, f)

        return sg, _get_self(sg, login)

    def _connect(self, is_headless):
        """
        Ensures that the user is logged into Shotgun. If not logged, the credentials are
        queried. If out of date, useful defaults are provided.

        :param bool is_headless: If True, logging won't attempt to ask for credentials.

        :returns: Shotgun connection and associated HumanUser entity.
        """
        # Assume the file is empty originally.
        data = _get_credentials_from_file()

        # No session token, create a new connection.
        if not data.get("session_token"):
            return self._create_new_connection(is_headless, data)
        # Try to create a session with the session token that is stored.
        sg = Shotgun(data["site"], session_token=data["session_token"])
        try:
            return sg, _get_self(sg, data["login"])
        except AuthenticationFault:
            pass

        print "Session token expired. Retrieving password from keyring."

        password = _get_password(data["site"], data["login"])
        # If there is no password, ask for the credentials from scratch.
        if not password:
            print "Password not found in keyring or empty."
            return self._create_new_connection(is_headless, data)

        try:
            sg = Shotgun(data["site"], login=data["login"], password=password)
            data["session_token"] = sg.get_session_token()
            with open(_get_credential_file_path(), "w") as f:
                json.dump(data, f)
            return sg, _get_self(sg, data["login"])
        except AuthenticationFault:
            print "Password in keychain doesnt't seem to work. Did you change it?"
            return self._create_new_connection(is_headless, data)

    def get_tickets(self):
        """
        Retrieves all the the tickets from the sprint in progress.

        :param sg_self: HumanUser entity dictionary for whom we request the tickets.

        :returns: An iterable that yields (shotgun ticket id, shotgun ticket title)
        """
        for item in self._sg.find(
            "Ticket",
            [
                ["sg_sprint.CustomEntity01.sg_status_list", "is", "ip"],
                ["addressings_to", "is", self._sg_self]
            ],
            ["title"]
        ):
            yield item["id"], item["title"], "#%d %s" % (item["id"], item["title"])

    def filter_projects(self, projects):
        """
        Filters out projects that are not understood by this backend
        """
        for project in projects:
            project_name = project["name"]
            if not project_name.startswith("#"):
                continue
            ticket_id, ticket_desc = re.match("#([0-9]+) (.*)", project_name).groups()

            yield int(ticket_id), TogglProject(str(ticket_desc), project["id"], project["active"])

    def update_ticket(self, ticket_id, task_name, day, total_task_duration):

        ticket_link = {"type": "Ticket", "id": ticket_id}

        # Find if we have an entry for this time log.
        timelog_entity = self._sg.find_one(
            "TimeLog",
            [
                ["entity", "is", ticket_link],
                ["description", "is", task_name],
                ["date", "is", day]
            ]
        )

        # Create or update the entry in Shotgun.
        if timelog_entity:
            self._sg.update(
                "TimeLog",
                timelog_entity["id"],
                {"duration": total_task_duration}
            )
        else:
            self._sg.create("TimeLog", {
                "entity": ticket_link,
                "description": task_name,
                "duration": total_task_duration,
                "project": {"type": "Project", "id": 12},
                "date": day
            })
