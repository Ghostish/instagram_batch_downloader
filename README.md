# instagram_batch_downloader
A python script which allows you to download all the photos and video from an instagram user's page.


## Dependencies
+ [python3]
+ [requests]

## usage:
+ -u username  
    The username. eg: NASA, adidas

+ -t download_type  
    A short string which indicates the download_type.   
    Should be one of 'video', 'photo' and 'both' (case insensitive)  
    The default value is 'both'.

+ -m max_page_count:  
    The maximum number of pages that you want to download.  
    The default value is 9999.  
    Normally each page contains 12 files

+ -C  
    Continue the last download. If -C is given, all the other arguments will be ignored.

+ -A  
    Download posts after the last download, Similiar to -C, but allow you to reconfig -t and -m
+ -S   
    Stop the program automatically when seeing an already downloaded file the first time.

+ -d path:
    the dirctory which you want to saving your downloads. defalut current dirctory("./").
## examples:
```python
python3 go_spider.py -u nasa -m 5 -t video
```

```python
python3 go_spider.py -C
```

```python
mkdir instagram
python3 go_spider.py -u nasa -m 5 -t video -d ./instagram
```

## docker:
```
docker build -t instagram_downloader .
docker run -it --rm -v /path/to/save/downloads:/downloads instagram_downloader -u nasa -m 5 -t video
```

## LICENSE

       Copyright 2017 Kangel Zenn(Ghostish)
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
        http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

[requests]:https://github.com/kennethreitz/requests
[python3]:https://www.python.org/