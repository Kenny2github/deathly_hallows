import requests, re, json, time, xmlx
import mwparserfromhell as mw, easygui as e

#setup
s = requests.session() #start a new session
with open('login.txt') as info: #open login info
    username = info.readline().strip() #username on first line
    password = info.readline().strip() #password on second line
    api = info.readline().strip() #api url on third line
#get configuration
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'comment','rvlimit':'1','titles':'User:%s/Config/TemplatesWithDateParams' % username,'format':'json'}).text) #get list of templates with date parameters
templates = r['query']['pages'].values()[0]['revisions'][0]['comment'] #get the comment of the last revision - the list is stored there
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'comment','rvlimit':'1','titles':'User:%s/Config/TemplateDateFormat' % username,'format':'json'}).text) #get format for dates in templates
dateformat = r['query']['pages'].values()[0]['revisions'][0]['comment'] #get the comment of the last revision - the format is stored there
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'comment','rvlimit':'1','titles':'User:%s/Config/InaccurateCnCount' % username,'format':'json'}).text) #get number of {{cn}}s for inaccurate template
cncount = int(r['query']['pages'].values()[0]['revisions'][0]['comment']) #get the comment of the last revision - the number is stored there
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','rvlimit':'1','titles':'User:%s/Config/FirstAndSecondPersonWords' % username,'format':'json'}).text) #get first and second person words
words = re.search('<pre>(.*)</pre>', r['query']['pages'].values()[0]['revisions'][0]['*'], re.S).group(0).strip().replace('\n', '|') #find the <pre> tag
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'comment','rvlimit':'1','titles':'User:%s/Config/ReferenceFormat' % username,'format':'json'}).text) #get reference format
refformat = r['query']['pages'].values()[0]['revisions'][0]['comment'] #get the comment of the last revision - the format is stored there
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','rvlimit':'1','titles':'Project:Style Guide','format':'json'}).text) #get the project style guide
r = r['query']['pages'].values()[0]['revisions'][0]['*']
r = re.search(r'<!--\nbots::[\s\S]*-->', r).group(0)
styles = {}
for match in re.finditer(r'(?P<key>[-a-zA-Z]+): (?P<negate>!?)%(?P<value>.*?)%', r):
    styles[match.group('key')] = {'*': match.group('value'), 'negate': match.group('negate')}

#login
r = json.loads(s.post(api, params={'action':'login','lgname':username,'format':'json'}).text) #request login token through action=login
token = r['login']['token'] #get token from result
r = json.loads(s.post(api, data={'action':'login','lgname':username,'lgpassword':password,'lgtoken':token,'format':'json'}).text) #login with token
result = r['login']['result'] #set result
print 'Login result:', result #print result

def submitedit(title, content, summary): #submit edit function
    r = json.loads(s.get(api, params={'action':'tokens','type':'edit','format':'json'}).text) #request edittoken
    token = r['tokens']['edittoken'] #get token from result
    r = json.loads(s.post(api, data={'action':'edit','title':title,'text':content,'summary':summary,'token':token,'bot':'true','format':'json'}).text) #long post request for edit
    return r['edit']['result'] #return edit result

"""
This section is the de-1st/2nd-personifying section.
It asks for user input as to how many pages to depersonify, and, if the input is a non-zero number:
1. gets a list of random pages with length equal to input,
2. for every page:
    1. makes sure that it has 1st/2nd person words (as specified in configuration). If it doesn't, it stops here. If it does,
    2. highlights each instance with unicode FULL BLOCK (U+0x2588) characters,
    3. pops up a dialog box with the highlighted content, and waits for the user to finish editing,
    4. makes sure that the content is not None or empty. If it is, it skips the edit (the usages of personification could have been perfectly legitimate). Otherwise,
    5. submits the edit.
"""

limit = int(raw_input('Press Enter to skip de-personifying, or a number (then Enter) to do it on that amount of pages: ') or '0') #limit is int(input) or 0
if limit: #if limit != 0
    pages = [] #no pages yet
    while limit > 0: #while we still have pages left to get
        r = json.loads(s.get(api, params={'action':'query','list':'random','rnlimit':str(limit % 20 if limit > 20 else limit),'rnnamespace':'0','format':'json'}).text) #get list of random pages
        limit -= 20 #limit -= 20
        r = r['query']['random'] #narrow down to list
        pages += [p['title'] for p in r] #titles, not page dicts
    for page in pages: #for every page
        r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvprop':'content','format':'json'}).text) #get page
        content = r['query']['pages'].values()[0]['revisions'][0]['*'] #get page content
        exp = re.compile(r'(\s|(?=[ -~])\W)(?=[a-zA-Z\']+)(' + words + r')((?=[ -~])\W)', re.I) #compile expression for quick use
        if re.search(exp, content): #if there's a match
            content = re.sub(exp, ur'\1\u2588\2\u2588\3', content) #highlight every instance
            try: content = e.codebox(u'Modify content below - first and second person are highlighted in \u2588s. Press Cancel or leave blank to cancel.', 'Modify Content of ' + page, content).strip() #pop up box, let them make edits
            except AttributeError: content = None
            if len(content) < 1: content = None
            if content is not None: #if it's not None
                content = re.sub(ur'\u2588([^\u2588\s]+?)\u2588', r'\1', content) #remove all highlights
                print 'Edit on page ' + page + ': ' + submitedit(page, content, 'Semi-automated edit: de-1st/2nd-personified.') #submit the edit

