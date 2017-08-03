#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys

import requests


def progress(curr, total):
    percentage = min(curr * 100 // total, 100)
    curr = min(curr, total)
    sys.stdout.write('\r')
    screen_width, screen_height = os.get_terminal_size()
    progress_width = min(screen_width - len(str(curr) + str(total)) - 10, 20)
    sys.stdout.write(
        "[%-*s] %d%% %d/%d" % (progress_width, '=' * (progress_width * percentage // 100), percentage, curr, total))
    if percentage == 100:
        sys.stdout.write('\n')
    sys.stdout.flush()


class Spider:
    TYPE_VIDEO = 'VIDEO'
    TYPE_PHOTO = 'PHOTO'
    TYPE_BOTH = 'BOTH'
    BASE_URL = 'https://www.instagram.com'
    QUERY_URL = BASE_URL + '/graphql/query/'
    SCRIPT_URL = BASE_URL + "/static/bundles/en_US_Commons.js/"
    HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"}

    class Downloader:
        def __init__(self, spider):
            self.session = requests.Session()
            self.spider = spider

        def download(self, account, code):
            """download content of the post given by the code"""

            url = Spider.BASE_URL + "/p/%s/?taken-by=%s" % (code, account)
            r = self.session.get(url)
            content_match = re.search(r"<script.*?>\s*?window._sharedData\s*?=\s*?({.*}).*?</script>", r.text,
                                      re.MULTILINE)
            data = json.loads(content_match.group(1))
            media = data['entry_data']['PostPage'][0]['graphql']['shortcode_media']
            download_urls = []
            if media['__typename'] == 'GraphVideo':  # video
                download_urls.append(media["video_url"])
            if media['__typename'] == 'GraphImage':  # image
                download_urls.append(media["display_url"])
            if media['__typename'] == 'GraphSidecar':  # slide
                nodes = media['edge_sidecar_to_children']['edges']
                for node in nodes:
                    node = node['node']
                    if node['is_video']:
                        download_urls.append(node['video_url'])
                    else:
                        download_urls.append(node['display_url'])

            if not os.path.isdir(account):
                os.mkdir(account)
            for url in download_urls:
                filename = account + '/' + url.split('/')[-1]
                temp_name = filename + '.tmp'
                if os.path.isfile(filename):
                    if self.spider.auto_stop:
                        print('file', filename, "already exists, exiting......")
                        sys.exit()
                    print('file', filename, "already exists, skipping")
                else:
                    print('downloading %s:' % filename)
                    r = self.session.get(url, stream=True)
                    content_length = int(r.headers['content-length'])
                    curr = 0
                    with open(temp_name, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            f.write(chunk)
                            curr += 1024
                            progress(curr, content_length)
                    os.rename(temp_name, filename)
                    self.spider.item_count += 1

        def close(self):
            self.session.close()

    def __init__(self, username, max_page_count, download_type, after,auto_stop):
        self.session = requests.Session()
        self.item_count = 0
        self.max_page = max_page_count
        self.username = username
        self.download_type = download_type
        self.auto_stop = auto_stop
        self.page_count = 0
        self.target_url = self.BASE_URL + '/' + username
        self.downloader = self.Downloader(self)
        self.end_cursor = None
        if after is not None:
            self.end_cursor = after['end_cursor']
            self.page_count = after['last_page']
            self.max_page = self.page_count + max_page_count

    def json_dump(self):
        return json.dumps({'end_cursor': self.end_cursor, 'username': self.username, 'last_page': self.page_count,
                           'download_type': self.download_type, 'max_page': self.max_page})

    def prepare(self):
        print('getting info of', self.username)
        r = self.session.get(self.target_url)
        match = re.search(r"<script.*?>\s*?window._sharedData\s*?=\s*?({.*}).*?</script>", r.text, flags=re.MULTILINE)
        shared_data = json.loads(match.group(1))
        target_user = shared_data['entry_data']['ProfilePage'][0]['user']
        self.target_id = target_user['id']
        self.csrf_token = shared_data['config']['csrf_token']
        self.has_next = target_user['media']['page_info']['has_next_page']
        self.main_nodes = target_user['media']['nodes']
        if self.end_cursor is None:  # if the end_cursor was already set, don't use the new one
            self.end_cursor = target_user['media']['page_info']['end_cursor']

        # find the url of the javascript which contains the query id
        # pattern:
        # <script type="text/javascript" src="/static/bundles/en_US_Commons.js/97a256f04378.js" crossorigin="anonymous"></script>
        match = re.search(r"<script.*?Commons\.js/(.*js)", r.text)
        js_name = match.group(1)
        # get the javascript
        r = self.session.get(self.SCRIPT_URL + js_name)
        # find out the query id
        match = re.findall(r'queryId:"(\d+)"', r.text)
        self.query_id = match[-1]

    def download(self):
        print('starting...')
        if self.page_count == 0:
            print('downloading page', self.page_count + 1)
            for node in self.main_nodes:
                is_video = node['is_video']
                if not ((is_video and self.download_type == self.TYPE_PHOTO) or (
                            not is_video and self.download_type == self.TYPE_VIDEO)):
                    self.downloader.download(self.username, node['code'])
            self.page_count += 1

        while self.page_count < self.max_page and self.has_next:
            print('downloading page', self.page_count + 1)
            query_data = {"query_id": self.query_id,
                          "id": self.target_id,
                          "first": 12,
                          "after": self.end_cursor}
            r = self.session.get(self.QUERY_URL, params=query_data)
            more = json.loads(r.text)
            if more['data']['user'] is None:
                print('no more data')
                exit(0)
            media = more['data']['user']['edge_owner_to_timeline_media']
            self.has_next = media['page_info']['has_next_page']
            self.end_cursor = media['page_info']['end_cursor']
            nodes = media['edges']
            for node in nodes:
                node = node['node']
                is_video = node['is_video']
                if not ((is_video and self.download_type == self.TYPE_PHOTO) or (
                            not is_video and self.download_type == self.TYPE_VIDEO)):
                    self.downloader.download(self.username, node['shortcode'])
            self.page_count += 1

        if self.page_count < self.max_page and not self.has_next:
            print("no more pages.")
        print('done. exiting...')

    def close(self):
        self.session.close()
        self.downloader.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download the photos and videos from an instagram user's page")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-C', '--Continue', action='store_true', help='continue the last download task.')
    group.add_argument('-A', '--After', action='store_true', help='download posts after the last downloaded post')
    group.add_argument('-u', '--username', help='the username')
    parser.add_argument('-m', '--maxPageCount', type=int, default=9999,
                        help='the maximum number of pages that you want to download. default 9999')
    parser.add_argument('-t', '--downloadType', choices=[Spider.TYPE_BOTH, Spider.TYPE_PHOTO, Spider.TYPE_VIDEO],
                        default=Spider.TYPE_BOTH, help='the download type')
    parser.add_argument('-S', '--AutoStop',action='store_true',help='Stop the program automatically when it first sees a already downloaded file.')
    args = parser.parse_args()

    username = args.username
    max_page_count = args.maxPageCount
    dtype = args.downloadType
    after = None
    auto_stop = args.AutoStop
    if args.Continue:
        if os.path.isfile('ig_spider.meta'):
            with open('ig_spider.meta', 'r') as f:
                meta = json.loads(f.read())
            username = meta['username']
            max_page = int(meta['max_page'])
            last_page = int(meta['last_page'])
            max_page_count = max_page - last_page
            dtype = meta['download_type']
            after = {'end_cursor': meta['end_cursor'], 'last_page': last_page}
        else:
            print('can not find ig_spider.meta under', os.getcwd())
            exit(0)
    if args.After:
        if os.path.isfile('ig_spider.meta'):
            with open('ig_spider.meta', 'r') as f:
                meta = json.loads(f.read())
            last_page = int(meta['last_page'])
            after = {'end_cursor': meta['end_cursor'], 'last_page': last_page}
            username = meta['username']
        else:
            print('can not find ig_spider.meta under', os.getcwd())
            exit(0)

    if username is None:
        print('Please provide a username')
        exit(0)

    s = Spider(username, max_page_count, dtype, after, auto_stop)
    try:
        s.prepare()
        s.download()
    except KeyboardInterrupt:
        print("shutting down")
    except KeyError:
        print('KeyError:', 'Make sure you give the correct username', file=sys.stderr)
    except requests.RequestException as e:
        print('A network error occurred, please retry', file=sys.stderr)
        print(e, file=sys.stderr)
    except SystemExit:
        pass
    finally:
        s.close()
        print('Downloaded', s.item_count, 'items')
        with open('ig_spider.meta', 'w') as f:
            meta = s.json_dump()
            f.write(meta)
            print('ig_spider.meta was saved')
