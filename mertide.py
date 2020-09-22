#!/usr/bin/env python3

# USAGE: ./mertide.py -i merform.csv -d /path/to/disagg/files/ [-n] [-f formuid1234,formid2468] [-h]
#		 ./mertide.py -i merdirectory -d /path/to/disagg/files/ [-n] [-f formuid1234,formid2468] [-h]
#		 ./mertide.py --input=merform.csv --disaggs=/path/to/disagg/files/ [--noconnection] [--forms="formuid1234,formid2468"] [--help]

import os
import re
import csv
import sys
import copy
import json
import zlib
import base64
import getopt
import pprint
import random
import string
import urllib
import hashlib
import zipfile
import operator
import requests
import datetime
from collections import defaultdict
from xml.sax.saxutils import escape

# Output logging information to the screen and to logFile
# logFile is updated as the script runs, instead of only being complete at the end
def log(line, level = False):
	if level == 'warn':
		prefix = 'Warning: '
	elif level == 'severe':
		prefix = 'SEVERE: '
		global severe
		severe = True
	else:
		prefix = ''
	print(prefix + line)
	logFile.write(prefix + line + '\n')
	logFile.flush()
	os.fsync(logFile.fileno())

def getNumeratorDenominator(shortName):
	numeratorDenominator=re.sub('^.* \((.*)\).*', r'\1', shortName)
	numeratorDenominator=re.sub('([^,]*),.*', r'\1', numeratorDenominator)

	if numeratorDenominator != 'D' and numeratorDenominator != 'N':
		return 'Other'

	return numeratorDenominator

def getDisagg(shortName):
	if shortName.count(',') < 2:
		return 'No Disagg'
	else:
		disagg=re.sub('^.* \((.*)\).*', r'\1', shortName)
		disagg=re.sub('.*, (.*)', r'\1', disagg)
	return disagg

# Remove files with funny names
def filenameChecker(filename):
	bumFiles=['.DS_Store']
	if filename in bumFiles:
		return False
	return True

# current fiscal year for fyoct
def curFyOct():
	curQ=(int(datetime.datetime.now().strftime("%m"))+2)//3
	curY=int(datetime.datetime.now().strftime("%Y"))
	if curQ == 4:
		curY = curY + 1
	return str(curY)

# current year
def curYear():
	return str(int(datetime.datetime.now().strftime("%Y")))

def curQuarter():
	curQ = (int(datetime.datetime.now().strftime("%m"))+2) // 3
	return str(curQ)

def curISOQuarter():
	return "FY"+curYear()+"Q"+curQuarter()

# FIXME
def ISOQuarterToISOSAApr(ISOQuarter):
	#2018Q4 -> 2018AprilS2
	#2019Q1 -> 2018AprilS2
	#2019Q2 -> 2019AprilS1
	#2019Q3 -> 2019AprilS1

	year = int(ISOQuarter[:4])
	quarter = int(ISOQuarter[-1])
	fyaprYear=0
	fyaprSA=0

	if quarter == 1:
		fyoctYear = year-1
		fyaprSA = 2
	elif quarter == 2:
		fyoctYear = year
		fyaprSA = 1
	elif quarter == 3:
		fyoctYear = year
		fyaprSA = 1
	elif quarter == 4:
		fyoctYear = year
		fyaprSA = 2

	return str(fyoctYear)+"AprilS"+str(fyaprSA)

def ISOQuarterToISOFYOctTARGET(ISOQuarter):
	year = int(ISOQuarter[:4])
	fyoctYear = year
	return str(fyoctYear)+"Oct"

def ISOQuarterToISOFYOct(ISOQuarter):
	year = int(ISOQuarter[:4])
	quarter = int(ISOQuarter[-1])
	fyoctYear = 0

	if quarter < 4:
		fyoctYear = year - 1
	else:
		fyoctYear = year

	return str(fyoctYear)+"Oct"

def pepfarReportingQuarter(ISOQuarter,frequency):
	quarter = int(ISOQuarter[-1])

	if frequency == 'Quarterly':
		return True
	elif frequency == 'Semiannually' and (quarter == 1 or quarter == 3):
		return True
	elif frequency == 'Annually' and quarter == 3:
		return True

	return False



def ISOQuarterToFYOctQuarter(ISOQuarter):
	year = int(ISOQuarter[:4])
	quarter = int(ISOQuarter[-1])
	fyoctYear=0
	fyoctQuarter=0

	if quarter == 1:
		fyoctQuarter = 2
		fyoctYear = year
	elif quarter == 2:
		fyoctQuarter = 3
		fyoctYear = year
	elif quarter == 3:
		fyoctQuarter = 4
		fyoctYear = year
	elif quarter == 4:
		fyoctQuarter = 1
		fyoctYear = year+1

	return str(fyoctYear)+"Q"+str(fyoctQuarter)

# Check to see if a string is a properly formatted DHIS2 uid
def isDhisUid(string):
	if (len(string) != 11):
		return False
	if not bool(re.search('[A-Za-z]', string[:1])):
		return False
	if not bool(re.search('[A-Za-z0-9]{9}', string[1:11])):
		return False
	return True

# Find a data element, either using the dataElementCache or DHIS2
def getDataElement(uid, optionCombo=False):
	if uid not in dataElementCache:
		d = requests.get(api + 'dataElements.json', cookies=jsessionid,
						 params = {'paging': False, 'fields': 'name,shortName', 'filter': 'id:eq:' + uid})
		try:
			dataElementCache[uid] = d.json()['dataElements'][0]
		except:
			dataElementCache[uid] = {}
	d = dataElementCache[uid]
	if d:
		d['id'] = uid
		d['optionCombo'] = False
		if optionCombo:
			d['optionCombo'] = getCoc(optionCombo, uid)
	else:
		log('Data element ' + uid + ' is missing on ' + config['dhis']['baseurl'], 'warn')
	return d

# Generate a random uid
def makeUid():
	uid = random.choice(string.ascii_letters)
	for i in range(0, 10):
		uid += random.choice(string.ascii_letters+'0123456789')
	return uid

# Return 5+input char ssid. This should be max 8 total, #TODO, limit returned result to 8 chars.
def makeSsid(htabType):
	ssid = random.choice(string.ascii_letters)
	for i in range(0, 4):
		ssid += random.choice(string.ascii_letters+'0123456789')
	return ssid + htabType

# Generate an SSID deterministically from a unique string, using sha
def makeSsidHash(uniqueName, htabType):
	sha = hashlib.sha1((uniqueName).encode())
	num = int(sha.hexdigest(), 16)
	uid = ''
	for i in range(0, 5):
		mod = num % 26
		num = int(num / 26)
		uid += string.ascii_letters[mod]
	uid += htabType
	return uid

# Generate a UID deterministcally from a unique string, using sha
def makeUidHash(s):
	if s=='':
		return 'NotAUID'
	hashBytes = bytearray(hashlib.sha256((s).encode()).digest())
	uid = string.ascii_letters[hashBytes[0] % 52]
	for i in range(1, 11):
		uid += (string.ascii_letters+string.digits)[hashBytes[i] % 62]
	return uid

# Turn string s into a name that's safe for metadata usage
def safeName(s):
	s = s.replace('<', '_lt_') \
		.replace('>', '_gt_') \
		.replace('+', '_plus_')
	s = re.sub('[\[\(\)\-\s\:,\\\|^&/]', '_', s)
	s = re.sub('_+', '_', s)
	s = re.sub('_$', '', s)
	return s.lower()
	
# Same as safeName, but make it all uppercase as well
def codeName(s):
	return safeName(s).upper()

# Within a vertical tab, find which horizontal tabs are present.
def findHtabs(vtab):
	htabsPresent = set([]) # Set of htabs present in this list of rows
	for indicator in vtab['indicators']:
		for row in indicator['rows']:
			if (row['de_dsd1']): htabsPresent.add("DSD")
			if (row['de_ta1']): htabsPresent.add("TA")
			if (row['de_cs1']): htabsPresent.add("CS")
			if (row['de_na1']): htabsPresent.add("NA")
	htabs = []
	for htab in allHtabs:
		if (htab['type'] in htabsPresent):
			htabs.append(htab)
	return htabs

# Within a row, find all data elements.
def findDataElementsFromRow(row):
	dataElementsPresent = set([]) # Set of dataelements in the row
	for de in ['de_dsd1', 'de_dsd2', 'de_dsd3', 'de_ta1', 'de_ta2', 'de_ta3', 'de_cs1', 'de_cs2', 'de_cs3', 'de_na1', 'de_na2', 'de_na3']:
		if row[de]: dataElementsPresent.add(row[de])
	return dataElementsPresent

# Find out if an indicator should be displayed in a given HTAB.
def htabInIndicator(htab, indicator):
	for row in indicator['rows']:
		if row['de_' + htab['type'].lower() + '1']:
			return True
	return False

