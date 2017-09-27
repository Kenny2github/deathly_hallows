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
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'comment','rvlimit':'1','titles':'User:%s/Config/InaccurateCnCount' % username,'format':'json'}).text) #get number of {{cn}}s for inaccurate template
cncount = int(r['query']['pages'].values()[0]['revisions'][0]['comment']) #get the comment of the last revision - the number is stored there
r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','rvlimit':'1','titles':'User:%s/Config/FirstAndSecondPersonWords' % username,'format':'json'}).text) #get first and second person words
words = re.search('<pre>(.*)</pre>', r['query']['pages'].values()[0]['revisions'][0]['*'], re.S).group(0).strip().replace('\n', '|')

#login
r = json.loads(s.post(api, params={'action':'login','lgname':username,'format':'json'}).text) #request login token through action=login
token = r['login']['token'] #get token from result
r = json.loads(s.post(api, data={'action':'login','lgname':username,'lgpassword':password,'lgtoken':token,'format':'json'}).text) #login with token
result = r['login']['result'] #set result
print 'Login result:', result #print result

#define some stuff
def submitedit(title, content, summary): #submit edit function
    r = json.loads(s.get(api, params={'action':'tokens','type':'edit','format':'json'}).text) #request edittoken
    token = r['tokens']['edittoken'] #get token from result
    r = json.loads(s.post(api, data={'action':'edit','title':title,'text':content,'summary':summary,'token':token,'bot':'true','format':'json'}).text) #long post request for edit
    return r['edit']['result'] #return edit result

limit = int(raw_input('Press Enter to skip de-personifying, or a number (then Enter) to do it on that amount of pages: ') or '0')
if limit:
    pages = []
    contin = ''
    while limit > 0:
        r = json.loads(s.get(api, params={'action':'query','list':'random','rnlimit':str(limit % 20 if limit > 20 else limit),'rnnamespace':'0','format':'json'}).text) #get list of random pages
        limit -= 20
        r = r['query']['random']
        pages += [p['title'] for p in r]
    for page in pages:
        r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvprop':'content','format':'json'}).text) #get page
        content = r['query']['pages'][r['query']['pages'].keys()[0]]['revisions'][0]['*'] #get page content
        exp = re.compile(r'(\s|(?=[ -~])\W)(?=[a-zA-Z\']+)(' + words + r')((?=[ -~])\W)', re.I)
        if re.search(exp, content):
            content = re.sub(exp, ur'\1\u2588\2\u2588\3', content)
            content = e.codebox(u'Modify content below - first and second person are highlighted in \u2588s. Press Cancel to cancel.', 'Modify Content of ' + page, content)
            if not content is None:
                content = content.strip()
                content = re.sub(ur'\u2588([^!\s]+?)\u2588', r'\1', content)
                print 'Edit on page ' + page + ': ' + submitedit(page, content, 'Semi-automated edit: de-1st/2nd-personified.')
else:
    del limit

#raise SystemExit #uncomment this to stop here

