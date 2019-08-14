# MERtide
**Repo Owner:** Ben Guaraldi [@benguaraldi](https://github.com/benguaraldi)

A tool for creation of PEPFAR Monitoring, Evaluation, and Reporting (MER) forms in DHIS 2.

## Getting Started

In order to run MERtide, you only need Python 3.x with these libraries, most of which should be installed by default: base64, collections, copy, csv, defaultdict, getopt, hashlib, json, operator, os, random, re, requests, string, sys, urllib, xml, zipfile, and zlib.

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

Funded by [PEPFAR](https://pepfar.gov). Created by HISP US and [BAO Systems](https://baosystems.com/) for use on [PEPFAR DATIM](https://www.datim.org/).

## License

This project is licensed under the new BSD License. See the [LICENSE.md](LICENSE.md) file for details.