# Add a dataElement to the data element list for this form
# and to all the dataElementGroups belonging to this form
def addDataElement(form, uid, groups, frequency, categoryCombo = False):
	form['formDataElements'].add(uid)
	for group in groups:
		dataElementGroups[group].add(uid)
	if categoryCombo:
		catComboCache[uid] = categoryCombo
	# Adds DEs used in forms to directory and label target/result.
	if uid in masterDataElementList:
		if form['name'].count('Targets') > 0:
			formDataElementList[uid] = {'type': 'Target', 'name': masterDataElementList[uid]['name'], 'form': form['name'], 'categoryCombo': categoryCombo, 'frequency': frequency}
		else:
			formDataElementList[uid] = {'type': 'Target', 'name': masterDataElementList[uid]['name'], 'form': form['name'], 'categoryCombo': categoryCombo, 'frequency': frequency}
	else:
		log('Cannot find data element ' + uid + ' in DHIS2')

# Query the api to get all DE and put them in a master directory.
def getAllDataElements():
	d = requests.get(api + 'dataElements.json', cookies=jsessionid,
			params = {'paging': False, 'fields': 'name,shortName,id,categoryCombo[id]'})

	for i in d.json()['dataElements']:
		id = i['id']
		masterDataElementList[id] = {'name' : i['name'], 'shortName': i['shortName'], 'id': i['id'], 'categoryComboID' : i['categoryCombo']['id']}

# Query the api to get all Category Option Combos and put them in a master directory
def getAllCategoryOptionCombos():
	d = requests.get(api + 'categoryOptionCombos.json', cookies=jsessionid,
			params = {'paging': False, 'fields': 'name,id,categoryCombo[name,id]'})
	for i in d.json()['categoryOptionCombos']:
		id = i['id']
		masterCategoryOptionComboList[id] = {'name' : i['name'], 'id': i['id'], 'categoryComboName': i['categoryCombo']['name'], 'categoryComboID' : i['categoryCombo']['id']}

# Puts DE from forms into a list to be put in the data store.



def getDataElementCadence():
	for key, value in formDataElementList.items():
		if masterDataElementList[key]['shortName'].count('TARGET') == 0 and checkDataElementQuarter(formDataElementList[key]['frequency']):
			a = {}
			a['uid'] = masterDataElementList[key]['id']
			a['shortName'] = masterDataElementList[key]['shortName']
			dataElementCadence.append(a)
			

def checkDataElementQuarter(frequency):
	quarter = int(favoritesISOQuarter[-1])
	if frequency == 'Annually' and quarter == 3:
		return True
	elif frequency == 'Semiannually' and (quarter == 1 or quarter == 3):
		return True
	elif frequency == 'Quarterly' and (quarter >= 1 and quarter <= 4):
		return True
	else:
		return False
		

# Determine whether any of a category option combo's category options are found
# within a category
def findCo(category, coc):
	for option in category:
		for co in coc['categoryOptions']:
			if co['name'] == option:
				return co['name']
	return False

def getCocsFromOptions(options, uid):
	optionCacheId = str(options) + '_' + uid
	try:
		if optionCacheId not in optionCache:
			req = requests.get(api + 'dataElements/' + uid + '.json', cookies=jsessionid,
				params = {'paging': False, 'fields': 'name,id,categoryCombo[name,id,categories[name,id,categoryOptions[name,id]],categoryOptionCombos[name,id,categoryOptions[name,id]]]'})
			categoryCache = []
			found = []
			categories = req.json()['categoryCombo']['categories']
			for i in range(len(categories)):
				categoryCache.append({})
				for co in categories[i]['categoryOptions']:
					if co['name'] in options:
						found.append(co['name'])
						categoryCache[i] = {co['name']: True}
						break
					else:
						categoryCache[i][co['name']] = True

			for option in options:
				if not(option in found):
					raise ValueError('The option ' + option + ' was not found in the categories for data element ' + uid)

			optionCache[optionCacheId] = []
			cocs = req.json()['categoryCombo']['categoryOptionCombos']
			for coc in cocs:
				for category in categoryCache:
					found = findCo(category, coc)
					if not(found):
						break

				if found:
					optionCache[optionCacheId].append(coc['id'])
					cocCache[coc['id']] = coc['id']
					if found in options:
						cocCache2[coc['id']] = found
					else:
						cocCache2[coc['id']] = options[0]

	except:
		optionCache[optionCacheId] = []
	return optionCache[optionCacheId]

# Get the category option combo that matches a given name and element
def getCoc(name, element):
	try:
		if (name + '_' + element) not in cocCache and name not in cocCache:
			req = requests.get(api + 'dataElements/' + element + '.json', cookies=jsessionid,
				params = {'paging': False, 'fields': 'id,name,categoryCombo[id,name,categoryOptionCombos[id,name]]',
							'filter': 'categoryCombo.categoryOptionCombos.name:eq:' + name})
			for coc in req.json()['categoryCombo']['categoryOptionCombos']:
				cocCache2[coc['id']] = coc['name']
				if coc['name'] == name:
					cocCache[name + '_' + element] = coc['id']
			if (name + '_' + element) not in cocCache:
				cocCache[name + '_' + element] = False
	except:
		cocCache[name + '_' + element] = False
	if name in cocCache:
		return cocCache[name]
	else:
		return cocCache[name + '_' + element]

def getUids(term, suffix, alluids, uidCache):
	if term == 'R':
		return alluids
	elif (term + '_' + suffix) in uidCache:
		return uidCache[term + '_' + suffix]
	else:
		return []

# Given a MERtide expression, returns an array of MERtide expressions
# Used to split MERtide expressions with the command "options"
# e.g., R.options:"25-29","30-34" will become R.option:"25-29"+R.option:"30-34"
def splitMertideExpression(expression):
	a = []
	if '.options:' in expression:
		try:
			r = re.compile(r'(.+)\.options\:\s*\"([^:]+)\"(.*)')
			s = r.search(expression)
			for e in s.group(2).split('","'):
				a.append(s.group(1) + '.option:"' + e + '"' + s.group(3))
		except:
			log('Syntax error: ' + expression + ' has an option that cannot be parsed', 'warn')
			return

	b = []
	for i in a:
		if '.options:' in i:
			b.extend(splitMertideExpression(i))
		else:
			b.append(i)
	if b:
		return(b)
	else:
		return([expression])

# Given a MERtide expression, returns an array of parsed expression, data element,
# category option, category options list, and category option combo
def parseMertideExpression(expression):
	# a is the variable to be returned, the array mentioned above
	a = [urllib.parse.unquote(expression).strip(' '), False, [], [], []]
	while '.optionCombo:' in a[0]:
		try:
			r = re.compile(r'(.+)\.optionCombo\:\s*\"(.*)\"')
			s = r.search(a[0])
			a[4].append(s.group(2)) # category option combos
			a[0] = s.group(1)
		except:
			log('Syntax error: ' + a[0] + ' has an option combo that cannot be parsed', 'warn')
			break

	while '.options:' in a[0]:
		try:
			r = re.compile(r'(.+)\.options\:\s*([^:\.]*)(.*)')
			s = r.search(a[0])
			a[3].append(s.group(2)) # options lists
			a[0] = s.group(1) + s.group(3)
		except:
			log('Syntax error: ' + a[0] + ' has options that cannot be parsed', 'warn')
			break

	while '.option:' in a[0]:
		try:
			r = re.compile(r'(.+)\.option\:\s*\"([^:]*)\"(.*)')
			s = r.search(a[0])
			a[2].append(s.group(2)) # category options
			a[0] = s.group(1) + s.group(3)
		except:
			log('Syntax error: ' + a[0] + ' has an option that cannot be parsed', 'warn')
			break

	if '.de' in a[0]:
		try:
			r = re.compile(r'(.+)\.de(.*)')
			s = r.search(a[0])
			a[1] = int(s.group(2)) # data element
			a[0] = s.group(1)
		except:
			log('Syntax error: ' + a[0] + ' has an element that cannot be parsed', 'warn')

	return a

