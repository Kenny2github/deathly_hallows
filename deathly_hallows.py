"""It's a bot."""
import sys
import os
import time
import re
import pickle
import mw_api_client as mwc
import mwparserfromhell as mwp
import easygui as e

#setup
print('Loading login data...')
with open('login.txt') as info: #open login info
    USERNAME = info.readline().strip() #username on first line
    PASSWORD = info.readline().strip() #password on second line
    API = info.readline().strip() #api url on third line
print('Loaded login data.')
sw = mwc.Wiki(API, 'Python/3.6.3, deathly_hallows/2.0') #init the wiki
#get configuration
print('Loading config...')
CONFIG = {}
if '--refresh-config' in sys.argv or 'config.pickle' not in os.listdir('.'):
    print(' Fetching config...')
    CONFIG['arbit'] = list(sw.page(f'User:{USERNAME}/Config/ArbitraryPages')
                           .revisions(1))[0].comment.split(';')
    print(' Loaded config: arbitrary page names')
    gen = sw.category(CONFIG['arbit'][0]).categorymembers(cmnamespace=10)
    gen = [cm for cm in gen if not cm.title.endswith('/doc')] #no documentations
    templates = gen[:]
    for temp_ in gen: #for every template
        links = temp_.backlinks(blfilterredir='redirects', blnamespace=10) #get template redirects
        templates.extend(links) #list.extend is so cool
    templates = [temp.title.replace('Template:',
                                    '(?:Template:)?') for temp in templates]
    CONFIG['templates'] = '|'.join(templates) #join into one alternative
    del templates, gen #not for export (?)
    print(' Loaded config: templates with date parameters')
    CONFIG['dateformat'] = list(sw.page(f'User:{USERNAME}/Config/TemplateDateFormat')
                                .revisions(1))[0].comment
    print(' Loaded config: template date format')
    CONFIG['cncount'] = int(list(sw.page(f'User:{USERNAME}/Config/InaccurateCnCount')
                             .revisions(1))[0].comment)
    print(' Loaded config: inaccurate {{cn}} count')
    contents = sw.page(f'User:{USERNAME}/Config/FirstAndSecondPersonWords').read()
    CONFIG['words'] = re.search('<pre>(.*)</pre>',
                                contents, re.S).group(1).strip().replace('\n', '|')
    del contents #not for export (?)
    print(' Loaded config: first and second person words')
    CONFIG['refformat'] = list(sw.page(f'User:{USERNAME}/Config/ReferenceFormat')
                               .revisions(1))[0].comment
    print(' Loaded config: reference format')
    contents = sw.page(f'User:{USERNAME}/Config/StyleRegexes').read()
    contents = re.search(r'<pre>(.*?)</pre>', contents, re.S).group(1)
    CONFIG['styles'] = {}
    for match in re.finditer(r'(?P<key>[-a-zA-Z]+): (?P<negate>!?)%(?P<value>.*?)%', contents):
        CONFIG['styles'][match.group('key')] = {
            '*': match.group('value'), 'negate': match.group('negate')
        }
    del contents #not for export (?)
    print(' Loaded config: style guideline regexes')
    print(' Pickling config...')
    with open('config.pickle', 'wb') as config:
        pickle.dump(CONFIG, config, -1)
    print(' Pickled config.')
else:
    print(' Using cached config.')
    with open('config.pickle', 'rb') as config:
        CONFIG = pickle.load(config)
        print(' Loaded config: everything')
print('Loaded config.')

#login
print('Logging in...')
result = sw.login(USERNAME, PASSWORD)
print('Login result:', result['result'])

def submitedit(pageobj_, contents_, summ):
    """Submit edit function"""
    if '--confirmedit' in sys.argv:
        confirm = e.codebox(f'Confirm edit on {page}', 'Confirm Edit', contents_)
        if confirm is None or not confirm.strip():
            return 'Cancelled'
    result = pageobj_.edit(contents_, summ, nocreate=1)
    return result['edit']['result']