#raise SystemExit #uncomment this to stop here

"""
This section is the reference updating section.
It asks for user input as to how many pages to depersonify, and, if the input is a non-zero number:
1. gets a list of random pages with length equal to input,
2. for every page:
    1. makes sure that it has a <references/> tag, meaning that there are references,. If it doesn't, it stops here. If it does,
    2. highlights each instance with unicode FULL BLOCK (U+0x2588) characters,
    3. pops up a dialog box with the highlighted content, and waits for the user to finish editing,
    4. makes sure that the content is not None or empty. If it is, it skips the edit (all of the references might have not needed to follow the format). Otherwise,
    5. submits the edit.
"""

limit = int(raw_input('Press Enter to skip reference updating, or a number (then Enter) to do it on that amount of pages: ') or '0') #limit is int(input) or 0
if limit: #if limit != 0
    pages = [] #no pages yet
    while limit > 0: #while we still have pages left to get
        r = json.loads(s.get(api, params={'action':'query','list':'random','rnlimit':str(limit % 20 if limit > 20 else limit),'rnnamespace':'0','format':'json'}).text) #get list of random pages
        limit -= 20 #limit -= 20
        r = r['query']['random'] #narrow down to list
        pages += [p['title'] for p in r] #titles, not page dicts
    for page in pages: #for every page
        r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvprop':'content','format':'json'}).text) #get page
        content = r['query']['pages'].values()[0]['revisions'][0]['*'] #get page content
        if re.search('<references */>', content, re.I): #if we have a <references/> tag - that means we have references!
            content = re.sub(r'((?!<ref>%s</ref>)(?:<ref>.*?</ref>))' % refformat,ur'\u2588\1\u2588', content) #monster regex to highlight every instance
            content = e.codebox(u'Modify content below - bad references are highlighted in \u2588s. Press Cancel or leave blank to cancel.', 'Modify Content of ' + page, content).strip() or None #pop up box, and get result, make it None if it's empty
            if content is not None: #if it's not None
                content = re.sub(ur'\u2588([^\u2588]*?)\u2588', r'\1', content, re.S) #remove all highlights
                print 'Edit on page ' + page + ': ' + submitedit(page, content, 'Semi-automated edit: updated references to follow format.') #submit the edit
else:
    del limit #otherwise just delete limit

#raise SystemExit #uncomment this to stop here

"""
This section is the most complicated - the adding of dates to templates.
It checks that there are pages in the category "Pages with Dateless Templates", and if there are, for ever page:
1. gets the page content,
2. checks that {{NoBots}} isn't in the page. If it is, it skips to the next page. Otherwise,
3. checks that the page has any templates without dates (duh), and if there are,
4. adds the date (more about this is in the docstrings of gd and repl),
5. adds {{inaccurate}} with date if there are over configured {{citation needed}}s,
6. finally, submits the edit.
"""

