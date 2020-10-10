import csv
import logging
import operator
import os

AREA_SURFIX = ['COUNTY', 'TOWN', 'PARISH', '(CITY)']


def setup_log():
  global logger
  logger = logging.getLogger('myapp')
  log_file = 'error.log'
  if os.path.exists(log_file):
    os.remove(log_file)
  hdlr = logging.FileHandler(log_file)
  formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
  hdlr.setFormatter(formatter)
  logger.addHandler(hdlr)
  logger.setLevel(logging.WARNING)


setup_log()


def conver_wage_to_hour(wage):
  if wage > 5000:
    # this is annual wage
    return wage / 50.0 / 40.0
  return wage


class Record:
  def __init__(self, wage, prevaling_wage, level, soc_code, state, county,
      postal_code, employer, geo_data, wage_level):
    self.wage = conver_wage_to_hour(float(wage))
    self.prevaling_wage = prevaling_wage
    if level == 'IV':
      self.level = 4
    else:
      self.level = len(level)
    self.soc_code = soc_code
    self.state = state.upper()
    self.county = county.upper().replace('.', '').replace('  ', ' ')
    for suf in AREA_SURFIX:
      self.county = self.county.replace(' {}'.format(suf), '')
    self.postal_code = postal_code
    self.employer = employer.upper().replace('.', '').replace('  ', ' ')
    self.find_area_code(geo_data)
    self.meet_new_wage = 'U'
    self.check_wage_level(wage_level)

  def find_area_code(self, geo_data):
    state = self.state
    if state in geo_data:
      county = self.county
      if county in geo_data[state]:
        self.area_code = geo_data[state][county]
      else:
        logger.warning(
            '[CNT] County "{}" not found in DB for state {}'.format(county,
                                                                    state))
        self.area_code = -1
    else:
      logger.warning('[STA] State "{}" not found in DB'.format(state))
      self.area_code = -1

  def check_wage_level(self, wage_level):
    if self.area_code != -1:
      if self.area_code in wage_level:
        if self.soc_code in wage_level[self.area_code]:
          if self.level < 1 or self.level > 4:
            logger.warning('[LEV] Got illigal level {}'.format(str(self.level)))
            return
          prevaling_wage = wage_level[self.area_code][self.soc_code][self.level]
          prevaling_wage = conver_wage_to_hour(prevaling_wage)
          if prevaling_wage == 0 or self.wage == 0:
            # missing data
            return
          if self.wage >= prevaling_wage:
            self.meet_new_wage = 'T'
          else:
            self.meet_new_wage = 'F'
        else:
          logger.info('[SOC] SOC code {} not found in DB for area {}'.format(
              self.soc_code, self.area_code))
      else:
        logger.warning(
            '[ARE] Area code {} not found in DB'.format(self.area_code))

  def print_std(self):
    print(self.level, self.wage, self.area_code, self.soc_code,
          self.employer)


def get_area_code():
  filename = 'Geography.csv'
  fields = []
  rows = []

  with open(filename, 'r') as csvfile:
    csvreader = csv.reader(csvfile)
    fields = next(csvreader)
    for row in csvreader:
      rows.append(row)

  content2idx = {
      'Area': -1,
      'StateAb': -1,
      'CountyTownName': -1,
  }
  for i in range(len(fields)):
    name = fields[i]
    if name in content2idx:
      content2idx[name] = i

  geo_data = {}
  for row in rows[:]:
    state = row[content2idx['StateAb']]
    county = row[content2idx['CountyTownName']].upper().replace('.', '')
    for suf in AREA_SURFIX:
      county = county.replace(' {}'.format(suf), '')
    code = row[content2idx['Area']]
    if state not in geo_data:
      geo_data[state] = {}
    if county not in geo_data[state]:
      geo_data[state][county] = code

  return geo_data


