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
third_party_location = os.path.join(os.path.dirname(__file__), "3rd_party")
sys.path.append(third_party_location)

# Disable SSL warnings on Windows.
import requests
from requests.packages.urllib3.exceptions import InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

from togglwrapper import Toggl
from shotgun_api3 import Shotgun, AuthenticationFault
from getpass import getpass
import keyring
import json
import os
import re


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
    except:
        return {}


def _create_new_connection(is_headless, data):
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


def _log_into_sg(is_headless):
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
        return _create_new_connection(is_headless, data)

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
        return _create_new_connection(is_headless, data)

    try:
        sg = Shotgun(data["site"], login=data["login"], password=password)
        data["session_token"] = sg.get_session_token()
        with open(_get_credential_file_path(), "w") as f:
            json.dump(data, f)
        return sg, _get_self(sg, data["login"])
    except AuthenticationFault:
        print "Password in keychain doesnt't seem to work. Did you change it?"
        return _create_new_connection(is_headless, data)


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


def connect(is_headless):
    """
    Connects you to both Shotgun and Toggle.

    :param bool is_headless: Indicates if the script is invoked headless.

    :returns: A tuple of ((shotgun connection, user entity dictionary), toggl api key).
    """
    return _log_into_sg(is_headless), _log_into_toggl()
