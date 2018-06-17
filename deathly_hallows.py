"""It's a bot."""
import sys
import os
import time
import re
from urllib import unquote
from urllib.parse import urlparse
import pickle
import mwparserfromhell as mwp
import easygui as e
import mw_api_client as mwc

#protect against importing
if __name__ != '__main__':
    raise RuntimeError('This module cannot be imported!')

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
        _links = temp_.backlinks(blfilterredir='redirects', blnamespace=10) #get template redirects
        templates.extend(_links) #list.extend is so cool
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
    CONFIG['styletags'] = list(sw.page(f'User:{USERNAME}/Config/BadStyleIgnoreTags')
                               .revisions(1))[0].comment.split('|')
    print(' Loaded config: bad style ignore tags')
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

class StyleGuide(object): #pylint: disable=too-many-public-methods
    """Style guide rules"""
    #pylint: disable=missing-docstring
    @staticmethod
    def _remove_ignore(parsed):
        parsed = mwp.parse(str(parsed))
        for tag in parsed.ifilter_tags():
            if tag.tag in CONFIG['styletags']:
                parsed.remove(tag)
        return parsed

    @staticmethod
    def no_spaces_inside_apos(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        for thing in parsed.ifilter(
                matches=lambda n: getattr(n, 'tag', None) in ('i', 'b')):
            if getattr(thing, 'contents', '').startswith(' ') \
                   or getattr(thing, 'contents', '').endswith(' '):
                return False
        return True

    @staticmethod
    def no_link_underscores(parsed):
        for link in parsed.ifilter_wikilinks():
            if '_' in link.title:
                return False
        return True

    @staticmethod
    def fix_no_link_underscores(parsed):
        for link in parsed.ifilter_wikilinks():
            link.title = str(link.title).replace('_', ' ')

    @staticmethod
    def no_ext_wikilinks(parsed):
        for link in parsed.ifilter_external_links():
            if re.match(r'https?://en\.scratch-wiki\.info',
                        str(link.url), re.I):
                return False
        return True

    @staticmethod
    def fix_no_ext_wikilinks(parsed):
        links = parsed.filter_external_links()
        for link in links:
            if re.match(r'https?://en\.scratch-wiki\.info',
                        str(link.url), re.I):
                url = urlparse(str(link.url))
                letitle = url.path.rsplit('/', 1)[1]
                letitle = unquote(letitle).replace('_', ' ')
                if link.title:
                    newlink = '[[{}|{}]]'.format(
                        letitle, link.title
                    )
                else:
                    newlink = '[[{}]]'.format(letitle)
                parsed.replace(link, newlink)

    @staticmethod
    def no_section_underscores(parsed):
        for link in parsed.ifilter_wikilinks():
            if '#' not in link.title:
                continue
            section = link.title.split('#', 1)[1]
            if re.search(r'(\.[0-9A-Fa-f][0-9A-Fa-f]|_)', str(section)):
                return False
        return True

    @staticmethod
    def fix_no_section_underscores(parsed):
        for link in parsed.ifilter_wikilinks():
            if '#' not in link.title:
                continue
            title, section = link.title.split('#', 1)
            section = section.replace('_', ' ')
            section = re.sub(r'\.([A-Za-z0-9]{2})',
                             lambda m: chr(int(m.group(1), 16)),
                             section)
            link.title = title + '#' + section

    @staticmethod
    def no_cat_underscores(parsed):
        for link in parsed.ifilter_wikilinks():
            if link.title.startswith('Category:') and '_' in link.title:
                return False
        return True

    @staticmethod
    def fix_no_cat_underscores(parsed):
        StyleGuide.fix_no_link_underscores(parsed)

    @staticmethod
    def cat_at_end(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        links = parsed.filter_wikilinks()
        links = list(l for l in links
                     if not re.match('^[a-z][a-z](-[a-z]+|[a-z])?:',
                                     str(l.title)))
        if not links[-1].title.startswith('Category:'):
            return False #not even the last non-interwikilink is a category link
        nodes = list(n for n in parsed.nodes
                     if not re.match('^[a-z][a-z](-[a-z]+|[a-z])?:',
                                     str(getattr(n, 'title', ''))))
        nodes = list(n for n in nodes if n.strip())
        if not str(getattr(nodes[-1], 'title', '')).startswith('Category:'):
            # by the way, str(nodes[-1].title) can't possibly start with
            # Category: if it isn't a link (str(the builtin method) is
            # <built-in...)
            return False #the last non-interwikilink node isn't a catlink
        return True

    @staticmethod
    def no_capitalized_templates(parsed):
        for template in parsed.ifilter_templates():
            if re.match('^[A-Z][^A-Z]+$', str(template.name)):
                return False
        return True

    @staticmethod
    def fix_no_capitalized_templates(parsed):
        for template in parsed.ifilter_templates():
            if re.match('^[A-Z][^A-Z]+$', str(template.name)):
                template.name = template.name[0].lower() + template.name[1:]

    @staticmethod
    def pipe_at_line_start(parsed):
        for template in parsed.ifilter_templates():
            for param in template.params:
                if param.startswith('\n'):
                    return False
        return True

    @staticmethod
    def nwc_param_text(parsed):
        for template in parsed.ifilter_templates():
            if template.name.lower() in ('note', 'warning', 'caution'):
                if not template.has('1'):
                    return False
        return True

    @staticmethod
    def no_main_underscores(parsed):
        for template in parsed.ifilter_templates():
            if template.name.lower() == 'main':
                if '_' in template.get('1'):
                    return False
        return True

    @staticmethod
    def fix_no_main_underscores(parsed):
        for template in parsed.ifilter_templates():
            if template.name.lower() == 'main':
                template.params[0].value = str(template.params[0].value).replace(
                    '_', ' '
                )

    @staticmethod
    def no_redirect_underscores(parsed):
        if not parsed.upper().startswith('#REDIRECT'):
            return True #it's not a redirect, it passes the test
        return StyleGuide.no_link_underscores(parsed)

    @staticmethod
    def fix_no_redirect_underscores(parsed):
        StyleGuide.fix_no_link_underscores(parsed)

    @staticmethod
    def redirect_category_newline(parsed):
        if not parsed.upper().startswith('#REDIRECT'):
            return True #it's not a redirect, it passes the test
        links = parsed.filter_wikilinks()
        if not parsed.get(parsed.index(links[1]) - 1).endswith('\n'):
            return False
        return True

    @staticmethod
    def no_redir_section_underscores(parsed):
        if not parsed.upper().startswith('#REDIRECT'):
            return True #it's not a redirect, it passes the test
        return StyleGuide.no_section_underscores(parsed)

    @staticmethod
    def fix_no_redir_section_underscores(parsed):
        StyleGuide.fix_no_section_underscores(parsed)

    @staticmethod
    def whitespace_headings(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        for heading in parsed.ifilter_headings():
            if not parsed.get(parsed.index(heading) - 1).endswith('\n\n'):
                return False
        return True

    @staticmethod
    def no_nih_space(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        return not bool(re.search('^; .*', str(parsed), re.M))

    @staticmethod
    def fix_no_nih_space(parsed):
        objs = parsed.filter()
        for i, obj in enumerate(objs): #not ifilter because it modifies in-place
            if getattr(obj, 'tag', 'notdt') == 'dt':
                parsed.replace(objs[i + 1], objs[i + 1].lstrip())

    @staticmethod
    def whitespace_ul(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        if re.search(r'^[\*:]*\*[^ ]', str(parsed), re.M):
            return False
        if re.search(r'^:+\*+', str(parsed), re.M):
            return False
        return True

    @staticmethod
    def whitespace_ol(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        if re.search(r'^[#:]*#[^ ]', str(parsed), re.M):
            return False
        if re.search(r'^:+#+', str(parsed), re.M):
            return False
        return True

    @staticmethod
    def no_indent_space(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        return not bool(re.search(r'^: [^\*#:;]?.*', str(parsed), re.M))

    @staticmethod
    def fix_no_indent_space(parsed):
        objs = parsed.filter()
        for i, obj in enumerate(objs): #not ifilter because it modifies in-place
            if getattr(obj, 'tag', 'notdd') == 'dd':
                parsed.replace(objs[i + 1], objs[i + 1].lstrip())

    @staticmethod
    def ref_punctuation(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        return not bool(re.search(' <ref', str(parsed)))

    @staticmethod
    def no_spaces_inside_tags(parsed):
        for tag in parsed.ifilter_tags():
            if tag.contents is None:
                continue
            if tag.contents.startswith(' ') or tag.contents.endswith(' '):
                return False
        return True

    @staticmethod
    def no_hr_whitespace(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        return '\n\n----\n\n' not in str(parsed)

    @staticmethod
    def no_space_pre(parsed):
        parsed = StyleGuide._remove_ignore(parsed)
        return not bool(re.search('^ .*', str(parsed), re.M))

    @staticmethod
    def no_pre_space(parsed):
        for tag in parsed.ifilter_tags():
            if tag.tag == 'pre' and (tag.contents.startswith('\n')
                                     or tag.contents.endswith('\n')):
                return False
        return True

    @staticmethod
    def fix_no_pre_space(parsed):
        for tag in parsed.ifilter_tags():
            if tag.tag == 'pre':
                tag.contents = tag.contents.strip('\n')
    #pylint: enable=missing-docstring

def runme(name):
    """Check if this section should run."""
    if '--only' not in sys.argv:
        return True
    idx = sys.argv.index('--only')
    return name in sys.argv[idx + 1].split(',')

#login
print('Logging in...')
loginresult = sw.login(USERNAME, PASSWORD)
print('Login result:', loginresult['result'])

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


if runme('depersonifying'):
    limit = int(input('Press Enter to skip de-personifying, or a number '
                      '(then Enter) to do it on that amount of pages: ') or '0')
    if limit: #if limit != 0
        pages = [] #no pages yet
        print(' Requesting random pages...')
        pages = (sw.random(limit=limit, namespace=0)
                 if '--page' not in sys.argv
                 else (sw.page(sys.argv[sys.argv.index('--page') + 1]),))
        print(' Requested random pages.')
        for page in pages: #for every page
            content = page.read()
            exp = re.compile(r'(\s|(?=[ -~])\W)(?=[a-zA-Z\']+)('
                             + CONFIG['words'] + r')((?=[ -~])\W)', re.I)
            if re.search(exp, content): #if there's a match
                content = re.sub(exp, '\\1\u2588\\2\u2588\\3', content) #highlight every instance
                try:
                    content = e.codebox('Modify content below - first and second '
                                        'person are highlighted in \u2588s. Press '
                                        'Cancel or leave blank to cancel.',
                                        'Modify Content of ' + page.title,
                                        content).strip() or None
                except AttributeError:
                    content = None
                if content is not None: #if it's not None
                    content = content.replace('\u2588', '') #remove all highlights
                    print('Edit on page',
                          page.title + ':',
                          submitedit(page,
                                     content,
                                     'Semi-automated edit: de-1st/2nd-personified.'))
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


if runme('references'):
    limit = int(input('Press Enter to skip reference updating, '
                      'or a number (then Enter) to do it on that amount of pages: ') or '0')
    if limit: #if limit != 0
        pages = [] #no pages yet
        print(' Requesting random pages...')
        pages = (sw.random(limit=limit, namespace=0)
                 if '--page' not in sys.argv
                 else (sw.page(sys.argv[sys.argv.index('--page') + 1]),))
        print(' Requested random pages.')
        for page in pages: #for every page
            content = page.read()
            if re.search('<references */>', content, re.I):
                content = re.sub(r'((?!<ref>{}</ref>)(?:<ref>.*?</ref>))'.format(CONFIG['refformat']),
                                 '\u2588\\1\u2588', content) #monster regex to highlight every instance
                try:
                    content = e.codebox('Modify content below - bad references '
                                        'are highlighted in \u2588s. Press Cancel '
                                        'or leave blank to cancel.',
                                        'Modify Content of ' + page.title, content).strip() or None
                except AttributeError:
                    content = None
                if content is not None: #if it's not None
                    content = content.replace('\u2588', '') #remove all highlights
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
        parsedcontents = mwp.parse(rev.content, 0, True)
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

if runme('dates'):
    cms = (sw.category(CONFIG['arbit'][1]).categorymembers()
           if '--page' not in sys.argv
           else (sw.page(sys.argv[sys.argv.index('--page') + 1]),))
    for page in cms: #for every title
        print('Page', page.title)
        content = page.read()
        parsed_content = mwp.parse(content, 0, True)
        #nobots check
        go_on = True
        for umtemplate in parsed_content.ifilter_templates():
            if umtemplate.name.lower() == 'nobots':
                go_on = False
                break
        if not go_on:
            print(' {{NoBots}} in page, skipping.')
            continue
        #add dates! :)
        go_on = False
        for datedtemplate in parsed_content.ifilter_templates():
            if re.search(CONFIG['templates'], str(datedtemplate.name), re.I) \
                    and not datedtemplate.has('date'):
                datedtemplate.add('date', get_date(page, datedtemplate.name))
                go_on = True #at least one template was changed
        if go_on:         #if ^
            print("Edit on page", page.title + ":",
                  submitedit(page, str(parsed_content),
                             'Automated edit: added dates to templates')) #submit the edit!
        else:
            print("Page", page.title, "was not edited.") #no change
        time.sleep(1)

#raise SystemExit #uncomment this to stop here

# This section is the {{bad style}} adding section.
# It asks for user input as to how many pages to check style for,
# and, if the input is a non-zero number:
# 1. gets a list of random pages with length equal to input,
# 2. for every page:
#     1. checks if it has a {{good style}} template. If it does, it stores
#        the style guidelines to ignore in memory, then
#     2. checks if it has any templates that cause the page to be ignored
#        (i.e. {{NoBots}}, {{disambig}}, {{faq}}, etc). If it does, it stops
#        here. If it doesn't,
#     3. for every style guideline in the StyleGuide class (defined above),
#         1. executes that guideline's method.
#         2. If the method returned True, the page does not break
#            that guideline, and it continues
#         3. If it returned False, it does break that guideline. It adds
#            the guideline name to a list stored in memory.
#     4. Then it checks if the list has any members. If it doesn't, it
#        logs that and stops. If it does, it constructs a {{bad style}}
#        template with the guideline names, and inserts it before the
#        first category link, and finally,
#     4. submits the edit.


if runme('style'):
    limit = int(input('Enter a number of pages to check for bad style (default 10): ') or '10')
    print(' Requesting random pages...')
    pages = (sw.random(limit=limit, namespace=0)
             if '--page' not in sys.argv
             else (sw.page(sys.argv[sys.argv.index('--page') + 1]),))
    print(' Requested random pages.')
    for page in pages:
        print('Page', page)
        content = page.read()
        parsed_content = mwp.parse(content)
        ignore = []
        for good_style in parsed_content.ifilter_templates():
            if good_style.name.lower() == CONFIG['arbit'][3].lower():
                ignore = good_style.params
                break
        go_on = True
        for warntemplate in parsed_content.ifilter_templates():
            if warntemplate.name.lower() in (CONFIG['arbit'][2].lower(), 'nobots', 'disambig', 'faq'):
                go_on = False
                break
        if go_on:
            bads = []
            fixed = 0
            for k in StyleGuide.__dict__:
                if k.startswith(('_', 'fix_')):
                    continue
                k = k.replace('_', '-')
                if k not in ignore:
                    passed = getattr(StyleGuide, k.replace('-', '_'),
                                     lambda *_: True)(parsed_content)
                    if not passed:
                        if '--style-fix' in sys.argv and hasattr(
                            StyleGuide, 'fix_' + k.replace('-', '_')
                        ):
                            getattr(
                                StyleGuide,
                                'fix_' + k.replace('-', '_')
                            )(parsed_content)
                            fixed += 1
                            print(' Fixed flaw:', k)
                        else:
                            print(' Found flaw:', k)
                            bads.append(k)
            if bads or fixed:
                insert = '{{' + CONFIG['arbit'][2] + '\n|' + '\n|'.join(bads) \
                         + '\n|date={{subst:CURRENTMONTHNAME}} {{subst:CURRENTYEAR}}\n}}\n'
                wikilinks = parsed_content.filter_wikilinks()
                wikilinks = list(filter(
                    lambda link: re.match(r'(Category|[a-z][a-z]([a-z]|-[a-z]+)?):.*',
                                          str(link.title), re.I), wikilinks
                ))
                try:
                    parsed_content.insert_before(wikilinks[0], insert)
                except (ValueError, IndexError):
                    parsed_content.append(insert)
                content = str(parsed_content)
                print('Edit on page', page.title + ':', submitedit(
                    page,
                    content,
                    'Automated edit: added {} ({} guidelines broken){}'.format(
                        '{{[[Template:' + CONFIG['arbit'][2] + '|' + CONFIG['arbit'][2] + ']]}}',
                        len(bads),
                        ' ({} fixed)'.format(fixed) if fixed > 0 else ''
                    )
                ))
            else:
                print('Page', page, 'was not edited - no broken guidelines found.')
        else:
            print(' {{NoBots}}, {{disambig}}, {{faq}}, or {{bad style}} in page, skipping.')

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


if runme('cn'):
    if '--nocache' not in sys.argv:
        try:
            with open('inaccuratecache.pickle', 'rb') as cache:
                cache = pickle.load(cache) #load cache
        except IOError: #if there isn't any cache
            cache = [] #make an empty cache
    else:
        cache = [] #no cache, reset it

    if '--page' not in sys.argv:
        eis = [] #empty list for now
        eis.extend([ei.title for ei in sw.template('citation needed').transclusions(namespace='0|4|12')])
        eis.extend([ei.title for ei in sw.template('cn').transclusions(namespace='0|4|12')])
        for ei in sw.template('inaccurate').transclusions(): #for every embeddedin
            if ei.title in eis:
                eis.remove(ei.title)
    else:
        eis = (sys.argv[sys.argv.index('--page') + 1],)
    try:
        for page in eis: #for every page in embeddedins
            try:
                if page in cache:
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
                    parsed_content = mwp.parse(content, 0, True)
                    go_on = True
                    for warntemplate in parsed_content.ifilter_templates():
                        if warntemplate.name.lower() == 'nobots':
                            go_on = False
                            break
                    if not go_on:
                        print(' {{NoBots}} in page, skipping.')
                        continue
                    go_on = False
                    #all pages with dateless templates have had their dates added now
                    detected = 0
                    inaccurate_already = False
                    for cntemplate in parsed_content.ifilter_templates():
                        if cntemplate.name.lower() in ('cn', 'citation needed'):
                            detected += 1
                        elif cntemplate.name.lower() == 'inaccurate':
                            inaccurate_already = True
                    if detected > CONFIG['cncount'] and not inaccurate_already:
                        content = '{{inaccurate|date={{subst:CURRENTMONTHNAME}} ' \
                                  '{{subst:CURRENTYEAR}}}}\n' + content
                        summary = 'Automated edit: added {{inaccurate}} (' \
                                  + str(detected) + ' {{citation needed}}s)'
                        print('', detected, '{{citation neeeded}}s') #log how many cns
                        go_on = True
                    if go_on: #if something happened
                        print("Edit on page", page + ":", submitedit(pageobj, content, summary))
                    else:
                        if not detected > CONFIG['cncount']:
                            print(" Not enough {{citation needed}}s")
                        else:
                            print(" {{inaccurate}} already on page")
                        print("Page", page, "was not edited.") #log not editing
                    time.sleep(5) #sleep 5 to avoid throttling
            except mwc.wiki.requests.ConnectionError: #if we were throttled anyway
                print('Throttled, sleeping for 30 seconds...') #log that
                if page in cache:
                    cache.remove(page)
                time.sleep(30) #sleep half a minute
    finally: #no matter what
        with open('inaccuratecache.pickle', 'wb') as cach:
            pickle.dump(cache, cach, -1) #dump the cache