def load_wage_level():
  wage_level = {}

  # The ALC_Export File includes data from all industries and should be used for
  # most prevailing wage determinations.
  #
  # The EDC_Export File includes data from educational/research institutions only
  # and should only be used for requests from institutions that are covered by
  # ACWIA.

  for filename in ['ALC_Export.csv']:
    rows = []
    with open(filename, 'r') as csvfile:
      csvreader = csv.reader(csvfile)
      fields = next(csvreader)
      for row in csvreader:
        rows.append(row)

    content2idx = {
        'Area': -1,
        'SocCode': -1,
        'Level1': -1,
        'Level2': -1,
        'Level3': -1,
        'Level4': -1,
    }
    for i in range(len(fields)):
      name = fields[i]
      if name in content2idx:
        content2idx[name] = i

    for row in rows[:]:

      area = row[content2idx['Area']]
      soc_code = row[content2idx['SocCode']]

      if area not in wage_level:
        wage_level[area] = {}
      if soc_code not in wage_level[area]:
        wage_level[area][soc_code] = {}
      for i in range(1, 5):
        level_name = 'Level{}'.format(str(i))
        wage_string = row[content2idx[level_name]]
        if not wage_string:
          wage_string = '0'
        wage_level[area][soc_code][i] = float(wage_string)
  return wage_level


def load_dol_data(geo_data, wage_level):
  # filename = 'small.csv'
  filename = 'h1b.csv'

  rows = []
  with open(filename, 'r') as csvfile:
    csvreader = csv.reader(csvfile)
    fields = next(csvreader)
    for row in csvreader:
      rows.append(row)

  content2idx = {
      'WAGE_RATE_OF_PAY_FROM': -1,
      'PW_WAGE_LEVEL': -1,
      'WORKSITE_POSTAL_CODE': -1,
      'FULL_TIME_POSITION': -1,
      'EMPLOYER_NAME': -1,
      'VISA_CLASS': -1,
      'SOC_CODE': -1,
      'PREVAILING_WAGE': -1,
      'WORKSITE_STATE': -1,
      'WORKSITE_COUNTY': -1,
  }
  for i in range(len(fields)):
    name = fields[i]
    if name in content2idx:
      content2idx[name] = i

  all_records = []
  for row in rows[:]:
    # parsing each column of a row
    if row[content2idx['VISA_CLASS']] != 'H-1B' or row[
      content2idx['FULL_TIME_POSITION']] != 'Y':
      continue
    wage = row[content2idx['WAGE_RATE_OF_PAY_FROM']]
    level = row[content2idx['PW_WAGE_LEVEL']]
    soc_code = row[content2idx['SOC_CODE']]
    postal_code = row[content2idx['WORKSITE_POSTAL_CODE']]
    employer = row[content2idx['EMPLOYER_NAME']]
    prevaling_wage = row[content2idx['PREVAILING_WAGE']]
    state = row[content2idx['WORKSITE_STATE']]
    county = row[content2idx['WORKSITE_COUNTY']]

    all_records.append(
        Record(wage=wage, prevaling_wage=prevaling_wage, level=level,
               soc_code=soc_code, state=state, county=county,
               postal_code=postal_code, employer=employer, geo_data=geo_data,
               wage_level=wage_level))

  return all_records


class Employer_data:
  def __init__(self, name):
    self.name = name
    self.total = 0
    self.passed = 0

  def print_string(self):
    print('{}\t{}\t{:05.2f}%\t{}'.format(str(self.total), str(self.passed),
                                         (self.passed * 100.0 / self.total),
                                         self.name))


def sort_employer_data(company_count):
  company_list = list(company_count.values())
  sorted_company_list = sorted(company_list, key=operator.attrgetter('total'))
  sorted_company_list.reverse()
  return sorted_company_list


if __name__ == "__main__":
  geo_data = get_area_code()
  wage_level = load_wage_level()
  all_records = load_dol_data(geo_data, wage_level)

  count = 0
  meet_count = 0
  company_count = {}
  for record in all_records:
    if record.meet_new_wage != 'U':
      if record.employer not in company_count:
        company_count[record.employer] = Employer_data(record.employer)
      count += 1
      company_count[record.employer].total += 1
      if record.meet_new_wage == 'T':
        meet_count += 1
        company_count[record.employer].passed += 1

  print('total records: ', count, "  meet new requirement: ", meet_count)
  sorted_company_count = sort_employer_data(company_count)
  print('\nTotal\tPassed\tPercent\tEmployer')
  for entry in sorted_company_count[:20]:
    entry.print_string()
