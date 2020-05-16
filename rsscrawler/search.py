# -*- coding: utf-8 -*-
# RSScrawler
# Projekt von https://github.com/rix1337

import json
import logging
import re

import cloudscraper
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from rsscrawler.fakefeed import fx_content_to_soup
from rsscrawler.fakefeed import fx_download_links
from rsscrawler.fakefeed import fx_post_title
from rsscrawler.fakefeed import fx_search_results
from rsscrawler.fakefeed import hs_search_results
from rsscrawler.fakefeed import nk_search_results
from rsscrawler.myjd import myjd_download
from rsscrawler.notifiers import notify
from rsscrawler.rsscommon import check_hoster
from rsscrawler.rsscommon import decode_base64
from rsscrawler.rsscommon import encode_base64
from rsscrawler.rsscommon import is_retail
from rsscrawler.rsscommon import sanitize
from rsscrawler.rssconfig import RssConfig
from rsscrawler.rssdb import ListDb
from rsscrawler.rssdb import RssDb
from rsscrawler.sites.bl import BL
from rsscrawler.url import check_is_site
from rsscrawler.url import get_url
from rsscrawler.url import get_urls_async
from rsscrawler.url import post_url

logger = logging.getLogger('rsscrawler')


def get(title, configfile, dbfile):
    specific_season = re.match(r'^(.*);(s\d{1,3})$', title.lower())
    specific_episode = re.match(r'^(.*);(s\d{1,3}e\d{1,3})$', title.lower())
    if specific_season:
        split = title.split(";")
        title = split[0]
        special = split[1].upper()
    elif specific_episode:
        split = title.split(";")
        title = split[0]
        special = split[1].upper()
    else:
        special = None

    query = title.replace(" ", "+")
    mb_query = sanitize(title).replace(" ", "+")
    if special:
        bl_query = mb_query + "+" + special
    else:
        bl_query = mb_query

    unrated = []

    config = RssConfig('MB', configfile)

    quality = config.get('quality')
    if "480p" not in quality:
        search_quality = "+" + quality
    else:
        search_quality = ""

    mb_search = decode_base64(
        'aHR0cDovL21vdmllLWJsb2cuc3g=') + '/search/' + bl_query + search_quality + '/feed/rss2/'
    hw_search = decode_base64('aHR0cDovL2hkLXdvcmxkLm9yZw==') + '/search/' + bl_query + search_quality + '/feed/rss2/'
    hs_search = decode_base64('aHR0cHM6Ly9oZC1zb3VyY2UudG8vc2VhcmNoLw==') + bl_query + search_quality + '/feed'
    fx_search = decode_base64('aHR0cHM6Ly9mdW54ZC5zaXRl') + '/search/' + bl_query + search_quality + '/feed/'

    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'mobile': False})
    async_results = get_urls_async([mb_search, hw_search, hs_search, fx_search], configfile, dbfile, scraper)
    scraper = async_results[1]
    async_results = async_results[0]

    mb_results = []
    hw_results = []
    hs_results = []
    fx_results = []

    for res in async_results:
        if decode_base64('bW92aWUtYmxvZy5zeA==') in res:
            mb_results = re.findall(r'<title>(.*?)<\/title>\n.*?<link>(.*?)<\/link>', res)
        elif decode_base64('aGQtd29ybGQub3Jn') in res:
            hw_results = re.findall(r'<title>(.*?)<\/title>\n.*?<link>(.*?)<\/link>', res)
        elif decode_base64('aGQtc291cmNlLnRv') in res:
            hs_results = hs_search_results(res)
        elif decode_base64('ZnVueGQuc2l0ZQ==') in res:
            fx_results = fx_search_results(fx_content_to_soup(res))

    nk_base_url = decode_base64('aHR0cHM6Ly9uaW1hNGsub3JnLw==')
    nk_search = post_url(nk_base_url + "search", configfile, dbfile,
                         data={'search': bl_query.replace("+", " ") + " " + quality})
    nk_results = nk_search_results(nk_search, nk_base_url)

    password = decode_base64("bW92aWUtYmxvZy5vcmc=")
    for result in mb_results:
        if "480p" in quality:
            if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[0].lower() or "2160p" in \
                    result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                0].lower() or "complete.uhd.bluray" in result[0].lower():
                continue
        if not result[0].endswith("-MB") and not result[0].endswith(".MB"):
            unrated.append(
                [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (MB)"])

    password = decode_base64("aGQtd29ybGQub3Jn")
    for result in hw_results:
        if "480p" in quality:
            if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[0].lower() or "2160p" in \
                    result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                0].lower() or "complete.uhd.bluray" in result[0].lower():
                continue
        unrated.append(
            [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (HW)"])

    password = decode_base64("aGQtc291cmNlLnRv")
    for result in hs_results:
        if "480p" in quality:
            if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[0].lower() or "2160p" in \
                    result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                0].lower() or "complete.uhd.bluray" in result[0].lower():
                continue
        unrated.append(
            [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (HS)"])

    password = decode_base64("ZnVueGQ=")
    for result in fx_results:
        if "480p" in quality:
            if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[0].lower() or "2160p" in \
                    result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                0].lower() or "complete.uhd.bluray" in result[0].lower():
                continue
        unrated.append(
            [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (FX)"])

    password = decode_base64("TklNQTRL")
    for result in nk_results:
        if "480p" in quality:
            if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[0].lower() or "2160p" in \
                    result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                0].lower() or "complete.uhd.bluray" in result[0].lower():
                continue
        unrated.append(
            [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (NK)"])

    if config.get("crawl3d"):
        mb_search = decode_base64(
            'aHR0cDovL21vdmllLWJsb2cuc3g=') + '/search/' + bl_query + search_quality + "+3D/feed/rss2/"
        hw_search = decode_base64(
            'aHR0cDovL2hkLXdvcmxkLm9yZw==') + '/search/' + bl_query + search_quality + "+3D/feed/rss2/"
        hs_search = decode_base64('aHR0cHM6Ly9oZC1zb3VyY2UudG8vc2VhcmNoLw==') + bl_query + search_quality + '+3D/feed'
        fx_search = decode_base64('aHR0cHM6Ly9mdW54ZC5zaXRl') + '/search/' + bl_query + search_quality + "+3D/feed/"

        async_results = get_urls_async([mb_search, hw_search, hs_search, fx_search], configfile, dbfile, scraper)
        async_results = async_results[0]

        mb_results = []
        hw_results = []
        hs_results = []
        fx_results = []

        for res in async_results:
            if decode_base64('bW92aWUtYmxvZy5zeA==') in res:
                mb_results = re.findall(r'<title>(.*?)<\/title>\n.*?<link>(.*?)<\/link>', res)
            elif decode_base64('aGQtd29ybGQub3Jn') in res:
                hw_results = re.findall(r'<title>(.*?)<\/title>\n.*?<link>(.*?)<\/link>', res)
            elif decode_base64('aGQtc291cmNlLnRv') in res:
                hs_results = hs_search_results(res)
            elif decode_base64('ZnVueGQuc2l0ZQ==') in res:
                fx_results = re.findall(r'<title>(.*?)<\/title>\n.*?<link>(.*?)<\/link>', res)

        nk_base_url = decode_base64('aHR0cHM6Ly9uaW1hNGsub3JnLw==')
        nk_search = post_url(nk_base_url + "search", configfile, dbfile,
                             data={'search': bl_query.replace("+", " ") + " " + quality + "3D"})
        nk_results = nk_search_results(nk_search, nk_base_url)

        password = decode_base64("bW92aWUtYmxvZy5vcmc=")
        for result in mb_results:
            if not result[1].endswith("-MB") and not result[1].endswith(".MB"):
                unrated.append(
                    [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (3D-MB)"])

        password = decode_base64("aGQtd29ybGQub3Jn")
        for result in hw_results:
            unrated.append(
                [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (3D-HW)"])

        password = decode_base64("aGQtc291cmNlLnRv")
        for result in hs_results:
            unrated.append(
                [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (3D-HS)"])

        password = decode_base64("ZnVueGQ=")
        for result in fx_results:
            unrated.append(
                [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (3D-FX)"])

        password = decode_base64("TklNQTRL")
        for result in nk_results:
            unrated.append(
                [rate(result[0], configfile), encode_base64(result[1] + ";" + password), result[0] + " (3D-NK)"])

    rated = sorted(unrated, reverse=True)

    results = {}
    i = 0

    for result in rated:
        res = {"payload": result[1], "title": result[2]}
        if len(rated) > 9 >= i:
            results["result0" + str(i)] = res
        elif len(rated) > 99 and i <= 9:
            results["result00" + str(i)] = res
        elif len(rated) > 99 >= i:
            results["result0" + str(i)] = res
        else:
            results["result" + str(i)] = res
        i += 1
    mb_final = results

    sj_search = get_url(decode_base64("aHR0cHM6Ly9zZXJpZW5qdW5raWVzLm9yZy9zZXJpZS9zZWFyY2g/cT0=") + query, configfile,
                        dbfile, scraper)
    try:
        sj_results = BeautifulSoup(sj_search, 'lxml').findAll("a", href=re.compile("/serie"))
    except:
        sj_results = []

    if special:
        append = " (" + special + ")"
    else:
        append = ""
    i = 0
    results = {}
    for result in sj_results:
        r_title = result.text
        r_rating = fuzz.ratio(title.lower(), r_title)
        if r_rating > 60:
            res = {"payload": encode_base64(result['href'] + ";" + r_title + ";" + str(special)),
                   "title": r_title + append}
            if len(sj_results) > 9 >= i:
                results["result0" + str(i)] = res
            elif len(sj_results) > 99 and i <= 9:
                results["result00" + str(i)] = res
            elif len(sj_results) > 99 >= i:
                results["result0" + str(i)] = res
            else:
                results["result" + str(i)] = res
            i += 1
    sj_final = results
    return mb_final, sj_final


def rate(title, configfile):
    score = 0
    if ".bluray." in title.lower():
        score += 7
    if ".bd." in title.lower():
        score += 7
    if ".bdrip." in title.lower():
        score += 7
    if re.match(r'.*\-(4SJ|TVS)', title):
        score += 4
    if ".dl." in title.lower():
        score += 2
    if re.match(r'.*\.(DTS|DD\+*51|DD\+*71|AC3\.5\.*1)\..*', title):
        score += 2
    if re.match(r'.*\.(720|1080|2160)p\..*', title):
        score += 2
    if ".ml." in title.lower():
        score += 1
    if ".dd20." in title.lower():
        score += 1
    if "dubbed." in title.lower():
        score -= 1
    if ".synced." in title.lower():
        score -= 1
    if ".ac3d." in title.lower():
        score -= 1
    if ".dtsd." in title.lower():
        score -= 1
    if ".hdtv." in title.lower():
        score -= 1
    if ".dtv" in title.lower():
        score -= 1
    if ".pdtv" in title.lower():
        score -= 1
    if "tvrip." in title.lower():
        score -= 1
    if ".subbed." in title.lower():
        score -= 2
    if ".xvid." in title.lower():
        score -= 2
    if ".pal." in title.lower():
        score -= 10
    if "dvd9" in title.lower():
        score -= 10
    try:
        config = RssConfig('SJ', configfile)
        reject = config.get("rejectlist").replace(",", "|").lower() if len(
            config.get("rejectlist")) > 0 else r"^unmatchable$"
    except TypeError:
        reject = r"^unmatchable$"
    r = re.search(reject, title.lower())
    if r:
        score -= 5
    if ".subpack." in title.lower():
        score -= 10
    return score


def best_result_bl(title, configfile, dbfile):
    title = sanitize(title)
    try:
        # ToDo: Only query blogs with this
        mb_results = get(title, configfile, dbfile)[0]
    except:
        return False
    conf = RssConfig('MB', configfile)
    ignore = "|".join([r"\.%s(\.|-)" % p for p in conf.get('ignore').lower().split(',')]) if conf.get(
        'ignore') else r"^unmatchable$"
    results = []
    i = len(mb_results)
    i_len = i

    j = 0
    while i > 0:
        try:
            if i_len > 9 >= j:
                q = "result0" + str(j)
            elif i_len > 99 and j <= 9:
                q = "result00" + str(j)
            elif i_len > 99 >= j:
                q = "result0" + str(j)
            else:
                q = "result" + str(j)
            results.append(mb_results.get(q).get('title'))
        except:
            pass
        i -= 1
        j += 1
    best_score = 0
    best_match = 0
    for r in results:
        r = re.sub(r'\(.*\)', '', r).strip()
        r = r.replace(".", " ")
        without_year = re.sub(
            r'(|.UNRATED.*|.Unrated.*|.Uncut.*|.UNCUT.*)(|.Directors.Cut.*|.Final.Cut.*|.DC.*|.EXTENDED.*|.Extended.*|.Theatrical.*|.THEATRICAL.*)(|.3D.*|.3D.HSBS.*|.3D.HOU.*|.HSBS.*|.HOU.*)(|.)\d{4}(|.)(|.UNRATED.*|.Unrated.*|.Uncut.*|.UNCUT.*)(|.Directors.Cut.*|.Final.Cut.*|.DC.*|.EXTENDED.*|.Extended.*|.Theatrical.*|.THEATRICAL.*)(|.3D.*|.3D.HSBS.*|.3D.HOU.*|.HSBS.*|.HOU.*).(German|GERMAN)(|.AC3|.DTS|.DTS-HD)(|.DL)(|.AC3|.DTS).(2160|1080|720)p.(UHD.|Ultra.HD.|)(HDDVD|BluRay)(|.HDR)(|.AVC|.AVC.REMUX|.x264|.x265)(|.REPACK|.RERiP|.REAL.RERiP)-.*',
            "", r)
        with_year = re.sub(
            r'(|.UNRATED.*|.Unrated.*|.Uncut.*|.UNCUT.*)(|.Directors.Cut.*|.Final.Cut.*|.DC.*|.EXTENDED.*|.Extended.*|.Theatrical.*|.THEATRICAL.*)(|.3D.*|.3D.HSBS.*|.3D.HOU.*|.HSBS.*|.HOU.*).(German|GERMAN)(|.AC3|.DTS|.DTS-HD)(|.DL)(|.AC3|.DTS|.DTS-HD).(2160|1080|720)p.(UHD.|Ultra.HD.|)(HDDVD|BluRay)(|.HDR)(|.AVC|.AVC.REMUX|.x264|.x265)(|.REPACK|.RERiP|.REAL.RERiP)-.*',
            "", r)
        score = fuzz.ratio(title, without_year) + fuzz.ratio(title, with_year)
        if score > best_score:
            best_score = score
            best_match = i
        i += 1
    best_match = 'result' + str(best_match)
    best_result = mb_results.get(best_match)
    if best_result:
        best_title = best_result.get('title')
        best_link = best_result.get('link')
        if re.search(ignore, best_title.lower()):
            best_title = None
        quality = conf.get('quality')
        if "480p" not in quality and best_title and not re.search(
                r'^' + title.replace(" ", ".") + r'.(\d{4}|German|\d{3,4}p).*',
                best_title):
            best_title = None
        elif "480p" in quality and best_title and re.search(
                r'^' + title.replace(" ", ".") + r'.(\d{4}|German|\d{3,4}p).*',
                best_title):
            best_title = None
    else:
        best_title = None
    if not best_title:
        logger.debug(u'Kein Treffer für die Suche nach ' + title + '! Suchliste ergänzt.')
        liste = "MB_Filme"
        cont = ListDb(dbfile, liste).retrieve()
        if not cont:
            cont = ""
        if title not in cont:
            ListDb(dbfile, liste).store(title)
        return False
    if not is_retail(best_title, 1, dbfile):
        logger.debug(u'Kein Retail-Release für die Suche nach ' + title + ' gefunden! Suchliste ergänzt.')
        liste = "MB_Filme"
        cont = ListDb(dbfile, liste).retrieve()
        if not cont:
            cont = ""
        if title not in cont:
            ListDb(dbfile, liste).store(title)
        return best_link
    else:
        logger.debug('Bester Treffer fuer die Suche nach ' + title + ' ist ' + best_title)
        return best_link


def best_result_sj(title, configfile, dbfile):
    try:
        # ToDo: only query SJ here
        sj_results = get(title, configfile, dbfile)[1]
    except:
        return False
    results = []
    i = len(sj_results)
    i_len = i

    j = 0
    while i > 0:
        try:
            if i_len > 9 >= j:
                q = "result0" + str(j)
            elif i_len > 99 and j <= 9:
                q = "result00" + str(j)
            elif i_len > 99 >= j:
                q = "result0" + str(j)
            else:
                q = "result" + str(j)
            results.append(sj_results.get(q).get('title'))
        except:
            pass
        i -= 1
        j += 1
    best_score = 0
    best_match = 0
    for r in results:
        score = fuzz.ratio(title, r)
        if score > best_score:
            best_score = score
            best_match = i
        i += 1
    best_match = 'result' + str(best_match)
    try:
        best_title = sj_results.get(best_match).get('title')
        best_id = sj_results.get(best_match).get('id')
    except:
        logger.debug('Kein Treffer fuer die Suche nach ' + title + '! Suchliste ergänzt.')
        listen = ["SJ_Serien", "MB_Staffeln"]
        for liste in listen:
            cont = ListDb(dbfile, liste).retrieve()
            if not cont:
                cont = ""
            if title not in cont:
                ListDb(dbfile, liste).store(title)
            return
    logger.debug('Bester Treffer fuer die Suche nach ' + title + ' ist ' + best_title)
    return best_id


def download_bl(payload, device, configfile, dbfile):
    payload = decode_base64(payload).split(";")
    link = payload[0]
    password = payload[1]
    url = get_url(link, configfile, dbfile)
    if not url or "NinjaFirewall 429" in url:
        return False

    config = RssConfig('MB', configfile)
    db = RssDb(dbfile, 'rsscrawler')
    soup = BeautifulSoup(url, 'lxml')

    site = check_is_site(link)
    if not site:
        return False
    else:
        if "MB" in site:
            key = soup.find("span", {"class": "fn"}).text
            hosters = soup.find_all("a", href=re.compile("filecrypt"))
            url_hosters = []
            for hoster in hosters:
                dl = hoster["href"]
                hoster = hoster.text
                url_hosters.append([dl, hoster])
        elif "HW" in site:
            key = re.findall(r'Permanent Link: (.*?)"', str(soup)).pop()
            hosters = soup.find_all("a", href=re.compile("filecrypt"))
            url_hosters = []
            for hoster in hosters:
                dl = hoster["href"]
                hoster = hoster.text
                url_hosters.append([dl, hoster])
        elif "HS" in site:
            download = soup.find("div", {"class": "entry-content"})
            key = soup.find("h2", {"class": "entry-title"}).text
            url_hosters = re.findall(r'href="([^"\'>]*)".+?(.+?)<', str(download))
        elif "FX" in site:
            key = fx_post_title(url)
        elif "NK" in site:
            key = soup.find("span", {"class": "subtitle"}).text
            url_hosters = []
            base_url = decode_base64('aHR0cHM6Ly9uaW1hNGsub3JnLw==')
            hosters = soup.find_all("a", href=re.compile("/go/"))
            for hoster in hosters:
                url_hosters.append([base_url + hoster["href"], hoster.text])
        else:
            return False

        links = {}
        if "MB" in site or "HW" in site or "HS" in site or "NK" in site:
            for url_hoster in reversed(url_hosters):
                try:
                    if not decode_base64("bW92aWUtYmxvZy4=") in url_hoster[0] and "https://goo.gl/" not in url_hoster[
                        0]:
                        link_hoster = url_hoster[1].lower().replace('target="_blank">', '').replace(" ", "-")
                        if check_hoster(link_hoster, configfile):
                            links[link_hoster] = url_hoster[0]
                except:
                    pass
            if config.get("hoster_fallback") and not links:
                for url_hoster in reversed(url_hosters):
                    if not decode_base64("bW92aWUtYmxvZy4=") in url_hoster[0] and "https://goo.gl/" not in url_hoster[
                        0]:
                        link_hoster = url_hoster[1].lower().replace('target="_blank">', '').replace(" ", "-")
                        links[link_hoster] = url_hoster[0]
            download_links = list(links.values())
        elif "FX" in site:
            download_links = fx_download_links(url, key)

        englisch = False
        if "*englisch" in key.lower() or "*english" in key.lower():
            key = key.replace(
                '*ENGLISCH', '').replace("*Englisch", "").replace("*ENGLISH", "").replace("*English",
                                                                                          "").replace(
                "*", "")
            englisch = True

        staffel = re.search(r"s\d{1,2}(-s\d{1,2}|-\d{1,2}|\.)", key.lower())

        if config.get('enforcedl') and '.dl.' not in key.lower():
            fail = False
            get_imdb_url = url
            key_regex = r'<title>' + \
                        re.escape(
                            key) + r'.*?<\/title>\n.*?<link>(?:(?:.*?\n){1,25}).*?[mM][kK][vV].*?(?:|href=.?http(?:|s):\/\/(?:|www\.)imdb\.com\/title\/(tt[0-9]{7,9}).*?)[iI][mM][dD][bB].*?(?!\d(?:\.|\,)\d)(?:.|.*?)<\/a>'
            imdb_id = re.findall(key_regex, get_imdb_url)
            if len(imdb_id) > 0:
                if not imdb_id[0]:
                    fail = True
                else:
                    imdb_id = imdb_id[0]
            else:
                fail = True
            if fail:
                search_title = re.findall(
                    r"(.*?)(?:\.(?:(?:19|20)\d{2})|\.German|\.\d{3,4}p|\.S(?:\d{1,3})\.)", key)[0].replace(".", "+")
                search_url = "http://www.imdb.com/find?q=" + search_title
                search_page = get_url(search_url, configfile, dbfile)
                search_results = re.findall(
                    r'<td class="result_text"> <a href="\/title\/(tt[0-9]{7,9})\/\?ref_=fn_al_tt_\d" >(.*?)<\/a>.*? \((\d{4})\)..(.{9})',
                    search_page)
                total_results = len(search_results)
                if staffel:
                    try:
                        imdb_id = search_results[0][0]
                    except:
                        imdb_id = False
                else:
                    no_series = False
                    while total_results > 0:
                        attempt = 0
                        for result in search_results:
                            if result[3] == "TV Series":
                                no_series = False
                                total_results -= 1
                                attempt += 1
                            else:
                                no_series = True
                                imdb_id = search_results[attempt][0]
                                total_results = 0
                                break
                    if no_series is False:
                        logger.debug(
                            "%s - Keine passende Film-IMDB-Seite gefunden" % key)

            if staffel:
                filename = 'MB_Staffeln'
            else:
                filename = 'MB_Filme'

            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'mobile': False})
            bl = BL(configfile, dbfile, device, logging, scraper, filename=filename)

            if not imdb_id:
                if not bl.dual_download(key, password):
                    logger.debug(
                        "%s - Kein zweisprachiges Release gefunden." % key)
            else:
                if isinstance(imdb_id, list):
                    imdb_id = imdb_id.pop()
                imdb_url = "http://www.imdb.com/title/" + imdb_id
                details = get_url(imdb_url, configfile, dbfile)
                if not details:
                    logger.debug("%s - Originalsprache nicht ermittelbar" % key)
                original_language = re.findall(
                    r"Language:<\/h4>\n.*?\n.*?url'>(.*?)<\/a>", details)
                if original_language:
                    original_language = original_language[0]
                if original_language == "German":
                    logger.debug(
                        "%s - Originalsprache ist Deutsch. Breche Suche nach zweisprachigem Release ab!" % key)
                else:
                    if not bl.dual_download(key, password) and not englisch:
                        logger.debug(
                            "%s - Kein zweisprachiges Release gefunden!" % key)

        if download_links:
            if staffel:
                if myjd_download(configfile, dbfile, device, key, "RSScrawler", download_links, password):
                    db.store(
                        key.replace(".COMPLETE", "").replace(".Complete", ""),
                        'notdl' if config.get(
                            'enforcedl') and '.dl.' not in key.lower() else 'added'
                    )
                    log_entry = '[Suche/Staffel] - ' + key.replace(".COMPLETE", "").replace(".Complete",
                                                                                            "") + ' - [' + site + ']'
                    logger.info(log_entry)
                    notify([log_entry], configfile)
                    return True
            elif '.3d.' in key.lower():
                retail = False
                if config.get('cutoff') and '.COMPLETE.' not in key.lower():
                    if config.get('enforcedl'):
                        if is_retail(key, '2', dbfile):
                            retail = True
                if myjd_download(configfile, dbfile, device, key, "RSScrawler/3Dcrawler", download_links, password):
                    db.store(
                        key,
                        'notdl' if config.get(
                            'enforcedl') and '.dl.' not in key.lower() else 'added'
                    )
                    log_entry = '[Suche/Film' + (
                        '/Retail' if retail else "") + '/3D] - ' + key + ' - [' + site + ']'
                    logger.info(log_entry)
                    notify([log_entry], configfile)
                    return True
            else:
                retail = False
                if config.get('cutoff') and '.COMPLETE.' not in key.lower():
                    if config.get('enforcedl'):
                        if is_retail(key, '1', dbfile):
                            retail = True
                    else:
                        if is_retail(key, '0', dbfile):
                            retail = True
                if myjd_download(configfile, dbfile, device, key, "RSScrawler", download_links, password):
                    db.store(
                        key,
                        'notdl' if config.get(
                            'enforcedl') and '.dl.' not in key.lower() else 'added'
                    )
                    log_entry = '[Suche/Film' + ('/Englisch' if englisch and not retail else '') + (
                        '/Englisch/Retail' if englisch and retail else '') + (
                                    '/Retail' if not englisch and retail else '') + '] - ' + key + ' - [' + site + ']'
                    logger.info(log_entry)
                    notify([log_entry], configfile)
                    return True
        else:
            return False


def download_sj(payload, device, configfile, dbfile):
    payload = decode_base64(payload).split(";")
    href = payload[0]
    title = payload[1]
    special = payload[2].strip().replace("None", "")

    series_url = get_url(decode_base64("aHR0cHM6Ly9zZXJpZW5qdW5raWVzLm9yZw==") + href, configfile, dbfile)
    series_id = BeautifulSoup(series_url, 'lxml').find("div", {"data-mediaid": True})['data-mediaid']

    api_url = decode_base64('aHR0cHM6Ly9zZXJpZW5qdW5raWVzLm9yZw==') + '/api/media/' + series_id + '/releases'
    releases = get_url(api_url, configfile, dbfile)

    seasons = json.loads(releases)

    listen = ["SJ_Serien", "MB_Staffeln"]
    for liste in listen:
        cont = ListDb(dbfile, liste).retrieve()
        list_title = sanitize(title)
        if not cont:
            cont = ""
        if not list_title in cont:
            ListDb(dbfile, liste).store(list_title)

    config = RssConfig('SJ', configfile)
    english_ok = RssConfig('RSScrawler', configfile).get("english")
    quality = config.get('quality')

    result_seasons = {}
    result_episodes = {}

    for season in seasons:
        releases = seasons[season]
        for release in releases['items']:
            name = release['name']
            hosters = release['hoster']
            try:
                valid = bool(release['resolution'] == quality)
            except:
                valid = re.match(re.compile(r'.*' + quality + r'.*'), name)
            if valid and special:
                valid = bool("." + special.lower() + "." in name.lower())
            if valid and not english_ok:
                valid = bool(".german." in name.lower())
            if valid:
                valid = False
                for hoster in hosters:
                    if check_hoster(hoster, configfile) or config.get("hoster_fallback"):
                        valid = True
            if valid:
                try:
                    ep = release['episode']
                    if ep:
                        existing = result_episodes.get(season)
                        if existing:
                            for e in existing:
                                dont = False
                                if e == ep:
                                    if rate(name, configfile) < rate(existing[e][0], configfile):
                                        dont = True
                            if not dont:
                                existing.update({ep: [name, hosters]})
                        else:
                            existing = {ep: [name, hosters]}
                        result_episodes.update({season: existing})
                        continue
                except:
                    pass
                # ToDo check if season already exists and replace if its rated worse
                result_seasons.update({season: [name, hosters]})

        try:
            if result_seasons[season] and result_episodes[season]:
                del result_episodes[season]
        except:
            pass

        try:
            if result_seasons[season] or result_episodes[season]:
                logger.debug(u"Websuche erfolgreich für " + title + " - " + season)
        except:
            for release in releases['items']:
                name = release['name']
                hosters = release['hoster']
                valid = True
                if valid and special:
                    valid = bool("." + special.lower() + "." in name.lower())
                if valid and not english_ok:
                    valid = bool(".german." in name.lower())
                if valid:
                    valid = False
                    for hoster in hosters:
                        if check_hoster(hoster, configfile) or config.get("hoster_fallback"):
                            valid = True
                if valid:
                    try:
                        ep = release['episode']
                        if ep:
                            existing = result_episodes.get(season)
                            if existing:
                                for e in existing:
                                    dont = False
                                    if e == ep:
                                        if rate(name, configfile) < rate(existing[e][0], configfile):
                                            dont = True
                                if not dont:
                                    existing.update({ep: [name, hosters]})
                            else:
                                existing = {ep: [name, hosters]}
                            result_episodes.update({season: existing})
                            continue
                    except:
                        pass
                    # ToDo check if season already exists and replace if its rated worse
                    result_seasons.update({season: [name, hosters]})

            try:
                if result_seasons[season] and result_episodes[season]:
                    del result_episodes[season]
            except:
                pass

    # ToDo append every remaining release to the matches
    matches = []

    notify_array = []
    for match in matches:
        title = match[0]
        link = match[1]
        db = RssDb(dbfile, 'rsscrawler')
        if myjd_download(configfile, dbfile, device, title, "RSScrawler", link,
                         decode_base64("c2VyaWVuanVua2llcy5vcmc=")):
            db.store(title, 'added')
            log_entry = '[Suche/Serie] - ' + title + ' - [SJ]'
            logger.info(log_entry)
            notify_array.append(log_entry)

    notify(notify_array, configfile)

    if not matches:
        return False
    return True


def best_links(pakete):
    to_return = []
    highest_score = sorted(pakete, reverse=True)[0][0]
    for p in pakete:
        if p[0] == highest_score:
            to_return.append([p[1], p[2]])
    return to_return
