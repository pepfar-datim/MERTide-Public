# MERtide

A tool for creation of PEPFAR Monitoring, Evaluation, and Reporting (MER) forms in DHIS 2.

**Repo Owner:** Ben Guaraldi [@benguaraldi](https://github.com/benguaraldi)

## Getting Started

In order to run MERtide, you only need Python 3.x with these libraries, most of which should be installed by default: base64, collections, copy, csv, defaultdict, getopt, hashlib, json, operator, os, random, re, requests, string, sys, urllib, xml, zipfile, and zlib.

You will need your `/opt/dhis2/dish.json` to contain the admin user/password info for your DHIS2 instance. A template file exists in the repo

The proper data elements and category option combos must exist in your targeted DHIS2 instance for MERTide to run. For this repo upload `public_metadata.xml` found in the samples folder.

To run MERtide, use a command like this:
```
python3 mertide.py -i controlfile.csv -d disaggs/
```

The ```-i``` refers to the CSV control file and the ```-d``` refers to the directory of HTML templates for disaggs.

## Authors

* **Jim Grace** - *Initial working version* - [jimgrace](https://github.com/jimgrace)
* **Ben Guaraldi** - *Validation rules and other work for v2* - [benguaraldi](https://github.com/benguaraldi)
* **Tim Harding** - *Control file and disagg file formats, subject-matter expertise, many other contributions* - [hardingt](https://github.com/hardingt)
* **Greg Wilson** - *Javascript for form interactivity and off-line functionality* - [Awnage](https://github.com/Awnage)
* **Kyle Pittleman** - *Error handling, additional output files, and other features* - [kpittleman](https://github.com/kpittleman)

Funded by [PEPFAR](https://pepfar.gov). Created by HISP US and [BAO Systems](https://baosystems.com/) for use on [PEPFAR DATIM](https://www.datim.org/).

## License

This project is licensed under the new BSD License. See the [LICENSE.md](LICENSE.md) file for details.

## Support

**Options:**
	 
-n, --noconnection: Parse CSV even if there is no connection to DHIS2
    
-f formuid1234,formid2468, --forms=formuid1234,formid2468: Only include forms with uid formuid1234 and formuid2468

--nofavorites: Do not output favorites

--html: Outputs static HTML versions of the forms for uploading directly to DHIS2

--favoriteisoquarter=2019Q1: Year and Quarter in which to create favorites override (Defaults to current quarter)

-h, --help: Prints this message
