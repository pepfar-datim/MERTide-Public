#!/usr/bin/env python3

# USAGE: ./mertide.py -i merform.csv -d /path/to/disagg/files/ [-n] [-f formuid1234,formid2468] [-h]
#		 ./mertide.py -i merdirectory -d /path/to/disagg/files/ [-n] [-f formuid1234,formid2468] [-h]
#		 ./mertide.py --input=merform.csv --disaggs=/path/to/disagg/files/ [--noconnection] [--forms="formuid1234,formid2468"] [--help]

# pip install openpyxl

import sys
import getopt
import csv
import random
import string
import re
import os
from collections import defaultdict
from xml.sax.saxutils import escape
import zipfile
import zlib
import hashlib
import base64
import requests
import json
import operator
from pprint import pprint

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

# Removes files with funny names
def filenameChecker(filename):
	bumFiles=['.DS_Store']
	if filename in bumFiles:
		return False
	return True

def isDhisUid(string):
	if (len(string) != 11):
		return False
	if not bool(re.search('[A-Za-z]', string[:1])):
		return False
	if not bool(re.search('[A-Za-z0-9]{9}', string[1:11])):
		return False
	return True

# Finds a data element, either using the dataElementCache or DHIS 2
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

def makeUid():
	uid = random.choice(string.ascii_letters)
	for i in range(0, 10):
		uid += random.choice(string.ascii_letters+'0123456789')
	return uid

# return 5+input char ssid. This should be max 8 total, #TODO, limit returned result to 8 chars.
def makeSsid(htabType):
	ssid = random.choice(string.ascii_letters)
	for i in range(0, 4):
		ssid += random.choice(string.ascii_letters+'0123456789')
	return ssid + htabType

# Make an SSID using a hash that conforms to the SSIDs
# The SSID must be deterministic, so no random functions are used
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

def makeUidHash(s): # Generate a UID deterministcally from a unique string.
	if s=='':
		return 'NotAUID'
	hashBytes = bytearray(hashlib.sha256((s).encode()).digest())
	uid = string.ascii_letters[hashBytes[0] % 52]
	for i in range(1, 11):
		uid += (string.ascii_letters+string.digits)[hashBytes[i] % 62]
	return uid

def safeName(s):
	s = s.replace('<', '_lt_') \
		.replace('>', '_gt_') \
		.replace('+', '_plus_')
	s = re.sub('[\[\(\)\-\s\:,\\\|^&/]', '_', s)
	s = re.sub('_+', '_', s)
	s = re.sub('_$', '', s)
	return s.lower()
	
def codeName(s):
	s = safeName(s)
	return s.upper()

# Within a vertical tab, find which horizontal tabs are present.
def findHtabs(vtab):
	htabsPresent = set([]) # Set of htabs present in this list of rows
	for indicator in vtab['indicators']:
		for row in indicator['rows']:
			if (row['de_dsd1']): htabsPresent.add("DSD")
			if (row['de_ta1']): htabsPresent.add("TA")
			if (row['de_na1']): htabsPresent.add("NA")
	htabs = []
	for htab in allHtabs:
		if (htab['type'] in htabsPresent):
			htabs.append(htab)
	return htabs

# Find out if an indicator should be displayed in a given HTAB.
def htabInIndicator(htab, indicator):
	for row in indicator['rows']:
		if row['de_' + htab['type'].lower() + '1']:
			return True
	return False

# Add a dataElement to the data element list for this form
# and to all the dataElementGroups belonging to this form
def addDataElement(form, uid, groups, categoryCombo = False):
	form['formDataElements'].add(uid)
	for group in groups:
		dataElementGroups[group].add(uid)
	if categoryCombo:
		catComboCache[uid] = categoryCombo

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

def parseMertideExpression(expression):
	# a, the variable to be returned, is an array of parsed expression, data element, 
	# category option, and category option combo
	a = [expression.strip(' '), False, [], []]
	while '.optionCombo:' in a[0]:
		try:
			r = re.compile(r'(.+)\.optionCombo\:\s*\"(.*)\"')
			s = r.search(a[0])
			a[3].append(s.group(2)) # category option combos
			a[0] = s.group(1)
		except:
			log('Syntax error: ' + a[0] + ' has an option combo that cannot be parsed', 'warn')
			break

	while '.option:' in a[0]:
		try:
			r = re.compile(r'(.+)\.option\:\s*\"(.*)\"')
			s = r.search(a[0])
			a[2].append(s.group(2)) # category options
			a[0] = s.group(1)
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

