# toggl2shotgun
Syncs data back and forth between Shotgun and Toggl

This package allows to take Shotgun tickets and turn them into Toggl projects (`shotgun2toggl`) and to take Toggl event data and submit them as Time Logs on Shotgun tickets (`toggl2shotgun`).

Both scripts will ask for your Shotgun and Toggl credentials on startup and will save them in a file name `~/.toggl2shotgun`. It will reuse them on successive runs.

# Before first use
You need to run `python -r requirements.txt` in order to add the Shotgun API and toggl API to your Python environment

## shotgun2toggl

This script will create Toggl projects with the name "#`shotgun_ticket_number` `shotgun_ticket_title`". If the project already exists, it will ensure that the `shotgun_ticket_tile` part is up to date with the title in Shotgun.

## toggl2shotgun

This script will create Shotgun Time Logs on tickets for every project time log that exist in Toggl for the last 7 days. You can tweak with using the `--start` and `-end` command line arguments.