def gd(page, template): #get date from diffs function
    '  Getting date'
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvlimit':'max','format':'json'}).text) #get all (or amap) revisions on that page
    rvs = r['query']['pages'][r['query']['pages'].keys()[0]]['revisions'] #narrow down to list of revisions
    date = None
    for rev in rvs: #for every revision
        print '   Revision ID', rev['revid']
        r = json.loads(s.get(api, params={'action':'query','prop':'revisions','titles':page,'rvstartid':rev['revid'],'rvendid':rev['revid'],'rvdiffto':'prev','format':'json'}).text) #get diff to prev using this rev’s revid
        diff = r['query']['pages'][r['query']['pages'].keys()[0]]['revisions'][0] #narrow down to revision
        try:
            difftags = mw.parse(diff['diff']['*']).filter_tags() #filter tags for better processing
            tags = [] #blank for now
            for i in difftags:
                try: tags.append(xmlx.Element(str(i))) #convert tag to str and make it an element, then append
                except: continue #if it couldn't be converted or wasn't parsable, continue
            tags = [i for i in tags if i.name != 'del'] #remove all the del tags
            for tag in tags:
                i.removechildren(lambda e:e.name == 'del') #remove del tags from all children
            for tag in tags: #for every remaining tag
                if re.search(r'(?:{{((?:%s)(?![^{}]*?\|date=)[^{}]*?)}})|(?:{{[^{}]*?<([^<>/]*?)[^<>/]*?>%s</\2>[^{}]*?}})' % (template, template), tag.content, re.S|re.I): #check if there was 
                    date = time.strptime(diff['timestamp'], '%Y-%m-%dT%H:%M:%SZ') #get date if it was
                    break #we’ve found the date, get outta here
        except KeyError: #workaround for hidden revisions - diff['diff']['*'] will raise a KeyError if the diff is missing
            continue #skip the hidden revision
    if not date:
        date = time.strptime(rvs[-1]['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
    date = [None, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][date.tm_mon] + ' ' + str(date.tm_year)
    print '  Found date:', date
    return date #return the month name and year

def repl(m): #just for date-getting
    global page #globals :)
    print ' Adding date to template', m.group('template')
    return '{{' + m.group(1) + '|date=' + gd(page, m.group('template')) + '}}' #return template with date added

r = json.loads(s.get(api, params={'action':'query','list':'categorymembers','cmtype':'page','cmlimit':'max','cmtitle':'Category:Pages with Dateless Templates','format':'json'}).text) #get Category:Pages with Dateless Templates
r = r['query']['categorymembers'] #list of cms
cms = [] #empty list for now
for cm in r: #for every member
    cms.append(cm['title']) #add its title
for page in cms: #for every title
    print 'Page', page
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','titles':page,'rvlimit':'1','format':'json'}).text) #get content of page
    content = r['query']['pages'][r['query']['pages'].keys()[0]]['revisions'][0]['*'] #get page content
    if re.search('{{NoBots}}', content, flags=re.S|re.I): #if there's a {{NoBots}} tag
        print ' {{NoBots}} in page, skipping.'
        continue #skip the entire page
    summary = 'Automated edit:' #first part of summary
    if re.search(r'{{((?:%s)(?![^{}]*?\|date=)[^{}]*?)}}' % templates, content, flags=re.S|re.I): #if there are templates without dates
        content = re.sub(r'{{((?P<template>%s)(?![^{}]*?\|date=)[^{}]*?)}}' % templates, repl, content, flags=re.S|re.I) #add the dates
        summary += ' added date to templates;' #add to summary
    if len(re.findall('{{(cn|citation needed)}}', content)) > cncount and not re.search('{{inaccurate[^{}]*?}}', content, flags=re.S|re.I): #if over cncount cns and {{inaccurate}} hasn't already been added
        content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}}}' + content #add inaccurate template to top (with date)
        summary += ' added {{inaccurate}} (' + str(len(re.findall('{{(cn)|(citation needed)}}', content))) + ' {{citation needed}}s);' #add to summary
    if summary != 'Automated edit:': #if something happened
        print "Edit on page", page, "with summary '" + summary + "':", submitedit(page, content, summary[:-1]) #submit the edit and print edit result (might not be “success” if page is protected)
    else:
        print "Page", page, "was not edited."
    time.sleep(1)

#raise SystemExit #uncomment this to stop here

r = json.loads(s.get(api, params={'action':'query','list':'embeddedin','eititle':'Template:Citation needed','eilimit':'max','format':'json'}).text) #get embeddedins for citation needed
r = r['query']['embeddedin'] #narrow down to list
eis = [] #empty list for now
for ei in r: #for every embeddedin
    eis.append(ei['title']) #add its title to list
r = json.loads(s.get(api, params={'action':'query','list':'embeddedin','eititle':'Template:Cn','eilimit':'max','format':'json'}).text) #get embeddedins for cn
r = r['query']['embeddedin'] #narrow down to list
for ei in r: #for every extra embeddedin
    eis.append(ei['title']) #add it too
for page in eis: #for every page in embeddedins
    print 'Page', page
    r = json.loads(s.get(api, params={'action':'query','prop':'revisions','rvprop':'content','titles':page,'rvlimit':'1','format':'json'}).text) #get content of page
    if r['query']['pages'][r['query']['pages'].keys()[0]]['ns'] in [2,3]: #if this page is in userspace
        print ' In userspace, skipping.'
        continue #skip the entire page
    content = r['query']['pages'][r['query']['pages'].keys()[0]]['revisions'][0]['*'] #get page content
    if re.search('{{NoBots}}', content, flags=re.S|re.I): #if there's a {{NoBots}} tag
        print ' {{NoBots}} in page, skipping.'
        continue #skip it too
    summary = 'Automated edit:' #first part of summary
    #all pages with dateless templates have had their dates added now
    detected = len(re.findall('{{(cn|citation needed)}}', content))
    if detected > cncount and not re.search('{{inaccurate[^{}]*?}}', content, flags=re.S|re.I): #if over cncount cns and {{inaccurate}} hasn't already been added
        content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}}}' + content #add inaccurate template to top (with date)
        summary += ' added {{inaccurate}} (' + str(detected) + ' {{citation needed}}s);' #add to summary
        print ' ' + str(detected) + ' {{citation neeeded}}s'
    if summary != 'Automated edit:': #if something happened
        print "Edit on page", page, "with summary '" + summary + "':", submitedit(page, content, summary[:-1]) #submit the edit
    else:
        print "Page", page, "was not edited."
    time.sleep(5)