# Adds an expression to a validation rule and returns the modified validation rule
def addExpression(j, side, first, sideData):
	if first:
		j[side]['description'] = 'Value'
		j[side]['expression'] = ''
	else:
		j['name'] += ' + '
		j[side]['description'] += ' + value'
		j[side]['expression'] += '+'

	j[side]['dataElements'].add(sideData['id'])

	if (sideData['optionCombo']):
		j['name'] += sideData['shortName'] + ' / ' + cocCache2[sideData['optionCombo']]
		j[side]['description'] += ' of element ' + sideData['id'] + ' (' + sideData['name'] + ') / ' + cocCache2[sideData['optionCombo']]
		j[side]['expression'] += '#{' + sideData['id'] + '.' + sideData['optionCombo'] + '}'
	else:
		j['name'] += sideData['shortName']
		j[side]['description'] += ' of element ' + sideData['id'] + ' (' + sideData['name'] + ')'
		j[side]['expression'] += '#{' + sideData['id'] + '}'

	return j

def reformatDataElements(elements):
	a = []
	for e in elements:
		a.append({'id': e})
	return a

def hashRule(rule):
	try:
		# Sort both left and right expressions by character, 
		# so if two expressions add terms in different orders,
		# they will still match
		l = ''.join(sorted(rule['leftSide']['expression']))
		r = ''.join(sorted(rule['rightSide']['expression']))
		
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
		log('Could not evaluate either the left or right side of rule ' + rule['description'], 'warn')