# This section is the de-1st/2nd-personifying section.
# It asks for user input as to how many pages to depersonify,
# and, if the input is a non-zero number:
# 1. gets a list of random pages with length equal to input,
# 2. for every page:
#     1. makes sure that it has 1st/2nd person words (as specified in configuration).
#        If it doesn't, it stops here. If it does,
#     2. highlights each instance with unicode FULL BLOCK (U+0x2588) characters,
#     3. pops up a dialog box with the highlighted content,
#        and waits for the user to finish editing,
#     4. makes sure that the content is not None or empty. If it is, it skips the edit
#        (the usages of personification could have been perfectly legitimate). Otherwise,
#     5. submits the edit.

limit = int(input('Press Enter to skip de-personifying, or a number '
                  '(then Enter) to do it on that amount of pages: ') or '0')
if limit: #if limit != 0
    pages = [] #no pages yet
    print(' Requesting random pages...')
    pages = sw.random(limit=limit, namespace=0)
    print(' Requested random pages.')
    for page in pages: #for every page
        content = page.read()
        exp = re.compile(r'(\s|(?=[ -~])\W)(?=[a-zA-Z\']+)('
                         + CONFIG['words'] + r')((?=[ -~])\W)', re.I)
        if re.search(exp, content): #if there's a match
            content = re.sub(exp, r'\1\u2588\2\u2588\3', content) #highlight every instance
            try:
                content = e.codebox('Modify content below - first and second person '
                                    'are highlighted in \u2588s. Press Cancel '
                                    'or leave blank to cancel.',
                                    'Modify Content of ' + page, content).strip() or None
            except AttributeError:
                content = None
            if content is not None: #if it's not None
                content = content.replace('\u2588', '') #remove all highlights
                print('Edit on page',
                      page.title + ':',
                      submitedit(page,
                                 content,
                                 'Semi-automated edit: de-1st/2nd-personified.')) #submit the edit
else:
    del limit

#raise SystemExit #uncomment this to stop here


# This section is the reference updating section.
# It asks for user input as to how many pages to depersonify,
# and, if the input is a non-zero number:
# 1. gets a list of random pages with length equal to input,
# 2. for every page:
#     1. makes sure that it has a <references/> tag, meaning that there are references.
#        If it doesn't, it stops here. If it does,
#     2. highlights each instance with unicode FULL BLOCK (U+0x2588) characters,
#     3. pops up a dialog box with the highlighted content,
#        and waits for the user to finish editing,
#     4. makes sure that the content is not None or empty. If it is, it skips the edit
#        (all of the references might have not needed to follow the format). Otherwise,
#     5. submits the edit.


limit = int(input('Press Enter to skip reference updating, '
                  'or a number (then Enter) to do it on that amount of pages: ') or '0')
if limit: #if limit != 0
    pages = [] #no pages yet
    print(' Requesting random pages...')
    pages = sw.random(limit=limit, namespace=0)
    print(' Requested random pages.')
    for page in pages: #for every page
        content = page.read()
        if re.search('<references */>', content, re.I):
            content = re.sub(r'((?!<ref>{}</ref>)(?:<ref>.*?</ref>))'.format(CONFIG['refformat']),
                             r'\u2588\1\u2588', content) #monster regex to highlight every instance
            try:
                content = e.codebox(u'Modify content below - bad references '
                                    'are highlighted in \u2588s. Press Cancel '
                                    'or leave blank to cancel.',
                                    'Modify Content of ' + page, content).strip() or None
            except AttributeError:
                content = None
            if content is not None: #if it's not None
                content = content.replace(u'\u2588', '') #remove all highlights
                print('Edit on page', page.title + ':',
                      submitedit(page,
                                 content,
                                 'Semi-automated edit: updated references to follow format.'))
else:
    del limit #otherwise just delete limit

#raise SystemExit #uncomment this to stop here

# This section is the most complicated - the adding of dates to templates.
# It checks that there are pages in the category "Pages with Dateless Templates",
# and if there are, for ever page:
# 1. gets the page content,
# 2. checks that {{NoBots}} isn't in the page. If it is, it skips to the next page. Otherwise,
# 3. checks that the page has any templates without dates (duh), and if there are,
# 4. adds the date (more about this is in the docstrings of gd and repl),
# 5. adds {{inaccurate}} with date if there are over configured {{citation needed}}s,
# 6. finally, submits the edit.