# Given a MERtide expression, returns an array of [vr, js, missingValue] where
# vr is an array of operands for validation rules, js is an array of operands for javascript,
# and missingValue is our sense of what to give DHIS2 for the missing value rule
def processMertideExpression(expression, rule, missingValue, which, uidCache, skipCache, dataElementCache):
	vr = []
	js = []
	names = []
	[ignore, operator, ignore2, suffix, alluids, allssids, priority, ruleText, ignore3] = rule
	if '+' in expression:
		termsNotSplit = expression.split('+')
	else:
		termsNotSplit = [expression]

	for terms in termsNotSplit:
		for term in splitMertideExpression(terms):
			termnames = []
			[term, element, options, ignore, optionCombos] = parseMertideExpression(term)

			try:
				if operator == 'autocalculate' or operator == 'exclusive_pair':
					if term == 'R':
						ssids = allssids
						uids = alluids
					else:
						ssids = [makeSsidHash(term, suffix)]
						uids = uidCache[term + '_' + suffix]

					for i in range(len(ssids)):
						if element:
							js.append([ssids[i], [uids[element-1]]])
						elif options:
							cocs = getCocsFromOptions(options, uids[i])
							js.append([ssids[i], cocs])
						elif optionCombos:
							for coc in optionCombos:
								optionCombo = getCoc(coc, uids[i])
								js.append([ssids[i], [optionCombo]])
						else:
							js.append([ssids[i]])

				if operator != 'autocalculate':
					uids = getUids(term, suffix, alluids, uidCache)

					if element:
						uids = [uids[element-1]]
					for u in uids:
						if options:
							cocs = getCocsFromOptions(options, u)
							for coc in cocs:
								vr.append(getDataElement(u, coc).copy())

							termnames.append(getDataElement(u, False)['shortName'] + ' option ' + ' and option '.join(options))

							if optionCombos:
								log('Syntax error: optionCombo used at the same time as option or options in rule ' + ruleText, 'warn')

						else:
							if optionCombos:
								for coc in optionCombos:
									vr.append(getDataElement(u, coc).copy())
								termnames.append(dataElementCache[u]['shortName'] + ' option combo ' + 'and option combo '.join(optionCombos))
							else:
								vr.append(getDataElement(u, False).copy())
								termnames.append(getDataElement(u, False)['shortName'])

					if missingValue != 'NEVER_SKIP' and operator != 'exclusive_pair':
						q = term
						if term == 'R':
							q = priority
						elif term in skipCache:
							q = skipCache[term]

						if q in skip:
							missingValue = 'SKIP_IF_ALL_VALUES_MISSING'
						elif q in neverskip:
							missingValue = 'NEVER_SKIP'
						else:
							log('Syntax error: ' + q + ' not associated with missing value strategy for rule ' + ruleText, 'warn')

			except Exception as e:
				log('Syntax error: Problem compiling ' + which + ' expression in ' + ruleText, 'warn')

		if operator != 'autocalculate':
			if '.options:' in terms:
				[term, element, options, optionses, optionCombos] = parseMertideExpression(terms)

				uids = getUids(term, suffix, alluids, uidCache)
				namesuffix = suffix

				if element:
					uids = [uids[element-1]]
				for u in uids:
					namesuffix = ' options ' + ' and options '.join(optionses).replace('","', ', ').replace('"', '')
					if options:
						namesuffix = namesuffix + ' and option ' + ' and option '.join(options)
					names.append(getDataElement(u, False)['shortName'] + namesuffix)
			else:
				names.extend(termnames)

	return [vr, js, names, missingValue]

# Add an expression to a validation rule and returns the modified validation rule
def addExpression(j, side, sideData):
	if ('description' in j[side]):
		j[side]['description'] += ' + value'
		j[side]['expression'] += '+'
	else:
		j[side]['description'] = 'Value'
		j[side]['expression'] = ''

	j[side]['dataElements'].add(sideData['id'])

	if (sideData['optionCombo']):
		j[side]['description'] += ' of element ' + sideData['id'] + ' (' + sideData['name'] + ') / ' + cocCache2[sideData['optionCombo']]
		j[side]['expression'] += '#{' + sideData['id'] + '.' + sideData['optionCombo'] + '}'
	else:
		j[side]['description'] += ' of element ' + sideData['id'] + ' (' + sideData['name'] + ')'
		j[side]['expression'] += '#{' + sideData['id'] + '}'

	return j

# Given an array of elements, turn it into an array of hashes of {'id': element}
def reformatDataElements(elements):
	a = []
	for e in elements:
		a.append({'id': e})
	return a

# Create a string from an expression, in which two equivalent expressions will have the same string
#
# Note that in very rare circumstances, will give a false positive; for instance,
# {#aaaaaaaaaaa}+{#bbbbbbbbbbb} will be considered to be the same as {#aaaaaaaaaab}+{#abbbbbbbbbb}
# Hopefully that never occurs in practice!
def hashExpression(expression):
	return ''.join(sorted(expression))

# Create a string from a rule, in which two equivalent rules will have the same string
# Deals with the situation of a + b <= c + d being the same as b + a <= d + c
# as well as a + b <= c + d being the same as c + d >= a + b
def hashRule(rule):
	try:
		# Sort both left and right expressions by character,
		# so if two expressions add terms in different orders,
		# they will still match
		l = hashExpression(rule['leftSide']['expression'])
		r = hashExpression(rule['rightSide']['expression'])

		# Change greater_thans to less_thans
		o = rule['operator']
		if o.startswith('greater'):
			l,r = r,l # swap left and right
			o = o.replace('greater', 'less')

		# Look up the operator in our operators hash
		o = operators[o]

		# Return the result
		return l + o + r

	except KeyError:
		e = []
		if 'leftSide' not in rule:
			e.append('left side missing')
		elif 'expression' not in rule['leftSide']:
			e.append('left side expression missing')

		if 'rightSide' not in rule:
			e.append('right side missing')
		elif 'expression' not in rule['rightSide']:
			e.append('right side expression missing')

		if e:
			log('Due to ' + ' and '.join(e) + ', could not evaluate rule ' + rule['description'], 'warn')
		else:
			log('Could not evaluate either the left or right side of rule ' + rule['description'], 'warn')

		return False

def encodeQuote(quote):
	# The replace '%25' with '%' stops encoding from being effective with percentages
	# but it does stop the double encoding that was stopping some rules from working
	return '"' + urllib.parse.quote(quote[0][1:-1]).replace('%25', '%') + '"'