# Make and output a form. This is the core work.
def makeForm(form):
	formFileName = safeName(form['name'])
	form['formDataElements'] = set([])
	outputHTML = htmlBefore
	#print ('vtabRowsList:', vtabRowsList)

	# Build major navigation (vtab navigation)
	vtabNames = []
	autocalcjs = ''
	degs = {}
	uidCache = {}
	uidCache2 = []
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
							uid1 = row[prefix + '1']
							uid2 = row[prefix + '2']
							uid3 = row[prefix + '3']
							uids = []

							prefix = 'de_cc_' + htab['type'].lower()
							ccs = {}
							ccs[uid1] = row[prefix + '1']
							ccs[uid2] = row[prefix + '2']
							ccs[uid3] = row[prefix + '3']

							for u in [uid1, uid2, uid3]:
								if u and u != 'null':
									if u in uidCache2:
										log('The uid ' + u + ' appears multiple times', 'severe')
									addDataElement(form, u, form['dataElementGroups'], ccs[u])
									uids.append(u)
									uidCache2.append(u)

							if row['ctl_uniqueid']:
								if (row['ctl_uniqueid'] + '_' + htab['uidsuffix']) in uidCache:
									log('Unique id ' + row['ctl_uniqueid'] + ' for htab ' + htab['uidsuffix'] + ' appears multiple times', 'severe')
								uidCache[row['ctl_uniqueid'] + '_' + htab['uidsuffix']] = uids
								skipCache[row['ctl_uniqueid']] = row['sub_priority']
								ssid = makeSsidHash(row['ctl_uniqueid'], htab['uidsuffix'])
							else:
								ssid = makeSsid(htab['uidsuffix'])
								uidCache[ssid] = uids

							if row['ctl_exclusive']:
								# FIXME: Maybe cache ssid hashes
								mewid = makeSsidHash(row['ctl_exclusive'], htab['uidsuffix'])
								mewid = ' mew_' + mewid
								left = 'R'
								action = 'exclusive_pair'
								right = row['ctl_exclusive']
								rules.append([left, action, right, htab['uidsuffix'], uids, '', 'ctl_exclusive row ' + row['ctl_exclusive'], '', form['periodType']])
							else:
								mewid = ''

							if row['ind_top_level']:
								if row['ind_top_level'] not in topLevelIndicators:
									topLevelIndicators[row['ind_top_level']] = {}
								for u in uids:
									topLevelIndicators[row['ind_top_level']][u] = True
								
							subIndicatorsHTML += '<div class="si_' + ssid + mewid + '">\n'
							if not('autocalc' in row['sub_disagg'] and 'wide' in row['sub_disagg']):
								ssids = [ssid]
								subIndicatorsHTML += open(comboDir + row['sub_disagg'] + '.html').read().format(
									priority=row['sub_priority'], priority_css='PEPFAR_Form_Priority_'+safeName(row['sub_priority']), 
									description=row['sub_heading'], description2=row['sub_text'], 
									ssid=ssid, mew=mewid, deuid1=uid1, deuid2=uid2, deuid3=uid3) + '\n</div>\n\n\n'
							else:
								ssids = [ssid, makeSsid(htab['uidsuffix']), makeSsid(htab['uidsuffix']), makeSsid(htab['uidsuffix'])]
								if (';' in row['sub_text']):
									sub_text_1, sub_text_2, sub_text_3 = row['sub_text'].split(';')
								else:
									sub_text_1, sub_text_2, sub_text_3 = ['', '', '']

								subIndicatorsHTML += open(comboDir + row['sub_disagg'] + '.html').read().format(
									priority=row['sub_priority'], priority_css='PEPFAR_Form_Priority_'+safeName(row['sub_priority']), 
									description=row['sub_heading'], sub_text_1=sub_text_1, sub_text_2=sub_text_2, sub_text_3=sub_text_3,
									ssid1=ssids[1], ssid2=ssids[2], ssid3=ssids[3], mew=mewid, deuid1=uid1, deuid2=uid2, deuid3=uid3) + '\n</div>\n\n\n'

							if row['ctl_rules']:
								if ';' in row['ctl_rules']:
									rs = row['ctl_rules'].split(';')
								else: 
									rs = [row['ctl_rules']]
								for r in rs:
									if ('=' not in r):
										log('Syntax error: Cannot compile rule ' + r + ' as it is missing equals sign', 'warn')
									else:
										# Save the rules to process later in the script
										a = r.split('=')
										left = a[0]
										right = a[1].strip(' ')
										if (re.search('[^A-Za-z0-9\_\-\s\.\:\"\/\(\)\<\>]', left)):
											log('Syntax error: Rule ' + r + ' cannot be compiled as it either uses an illegal operator (=, <= or >= allowed) or the left expression has illegal characters (letters, numbers, spaces, parens, and certain symbols ("._-:/) allowed)', 'warn')
										elif (re.search('[^A-Za-z0-9\_\-\s\.\:\"\/\(\)\+]', right)):
											log('Syntax error: Rule ' + r + ' cannot be compiled as it either uses an illegal operator (=, <= or >= allowed) or the right expression has illegal characters (letters, numbers, spaces, parens, and certain symbols ("._-:/+) allowed)', 'warn')
										elif (left[-1:] == '<'):
											action = 'less_than_or_equal_to'
											left = left.strip('< ')
											rules.append([left, 'less_than_or_equal_to', right, htab['uidsuffix'], uids, [], row['sub_priority'], 'ctl_rules row ' + r, form['periodType']])
										elif (left[-1:] == '>'):
											action = 'greater_than_or_equal_to'
											left = left.strip('> ')
											rules.append([left, 'greater_than_or_equal_to', right, htab['uidsuffix'], uids, [], row['sub_priority'], 'ctl_rules row ' + r, form['periodType']])
										else:
											rules.append([left, 'autocalculate', right, htab['uidsuffix'], uids, ssids, row['sub_priority'], 'ctl_rules row ' + r, ''])

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

	if not(noconnection):
		for z in rules:
			# Get validation rule period
			rulePeriod = z[8]
		
			# Process left side
			a = parseMertideExpression(z[0])
			leftElement = a[1]
			leftOptions = a[2]
			leftOptionCombos = a[3]

			right = []
			rightMissingValue = False

			if '+' in z[2]:
				rightTerms = z[2].split('+')
			else: 
				rightTerms = [z[2]]

			for t in range(len(rightTerms)):
				a = parseMertideExpression(rightTerms[t])
				rightTerms[t] = a[0]
				rightElement = a[1]
				rightOptions = a[2]
				rightOptionCombos = a[3]

				try:
					if z[1] == 'autocalculate':
						if rightTerms[t] == 'R':
							rssid = z[5]
						else:
							rssid = makeSsidHash(rightTerms[t], z[3])

						uids = uidCache[rightTerms[t] + '_' + z[3]]
						for uid in uids:
							if rightOptions:
								cocs = getCocsFromOptions(rightOptions, uid)
								right.append([rssid, cocs])
							elif rightOptionCombos:
								for coc in rightOptionCombos:
									rightOptionCombo = getCoc(coc, uid)
									right.append([rssid, [rightOptionCombo]])
							else:
								right.append([rssid])
								break

					else:
						if rightTerms[t] == 'R':
							ruids = z[4]
						elif (rightTerms[t] + '_' + z[3]) in uidCache:
							ruids = uidCache[rightTerms[t] + '_' + z[3]]
						else:
							ruids = []
						if rightElement:
							ruids = [ruids[rightElement-1]]
						for r in ruids:
							if rightOptions:
								cocs = getCocsFromOptions(rightOptions, r)
								for coc in cocs:
									right.append(getDataElement(r, coc).copy())
							else:
								if rightOptionCombos:
									for coc in rightOptionCombos:
										right.append(getDataElement(r, coc).copy())
								else:
									right.append(getDataElement(r, False).copy())

						if rightMissingValue != 'NEVER_SKIP':
							q = rightTerms[t]
							if rightTerms[t] == 'R':
								q = z[6]
							elif rightTerms[t] in skipCache:
								q = skipCache[rightTerms[t]]

							if q in skip:
								rightMissingValue = 'SKIP_IF_ALL_VALUES_MISSING'
							elif q in neverskip:
								rightMissingValue = 'NEVER_SKIP'
							else:
								log('Syntax error: ' + q + ' not associated with missing value strategy for rule ' + z[7], 'warn')

				except Exception as e: 
					log('Syntax error: Problem compiling right expression in ' + z[7], 'warn')

			if right:
				if z[1] == 'autocalculate':
					if not(leftElement):
						left = z[5][0]
					else:
						left = z[5][leftElement]
					autocalcjs += "\tstella.autocalc('" + left + "', " + str(right) + ");\n"

				else:
					left = []
					try:
						luids = z[4]
						if leftElement:
							luids = [luids[leftElement-1]]
						for l in luids:
							if leftOptions:
								cocs = getCocsFromOptions(leftOptions, l)
								for coc in cocs:
									left.append(getDataElement(l, coc).copy())
							else:
								if leftOptionCombos:
									for coc in leftOptionCombos:
										left.append(getDataElement(l, coc).copy())
								else:
									left.append(getDataElement(l, False).copy())

					except Exception as e:
						log('Syntax error: Problem compiling left expression in ' + z[7], 'warn')
						left = [{}]

					if left != [{}] and right != [{}]:
						j = {}
						j['importance'] = 'MEDIUM'
						j['ruleType'] = 'VALIDATION'
						j['periodType'] = rulePeriod
						j['operator'] =  z[1]
						j['leftSide'] = {}
						j['rightSide'] = {}
						j['leftSide']['dataElements'] = set([])
						j['rightSide']['dataElements'] = set([])
						j['name'] = ''
						j['leftSide']['description'] = ''
						j['rightSide']['description'] = ''

						for l in left:
							j = addExpression(j, 'leftSide', not(j['name']), l)

						if j['operator'] == 'less_than_or_equal_to' or j['operator'] == 'greater_than_or_equal_to' :
							if j['operator'] == 'less_than_or_equal_to':
								j['name'] += ' <= '
							else:
								j['name'] += ' >= '

							if z[6] in skip:
								j['leftSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'
							else:
								j['leftSide']['missingValueStrategy'] = 'NEVER_SKIP'
								if z[6] not in neverskip:
									log('Syntax error: ' + z[6] + ' not associated with missing value strategy for rule ' + z[7], 'warn')
							j['rightSide']['missingValueStrategy'] = 'NEVER_SKIP'

							if rightMissingValue:
								j['rightSide']['missingValueStrategy'] = rightMissingValue
							else:
								log('Error: Unable to identify missing value strategy for right side of rule ' + z[7] + '; defaulting to NEVER_SKIP', 'warn')
								j['rightSide']['missingValueStrategy'] = 'NEVER_SKIP'

						elif j['operator'] == 'exclusive_pair':
							j['name'] += ' :exclusive: '
							j['leftSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'
							j['rightSide']['missingValueStrategy'] = 'SKIP_IF_ALL_VALUES_MISSING'

						firstRight = True

						for r in right:
							j = addExpression(j, 'rightSide', firstRight, r)
							firstRight = False

						j['description'] = j['name']
						j['instruction'] = j['name']
						j['leftSide']['dataElements'] = reformatDataElements(j['leftSide']['dataElements'])
						j['rightSide']['dataElements'] = reformatDataElements(j['rightSide']['dataElements'])
						h = hashRule(j)
						if h in rulesCache:
							j['id'] = rulesCache[h]
						else:
							j['id'] = makeUid()
						
						# Shorten the name if it's over 230 chars
						j['name'] = j['name'][0:230]
						
						# Shorten the descriptions if they are over 255 chars
						j['leftSide']['description'] = j['leftSide']['description'][0:255]
						j['rightSide']['description'] = j['rightSide']['description'][0:255]
						
						rulesCache[h] = 'used'

						# Only add each rule once
						if j['id'] != 'used':
							if h in dhisRulesCache:
								modified = False
								for key in dhisRulesCache[h]:
									if key == 'leftSide' or key == 'rightSide':
										for key2 in dhisRulesCache[h][key]:
											if dhisRulesCache[h][key][key2] != j[key][key2]:
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
					else:
						if left == [{}]:
							log('Syntax error: Left expression appears empty after processing in ' + z[7], 'warn')
						if right == [{}]:
							log('Syntax error: Right expression appears empty after processing in ' + z[7], 'warn')

		for i in degs:
			try:
				req = requests.get(api + 'dataElementGroups.json', cookies=jsessionid,
					params = {'paging': False, 'fields': 'name,id', 'filter': 'name:eq:' + i})
				groups = form['dataElementGroups'].copy()
				groups.append(req.json()['dataElementGroups'][0]['id'] + '_' + i)
				for uid in degs[i]:
					addDataElement(form, uid, groups)
			except Exception as e: 
				log('Syntax error: Problem with data element group set ' + i, 'warn')

	else:
		log('Not connected to DHIS 2, so skipping all rules and data element group sets', 'warn')


	# Set special JS extras
	outputHTML = outputHTML.replace("//#dataValuesLoaded#", '\n' + autocalcjs) #cannot use format here because all the curly braces {} in the javascript and css
	#outputHTML = outputHTML.replace("//#formReady#","") 
	#outputHTML = outputHTML.replace("//#dataValueSaved#","") 

	outputHTML += majorNavHTML_end+'<!-- End Custom DHIS 2 Form -->\n\n'

	# Create the standalone form preview file
	if severe:
		log('Skipping form due to severe error: ' + form['name'] + ' - ' + form['uid'])
		return
	elif specificForms and form['uid'] not in formsToOutput:
		log('Skipping form: ' + form['name'] + ' - ' + form['uid'])
	else:
		log('Creating form: ' + form['name'] + ' - ' + form['uid'])
		formFile = open(outDir+formFileName+'.html', 'w')
		formFile.write(open(standaloneHTMLa).read().replace('MER Results: Facility Based', form['name']))
		formFile.write(outputHTML)
		formFile.write(open(standaloneHTMLb).read())
		formFile.close()

	# Format the dataset for the ouput XML files
	datasetPrefix = open('codechunks/dataset_prefix.xml').read() \
		.format(code=codeName(form['shortshortname']), name=form['name'], shortname=form['shortshortname'], uid=form['uid'], periodType=form['periodType'],
				categoryCombo=form['categoryCombo'], version=form['version'], approveData=form['approveData'] )

#   2.21 to 2.24
#   dataElements = '			<dataElements>\n'
#   for id in form['formDataElements']:
#	   dataElements += '			   <dataElement id="' + id + '" />\n'
#   dataElements += '		   </dataElements>\n'

	#2.25 updates
	dataElements = '			<dataSetElements>\n'
	for id in form['formDataElements']:
		dataElements += '			   <dataSetElement>\n'
#	   dataElements += '				   <externalAccess>false</externalAccess>\n'
		dataElements += '				   <dataElement id="' + id + '" />\n'
		dataElements += '				   <dataSet id="' + form['uid'] + '" />\n'
		if id in catComboCache:
			dataElements += '				   <categoryCombo id="' + catComboCache[id] + '" />\n'
		dataElements += '			   </dataSetElement>\n'
	dataElements += '		   </dataSetElements>\n'

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

		thisDatasetPrefix = datasetPrefix
		
		if form['workflow']:
			thisDatasetPrefix += '		  <workflow id="' + form['workflow'] + '" />\n'
			
		exportDatasets.append(thisDatasetPrefix +
			'		   <dataEntryForm id="' + form['formUid'] + '" />\n' +
			dataElements +
			'	   </dataSet>\n')


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
				if row['deg1_name']: form['dataElementGroups'].append(row['deg1_uid'] + '_' + row['deg1_name'])
				if row['deg2_name']: form['dataElementGroups'].append(row['deg2_uid'] + '_' + row['deg2_name'])
				if row['deg3_name']: form['dataElementGroups'].append(row['deg3_uid'] + '_' + row['deg3_name'])
				if row['deg4_name']: form['dataElementGroups'].append(row['deg4_uid'] + '_' + row['deg4_name'])
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

# Function to write dataElementGroups to an export file
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

def main(argv):
	
	sysargs = ['','','',False,'']
	usage = 'usage: mertide.py -i [merform.csv|merdirectory] -d /path/to/disagg/files/ [options]\n  options:\n    -n, --noconnection Parse CSV even if there is no connection to DHIS2\n    -f formuid1234,formid2468, [--forms=formuid1234,formid2468]\n	Only include forms with uid formuid1234 and formuid2468\n    -h,--help Prints this message'
	
	try:
		opts, args = getopt.getopt(argv,'i:d:f:h:n',['input=','disaggs=','noconnection','forms=','help'])
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
				elif not os.path.isfile(arg):
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
	
	if sysargs[2] == '' or (sysargs[0] == '' and sysargs[1] == ''):
		log(usage)
		sys.exit(2)
 
	return sysargs

dataElementCache = {}
catComboCache = {}
optionCache = {}
cocCache = {}
cocCache2 = {}
rulesCache = {}
dhisRulesCache = {}
newRules = []
modifiedRules = []
oldRules = []
topLevelIndicators = {}
inputArgs = []
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

#Get those args!
if __name__ == '__main__':
   inputArgs = main(sys.argv[1:])
controlDir = inputArgs[0]
controlFile = inputArgs[1]
comboDir = inputArgs[2]
noconnection = inputArgs[3]

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
#	req = requests.get(api + 'resources.json', auth=credentials)
	req = requests.get(api + 'resources.json', cookies=jsessionid)
	if req.json()['resources'][0]:
		log('Connected to DHIS 2 using ' + api)
	else:
		raise ConnectionError('Not connected to DHIS 2')
except:
	log('Not connected to DHIS 2')
	if not(noconnection):
		sys.exit(2)

#CSS
cssStart = '<style>'
css = './css/main.css'
cssEnd = '</style>'

#Javascript
jsStart = '<script>'
js = []
jsEnd = '</script>'
jsDir = './js'
for (dirpath, dirnames, filenames) in os.walk(jsDir):
	js.extend(filenames)
	break

outDirStandalone = './output/'
htmlBefore = "<!-- Start Custom DHIS 2 Form -->\n"

#standalone wrappers
standaloneHTMLa = './codechunks/standaloneform_before.html'
standaloneHTMLb = './codechunks/standaloneform_end.html'

ulClose = '</ul>\n'
divClose = '</div>\n'

#Major Navigation List with HTML
majorNavHTML_before = \
	'<div class="PEPFAR_reporting_legend">\n' + \
	'\t<i class="fa fa-square PEPFAR_quarterly_square">&nbsp;</i>\n' + \
	'\t<span>Quarterly Reporting</span>\n' + \
	'\t<i class="fa fa-square PEPFAR_semiannually_square">&nbsp;</i>\n' + \
	'\t<span>Semiannually Reporting</span>\n' + \
	'\t<i class="fa fa-square PEPFAR_annually_square">&nbsp;</i>\n' + \
	'\t<span>Annually Reporting</span>\n</div>\n\n' + \
	'<div id="PEPFAR_Tabs_vertical">\n' + \
	'<ul>'
majorNavHTML_li = '\t<li><a href="#PEPFAR_Tabs_vertical_%s">%s</a></li>'
majorNavHTML_after = ulClose
majorNavHTML_end = divClose

allHtabs = [{'type': 'DSD', 'label': 'DSD', 'uidsuffix': 'dsd'}, {'type': 'TA', 'label': 'TA-SDI', 'uidsuffix': 'xta'}, {'type': 'NA', 'label': 'Other', 'uidsuffix': 'xna'}]

#Minor Navigation List with HTML
minorNavHTML_before = '<div id="PEPFAR_Tabs_vertical_%s">\n<div id="PEPFAR_Tabs_h_%s">\n<ul>'
minorNavHTML_li='\t<li><a href="#PEPFAR_Form_%s_%s">%s</a></li>'
minorNavHTML_after=ulClose
minorNavHTML_end=divClose+divClose

#Entry Area
entryAreaHTML_start = '<div id="PEPFAR_Form_%s_%s">\n<p class="PEPFAR_Form_ShowHide">&nbsp;</p>\n\n'
entryAreaHTML_end = divClose

#Indicator
indicatorHTML_before = \
	'<!-- {title} -->\n' + \
	'<div class="PEPFAR_Form">\n' + \
	'<div class="PEPFAR_Form_Container PEPFAR_Form_Title PEPFAR_Form_Title_{frequency}">{name}</div>\n' + \
	'<div class="PEPFAR_Form_Collapse">\n'
indicatorHTML_after = \
	'</div>\n' + \
	'<!-- END {title} --></div>\n\n' + \
	'<p>&nbsp;</p>\n\n'

# Builds HTML prefix to use before the form-specific contents

#CSS
htmlBefore+="\n"+cssStart+"\n"
with open(css, "r") as readFile:
	htmlBefore+=readFile.read()
htmlBefore+="\n"+cssEnd+"\n"

#All JS Files
htmlBefore+="\n"+jsStart+"\n"
for jsFile in js:
	with open(jsDir+'/'+jsFile, "r") as readFile:
		if(filenameChecker(jsFile)):
			htmlBefore+=readFile.read()
			htmlBefore+="\n"
htmlBefore+="\n"+jsEnd+"\n"

#Major Nav
htmlBefore+=majorNavHTML_before+"\n"

exportDataEntryForms = [] #Array of XML <dataEntryForm> definitions to export (v2.22 and following)
exportDatasets = [] #Array of XML <dataset> definitions to export (v2.22 and following)
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
	controlFile = outDirStandalone + 'temp.csv'
	o = open(controlFile, 'w')
	for i in os.listdir(controlDir):
		if i.endswith('.csv'):
			ih = open(controlDir + i, 'r')
			o.write(ih.read())
	o.close()

doControlFile(controlFile)

# Write XML import file for api/xx/metadata

if severe:
	log('Skipping datasets.xml due to severe error')
else:
	export = open(outDir+'datasets.xml', 'w')
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

	if len(topLevelIndicators) > 0:
		export.write('	<indicators>\n')
		for indicator in topLevelIndicators:
			log('Creating indicator: ' + indicator + ' - ' + makeUidHash('datimIndicator' + indicator))
			export.write(formatIndicator(indicator, topLevelIndicators[indicator]))
		export.write('	</indicators>\n')

	export.write('</metadata>\n')
	export.close()
	z = zipfile.ZipFile(outDir + 'datasets.xml.zip', 'w', zipfile.ZIP_DEFLATED)
	z.write(outDir+'datasets.xml')
	z.close()

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

log('Finished processing control file, exiting normally')
logFile.close()
