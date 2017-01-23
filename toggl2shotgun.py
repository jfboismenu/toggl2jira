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


import iso8601
from common import connect, get_projects_from_toggl
from itertools import groupby


def _main():
    # Log into Shotgun
    (sg, sg_self), toggl = connect()

    # Get Toggl project information
    toggl_projects = get_projects_from_toggl(toggl)
    toggl_projects_to_sg = {project_id: ticket_id for ticket_id, (_, project_id) in toggl_projects}

    time_entries = toggl.TimeEntries.get()

    def key_func(item):
        return item.get("pid")

    # Sort time entries by project.
    time_entries = sorted(time_entries, key=key_func)

    for project_id, items in groupby(time_entries, lambda item: item.get("pid")):
        ticket_id = toggl_projects_to_sg.get(project_id)
        ticket_link = {"type": "Ticket", "id": ticket_id}
        if not ticket_id:
            continue

        time_logs = {
            tl["sg_tag__text_"] for tl in sg.find(
                "TimeLog",
                [["entity", "is", ticket_link]],
                ["sg_tag__text_"]
            )
        }
        for item in items:
            if str(item["id"]) not in time_logs:
                sg.create("TimeLog", {
                    "entity": ticket_link,
                    "description": item["description"],
                    "sg_tag__text_": str(item["id"]),
                    "duration": max(int(item["duration"] / 60.0), 1),
                    "project": {"type": "Project", "id": 12},
                    "date": iso8601.parse_date(item["start"]).date()
                })

_main()