def get_date(pageob, templatename): #get date from diffs function
    """Get the date that a certain template was added.
The process is:
1. Get a list of revision IDs, and for each revision:
    1. Get the difference to the previous revision,
    2. Get a list of tags whose names are not "del"
    3. Use a monster regex to find out if this diff added the particular template we're looking for,
    4. If it did, set the date to a time.struct_time from the revision timestamp, and break.
2. If the date was never set, assume it's the date of the earliest revision,
3. Get the month name and year, and return that."""
    print(f'Adding date to template {templatename}\n  Getting date') #log getting date
    processed = []
    for rev in pageob.revisions(rvprop='content|ids|timestamp'): #for every revision
        print('   Revision ID', rev.revid)
        processed.append(rev)
        parsedcontents = mwp.parse(rev.__dict__['*'], 0, True) #hack
        has_template = False
        for temp in parsedcontents.ifilter_templates():
            if temp.name.lower() == templatename and not temp.has('date'):
                has_template = True
                break
        if not has_template:
            break
    interesting = processed[-2] if len(processed) >= 2 else processed[0]
    date = time.strptime(interesting.timestamp, '%Y-%m-%dT%H:%M:%SZ')
    date = [None, 'January', 'February', 'March', 'April',
            'May', 'June', 'July', 'August', 'September',
            'October', 'November', 'December'][date.tm_mon] + ' ' + str(date.tm_year)
    print('  Found date:', date)
    return date

cms = sw.category(CONFIG['arbit'][1]).categorymembers()
for page in cms: #for every title
    print('Page', page.title)
    content = page.read()
    parsed = mwp.parse(content, 0, True)
    #nobots check
    go_on = True
    for template in parsed.ifilter_templates():
        if template.name.lower() == 'nobots':
            go_on = False
            break
    if not go_on:
        print(' {{NoBots}} in page, skipping.')
        continue
    #add dates! :)
    go_on = False
    for template in parsed.ifilter_templates():
        if re.search(CONFIG['templates'], str(template.name), re.I) \
                and not template.has('date'):
            template.add('date', get_date(page, template.name))
            go_on = True #at least one template was changed
    if go_on:         #if ^
        print("Edit on page", page.title + ":",
              submitedit(page, str(parsed),
                         'Automated edit: added dates to templates')) #submit the edit!
    else:
        print("Page", page.title, "was not edited.") #no change
    time.sleep(1) #sleep 1

#raise SystemExit #uncomment this to stop here

# This section is the {{bad style}} adding section.

limit = int(input('Enter a number of pages to check for bad style (default 10): ') or '10')
print(' Requesting random pages...')
pages = sw.random(limit=limit, namespace=0)
print(' Requested random pages.')
for page in pages:
    print('Page', page)
    content = page.read()
    parsed = mwp.parse(content, 0, True)
    ignore = []
    for template in parsed.ifilter_templates():
        if template.name.lower() == CONFIG['arbit'][3].lower():
            ignore = template.params
            break
    go_on = True
    for template in parsed.ifilter_templates():
        if template.name.lower() in (CONFIG['arbit'][2].lower(), 'nobots', 'disambig', 'faq'):
            go_on = False
            break
    if go_on:
        bads = []
        for k, v in CONFIG['styles'].items():
            if k not in ignore:
                match = (not re.search(v['*'], content)
                         if v['negate'] else re.search(v['*'], content)
                         and not re.search('<(?P<spe>scratchblocks|pre)>.*?'
                                           + v['*'] + '.*?</(?P=spe)>', content, re.S))
                if match:
                    print(' Found flaw:', k)
                    bads.append(k)
        if bads:
            insert = '{{' + CONFIG['arbit'][2] + '\n|' + '\n|'.join(bads) \
                     + '\n|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}\n}}\n'
            links = parsed.filter_wikilinks()
            links = list(filter(lambda link: re.match(r'(Category|[a-z][a-z]([a-z]|-[a-z]+)?):.*',
                                                      str(link.title), re.I), links))
            try:
                parsed.insert_before(links[0], insert)
            except (ValueError, IndexError):
                parsed.append(insert)
            content = str(parsed)
            print('Edit on page', page.title + ':', submitedit(
                page,
                content,
                'Automated edit: added {} ({} guidelines broken)'.format(
                    '{{[[Template:' + CONFIG['arbit'][2] + '|' + CONFIG['arbit'][2] + ']]}}',
                    len(bads)
                )
            ))
        else:
            print('Page', page, 'was not edited - no broken guidelines found.')
    else:
        print(' {{NoBots}} or {{bad style}} in page, skipping.')

