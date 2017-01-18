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
    (sg, sg_self), toggl = connect()

    # Get Toggl project information
    toggl_projects = dict(get_projects_from_toggl(toggl))

    # For each ticket in Shotgun, create or update one in Toggl.
    for ticket_id, ticket_title in get_tickets_from_shotgun(sg, sg_self):
        if ticket_id in toggl_projects:
            print "Found", ticket_title
#             project_desc, project_id = toggl_projects[ticket_id]
#             if project_desc != ticket_title:
# #                toggl.Project.update({"project": {"id": project_id, "name": ticket_title}})
#                 return
        else:
            project_name = "#%d %s" % (ticket_id, ticket_title)
            toggl.Projects.create({"project": {"name": project_name}})
            print "Created project '%s'" % (project_name, )

_main()
