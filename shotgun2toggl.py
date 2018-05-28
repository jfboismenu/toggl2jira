#!/usr/bin/env python
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

from argparse import ArgumentParser
import sys

from common import (
    connect_to_toggl, get_projects_from_toggl, ShotgunTickets, JiraTickets,
    Toggl2ShotgunError, UserInteractionRequiredError, add_common_arguments
)

DRY_RUN = False


def _main():

    parser = ArgumentParser(description="Import time entries from Toggl to Shotgun")
    add_common_arguments(parser)

    args = parser.parse_args()
    # Log into Shotgun
    (toggl, wid) = connect_to_toggl(args.headless)

    # print "Exporting Shotgun tickets to Toggl..."
    # print "====================================="
    # _import_tickets(ShotgunTickets, toggl, wid, args)

    print
    print "Exporting JIRA issues to Toggl..."
    print "================================="
    _import_tickets(JiraTickets, toggl, wid, args)


def _import_tickets(ticket_factory, toggl, wid, args):

    backend = ticket_factory(args.headless)

    # Get Toggl project information
    toggl_projects = get_projects_from_toggl(toggl)

    toggl_projects = dict(backend.filter_projects(toggl_projects))

    sprint_tickets = set()

    # For each ticket from the current sprint in Shotgun, create or update one in Toggl.
    for ticket_id, ticket_title, project_title in backend.get_tickets():

        # Keep track of the tickets that have been processed.
        sprint_tickets.add(ticket_id)

        # If the ticket is already imported into Toggl
        if ticket_id in toggl_projects:
            # Make sure the description part of the project name matches the title in shotgun.
            if toggl_projects[ticket_id].description != ticket_title:
                # No match, so update!
                if not DRY_RUN:
                    toggl.Projects.update(
                        toggl_projects[ticket_id].id,
                        data={"project": {"name": project_title}}
                    )
                print "Updated project: '%s'" % (project_title,)
            elif not toggl_projects[ticket_id].active:
                if not DRY_RUN:
                    # If the project was archived in the past, unarchive it.
                    toggl.Projects.update(
                        toggl_projects[ticket_id].id,
                        data={"project": {"active": True}}
                    )
                print "Unarchived project: '%s'" % (project_title,)
            else:
                print "Project already in Toggl: %s" % (ticket_title,)
        else:
            if not DRY_RUN:
                # Project is missing, create in Toggl.
                toggl.Projects.create({"project": {"name": project_title, "wid": wid}})
            print "Created project: '%s'" % (project_title,)

    projects_to_archive = set(toggl_projects.keys()) - sprint_tickets

    for ticket_id, toggl_project in toggl_projects.iteritems():
        if ticket_id in projects_to_archive and toggl_project.active:
            print "Archiving project: '%s'" % (toggl_project.description,)
            if not DRY_RUN:
                toggl.Projects.update(toggl_project.id, data={"project": {"active": False}})


if __name__ == '__main__':
    try:
        _main()
        sys.exit(0)
    except UserInteractionRequiredError as e:
        print "Headless invocation failed because credentials were invalid."
        sys.exit(1)
    except Toggl2ShotgunError as e:
        print
        print str(e)
        sys.exit(2)
