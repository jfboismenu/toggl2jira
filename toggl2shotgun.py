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


import datetime
import iso8601
from common import connect, get_projects_from_toggl, get_tickets_from_shotgun
from pprint import pprint
from itertools import groupby


def _main():
    # Log into Shotgun
    (sg, sg_self), toggl = connect()

    # Get Toggl project information
    shotgun_tickets = dict(get_tickets_from_shotgun(sg, sg_self))
    toggl_projects = get_projects_from_toggl(toggl)
    toggl_projects_to_sg = {project_id: ticket_id for ticket_id, (_, project_id) in toggl_projects}

    time_entries = toggl.TimeEntries.get()

    key = lambda item: item.get("pid")

    # Sort time entries by project.
    time_entries = sorted(time_entries, key=key)

    for project_id, items in groupby(time_entries, lambda item: item.get("pid")):
        ticket_id = toggl_projects_to_sg.get(project_id)
        ticket_link = {"type": "Ticket", "id": ticket_id}
        if not ticket_id:
            continue

        time_logs = {tl["sg_tag__text_"] for tl in sg.find("TimeLog", [["entity", "is", ticket_link]], ["sg_tag__text_"])}

        for item in items:
            if str(item["id"]) not in time_logs:
                sg.create("TimeLog", {
                    "entity": ticket_link,
                    "description": item["description"],
                    "sg_tag__text_": str(item["id"]),
                    "duration": max(int(item["duration"] / 60.0), 1),
                    "project": {"type": "Project", "id": 12},
                    "created_at": iso8601.parse_date(item["start"])
                })

#        if current_ticket != ticket_id:

        # Get the current project from the entry
        # If the project changed, fetch the ticket's timelogs in Shotgun
        # If the entry doesn't have an associated timelog in Shotgun (look at tags), create it.


    # For each ticket in Shotgun, create or update one in Toggl.
    #for ticket_id, (project_desc, project_id) in :



_main()