# Make and output a form. This is the core work.
def makeForm(form):
	global exportIndicators
	#pprint.pprint(form)
	formFileName = safeName(form['name'])
	form['formDataElements'] = set([])
	outputHTML = htmlBefore

	# Build major navigation (vtab navigation)
	vtabNames = []
	dynamicjs = ''
	degs = {}
	uidCache = {}
	uidCache2 = []
	warnUidCache = []
	skipCache = {}
	rules = []
	for i in range(len(form['vtabs'])):
		vtab = form['vtabs'][i]
		outputHTML += majorNavHTML_li % (str(i+1), vtab['name']) + "\n"
	outputHTML += majorNavHTML_after+"\n"

	# Loop through the VTABs in a FORM:
	for i in range(len(form['vtabs'])):
		vtab = form['vtabs'][i]
		htabs = findHtabs(vtab) # Find htabs referenced in this vtab

		# Build minor navigation (htab navigation)
		outputHTML += minorNavHTML_before % (str(i+1), str(i+1)) + "\n"
		for htab in htabs:
			outputHTML += minorNavHTML_li % (str(i+1), htab['type'], htab['label']) + "\n"
		outputHTML += minorNavHTML_after + "\n"

		# Loop through the HTABs in this VTAB:
		for j in range(len(htabs)):
			htab = htabs[j]
			outputHTML += entryAreaHTML_start % (str(i+1), htab['type'])

			# Loop through the Indicators in a VTAB (combined with HTAB):
			for k in range(len(vtab['indicators'])):
				indicator = vtab['indicators'][k]

				subIndicatorsHTML = ""
				subIndicatorsCount = 0

				if htabInIndicator(htab, indicator):
					for row in indicator['rows']:
						# Some edge cases will mix DSD/TA/Other _exclusives_ inside the same indicator,
						# make sure that we only echo out if it has a UID 1
						if row['de_' + htab['type'].lower() + '1'] :
							mutuallyExclusive = row['ctl_exclusive']

							prefix = 'de_' + htab['type'].lower()
							uids = []
							ccs = {}

							for k in ['1', '2', '3']:
								uid = row[prefix + k]
								val = open(comboDir + row['sub_disagg'] + '.html').read().find('{deuid' + k + '}')
								coc = open(comboDir + row['sub_disagg'] + '.html').read()[val+9:val+20]
								if val > 0:
									ccs[uid] = masterCategoryOptionComboList[coc]['categoryComboID']

								if uid and uid != 'null':
									if uid in uidCache2 and uid not in warnUidCache:
										log(form['name'] + ': The uid ' + uid + ' appears multiple times', 'warn')
										warnUidCache.append(uid)
									if masterDataElementList[uid]['categoryComboID'] not in ccs[uid]:
										log ("The data element " + masterDataElementList[uid]['name'] + 
											 " - " + uid + " DATIM cat combo " + masterDataElementList[uid]['categoryComboID'] + 
											 " does not match the " + row['sub_disagg'] + ".html catcombo(s) " + ccs[uid], 'warn')

									addDataElement(form, uid, form['dataElementGroups'], indicator['frequency'], ccs[uid])
									uids.append(uid)
									uidCache2.append(uid)

								if not('autocalc' in row['sub_disagg'] and 'wide' in row['sub_disagg']):
									# Will need to phase out when CC is removed from .csv
									if val > 0:
										if coc in masterCategoryOptionComboList:
											if masterCategoryOptionComboList[coc]['categoryComboID'] != ccs[uid]:
												log("Cat Combo: " + masterCategoryOptionComboList[coc]['categoryComboName'] + 
													" - " + masterCategoryOptionComboList[coc]['categoryComboID'] + 
													" found in " + row['sub_disagg'] + ".html does not match the form of cat combo " + 
													k + " " + ccs[uid] + " at " + indicator['name'], 'warn')
										else:
											log("Could not find coc in master list: " + row['sub_disagg'] + ". Val is " + str(val),'warn')

								globals()['uid' + k] = uid

							if row['ctl_uniqueid']:
								if (row['ctl_uniqueid'] + '_' + htab['uidsuffix']) in uidCache:
									log('Unique id ' + row['ctl_uniqueid'] + ' for htab ' + htab['uidsuffix'] + ' appears multiple times', 'severe')
								uidCache[row['ctl_uniqueid'] + '_' + htab['uidsuffix']] = uids
								skipCache[row['ctl_uniqueid']] = row['sub_priority']
								ssid = makeSsidHash(row['ctl_uniqueid'], htab['uidsuffix'])
							else:
								ssid = makeSsid(htab['uidsuffix'])
								uidCache[ssid] = uids

							subIndicatorsHTML += '<div class="si_' + ssid + '">\n'

							if 'autocalc' in row['sub_disagg'] and 'wide' in row['sub_disagg']:
								ssids = [ssid, makeSsid(htab['uidsuffix']), makeSsid(htab['uidsuffix']), makeSsid(htab['uidsuffix'])]
								if (';' in row['sub_text']):
									sub_text_1, sub_text_2, sub_text_3 = row['sub_text'].split(';')
								else:
									sub_text_1, sub_text_2, sub_text_3 = ['', '', '']

								subIndicatorsHTML += open(comboDir + row['sub_disagg'] + '.html').read().format(
									priority=row['sub_priority'], priority_css='PEPFAR_Form_Priority_'+safeName(row['sub_priority']),
									description=row['sub_heading'], sub_text_1=sub_text_1, sub_text_2=sub_text_2, sub_text_3=sub_text_3,
									ssid1=ssids[1], ssid2=ssids[2], ssid3=ssids[3], deuid1=uid1, deuid2=uid2, deuid3=uid3) + '\n</div>\n\n\n'
							else:
								ssids = [ssid]
								subIndicatorsHTML += open(comboDir + row['sub_disagg'] + '.html').read().format(
									priority=row['sub_priority'], priority_css='PEPFAR_Form_Priority_'+safeName(row['sub_priority']),
									description=row['sub_heading'], description2=row['sub_text'],
									ssid=ssid, deuid1=uid1, deuid2=uid2, deuid3=uid3) + '\n</div>\n\n\n'

							if row['ctl_exclusive']:
								left = 'R'
								action = 'exclusive_pair'
								exclusions = row['ctl_exclusive'].split(';')
								for e in exclusions:
									rules.append([left, action, e, htab['uidsuffix'], uids, ssids, row['sub_priority'], 'ctl_exclusive ' + e + ' from row ' + row['ctl_exclusive'], form['periodType']])

							if row['ctl_rules']:
								if '"' in row['ctl_rules']:
									row['ctl_rules'] = re.sub('"[^"]*"', encodeQuote, row['ctl_rules'])

								if ';' in row['ctl_rules']:
									rs = row['ctl_rules'].split(';')
								else:
									rs = [row['ctl_rules']]

								for r in rs:
									operator = False
									if ('>=' in r):
										operator = '>='
										action = 'greater_than_or_equal_to'
									elif ('<=' in r):
										operator = '<='
										action = 'less_than_or_equal_to'
									elif ('=' in r):
										operator = '='
										action = 'autocalculate'
									elif ('!!!' in r):
										operator = '!!!'
										action = 'exclusive_pair'
									else:
										log('Syntax error: Cannot compile rule ' + urllib.parse.unquote(r) + ' as it does not have an operator (=, <=, >=, !!!)', 'warn')

									if operator:
										# Save the rules to process later in the script
										a = r.split(operator)
										left = a[0]
										right = a[1].strip(' ')
										if (re.search('[^A-Za-z0-9\_\-\+\%\s\.\,\:\"\/\(\)]', left)):
											log('Syntax error: Rule ' + urllib.parse.unquote(r) + ' cannot be compiled as it either uses an illegal operator (=, <=, >= or !!! allowed) or the left expression has illegal characters (letters, numbers, spaces, parens, and certain symbols (".,_-:/+%) allowed)', 'warn')
										elif (re.search('[^A-Za-z0-9\_\-\+\%\s\.\,\:\"\/\(\)]', right)):
											log('Syntax error: Rule ' + urllib.parse.unquote(r) + ' cannot be compiled as it either uses an illegal operator (=, <=, >= or !!! allowed) or the right expression has illegal characters (letters, numbers, spaces, parens, and certain symbols (".,_-:/+%) allowed)', 'warn')
										else:
											rules.append([left, action, right, htab['uidsuffix'], uids, ssids, row['sub_priority'], 'ctl_rules row ' + urllib.parse.unquote(r), form['periodType']])
											if row['dhis_ind'] and action == 'autocalculate' and left == 'R' and htab['uidsuffix'] != 'xta':
												rules.append([left, 'indicator', right, htab['uidsuffix'], uids, ssids, row['sub_priority'], 'indicator for ctl_rules row ' + urllib.parse.unquote(r), row['dhis_ind']])

							for x in range(1, 3):
								j = 'degs' + str(x)
								if row[j]:
									d = row[j]
									for uid in uids:
										if d not in degs:
											degs[d] = []
										degs[d].append(uid)

							subIndicatorsCount += 1

				if(subIndicatorsCount > 0):
					if(len(htabs) == 1):
						outputHTML += indicatorHTML_before.format(name=indicator['name'], frequency=indicator['frequency'], title=htab['type'] + ': ' + indicator['name'])
					else:
						outputHTML += indicatorHTML_before.format(name=htab['label'] + ': ' + indicator['name'], frequency=indicator['frequency'], title=htab['type'] + ': ' + indicator['name'])
					outputHTML += subIndicatorsHTML
					outputHTML += indicatorHTML_after.format(title=htab['type'] + ' ' + indicator['name'])

			outputHTML += entryAreaHTML_end

		outputHTML += minorNavHTML_end

	#skipping targets for now
	#form['name'].count('Targets') == 0
	if not(nofavorites) and form['name'].count('Narratives') == 0 and (not(specificForms) or form['uid'] in formsToOutput):

		favoriteType = ''
		if form['name'].count('Targets') > 0:
			favoriteType = 'Targets'
		elif form['name'].count('Results') > 0:
			favoriteType = 'Results'

		for i in range(len(form['vtabs'])):
			vtab = form['vtabs'][i]

			for k in range(len(vtab['indicators'])):
				indicator = vtab['indicators'][k]

				for row in indicator['rows']:

					#check to see if the row is anything by AutoCalc
					if row['sub_priority'] == 'Required' or row['sub_priority'] == 'Conditional' or row['sub_priority'] == 'Optional':
						#Check to see if we should make a favorite for this indicator
						#Check to see if this is actually an autocalc row that is mislabled
						#print(indicator['name']+" - "+indicator['frequency'])
						
						favoriteFirstDeShortName=getDataElement(list(findDataElementsFromRow(row))[0])['shortName']
						#favoriteName="PEPFAR "+ISOQuarterToFYOctQuarter(favoritesISOQuarter)+" "+favoriteType+" "+indicator['name']+" "+getNumeratorDenominator(favoriteFirstDeShortName)+" "+getDisagg(favoriteFirstDeShortName)+" Completeness Review Precursor"

						curISOQuarter="FY"+curYear()+"Q"+curQuarter()

						favoriteName="PEPFAR "+favoritesISOQuarter+" "+favoriteType+" "+indicator['name']+" "+getNumeratorDenominator(favoriteFirstDeShortName)+" "+getDisagg(favoriteFirstDeShortName)+" Completeness Review Precursor"

						favoriteDisplayName=favoriteName
						favoriteDescription="This is an auto generated favorite made by MERTIDE, this is not intended to be deployed in its current form, but rather a precursor for PPM staff to create the completeness review pivot."

						favoriteId=makeUidHash(favoriteName)

						#log(favoriteName)
						#no else statement, previous if that checks for a valid frequency would kick out sooner

						favoriteISOPeriod=favoritesISOQuarter
						favoritePeriodsPreCursor='{"periods": [{"id": ""}]}'
						favoritePeriods=json.loads(favoritePeriodsPreCursor)


						if favoriteType == 'Targets':
							#favoriteISOPeriod=ISOQuarterToISOFYOctTARGET(favoritesISOQuarter)
							#HARDCODE IS BAD
							favoritePeriods['periods'][0]['id']='2019Oct'
						elif indicator['frequency'] == 'Annually':
							favoriteISOPeriod=ISOQuarterToISOFYOct(favoritesISOQuarter)
							favoritePeriods['periods'][0]['id']=favoriteISOPeriod
						elif indicator['frequency'] == 'Semiannually':
							favoriteISOPeriod=ISOQuarterToISOSAApr(favoritesISOQuarter)
							favoritePeriods['periods'][0]['id']=favoriteISOPeriod
						elif indicator['frequency'] == 'Quarterly':
							favoriteISOPeriod=favoritesISOQuarter
							favoritePeriods['periods'][0]['id']=favoriteISOPeriod

						favoriteDataDimensionsItems = {"dataDimensionItems": []}

						for de in findDataElementsFromRow(row):
							favoriteDataDimensionItemTypeFull = {"dataDimensionItemType": "DATA_ELEMENT","dataElement": {"id": ""}}
							favoriteDataDimensionItemTypeFull["dataElement"]["id"] = str(de)
							favoriteDataDimensionsItems["dataDimensionItems"].append(favoriteDataDimensionItemTypeFull)

						favoriteNew=favoriteStub.copy()

						favoriteNew['id'] = favoriteId
						favoriteNew['name'] = favoriteName
						favoriteNew['displayName'] = favoriteDisplayName
						favoriteNew['description'] = favoriteDescription
						favoriteNew['dataDimensionItems'] = favoriteDataDimensionsItems['dataDimensionItems']
						favoriteNew['periods'] = favoritePeriods['periods']

						if favoriteId not in favoritesCreated:
							favoritesCreated.append(favoriteId)
							if indicator['frequency'] == 'Annually':
								favoriteAnnuallyJSON['reportTables'].append(favoriteNew)
							if indicator['frequency'] == 'Semiannually':
								favoriteSemiannuallyJSON['reportTables'].append(favoriteNew)
							if indicator['frequency'] == 'Quarterly':
								favoriteQuarterlyJSON['reportTables'].append(favoriteNew)

	if not(noconnection):
		for rule in rules:
			# Get validation rule period
			rulePeriod = rule[8]

			[left, leftjs, leftnames, ignore] = processMertideExpression(rule[0], rule, False, 'left', uidCache, skipCache, dataElementCache)
			[right, rightjs, rightnames, rightMissingValue] = processMertideExpression(rule[2], rule, False, 'right', uidCache, skipCache, dataElementCache)

			if right or rightjs:
				if rule[1] == 'autocalculate':
					dynamicjs += "      stella.autocalc(" + str(rightjs) + ", " + str(leftjs) + ");\n"

				elif rule[1] == 'indicator':
					if rule[3] == 'dsd':
						temprule = rule.copy()
						temprule[3] = 'xta'
						[tempright, ignore1, temprightnames, ignore2] = processMertideExpression(rule[2], temprule, False, 'right', uidCache, skipCache, dataElementCache)
						right.extend(tempright)
						rightnames.extend(temprightnames)
					n = []
					for x in right:
						if x['optionCombo']:
							n.append('#{' + x['id'] + '.' + x['optionCombo'] + '}')
						else:
							n.append('#{' + x['id'] + '}')

					[uid, name] = rule[8].split(';')
					exportIndicators.append([name, uid, n, ' + '.join(rightnames)])

				else:
					if left != [{}] and right != [{}]:
						j = {}
						j['importance'] = 'MEDIUM'
						j['ruleType'] = 'VALIDATION'
						j['periodType'] = rulePeriod
						j['operator'] = rule[1]
						j['leftSide'] = {}
						j['rightSide'] = {}
						j['leftSide']['dataElements'] = set([])
						j['rightSide']['dataElements'] = set([])

						for l in left:
							j = addExpression(j, 'leftSide', l)

						if j['operator'] == 'less_than_or_equal_to' or j['operator'] == 'greater_than_or_equal_to':
							if j['operator'] == 'less_than_or_equal_to':
								j['name'] = ' <= '
							else:
								j['name'] = ' >= '

							if rule[6] in skip:
								j['leftSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'
							else:
								j['leftSide']['missingValueStrategy'] = 'NEVER_SKIP'
								if rule[6] not in neverskip:
									log('Syntax error: ' + rule[6] + ' not associated with missing value strategy for rule ' + rule[7], 'warn')
							j['rightSide']['missingValueStrategy'] = 'NEVER_SKIP'

							if rightMissingValue:
								j['rightSide']['missingValueStrategy'] = rightMissingValue
							else:
								log('Error: Unable to identify missing value strategy for right side of rule ' + rule[7] + '; defaulting to NEVER_SKIP', 'warn')
								j['rightSide']['missingValueStrategy'] = 'NEVER_SKIP'

						elif j['operator'] == 'exclusive_pair':
							j['name'] = ' :OR: '
							j['leftSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'
							j['rightSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'

						for r in right:
							j = addExpression(j, 'rightSide', r)

						j['name'] = ' + '.join(leftnames) + j['name'] + ' + '.join(rightnames)

						j['description'] = j['name']
						j['instruction'] = j['name']
						j['leftSide']['dataElements'] = reformatDataElements(j['leftSide']['dataElements'])
						j['rightSide']['dataElements'] = reformatDataElements(j['rightSide']['dataElements'])
						h = hashRule(j)
						if h:
							if h in rulesCache:
								j['id'] = rulesCache[h]
							else:
								if j['operator'] == 'exclusive_pair':
									k = copy.deepcopy(j)
									k['leftSide']['expression'] = j['rightSide']['expression']
									k['rightSide']['expression'] = j['leftSide']['expression']
									h = hashRule(k)
									if h in rulesCache:
										j['id'] = rulesCache[h]
									else:
										j['id'] = makeUid()
								else:
									j['id'] = makeUid()

							# Shorten the name if it's over 230 chars
							j['name'] = j['name'][0:230]

							# Shorten the descriptions if they are over 255 chars
							j['leftSide']['description'] = j['leftSide']['description'][0:255]
							j['rightSide']['description'] = j['rightSide']['description'][0:255]

							rulesCache[h] = 'used' + form['uid']

							# Only add each rule once to DHIS2
							if not(j['id'].startswith('used')):
								if h in dhisRulesCache:
									modified = False
									for key in dhisRulesCache[h]:
										if key == 'leftSide' or key == 'rightSide':
											for key2 in dhisRulesCache[h][key]:
												if (dhisRulesCache[h][key][key2] != j[key][key2] and
														(key2 != 'expression' or hashExpression(dhisRulesCache[h][key][key2]) != hashExpression(j[key][key2]))):
													modified = True
													break
										else:
											if dhisRulesCache[h][key] != j[key]:
												modified = True
										if modified:
											break
									if modified:
										modifiedRules.append(j)
									else:
										oldRules.append(j)
								else:
									newRules.append(j)

							if j['operator'] == 'exclusive_pair':
								dynamicjs += "      meany.autoexclude(" + str(leftjs) + ", " + str(rightjs) + ");\n"

					else:
						if left == [{}]:
							log('Syntax error: Left expression appears empty after processing in ' + rule[7], 'warn')
						if right == [{}]:
							log('Syntax error: Right expression appears empty after processing in ' + rule[7], 'warn')

		for i in degs:
			try:
				req = requests.get(api + 'dataElementGroups.json', cookies=jsessionid,
					params = {'paging': False, 'fields': 'name,id', 'filter': 'name:eq:' + i})
				groups = form['dataElementGroups'].copy()
				groups.append(req.json()['dataElementGroups'][0]['id'] + '_' + i)
				for uid in degs[i]:
					addDataElement(form, uid, groups, indicator['frequency'])
			except Exception as e:
				pass
				#log('Syntax error: Problem with data element group set ' + i, 'warn')

	else:
		log('Not connected to DHIS2, so skipping all rules and data element group sets', 'warn')


	# Set special JS extras
	outputHTML = outputHTML.replace("//#dataValuesLoaded#", '\n' + dynamicjs) #cannot use format here because all the curly braces {} in the javascript and css
	#outputHTML = outputHTML.replace("//#formReady#","")
	#outputHTML = outputHTML.replace("//#dataValueSaved#","")

	outputHTML += open(setuptabsHTML).read()
	outputHTML += majorNavHTML_end + '<!-- End Custom DHIS2 Form -->\n\n'

	# Create the standalone form preview file
	if severe:
		log('Skipping form due to severe error: ' + form['name'] + ' - ' + form['uid'])
		return
	elif specificForms and form['uid'] not in formsToOutput:
		log('Skipping form: ' + form['name'] + ' - ' + form['uid'])
	else:
		log('Creating form: ' + form['name'] + ' - ' + form['periodType'] + ' - ' + form['uid'])
		formFile = open(outDir+formFileName+'.html', 'w')



		#Creats an offline version of the form for offline specific requests.

		offlineOutputHTML = open(standaloneHTMLa).read().replace('MER Results: Facility Based', form['name'])

		insertArray = ""
		insertArray2 = ""
		for key, value in formDataElementList.items():
			if value['form'] == form['name']:
				insertArray += "dataElementList['"+key+"'] = '"+value['name']+"';\n"
			for cocKey, cocValue in masterCategoryOptionComboList.items():
				if cocValue['categoryComboID'] == value['categoryCombo']:
					insertArray2 += "catOptionCombo['"+cocKey+"'] = '"+cocValue['name']+"';\n"


		offlineOutputHTML += outputHTML

		insertArrayCombined = insertArray+insertArray2
		offlineOutputHTML = offlineOutputHTML.replace('//dataElementListHere', insertArrayCombined)

		if form['categoryCombo'] == 'bjDvmb4bfuf':
			offlineOutputHTML = re.sub(r'<!--attributeComboStart(.*)attributeComboEnd-->','',offlineOutputHTML, flags=re.S)

		formFile.write(offlineOutputHTML)


		formFile.write(open(standaloneHTMLb).read())
		formFile.close()

	# Format the dataset for the ouput XML files
	datasetPrefix = open('codechunks/dataset_prefix.xml').read() \
		.format(code=codeName(form['shortshortname']), name=form['name'], shortname=form['shortshortname'], uid=form['uid'], periodType=form['periodType'],
				categoryCombo=form['categoryCombo'], version=form['version'], approveData=form['approveData'], userGroupAccesses=form['userGroupAccesses'] )

	#   2.21 to 2.24
	#   dataElements = '			<dataElements>\n'
	#   for id in form['formDataElements']:
	#	   dataElements += '			   <dataElement id="' + id + '" />\n'
	#   dataElements += '		   </dataElements>\n'

	#2.25 updates
	dataElements = '			<dataSetElements>\n'
	for id in form['formDataElements']:
		dataElements += '			   <dataSetElement>\n'
	#   dataElements += '				   <externalAccess>false</externalAccess>\n'
		dataElements += '				   <dataElement id="' + id + '" />\n'
		dataElements += '				   <dataSet id="' + form['uid'] + '" />\n'
		if id in catComboCache:
			dataElements += '				   <categoryCombo id="' + catComboCache[id] + '" />\n'
		dataElements += '			   </dataSetElement>\n'
	dataElements += '		   </dataSetElements>\n'

	# .xml export file
	if not(specificForms) or (form['uid'] in formsToOutput):
		exportDataEntryForms.append(
			'	   <dataEntryForm id="' + form['formUid'] + '">\n' +
			'		   <name>' +form['name'] + '</name>\n' +
			'		   <externalAccess>false</externalAccess>\n' +
			'		   <style>NORMAL</style>\n' +
			'		   <htmlCode>\n' + escape(outputHTML) + '\n' +
			'		   </htmlCode>\n' +
			'		   <format>2</format>\n' +
			'	   </dataEntryForm>\n')

		# Offline forms

		exportStaticHTML.append(outputHTML)

		thisDatasetPrefix = datasetPrefix

		if form['workflow']:
			thisDatasetPrefix += '		  <workflow id="' + form['workflow'] + '" />\n'

		exportDatasets.append(thisDatasetPrefix +
			'		   <dataEntryForm id="' + form['formUid'] + '" />\n' +
			dataElements +
			'	   </dataSet>\n')

# Remove white space from all keys in a row
def stripWhiteSpace(row):
	for key in row:
		if isinstance(row[key], str):
			row[key] = row[key].strip()

# Process a control .CSV file.
# The lines of the .CSV file are assembled into a structure of dictionaries
# and lists for each form as follows:
#
# form: name, uid, vtabs
# vtab: name, indicators
# indicator: name, frequency, rows (SUB / AUTO / DESC)
def doControlFile(controlFileName):
	with open(controlFileName, encoding = "ISO-8859-1") as controlFile:
		reader = csv.DictReader(controlFile, dialect='excel')
		form = {} # FORM: name, uid, vtabs
		for row in reader:
			stripWhiteSpace(row)
			type = row['Type']
			if type == 'FORM':
				if (form): # Not the first FORM
					makeForm(form)
					form = {}
				form['name'] = row['form_name']
				form['shortname'] = row['form_shortname']
				form['shortshortname'] = form['shortname'][:50]
				form['uid'] = row['form_uid'] or makeUid()
				form['formUid'] = row['form_dsf_uid'] or makeUid()
				form['periodType'] = row['form_freq'] or 'Quarterly' # Probably need to remove the defaults
				form['categoryCombo'] = row['form_atr'] or 'wUpfppgjEza' # Probably need to remove the defaults Default to 'Funding Mechanism'
				form['version'] = row['form_dsf_v'] or '1'
				form['approveData'] = row['form_awf_tf'].lower() or 'true'
				form['workflow'] = row['form_awf_uid']
				form['vtabs'] = []
				form['dataElementGroups'] = []
				form['userGroupAccesses'] = ''
				for key in row:
					if key is not None:
						if key.startswith('deg') and row[key]:
							form['dataElementGroups'].append(row[key])
						elif key.startswith('group'):
							value = row[key]
							if value:
								if (';' in value):
									parts = value.split(';')
									group = parts[0]
									permissions = parts[1]
								else:
									group = value
									permissions = 'r-r-----'

								if form['userGroupAccesses']:
									form['userGroupAccesses'] += '\n\t\t\t\t'

								form['userGroupAccesses'] += '<userGroupAccess>\n\t\t\t\t\t<id>{group}</id>\n\t\t\t\t\t<access>{permissions}</access>\n\t\t\t\t\t<userGroupUid>{group}</userGroupUid>\n\t\t\t\t</userGroupAccess>' \
									.format(group=group, permissions=permissions)

			elif type == 'VTAB':
				if not form['name']: # Haven't seen a FORM yet
					log('Error in ' + controlFileName + ': expected FORM before VTAB.', 'warn')
					return
				form['vtabs'].append({})
				form['vtabs'][-1]['name'] = row['vtab_name']
				form['vtabs'][-1]['indicators'] = []
			elif type == 'IND':
				if not form['vtabs']: # Haven't seen a VTAB yet
					log('Error in ' + controlFileName + ': expected VTAB before IND.', 'warn')
					return
				form['vtabs'][-1]['indicators'].append({})
				form['vtabs'][-1]['indicators'][-1]['name'] = row['ind_name']
				form['vtabs'][-1]['indicators'][-1]['frequency'] = row['ind_freq']
				form['vtabs'][-1]['indicators'][-1]['rows'] = []
			elif type in ['SUB']:
				if not (form['vtabs'] and form['vtabs'][-1]['indicators'] ): # Haven't seen a IND yet
					log('Error in ' + controlFileName + ': expected IND before' + type + '.', 'warn')
					return
				form['vtabs'][-1]['indicators'][-1]['rows'].append(row)
			elif type:
				log('Error in ' + controlFileName + ': unexpected type' + type + '.', 'warn')
		makeForm(form)

# Write dataElementGroups to an export file
def writeDataElementGroups(out):
	out.write('	<dataElementGroups>\n')
	for group, uids in dataElementGroups.items():
		out.write('		<dataElementGroup id="' + group[:11] + '" name="' + group[12:] + '" shortName="' + group[12:62] + '">\n')
		out.write('			<externalAccess>false</externalAccess>\n')
		out.write('			<publicAccess>r-------</publicAccess>\n')
		out.write('			<dataElements>\n')
		for uid in uids:
			out.write('				<dataElement id="' + uid + '" />\n')
		out.write('			</dataElements>\n')
		out.write('		</dataElementGroup>\n')
	out.write('	</dataElementGroups>\n')

# Format indicator into XML
def formatIndicator(key, value):
	code = key.upper().replace(' ', '_')
	uid = makeUidHash('datimIndicator' + key)
	r =  '	    <indicator code="' + code + '" id="' + uid + '" name="' + key + '" shortName="' + key + '">\n'
	r += '		    <publicAccess>r-------</publicAccess>\n'
	r += '		    <denominatorDescription>1</denominatorDescription>\n'
	r += '		    <numeratorDescription>' + key + '</numeratorDescription>\n'
	r += '		    <numerator>\n'
	firstValue = True
	for k in value:
		if (firstValue):
			r += '			    '
			firstValue = False
		else:
			r += '+'
		r += '#{' + k + '}'
	r += '\n'
	r += '		    </numerator>\n'
	r += '		    <denominator>1</denominator>\n'
	r += '		    <annualized>false</annualized>\n'
	r += '		    <indicatorType id="QEjvmP5XVSn"/>\n'
	r += '	    </indicator>\n'
	return(r)

# The main function
def main(argv):
	curISOQuarter=curYear()+"Q"+curQuarter()
	# Order of sysargs:
	sysargs = ['','','',False,'',False,curISOQuarter,False]
	usage = 'usage: mertide.py -i [merform.csv|merdirectory] -d /path/to/disagg/files/ [options]\n	options:\n	  -n, --noconnection\n			Parse CSV even if there is no connection to DHIS2\n\n	  -f formuid1234,formid2468, --forms=formuid1234,formid2468\n			Only include forms with uid formuid1234 and formuid2468\n\n	  --nofavorites\n			Do not output favorites\n\n	  --html\n			Outputs static HTML versions of the forms\n			for uploading directly to DHIS2\n\n	  --favoriteisoquarter=2019Q1\n			Year and Quarter in which to create favorites override\n			(Defaults to current quarter)\n\n	 -h, --help\n		Prints this message\n'

	try:
		opts, args = getopt.getopt(argv,'i:d:f:h:n',['input=','disaggs=','noconnection','forms=','nofavorites','favoriteisoquarter=','html','help'])
	except getopt.GetoptError:
		log(usage)
		sys.exit(2)

	for opt, arg in opts:
		if opt in ('-h', '--help'):
			log(usage)
			sys.exit(2)
		elif opt in ('-i', '--input'):
			if sysargs[0] == '' and sysargs[1] == '':
				if os.path.isdir(arg):
					sysargs[0] = arg
				elif os.path.isfile(arg):
					sysargs[1] = arg
				else:
					log('Input argument (' + arg + ') is not a file or directory', 'severe')
					log(usage)
					sys.exit(2)
			else:
				log(usage)
				sys.exit(2)
		elif opt in ('-d', '--disaggs'):
			if sysargs[2] == '':
				if not os.path.isdir(arg):
					log('Disagg folder (' + arg + ') not found', 'severe')
					log(usage)
					sys.exit(2)
				sysargs[2] = arg
			else:
				log(usage)
				sys.exit(2)
		elif opt in ('-n', '--noconnection'):
			sysargs[3] = True
		elif opt in ('-f', '--forms'):
			if sysargs[4] == '':
				formuids = arg.split(',')
				for formuid in formuids:
					if not isDhisUid(formuid):
						log('At least one form UID is not valid:' + formuid, 'severe')
						log(usage)
						sys.exit(2)
				sysargs[4] = formuids
		elif opt in ('--nofavorites'):
			sysargs[5] = True
		elif opt in ('--html'):
			sysargs[7] = True
		elif opt in ('--favoriteisoquarter'):
			print(arg)
			#Example: 2018Q4
			#Check length, check for the 20, check for the Q
			if len(arg) == 6 and arg[:2] == '20' and arg[-2] == 'Q':
				#Check Quarter
				if arg[-1] == '1' or arg[-1] == '2' or arg[-1] == '3' or arg[-1] == '4':
					#Check year
					try:
						if int(arg[2:4]) >= 18:
							sysargs[6] = arg
						else:
							log(usage)
							sys.exit(5)
					except:
						log(usage)
						sys.exit(4)
				else:
					log(usage)
					sys.exit(3)
			else:
				log(usage)
				sys.exit(2)


	if sysargs[2] == '' or (sysargs[0] == '' and sysargs[1] == ''):
		log(usage)
		sys.exit(2)

	return sysargs

masterDataElementList = {}
formDataElementList = {}
dataElementCache = {}
masterCategoryOptionComboList = {}
catComboCache = {}
optionCache = {}
cocCache = {}
cocCache2 = {}
rulesCache = {}
dhisRulesCache = {}
newRules = []
modifiedRules = []
oldRules = []
inputArgs = []
favoritesCreated = []
favoriteAnnuallyJSON=json.loads('{"reportTables": []}')
favoriteSemiannuallyJSON=json.loads('{"reportTables": []}')
favoriteQuarterlyJSON=json.loads('{"reportTables": []}')
dataElementCadence= []

noconnection = False
severe = False

neverskip = ['Required', 'Auto-Calculate']
skip = ['Optional', 'Conditional', 'DREAMS Only']

operators = {'equal_to': '==',
			'not_equal_to': '!=',
			'less_than': '<',
			'less_than_or_equal_to': '<=',
			'compulsory_pair': '[Compulsory pair]',
			'exclusive_pair': '[Exclusive pair]'}

outDir = 'output/'

if not(os.path.exists(outDir)):
	os.makedirs(outDir)

for f in os.listdir(outDir):
	if (f != '.gitignore' and not(os.path.isdir(f))):
		os.remove(os.path.join(outDir, f))

logFile = open(outDir+'mertide.log', 'w')

# Get those args!
if __name__ == '__main__':
   inputArgs = main(sys.argv[1:])

controlDir = inputArgs[0]
controlFile = inputArgs[1]
comboDir = inputArgs[2]
noconnection = inputArgs[3]
nofavorites = inputArgs[5]
favoritesISOQuarter = inputArgs[6]
statichtml = inputArgs[7]

if controlDir:
	log('Control Folder: ' + controlDir)
	if not(controlDir.endswith('/')):
		controlDir += '/'
else:
	log('Control File: ' + controlFile)

log('Disagg Folder: ' + comboDir)
if not(comboDir.endswith('/')):
	comboDir += '/'

specificForms = False
formsToOutput = []
if inputArgs[4]:
	log('Output forms: ' + ', '.join(inputArgs[4]))
	formsToOutput = inputArgs[4]
	specificForms = True
else:
	log('Outputting all forms')

try:
	config = json.load(open('/opt/dhis2/dish.json', 'r'))
	api = config['dhis']['baseurl'] + '/api/'
	credentials = (config['dhis']['username'], config['dhis']['password'])
except FileNotFoundError:
	# If you wish to hardcode the api endpoint and the username and password, you can do that here
	api = 'http://localhost:8080/api/'
	credentials = ('user', 'password')

try:
	req = requests.Session()
	req.get(api, auth=credentials)
	jsessionid = req.cookies.get_dict()
	req = requests.get(api + 'resources.json', cookies=jsessionid)
	if req.json()['resources'][0]:
		log('Connected to DHIS2 using ' + api)
	else:
		raise ConnectionError('Not connected to DHIS2')
except:
	log('Not connected to DHIS2')
	if not(noconnection):
		sys.exit(2)

# get the favorite stub
if not nofavorites:
	try:
		favoriteStub = json.load(open('./codechunks/favorite_stub.json', 'r'))
		log('Outputting favorites for '+favoritesISOQuarter)
	except FileNotFoundError:
		log('favorite stub not found exiting')
		sys.exit(2)
else:
	log('Skipping favorite generation')


# CSS
cssStart = '<style>'
css = './css/main.css'
cssEnd = '</style>'

# Javascript
jsStart = '<script>'
js = []
jsEnd = '</script>'
jsDir = './js'
for (dirpath, dirnames, filenames) in os.walk(jsDir):
	js.extend(filenames)
	break

htmlBefore = "<!-- Start Custom DHIS2 Form -->\n"

# Standalone wrappers
standaloneHTMLa = './codechunks/standaloneform_before.html'
standaloneHTMLb = './codechunks/standaloneform_end.html'
setuptabsHTML = './codechunks/setuptabs.html'

ulClose = '</ul>\n'
divClose = '</div>\n'

# Major Navigation List with HTML
majorNavHTML_before = \
	'<div class="PEPFAR_reporting_legend">\n' + \
	'\t<span id="PEPFAR_loading"><i class="fa fa-cog fa-spin PEPFAR_spinner">&nbsp;</i><span>&nbsp;Loading</span>&nbsp;</span>\n' + \
	'\t<i class="fa fa-square PEPFAR_quarterly_square">&nbsp;</i><span>Quarterly Reporting</span>\n' + \
	'\t<i class="fa fa-square PEPFAR_semiannually_square">&nbsp;</i><span>Semiannually Reporting</span>\n' + \
	'\t<i class="fa fa-square PEPFAR_annually_square">&nbsp;</i><span>Annually Reporting</span>\n</div>\n\n' + \
	'<div id="PEPFAR_Tabs_vertical" class="ui-tabs-vertical ui-helper-clearfix">\n' + \
	'<ul class="ui-helper-hidden">'
majorNavHTML_li = '\t<li class="ui-corner-left"><a href="#PEPFAR_Tabs_vertical_%s">%s</a></li>'
majorNavHTML_after = ulClose
majorNavHTML_end = divClose

allHtabs = [{'type': 'DSD', 'label': 'DSD', 'uidsuffix': 'dsd'}, {'type': 'TA', 'label': 'TA-SDI', 'uidsuffix': 'xta'}, {'type': 'CS', 'label': 'CS', 'uidsuffix': 'xcs'}, {'type': 'NA', 'label': 'Other', 'uidsuffix': 'xna'}]

# Minor Navigation List with HTML
minorNavHTML_before = '<div id="PEPFAR_Tabs_vertical_%s">\n<div id="PEPFAR_Tabs_h_%s">\n<ul class="ui-helper-hidden">'
minorNavHTML_li='\t<li><a href="#PEPFAR_Form_%s_%s">%s</a></li>'
minorNavHTML_after=ulClose
minorNavHTML_end=divClose+divClose

# Entry Area
entryAreaHTML_start = '<div id="PEPFAR_Form_%s_%s">\n<p class="PEPFAR_Form_ShowHide">&nbsp;</p>\n\n'
entryAreaHTML_end = divClose

# Indicator
indicatorHTML_before = \
	'<!-- {title} -->\n' + \
	'<div class="PEPFAR_Form">\n' + \
	'<div class="PEPFAR_Form_Container PEPFAR_Form_Title PEPFAR_Form_Title_{frequency}">{name}</div>\n' + \
	'<div class="PEPFAR_Form_Collapse">\n'
indicatorHTML_after = \
	'</div>\n' + \
	'<!-- END {title} --></div>\n\n' + \
	'<p>&nbsp;</p>\n\n'

# Build HTML prefix to use before the form-specific contents

# CSS
htmlBefore+="\n"+cssStart+"\n"
with open(css, "r") as readFile:
	htmlBefore+=readFile.read()
htmlBefore+="\n"+cssEnd+"\n"

# All JS Files
htmlBefore+="\n"+jsStart+"\n"
for jsFile in js:
	with open(jsDir+'/'+jsFile, "r") as readFile:
		if(filenameChecker(jsFile)):
			htmlBefore+=readFile.read()
			htmlBefore+="\n"
htmlBefore+="\n"+jsEnd+"\n"

# Major Nav
htmlBefore+=majorNavHTML_before+"\n"

exportDataEntryForms = [] #Array of XML <dataEntryForm> definitions to export (v2.22 and following)
exportStaticHTML = [] #Array of static HTML forms
exportDatasets = [] #Array of XML <dataset> definitions to export (v2.22 and following)
exportIndicators = []
dataElementGroups = defaultdict(set) # Data element groups and their members for export

# Top-level logic

random.seed()

# for (dirpath, dirnames, filenames) in os.walk('.'):
#	 for filename in filenames:
#		 if re.match('^mertide_.*csv$',filename):
#			 doControlFile(dirpath + '/' + filename)

if not(noconnection):
	# Cache currently existing rules
	req = requests.get(api + 'validationRules.json', cookies=jsessionid,
			params = {'paging': False, 'fields': 'name,id,leftSide[expression,description,missingValueStrategy],operator,rightSide[expression,description,missingValueStrategy],description,ruleType,periodType,instruction,importance'})
	for r in req.json()['validationRules']:
		rulesCache[hashRule(r)] = r['id']
		dhisRulesCache[hashRule(r)] = r

if controlDir:
	controlFile = outDir + 'temp.csv'
	o = open(controlFile, 'w')
	for i in os.listdir(controlDir):
		if i.endswith('.csv'):
			ih = open(controlDir + i, 'r')
			o.write(ih.read())
	o.close()

# Pull Data Element and Cat Option Combo data from connected dhis2 server
getAllDataElements()
getAllCategoryOptionCombos()
doControlFile(controlFile)

# Write indicator file

indicator = open('codechunks/indicator.json').read()
j = []
for i in exportIndicators:
	n = '+'.join(i[2])
	shortName = i[0][:50]
	j.append(indicator.format(name=i[0], uid=i[1], numerator=n, numeratorDescription=i[3], shortName=shortName))
export = open(outDir+'indicators.json', 'w')
export.write('{\n  "indicators": [\n' + '\n,\n'.join(j) + '  ]\n}')
export.close()


# Write XML import file for api/xx/metadata

if severe:
	log('Skipping datasets.xml due to severe error')
else:
	export = open(outDir + 'datasets.xml', 'w')
	export.write(open('codechunks/datasets_before.xml').read())

	export.write('	<dataEntryForms>\n')
	for form in exportDataEntryForms:
		export.write(form)
	export.write('	</dataEntryForms>\n')

	export.write('	<dataSets>\n')
	for dataSet in exportDatasets:
		export.write(dataSet)
	export.write('	</dataSets>\n')

	writeDataElementGroups(export)

	export.write('</metadata>\n')
	export.close()
	z = zipfile.ZipFile(outDir + 'datasets.xml.zip', 'w', zipfile.ZIP_DEFLATED)
	z.write(outDir + 'datasets.xml')
	z.close()

if not(nofavorites):
	export = open(outDir + 'precursorFavoritesAnnually.json', 'w')
	export.write(json.dumps(favoriteAnnuallyJSON, sort_keys=True, indent=2, separators=(',', ': ')))
	export.close()

	export = open(outDir + 'precursorFavoritesSemiannually.json', 'w')
	export.write(json.dumps(favoriteSemiannuallyJSON, sort_keys=True, indent=2, separators=(',', ': ')))
	export.close()

	export = open(outDir + 'precursorFavoritesQuarterly.json', 'w')
	export.write(json.dumps(favoriteQuarterlyJSON, sort_keys=True, indent=2, separators=(',', ': ')))
	export.close()

if not(noconnection):
	deleteRules = ''
	addRulesToGroup = ''
	shellScriptBegin = open('codechunks/shellscript.sh').read()

	for r in newRules:
		deleteRules += "dhis_api --request DELETE --api-request='validationRules/" + r['id'] + "'\n"
		addRulesToGroup += "dhis_api --request POST --api-request='validationRuleGroups/wnFo1vX2IW3/validationRules/" + r['id'] + "'\n"

	for r in modifiedRules:
		deleteRules += "# dhis_api --request DELETE --api-request='validationRules/" + r['id'] + "'\n"
		addRulesToGroup += "# dhis_api --request POST --api-request='validationRuleGroups/wnFo1vX2IW3/validationRules/" + r['id'] + "'\n"

	for r in oldRules:
		deleteRules += "# dhis_api --request DELETE --api-request='validationRules/" + r['id'] + "'\n"
		addRulesToGroup += "# dhis_api --request POST --api-request='validationRuleGroups/wnFo1vX2IW3/validationRules/" + r['id'] + "'\n"

	if severe:
		log('Skipping validation rule JSONs due to severe error')
	else:
		export = open(outDir + 'newValidationRules.json', 'w')
		export.write(json.dumps({'validationRules': newRules}, sort_keys=True, indent=2, separators=(',', ': ')))
		export.close()

		export = open(outDir + 'modifiedValidationRules.json', 'w')
		export.write(json.dumps({'validationRules': modifiedRules}, sort_keys=True, indent=2, separators=(',', ': ')))
		export.close()

		export = open(outDir + 'oldValidationRules.json', 'w')
		export.write(json.dumps({'validationRules': oldRules}, sort_keys=True, indent=2, separators=(',', ': ')))
		export.close()

		export = open(outDir + 'createValidationRules.sh', 'w')
		export.write(shellScriptBegin)
		export.write("dhis_api --content-json --request POST --data-binary '@newValidationRules.json' --api-request='metadata/?preheatCache=false&dryRun=false'\n")
		export.write("dhis_api --content-json --request POST --data-binary '@modifiedValidationRules.json' --api-request='metadata/?preheatCache=false&dryRun=false'\n")
		export.write("# dhis_api --content-json --request POST --data-binary '@oldValidationRules.json' --api-request='metadata/?preheatCache=false&dryRun=false'\n\n")
		export.write(addRulesToGroup)
		os.fchmod(export.fileno(), 0o755) # Make the script executable
		export.close()

		export = open(outDir + 'deleteValidationRules.sh', 'w')
		export.write(shellScriptBegin)
		export.write(deleteRules)
		os.fchmod(export.fileno(), 0o755) # Make the script executable
		export.close()

		export = open(outDir + 'dataElements.tsv', 'w')
		for key, value in formDataElementList.items():
			export.write(key+"\t"+value['type']+"\t"+value['form']+"\t"+value['categoryCombo']+"\t"+value['name']+"\t"+value['frequency']+"\n")

		export.close()


getDataElementCadence()
export = open(outDir + 'dataElementCadence.json', 'w')
export.write(json.dumps({'period' : favoritesISOQuarter, 'dataElements': dataElementCadence}, sort_keys=True, indent=2, separators=(',', ': '))) 
export.close()



log('Finished processing control file, exiting normally')

logFile.close()
