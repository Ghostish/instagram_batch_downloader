import requests
import re
import json
import os, sys
from  getopt import getopt


def progress(curr, total):
    percentage = min(curr * 100 // total, 100)
    curr = min(curr, total)
    sys.stdout.write('\r')
    sys.stdout.write("[%-100s] %d%% %d/%d" % ('=' * percentage, percentage, curr, total))
    if percentage == 100:
        sys.stdout.write('\n')
    sys.stdout.flush()


class Spider:
    TYPE_VIDEO = 1
    TYPE_PHOTO = 2
    TYPE_BOTH = 3
    BASE_URL = 'https://www.instagram.com'
    QUERY_URL = BASE_URL + '/graphql/query/'
    SCRIPT_URL = BASE_URL + "/static/bundles/en_US_Commons.js/"

    class Downloader:
        def __init__(self):
            self.session = requests.Session()

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
                    print('file', filename, "already exists, skipping")
                else:
                    print('downloading %s:' % (filename))
                    r = self.session.get(url, stream=True)
                    content_length = int(r.headers['content-length'])
                    curr = 0
                    with open(temp_name, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            f.write(chunk)
                            curr += 1024
                            progress(curr, content_length)
                    os.rename(temp_name, filename)

        def close(self):
            self.session.close()

    def __init__(self, username, max_page_count, download_type, after):
        self.session = requests.Session()
        self.max_page = max_page_count
        self.username = username
        self.download_type = download_type
        self.page_count = 0
        self.target_url = self.BASE_URL + '/' + username
        self.downloader = self.Downloader()
        self.prepare()
        if after is not None:
            self.end_cursor = after['end_cursor']
            self.page_count = int(after['last_page'])
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
        self.end_cursor = target_user['media']['page_info']['end_cursor']
        self.main_nodes = target_user['media']['nodes']
        match = re.search(r"<script.*?Commons\.js/(.*js)", r.text)
        js_name = match.group(1)
        r = self.session.get(self.SCRIPT_URL + js_name)
        match = re.search(r'ye="(\d+)"', r.text)
        self.query_id = match.group(1)

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


if __name__ == '__main__':
    opts, args = getopt(sys.argv[1:], 'Cu:m:t:A')
    max_page_count = 9999
    dtype = Spider.TYPE_BOTH
    end_cursor = None
    username = None
    after = None
    for op, val in opts:
        if op == '-u':
            if username is None:  # make sure username is not set in meta file
                username = val
        if op == '-m':
            max_page_count = int(val)
        if op == '-t':
            dtype = int(val)
        if op == '-A':
            if os.path.isfile('ig_spider.meta'):
                with open('ig_spider.meta', 'r') as f:
                    meta = json.loads(f.read())
                after = {'end_cursor': meta['end_cursor'], 'last_page': meta['last_page']}
                username = meta['username']
            else:
                print('can not find ig_spider.meta under', os.getcwd())
                exit(0)
        if op == '-C':
            if os.path.isfile('ig_spider.meta'):
                with open('ig_spider.meta', 'r') as f:
                    meta = json.loads(f.read())
                username = meta['username']
                max_page_count = int(meta['max_page'])
                dtype = int(meta['download_type'])
                after = {'end_cursor': meta['end_cursor'], 'last_page': meta['last_page']}
                break
            else:
                print('can not find ig_spider.meta under', os.getcwd())
                exit(0)
    s = Spider(username, max_page_count, dtype, after)
    try:
        s.download()
    except KeyboardInterrupt:
        print("shutting down")
    finally:
        with open('ig_spider.meta', 'w') as f:
            meta = s.json_dump()
            f.write(meta)
            print('ig_spider.meta was saved')