def gd(page, template): #get date from diffs function
    """Get the date that a certain template was added.
The process is:
1. Get a list of revision IDs, and for each revision:
    1. Get the difference to the previous revision,
    2. Remove all "del" tags from the diff,
    3. Convert all of the remaining tags to xmlx Elements for easier handling,
    4. Recursively remove all "del" tags from all children,
    5. Use a monster regex to find out if this diff added the particular template we're looking for,
    6. If it did, set the date to a time.struct_time from the revision timestamp, and break.
2. If the date was never set, assume it's the date of the earliest revision,
3. Get the month name and year, and return that."""
    print '  Getting date' #log getting date
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvlimit':'max','format':'json'}).text) #get all (or amap) revisions on that page
    rvs = r['query']['pages'].values()[0]['revisions'] #narrow down to list of revisions
    date = None #date is none for now
    for rev in rvs: #for every revision
        print '   Revision ID', rev['revid'] #log revision id
        r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvstartid':rev['revid'],'rvendid':rev['revid'],'rvdiffto':'prev','format':'json'}).text) #get diff to prev using this rev's revid
        diff = r['query']['pages'].values()[0]['revisions'][0] #narrow down to revision
        try:
            difftags = mw.parse(diff['diff']['*']).filter_tags() #filter tags for better processing
            tags = [] #blank for now
            for i in difftags: #for every tag
                try: tags.append(xmlx.Element(str(i))) #convert tag to str and make it an element, then append
                except: continue #if it couldn't be converted or wasn't parsable, continue
            tags = [i for i in tags if i.name != 'del'] #remove all the del tags
            for tag in tags:
                i.removechildren(lambda e:e.name == 'del') #remove del tags from all children
            for tag in tags: #for every remaining tag
                if re.search(r'(?:{{((?:%s)(?![^{}]*?\|date=%s)[^{}]*?)}})|(?:{{[^{}]*?<([^<>/]*?)[^<>/]*?>%s</\2>[^{}]*?}})' % (template, dateformat, template), tag.content, re.S|re.I): #check if there was 
                    date = time.strptime(diff['timestamp'], '%Y-%m-%dT%H:%M:%SZ') #get date if it was
                    break #we've found the date, get outta here
            if date is not None: #we've found the date
                break #get outta here
        except KeyError: #workaround for hidden revisions - diff['diff']['*'] will raise a KeyError if the diff is missing
            continue #skip the hidden revision
    if not date: #if date is still none
        date = time.strptime(rvs[-1]['timestamp'], '%Y-%m-%dT%H:%M:%SZ') #assume it's the earliest revision
    date = [None, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][date.tm_mon] + ' ' + str(date.tm_year) #get month and year
    print '  Found date:', date #log found date
    return date #return the month name and year

def repl(m): #just for date-getting
    """Add the date to the template.
This simply passes the title of the page and the name of the template to gd, and adds the date it returns to the template."""
    global page #globals :)
    print ' Adding date to template', m.group('template')
    return '{{' + m.group(1) + '|date=' + gd(page, m.group('template')) + '}}' #return template with date added

r = json.loads(s.get(api, params={'action':'query','list':'categorymembers','cmtype':'page','cmlimit':'max','cmtitle':'Category:Pages with Dateless Templates','format':'json'}).text) #get Category:Pages with Dateless Templates
r = r['query']['categorymembers'] #list of cms
cms = [] #empty list for now
for cm in r: #for every member
    cms.append(cm['title']) #add its title
for page in cms: #for every title
    print 'Page', page #log which page
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','titles':page,'rvlimit':'1','format':'json'}).text) #get content of page
    content = r['query']['pages'].values()[0]['revisions'][0]['*'] #get page content
    if re.search('{{NoBots.*?}}', content, flags=re.S|re.I): #if there's a {{NoBots}} tag
        print ' {{NoBots}} in page, skipping.'
        continue #skip the entire page
    summary = 'Automated edit:' #first part of summary
    if re.search(r'{{((?:%s)(?![^{}]*?\|date=%s)(?:\|??[^{}]*?))}}' % (templates, dateformat), content, flags=re.S|re.I): #if there are templates without dates
        content = re.sub(r'{{((?P<template>%s)(?![^{}]*?\|date=%s)(?:\|??[^{}]*?))}}' % (templates, dateformat), repl, content, flags=re.S|re.I) #add the dates
        summary += ' added date to templates;' #add to summary
    if len(re.findall('{{(cn|citation needed)}}', content)) > cncount and not re.search('{{inaccurate[^{}]*?}}', content, flags=re.S|re.I): #if over cncount cns and {{inaccurate}} hasn't already been added
        content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}}}' + content #add inaccurate template to top (with date)
        summary += ' added {{inaccurate}} (' + str(len(re.findall('{{(cn)|(citation needed)}}', content))) + ' {{citation needed}}s);' #add to summary
    if summary != 'Automated edit:': #if something happened
        print "Edit on page", page, "with summary '" + summary + "':", submitedit(page, content, summary[:-1]) #submit the edit
    else:
        print "Page", page, "was not edited." #log not editing
    time.sleep(1) #sleep 1

#raise SystemExit #uncomment this to stop here

limit = 10 #yes, it's hardcoded
r = json.loads(s.get(api, params={'action':'query','list':'random','rnlimit':limit,'rnnamespace':'0','format':'json'}).text)
pages = ['User:Kenny2scratch/Sandbox 2']#[p['title'] for p in r['query']['random']]
for page in pages:
    print 'Page', page
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvlimit':'1','rvprop':'content','titles':page,'format':'json'}).text)
    content = r['query']['pages'].values()[0]['revisions'][0]['*']
    if not re.search('(?:{{bad style.*?}}|{{NoBots.*?}})', content, re.S|re.I):
        bads = []
        for k, v in styles.items():
            match = (not re.search(v['*'], content) if v['negate'] else re.search(v['*'], content))
            if match:
                print ' Found flaw:', k
                bads.append(k)
        if bads:
            insert = '{{bad style\n|' + '\n|'.join(bads) + '\n|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}\n}}'
            content = re.sub(r'(?P<pre>[\s\S]*)(?P<cats>(?:\[\[[^]]\]\]\n?)*)\n*$', r'\g<pre>' + insert + r'\g<cats>', content)
            print 'Edit on page', page + ':', submitedit(
                page,
                content,
                'Automated edit: added {template} ({count} guidelines broken)'.format(
                    template='{{[[Template:Bad style|bad style]]}}',
                    count=len(bads)
                )
            )
    else:
        print ' {{NoBots}} or {{bad style}} in page, skipping.'

