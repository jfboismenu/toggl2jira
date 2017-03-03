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

from togglwrapper import Toggl
from shotgun_api3 import Shotgun
from getpass import getpass
import json
import os
import re


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
        while not cred_value.strip():
            cred_value = raw_input("%s: " % cred_name)
        return cred_value.strip()


def _get_credential_file_path():
    """
    Retrieves the path to the credential file.
    """
    return os.path.expanduser("~/.toggl2shotgun")


def _get_self(sg, login):
    """
    Finds the the human user associated with a given login.

    :param str login: Shotgun login string.

    :returns: HumanUser entity associated with the login.
    """
    return sg.find("HumanUser", [["login", "is", login]])


def _log_into_sg():
    """
    Ensures that the user is logged into Shotgun. If not logged, the credentials are
    queried. If out of date, useful defaults are provided.

    :returns: Shotgun connection and associated HumanUser entity.
    """

    site = None
    login = None
    session_token = None

    # Assume the file is empty originally.
    data = {}
    try:
        # Try to read it in.
        with open(_get_credential_file_path(), "r") as f:
            data = json.load(f)
        site = data["site"]
        login = data["login"]
        session_token = data["session_token"]

        # Try to create a session.
        sg = Shotgun(site, session_token=session_token)
        return sg, _get_self(sg, login)
    except:

        # If the credentials didn't  work or the file didn't exist,
        # ask for the credentials.
        site = _get_credential("Site", site)
        login = _get_credential("Login", login)
        password = getpass("Password: ")

        # Try to connect again. Assume it'll work.
        sg = Shotgun(site, login=login, password=password)
        session_token = sg.get_session_token()

        # Update the data dictionary. Note that the dictionary can also
        # contain information about Toggl, so we need to update it
        # instead of creating a new one.
        with open(_get_credential_file_path(), "w") as f:
            data["site"] = site
            data["login"] = login
            data["session_token"] = session_token
            json.dump(data, f)

    return sg, _get_self(sg, login)


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

        return Toggl(api_key)
    except:
        api_key = _get_credential("Toggl API Key", api_key)

        toggl = Toggl(api_key)

        with open(_get_credential_file_path(), "w") as f:
            data["toggl"] = api_key
            json.dump(data, f)

        return toggl


def _get_workspace_id(toggl):
    """
    Retrieves the one and only workspace id we are using.
    """
    # Get the one and only workspace id.
    return toggl.Workspaces.get()[0]["id"]


def get_projects_from_toggl(toggl):
    """
    Retrieves all projects from Toggl.

    :returns: An iterable that yields (shotgun ticket id, (toggl project title, toggl project id)).
    """
    workspace_id = _get_workspace_id(toggl)

    for project in toggl.Workspaces.get_projects(workspace_id):
        project_name = project["name"]
        if not project_name.startswith("#"):
            continue
        ticket_id, ticket_desc = re.match("#([0-9]+) (.*)", project_name).groups()

        yield int(ticket_id), (str(ticket_desc), project["id"])


def get_tickets_from_shotgun(sg, sg_self):
    """
    Retrieves all the the tickets from the sprint in progress.

    :param sg_self: HumanUser entity dictionary for whom we request the tickets.

    :returns: An iterable that yields (shotgun ticket id, shotgun ticket title)
    """
    for item in sg.find(
        "Ticket",
        [
            ["sg_sprint.CustomEntity01.sg_status_list", "is", "ip"],
            ["addressings_to", "is", sg_self]
        ],
        ["title"]
    ):
        yield item["id"], item["title"]


def connect():
    """
    Connects you to both Shotgun and Toggle.

    :returns: A tuple of ((shotgun connection, user entity dictionary), toggl api key).
    """
    return _log_into_sg(), _log_into_toggl()
