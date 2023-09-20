# EEPatchNotesExtractor

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
<!-- TOC -->

## Usage

Make sure to install the required packages from the [requirements.txt](requirements.txt) file. This script was tested
with Python 3.10.

Command line help:

```
usage: main.py [-h] mode output_path [-c] [-f] [-url URL] [-r RATELIMIT] [--ratelimit_rnd_fac RATELIMIT_RND_FAC]

Patch notes scrapper for the game Eve Echoes


positional arguments:
  mode                  Options: load_all,load_new,create_html
                        Select the mode, must be load_all, load_new or create_html
  output_path           The output directory

options:
  -h, --help            show this help message and exit
  -c, --cache           Use the cached patch note urls (new patch notes will be missing), only effective for load_all
  -f, --force_reload    Reload and overwrite already (locally) saved patch notes, only effective for load_all
  -url URL              The url for the patch notes, should contain {index} for the page number
  -r RATELIMIT, --ratelimit RATELIMIT
                        The delay between http requests in seconds
  --ratelimit_rnd_fac RATELIMIT_RND_FAC
                        A factor that gets multiplied with a random number between 0 and 1, the result will get added to the rate limit (will be random for every request)

```
## Modes

The argument `output_path` specifies the directory for saving the downloaded and processed files. There are three
different modes available, the path should stay the same for all modes (as they all use the same files). The raw
patch note files can be found in `output_path/patch_notes`.

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
