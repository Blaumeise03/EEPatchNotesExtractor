# EEPatchNotesExtractor

![GitHub last commit (branch)](https://img.shields.io/github/last-commit/Blaumeise03/EEPatchNotesExtractor/master)
![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Blaumeise03/EEPatchNotesExtractor?label=latest)
![GitHub forks](https://img.shields.io/github/forks/Blaumeise03/EEPatchNotesExtractor)
![GitHub Repo stars](https://img.shields.io/github/stars/Blaumeise03/EEPatchNotesExtractor)


This is a web scraper to extract the patch notes for the game [Eve Echoes](https://www.eveechoes.com/). It searches on
https://www.eveechoes.com/news/updata/ for all published patch notes and downloads them. After downloading they can be
combined into a single html file which can be used to search for specific updates.

<!-- TOC -->
* [EEPatchNotesExtractor](#eepatchnotesextractor)
  * [Usage](#usage)
  * [Modes](#modes)
    * [load_all](#loadall)
    * [load_new](#loadnew)
    * [create_html](#createhtml)
  * [Installation](#installation)
  * [Automation](#automation)
<!-- TOC -->

## Usage

Make sure to install the required packages from the [requirements.txt](requirements.txt) file. This script was tested
with Python 3.10.

Command line help:

```
usage: main.py [-h] [-c] [-f] [-url URL] [-r RATELIMIT] [-rd RATELIMIT_RND_FAC] [-cp COPY_TO] {load_all,load_new,export_html,load_all_export,load_new_export} output_path
                                                                                                                                                                         
Patch notes scrapper for the game Eve Echoes                                                                                                                             
                                                                                                                                                                         
positional arguments:                                                                                                                                                    
  {load_all,load_new,export_html,load_all_export,load_new_export}                                                                                                        
                        Select the mode, must be load_all, load_new, export_html, load_all_export, load_new_export                                                       
  output_path           The output directory                                                                                                                             
                                                                                                                                                                         
options:                                                                                                                                                                 
  -h, --help            show this help message and exit
  -c, --cache           Use the cached patch note urls (new patch notes will be missing), only effective for load_all
  -f, --force_reload    Reload and overwrite already (locally) saved patch notes, only effective for load_all
  -url URL              The url for the patch notes, should contain {index} for the page number
  -r RATELIMIT, --ratelimit RATELIMIT
                        The delay between http requests in seconds
  -rd RATELIMIT_RND_FAC, --ratelimit_rnd_fac RATELIMIT_RND_FAC
                        A factor that gets multiplied with a random number between 0 and 1, the result will get added to the rate limit (will be random for every request)
  -cp COPY_TO, --copy_to COPY_TO
                        Copy the generated html to the target path
```
## Modes

The argument `output_path` specifies the directory for saving the downloaded and processed files. There are three
different modes available, the path should stay the same for all modes (as they all use the same files). The raw
patch note files can be found in `output_path/patch_notes`.

It is also possible to combine one of the two loading modes with the html export. For example `load_new_export` will 
chain `load_all` and `export_html`.

### load_all
This mode loads all patch notes that are available and downloads them. While doing so, it generates a cache file
containing all found patch notes (but not the content itself). This cache can be reused via the `-c` / `--cache`
argument. This will save time as the loading of all available patch notes requires a lot of requests.

By default, the scraper will only download the patch notes that are not yet saved locally. If the patch note was already
downloaded, it will be skipped. A reload of old patch notes can be forced via the `-f` / `--force_reload` argument.

The scraper will apply a randomised rate limit to all requests, the rate limit is calculated in seconds and can be
adjusted with the `-r` / `--ratelimit` and `--ratelimit_rnd_fac` arguments. The formula is as follows:
```
RATE_LIMIT_SECONDS + RATE_LIMIT_RAND_FAC * random.random()
```

### load_new
This mode will only load the latest patch notes, until it finds a page that only contains old patch notes. It is
recommended to use this mode for updating the patch notes as this moda drastically reduces the number of 
requests compared to `load_all`.

### create_html
This mode uses the downloaded data from the previous two modes and generates a complete html file containing all patch
notes. The output file can be found under `output_path/patch_notes.html` (with `**{PATH}**` being the specified output
directory).
The generated html file does not use any external files and does not use any JavaScript. It can be used as
a standalone website. You can find and customize the template in [resources/patch_notes_template.html](resources/patch_notes_template.html).

The template contains two elements with ids:
```html
<br id="timestamp"/>
```
This tag will get *replaced* with the current timestamp (in ISO-format, e.g. `2023-09-20 19:20`).

```html
<div class="content" id="patch-notes">

</div>
```
This div will get *filled* with all patch notes. Every patch note is in a `<div>` by itself which has the class 
`patch-note` an id like `patch-note-2023-09-20` which can be used for linking to a specific patch note. The header of
the patch note is a `div` with class `patch-title` and the content is inside a `div` with class`patch-content`.

## Installation
It is recommended to install this programm in a python venv. To do so, use the command
```shell
python -m venv /path/to/EEPatchNotesExtractor
```
> Depending on the installed python versions, a specific version might have to be specified, e.g. `python3 -m ...` or 
> `python3.11 -m ...`.

Inside the folder the venv can be activated with `source bin/activate` (Linux) or `venv\Scripts\activate` (Windows). The
exact command might differ depending on your OS. When the venv is activated, the script can be executed via
```shell
# Initial loading with reduced rate limits.
python main.py load_all_export data -r 0.5 --ratelimit_rnd_fac 0.5

# Loads only the new patch notes and creates the .html
python main.py load_new_export data
```

## Automation
This section describes on how to automate the updating using a `systemd` Service (Linux). This requires that the program
has been installed as shown above. An example `systemd` service might look as follows. In this example, the program is 
installed in `/home/echoesnotes/extractor/` (such that the `main.py` is located within the `extractor` directory).

The service automatically downloads the new patch notes (the program gets executed as the user `echoesnotes` for 
safety reasons) and afterward the html file gets copied into the webserver directory (in this case `/var/www/html`).

Make sure the whole user directory belongs
to the user, if you did upload the files as root (or another user), the permissions will be screwed up. In that case use
```shell
chown -R echoesnotes:echoesnotes /home/echoesnotes
# or
chown -R echoesnotes /home/echoesnotes
```
to fix the permissions. You can add a user with
```shell
adduser echoesnotes --system
```
The --system parameter will make a user that can not be logged in like a regular user, you also won't have to define
a password.

Now you have to create the service:

```unit file (systemd)
# echoesnotes.service
[Unit]
Description=Eve Echoes Patch Notes Extractor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=echoesnotes
WorkingDirectory=/home/echoesnotes/extractor
ExecStart=/home/echoesnotes/extractor/bin/python main.py load_new_export data
# Copy with root privileges (+) to www directory
ExecStartPost=+cp /home/echoesnotes/extractor/data/patch_notes.html /var/www/html/EveEchoesPatchNotes.html

[Install]
WantedBy=multi-user.target
```
To run it automatic every week, we also need a timer. This will run the script every wednesday at 12:00 *local* time.
Depending on your servers timezone, you have to adjust the time accordingly. 
```unit file (systemd)
# echoesnotes.timer
[Unit]
Description=Run the Eve Echoes Patch Notes Extractor every week after the maintenance.

[Timer]
OnCalendar=Wed *-*-* 12:00:00
Persistent=true

[Install]
WantedBy=timers.target
```
Both files have to be saved/copied to `/etc/systemd/system`. Enable the `.timer` afterward:
```shell
systemctl enable echoesnotes.timer
systemctl start echoesnotes.timer
```
Do not enable the `echoesnotes.service` or else it will get executed after every reboot (unless that's what you want).
But you can manually start the update script once with
```shell
systemctl start echoesnotes.service
```