raise SystemExit #uncomment this to stop here

"""This section is the adding {{inaccurate}} section.
The process is:
1. Unpickle the cache of pages already seen (using an empty cache if no such file is found)
2. Get all the pages embedding Template:Citation needed and Template:Cn, and join those lists together.
3. Get all the pages embedding Template:Inaccurate, and remove all titles in the list that embed inaccurate.
4. For each page:
    1. Add the page to the cache,
    2. Count the number of {{citation needed}}s,
    3. If the number is over configuration, add {{inaccurate}} with date to the top of the page,
    4. Submit the edit.
5. Pickle the updated cache.
"""

import cPickle as pickle, sys #import pickle and sys
try:
    with open('inaccuratecache.pickle', 'rb') as f: cache = pickle.load(f) #load cache
except IOError: #if there isn't any cache
    cache = [] #make an empty cache

r = json.loads(s.get(api, params={'action':'query','list':'embeddedin','eititle':'Template:Citation needed','eilimit':'max','format':'json'}).text) #get embeddedins for citation needed
r = r['query']['embeddedin'] #narrow down to list
eis = [] #empty list for now
for ei in r: #for every embeddedin
    eis.append(ei['title']) #add its title to list
r = json.loads(s.get(api, params={'action':'query','list':'embeddedin','eititle':'Template:Cn','eilimit':'max','format':'json'}).text) #get embeddedins for cn
r = r['query']['embeddedin'] #narrow down to list
for ei in r: #for every extra embeddedin
    eis.append(ei['title']) #add it too
r = json.loads(s.get(api, params={'action':'query','list':'embeddedin','eititle':'Template:Inaccurate','eilimit':'max','format':'json'}).text) #get embeddedins for inaccurate
r = r['query']['embeddedin'] #narrow down to list
for ei in r: #for every embeddedin
    if ei['title'] in eis: eis.remove(ei['title']) #remove it from the list if it's in the list - we won't edit pages that already have inaccurate
try:
    for page in eis: #for every page in embeddedins
        try:
            if page in cache and not '--nocache' in sys.argv: print page, "already in cache, skipping"; continue #if the page is in the cache, skip it
            else:
                print 'Page', page #log which page we're working on
                cache.append(page) #add the page to cache
                r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','titles':page,'rvlimit':'1','format':'json'}).text) #get content of page
                if r['query']['pages'].values()[0]['ns'] in [2,3]: #if this page is in userspace
                    print ' In userspace, skipping.'
                    continue #skip the entire page
                content = r['query']['pages'].values()[0]['revisions'][0]['*'] #get page content
                if re.search('{{NoBots.*?}}', content, flags=re.S|re.I): #if there's a {{NoBots}} tag
                    print ' {{NoBots}} in page, skipping.'
                    continue #skip it too
                summary = 'Automated edit:' #first part of summary
                #all pages with dateless templates have had their dates added now
                detected = len(re.findall('{{(cn|citation needed)[^{}]*?}}', content)) #number of cns
                if detected > cncount and not re.search('{{inaccurate[^{}]*?}}', content, flags=re.S|re.I): #if over cncount cns and {{inaccurate}} hasn't already been added
                    content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}}}' + content #add inaccurate template to top (with date)
                    summary += ' added {{inaccurate}} (' + str(detected) + ' {{citation needed}}s);' #add to summary
                    print ' ' + str(detected) + ' {{citation neeeded}}s' #log how many cns
                if summary != 'Automated edit:': #if something happened
                    print "Edit on page", page, "with summary '" + summary + "':", submitedit(page, content, summary[:-1]) #submit the edit
                else:
                    if not detected > cncount: print " Not enough {{citation needed}}s" #if it was because there weren't enough cns, log that
                    else: print " {{inaccurate}} already on page" #otherwise, log reason being inaccurate already there
                    print "Page", page, "was not edited." #log not editing
                time.sleep(5) #sleep 5 to avoid throttling
        except requests.ConnectionError: #if we were throttled anyway
            print 'Throttled, sleeping for 30 seconds...' #log that
            time.sleep(30) #sleep half a minute
finally: #no matter what
    with open('inaccuratecache.pickle', 'wb') as f: pickle.dump(cache, f, -1) #dump the cache
