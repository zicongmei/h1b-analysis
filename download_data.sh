#!/bin/bash

set -ex

if [[ "x${SKIP_DOWNLOD}" != "xyes" ]]; then
  wget https://raw.githubusercontent.com/dilshod/xlsx2csv/master/xlsx2csv.py

  # Get the case data from dol.gov
  wget https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/H-1B_H-1B1_E-3-FY2020_Q3.xlsx -O h1b.xlsx
  python xlsx2csv.py h1b.xlsx h1b.csv


  # got the salary and geometry data
  wget https://www.flcdatacenter.com/download/OWL_2021_2_TEXT.zip
  unzip OWL_2021_2_TEXT.zip
fi

