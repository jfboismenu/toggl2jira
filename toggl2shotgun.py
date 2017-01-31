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

from itertools import groupby

import datetime
import iso8601
from common import connect, get_projects_from_toggl
import argparse


def _cmp_time_entry(a, b):
    """
    Compares time entries. Sorts everything by date, project and then task.
    """
    res = cmp(iso8601.parse_date(a["start"]).date(), iso8601.parse_date(b["start"]).date())
    if res != 0:
        return res
    res = cmp(a.get("pid"), b.get("pid"))
    if res != 0:
        return res
    return cmp(a.get("description"), b.get("description"))


def _time_entry_key_func(time_entry):
    """
    Returns a key composed of date, project id and task name.
    """
    return (iso8601.parse_date(time_entry["start"]).date(), time_entry.get("pid"), time_entry.get("description"))


def _sort_time_entries(items):
    """
    Iterates on tasks grouped by date, project and task name.
    """
    return groupby(
        sorted(items, _cmp_time_entry),
        _time_entry_key_func
    )


def _main():

    # Get some time interval options.
    parser = argparse.ArgumentParser(description="Import time entries from Toggl to Shotgun")
    parser.add_argument("--start", "-s", action="store", required=False, default=str(datetime.date.today()))
    parser.add_argument("--end", "-e", action="store", required=False, default=str(datetime.date.today()))

    # Read the options from the command line.
    args = parser.parse_args()

    # Log into Shotgun and toggl.
    (sg, sg_self), toggl = connect()

    # Get Toggl project information
    toggl_projects = get_projects_from_toggl(toggl)
    # Create a map that goes from Toggl project id to a Shotgun ticket id.
    toggl_projects_to_sg = {project_id: ticket_id for ticket_id, (_, project_id) in toggl_projects}

    # Get the entries that the user requested.
    time_entries = toggl.TimeEntries.get(
        start_date="%sT00:00:00+00:00" % args.start,
        end_date="%sT23:59:59+00:00" % args.end
    )

    previous_day = None
    # Group tasks by day, project and task name so we can compute and save a duration for a given task
    # on a given project on a give day.
    for (day, pid, task_name), time_entries in _sort_time_entries(time_entries):

        # if the project is not tracked in Shotgun, skip it!
        ticket_id = toggl_projects_to_sg.get(pid)
        if ticket_id is None:
            continue

        # If we're on a new day, print its header.
        if previous_day != day:
            print day
            previous_day = day

        # Sum all the durationss.
        total_task_duration = int(sum((entry["duration"] for entry in time_entries)) / 60.0)

        # Show some progress.
        print "   Ticket %s, Task %s %.2f minutes" % (
            ticket_id,
            task_name.ljust(40),
            total_task_duration
        )

        ticket_link = {"type": "Ticket", "id": ticket_id}

        # Find if we have an entry for this time log.
        timelog_entity = sg.find_one(
            "TimeLog",
            [
                ["entity", "is", ticket_link],
                ["description", "is", task_name],
                ["date", "is", day]
            ]
        )

        # Create or update the entry in Shotgun.
        if timelog_entity:
            sg.update(
                "TimeLog",
                timelog_entity["id"],
                {"duration": total_task_duration}
            )
        else:
            sg.create("TimeLog", {
                "entity": ticket_link,
                "description": task_name,
                "duration": max(total_task_duration, 1),
                "project": {"type": "Project", "id": 12},
                "date": day
            })

if __name__ == "__main__":
    _main()