#raise SystemExit #uncomment this to stop here

# This section is the adding {{inaccurate}} section.
# The process is:
# 1. Unpickle the cache of pages already seen (using an empty cache if no such file is found)
# 2. Get all the pages embedding Template:Citation needed and Template:Cn,
# and join those lists together.
# 3. Get all the pages embedding Template:Inaccurate, and remove all titles in the list
#    that embed inaccurate.
# 4. For each page:
#     1. Add the page to the cache,
#     2. Count the number of {{citation needed}}s,
#     3. If the number is over configuration, add {{inaccurate}} with date to the top of the page,
#     4. Submit the edit.
# 5. Pickle the updated cache.

try:
    with open('inaccuratecache.pickle', 'rb') as cache:
        cache = pickle.load(cache) #load cache
except IOError: #if there isn't any cache
    cache = [] #make an empty cache

eis = [] #empty list for now
eis.extend([ei.title for ei in sw.template('citation needed').transclusions(namespace='0|4|12')])
eis.extend([ei.title for ei in sw.template('cn').transclusions(namespace='0|4|12')])
for ei in sw.template('inaccurate').transclusions(): #for every embeddedin
    if ei.title in eis:
        eis.remove(ei.title)
try:
    for page in eis: #for every page in embeddedins
        try:
            if page in cache and '--nocache' not in sys.argv:
                print(page, "already in cache, skipping")
                continue #if the page is in the cache, skip it
            else:
                print('Page', page) #log which page we're working on
                cache.append(page) #add the page to cache
                pageobj = sw.page(page, getinfo=True)
                if pageobj.ns in (2, 3): #if this page is in userspace
                    print(' In userspace, skipping.')
                    continue #skip the entire page
                content = pageobj.read()
                parsed = mwp.parse(content, 0, True)
                go_on = True
                for template in parsed.ifilter_templates():
                    if template.name.lower() == 'nobots':
                        go_on = False
                        break
                if not go_on:
                    print(' {{NoBots}} in page, skipping.')
                    continue
                go_on = False
                #all pages with dateless templates have had their dates added now
                detected = 0
                inaccurate_already = False
                for template in parsed.ifilter_templates():
                    if template.name.lower() in ('cn', 'citation needed'):
                        detected += 1
                    elif template.name.lower() == 'inaccurate':
                        inaccurate_already = True
                if detected > CONFIG['cncount'] and not inaccurate_already:
                    content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} ' \
                              '{{subst:CURRENTYEAR}}}}\n' + content
                    summary = 'Automated edit: added {{inaccurate}} (' \
                              + str(detected) + ' {{citation needed}}s)'
                    print('', detected, '{{citation neeeded}}s') #log how many cns
                    go_on = True
                if go_on: #if something happened
                    print("Edit on page", page + ":", submitedit(page, content, summary))
                else:
                    if not detected > CONFIG['cncount']:
                        print(" Not enough {{citation needed}}s")
                    else:
                        print(" {{inaccurate}} already on page")
                    print("Page", page, "was not edited.") #log not editing
                time.sleep(5) #sleep 5 to avoid throttling
        except mwc.requests.ConnectionError: #if we were throttled anyway
            print('Throttled, sleeping for 30 seconds...') #log that
            if page in cache:
                cache.remove(page)
            time.sleep(30) #sleep half a minute
finally: #no matter what
    with open('inaccuratecache.pickle', 'wb') as cach:
        pickle.dump(cache, cach, -1) #dump the cache
