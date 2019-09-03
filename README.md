# toggl2jira
Syncs data back and forth between JIRA and Toggl

This package allows to take JIRA issues from a given JIRA board and turn them into Toggl projects and to sync Toggl time logs back to JIRA.

When running for the first time, the script will ask for your JIRA and Toggl information on startup and will save them in a file name `~/.toggl2jira` and in the OS keychain.

# Before first use

1. Open a Toggl account at [toggl.com/signup](https://toggl.com/signup). It's FREE!
2. Go to your [profile](https://toggl.com/app/profile) page and get your API token. Keep that page open because you will need it the first time you launch any of the scripts.
3. Visit your [workspaces](https://toggl.com/app/workspaces) page and create a workspace named `Shotgun`. This is where your tickets will be tracked.

## Running the script

1. Clone the repo
2. Run `pip install -r requirements.txt` to install all the third-parties.
3. Run the script and answer all the questions. Do not worry, the JIRA password is stored in the keychain.

Note: When asked for then project name, this is the prefix for all your tickets in JIRA. For example, ticket `GA-12302` would have a project name of `GA`.
