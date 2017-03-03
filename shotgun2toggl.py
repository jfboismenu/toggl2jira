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


from common import connect, get_projects_from_toggl, get_tickets_from_shotgun


def _main():
    # Log into Shotgun
    (sg, sg_self), (toggl, wid) = connect()

    # Get Toggl project information
    toggl_projects = dict(get_projects_from_toggl(toggl))

    # For each ticket in Shotgun, create or update one in Toggl.
    for ticket_id, ticket_title in get_tickets_from_shotgun(sg, sg_self):

        # Compute the project title.
        project_title = "#%d %s" % (ticket_id, ticket_title)

        # If the ticket is already imported into Toggl
        if ticket_id in toggl_projects:
            project_desc, project_id = toggl_projects[ticket_id]
            # Make sure the description part of the project name matches the title in shotgun.
            if project_desc != ticket_title:
                # No match, so update!
                toggl.Projects.update(project_id, data={"project": {"name": project_title}})
                print "Updated project '%s'" % (project_title,)
            else:
                print "Ticket %d %s is already in Toggl." % (ticket_id, ticket_title)
        else:
            # Project is missing, create in Toggl.
            toggl.Projects.create({"project": {"name": project_title, "wid": wid}})
            print "Created project '%s'" % (project_title, )

_main()
